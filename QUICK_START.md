# Quick Start Guide - Advanced Cheating Detection System

## Installation

### 1. Prerequisites
- Python 3.9+
- Windows/Linux/macOS
- Webcam
- ~500MB free disk space

### 2. Setup Virtual Environment

```bash
cd "Cheat detection"
.\mp_env\Scripts\activate
```

### 3. Run System

```bash
python main.py
```

**Press 'q' to stop**

---

## Basic Usage

### Starting a Proctoring Session

The system automatically initializes with:
- **Session ID**: Auto-generated (e.g., "a1b2c3d4")
- **User ID**: "student_001" (customize in main.py)
- **Exam ID**: "exam_2025_001" (customize in main.py)

### Monitoring the Dashboard

**Real-time Display Shows:**
- 🔴 **Cheating Score** (0-100)
- 📊 **Score Timeline** (trending)
- 📋 **Recent Events** (last 5 detections)
- ⚠️ **Alarm Level** (NOTICE/LOW/MEDIUM/HIGH/CRITICAL)
- 🎯 **Recommended Action** (next step for proctor)
- 📹 **Live Video Feed** (1400x800 embedded)
- 📈 **Event Breakdown** (type distribution)

### Color Coding

- 🟢 **GREEN** = Low Suspicion
- 🟡 **YELLOW** = Medium Suspicion
- 🟠 **ORANGE** = High Suspicion
- 🔴 **RED** = Critical Alert

---

## Configuration

### Quick Tweaks

Edit in `main.py`:

```python
alarm_config = AlarmConfig(
    # Thresholds (adjust sensitivity)
    thresholds={
        "critical": 60.0,  # Lower = more sensitive
        "high": 40.0,
        ...
    },
    
    # Debounce (delay before escalating)
    debounce={"medium": 1.2, ...},
    
    # Cooldown (suppress repeat alerts)
    cooldown={"medium": 6.0, ...},
    
    # Auto-pause exam on critical
    auto_pause_on_critical=False,  # Set to True
)
```

### Full Configuration

Edit `alarm_config_template.json` and load in code:

```python
import json
with open('alarm_config_template.json') as f:
    config_dict = json.load(f)
alarm_config = AlarmConfig(**config_dict['alarm_thresholds'])
```

---

## Outputs & Results

### Session Reports

After session ends, check:

```
log/evidence/
├── session_abc123_*.png           # Evidence frames
├── session_abc123_manifest.json   # Checksum audit
├── session_abc123_alarms.jsonl    # Alarm timeline
└── session_abc123_report.json     # Full report
```

### Sample Report JSON

```json
{
  "session_id": "a1b2c3d4",
  "user_id": "student_001",
  "exam_id": "exam_2025_001",
  "total_alarms": 5,
  "critical_alarms": 1,
  "high_alarms": 2,
  "medium_alarms": 2,
  "operator_actions": 0,
  "evidence_files": 15,
  "alarm_timeline": [
    {
      "timestamp": "2025-01-01T12:34:56.789Z",
      "level": "MEDIUM",
      "score": 32.5,
      "incident_id": "a1b2c3d4_1",
      "events": [...]
    }
  ]
}
```

---

## Operator Controls

### Acknowledge Alert (5 minutes)
```python
alarm_controller.operator_action(
    operator_id="proctor_001",
    action=OperatorAction.ACKNOWLEDGE,
    reason="False positive - student just stretching"
)
```

### Mark as False Positive
```python
alarm_controller.operator_action(
    operator_id="proctor_001",
    action=OperatorAction.MARK_FALSE_POSITIVE,
    reason="Camera glitch"
)
```

### Lock/Unlock Exam
```python
alarm_controller.operator_action(
    operator_id="proctor_001",
    action=OperatorAction.LOCK_EXAM,
    reason="Cheating detected"
)
```

---

## Notifications Setup

### Webhook (Monitoring Dashboard)

Set environment variable:
```bash
export PROCTOR_WEBHOOK_URL="https://dashboard.example.com/webhook"
```

System will POST JSON on MEDIUM+ alarms:
```json
{
  "level": "HIGH",
  "score": 45.5,
  "session_id": "a1b2c3d4",
  "incident_id": "a1b2c3d4_2",
  "evidence_urls": ["file1.png", "file2.mp4"],
  "timestamp": "2025-01-01T12:34:56Z"
}
```

### Email Alerts

```bash
export PROCTOR_EMAIL="proctor@example.com"
export SMTP_SERVER="smtp.gmail.com"
export SENDER_EMAIL="alerts@example.com"
export SENDER_PASSWORD="app_password"
```

### SMS Alerts

```bash
export PROCTOR_PHONE="+1234567890"
export SMS_API_URL="https://api.twilio.com/..."
export SMS_API_KEY="your_key"
```

