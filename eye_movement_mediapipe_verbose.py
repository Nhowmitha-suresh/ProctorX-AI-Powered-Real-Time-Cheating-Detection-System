# eye_movement_mediapipe_verbose.py

import cv2
import mediapipe as mp
import numpy as np
import time
import os
import collections

print("Starting MediaPipe Eye Demo")
print("mediapipe version:", getattr(mp, "__version__", "unknown"))
print("opencv version:", cv2.__version__)

mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils

# ========= IRIS LANDMARKS =========
LEFT_IRIS_IDX = [474, 475, 476, 477]
RIGHT_IRIS_IDX = [469, 470, 471, 472]

# ========= CHEAT DETECTION VARIABLES =========
gaze_window = collections.deque(maxlen=30)
glance_times = []

GLANCE_THRESHOLD = 0.15
GLANCE_TIME = 1.2  # seconds

events = collections.deque()

def push_event(score):
    events.append((time.time(), score))
    cutoff = time.time() - 10
    while events and events[0][0] < cutoff:
        events.popleft()

def current_score():
    return sum(s for _, s in events)

# ========= HELPERS =========
def eye_bbox_from_pts(pts, pad=8, img_w=640, img_h=480):
    x_min = max(0, pts[:, 0].min() - pad)
    y_min = max(0, pts[:, 1].min() - pad)
    x_max = min(img_w - 1, pts[:, 0].max() + pad)
    y_max = min(img_h - 1, pts[:, 1].max() + pad)
    return x_min, y_min, x_max, y_max

def normalized_iris_center(iris_pts, eye_pts, img_w, img_h):
    cx, cy = iris_pts.mean(axis=0)
    x0, y0, x1, y1 = eye_bbox_from_pts(eye_pts, img_w=img_w, img_h=img_h)
    w = max(1, x1 - x0)
    h = max(1, y1 - y0)
    nx = (cx - x0) / w
    ny = (cy - y0) / h
    return nx, ny

# ========= CAMERA OPEN =========
def open_camera():
    for idx in (0, 1, 2):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            print(f"Opened camera index {idx}")
            return cap, idx
        else:
            cap.release()
    return None, None

cap, cam_idx = open_camera()
if cap is None:
    print("ERROR: Could not open any webcam.")
    raise SystemExit(1)

# Save first frame
ret, frame = cap.read()
first_frame_path = os.path.join(os.getcwd(), "first_frame_debug.png")
cv2.imwrite(first_frame_path, frame)
print("Saved first frame to:", first_frame_path)

# ========= WINDOW SETUP =========
win_name = "MP FaceMesh Verbose"
cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(win_name, 960, 720)

# ========= PROCESSING LOOP =========
with mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5) as face_mesh:

    last_time = time.time()
    detected_any = False

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        img_h, img_w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        now = time.time()
        fps = 1.0 / (now - last_time)
        last_time = now

        if results.multi_face_landmarks:
            detected_any = True
            face_landmarks = results.multi_face_landmarks[0]

            lm = np.array([(int(p.x * img_w), int(p.y * img_h))
                           for p in face_landmarks.landmark])

            # IRIS POINTS
            left_iris_pts = lm[LEFT_IRIS_IDX]
            right_iris_pts = lm[RIGHT_IRIS_IDX]

            left_center = np.mean(left_iris_pts, axis=0).astype(int)
            right_center = np.mean(right_iris_pts, axis=0).astype(int)

            # Draw iris dots
            cv2.circle(frame, tuple(left_center), 3, (0, 0, 255), -1)
            cv2.circle(frame, tuple(right_center), 3, (0, 0, 255), -1)

            # ========= CHEAT DETECTION: IRIS NORMALIZATION =========
            nxL, nyL = normalized_iris_center(left_iris_pts, left_iris_pts, img_w, img_h)
            nxR, nyR = normalized_iris_center(right_iris_pts, right_iris_pts, img_w, img_h)

            nx = (nxL + nxR) / 2
            ny = (nyL + nyR) / 2

            gaze_window.append((time.time(), nx, ny))

            # Check if off-screen
            if nx < GLANCE_THRESHOLD or nx > 1 - GLANCE_THRESHOLD or ny < GLANCE_THRESHOLD or ny > 1 - GLANCE_THRESHOLD:
                glance_times.append(time.time())
            else:
                glance_times.clear()

            if glance_times and (time.time() - glance_times[0]) > GLANCE_TIME:
                push_event(2)
                print("⚠️  WARNING: User looking away from screen too long!")

            # ========= DRAW FACE MESH =========
            mp_drawing.draw_landmarks(
                image=frame,
                landmark_list=face_landmarks,
                connections=mp.solutions.face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=1, circle_radius=1),
                connection_drawing_spec=mp_drawing.DrawingSpec(color=(0, 128, 255), thickness=1, circle_radius=1)
            )

        # ========= DISPLAY INFO =========
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        score = current_score()
        cv2.putText(frame, f"CHEAT SCORE: {score:.1f}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (0, 0, 255) if score >= 12 else (0, 255, 0), 2)

        if score >= 12:
            cv2.putText(frame, "⚠ POSSIBLE CHEATING!", (10, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)

        cv2.imshow(win_name, frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            break
        if key == ord("s"):
            path = os.path.join(os.getcwd(), f"frame_{int(time.time())}.png")
            cv2.imwrite(path, frame)
            print("Saved:", path)

cap.release()
cv2.destroyAllWindows()
print("Exited cleanly.")
