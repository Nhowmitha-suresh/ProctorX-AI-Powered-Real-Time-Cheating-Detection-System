/**
 * Proctor+ v4 Core Logic
 * Real-time exam proctoring with MediaPipe + YOLO detection
 */

// ============================================================================
// CONFIG & CONSTANTS
// ============================================================================

const CONFIG = {
    gaze: {
        calibration_samples: 30,
        ema_alpha: 0.35,
        glance_threshold: 0.20,
        long_glance_sec: 0.8
    },
    head: {
        head_turn_threshold: 0.25,
        extreme_turn_threshold: 0.45
    },
    hand: {
        hand_face_overlap_threshold: 0.20,
        hand_near_distance_ratio: 0.5
    },
    audio: {
        rms_threshold: 0.035
    },
    weights: {
        glance: 0.8,
        head_turn: 1.5,
        extreme_turn: 4.0,
        mouth_open: 1.0,
        hand_overlap: 2.5,
        phone_detect: 20,
        external_voice: 8
    },
    alarm: {
        thresholds: { notice: 6, low: 15, medium: 25, high: 40, critical: 60 },
        debounce: { notice: 0.4, low: 0.6, medium: 1.2 },
        cooldown: { low: 4, medium: 6, high: 12, critical: 30 }
    },
    PROCESS_EVERY_N: 3
};

const ALARM_LEVELS = ['NONE', 'NOTICE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const ALARM_COLORS = {
    'NONE': '#7fffd4',
    'NOTICE': '#7fffd4',
    'LOW': '#ffcc00',
    'MEDIUM': '#ffcc00',
    'HIGH': '#ff6644',
    'CRITICAL': '#ff4444'
};

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

const state = {
    sessionId: 'sess_' + Date.now(),
    userId: 'user_' + Math.random().toString(36).substr(2, 9),
    examName: 'Final Exam',
    studentName: 'Student',

    // Calibration
    calibrationSamples: [],
    calibrationCenter: { x: 0.5, y: 0.5 },
    calibrated: false,
    calibrationMode: false,

    // Gaze
    gazeEMA: { x: 0.5, y: 0.5 },
    gazeHistory: [],
    gazePersistenceTimer: 0,

    // Head Pose
    headYaw: 0,
    headPitch: 0,
    headRoll: 0,

    // Score & Alarm
    currentScore: 0,
    currentLevel: 'NONE',
    lastAlarmAt: {},
    recentEvents: [],
    evidenceFiles: [],

    // Performance
    frameCount: 0,
    lastFrameTime: Date.now(),
    fps: 0,
    processingTime: 0,

    // Detection
    faceDetected: false,
    handDetected: false,
    phoneDetected: false,
    faceBbox: null,
    handBbox: null,
    phoneBbox: null,
    irisPoints: null,

    // Charts
    scoreHistory: new Array(60).fill(0),
    audioHistory: new Array(60).fill(0)
};

// ============================================================================
// DOM ELEMENTS
// ============================================================================

const elements = {
    videoCanvas: document.getElementById('videoCanvas'),
    sessionTitle: document.getElementById('sessionTitle'),
    fpsDisplay: document.getElementById('fpsDisplay'),
    cpuDisplay: document.getElementById('cpuDisplay'),
    resDisplay: document.getElementById('resDisplay'),
    scorePill: document.getElementById('scorePill'),
    statusBadge: document.getElementById('statusBadge'),
    statusText: document.getElementById('statusText'),
    statusDetail: document.getElementById('statusDetail'),
    alarmLevel: document.getElementById('alarmLevel'),
    alarmPanel: document.getElementById('alarmPanel'),
    eventsList: document.getElementById('eventsList'),
    evidenceGallery: document.getElementById('evidenceGallery'),
    timelineGroup: document.getElementById('timelineGroup'),
    scoreChart: document.getElementById('scoreChart'),
    audioChart: document.getElementById('audioChart'),
    uptimeDisplay: document.getElementById('uptimeDisplay'),
    frameCountDisplay: document.getElementById('frameCountDisplay'),
    calibrationTarget: document.getElementById('calibrationTarget'),
    calibProgressBar: document.getElementById('calibProgressBar'),
    calibProgress: document.getElementById('calibProgress'),
    gaugeYaw: document.getElementById('gaugeYaw'),
    gaugePitch: document.getElementById('gaugePitch'),
    gaugeRoll: document.getElementById('gaugeRoll'),
    criticalModal: document.getElementById('criticalModal'),
    criticalMessage: document.getElementById('criticalMessage')
};

