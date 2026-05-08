"""
CCTV Attendance System
======================
Designed for wall-mounted CCTV cameras where faces appear SMALL.

Key features:
  • Auto-upscales tiny face crops (bicubic + CLAHE contrast boost)
  • Multi-frame voting — ignores single-frame false positives
  • Works with webcam index OR RTSP / HTTP stream URL
  • Logs to CSV (attendance_log.csv)

Usage:
  python cctv_attendance.py                  # webcam 0
  python cctv_attendance.py --source 1       # webcam 1
  python cctv_attendance.py --source rtsp://192.168.1.100/stream
  python cctv_attendance.py --scale 200      # upscale target px (default 160)
"""

import cv2
import numpy as np
import argparse
import time
import os
import pickle
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter

import torch
from ultralytics import YOLO
from facenet_pytorch import InceptionResnetV1, MTCNN
from sklearn.decomposition import PCA
import faiss
import pandas as pd
from mongo_manager import MongoDatabaseManager

# ─────────────────────────────────────────────────────────────
# Shared utility: upscale a small face crop for better matching
# ─────────────────────────────────────────────────────────────

def upscale_face(face_bgr: np.ndarray, target_size: int = 160) -> np.ndarray:
    """
    Enlarge a small face crop to `target_size` pixels on the shortest edge.
    Applies bicubic interpolation + CLAHE contrast enhancement.

    Args:
        face_bgr:    BGR face crop (any size).
        target_size: Minimum side length of the output image (px).

    Returns:
        Upscaled BGR image. If the crop is already >= target_size, a CLAHE-
        enhanced copy is returned without rescaling.
    """
    if face_bgr is None or face_bgr.size == 0:
        return face_bgr

    h, w = face_bgr.shape[:2]
    min_side = min(h, w)

    if min_side < target_size:
        scale = target_size / min_side
        new_w = int(w * scale)
        new_h = int(h * scale)
        face_bgr = cv2.resize(face_bgr, (new_w, new_h),
                              interpolation=cv2.INTER_CUBIC)

    # CLAHE on luminance channel — improves contrast for dark / backlit faces
    lab = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    l_ch = clahe.apply(l_ch)
    lab = cv2.merge([l_ch, a_ch, b_ch])
    face_bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    return face_bgr


# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

ROOT               = os.path.dirname(os.path.abspath(__file__))
YOLO_WEIGHTS       = os.path.join(ROOT, "yolov8n.pt")
DATABASE_PATH      = os.path.join(ROOT, "face_database.pkl")
ATTENDANCE_LOG     = os.path.join(ROOT, "attendance_log.csv")

# Detection
YOLO_CONFIDENCE    = 0.35   # lower than default — catches far-away people
MIN_FACE_PX        = 30     # minimum bounding-box side length to attempt recognition
UPSCALE_TARGET     = 160    # pixels — faces smaller than this will be upscaled

# Recognition
SIMILARITY_THRESHOLD = 0.55  # slightly lower for upscaled faces

# Attendance
COOLDOWN_SECONDS   = 300     # 5 minutes between re-logging same person
VOTE_FRAMES        = 5       # frames a name must appear before being logged
VOTE_MAJORITY      = 3       # how many of those must agree
# Initialize Database Manager
db_manager = MongoDatabaseManager()
# ─────────────────────────────────────────────────────────────
# Model loading
# ─────────────────────────────────────────────────────────────

def load_models():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"📱 Device: {device}")

    print("📦 Loading YOLO…")
    yolo = YOLO(YOLO_WEIGHTS)

    print("📦 Loading FaceNet…")
    facenet = InceptionResnetV1(pretrained="vggface2").eval().to(device)

    print("📦 Loading MTCNN…")
    mtcnn = MTCNN(image_size=160, margin=0, keep_all=False, device=device)

    return yolo, facenet, mtcnn, device


