import cv2
import mediapipe as mp
import numpy as np

mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils

# Indices for left & right iris in mediapipe face mesh (468 points).
# MediaPipe has iris landmarks: 468.. (depends on version) — but face mesh maps:
# left iris: [474,475,476,477], right iris: [469,470,471,472]
LEFT_IRIS_IDX = [474, 475, 476, 477]
RIGHT_IRIS_IDX = [469, 470, 471, 472]

# Eye outer landmarks for cropping (example points from Face Mesh)
LEFT_EYE_IDX = [33, 133]    # approx left eye corners
RIGHT_EYE_IDX = [362, 263]  # approx right eye corners

# Initialize face mesh globally
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,   # enables iris landmarks if available
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

def process_eye_movement(frame):
    """
    Process eye movement and gaze direction detection.
    
    Args:
        frame: Input video frame
        
    Returns:
        tuple: (processed_frame, gaze_direction)
    """
    img_h, img_w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)
    
    gaze_direction = "Looking at Screen"

    if results.multi_face_landmarks:
        face_landmarks = results.multi_face_landmarks[0]

        # Convert normalized landmarks to pixel coords
        lm = np.array([(int(p.x * img_w), int(p.y * img_h)) for p in face_landmarks.landmark])

        # get iris centers
        left_iris_pts = lm[LEFT_IRIS_IDX]
        right_iris_pts = lm[RIGHT_IRIS_IDX]

        left_center = np.mean(left_iris_pts, axis=0).astype(int)
        right_center = np.mean(right_iris_pts, axis=0).astype(int)

        # draw iris centers
        cv2.circle(frame, tuple(left_center), 3, (0, 0, 255), -1)
        cv2.circle(frame, tuple(right_center), 3, (0, 0, 255), -1)

        # Get eye region landmarks
        left_eye_pts = lm[LEFT_EYE_IDX]
        right_eye_pts = lm[RIGHT_EYE_IDX]

        # Determine gaze direction based on iris position
        # Normalize iris position relative to eye region
        left_iris_x = (left_center[0] - left_eye_pts[:, 0].min()) / (left_eye_pts[:, 0].max() - left_eye_pts[:, 0].min())
        right_iris_x = (right_center[0] - right_eye_pts[:, 0].min()) / (right_eye_pts[:, 0].max() - right_eye_pts[:, 0].min())
        
        # Average normalized position
        avg_iris_x = (left_iris_x + right_iris_x) / 2
        
        # Determine direction based on iris position
        if avg_iris_x < 0.35:
            gaze_direction = "Looking Left"
        elif avg_iris_x > 0.65:
            gaze_direction = "Looking Right"
        else:
            gaze_direction = "Looking at Screen"

    return frame, gaze_direction