// ============================================================================
// INITIALIZATION
// ============================================================================

async function initializeSystem() {
    console.log('🚀 Initializing Proctor+ v4...');

    try {
        // Update UI
        updateSessionInfo();

        // Initialize video canvas
        const ctx = elements.videoCanvas.getContext('2d');

        // Setup MediaPipe
        const faceMesh = new MediaPipe.FaceMesh({
            locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`
        });

        const hands = new MediaPipe.Hands({
            locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`
        });

        // Setup camera
        const camera = new MediaPipe.Camera.Camera(elements.videoCanvas, {
            onFrame: async () => {
                await processingLoop(faceMesh, hands, ctx);
            },
            width: 1280,
            height: 720
        });

        // Event listeners
        setupEventListeners();

        // Start camera
        await camera.initialize();
        camera.start();

        console.log('✅ System initialized successfully');
    } catch (error) {
        console.error('❌ Initialization error:', error);
        alert('Failed to initialize system: ' + error.message);
    }
}

function setupEventListeners() {
    document.getElementById('calibrateBtn').addEventListener('click', startCalibration);
    document.getElementById('acknowledgeBtn').addEventListener('click', acknowledgeAlarm);
    document.getElementById('pauseBtn').addEventListener('click', pauseExam);
    document.getElementById('captureBtn').addEventListener('click', captureEvidence);
    document.getElementById('messageBtn').addEventListener('click', sendMessage);
    document.getElementById('startBtn').addEventListener('click', startMonitoring);
    document.getElementById('stopBtn').addEventListener('click', stopMonitoring);
    document.getElementById('recalibBtn').addEventListener('click', recalibrate);
    document.getElementById('resetBtn').addEventListener('click', resetScore);
    document.getElementById('dismissBtn').addEventListener('click', dismissCritical);
}

function updateSessionInfo() {
    const title = `Exam: ${state.examName} · Student: ${state.studentName} · Session: ${state.sessionId}`;
    elements.sessionTitle.textContent = title;
}

// ============================================================================
// CALIBRATION
// ============================================================================

function startCalibration() {
    state.calibrationMode = true;
    state.calibrationSamples = [];
    console.log('📍 Calibration started');
    elements.statusBadge.className = 'status-badge calibrating';
    elements.statusBadge.textContent = 'Calibrating';
}

function addCalibrationSample(iris) {
    if (!state.calibrationMode) return;

    // Normalize iris position to screen coordinates
    const nx = iris.x || 0.5;
    const ny = iris.y || 0.5;

    state.calibrationSamples.push({ x: nx, y: ny });
    updateCalibrationProgress();

    if (state.calibrationSamples.length >= CONFIG.gaze.calibration_samples) {
        finalizeCalibration();
    }
}

function updateCalibrationProgress() {
    const progress = state.calibrationSamples.length;
    elements.calibProgress.textContent = progress;
    elements.calibProgressBar.style.width = (progress / CONFIG.gaze.calibration_samples * 100) + '%';
}

function finalizeCalibration() {
    // Compute average iris center
    const avgX = state.calibrationSamples.reduce((sum, s) => sum + s.x, 0) / state.calibrationSamples.length;
    const avgY = state.calibrationSamples.reduce((sum, s) => sum + s.y, 0) / state.calibrationSamples.length;

    state.calibrationCenter = { x: avgX, y: avgY };
    state.calibrated = true;
    state.calibrationMode = false;

    console.log('✅ Calibration complete', state.calibrationCenter);
    elements.statusBadge.className = 'status-badge monitoring';
    elements.statusBadge.textContent = 'Monitoring';
}

