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
    """
    Send a password reset email. 
    Tries Brevo API (recommended), then Resend, then Gmail SMTP fallback.
    """
    import urllib.request
    import json
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    # Load configuration
def _send_reset_email(to_email: str, token: str) -> bool:
    """
    Send a password reset email. 
    Tries Brevo API (recommended), then Resend, then Gmail SMTP fallback.
    """
    import urllib.request
    import json
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    # Load configuration - check both names for the API key
    brevo_api_key = (os.getenv("BREVO_API_KEY") or os.getenv("BREVO_API") or "").strip()
    resend_api_key = (os.getenv("RESEND_API_KEY") or os.getenv("RESEND_API") or "").strip()
    
    smtp_email = os.getenv("SMTP_EMAIL", "roynabhajit@gmail.com")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    
    reset_link = f"{frontend_url}/reset-password?token={token}"

    # Premium Email Template
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            .email-container {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #0f172a 0%, #3b82f6 100%);
                padding: 40px 20px;
                text-align: center;
                color: white;
            }}
            .content {{
                padding: 40px;
                color: #334155;
                line-height: 1.6;
            }}
            .button {{
                display: inline-block;
                padding: 16px 36px;
                background-color: #2563eb;
                color: #ffffff !important;
                text-decoration: none;
                border-radius: 8px;
                font-weight: bold;
                margin: 30px 0;
                box-shadow: 0 4px 10px rgba(37,99,235,0.2);
            }}
            .footer {{
                background-color: #f8fafc;
                padding: 20px;
                text-align: center;
                font-size: 12px;
                color: #94a3b8;
            }}
        </style>
    </head>
    <body style="background-color: #f1f5f9; padding: 20px;">
        <div class="email-container">
            <div class="header">
                <h1 style="margin: 0; font-size: 28px;">🔐 Password Reset</h1>
                <p style="margin-top: 10px; opacity: 0.9;">Smart Attendance Platform</p>
            </div>
            <div class="content">
                <h2 style="color: #1e293b;">Hello,</h2>
                <p>We received a request to reset the password for your Smart Attendance account. No changes have been made yet.</p>
                <p>You can reset your password by clicking the secure button below:</p>
                
                <div style="text-align: center;">
                    <a href="{reset_link}" class="button">Reset My Password</a>
                </div>
                
                <p style="font-size: 14px; color: #64748b;">
                    <strong>Note:</strong> This link will expire in 15 minutes for your security. 
                    If you did not request this, please ignore this email or contact support.
                </p>
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;">
                <p style="font-size: 13px;">Best regards,<br>The Smart Attendance Team</p>
            </div>
            <div class="footer">
                <p>This is an automated message, please do not reply.</p>
                <p>&copy; 2024 Smart Attendance System. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    # --- METHOD 1: BREVO API (Recommended) ---
    if brevo_api_key:
        print(f"Trying Brevo API with key: {brevo_api_key[:10]}...")
        payload = json.dumps({
            "sender": {"name": "Smart Attendance", "email": smtp_email},
            "to": [{"email": to_email}],
            "subject": "🔐 Password Reset — Smart Attendance System",
            "htmlContent": html_body
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=payload,
            headers={
                "api-key": brevo_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201, 202):
                    print(f"✅ Success: Email sent via Brevo to {to_email}")
                    return True
                print(f"⚠️ Brevo returned status: {resp.status}")
        except Exception as e:
            print(f"❌ Brevo API failed: {e}")

    # --- METHOD 2: RESEND API ---
    if resend_api_key:
        print(f"Trying Resend for: {to_email}")
        payload = json.dumps({
            "from": "onboarding@resend.dev",
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
                    print(f"✅ Success: Email sent via Resend to {to_email}")
                    return True
        except Exception as e:
            print(f"❌ Resend failed: {e}")

    # --- METHOD 3: SMTP FALLBACK ---
    if smtp_email and smtp_password:
        print(f"Trying SMTP fallback for: {to_email}")
        try:
            msg = MIMEMultipart()
            msg["Subject"] = "🔐 Password Reset — Smart Attendance System"
            msg["From"] = f"Smart Attendance <{smtp_email}>"
            msg["To"] = to_email
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_email, smtp_password)
                server.send_message(msg)
                print(f"✅ Success: Email sent via SMTP to {to_email}")
                return True
        except Exception as e:
            print(f"❌ SMTP fallback failed: {e}")

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