def load_database():
    if not os.path.exists(DATABASE_PATH):
        print(f"⚠️ Database not found at {DATABASE_PATH}. Attempting to rebuild from MongoDB...")
        try:
            return rebuild_database()
        except Exception as e:
            print(f"❌ Failed to rebuild database: {e}")
            sys.exit(1)

    with open(DATABASE_PATH, "rb") as f:
        db = pickle.load(f)

    if db.get("faiss_index") is None:
        print("⚠️ Database is empty. Attempting to rebuild...")
        return rebuild_database()

    count = len(db.get('rolls', db['names']))
    print(f"✅ Database loaded — {count} users.")
    return db


def rebuild_database():
    """Reconstruct the face database from MongoDB data."""
    print("🔄 Rebuilding face database from MongoDB...")
    students = db_manager.get_all_students()
    
    if not students:
        print("⚠️ No students found in MongoDB. Database will be empty.")
        return {"names": [], "rolls": [], "embeddings": [], "faiss_index": None, "pca_model": None}

    all_embeddings = []
    all_names = []
    all_rolls = []

    for s in students:
        name = s.get("name")
        roll = s.get("roll")
        # Check if student already has a pre-computed embedding in MongoDB
        emb = s.get("embedding")
        
        if emb:
            all_embeddings.append(np.array(emb, dtype="float32"))
            all_names.append(name)
            all_rolls.append(roll)
        else:
            # Skip for now if no embedding exists (they should have one if registered via FaceRegistrationModal)
            print(f"  ⏭️ Skipping {name} ({roll}) - No embedding found in MongoDB.")

    if not all_embeddings:
        print("❌ No valid embeddings found for any student.")
        return {"names": [], "rolls": [], "embeddings": [], "faiss_index": None, "pca_model": None}

    embeddings_np = np.array(all_embeddings).astype("float32")
    
    # Simple PCA — reduce dimensions to 128 if we have enough samples, else use original size
    n_samples = embeddings_np.shape[0]
    n_features = embeddings_np.shape[1]
    n_components = min(n_samples, 128)
    
    pca = PCA(n_components=n_components)
    embeddings_reduced = pca.fit_transform(embeddings_np).astype("float32")
    
    # Build FAISS index
    index = faiss.IndexFlatIP(n_components)
    faiss.normalize_L2(embeddings_reduced)
    index.add(embeddings_reduced)

    db = {
        "names": all_names,
        "rolls": all_rolls,
        "embeddings": all_embeddings,
        "faiss_index": index,
        "pca_model": pca
    }

    # Save to disk for future calls in this session
    with open(DATABASE_PATH, "wb") as f:
        pickle.dump(db, f)

    print(f"✅ Database successfully rebuilt with {len(all_names)} students.")
    return db


# ─────────────────────────────────────────────────────────────
# Recognition
# ─────────────────────────────────────────────────────────────

def extract_embedding(face_bgr, facenet, device):
    """Extract 512-D FaceNet embedding from a BGR face crop."""
    try:
        face_rgb   = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        face_res   = cv2.resize(face_rgb, (160, 160))
        tensor     = torch.from_numpy(face_res).permute(2, 0, 1).float()
        tensor     = (tensor - 127.5) / 128.0
        tensor     = tensor.unsqueeze(0).to(device)
        with torch.no_grad():
            emb = facenet(tensor).cpu().numpy().flatten()
        emb = emb / (np.linalg.norm(emb) + 1e-8)
        return emb.astype("float32")
    except Exception:
        return None


def recognize(face_bgr, db, facenet, device, threshold=SIMILARITY_THRESHOLD):
    """Recognise a face. Returns (name, confidence) or (None, score)."""
    if db["faiss_index"] is None:
        return None, 0.0

    emb = extract_embedding(face_bgr, facenet, device)
    if emb is None:
        return None, 0.0

    emb_r = db["pca_model"].transform(emb.reshape(1, -1)).astype("float32")
    emb_r = np.ascontiguousarray(emb_r)
    faiss.normalize_L2(emb_r)

    D, I = db["faiss_index"].search(emb_r, k=1)
    score = float(D[0][0])
    idx   = int(I[0][0])

    if score >= threshold:
        roll = db.get("rolls", db["names"])[idx]
        name = db["names"][idx]
        return (name, roll), score
    return (None, None), score


