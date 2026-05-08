from fastapi import APIRouter, HTTPException, Depends
from ..models import UserRegister, UserLogin, ForgotPasswordRequest, ResetPasswordRequest
from ..auth_utils import get_password_hash, verify_password, create_access_token
from ..database import users_collection, password_resets_collection
import secrets
import os
from datetime import datetime, timedelta
from .. import env_loader
router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register")
def register(user: UserRegister):
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    if user.roll_number and users_collection.find_one({"roll_number": user.roll_number}):
        raise HTTPException(status_code=400, detail="Roll number already registered")
        
    # Password Complexity Enforcement
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")
    if not any(char.isdigit() for char in user.password):
        raise HTTPException(status_code=400, detail="Password must contain at least one number.")
    if not any(char.isalpha() for char in user.password):
        raise HTTPException(status_code=400, detail="Password must contain at least one letter.")
        
    user_dict = user.model_dump()
    user_dict["password_hash"] = get_password_hash(user_dict.pop("password"))
    user_dict["is_suspended"] = False
    
    # Security patch: force role to student to prevent privilege escalation via public UI.
    user_dict["role"] = "student"
    
    users_collection.insert_one(user_dict)
    return {"message": "User registered successfully"}

@router.post("/login")
def login(user: UserLogin):
    db_user = users_collection.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    if db_user.get("is_suspended", False):
        raise HTTPException(status_code=403, detail="Your account has been suspended")
        
    access_token = create_access_token(
        data={"sub": db_user["email"], "role": db_user["role"], "roll_number": db_user.get("roll_number")}
    )
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "role": db_user["role"],
        "name": db_user.get("name")
    }


# ─────────────────────────────────────────────────────────
# Forgot Password / Reset Password
# ─────────────────────────────────────────────────────────

def _send_reset_email(to_email: str, token: str) -> bool:
    """Send a password reset email via Resend HTTP API. Returns True on success, False on failure."""
    import urllib.request
    import json

    resend_api_key = os.getenv("RESEND_API_KEY") or os.getenv("RESEND_API")
    # Resend trial accounts require sending from onboarding@resend.dev
    from_email = "onboarding@resend.dev" 
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

    if not resend_api_key:
        print("🚨 RESEND_API_KEY missing — will return link directly.")
        return False

    reset_link = f"{frontend_url}/reset-password?token={token}"

    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 32px; background: #f8fafc; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #0f172a; font-size: 24px; margin: 0;">🔐 Password Reset</h1>
            <p style="color: #64748b; font-size: 14px; margin-top: 8px;">Smart Attendance System</p>
        </div>
        <div style="background: white; border-radius: 12px; padding: 28px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">
            <p style="color: #334155; font-size: 15px; line-height: 1.6; margin: 0 0 20px 0;">
                We received a request to reset your password. Click the button below to set a new one.
                This link is valid for <strong>15 minutes</strong>.
            </p>
            <div style="text-align: center; margin: 24px 0;">
                <a href="{reset_link}"
                   style="display: inline-block; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                          color: white; text-decoration: none; padding: 14px 36px; border-radius: 10px;
                          font-weight: bold; font-size: 15px; box-shadow: 0 4px 12px rgba(59,130,246,0.35);">
                    Reset My Password
                </a>
            </div>
            <p style="color: #94a3b8; font-size: 12px; line-height: 1.5; margin: 20px 0 0 0; text-align: center;">
                If you did not request this, you can safely ignore this email.<br/>
                Your password will remain unchanged.
            </p>
        </div>
        <p style="text-align: center; color: #cbd5e1; font-size: 11px; margin-top: 20px;">
            © Smart Attendance Platform
        </p>
    </div>
    """

    payload = json.dumps({
        "from": f"Smart Attendance <{from_email}>",
        "to": [to_email],
        "subject": "🔐 Password Reset — Smart Attendance System",
        "html": html_body
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 201, 202, 204):
                print(f"✅ Password reset email sent to {to_email} via Resend")
                return True
            print(f"❌ Resend API returned status: {resp.status}")
            return False
    except Exception as e:
        print(f"❌ Failed to send email via Resend: {e}")
        return False



@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest):
    """Generate a reset token and email it to the user."""
    user = users_collection.find_one({"email": request.email})

    # Always return success to prevent email enumeration attacks
    if not user:
        return {"message": "If an account with that email exists, a reset link has been sent."}

    # Generate a secure random token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    # Remove any existing tokens for this user
    password_resets_collection.delete_many({"email": request.email})

    # Store the new token
    password_resets_collection.insert_one({
        "email": request.email,
        "token": token,
        "expires_at": expires_at,
        "created_at": datetime.utcnow()
    })

    # Try to send the email; if network is blocked (e.g. HF Spaces), return link directly
    email_sent = _send_reset_email(request.email, token)

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    reset_link = f"{frontend_url}/reset-password?token={token}"

    if email_sent:
        return {"message": "A reset link has been sent to your email. Please check your inbox."}
    else:
        # Fallback: return the link directly so the user can still reset
        return {
            "message": "Email could not be sent automatically. Please use the link below to reset your password:",
            "reset_link": reset_link
        }


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest):
    """Verify the token and update the user's password."""
    # Find the token record
    reset_record = password_resets_collection.find_one({"token": request.token})
    
    if not reset_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    
    # Check expiry
    if datetime.utcnow() > reset_record["expires_at"]:
        password_resets_collection.delete_one({"token": request.token})
        raise HTTPException(status_code=400, detail="This reset link has expired. Please request a new one.")
    
    # Enforce password complexity
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")
    if not any(char.isdigit() for char in request.new_password):
        raise HTTPException(status_code=400, detail="Password must contain at least one number.")
    if not any(char.isalpha() for char in request.new_password):
        raise HTTPException(status_code=400, detail="Password must contain at least one letter.")
    
    # Update the password
    new_hash = get_password_hash(request.new_password)
    result = users_collection.update_one(
        {"email": reset_record["email"]},
        {"$set": {"password_hash": new_hash}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Password update failed.")
    
    # Invalidate the token
    password_resets_collection.delete_many({"email": reset_record["email"]})
    
    return {"message": "Password reset successfully! You can now log in with your new password."}
