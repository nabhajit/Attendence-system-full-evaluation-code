import os
import io
import sys
import numpy as np
import cloudinary
import cloudinary.uploader
import torch
from PIL import Image
from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi import HTTPException
from typing import List
from dotenv import load_dotenv
from ..database import students_collection, users_collection
from ..auth_utils import require_role, get_password_hash
import pathlib
from .. import env_loader
from datetime import datetime
import calendar
from ..database import timetables_collection, enrollments_collection
# face_register.py is 3 levels deep: Attendence/backend/routes/face_register.py
_attendence_dir = pathlib.Path(__file__).parent.parent.parent
_model_dir = _attendence_dir / "model"

# Configure Cloudinary from the now-loaded environment
_cloud_url = os.getenv("CLOUDINARY_URL")
if not _cloud_url:
    print("⚠️  WARNING: CLOUDINARY_URL not found in root .env file!")
else:
    print(f"✅ Cloudinary configured successfully.")
cloudinary.config(cloudinary_url=_cloud_url)
import time
from fastapi import Request

# Simple in-memory rate limiter: {ip: [timestamps]}
_registration_attempts = {}

def check_rate_limit(request: Request):
    """Dependency to prevent spamming registration endpoints."""
    # Allow 5 attempts per 10 minutes per IP
    limit = 5
    window = 600 # seconds
    
    ip = request.client.host
    now = time.time()
    
    # Cleanup old attempts
    attempts = [t for t in _registration_attempts.get(ip, []) if now - t < window]
    
    if len(attempts) >= limit:
        raise HTTPException(
            status_code=429, 
            detail="Too many registration attempts. Please wait 10 minutes."
        )
    
    attempts.append(now)
    _registration_attempts[ip] = attempts
    return True

router = APIRouter(prefix="/admin/face", tags=["Face Registration"])

# Lazy-load heavy models to avoid slowing server startup
_mtcnn = None
_facenet = None
_device = None

def get_models():
    global _mtcnn, _facenet, _device
    if _mtcnn is None:
        # Add model/ directory to path so mongo_manager can be imported
        if str(_model_dir) not in sys.path:
            sys.path.insert(0, str(_model_dir))
        
        from facenet_pytorch import MTCNN, InceptionResnetV1
        _device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        _mtcnn = MTCNN(keep_all=False, device=_device, min_face_size=40)
        _facenet = InceptionResnetV1(pretrained='vggface2').eval().to(_device)
        print("✅ FaceNet models loaded for web-based registration.")
    
    return _mtcnn, _facenet, _device


async def compute_refined_embedding(images: List[UploadFile], name: str, roll_number: str):
    """Helper to process images, upload to Cloudinary, and return refined embedding."""
    if len(images) < 5:
        raise HTTPException(status_code=400, detail="Please provide at least 5 face images for accurate recognition.")
    
    mtcnn, facenet, device = get_models()
    
    cloudinary_urls = []
    all_embeddings = []
    processed = 0
    failed = 0

    for i, uploaded_file in enumerate(images):
        # Reset file pointer if needed
        await uploaded_file.seek(0)
        image_bytes = await uploaded_file.read()
        
        try:
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            face_tensor = mtcnn(pil_img)
            
            if face_tensor is None:
                failed += 1
                continue
            
            face_tensor = face_tensor.unsqueeze(0).to(device)
            with torch.no_grad():
                embedding = facenet(face_tensor)
            
            embedding_np = embedding.cpu().numpy().flatten()
            embedding_np = embedding_np / np.linalg.norm(embedding_np)
            all_embeddings.append(embedding_np)
            
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                image_bytes,
                folder=f"attendance/{roll_number}_{name}",
                public_id=f"img_{i+1}_{int(time.time())}", # unique public id
                resource_type="image"
            )
            cloudinary_urls.append(result['secure_url'])
            processed += 1
        
        except Exception as e:
            print(f"Error processing image {i+1}: {e}")
            failed += 1
            continue
    
    if not all_embeddings:
        raise HTTPException(
            status_code=422,
            detail="No valid faces detected in any of the uploaded images. Please try again with better lighting."
        )
    
    # Robust averaging logic
    embeddings_np = np.array(all_embeddings)
    if len(embeddings_np) > 3:
        centroid = np.mean(embeddings_np, axis=0)
        distances = np.linalg.norm(embeddings_np - centroid, axis=1)
        inlier_count = max(1, int(len(distances) * 0.8))
        inlier_indices = np.argsort(distances)[:inlier_count]
        avg_embedding = np.mean(embeddings_np[inlier_indices], axis=0)
    else:
        avg_embedding = np.mean(embeddings_np, axis=0)
        
    avg_embedding = avg_embedding / (np.linalg.norm(avg_embedding) + 1e-8)
    
    return avg_embedding.tolist(), cloudinary_urls, processed, failed


