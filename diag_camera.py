# diag_camera.py
import sys
import platform
import importlib
import cv2
import time

print("Python:", sys.version.splitlines()[0])
print("Platform:", platform.platform())

def try_import(name):
    try:
        m = importlib.import_module(name)
        print(f"Imported {name} OK, version:", getattr(m, "__version__", "unknown"))
    except Exception as e:
        print(f"FAILED to import {name}: {e}")

for pkg in ("mediapipe", "cv2", "numpy"):
    try_import(pkg)

print("\nTesting webcam (index 0). Press 'q' to quit or wait 5s to auto-close.")
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # use DirectShow on Windows
if not cap.isOpened():
    print("Webcam NOT opened. Try index 1 or check camera permissions.")
else:
    ret, frame = cap.read()
    print("Capture OK?", ret, "Frame shape:", None if frame is None else frame.shape)
    if ret and frame is not None:
        cv2.imshow("diag - webcam test", frame)
        # wait up to 5 seconds or until q pressed
        start = time.time()
        while True:
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            if time.time() - start > 5:
                break
        cv2.destroyAllWindows()
cap.release()
print("Done.")