# ─────────────────────────────────────────────────────────────
# Attendance logging
# ─────────────────────────────────────────────────────────────

def mark_attendance(roll: str, name: str, cooldown_map: dict, confidence: float = None, course_code: str = "Unknown", section: str = "Unknown") -> bool:
    now_ts = time.time()
    # Use roll + course_code for unique cooldown per class
    identifier = f"{roll}_{course_code}" 
    if identifier in cooldown_map and now_ts - cooldown_map[identifier] < COOLDOWN_SECONDS:
        return False  # still in cooldown

    now_dt  = datetime.now()
    date_s  = now_dt.strftime("%Y-%m-%d")
    time_s  = now_dt.strftime("%H:%M:%S")

    # Sync to MongoDB for Dashboard integration
    db_manager.mark_attendance(roll, name, confidence=confidence, course_code=course_code, section=section)

    if os.path.exists(ATTENDANCE_LOG):
        df = pd.read_csv(ATTENDANCE_LOG)
    else:
        df = pd.DataFrame(columns=["Name", "Date", "Time", "Course"])

    # Deduplicate within the same day using Roll and Course
    if not df[(df["Roll"] == roll) & (df["Date"] == date_s) & (df.get("Course", "") == course_code)].empty:
        cooldown_map[identifier] = now_ts
        return False

    new_row = pd.DataFrame([{"Name": name, "Roll": roll, "Date": date_s, "Time": time_s, "Course": course_code}])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(ATTENDANCE_LOG, index=False)
    cooldown_map[identifier] = now_ts
    print(f"  ✅ Attendance marked: {name} [Roll: {roll}] ({time_s}) - Class: {course_code}")
    return True


# ─────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────

