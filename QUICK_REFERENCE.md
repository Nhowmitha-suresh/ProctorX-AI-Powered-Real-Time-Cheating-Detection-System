# 🚀 Proctor+ v4 - Quick Reference Card

## ⚡ 3-Minute Startup

### Terminal 1: Backend API
```bash
cd "c:\Users\Lenovo\Desktop\Cheat detection"
python proctor_api.py
```
✓ Runs on http://localhost:5000

### Terminal 2: Web UI
```bash
# Option A: Direct file
file:///c:/Users/Lenovo/Desktop/Cheat detection/proctor_web_ui.html

# Option B: HTTP server
python -m http.server 8000
# Then: http://localhost:8000/proctor_web_ui.html
```

## 🎮 User Interface Map

```
┌─────────────────────────────────────────────────────────┐
│ BRAND LOGO │ SESSION INFO │ STATUS │ FPS │ CPU │ RES │  TOP BAR
├─────────────────────────────────────────────────────────┤
│                    │            │                      │
│   VIDEO CANVAS     │  STATUS    │                      │
│   (Face tracking,  │  PANEL     │  CONTROL             │
│    iris dots,      │            │  COLUMN              │
│    HUD overlays)   │  CALIB.    │  (6 panels)          │
│                    │  WIDGET    │                      │
│                    │            │  ALARM               │
│                    │  ALARMS    │  PANEL               │
│                    │            │                      │
│                    │  EVENTS    │  EVENTS              │
│                    │  LIST      │  LOG                 │
│                    │            │                      │
│                    │  EVIDENCE  │  GALLERY             │
│                    │  GALLERY   │                      │
│                    │            │  CONTROLS            │
├─────────────────────────────────────────────────────────┤
│  SCORE CHART (60s) │ AUDIO CHART (60s) │ METRICS     │  FOOTER
└─────────────────────────────────────────────────────────┘
```

## 🎯 Workflow

### Step 1: Start
Click **"Start Monitoring"** button

### Step 2: Calibrate
1. See **9 dots** on screen
2. **Look at each dot** (30 samples total)
3. Wait for **"Calibration complete"**

### Step 3: Monitor
- Score rises as suspicious behavior detected
- Alarm level changes (NOTICE → LOW → MEDIUM → HIGH → CRITICAL)
- Events logged in real-time

### Step 4: Respond (if needed)
- **Acknowledge**: Dismiss alarm
- **Pause**: Stop exam
- **Capture**: Manual evidence snapshot
- **Message**: Send TTS to student

### Step 5: End
Click **"Stop Monitoring"** to end session

## 📊 Score Interpretation

| Score | Level | Action | Color |
|-------|-------|--------|-------|
| 0-5 | NONE | Monitoring | 🔵 Blue |
| 6-14 | NOTICE | Log event | 🔵 Cyan |
| 15-24 | LOW | Notify | 🟡 Yellow |
| 25-39 | MEDIUM | Announce | 🟠 Orange |
| 40-59 | HIGH | Capture | 🔴 Red |
| 60+ | CRITICAL | Pause | 🔴 Dark Red |

## 🎪 Control Buttons

| Button | Function |
|--------|----------|
| **Start** | Begin monitoring session |
| **Stop** | End session and upload evidence |
| **Calibrate** | Restart 9-point calibration |
| **Acknowledge** | Dismiss alarm notification |
| **Pause** | Pause exam (sends TTS message) |
| **Capture** | Manual evidence snapshot |
| **Message** | Send TTS to student |
| **Reset** | Clear accumulated score |

## 📸 Evidence Management

### Auto-Capture
- Triggered on CRITICAL alarm
- Saves to evidence gallery
- Uploaded to server with checksum

### Manual Capture
- Click **"Capture"** button
- Current frame saved
- Added to gallery

### Upload
- Automatic batching (5 per request)
- Retry on failure (max 3 attempts)
- SHA256 checksum verification

## 🔧 Configuration (If Needed)

### Gaze Sensitivity
Edit `proctor_core.js`:
```javascript
CONFIG.gaze.glance_threshold = 0.20  // Lower = more sensitive
CONFIG.gaze.long_glance_sec = 0.8    // Shorter = more sensitive
```

### Alarm Thresholds
Edit `proctor_core.js`:
```javascript
CONFIG.alarm.thresholds.critical = 60  // Lower = easier to trigger
```

### API Endpoint
Edit `proctor_webhooks.js`:
```javascript
WEBHOOK_CONFIG.baseUrl = 'http://your-server.com'
```

## 🆘 Troubleshooting

### "Camera Permission Denied"
1. Reload page
2. Click **Allow** when prompted
3. Try different browser

### "Cannot connect to API"
1. Check backend is running (`python proctor_api.py`)
2. Check `localhost:5000/health` responds
3. Verify firewall allows port 5000

### "Low FPS (<20)"
1. Close other browser tabs
2. Restart browser
3. Try different computer

### "Calibration Not Completing"
1. Ensure face is visible
2. Click all 9 dots clearly
3. Restart calibration

## 📊 Keyboard Shortcuts

```
F12        Open browser console (debug)
Ctrl+Shift+I  Open developer tools
Ctrl+R     Reload page
F11        Fullscreen mode
```

## 🔗 Important URLs

```
Web UI:     file:///c:/Users/Lenovo/Desktop/Cheat detection/proctor_web_ui.html
API Health: http://localhost:5000/health
API Docs:   See API_REFERENCE.md
```

## 📱 Browser Requirements

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

**Requires**: Webcam, stable internet (for webhooks)

## 🎯 Key Metrics Explained

### FPS (Frames Per Second)
- Target: 30+ FPS
- <20 FPS: Likely camera or hardware issue

### CPU
- 0-30%: Good
- 30-50%: Normal
- >50%: High load

### UPTIME
- Shows session duration
- Format: MM:SS

### SCORE
- 0 = No suspicious activity
- 100 = Maximum alarm level
- Updates every 100ms

## 🔐 Security Notes

- ✅ Tokens expire with session
- ✅ Evidence checksummed
- ✅ HTTPS in production (configure)
- ✅ No student PII in logs
- ✅ Evidence auto-deleted (90 days)

## 📈 Event Types Detected

| Event | Points | Trigger |
|-------|--------|---------|
| Gaze Deviation | 0.8 | Eyes off-screen >800ms |
| Head Turn | 1.5 | Yaw >25° |
| Extreme Turn | 4.0 | Yaw >45° |
| Hand-Face | 2.5 | Hand touches face |
| Phone | 20 | Mobile detected |
| Voice | 8 | Non-student speaker |

## 💾 Database Tables

```
sessions          - Active/completed exams
alarms            - Alarm events logged
evidence          - Captured snapshots
operator_actions  - Manual interventions
```

Access via:
```bash
sqlite3 proctor_sessions.db
sqlite> SELECT * FROM sessions;
```

## 📞 Support

**Error in Console?**
```
1. Copy error message
2. Check IMPLEMENTATION_GUIDE.md troubleshooting
3. Review API_REFERENCE.md
```

**Backend Issues?**
```
1. Check server logs: log/api.log
2. Verify port 5000 available
3. Check Python version: python --version
```

## 🎓 Documentation

| File | Purpose |
|------|---------|
| README_PROCTOR_V4.md | Overview + features |
| IMPLEMENTATION_GUIDE.md | Setup + configuration |
| API_REFERENCE.md | Webhook endpoints |
| COMPLETION_SUMMARY.md | Architecture + status |

---

**Proctor+ v4** | Production-Ready Exam Proctoring  
Version 4.0.0 | December 1, 2025
