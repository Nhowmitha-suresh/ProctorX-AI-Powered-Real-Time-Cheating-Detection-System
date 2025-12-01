import cv2
import mediapipe as mp
import numpy as np
import time
import collections
import threading
import math
import sys
import pyttsx3

# Conditional import for Windows-specific sound library
if sys.platform == "win32":
    import winsound

# ===============================================================
# ======================== CONFIGURATION ========================
# ===============================================================

# --- Performance & Smoothing ---
FPS_TARGET = 30
FRAME_SKIP_HEAD_POSE = 3     # Calculate Head Pose every N frames (heavy task)
EMA_ALPHA = 0.40             # Exponential Moving Average factor (higher = less smoothing)
CALIBRATION_SECONDS = 3.0

# --- Detection Thresholds (Normalized/Degrees) ---
GLANCE_THRESHOLD = 0.20      # Gaze distance from center
YAW_THRESHOLD = 20.0         # Head rotation left/right (degrees)
PITCH_THRESHOLD = 18.0       # Head rotation up/down (degrees)
HAND_FACE_DIST_RATIO = 0.50  # Hand center must be this close to face diagonal

# --- Sustained Event Durations (in seconds) ---
GLANCE_SUSTAIN = 0.8         # Time required to trigger a gaze cheat
HEAD_SUSTAIN = 0.7           # Time required to trigger a head turn cheat
HAND_SUSTAIN = 0.6           # Time required for hand to be near face
OCCLUSION_SUSTAIN = 0.5      # Time required for face to be completely hidden
MULTIFACE_SUSTAIN = 0.5     # Time required for a second face to be present

# --- Scoring & Alarms ---
MAX_SCORE = 100.0
SCORE_DECAY_RATE = 0.95      # Multiplicative decay per frame (smooth)
SCORE_INCREMENT = 1.0        # Base score added per frame for a sustained event

# Event Multipliers (relative weights of cheating actions)
WEIGHT_OFFSCREEN = 1.0
WEIGHT_HEADTURN = 1.2
WEIGHT_HAND_NEAR = 1.5
WEIGHT_MULTI_FACE = 2.0
WEIGHT_OCCLUSION = 1.8

# Alarm Levels
ALARM_LOW = 15.0             # Verbal warning
ALARM_MEDIUM = 35.0          # Beep and explicit warning
ALARM_HIGH = 65.0            # High alert, session paused/blocked

# Voice messages
VOICE_LOW = "Please focus on the screen."
VOICE_MEDIUM = "Possible cheating detected. Please stop."
VOICE_HIGH = "High alert. Session paused."

# ===============================================================
# ======================= ASYNC ALERT SYSTEM ====================
# ===============================================================

engine = pyttsx3.init()
engine.setProperty('rate', 150)

_alert_lock = threading.Lock()
_stop_threads = False
_alarm_mode = None

def _speak_target(text):
    """Internal function for the voice thread."""
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception:
        pass

def _alarm_target(mode):
    """Internal function for the sound thread."""
    global _stop_threads
    try:
        if mode == 'low':
            if sys.platform == "win32": winsound.Beep(1000, 200)
        elif mode == 'medium':
            for _ in range(3):
                if _stop_threads: return
                if sys.platform == "win32": winsound.Beep(1000, 350)
                time.sleep(0.15)
        elif mode == 'high':
            while not _stop_threads:
                if sys.platform == "win32": winsound.Beep(1200, 450)
                time.sleep(0.08)
    except Exception:
        pass

def stop_alerts():
    """Stops all running sound/voice threads cleanly."""
    global _alarm_mode, _stop_threads
    with _alert_lock:
        if _alarm_mode is None:
            return
        _stop_threads = True
        _alarm_mode = None
    time.sleep(0.2)
    _stop_threads = False

def trigger_alert(mode):
    """Starts a new alert, stopping any current one."""
    global _alarm_mode
    with _alert_lock:
        if _alarm_mode == mode:
            return

        stop_alerts()
        _alarm_mode = mode

        # Start sound thread
        threading.Thread(target=_alarm_target, args=(mode,), daemon=True).start()

        # Start voice thread
        voice_map = {'low': VOICE_LOW, 'medium': VOICE_MEDIUM, 'high': VOICE_HIGH}
        threading.Thread(target=_speak_target, args=(voice_map.get(mode, ""),), daemon=True).start()