---

## Troubleshooting

### Issue: "No webcam found"
```
Solution: Check camera permissions and try:
  - Restart application
  - Unplug/replug webcam
  - Check Device Manager for driver issues
```

### Issue: "Face not detected"
```
Solution: Ensure:
  - Face is clearly visible and well-lit
  - Camera is at eye level
  - No obstructions (sunglasses, masks)
  - Adequate lighting (>50 lux)
```

### Issue: Too many false positives
```
Solution: Adjust thresholds in AlarmConfig:
  - Increase thresholds (higher = less sensitive)
  - Increase debounce windows
  - Increase face_missing_warn_s
```

### Issue: Too many false negatives (not detecting cheating)
```
Solution:
  - Lower thresholds
  - Reduce debounce windows
  - Enable verbose_logging to see what events are detected
```

### Issue: Slow performance
```
Solution:
  - Use simpler UI: set use_simple_ui = True
  - Reduce dashboard resolution
  - Lower webcam resolution
  - Close background applications
```

---

## Advanced Features

### Test Mode (No Incident Logging)

```python
alarm_config = AlarmConfig(test_mode=True, verbose_logging=True)
```

Useful for: Training, debugging, development

### Verbose Logging

```python
alarm_config = AlarmConfig(verbose_logging=True)
```

Shows detailed traces for:
- Corroboration checks
- Alarm transitions
- Evidence captures
- Webhook sends

### Custom Callbacks

```python
def on_alarm_triggered(alarm_event):
    # Custom logic when alarm fires
    print(f"Alarm! Level: {alarm_event.level}")
    # Send custom notification, log to external DB, etc.

def on_exam_paused(incident_id):
    # Custom logic when exam is paused
    print(f"Exam paused: {incident_id}")
    # Call your LMS API, notify institution, etc.

alarm_controller.on_alarm_callback = on_alarm_triggered
alarm_controller.on_exam_pause_callback = on_exam_paused
```

### UI Customization

Simple overlay UI (instead of full dashboard):
```python
use_simple_ui = True  # in main.py
```

Dashboard resolution:
```python
dashboard = CheatingDetectionDashboard(width=1280, height=720)
```

---

## Best Practices

✅ **DO:**
- Review false positives regularly
- Calibrate thresholds per exam
- Educate students on system (reduce anxiety)
- Use multi-channel notifications (webhook + email)
- Export evidence weekly for compliance
- Log all operator actions

❌ **DON'T:**
- Set thresholds too low (excessive false positives)
- Use single sensor for critical decisions
- Share raw evidence without permission
- Rely solely on automated system (always have human review)
- Disable audit logging
- Auto-lock exams without operator review

---

## Performance Tips

- **Target FPS**: 30 (adjust if lower on weak hardware)
- **Memory Usage**: ~500MB baseline
- **Latency**: <100ms from capture to alarm decision
- **Storage**: ~10MB per 10-minute session

For slower machines:
```python
# Reduce FPS
cv2.waitKey(50)  # ~20 FPS instead of 30

# Use simple UI
use_simple_ui = True

# Disable timeline graph
# (modify ui_dashboard.py)
```

---

## Integration Examples

### Blackboard LMS Integration
```python
def send_to_lms(incident_id, user_id, exam_id):
    import requests
    requests.post(
        "https://blackboard.example.com/api/incidents",
        json={
            "student_id": user_id,
            "exam_id": exam_id,
            "incident_id": incident_id,
            "flagged_for_review": True
        }
    )
```

### Canvas LMS Integration
```python
def flag_canvas_submission(exam_id, user_id):
    import canvasapi
    canvas = canvasapi.Canvas("https://canvas.example.com", "token")
    # Flag submission for manual review
```

### SIEM Integration (Splunk)
```python
def send_to_splunk(alarm_event):
    import requests
    requests.post(
        "https://splunk.example.com/services/collector",
        headers={"Authorization": "Splunk token"},
        json=alarm_event.__dict__
    )
```

---

## Privacy Checklist

- [ ] Evidence retention configured (default 90 days)
- [ ] Third-party sharing disabled (unless approved)
- [ ] GDPR compliance enabled
- [ ] FERPA compliance enabled
- [ ] Operator actions logged
- [ ] Evidence checksums verified
- [ ] Session IDs used (no PII in logs)
- [ ] Accessibility features enabled

---

## Support

For issues or questions:
1. Check SYSTEM_DOCUMENTATION.md
2. Enable verbose_logging
3. Review session report
4. Check evidence files for context
5. Contact your system administrator

---

**Happy Proctoring! 🎓**

Version: 2.0 | Last Updated: December 1, 2025