@router.post("/register")
async def register_student_face(
    name: str = Form(...),
    roll_number: str = Form(...),
    student_class: str = Form("Unknown"),
    contact: str = Form("N/A"),
    course: str = Form(""),
    email: str = Form(...),
    images: List[UploadFile] = File(...),
    user: dict = Depends(require_role(["admin", "superadmin"])),
    limit: bool = Depends(check_rate_limit)
):
    """
    Register a NEW student with biometric data.
    """
    # Check if student already exists
    existing = students_collection.find_one({"roll": roll_number})
    if existing:
        raise HTTPException(status_code=400, detail=f"Student with Roll Number '{roll_number}' already registered. Use 'Update' instead.")
    
    embedding, urls, processed, failed = await compute_refined_embedding(images, name, roll_number)
    
    # Save to MongoDB
    import importlib.util
    spec = importlib.util.spec_from_file_location("mongo_manager", _model_dir / "mongo_manager.py")
    mongo_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mongo_mod)
    db_manager = mongo_mod.MongoDatabaseManager()
    
    success = db_manager.add_student(
        name=name,
        student_class=student_class,
        roll=roll_number,
        contact=contact,
        course=course,
        cloudinary_urls=urls,
        embedding=embedding
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save to database.")
        
    # Extra: Save email to student document specifically
    students_collection.update_one({"roll": roll_number}, {"$set": {"email": email}})

    # Create Auth Account for Student with a UNIQUE password
    default_password = f"Student@{roll_number}"
    if not users_collection.find_one({"email": email}):
        user_data = {
            "name": name,
            "email": email,
            "password_hash": get_password_hash(default_password),
            "roll_number": roll_number,
            "role": "student",
            "is_suspended": False,
            "created_at": datetime.utcnow()
        }
        users_collection.insert_one(user_data)
        # Send Welcome Email
        _send_welcome_email(email, name, default_password)

    if course and student_class:
        from database import enrollments_collection
        enrollments_collection.update_one(
            {"course_code": course, "section": student_class},
            {"$addToSet": {"roll_numbers": roll_number}},
            upsert=True
        )
    
    return {
        "message": f"Student '{name}' registered and account created! Credentials sent to {email}.",
        "roll_number": roll_number,
        "images_processed": processed,
        "cloudinary_urls": urls[:3]
    }

def _send_welcome_email(to_email: str, name: str, password: str):
    """Send welcome email with hardcoded credentials."""
    import urllib.request
    import json
    
    brevo_api_key = (os.getenv("BREVO_API_KEY") or os.getenv("BREVO_API") or "").strip()
    smtp_email = os.getenv("SMTP_EMAIL", "roynabhajit@gmail.com")
    
    if not brevo_api_key:
        print("⚠️ No Brevo API key found. Welcome email skipped.")
        return

    html_body = f"""
    <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto; border: 1px solid #eee; border-radius: 10px; padding: 20px;">
        <h2 style="color: #2563eb;">Welcome to Smart Attendance System!</h2>
        <p>Hello <strong>{name}</strong>,</p>
        <p>Your student account has been created by the administration. You can now log in to track your attendance and view your timetable.</p>
        <div style="background: #f8fafc; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 0;"><strong>Login Email:</strong> {to_email}</p>
            <p style="margin: 5px 0 0 0;"><strong>Temporary Password:</strong> {password}</p>
        </div>
        <p style="font-size: 13px; color: #64748b;">Note: Please change your password after your first login for security.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; text-align: center; color: #94a3b8;">Smart Attendance Platform</p>
    </div>
    """

    payload = json.dumps({
        "sender": {"name": "Smart Attendance", "email": smtp_email},
        "to": [{"email": to_email}],
        "subject": "🎓 Welcome! Your Student Account Credentials",
        "htmlContent": html_body
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=payload,
        headers={"api-key": brevo_api_key, "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"✅ Welcome email sent to {to_email} (Status: {resp.status})")
    except Exception as e:
        print(f"❌ Failed to send welcome email: {e}")


@router.patch("/update")
async def update_student_face(
    roll_number: str = Form(...),
    images: List[UploadFile] = File(...),
    user: dict = Depends(require_role(["admin", "teacher", "superadmin"])),
    limit: bool = Depends(check_rate_limit)
):
    """
    UPDATE an existing student's biometric data (Re-enrollment).
    Does NOT require deletion first.
    """
    # Check if student exists
    student = students_collection.find_one({"roll": roll_number})
    if not student:
        raise HTTPException(status_code=404, detail=f"Student with Roll Number '{roll_number}' not found.")
    
    name = student.get("name")
    embedding, urls, processed, failed = await compute_refined_embedding(images, name, roll_number)
    
    # Update in MongoDB
    from database import students_collection
    result = students_collection.update_one(
        {"roll": roll_number},
        {"$set": {
            "embedding": embedding,
            "cloudinary_urls": urls,
            "updated_at": datetime.now()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Database update failed.")
    
    return {
        "message": f"Biometric data for student '{name}' updated successfully!",
        "roll_number": roll_number,
        "images_processed": processed
    }


@router.post("/recognize")
async def recognize_live_frame(
    file: UploadFile = File(...),
    user: dict = Depends(require_role(["admin", "teacher", "superadmin"]))
):
    """
    Identify a student from a single frame (browser webcam) and log attendance.
    """
    import importlib.util
    import cv2
    
    # 1. Load models and database (lazy-loaded)
    from cctv_attendance import load_database, recognize, upscale_face
    mtcnn, facenet, device = get_models()
    db = load_database()
    
    # 2. Process image
    image_bytes = await file.read()
    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    
    # 3. Detect and recognize
    face_tensor = mtcnn(pil_img)
    if face_tensor is None:
        return {"match": False, "message": "No face detected in frame."}
    
    # Recognition logic
    # Convert PIL image to BGR numpy array for the recognize function
    import cv2
    face_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    (name, roll), score = recognize(face_bgr, db, facenet, device)
    
    if roll and roll != "Unknown":
        # Check timetable and enrollments
        now = datetime.now()
        day_name = calendar.day_name[now.weekday()]
        current_time_str = now.strftime("%H:%M")
        
        active_tt = None
        for tt in timetables_collection.find({"day": day_name}):
            if tt["start_time"] <= current_time_str <= tt["end_time"]:
                active_tt = tt
                break
                
        if active_tt:
            course_code = active_tt.get("course_code")
            section = active_tt.get("section")
            # Verify enrollment
            enrollment = enrollments_collection.find_one({"course_code": course_code, "section": section})
            if not enrollment or roll not in enrollment.get("roll_numbers", []):
                return {
                    "match": False,
                    "message": f"{name} is not enrolled in the active class ({course_code} - Section {section})."
                }
        else:
            # Reject scan if no active class is scheduled
            return {
                "match": False,
                "message": f"No active class scheduled at this time. Scan rejected."
            }

        # 4. Mark attendance in MongoDB
        spec = importlib.util.spec_from_file_location("mongo_manager", _model_dir / "mongo_manager.py")
        mongo_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mongo_mod)
        db_manager = mongo_mod.MongoDatabaseManager()
        
        # Modify mark_attendance if needed, or just keep it as is.
        success = db_manager.mark_attendance(roll, name, confidence=score, course_code=course_code, section=section)
        
        return {
            "match": True,
            "name": name,
            "roll": roll,
            "confidence": score,
            "attendance_logged": success,
            "message": f"Recognized: {name} for {course_code}" if success else f"{name} (Attendance already marked for {course_code})"
        }
    
    return {
        "match": False,
        "score": float(score),
        "message": f"Student not recognized (Score: {score:.2f})"
    }


