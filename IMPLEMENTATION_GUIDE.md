# Proctor+ v4 Complete Implementation Guide

## 📋 System Overview

Proctor+ is a production-grade exam proctoring platform with:

- **Frontend**: Real-time web UI with MediaPipe face/hand detection
- **Backend**: Flask API with SQLite database for evidence storage
- **Webhooks**: Full bidirectional communication between client and server
- **Evidence**: Automatic capture and SHA256 verification
- **Operator Control**: Real-time intervention capabilities

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.9+ with these packages installed
pip install flask flask-cors

# For the browser:
# - Chrome 90+, Firefox 88+, Safari 14+
# - Webcam access required
```

### 1. Start Backend API Server

```bash
# From workspace root
python proctor_api.py
```

Expected output:
```
Starting Proctor+ API server on http://localhost:5000
INFO: Database initialized
INFO: * Running on http://0.0.0.0:5000
```

### 2. Open Web UI

```bash
# Open in web browser
file:///c:/Users/Lenovo/Desktop/Cheat detection/proctor_web_ui.html

# OR serve via simple HTTP
python -m http.server 8000
# Then visit http://localhost:8000/proctor_web_ui.html
```

### 3. Start Session

1. Allow camera access when prompted
2. Enter student name and exam name (or use defaults)
3. Click **"Start Monitoring"**
4. Follow 9-point calibration (click targets on screen)
5. System begins real-time monitoring

## 🔧 Configuration

### Frontend Settings (proctor_webhooks.js)

```javascript
const WEBHOOK_CONFIG = {
    baseUrl: 'http://localhost:5000',  // Change for production
    uploadBatchSize: 5,                // Evidence per upload
    uploadInterval: 5000,              // ms between uploads
    maxRetries: 3,                     // Retry failed uploads
};
```

### Gaze & Detection (proctor_core.js)

```javascript
const CONFIG = {
    gaze: {
        calibration_samples: 30,       // Higher = more accurate
        ema_alpha: 0.35,               // Smoothing (0=smooth, 1=raw)
        glance_threshold: 0.20,        // Deviation limit
        long_glance_sec: 0.8           // Persistence time
    },
    alarm: {
        thresholds: {
            notice: 6,
            low: 15,
            medium: 25,
            high: 40,
            critical: 60
        }
    }
};
```

## 📊 Dashboard Features

### Real-Time Monitoring

- **Score Pill**: Color-coded alarm level (0-100)
- **Status Badge**: Monitoring / Calibrating / Paused
- **Gauge Group**: Head pose (yaw/pitch/roll) in real-time
- **Timeline Dots**: Last 10 events visualized
- **Events List**: Scrollable log of detections

### Evidence Gallery

- Automatic capture on CRITICAL alarms
- Manual capture via "Capture" button
- Thumbnail grid (max 12 visible)
- SHA256 checksums for verification
- Hover for upload latency info

### Performance Metrics

- **FPS**: Frames per second (target: 30+)
- **CPU**: Estimated processor usage
- **Uptime**: Session duration
- **Frame Count**: Total frames processed
- **Charts**: 60-second score and audio history

## 🎯 Alarm System

### Five-Level Escalation

| Level | Score | Action | Sound |
|-------|-------|--------|-------|
| NONE | 0-5 | Continue | - |
| NOTICE | 6-14 | Log only | - |
| LOW | 15-24 | Log & notify | ✓ |
| MEDIUM | 25-39 | Announce | ✓ |
| HIGH | 40-59 | Capture + operator alert | ✓✓ |
| CRITICAL | 60+ | Pause + full-screen modal | ✓✓✓ |

### Event Scoring

- **Gaze Deviation** (0.8): Eyes off-screen >800ms
- **Head Turn** (1.5): Yaw >25° from center
- **Extreme Turn** (4.0): Yaw >45° from center
- **Hand-Face Overlap** (2.5): Hand obscures face
- **Phone Detection** (20): Mobile device visible
- **External Voice** (8): Non-student speaker detected

## 🔐 Security & Privacy

### Evidence Storage

```
evidence_storage/
├── {session_id}/
│   ├── CRITICAL/
│   │   ├── ev_1234567890_abc.jpg
│   │   └── checksum: SHA256
│   └── HIGH/
```

- **Retention**: 90 days default (configurable)
- **Checksums**: SHA256 for integrity verification
- **Encryption**: TLS/SSL in production
- **Access Control**: Token-based authentication

### Student Privacy

- No audio recording (configurable)
- Video processed locally, not stored
- Evidence auto-deleted after retention period
- Operator can view but not download evidence
- GDPR compliance: Right to deletion supported

## 📡 Webhook API Reference

### Session Endpoints

**POST /api/v1/sessions/start**
```json
Request:
{
  "student_name": "John Doe",
  "exam_name": "Final Exam",
  "session_id": "sess_1701388800123",
  "user_id": "user_abc123"
}