// ============================================================================
// GAZE CALCULATION
// ============================================================================

function updateGazeEMA(nx, ny) {
    const alpha = CONFIG.gaze.ema_alpha;
    state.gazeEMA.x = alpha * nx + (1 - alpha) * state.gazeEMA.x;
    state.gazeEMA.y = alpha * ny + (1 - alpha) * state.gazeEMA.y;

    const dx = state.gazeEMA.x - state.calibrationCenter.x;
    const dy = state.gazeEMA.y - state.calibrationCenter.y;
    const mag = Math.hypot(dx, dy);

    state.gazeHistory.push({ dx, dy, mag, time: Date.now() });
    if (state.gazeHistory.length > 100) state.gazeHistory.shift();

    return { dx, dy, mag };
}

function detectGazeDeviation() {
    const threshold = CONFIG.gaze.glance_threshold;
    const persistTime = CONFIG.gaze.long_glance_sec * 1000;
    const now = Date.now();

    // Check if gaze is deviated beyond threshold
    const recentGaze = state.gazeHistory.filter(g => now - g.time < persistTime);
    if (recentGaze.length === 0) return 0;

    const avgMag = recentGaze.reduce((sum, g) => sum + g.mag, 0) / recentGaze.length;

    if (avgMag > threshold) {
        // Sustained gaze deviation
        addEvent('gaze_deviation', CONFIG.weights.glance, { magnitude: avgMag });
        return CONFIG.weights.glance;
    }

    return 0;
}

// ============================================================================
// HEAD POSE DETECTION
// ============================================================================

function analyzeHeadPose(faceLandmarks) {
    if (!faceLandmarks || faceLandmarks.length < 468) return 0;

    // Key landmarks: nose (1), left eye (33), right eye (263)
    const nose = faceLandmarks[1] || {};
    const leftEye = faceLandmarks[33] || {};
    const rightEye = faceLandmarks[263] || {};

    // Compute yaw (head turn left/right)
    const eyeMidX = ((leftEye.x || 0) + (rightEye.x || 0)) / 2;
    const noseX = nose.x || 0;
    const yaw = Math.atan2(noseX - eyeMidX, 1) * (180 / Math.PI);

    // Compute pitch (head tilt up/down)
    const eyeMidY = ((leftEye.y || 0) + (rightEye.y || 0)) / 2;
    const noseY = nose.y || 0;
    const pitch = Math.atan2(noseY - eyeMidY, 1) * (180 / Math.PI);

    // Estimate roll from eye positions
    const eyeDeltaY = (rightEye.y || 0) - (leftEye.y || 0);
    const eyeDeltaX = (rightEye.x || 0) - (leftEye.x || 0);
    const roll = Math.atan2(eyeDeltaY, eyeDeltaX) * (180 / Math.PI);

    state.headYaw = yaw;
    state.headPitch = pitch;
    state.headRoll = roll;

    let score = 0;

    // Extreme head turns
    if (Math.abs(yaw) > CONFIG.head.extreme_turn_threshold * 180) {
        addEvent('extreme_head_turn', CONFIG.weights.extreme_turn, { yaw });
        score += CONFIG.weights.extreme_turn;
    } else if (Math.abs(yaw) > CONFIG.head.head_turn_threshold * 180) {
        addEvent('head_turn', CONFIG.weights.head_turn, { yaw });
        score += CONFIG.weights.head_turn;
    }

    // Downward gaze + head pitch down (suspicious combo)
    if (pitch > 10 && state.gazeEMA.y > 0.6) {
        addEvent('downward_sustained', 4.0, { pitch, gazeY: state.gazeEMA.y });
        score += 4.0;
    }

    return score;
}

// ============================================================================
// HAND & FACE DETECTION
// ============================================================================

