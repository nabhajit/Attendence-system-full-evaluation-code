"""
Liveness Detection Module
Detects real person vs photo/screen using:

  Body Motion Detection (Optical Flow)
    1. Isolate the body region below the detected face (torso area)
    2. Detect good feature points (Shi-Tomasi) in the body ROI
    3. Track those points across consecutive frames with Lucas-Kanade Optical Flow
    4. Compute mean displacement vector across tracked points
    5. If displacement exceeds MOTION_THRESHOLD -> motion event recorded
    6. After M motion events -> body motion challenge PASSED

  LIVENESS CONFIRMED when body motion challenge is passed.

No extra dependencies — pure OpenCV + NumPy.
"""

import cv2
import numpy as np
import os
import time
from collections import deque

# ---------------------------------------------------------------
# Load bundled OpenCV Haar cascades (always available with cv2)
# ---------------------------------------------------------------
_cv2_data = os.path.join(os.path.dirname(cv2.__file__), "data")

_face_cascade = cv2.CascadeClassifier(
    os.path.join(_cv2_data, "haarcascade_frontalface_default.xml")
)

MEDIAPIPE_AVAILABLE = False  # kept for backwards-compat with app.py import


# ---------------------------------------------------------------
# Optical Flow Parameters
# ---------------------------------------------------------------
_LK_PARAMS = dict(
    winSize=(15, 15),
    maxLevel=2,
    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
)

_FEATURE_PARAMS = dict(
    maxCorners=80,
    qualityLevel=0.3,
    minDistance=7,
    blockSize=7,
)


# ---------------------------------------------------------------
# Body Motion Detector (Optical Flow Sub-module)
# ---------------------------------------------------------------