Response:
{
  "success": true,
  "session_id": "sess_1701388800123",
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "status": "active"
}
```

**POST /api/v1/sessions/end**
```json
Request:
{
  "reason": "exam_completed",
  "final_score": 45.3,
  "final_level": "HIGH",
  "duration_seconds": 1800,
  "evidence_count": 23
}

Response:
{
  "success": true,
  "session_duration": 1800,
  "evidence_processed": 23
}
```

### Alarm Endpoints

**POST /api/v1/alarms/event**
```json
Request:
{
  "level": "MEDIUM",
  "score": 32.5,
  "frame_number": 945,
  "corroboration": {
    "event_count": 5,
    "recent_events": [
      {"type": "gaze_deviation", "weight": 0.8},
      {"type": "head_turn", "weight": 1.5}
    ],
    "head_pose": {"yaw": 28, "pitch": 5, "roll": 2},
    "gaze_position": {"x": 0.35, "y": 0.42},
    "face_detected": true,
    "hand_detected": false
  }
}

Response:
{
  "success": true,
  "alarm_id": "alm_abc123def456",
  "status": "recorded",
  "actions": [
    {"type": "message", "message": "Please focus on exam..."}
  ]
}
```

### Evidence Endpoints

**POST /api/v1/evidence/upload** (multipart/form-data)
```
Fields:
- image: JPEG file (max 5MB)
- session_id: string
- evidence_id: string
- event_type: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
- severity: number (0-100)
- timestamp: ISO8601
- frame_number: integer
- checksum: SHA256 hex

Response:
{
  "success": true,
  "evidence_id": "ev_1701388901234_xyz",
  "file_path": "/path/to/evidence.jpg",
  "size": 45678,
  "checksum": "a1b2c3d4e5..."
}
```

**GET /api/v1/evidence/list/{session_id}**
```json
Response:
{
  "success": true,
  "session_id": "sess_123",
  "count": 23,
  "evidence": [
    {
      "evidence_id": "ev_1234",
      "event_type": "CRITICAL",
      "severity": 65.3,
      "timestamp": "2025-12-01T14:30:45Z",
      "file_size": 45678
    }
  ]
}
```

## 🎮 Operator Controls

### Real-Time Actions

```javascript
// These actions are triggered from dashboard
acknowledgeAlarm()      // Dismiss alarm notification
pauseExam()             // Pause exam (student sees message)
resumeExam()            // Resume paused exam
sendMessage(msg)        // TTS announcement to student
captureEvidence()       // Manual evidence snapshot
startCalibration()      // Restart calibration
resetScore()            // Clear accumulated score
stopMonitoring()        // End exam session
```

### Operator Dashboard (Admin Interface)

```bash
# TODO: Create admin panel showing:
# - Active sessions
# - Real-time alarm feed
# - Evidence review
# - Student performance
# - Session history
```

## 📈 Performance Optimization

### Target Metrics

- **Detection FPS**: 30 fps minimum
- **Latency**: <100ms from event to alarm
- **Evidence Upload**: <2s per 5MB batch
- **Memory**: <200MB for browser session

### Optimization Tips

1. **Gaze Calibration**
   - Increase `calibration_samples` for better accuracy
   - Decrease for faster startup
   - Sweet spot: 20-40 samples

2. **Smoothing**
   - Increase `ema_alpha` (0.5-0.8) for responsiveness
   - Decrease (0.1-0.3) for stability
   - Default 0.35 is balanced

3. **Detection**
   - Disable `PROCESS_EVERY_N` > 3 for slower hardware
   - Set to 1 for maximum accuracy

## 🐛 Troubleshooting

### Camera Not Working

```javascript
// Browser console
navigator.mediaDevices.enumerateDevices()
  .then(devices => {
    console.log('Available devices:', devices);
  });