function analyzeHandBehavior(handLandmarks, faceLandmarks) {
    if (!handLandmarks || !faceLandmarks || handLandmarks.length === 0) return 0;

    let score = 0;

    // Get face bounding box
    const faceBbox = computeBoundingBox(faceLandmarks);

    for (const hand of handLandmarks) {
        if (!hand.landmarks) continue;

        const handBbox = computeBoundingBox(hand.landmarks);

        // Check hand-face overlap
        const overlap = computeIoU(faceBbox, handBbox);
        if (overlap > CONFIG.hand.hand_face_overlap_threshold) {
            addEvent('hand_face_overlap', CONFIG.weights.hand_overlap, { overlap });
            score += CONFIG.weights.hand_overlap;
        }

        // Check hand proximity to face
        const centerDist = Math.hypot(
            handBbox.cx - faceBbox.cx,
            handBbox.cy - faceBbox.cy
        );
        if (centerDist < CONFIG.hand.hand_near_distance_ratio) {
            addEvent('hand_near_face', CONFIG.weights.hand_overlap * 0.7, { distance: centerDist });
            score += CONFIG.weights.hand_overlap * 0.7;
        }
    }

    return score;
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function computeBoundingBox(landmarks) {
    if (!landmarks || landmarks.length === 0) return { x0: 0, y0: 0, x1: 1, y1: 1, cx: 0.5, cy: 0.5 };

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

    for (const lm of landmarks) {
        if (lm.x !== undefined) minX = Math.min(minX, lm.x);
        if (lm.x !== undefined) maxX = Math.max(maxX, lm.x);
        if (lm.y !== undefined) minY = Math.min(minY, lm.y);
        if (lm.y !== undefined) maxY = Math.max(maxY, lm.y);
    }

    return {
        x0: minX,
        y0: minY,
        x1: maxX,
        y1: maxY,
        cx: (minX + maxX) / 2,
        cy: (minY + maxY) / 2,
        width: maxX - minX,
        height: maxY - minY
    };
}

function computeIoU(box1, box2) {
    const ix0 = Math.max(box1.x0, box2.x0);
    const iy0 = Math.max(box1.y0, box2.y0);
    const ix1 = Math.min(box1.x1, box2.x1);
    const iy1 = Math.min(box1.y1, box2.y1);

    const interArea = Math.max(0, ix1 - ix0) * Math.max(0, iy1 - iy0);
    const box1Area = (box1.x1 - box1.x0) * (box1.y1 - box1.y0);
    const box2Area = (box2.x1 - box2.x0) * (box2.y1 - box2.y0);
    const unionArea = box1Area + box2Area - interArea;

    return unionArea > 0 ? interArea / unionArea : 0;
}

// ============================================================================
// EVENT & ALARM MANAGEMENT
// ============================================================================

function addEvent(type, weight, details) {
    const event = {
        type,
        weight,
        details,
        timestamp: Date.now(),
        frame: state.frameCount
    };

    state.recentEvents.push(event);
    if (state.recentEvents.length > 100) state.recentEvents.shift();

    // Update UI
    updateEventsList();
}

function calculateScore() {
    const now = Date.now();
    let score = 0;

    // Time-decay recent events (older events contribute less)
    for (const event of state.recentEvents) {
        const age = (now - event.timestamp) / 1000; // seconds
        const decay = Math.exp(-age / 30); // 30s half-life
        score += event.weight * decay;
    }

    // Cap score at 100
    state.currentScore = Math.min(score, 100);
    return state.currentScore;
}

function scoreToLevel(score) {
    if (score >= CONFIG.alarm.thresholds.critical) return 'CRITICAL';
    if (score >= CONFIG.alarm.thresholds.high) return 'HIGH';
    if (score >= CONFIG.alarm.thresholds.medium) return 'MEDIUM';
    if (score >= CONFIG.alarm.thresholds.low) return 'LOW';
    if (score >= CONFIG.alarm.thresholds.notice) return 'NOTICE';
    return 'NONE';
}

function alarmTick(score, events) {
    const level = scoreToLevel(score);
    const now = Date.now();

    // Check debounce
    const debounceTime = CONFIG.alarm.debounce[level.toLowerCase()] || 0;
    if (now - (state.lastAlarmAt[level] || 0) < debounceTime * 1000) {
        return; // Still in debounce window
    }

    // Check cooldown
    const cooldownTime = CONFIG.alarm.cooldown[level.toLowerCase()] || 0;
    if (now - (state.lastAlarmAt[level] || 0) < cooldownTime * 1000) {
        return; // Still in cooldown
    }

    // Escalate if needed
    if (level !== state.currentLevel) {
        state.currentLevel = level;
        state.lastAlarmAt[level] = now;

        updateAlarmUI();

        if (level === 'CRITICAL') {
            triggerCriticalAlarm();
        } else if (level === 'HIGH') {
            playAlarmSound('high');
        } else if (level === 'MEDIUM') {
            playAlarmSound('medium');
        }

        // TTS announcement
        if (level !== 'NONE' && level !== 'NOTICE') {
            announceTTS(`${level} alarm. Score ${score.toFixed(1)}.`);
        }
    }
}

function updateAlarmUI() {
    const level = state.currentLevel;
    const color = ALARM_COLORS[level];

    elements.alarmLevel.textContent = level;
    elements.alarmLevel.style.color = color;

    elements.scorePill.className = 'score-pill';
    if (level === 'HIGH' || level === 'MEDIUM') {
        elements.scorePill.classList.add('warning');
        elements.alarmPanel.classList.remove('critical');
        elements.alarmPanel.classList.add('warning');
    } else if (level === 'CRITICAL') {
        elements.scorePill.classList.add('critical');
        elements.alarmPanel.classList.add('critical');
    } else {
        elements.alarmPanel.classList.remove('warning', 'critical');
    }

    elements.scorePill.textContent = `SCORE ${state.currentScore.toFixed(1)}`;
    elements.statusText.textContent = `${level}${level === 'NONE' ? ' • MONITORING' : ''}`;
}

// ============================================================================
// UI UPDATES
// ============================================================================

function updateEventsList() {
    const html = state.recentEvents.slice(-10).reverse().map(e => `
        <div class="event-item">
            <span class="event-label">${e.type}</span>
            <span class="event-score">+${e.weight.toFixed(1)}</span>
        </div>
    `).join('');

    elements.eventsList.innerHTML = html || '<div style="color: var(--text-secondary); font-size: 11px;">No events</div>';
}

function updateGauges() {
    elements.gaugeYaw.innerHTML = `YAW<br>${state.headYaw.toFixed(0)}°`;
    elements.gaugePitch.innerHTML = `PITCH<br>${state.headPitch.toFixed(0)}°`;
    elements.gaugeRoll.innerHTML = `ROLL<br>${state.headRoll.toFixed(0)}°`;
}

function updateCharts() {
    // Score chart
    state.scoreHistory.push(state.currentScore);
    if (state.scoreHistory.length > 60) state.scoreHistory.shift();

    const maxScore = Math.max(CONFIG.alarm.thresholds.critical, 80);
    elements.scoreChart.innerHTML = state.scoreHistory.map(s => {
        const height = (s / maxScore) * 100;
        const barClass = s >= CONFIG.alarm.thresholds.critical ? 'critical' : s >= CONFIG.alarm.thresholds.high ? 'high' : '';
        return `<div class="bar ${barClass}" style="height: ${height}%"></div>`;
    }).join('');
}

function updatePerformanceMetrics() {
    const now = Date.now();
    const deltaMs = now - state.lastFrameTime;

    if (deltaMs > 100) { // Update every 100ms
        state.fps = Math.round(1000 / deltaMs);
        elements.fpsDisplay.textContent = `FPS: ${state.fps}`;
        state.lastFrameTime = now;
    }

    // Estimate CPU% (naive)
    const cpuPct = Math.min(100, (state.processingTime / 33) * 100); // Assuming 33ms target
    elements.cpuDisplay.textContent = `CPU: ${cpuPct.toFixed(0)}%`;

    // Uptime
    const uptimeSec = Math.floor((now - state.frameCount / state.fps) / 1000);
    const minutes = Math.floor(uptimeSec / 60);
    const seconds = uptimeSec % 60;
    elements.uptimeDisplay.textContent = `Uptime: ${minutes}:${seconds.toString().padStart(2, '0')}`;
    elements.frameCountDisplay.textContent = `Frames: ${state.frameCount}`;
}

// ============================================================================
// AUDIO & NOTIFICATIONS
// ============================================================================

function playAlarmSound(level) {
    // Create simple beep using Web Audio API
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioContext.createOscillator();
    const gain = audioContext.createGain();

    osc.connect(gain);
    gain.connect(audioContext.destination);

    if (level === 'high') {
        osc.frequency.value = 800;
        gain.gain.setValueAtTime(0.3, audioContext.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
        osc.start(audioContext.currentTime);
        osc.stop(audioContext.currentTime + 0.5);
    } else if (level === 'medium') {
        osc.frequency.value = 600;
        gain.gain.setValueAtTime(0.2, audioContext.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
        osc.start(audioContext.currentTime);
        osc.stop(audioContext.currentTime + 0.3);
    }
}

function announceTTS(message) {
    if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(message);
        utterance.rate = 1.2;
        speechSynthesis.speak(utterance);
    }
}

// ============================================================================
// ALARM ACTIONS
// ============================================================================

function triggerCriticalAlarm() {
    elements.criticalModal.classList.add('active');
    playAlarmSound('critical');
    announceTTS('CRITICAL. Multiple cheating indicators detected.');
    captureEvidence();
}

function acknowledgeAlarm() {
    console.log('Alarm acknowledged');
    state.currentLevel = 'NONE';
    updateAlarmUI();
}

function pauseExam() {
    console.log('Exam paused by operator');
    elements.statusBadge.className = 'status-badge paused';
    elements.statusBadge.textContent = 'Paused';
    announceTTS('Exam paused. Please wait for proctor.');
}

function captureEvidence() {
    const canvas = elements.videoCanvas;
    canvas.toBlob((blob) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const dataUrl = e.target.result;
            state.evidenceFiles.push(dataUrl);

            // Update gallery
            const thumb = document.createElement('div');
            thumb.className = 'evidence-thumb';
            thumb.innerHTML = `<img src="${dataUrl}" alt="Evidence">`;
            elements.evidenceGallery.appendChild(thumb);

            if (elements.evidenceGallery.children.length > 12) {
                elements.evidenceGallery.removeChild(elements.evidenceGallery.children[0]);
            }

            console.log('Evidence captured:', state.evidenceFiles.length, 'files');
        };
        reader.readAsDataURL(blob);
    });
}