class BodyMotionDetector:
    """
    Detects body/torso motion using Lucas-Kanade sparse optical flow.

    Works on the region BELOW the face — so a printed photo held still
    will not satisfy this check, even if the attacker blinks the photo
    in some other way.

    Args:
        required_events   : Number of distinct motion events to confirm.
        motion_threshold  : Minimum mean pixel displacement to count
                            as a motion event (tune lower = more sensitive).
        event_cooldown_s  : Minimum seconds between counting two events
                            (prevents a single long motion from counting
                             multiple times).
        history_len       : Frames of displacement to smooth over.
    """

    def __init__(
        self,
        required_events: int = 2,
        motion_threshold: float = 3.5,
        event_cooldown_s: float = 0.8,
        history_len: int = 6,
    ):
        self.required_events  = required_events
        self.motion_threshold = motion_threshold
        self.event_cooldown_s = event_cooldown_s

        self._prev_gray:  np.ndarray | None = None
        self._prev_pts:   np.ndarray | None = None
        self._prev_shape: tuple | None = None   # (h, w) of previous ROI
        self._event_count    = 0
        self._is_confirmed   = False
        self._last_event_ts  = 0.0
        self._disp_history   = deque(maxlen=history_len)

    # ----------------------------------------------------------
    def reset(self):
        self._prev_gray     = None
        self._prev_pts      = None
        self._prev_shape    = None
        self._event_count   = 0
        self._is_confirmed  = False
        self._last_event_ts = 0.0
        self._disp_history.clear()

    # ----------------------------------------------------------
    def process_body_roi(
        self,
        frame_bgr: np.ndarray,
        body_roi: tuple[int, int, int, int] | None,
        annotated: np.ndarray,
    ) -> dict:
        """
        Process the body region for this frame.

        Args:
            frame_bgr : Full BGR frame.
            body_roi  : (x, y, w, h) of the body region, or None.
            annotated : Frame to draw debug visuals onto (in-place).

        Returns dict with keys:
            motion_detected  bool  — True if motion event triggered
            event_count      int
            required         int
            is_confirmed     bool
            mean_disp        float — raw displacement magnitude this frame
        """
        if self._is_confirmed:
            return self._result(False, 0.0)

        now = time.time()

        # ── Determine crop ─────────────────────────────────────
        h_full, w_full = frame_bgr.shape[:2]

        if body_roi is not None:
            bx, by, bw, bh = body_roi
        else:
            # Fallback: use the bottom 40% of the frame
            by = int(h_full * 0.60)
            bx, bw, bh = 0, w_full, h_full - by

        # Clamp to frame
        bx  = max(0, bx)
        by  = max(0, by)
        bw  = min(bw, w_full - bx)
        bh  = min(bh, h_full - by)

        if bw < 30 or bh < 30:
            return self._result(False, 0.0)

        roi_bgr  = frame_bgr[by:by + bh, bx:bx + bw]
        roi_gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)

        # Reset tracker if ROI shape changed (face moved / resized)
        if self._prev_shape is not None and roi_gray.shape != self._prev_shape:
            self._prev_gray = None
            self._prev_pts  = None

        # Draw body ROI box
        cv2.rectangle(
            annotated,
            (bx, by),
            (bx + bw, by + bh),
            (200, 120, 0),
            1,
        )
        cv2.putText(
            annotated,
            "Body ROI",
            (bx + 4, by + 16),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 120, 0), 1,
        )

        mean_disp = 0.0
        motion_detected = False

        # ── Optical Flow ────────────────────────────────────────
        if self._prev_gray is not None and self._prev_pts is not None and len(self._prev_pts) > 0:
            next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
                self._prev_gray, roi_gray, self._prev_pts, None, **_LK_PARAMS
            )

            if next_pts is not None and status is not None:
                good_prev = self._prev_pts[status.flatten() == 1]
                good_next = next_pts[status.flatten() == 1]

                if len(good_prev) > 3:
                    displacements = np.linalg.norm(good_next - good_prev, axis=1)
                    mean_disp = float(np.mean(displacements))
                    self._disp_history.append(mean_disp)

                    smoothed = float(np.mean(self._disp_history))

                    # Draw motion vectors on body ROI in annotated frame
                    for p, q in zip(good_prev.astype(int), good_next.astype(int)):
                        px, py = p.ravel()
                        qx, qy = q.ravel()
                        cv2.line(
                            annotated,
                            (bx + px, by + py),
                            (bx + qx, by + qy),
                            (0, 200, 255), 1,
                        )
                        cv2.circle(annotated, (bx + qx, by + qy), 2, (0, 200, 255), -1)

                    # Check motion event
                    if (
                        smoothed >= self.motion_threshold
                        and now - self._last_event_ts >= self.event_cooldown_s
                    ):
                        self._event_count += 1
                        self._last_event_ts = now
                        motion_detected = True
                        if self._event_count >= self.required_events:
                            self._is_confirmed = True

                    # Update tracked points to good ones
                    self._prev_pts = good_next.reshape(-1, 1, 2)
                else:
                    # Too many lost points — refresh features
                    self._prev_pts = None

        # ── Refresh feature points periodically ─────────────────
        if self._prev_pts is None or len(self._prev_pts) < 10:
            mask = np.zeros_like(roi_gray)
            mask[:] = 255
            pts = cv2.goodFeaturesToTrack(roi_gray, mask=mask, **_FEATURE_PARAMS)
            self._prev_pts = pts  # may be None if no features

        # ── Update previous frame ───────────────────────────────
        self._prev_gray  = roi_gray.copy()
        self._prev_shape = roi_gray.shape

        return self._result(motion_detected, mean_disp)

    # ----------------------------------------------------------
    def _result(self, motion_detected: bool, mean_disp: float) -> dict:
        return {
            "motion_detected": motion_detected,
            "event_count":     self._event_count,
            "required":        self.required_events,
            "is_confirmed":    self._is_confirmed,
            "mean_disp":       mean_disp,
        }


# ---------------------------------------------------------------
# Main class
# ---------------------------------------------------------------

