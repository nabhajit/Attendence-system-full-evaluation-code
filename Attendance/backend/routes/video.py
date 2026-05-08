"""
Video Upload Router
Handles teacher-uploaded classroom recordings for automated attendance.
"""
import os
import sys
import shutil
import time
import cv2
import torch
import numpy as np
import pathlib
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from ..auth_utils import require_role
from ..database import attendance_collection, students_collection
from .. import env_loader

_attendance_dir = pathlib.Path(__file__).parent.parent.parent
_model_dir = _attendance_dir / "model"
UPLOAD_DIR = _attendance_dir / "backend" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/admin/video", tags=["Video Processing"])
admin_dep = Depends(require_role(["admin", "teacher"]))

# Helper: Add model directory to path for imports
if str(_model_dir) not in sys.path:
    sys.path.insert(0, str(_model_dir))

# Lazy-load utilities from cctv_attendance
from cctv_attendance import (
    load_models, load_database, recognize, upscale_face, mark_attendance as db_mark_attendance
)

def process_video_task(video_path: str):
    """Background task to process video and log attendance."""
    print(f"🚀 Started processing video: {video_path}")
    
    try:
        # 1. Initialize models and DB
        yolo, facenet, mtcnn, device = load_models()
        db = load_database()
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"❌ Cannot open video file: {video_path}")
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        print(f"🎞️ Video loaded: {total_frames} frames @ {fps} FPS")

        cooldown_map = {}
        processed_count = 0
        
        # Frame skipping - process 1 frame every 0.5 seconds for efficiency
        # This ensures we catch students but don't melt the CPU
        skip_frames = max(1, int(fps * 0.5))
        
        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_idx % skip_frames == 0:
                # Same logic as cctv_attendance.py
                results = yolo(frame, verbose=False, classes=[0])
                boxes = results[0].boxes
                
                if boxes is not None:
                    for box in boxes:
                        conf = float(box.conf[0])
                        if conf < 0.4: continue
                        
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        bw, bh = x2-x1, y2-y1
                        
                        # Use CCTV upscale logic
                        H, W = frame.shape[:2]
                        margin = max(5, int(min(bw, bh) * 0.1))
                        cx1, cy1 = max(0, x1-margin), max(0, y1-margin)
                        cx2, cy2 = min(W, x2+margin), min(H, y2+margin)
                        
                        face_crop = frame[cy1:cy2, cx1:cx2]
                        if face_crop.size == 0: continue
                        
                        face_up = upscale_face(face_crop, target_size=160)
                        
                        # Recognition
                        (name, roll), score = recognize(face_up, db, facenet, device)
                        
                        if roll and roll != "Unknown":
                            import calendar
                            from database import timetables_collection, enrollments_collection
                            
                            now = datetime.now()
                            day_name = calendar.day_name[now.weekday()]
                            current_time_str = now.strftime("%H:%M")
                            
                            active_tt = None
                            for tt in timetables_collection.find({"day": day_name}):
                                if tt["start_time"] <= current_time_str <= tt["end_time"]:
                                    active_tt = tt
                                    break
                                    
                            is_enrolled = False
                            if active_tt:
                                course_code = active_tt.get("course_code")
                                section = active_tt.get("section")
                                enrollment = enrollments_collection.find_one({"course_code": course_code, "section": section})
                                if enrollment and roll in enrollment.get("roll_numbers", []):
                                    is_enrolled = True
                            else:
                                print(f"⚠️ No active class scheduled right now. Skipping {name} ({roll}).")
                                    
                            if is_enrolled:
                                # Pass course_code and section for class-specific attendance
                                if db_mark_attendance(roll, name, cooldown_map, confidence=score, course_code=course_code, section=section):
                                    processed_count += 1
            
            frame_idx += 1
            
        cap.release()
        print(f"✅ Video processing complete. Found {processed_count} unique student sessions.")
        
    except Exception as e:
        print(f"❌ Error processing video {video_path}: {e}")
    finally:
        # Cleanup temp file
        if os.path.exists(video_path):
            os.remove(video_path)
            print(f"🧹 Temporary video file removed: {video_path}")

@router.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = admin_dep
):
    """Endpoint to upload a video file for background processing."""
    if not file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
        raise HTTPException(status_code=400, detail="Invalid video format. Use .mp4, .avi, or .mov")

    file_save_path = UPLOAD_DIR / f"upload_{int(time.time())}_{file.filename}"
    
    with open(file_save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Start background task
    background_tasks.add_task(process_video_task, str(file_save_path))
    
    return {
        "message": "Video uploaded successfully. Processing has started in the background.",
        "filename": file.filename,
        "status": "processing"
    }
