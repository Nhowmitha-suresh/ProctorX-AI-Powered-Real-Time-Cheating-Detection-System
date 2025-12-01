# API Reference - Advanced Cheating Detection System

## Table of Contents
1. [Alarm Escalation Controller](#alarm-escalation-controller)
2. [Cheating Detection Engine](#cheating-detection-engine)
3. [UI Dashboard](#ui-dashboard)
4. [Evidence Manager](#evidence-manager)
5. [Notification Manager](#notification-manager)
6. [Data Structures](#data-structures)

---

## Alarm Escalation Controller

### Class: `AlarmAndEscalationController`

Main controller for alarm management and escalation.

#### Constructor

```python
controller = AlarmAndEscalationController(
    config: AlarmConfig,
    session_id: str,
    user_id: str,
    exam_id: str,
    device_metadata: Dict = None
)
```

**Parameters:**
- `config`: AlarmConfig object with thresholds and policies
- `session_id`: Unique session identifier
- `user_id`: Student/exam-taker ID
- `exam_id`: Exam identifier
- `device_metadata`: Optional dict with device info

**Example:**
```python
from alarm_escalation_controller import AlarmAndEscalationController, AlarmConfig

config = AlarmConfig(
    thresholds={"critical": 60},
    auto_pause_on_critical=False
)

controller = AlarmAndEscalationController(
    config=config,
    session_id="exam_001_session_1",
    user_id="student_123",
    exam_id="cs101_final",
    device_metadata={"camera": "logitech_c920"}
)
```

#### Methods

##### `process_frame()`

Process a single video frame and decide on alarms.

```python
alarm_event = controller.process_frame(
    frame: np.ndarray,
    cheating_score: float,
    events: List[Dict],
    face_detected: bool,
    frame_index: int
) -> Optional[AlarmEvent]
```

**Parameters:**
- `frame`: OpenCV video frame (BGR format)
- `cheating_score`: Computed score (0-100)
- `events`: List of detected events
- `face_detected`: Boolean face detection state
- `frame_index`: Frame counter

**Returns:**
- `AlarmEvent` if alarm emitted, `None` otherwise

**Example:**
```python
# In main video loop
while True:
    ret, frame = cap.read()
    
    alarm_event = controller.process_frame(
        frame=frame,
        cheating_score=75.5,
        events=[{"type": "phone_detected", "severity": 10}],
        face_detected=True,
        frame_index=frame_count
    )
    
    if alarm_event:
        print(f"Alarm triggered: {alarm_event.level.name}")
```

##### `operator_action()`

Handle operator override actions.

```python
controller.operator_action(
    operator_id: str,
    action: OperatorAction,
    reason: str = ""
)
```

**Parameters:**
- `operator_id`: ID of operator performing action
- `action`: OperatorAction enum (ACKNOWLEDGE, MARK_FALSE_POSITIVE, etc.)
- `reason`: Optional explanation for action

**OperatorAction Enum Values:**
- `ACKNOWLEDGE`: Suppress alarms for 5 minutes
- `MARK_FALSE_POSITIVE`: Flag incident as false positive
- `LOCK_EXAM`: Lock exam from student
- `UNLOCK_EXAM`: Unlock exam
- `REQUEST_LIVE_VIEW`: Request live camera feed
- `REQUEST_STUDENT_RESPONSE`: Request student explanation

**Example:**
```python
from alarm_escalation_controller import OperatorAction

# Acknowledge alert
controller.operator_action(
    operator_id="proctor_alice",
    action=OperatorAction.ACKNOWLEDGE,
    reason="Student was just stretching neck"
)

# Mark as false positive
controller.operator_action(
    operator_id="proctor_bob",
    action=OperatorAction.MARK_FALSE_POSITIVE,
    reason="Camera glitch - face detection false positive"
)
```

##### `get_session_report()`

Generate complete session report.

```python
report = controller.get_session_report() -> Dict
```

**Returns:**
```python
{
    'session_id': 'abc123',
    'user_id': 'student_001',
    'exam_id': 'exam_2025_001',
    'total_alarms': 5,
    'critical_alarms': 1,
    'high_alarms': 2,
    'medium_alarms': 2,
    'operator_actions': 1,
    'evidence_files': 15,
    'alarm_timeline': [AlarmEvent(...), ...],
    'operator_actions_log': [OperatorOverride(...), ...]
}
```

**Example:**
```python
report = controller.get_session_report()
print(f"Total alarms: {report['total_alarms']}")
print(f"Critical incidents: {report['critical_alarms']}")
```

##### `export_session_evidence()`

Export full evidence package for audit.

```python
manifest_file = controller.export_session_evidence() -> str
```

**Returns:** Path to session report file

**Example:**
```python
evidence_path = controller.export_session_evidence()
print(f"Evidence exported to: {evidence_path}")
# Outputs: "log/evidence/session_abc123_report.json"
```

##### `cleanup_old_evidence()`

Remove evidence older than retention period.

```python
controller.cleanup_old_evidence()
```

**Example:**
```python
# Called periodically to clean up
controller.cleanup_old_evidence()
# Removes evidence older than 90 days (default)
```

#### Properties

- `current_level` (AlarmLevel): Current alarm level
- `alarm_history` (List[AlarmEvent]): All alarms in session
- `operator_overrides` (List[OperatorOverride]): All operator actions

#### Callbacks

```python
# Called when alarm is triggered
controller.on_alarm_callback = lambda event: print(f"Alarm: {event.level}")

# Called when exam is paused
controller.on_exam_pause_callback = lambda incident_id: pause_exam(incident_id)
```

---

## Cheating Detection Engine

### Class: `CheatingDetectionEngine`

Core detection logic with multi-modal event analysis.

#### Constructor

```python
engine = CheatingDetectionEngine(window_size: int = 300)
```

#### Methods

##### `detect_eye_behavior()`

```python
events = engine.detect_eye_behavior(
    gaze_direction: str,
    iris_position: Optional[Tuple[float, float]] = None,
    previous_iris_position: Optional[Tuple[float, float]] = None
) -> List[CheatEvent]
```

**Gaze Direction Values:**
- `"Looking at Screen"`
- `"Looking Left"`
- `"Looking Right"`
- `"Looking Up"`
- `"Looking Down"`

##### `detect_head_behavior()`

```python
events = engine.detect_head_behavior(
    head_direction: str,
    yaw: Optional[float] = None,
    pitch: Optional[float] = None,
    roll: Optional[float] = None
) -> List[CheatEvent]
```

**Angles:** In degrees (-90 to 90)

##### `detect_gadgets()`

```python
events = engine.detect_gadgets(
    phone_detected: bool = False,
    earphone_detected: bool = False,
    notes_detected: bool = False,
    secondary_screen_detected: bool = False
) -> List[CheatEvent]
```

##### `process_frame()`

```python
analysis = engine.process_frame(**detection_results) -> CheatingAnalysis
```

**Returns:** `CheatingAnalysis` with score and events

---

## UI Dashboard

### Class: `CheatingDetectionDashboard`

Real-time visualization dashboard.

#### Constructor

```python
dashboard = CheatingDetectionDashboard(width: int = 1920, height: int = 1440)
```

#### Methods

##### `update()`

```python
display_frame = dashboard.update(
    frame: np.ndarray,
    analysis: CheatingAnalysis,
    stats: Dict
) -> np.ndarray
```

**Returns:** Rendered dashboard frame (OpenCV format)

**Example:**
```python
import cv2

dashboard = CheatingDetectionDashboard(1920, 1440)

while True:
    ret, frame = cap.read()
    analysis = detector.analyze_frame(frame, ...)
    
    stats = {
        'total_events': 45,
        'critical_events': 3,
        'duration_sec': 120
    }
    
    display_frame = dashboard.update(frame, analysis, stats)
    cv2.imshow("Dashboard", display_frame)
```

### Function: `create_simple_ui()`

Simple overlay UI alternative.

```python
output_frame = create_simple_ui(
    frame: np.ndarray,
    analysis: CheatingAnalysis
) -> np.ndarray
```

**Returns:** Frame with overlay UI

---

## Evidence Manager

### Class: `EvidenceManager`

Manages evidence capture and storage.

#### Constructor

```python
manager = EvidenceManager(base_path: str = "log/evidence")
```

#### Methods

##### `capture_frame()`

```python
filepath, checksum = manager.capture_frame(
    frame: np.ndarray,
    session_id: str,
    timestamp: float,
    event_type: str,
    score: float,
    frame_index: int
) -> Tuple[str, str]
```

**Returns:** (file path, SHA256 checksum)

##### `export_manifest()`

```python
manifest_file = manager.export_manifest(session_id: str) -> str
```

**Returns:** Path to manifest JSON file

##### `cleanup_old_evidence()`

```python
manager.cleanup_old_evidence(retention_days: int)
```

---

## Notification Manager

### Class: `NotificationManager`

Handles multi-channel notifications.

#### Constructor

```python
notifier = NotificationManager(config: AlarmConfig)
```

#### Methods

##### `send_webhook()`

```python
notifier.send_webhook(
    alarm_event: AlarmEvent,
    evidence_urls: List[str]
)
```

##### `send_email()`

```python
notifier.send_email(
    recipient_email: str,
    level: AlarmLevel,
    alarm_event: AlarmEvent
)
```

##### `send_sms()`

```python
notifier.send_sms(
    phone_number: str,
    level: AlarmLevel,
    session_id: str
)
```

---

## Data Structures

### Enum: `AlarmLevel`

```python
class AlarmLevel(Enum):
    NONE = 0
    NOTICE = 1      # 6-15 score
    LOW = 2         # 15-25 score
    MEDIUM = 3      # 25-40 score
    HIGH = 4        # 40-60 score
    CRITICAL = 5    # 60+ score
```

### Enum: `OperatorAction`

```python
class OperatorAction(Enum):
    ACKNOWLEDGE = "acknowledge"
    MARK_FALSE_POSITIVE = "false_positive"
    LOCK_EXAM = "lock_exam"
    UNLOCK_EXAM = "unlock_exam"
    REQUEST_LIVE_VIEW = "live_view"
    REQUEST_STUDENT_RESPONSE = "student_response"
```

### Dataclass: `AlarmEvent`

```python
@dataclass
class AlarmEvent:
    timestamp: float              # Unix timestamp
    frame_index: int              # Frame number
    level: AlarmLevel             # Alarm severity
    score: float                  # Cheating score (0-100)
    events: List[Dict]            # Detected events
    session_id: str               # Session ID
    user_id: str                  # Student/user ID
    exam_id: str                  # Exam ID
    device_metadata: Dict         # Device info
    evidence_files: List[str]     # Captured evidence paths
    corroborated: bool            # Multi-modal validation
    incident_id: str              # Unique incident ID
```

### Dataclass: `AlarmConfig`

```python
@dataclass
class AlarmConfig:
    thresholds: Dict[str, float]  # Score thresholds
    debounce: Dict[str, float]    # Debounce windows (seconds)
    cooldown: Dict[str, float]    # Cooldown periods (seconds)
    phone_persist_frames: int     # Persistence threshold
    phone_persist_time_s: float   # Time threshold
    face_missing_warn_s: float    # LOW threshold (0.6s)
    face_missing_high_s: float    # HIGH threshold (2.0s)
    retain_evidence_days: int     # Retention policy
    notify_webhook_on: List[str]  # Webhook levels
    notify_email_on: List[str]    # Email levels
    notify_sms_on: List[str]      # SMS levels
    auto_pause_on_critical: bool  # Auto-pause policy
    require_multi_modal_corroboration: bool
    test_mode: bool               # No incident logging
    verbose_logging: bool         # Debug output
```

### Dataclass: `OperatorOverride`

```python
@dataclass
class OperatorOverride:
    timestamp: float              # When action was taken
    operator_id: str              # Operator ID
    action: OperatorAction        # Action type
    reason: str                   # Explanation
    session_id: str               # Session ID
    incident_id: Optional[str]    # Related incident
    is_false_positive: bool       # False positive flag
```

---

## Common Workflows

### Workflow 1: Basic Session

```python
from alarm_escalation_controller import AlarmAndEscalationController, AlarmConfig

# 1. Initialize
config = AlarmConfig()
controller = AlarmAndEscalationController(
    config=config,
    session_id="session_1",
    user_id="student_123",
    exam_id="final_exam"
)

# 2. Main loop
frame_count = 0
while True:
    ret, frame = cap.read()
    analysis = detector.analyze_frame(frame, ...)
    
    # 3. Process through alarm controller
    alarm = controller.process_frame(
        frame=frame,
        cheating_score=analysis.cheating_score,
        events=analysis.events,
        face_detected=True,
        frame_index=frame_count
    )
    
    if alarm:
        print(f"Alarm: {alarm.level.name}")
    
    frame_count += 1

# 4. Export report
controller.export_session_evidence()
```

### Workflow 2: Operator Override

```python
# When proctor reviews incident
if operator_says_false_positive:
    controller.operator_action(
        operator_id="proctor_alice",
        action=OperatorAction.MARK_FALSE_POSITIVE,
        reason="Student was just yawning"
    )
elif operator_confirms_cheating:
    controller.operator_action(
        operator_id="proctor_alice",
        action=OperatorAction.LOCK_EXAM,
        reason="Confirmed phone usage"
    )
```

### Workflow 3: Custom Notifications

```python
# Set callbacks
def custom_alarm_handler(event):
    if event.level == AlarmLevel.CRITICAL:
        # Call custom API
        requests.post(
            "https://my-system.com/api/cheating",
            json={
                "student_id": event.user_id,
                "score": event.score,
                "incident_id": event.incident_id
            }
        )

controller.on_alarm_callback = custom_alarm_handler
```

---

## Error Handling

```python
from alarm_escalation_controller import AlarmAndEscalationController

try:
    alarm_event = controller.process_frame(
        frame=frame,
        cheating_score=score,
        events=events,
        face_detected=face_detected,
        frame_index=frame_idx
    )
except Exception as e:
    print(f"Alarm processing error: {e}")
    # Continue without escalation
    pass
```

---

## Environment Variables

```bash
# Webhooks
export PROCTOR_WEBHOOK_URL="https://..."

# Email
export PROCTOR_EMAIL="proctor@example.com"
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
export SENDER_EMAIL="alerts@example.com"
export SENDER_PASSWORD="password"

# SMS
export PROCTOR_PHONE="+1234567890"
export SMS_API_URL="https://..."
export SMS_API_KEY="key"
```

---

**API Version:** 2.0  
**Last Updated:** December 1, 2025