class LivenessDetector:
    """
    Single-signal liveness detector:
      ① Body motion (Lucas-Kanade optical flow on torso ROI)

    The signal must pass for `is_live` to become True.

    Usage:
        detector = LivenessDetector(required_motions=2)
        while cap.isOpened():
            ret, frame = cap.read()
            result = detector.process_frame(frame)
            if result['is_live']:
                print("LIVE!")
    """

    NO_FACE_RESET_SECONDS = 8.0

    def __init__(self, required_motions: int = 2):
        self._last_face_ts     = time.time()

        # ── Body-motion sub-module ──────────────────────────────
        self._motion = BodyMotionDetector(required_events=required_motions)

    # ----------------------------------------------------------
    @property
    def is_live(self) -> bool:
        return self._motion._is_confirmed

    # ----------------------------------------------------------
    def reset(self):
        """Reset all state (call when switching to a new person)."""
        self._last_face_ts     = time.time()
        self._motion.reset()

    # ----------------------------------------------------------
    def process_frame(self, frame_bgr: np.ndarray) -> dict:
        """
        Process one BGR frame.

        Returns:
            {
                'is_live':          bool,
                'motion_events':    int,
                'motions_required': int,
                'motion_done':      bool,
                'face_found':       bool,
                'mean_disp':        float,
                'annotated':        np.ndarray,
            }
        """
        now = time.time()

        # Auto-reset if face absent too long
        if now - self._last_face_ts > self.NO_FACE_RESET_SECONDS:
            self.reset()

        annotated  = frame_bgr.copy()
        face_found = False
        body_roi   = None  # (x, y, w, h) of body region

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        # ── Face detection ──────────────────────────────────────
        faces = _face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
        )

        if len(faces) > 0:
            face_found = True
            self._last_face_ts = now

            # Use the largest face
            fx, fy, fw, fh = sorted(faces, key=lambda r: r[2] * r[3], reverse=True)[0]

            # ── Body ROI = region below face ────────────────────
            h_full = frame_bgr.shape[0]
            body_top  = fy + fh          # just below face
            body_left = max(0, fx - fw // 2)
            body_w    = min(fw * 2, frame_bgr.shape[1] - body_left)
            body_h    = max(30, h_full - body_top)
            body_roi  = (body_left, body_top, body_w, body_h)

            # ── Face bounding box ───────────────────────────────
            face_color = (0, 220, 0) if self.is_live else (0, 165, 255)
            cv2.rectangle(annotated, (fx, fy), (fx + fw, fy + fh), face_color, 2)

        # ── Body motion (always runs, even without a face detect) ──
        motion_result = self._motion.process_body_roi(frame_bgr, body_roi, annotated)

        # ── Draw HUD overlay ────────────────────────────────────
        self._draw_overlay(annotated, motion_result)

        return {
            "is_live":          self.is_live,
            "motion_events":    motion_result["event_count"],
            "motions_required": motion_result["required"],
            "motion_done":      motion_result["is_confirmed"],
            "face_found":       face_found,
            "mean_disp":        motion_result["mean_disp"],
            "annotated":        annotated,
        }

    # ----------------------------------------------------------
    def _draw_overlay(self, frame: np.ndarray, motion_result: dict):
        """Draw a two-row translucent HUD banner with signal status."""
        h, w = frame.shape[:2]

        # ── Determine overall status ────────────────────────────
        if self.is_live:
            status_text = "LIVE CONFIRMED"
            bar_base    = (0, 220, 0)
        else:
            status_text = "Move your body now"
            bar_base    = (0, 200, 255)

        # Semi-transparent banner (two rows)
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 88), (15, 15, 15), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        # Row 1 — overall status
        cv2.putText(
            frame, f"Liveness: {status_text}",
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.70, bar_base, 2,
        )

        # ── Row 2 — Signal: Body Motion ──────────────────────
        motion_ratio  = min(1.0, motion_result["event_count"] / max(1, motion_result["required"]))
        motion_color  = (0, 220, 0) if motion_result["is_confirmed"] else (0, 200, 255)
        disp_txt = f"Disp:{motion_result['mean_disp']:.1f}px"
        self._draw_progress_bar(
            frame,
            label=f"Motion {motion_result['event_count']}/{motion_result['required']}  {disp_txt}",
            ratio=motion_ratio,
            color=motion_color,
            x=10, y=55, bar_w=220, bar_h=22,
        )

    # ----------------------------------------------------------
    @staticmethod
    def _draw_progress_bar(
        frame, label, ratio, color,
        x, y, bar_w, bar_h
    ):
        filled = int(bar_w * ratio)
        cv2.rectangle(frame, (x, y), (x + bar_w, y + bar_h), (50, 50, 50), -1)
        cv2.rectangle(frame, (x, y), (x + filled, y + bar_h), color, -1)
        cv2.rectangle(frame, (x, y), (x + bar_w, y + bar_h), (160, 160, 160), 1)
        cv2.putText(
            frame, label,
            (x + 4, y + bar_h - 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1,
        )


# ---------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------
if __name__ == "__main__":
    detector = LivenessDetector(required_motions=2)
    cap = cv2.VideoCapture(0)

    print("\n=== Single-Signal Liveness Detection Demo ===")
    print("Step 1: Move your body/torso to pass the motion challenge.")
    print("Must pass for LIVE CONFIRMED. Press 'q' to quit.\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        result  = detector.process_frame(frame)
        display = result["annotated"]

        if result["is_live"]:
            cv2.putText(
                display, "YOU ARE LIVE!",
                (20, display.shape[0] - 25),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 0), 3,
            )

        # Debug info bottom-right
        dbg = (
            f"MotionEvt:{result['motion_events']}  "
            f"Disp:{result['mean_disp']:.2f}px"
        )
        cv2.putText(
            display, dbg,
            (10, display.shape[0] - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1,
        )

        cv2.imshow("Liveness Detection — Single Signal", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