function sendMessage() {
    const msg = prompt('Message to student:');
    if (msg) {
        announceTTS(msg);
        console.log('Message sent:', msg);
    }
}

function dismissCritical() {
    elements.criticalModal.classList.remove('active');
}

// ============================================================================
// CONTROL BUTTONS
// ============================================================================

function startMonitoring() {
    console.log('Monitoring started');
}

function stopMonitoring() {
    console.log('Monitoring stopped');
}

function recalibrate() {
    startCalibration();
}

function resetScore() {
    state.currentScore = 0;
    state.recentEvents = [];
    state.currentLevel = 'NONE';
    updateAlarmUI();
    console.log('Score reset');
}

// ============================================================================
// MAIN PROCESSING LOOP
// ============================================================================

let processFrameCount = 0;

async function processingLoop(faceMesh, hands, ctx) {
    const startTime = performance.now();

    state.frameCount++;
    processFrameCount++;

    try {
        // Run face detection
        const faceResults = await faceMesh.send({ image: elements.videoCanvas });

        if (faceResults.multiFaceLandmarks && faceResults.multiFaceLandmarks.length > 0) {
            const faceLandmarks = faceResults.multiFaceLandmarks[0];
            state.faceDetected = true;

            // Extract iris points
            const irisIndices = [468, 469, 470, 471, 472]; // Example indices
            state.irisPoints = irisIndices.map(i => faceLandmarks[i]);

            // Update gaze EMA
            const irisAvgX = state.irisPoints.reduce((s, p) => s + (p?.x || 0), 0) / state.irisPoints.length;
            const irisAvgY = state.irisPoints.reduce((s, p) => s + (p?.y || 0), 0) / state.irisPoints.length;
            updateGazeEMA(irisAvgX, irisAvgY);

            if (state.calibrationMode) {
                addCalibrationSample({ x: irisAvgX, y: irisAvgY });
            }

            // Analyze behavior (every Nth frame to save CPU)
            if (processFrameCount % CONFIG.PROCESS_EVERY_N === 0) {
                let score = 0;

                // Head pose
                score += analyzeHeadPose(faceLandmarks);

                // Gaze deviation
                score += detectGazeDeviation();

                // Calculate total score
                calculateScore();

                // Update alarm
                alarmTick(state.currentScore, state.recentEvents);

                updateGauges();
            }
        } else {
            state.faceDetected = false;
            addEvent('face_missing', 2.0, {});
        }

        // Run hand detection
        const handResults = await hands.send({ image: elements.videoCanvas });
        if (handResults.multiHandLandmarks && handResults.multiHandLandmarks.length > 0) {
            state.handDetected = true;
            if (state.faceDetected && faceResults.multiFaceLandmarks) {
                analyzeHandBehavior(handResults.multiHandLandmarks, faceResults.multiFaceLandmarks[0]);
            }
        } else {
            state.handDetected = false;
        }

        // Draw overlays
        drawOverlays(ctx, faceResults, handResults);

        // Update UI
        if (state.frameCount % 30 === 0) { // Update every 30 frames
            updateCharts();
            updateEventsList();
            updatePerformanceMetrics();
        }

    } catch (error) {
        console.error('Processing error:', error);
    }

    const endTime = performance.now();
    state.processingTime = endTime - startTime;
}