def run_cctv(source=0, upscale_target=UPSCALE_TARGET, confidence=YOLO_CONFIDENCE):
    print("\n" + "=" * 65)
    print("📷  CCTV ATTENDANCE SYSTEM  — CCTV / Wide-angle mode")
    print("=" * 65)

    yolo, facenet, mtcnn, device = load_models()
    db = load_database()

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"❌ Cannot open source: {source}")
        return

    # Try to set a reasonable resolution (CCTV streams may ignore this)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,  720)

    print(f"\n🎥 Stream opened  |  upscale target = {upscale_target}px")
    print("   Press 'q' to quit, 's' for screenshot\n")

    cooldown_map: dict  = {}
    vote_buffer:  dict  = {}   # person-position -> deque of names
    frame_count   = 0
    t_fps         = time.time()
    fps           = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️  Frame read failed — retrying…")
                time.sleep(0.1)
                continue

            frame_count += 1
            display      = frame.copy()
            now_ts       = time.time()

            # FPS calculation
            if frame_count % 30 == 0:
                fps     = 30 / (now_ts - t_fps + 1e-6)
                t_fps   = now_ts

            # ── YOLO detection (every frame for CCTV accuracy) ──────
            results = yolo(frame, verbose=False, classes=[0])  # class 0 = person
            boxes   = results[0].boxes

            active_ids: set = set()

            if boxes is not None and len(boxes) > 0:
                for box in boxes:
                    conf = float(box.conf[0])
                    if conf < confidence:
                        continue

                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    bw, bh = x2 - x1, y2 - y1

                    # Skip boxes too small even after expansion (noise)
                    if bw < MIN_FACE_PX or bh < MIN_FACE_PX:
                        continue

                    # ── Crop & upscale ───────────────────────────────
                    H, W = frame.shape[:2]
                    margin = max(5, int(min(bw, bh) * 0.08))
                    cx1 = max(0, x1 - margin)
                    cy1 = max(0, y1 - margin)
                    cx2 = min(W, x2 + margin)
                    cy2 = min(H, y2 + margin)

                    face_crop = frame[cy1:cy2, cx1:cx2]
                    if face_crop.size == 0:
                        continue

                    face_up = upscale_face(face_crop, target_size=upscale_target)

                    # ── Recognition ──────────────────────────────────
                    (name, roll), score = recognize(face_up, db, facenet, device)

                    # ── Multi-frame voting ────────────────────────────
                    grid_key = f"{int((cx1+cx2)/2/80)}_{int((cy1+cy2)/2/80)}"
                    active_ids.add(grid_key)

                    if grid_key not in vote_buffer:
                        vote_buffer[grid_key] = []
                    
                    # Buffer the unique roll to avoid name collisions
                    vote_buffer[grid_key].append(roll or "Unknown")
                    vote_buffer[grid_key] = vote_buffer[grid_key][-VOTE_FRAMES:]

                    # Decide final label
                    counts      = Counter(vote_buffer[grid_key])
                    voted_roll, voted_count = counts.most_common(1)[0]
                    
                    voted_name = "Unknown"
                    if voted_roll != "Unknown":
                        # Find the name corresponding to this roll
                        idx = db.get("rolls", []).index(voted_roll) if "rolls" in db else -1
                        voted_name = db["names"][idx] if idx != -1 else "Unknown"

                    if voted_roll != "Unknown" and voted_count >= VOTE_MAJORITY:
                        mark_attendance(voted_roll, voted_name, cooldown_map, confidence=score)
                        color = (0, 220, 0)
                        label = f"{voted_name}  {score:.2f}"
                    else:
                        color = (0, 60, 220)
                        label = f"Unknown  {score:.2f}"

                    # ── Draw ─────────────────────────────────────────
                    cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)

                    # Tiny upscale preview in corner of bbox
                    ph = min(60, bh)
                    pw = int(ph * (face_up.shape[1] / face_up.shape[0]))
                    preview = cv2.resize(face_up, (pw, ph))
                    px1, py1 = x2 + 4, y1
                    px2, py2 = px1 + pw, py1 + ph
                    if px2 < W and py2 < H:
                        display[py1:py2, px1:px2] = preview
                        cv2.rectangle(display, (px1, py1), (px2, py2), color, 1)

                    # Label tag
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
                    cv2.rectangle(display, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
                    cv2.putText(display, label, (x1 + 2, y1 - 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

                    # Size hint
                    cv2.putText(display, f"{bw}x{bh}px → {upscale_target}px",
                                (x1, y2 + 16), cv2.FONT_HERSHEY_SIMPLEX,
                                0.42, (200, 200, 200), 1)

            # Clean stale vote buffers
            for k in list(vote_buffer):
                if k not in active_ids:
                    del vote_buffer[k]

            # ── HUD ─────────────────────────────────────────────────
            cv2.rectangle(display, (0, 0), (370, 48), (20, 20, 20), -1)
            cv2.putText(display, f"CCTV Attendance  |  FPS: {fps:.1f}",
                        (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 255, 200), 1)
            
            db_count = len(db.get('rolls', db['names']))
            cv2.putText(display,
                        f"Upscale target: {upscale_target}px  |  DB: {db_count} users",
                        (8, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

            cv2.imshow("CCTV Attendance", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("s"):
                ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
                fn  = f"cctv_screenshot_{ts}.jpg"
                cv2.imwrite(fn, display)
                print(f"📸 Screenshot saved: {fn}")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("\n✅ CCTV session ended.")


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CCTV Attendance System")
    parser.add_argument("--source",  default=0,
                        help="Camera index (0, 1…) or RTSP URL")
    parser.add_argument("--scale",   type=int, default=UPSCALE_TARGET,
                        help=f"Upscale target px (default {UPSCALE_TARGET})")
    parser.add_argument("--conf",    type=float, default=YOLO_CONFIDENCE,
                        help=f"YOLO confidence (default {YOLO_CONFIDENCE})")
    args = parser.parse_args()

    # Convert source to int if it looks like a number
    source = args.source
    try:
        source = int(source)
    except (ValueError, TypeError):
        pass

    run_cctv(source=source, upscale_target=args.scale, confidence=args.conf)