```

**Solution**: 
- Check camera permissions
- Reload page and click "Allow"
- Try different browser

### Low FPS

- Reduce evidence upload batch size
- Disable audio RMS analysis
- Close other browser tabs
- Update GPU drivers

### Token Expiration

```javascript
// Session expires after 12 hours
// Extend: POST /api/v1/sessions/refresh
// Or start new session
```

### Evidence Upload Failures

- Check backend server is running
- Verify `baseUrl` in proctor_webhooks.js
- Check network latency (>500ms = issues)
- Look at browser console errors

## 📚 File Structure

```
Cheat detection/
├── proctor_web_ui.html      (1900 lines) - Main UI
├── proctor_core.js          (800 lines)  - Detection engine
├── proctor_webhooks.js      (600 lines)  - API integration
├── proctor_api.py           (700 lines)  - Flask backend
├── alarm_escalation_controller.py (v2.3) - Alarm logic
├── main.py                  - Video pipeline
├── requirements.txt         - Python packages
├── evidence_storage/        - Evidence directory
├── log/
│   ├── api.log
│   └── evidence/
└── proctor_sessions.db      - SQLite database
```

## 🔗 Integration Examples

### Custom Event Scoring

```javascript
// In proctor_core.js, add to detectBehavior():
if (someCustomCondition) {
    addEvent('custom_event', 3.5, { detail: 'your_data' });
}
```

### External Webhook

```javascript
// In proctor_webhooks.js:
// Add custom endpoint
async function sendToExternalSystem(data) {
    await fetch('https://your-lms.com/api/events', {
        method: 'POST',
        body: JSON.stringify(data)
    });
}
```

### Analytics Export

```python
# In proctor_api.py:
# Export to CSV/JSON
@app.route('/api/v1/export/session/<session_id>')
def export_session(session_id):
    # Query database
    # Generate CSV/JSON
    # Return file
```

## 🧪 Testing

### Unit Tests (Backend)

```bash
python -m pytest tests/
```

### Integration Tests

```javascript
// Browser console
// Simulate events
state.currentScore = 50;
calculateScore();
alarmTick(50, []);  // Should trigger MEDIUM alarm
```

### Load Testing

```bash
# 100 concurrent sessions
ab -n 100 -c 10 http://localhost:5000/health
```

## 📝 Logging

### Backend Logs

```bash
tail -f log/api.log

# Output:
# 2025-12-01 14:30:45 - Session started: sess_123 - John Doe - Final Exam
# 2025-12-01 14:30:52 - Calibration complete: sess_123
# 2025-12-01 14:31:15 - Alarm MEDIUM: sess_123 | Score: 32.5
# 2025-12-01 14:31:28 - Evidence uploaded: ev_1234 (234ms)
```

### Browser Console

```javascript
// Debug mode
localStorage.setItem('debugMode', 'true');
// Verbose logging of all events
```

## 🚢 Production Deployment

### Docker Setup

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "proctor_api.py"]
```

### Environment Variables

```bash
# .env file
FLASK_ENV=production
DATABASE_URL=postgresql://user:pass@host/db
EVIDENCE_STORAGE=/mnt/evidence
LOG_LEVEL=INFO
SESSION_TIMEOUT=43200  # 12 hours
MAX_EVIDENCE_SIZE=52428800  # 50MB
```

### HTTPS Setup

```bash
# Generate certificates
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# Update proctor_api.py
app.run(
    ssl_context=('cert.pem', 'key.pem'),
    host='0.0.0.0',
    port=5000
)
```

## 📞 Support

For issues:
1. Check browser console (F12)
2. Check server logs (log/api.log)
3. Review alarm_escalation_controller.py logs
4. Test API endpoints with curl/Postman

## 📄 License

Proctor+ v4 - © 2025 All Rights Reserved
