import cv2
import torch
from ultralytics import YOLO
import os

# Load trained YOLO model
# Try multiple possible paths
model_paths = [
    r"model/best_yolov8.pt",
    r"model/best_yolov12.pt",
    r"C:\Users\LENOVO\Documents\FYP\Cheating Surveillance\models\best.pt"
]

model = None
for path in model_paths:
    if os.path.exists(path):
        try:
            model = YOLO(path)
            print(f"Loaded model from: {path}")
            break
        except Exception as e:
            print(f"Failed to load model from {path}: {e}")
            continue

if model is None:
    print("Warning: No valid YOLO model found. Mobile detection will be disabled.")
    model = None

device = "cuda" if torch.cuda.is_available() else "cpu"
if model is not None:
    model.to(device)

def process_mobile_detection(frame):
    global model
    mobile_detected = False

    if model is None:
        return frame, mobile_detected

    results = model(frame, verbose=False)

    for result in results:
        for box in result.boxes:
            conf = box.conf[0].item()
            cls = int(box.cls[0].item())

            if conf < 0.8 or cls != 0:  # Mobile class index is 0
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])  
            label = f"Mobile ({conf:.2f})"

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            mobile_detected = True
    
    return frame, mobile_detected