// ============================================================================
// DRAWING & VISUALIZATION
// ============================================================================

function drawOverlays(ctx, faceResults, handResults) {
    const canvas = elements.videoCanvas;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw face bounding box
    if (faceResults.multiFaceLandmarks && faceResults.multiFaceLandmarks.length > 0) {
        const landmarks = faceResults.multiFaceLandmarks[0];
        const bbox = computeBoundingBox(landmarks);

        ctx.strokeStyle = state.currentLevel === 'CRITICAL' ? '#ff4444' : '#7fffd4';
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.5;
        ctx.strokeRect(bbox.x0 * canvas.width, bbox.y0 * canvas.height, bbox.width * canvas.width, bbox.height * canvas.height);
        ctx.globalAlpha = 1;

        // Draw iris centers
        const irisIndices = [468, 469, 470, 471, 472];
        for (const idx of irisIndices) {
            const point = landmarks[idx];
            if (point) {
                ctx.fillStyle = '#7fffd4';
                ctx.beginPath();
                ctx.arc(point.x * canvas.width, point.y * canvas.height, 3, 0, 2 * Math.PI);
                ctx.fill();
            }
        }
    }

    // Draw hands
    if (handResults.multiHandLandmarks && handResults.multiHandLandmarks.length > 0) {
        for (const hand of handResults.multiHandLandmarks) {
            const bbox = computeBoundingBox(hand);
            ctx.strokeStyle = '#ff6644';
            ctx.lineWidth = 1;
            ctx.globalAlpha = 0.3;
            ctx.strokeRect(bbox.x0 * canvas.width, bbox.y0 * canvas.height, bbox.width * canvas.width, bbox.height * canvas.height);
            ctx.globalAlpha = 1;
        }
    }
}

// ============================================================================
// INITIALIZATION TRIGGER
// ============================================================================

document.addEventListener('DOMContentLoaded', initializeSystem);
