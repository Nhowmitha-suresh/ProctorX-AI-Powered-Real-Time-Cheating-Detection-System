# ProctorX — AI-Powered Real-Time Cheating Detection System
<img width="1680" height="790" alt="Screenshot 2025-12-01 120613" src="https://github.com/user-attachments/assets/a7284658-cd1d-4baa-8499-92dfc7397598" />
<img width="1676" height="791" alt="Screenshot 2025-12-01 120549" src="https://github.com/user-attachments/assets/dcef0f73-52c8-47c3-b595-410a11fdbdae" />


# ProctorX – AI-Based Real-Time Cheating Detection

***ProctorX*** is an AI-powered real-time exam proctoring system that detects suspicious behavior using computer vision and audio analysis.  
It is designed as a lightweight research and demo project for automated remote examination monitoring.

---

### ***FEATURES***

- Eye-gaze tracking for on-screen and off-screen detection  
- Face presence and head movement analysis  
- Hand and occlusion monitoring  
- Object detection (mobile phones, earphones, notes) using YOLO  
- Audio-based activity detection (whispering, background voices)  
- Automated alert escalation system  
- Live web-based monitoring interface  

---

### ***TECH STACK***

- Python  
- OpenCV  
- MediaPipe  
- YOLO (Object Detection)  
- NumPy  
- HTML and JavaScript for Web UI  

---





---

### ***INSTALLATION***

Create and activate a virtual environment:

python -m venv .venv
.venv\Scripts\activate



Install dependencies:

pip install -r requirements.txt


---

### ***SETUP***

Place YOLO model weights inside the model directory:

model/best_yolov8.pt
model/best_yolov12.pt



***Do not upload `.pt` files to GitHub due to file size limits.***

---

### ***RUN***

Start backend detection:

python main.py



Launch the web interface:

python -m http.server



Open in browser:

http://localhost:8000/proctor_web_ui.html



---

### ***LOGGING***

The system automatically records:
- Screenshots of suspicious activities  
- Critical alerts  
- JSON event reports  

All logs are stored in the ***log*** directory.

---

### ***NOTES***

Do not commit the following directories or files:

.venv/
log/
model/*.pt



Use ***.gitignore*** to exclude them.

---

### ***AUTHOR***

**Nhowmitha Suresh**  
AI & Data Science Student

---

### ***LICENSE***

MIT License