# ===============================================================
# ======================= MEDIAPIPE & GEOMETRY ==================
# ===============================================================

mp_face_mesh = mp.solutions.face_mesh
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# Landmark indices for fast access
LEFT_IRIS_IDX = [474, 475, 476, 477]
RIGHT_IRIS_IDX = [469, 470, 471, 472]
HP_IDX = [1, 152, 33, 263, 61, 291] # Head Pose: Nose tip, Chin, Eyes, Mouth

model_points = np.array([
    (0.0, 0.0, 0.0), (0.0, -330.0, -65.0), # Nose, Chin
    (-225.0, 170.0, -135.0), (225.0, 170.0, -135.0), # Left Eye, Right Eye
    (-150.0, -150.0, -125.0), (150.0, -150.0, -125.0) # Left Mouth, Right Mouth
], dtype=np.float64)

def normalized_iris_center(iris_pts):
    """Calculates the center of the iris relative to its min/max boundaries (0.0 to 1.0)."""
    x0, y0 = iris_pts[:, 0].min(), iris_pts[:, 1].min()
    x1, y1 = iris_pts[:, 0].max(), iris_pts[:, 1].max()
    cx, cy = iris_pts.mean(axis=0)
    w = max(1, x1 - x0)
    h = max(1, y1 - y0)
    return (cx - x0) / w, (cy - y0) / h

