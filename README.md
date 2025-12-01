# ProctorX — AI-Powered Real-Time Cheating Detection System
<img width="1680" height="790" alt="Screenshot 2025-12-01 120613" src="https://github.com/user-attachments/assets/a7284658-cd1d-4baa-8499-92dfc7397598" />
<img width="1676" height="791" alt="Screenshot 2025-12-01 120549" src="https://github.com/user-attachments/assets/dcef0f73-52c8-47c3-b595-410a11fdbdae" />


**ProctorX** is a lightweight demo / research project that performs real-time proctoring using computer vision and audio analysis.  
It combines MediaPipe (face & eye tracking), YOLO (object detection for phones/notes), and a Python alarm/escalation engine to detect suspicious exam behavior.

Key Features
🔹 Eye-Gaze Detection

Tracks iris using MediaPipe

Detects off-screen gaze, downward reading, long deviations

Smooth and stable gaze estimation

🔹 Face & Head Movement Detection

Head yaw, pitch, roll

Face missing from frame

Extreme head turns

🔹 Hand & Occlusion Monitoring

Hand covering face

Hand near ear

Hand moving out of frame (possible hidden item)

🔹 YOLO Gadget Detection

Detects:

Mobile phones

Earphones / earbuds

Papers / books or other objects

🔹 Audio-Based Detection

Whispering

Background voices

Speech without lip movement

🔹 Alarm System

Automatically escalates:
Notice → Low → Medium → High → Critical
Captures screenshots and logs critical events.

🔹 Clean Web UI

Live camera stream

Gaze overlays

Alarm banners

Event timeline

Score display

🛠️ Installation & Setup
1️⃣ Create a Virtual Environment
python -m venv .venv
.venv\Scripts\activate

2️⃣ Install Dependencies
pip install -r requirements.txt

3️⃣ Add YOLO Models

Place your model weights in the /model/ folder:

model/best_yolov8.pt
model/best_yolov12.pt


⚠️ Do NOT upload .pt files to GitHub — they exceed 100MB.

▶️ How to Run
Run backend detection:
python main.py

Open Web UI:

Open the file:

proctor_web_ui.html


Or run:

python -m http.server


Then visit:

http://localhost:8000/proctor_web_ui.html

📸 Evidence Logging

The system automatically saves:

Suspicious activity screenshots

Critical alarms

JSON event reports

Stored in the /log/ folder.

⚠️ Important Notes

Do NOT commit the following folders:

.venv/

mp_env/

log/

model/*.pt files

Use .gitignore to exclude them.

👩‍💻 About the Author

Nhowmitha Suresh
AI & Data Science Student
Passionate about Computer Vision, AI Proctoring Systems, and Real-Time ML Applications.

This project demonstrates practical implementation of AI-based monitoring and automated cheating detection.

📄 License

This project is open-source under the MIT License.



