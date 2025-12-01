import cv2
import time
import os
from eye_movement import process_eye_movement
from head_pose import process_head_pose
from mobile_detection import process_mobile_detection
from cheating_detection_integration import CheatingDetectionIntegration
from ui_dashboard import CheatingDetectionDashboard, create_simple_ui
from alarm_escalation_controller import (
    AlarmAndEscalationController, AlarmConfig, AlarmLevel, OperatorAction
)
import uuid

# Initialize webcam
cap = cv2.VideoCapture(0)

# Create a log directory for screenshots and reports
log_dir = "log"
os.makedirs(log_dir, exist_ok=True)

# Initialize cheating detection engine
cheating_detector = CheatingDetectionIntegration()

# Initialize UI dashboard
dashboard = CheatingDetectionDashboard(width=1920, height=1440)
use_simple_ui = False  # Set to True for simpler overlay UI

# Initialize Alarm & Escalation Controller
session_id = str(uuid.uuid4())[:8]
user_id = "student_001"
exam_id = "exam_2025_001"

alarm_config = AlarmConfig(
    test_mode=False,
    verbose_logging=True,
    auto_pause_on_critical=False,  # Set to True to auto-pause exam
)

alarm_controller = AlarmAndEscalationController(
    config=alarm_config,
    session_id=session_id,
    user_id=user_id,
    exam_id=exam_id,
    device_metadata={
        'camera': 'built-in',
        'ip': '127.0.0.1',
        'timezone': 'UTC',
    }
)

# Calibration for head pose
calibrated_angles = None
start_time = time.time()

# Timers for each functionality
head_misalignment_start_time = None
eye_misalignment_start_time = None
mobile_detection_start_time = None

# Previous states
previous_head_state = "Looking at Screen"
previous_eye_state = "Looking at Screen"
previous_mobile_state = False

# Initialize head_direction with a default value
head_direction = "Looking at Screen"
iris_position = None
frame_count = 0

# Callbacks for alarm controller
def on_alarm_triggered(alarm_event):
    """Callback when alarm is triggered"""
    print(f"\n🚨 ALARM: {alarm_event.level.name} | Score: {alarm_event.score:.1f}")
    print(f"   Incident ID: {alarm_event.incident_id}")
    print(f"   Evidence files: {len(alarm_event.evidence_files)}")

def on_exam_paused(incident_id: str):
    """Callback when exam is paused"""
    print(f"\n⏸️  EXAM PAUSED: {incident_id}")

alarm_controller.on_alarm_callback = on_alarm_triggered
alarm_controller.on_exam_pause_callback = on_exam_paused

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Process eye movement
    frame, gaze_direction = process_eye_movement(frame)
    cv2.putText(frame, f"Gaze Direction: {gaze_direction}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Process head pose
    if time.time() - start_time <= 5:  # Calibration time
        cv2.putText(frame, "Calibrating... Keep your head straight", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        if calibrated_angles is None:
            _, calibrated_angles = process_head_pose(frame, None)
    else:
        frame, head_direction = process_head_pose(frame, calibrated_angles)
        cv2.putText(frame, f"Head Direction: {head_direction}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Process mobile detection
    frame, mobile_detected = process_mobile_detection(frame)
    cv2.putText(frame, f"Mobile Detected: {mobile_detected}", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # ============= CHEATING DETECTION ANALYSIS =============
    # Analyze frame with cheating detection engine
    analysis = cheating_detector.analyze_frame(
        frame=frame,
        gaze_direction=gaze_direction,
        head_direction=head_direction,
        iris_position=iris_position,
        mobile_detected=mobile_detected,
        face_detected=True  # Assume face is detected if we got here
    )
    
    # ============= ALARM & ESCALATION CONTROL =============
    # Process frame through alarm controller
    alarm_event = alarm_controller.process_frame(
        frame=frame,
        cheating_score=analysis.cheating_score,
        events=analysis.events,
        face_detected=True,
        frame_index=frame_count,
    )
    
    frame_count += 1
    
    # Prepare statistics
    stats = {
        'total_events': len(analysis.events),
        'critical_events': sum(1 for e in analysis.events if e.severity >= 8),
        'avg_events_per_min': len(analysis.events) / max(1, cheating_detector.engine.frame_count / 1800),
        'duration_sec': cheating_detector.engine.frame_count / 30,  # Assuming 30 FPS
        'current_alarm_level': alarm_controller.current_level.name if alarm_controller.current_level != AlarmLevel.NONE else "NONE",
    }
    
    # Render UI
    if use_simple_ui:
        # Simple overlay UI on video frame
        display_frame = create_simple_ui(frame, analysis)
    else:
        # Full dashboard UI
        display_frame = dashboard.update(frame, analysis, stats)
    
    # Display the combined output
    cv2.imshow("Advanced Cheating Detection Dashboard", display_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

# Print session reports
print("\n" + cheating_detector.get_session_report())

print("\n" + "="*70)
print("ALARM & ESCALATION CONTROLLER SESSION REPORT")
print("="*70)
report = alarm_controller.get_session_report()
print(f"Session ID: {report['session_id']}")
print(f"User ID: {report['user_id']}")
print(f"Exam ID: {report['exam_id']}")
print(f"\nAlarm Summary:")
print(f"  Total Alarms: {report['total_alarms']}")
print(f"  Critical: {report['critical_alarms']}")
print(f"  High: {report['high_alarms']}")
print(f"  Medium: {report['medium_alarms']}")
print(f"  Operator Actions: {report['operator_actions']}")
print(f"  Evidence Files: {report['evidence_files']}")
print("="*70)

# Export evidence package
evidence_report = alarm_controller.export_session_evidence()
print(f"\nEvidence package exported to: {evidence_report}")

print("\nSession ended.")