def estimate_head_pose(image_points, img_w, img_h):
    """Estimates Pitch and Yaw of the head using PnP algorithm."""
    try:
        focal_length = img_w
        center = (img_w / 2.0, img_h / 2.0)
        camera_matrix = np.array([[focal_length, 0, center[0]], [0, focal_length, center[1]], [0, 0, 1]], dtype=np.float64)
        dist_coeffs = np.zeros((4, 1))

        # Solve for Rotation and Translation vectors
        _, rvec, _ = cv2.solvePnP(
            model_points,
            np.array(image_points, dtype=np.float64),
            camera_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        rmat, _ = cv2.Rodrigues(rvec)
        # Convert rotation matrix to Euler angles (Pitch and Yaw are most relevant)
        pitch = math.atan2(rmat[2, 1], rmat[2, 2])
        yaw = math.atan2(-rmat[2, 0], math.sqrt(rmat[0, 0]**2 + rmat[1, 0]**2))

        return (math.degrees(pitch), math.degrees(yaw))
    except Exception:
        return None

# ===============================================================
# ==================== CAMERA/MEDIAPIPE SETUP ===================
# ===============================================================

def open_camera():
    """Initializes and opens the camera with preferred settings."""
    for idx in (0, 1, 2):
        # CAP_DSHOW for faster Windows camera I/O
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            # Set high resolution for better tracking accuracy
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            print(f"Camera opened at index: {idx}")
            return cap
    return None

cap = open_camera()
if cap is None:
    print("ERROR: No camera found.")
    sys.exit(1)


# Setup MediaPipe Processors
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

hands = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

cv2.namedWindow("CheatImproved", cv2.WINDOW_NORMAL)
cv2.resizeWindow("CheatImproved", 1280, 720)


# ===============================================================
# ======================== CALIBRATION ==========================
# ===============================================================

print(f"Calibration: Please look straight at the camera for {CALIBRATION_SECONDS}s...")

calib_start = time.time()
calib_samples = []

while time.time() - calib_start < CALIBRATION_SECONDS:
    ret, frame = cap.read()
    if not ret: continue

    h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    res = face_mesh.process(rgb)

    if res.multi_face_landmarks:
        lm = np.array([(int(p.x*w), int(p.y*h)) for p in res.multi_face_landmarks[0].landmark])

        left_iris = lm[LEFT_IRIS_IDX]
        right_iris = lm[RIGHT_IRIS_IDX]
        nxL, nyL = normalized_iris_center(left_iris)
        nxR, nyR = normalized_iris_center(right_iris)
        calib_samples.append(((nxL + nxR) / 2, (nyL + nyR) / 2))

    cv2.putText(frame, "CALIBRATING...", (10, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
    cv2.imshow("CheatImproved", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

if calib_samples:
    calib_center = np.mean(calib_samples, axis=0)
else:
    calib_center = (0.5, 0.5) # Fallback
print(f"Calibration complete. Center = ({calib_center[0]:.3f}, {calib_center[1]:.3f})")


# ===============================================================
# ======================== MAIN LOOP =============================
# ===============================================================

# --- State Variables ---
ema_nx, ema_ny = calib_center
ema_yaw, ema_pitch = 0.0, 0.0
current_alarm_score = 0.0
frame_counter = 0

# --- Sustained Buffers (using integer counts for high speed) ---
# Length is calculated based on target FPS and sustain time
glance_buf = collections.deque(maxlen=int(FPS_TARGET * GLANCE_SUSTAIN))
head_buf = collections.deque(maxlen=int(FPS_TARGET * HEAD_SUSTAIN / FRAME_SKIP_HEAD_POSE)) # Smaller buffer due to skip
hand_buf = collections.deque(maxlen=int(FPS_TARGET * HAND_SUSTAIN))
occ_buf = collections.deque(maxlen=int(FPS_TARGET * OCCLUSION_SUSTAIN))
mf_buf = collections.deque(maxlen=int(FPS_TARGET * MULTIFACE_SUSTAIN))


print("Starting main loop (ESC to exit)...")

try:
    while True:
        start_time = time.time()
        ret, frame = cap.read()
        if not ret: continue

        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_counter += 1

        # Process MediaPipe (most expensive step)
        res = face_mesh.process(rgb)
        hres = hands.process(rgb)

        # --- Flags Reset ---
        offscreen_flag = headturn_flag = handnear_flag = False
        occlusion_flag = multiface_flag = False
        face_detected = False
        face_lm = None
        
        # ========== 1. FACE DETECTION & GAZE/HEAD POSE ==========
        if res.multi_face_landmarks:
            face_detected = True
            lm = np.array([(int(p.x*w), int(p.y*h)) for p in res.multi_face_landmarks[0].landmark])
            face_lm = lm

            # --- Multi-Face Check ---
            if len(res.multi_face_landmarks) > 1:
                mf_buf.append(1)
                if len(mf_buf) == mf_buf.maxlen: multiface_flag = True
            else:
                mf_buf.clear()

            # --- Gaze Tracking ---
            Lpts = lm[LEFT_IRIS_IDX]
            Rpts = lm[RIGHT_IRIS_IDX]
            Lc = Lpts.mean(axis=0)
            Rc = Rpts.mean(axis=0)

            nxL, nyL = normalized_iris_center(Lpts)
            nxR, nyR = normalized_iris_center(Rpts)
            nx = (nxL + nxR) / 2
            ny = (nyL + nyR) / 2

            # EMA Smoothing
            ema_nx = EMA_ALPHA * nx + (1 - EMA_ALPHA) * ema_nx
            ema_ny = EMA_ALPHA * ny + (1 - EMA_ALPHA) * ema_ny

            # Glance Check
            if (abs(ema_nx - calib_center[0]) > GLANCE_THRESHOLD or
                abs(ema_ny - calib_center[1]) > GLANCE_THRESHOLD):
                glance_buf.append(1)
            else:
                glance_buf.clear()

            if len(glance_buf) == glance_buf.maxlen: offscreen_flag = True

            # --- Head Pose (Frame Skip for Performance) ---
            if frame_counter % FRAME_SKIP_HEAD_POSE == 0:
                pose = estimate_head_pose([tuple(lm[i]) for i in HP_IDX], w, h)
                if pose:
                    pitch, yaw = pose
                    # EMA Smoothing
                    ema_yaw = EMA_ALPHA * yaw + (1 - EMA_ALPHA) * ema_yaw
                    ema_pitch = EMA_ALPHA * pitch + (1 - EMA_ALPHA) * ema_pitch

                    # Head Turn Check
                    if abs(ema_yaw) > YAW_THRESHOLD or abs(ema_pitch) > PITCH_THRESHOLD:
                        head_buf.append(1)
                    else:
                        head_buf.clear()

                    if len(head_buf) == head_buf.maxlen: headturn_flag = True
            
            # --- Essential Drawing ---
            cv2.circle(frame, tuple(Lc.astype(int)), 3, (0,0,255), -1)
            cv2.circle(frame, tuple(Rc.astype(int)), 3, (0,0,255), -1)

        else:
            # --- Occlusion Check (No Face Detected) ---
            occ_buf.append(1)
            if len(occ_buf) == occ_buf.maxlen: occlusion_flag = True
            
            # Clear other buffers since face is lost
            glance_buf.clear()
            head_buf.clear()
            mf_buf.clear()


        # ========== 2. HAND DETECTION (Gadget Proxy) ==========
        if hres.multi_hand_landmarks and face_detected:
            fx0, fy0 = face_lm[:,0].min(), face_lm[:,1].min()
            fx1, fy1 = face_lm[:,0].max(), face_lm[:,1].max()
            fc = np.array([(fx0+fx1)/2, (fy0+fy1)/2])
            fdiag = math.hypot(fx1-fx0, fy1-fy0) # Face bounding box diagonal

            hand_is_near = False
            for hand_landmarks in hres.multi_hand_landmarks:
                pts = np.array([(int(p.x*w), int(p.y*h)) for p in hand_landmarks.landmark])
                hcx, hcy = pts[:,0].mean(), pts[:,1].mean()
                
                # Check distance relative to face size
                dist = math.hypot(hcx - fc[0], hcy - fc[1])
                if dist < HAND_FACE_DIST_RATIO * fdiag:
                    hand_is_near = True
                    cv2.circle(frame, (int(hcx), int(hcy)), 5, (255, 0, 0), 2) # Draw only if relevant
                    break

            if hand_is_near:
                hand_buf.append(1)
            else:
                hand_buf.clear()

            if len(hand_buf) == hand_buf.maxlen: handnear_flag = True
        else:
            hand_buf.clear()


        # ==================== 3. SCORING LOGIC ====================

        # 1. Decay the current score smoothly
        current_alarm_score *= SCORE_DECAY_RATE
        
        # 2. Add score based on triggered flags
        if offscreen_flag: current_alarm_score += SCORE_INCREMENT * WEIGHT_OFFSCREEN
        if headturn_flag: current_alarm_score += SCORE_INCREMENT * WEIGHT_HEADTURN
        if handnear_flag: current_alarm_score += SCORE_INCREMENT * WEIGHT_HAND_NEAR
        if occlusion_flag: current_alarm_score += SCORE_INCREMENT * WEIGHT_OCCLUSION
        if multiface_flag: current_alarm_score += SCORE_INCREMENT * WEIGHT_MULTI_FACE
        
        # 3. Clamp the score
        current_alarm_score = min(current_alarm_score, MAX_SCORE)

        # ==================== 4. ALARM TRIGGERING ====================

        if current_alarm_score >= ALARM_HIGH:
            trigger_alert('high')
        elif current_alarm_score >= ALARM_MEDIUM:
            trigger_alert('medium')
        elif current_alarm_score >= ALARM_LOW:
            trigger_alert('low')
        elif _alarm_mode is not None:
            stop_alerts()

        # ==================== 5. DISPLAY OVERLAY ====================

        text_color = (0, 255, 0) # Green (Safe)
        status_text = "SAFE"

        if current_alarm_score >= ALARM_HIGH:
            text_color = (0, 0, 255) # Red
            status_text = "HIGH ALERT"
        elif current_alarm_score >= ALARM_MEDIUM:
            text_color = (0, 165, 255) # Orange
            status_text = "MEDIUM ALERT"
        elif current_alarm_score >= ALARM_LOW:
            text_color = (0, 255, 255) # Yellow
            status_text = "LOW ALERT"

        cv2.putText(frame, f"STATUS: {status_text}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, text_color, 2)
        cv2.putText(frame, f"SCORE: {current_alarm_score:.1f}/{MAX_SCORE:.0f}", (10, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, text_color, 2)
        
        # Debug/Flag Info
        flags_info = f"Gaze: {int(offscreen_flag)} | Head: {int(headturn_flag)} | Hand: {int(handnear_flag)} | Occ: {int(occlusion_flag)} | Multi: {int(multiface_flag)}"
        cv2.putText(frame, flags_info, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        cv2.imshow("CheatImproved", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27: break

        # --- Frame Rate Enforcement (Wait to maintain target FPS) ---
        time_diff = time.time() - start_time
        sleep_time = (1 / FPS_TARGET) - time_diff
        if sleep_time > 0:
            time.sleep(sleep_time)


finally:
    stop_alerts()
    cap.release()
    cv2.destroyAllWindows()
    face_mesh.close()
    hands.close()
    print("Exiting cleanly.")