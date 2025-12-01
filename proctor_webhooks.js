/**
 * Proctor+ Webhook Integration Module
 * Handles evidence upload, session management, and operator notifications
 */

// ============================================================================
// WEBHOOK CONFIGURATION
// ============================================================================

const WEBHOOK_CONFIG = {
    // Backend endpoints
    baseUrl: 'http://localhost:5000', // Change to production URL
    endpoints: {
        sessionStart: '/api/v1/sessions/start',
        sessionEnd: '/api/v1/sessions/end',
        alarmEvent: '/api/v1/alarms/event',
        evidenceUpload: '/api/v1/evidence/upload',
        calibration: '/api/v1/calibration/complete',
        operatorAction: '/api/v1/actions/operator'
    },

    // Retry policy
    maxRetries: 3,
    retryDelay: 1000, // ms
    retryBackoff: 2.0, // exponential

    // Timeout
    requestTimeout: 30000, // ms

    // Evidence settings
    evidenceQuality: 0.8, // JPEG quality
    maxEvidenceSize: 5242880, // 5MB
    uploadBatchSize: 5, // evidences per request
    uploadInterval: 5000, // ms between batches
};

// ============================================================================
// WEBHOOK STATE & QUEUE
// ============================================================================

const webhookState = {
    connected: false,
    sessionToken: null,
    uploadQueue: [],
    pendingAcknowledgment: {},
    lastUploadTime: 0,
    statistics: {
        eventsSent: 0,
        evidenceUploaded: 0,
        failedUploads: 0,
        totalLatency: 0
    }
};

// ============================================================================
// SESSION MANAGEMENT
// ============================================================================

/**
 * Initialize session with backend
 */
async function initializeSession(studentName, examName) {
    try {
        const payload = {
            student_name: studentName,
            exam_name: examName,
            session_id: state.sessionId,
            user_id: state.userId,
            start_time: new Date().toISOString(),
            browser_info: {
                userAgent: navigator.userAgent,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                resolution: `${window.innerWidth}x${window.innerHeight}`
            }
        };

        const response = await fetchWithRetry(
            `${WEBHOOK_CONFIG.baseUrl}${WEBHOOK_CONFIG.endpoints.sessionStart}`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Session-ID': state.sessionId
                },
                body: JSON.stringify(payload)
            }
        );

        webhookState.sessionToken = response.token || response.session_token;
        webhookState.connected = true;

        console.log('✅ Session initialized:', webhookState.sessionToken);
        return response;
    } catch (error) {
        console.error('❌ Session initialization failed:', error);
        webhookState.connected = false;
        return null;
    }
}

/**
 * End session and upload final evidence
 */
async function endSession(reason = 'exam_completed') {
    try {
        // Flush remaining evidence first
        await flushEvidenceQueue();

        const payload = {
            session_id: state.sessionId,
            reason: reason,
            end_time: new Date().toISOString(),
            final_score: state.currentScore,
            final_level: state.currentLevel,
            total_events: state.recentEvents.length,
            duration_seconds: Math.floor((Date.now() - state.sessionStartTime) / 1000),
            evidence_count: webhookState.statistics.evidenceUploaded
        };

        const response = await fetchWithRetry(
            `${WEBHOOK_CONFIG.baseUrl}${WEBHOOK_CONFIG.endpoints.sessionEnd}`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Session-ID': state.sessionId,
                    'Authorization': `Bearer ${webhookState.sessionToken}`
                },
                body: JSON.stringify(payload)
            }
        );

        webhookState.connected = false;
        console.log('✅ Session ended:', response);
        return response;
    } catch (error) {
        console.error('❌ Session end failed:', error);
        return null;
    }
}

// ============================================================================
// ALARM EVENT REPORTING
// ============================================================================

/**
 * Report alarm event to backend with corroboration details
 */
async function reportAlarmEvent(level, score, events, timestamp) {
    try {
        // Build corroboration evidence
        const corroboration = {
            event_count: events.length,
            recent_events: events.slice(-5).map(e => ({
                type: e.type,
                weight: e.weight,
                timestamp: e.timestamp,
                details: e.details
            })),
            head_pose: {
                yaw: state.headYaw,
                pitch: state.headPitch,
                roll: state.headRoll
            },
            gaze_position: {
                x: state.gazeEMA.x,
                y: state.gazeEMA.y
            },
            face_detected: state.faceDetected,
            hand_detected: state.handDetected,
            phone_detected: state.phoneDetected
        };

        const payload = {
            session_id: state.sessionId,
            level: level,
            score: score,
            timestamp: timestamp || new Date().toISOString(),
            frame_number: state.frameCount,
            corroboration: corroboration,
            action_required: level === 'CRITICAL' || level === 'HIGH'
        };

        const response = await fetchWithRetry(
            `${WEBHOOK_CONFIG.baseUrl}${WEBHOOK_CONFIG.endpoints.alarmEvent}`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Session-ID': state.sessionId,
                    'Authorization': `Bearer ${webhookState.sessionToken}`
                },
                body: JSON.stringify(payload)
            }
        );

        webhookState.statistics.eventsSent++;

        // Check for operator actions in response
        if (response.actions && Array.isArray(response.actions)) {
            for (const action of response.actions) {
                handleOperatorAction(action);
            }
        }

        return response;
    } catch (error) {
        console.error('❌ Alarm event reporting failed:', error);
        return null;
    }
}

// ============================================================================
// EVIDENCE UPLOAD
// ============================================================================

/**
 * Queue evidence snapshot for upload
 */
function queueEvidence(imageData, eventType, severity) {
    const evidence = {
        id: 'ev_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
        imageData: imageData,
        eventType: eventType,
        severity: severity,
        timestamp: new Date().toISOString(),
        frameNumber: state.frameCount,
        checksum: null,
        uploaded: false,
        retries: 0
    };

    webhookState.uploadQueue.push(evidence);
    console.log(`📸 Evidence queued (${webhookState.uploadQueue.length} pending)`);

    // Trigger upload if queue is full or interval elapsed
    if (webhookState.uploadQueue.length >= WEBHOOK_CONFIG.uploadBatchSize ||
        Date.now() - webhookState.lastUploadTime > WEBHOOK_CONFIG.uploadInterval) {
        flushEvidenceQueue();
    }

    return evidence.id;
}

/**
 * Upload queued evidence in batch
 */
async function flushEvidenceQueue() {
    if (webhookState.uploadQueue.length === 0) return;

    const batch = webhookState.uploadQueue.splice(0, WEBHOOK_CONFIG.uploadBatchSize);
    webhookState.lastUploadTime = Date.now();

    for (const evidence of batch) {
        try {
            // Compute checksum using Web Crypto API
            evidence.checksum = await computeChecksum(evidence.imageData);

            // Create FormData for multipart upload
            const formData = new FormData();
            formData.append('session_id', state.sessionId);
            formData.append('evidence_id', evidence.id);
            formData.append('event_type', evidence.eventType);
            formData.append('severity', evidence.severity);
            formData.append('timestamp', evidence.timestamp);
            formData.append('frame_number', evidence.frameNumber);
            formData.append('checksum', evidence.checksum);

            // Convert data URL to blob
            const blob = await dataURLtoBlob(evidence.imageData);
            formData.append('image', blob, `${evidence.id}.jpg`);

            // Upload
            const startTime = Date.now();
            const response = await fetchWithRetry(
                `${WEBHOOK_CONFIG.baseUrl}${WEBHOOK_CONFIG.endpoints.evidenceUpload}`,
                {
                    method: 'POST',
                    headers: {
                        'X-Session-ID': state.sessionId,
                        'Authorization': `Bearer ${webhookState.sessionToken}`
                    },
                    body: formData
                }
            );

            const latency = Date.now() - startTime;
            evidence.uploaded = true;
            webhookState.statistics.evidenceUploaded++;
            webhookState.statistics.totalLatency += latency;

            console.log(`✅ Evidence uploaded: ${evidence.id} (${latency}ms)`);

            // Update UI
            updateEvidenceStatus(evidence.id, 'uploaded', latency);

        } catch (error) {
            console.error(`❌ Evidence upload failed: ${evidence.id}`, error);
            webhookState.statistics.failedUploads++;

            // Re-queue for retry
            if (evidence.retries < WEBHOOK_CONFIG.maxRetries) {
                evidence.retries++;
                webhookState.uploadQueue.push(evidence);
                console.log(`🔄 Evidence re-queued (retry ${evidence.retries}/${WEBHOOK_CONFIG.maxRetries})`);
            }

            updateEvidenceStatus(evidence.id, 'failed', null);
        }
    }
}

/**
 * Auto-upload evidence periodically
 */
function startEvidenceAutoUpload() {
    setInterval(() => {
        if (webhookState.uploadQueue.length > 0) {
            flushEvidenceQueue();
        }
    }, WEBHOOK_CONFIG.uploadInterval);
}

// ============================================================================
// CALIBRATION REPORTING
// ============================================================================

/**
 * Report calibration completion to backend
 */
async function reportCalibration(calibrationCenter, sampleCount) {
    try {
        const payload = {
            session_id: state.sessionId,
            calibration_center: calibrationCenter,
            sample_count: sampleCount,
            timestamp: new Date().toISOString(),
            screen_resolution: {
                width: window.innerWidth,
                height: window.innerHeight
            }
        };

        const response = await fetchWithRetry(
            `${WEBHOOK_CONFIG.baseUrl}${WEBHOOK_CONFIG.endpoints.calibration}`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Session-ID': state.sessionId,
                    'Authorization': `Bearer ${webhookState.sessionToken}`
                },
                body: JSON.stringify(payload)
            }
        );

        console.log('✅ Calibration reported:', response);
        return response;
    } catch (error) {
        console.error('❌ Calibration reporting failed:', error);
        return null;
    }
}

// ============================================================================
// OPERATOR ACTIONS
// ============================================================================

/**
 * Handle operator actions from backend
 */
function handleOperatorAction(action) {
    console.log('📢 Operator action received:', action.type);

    switch (action.type) {
        case 'acknowledge':
            acknowledgeAlarm();
            break;

        case 'pause':
            pauseExam();
            break;

        case 'resume':
            resumeExam();
            break;

        case 'message':
            if (action.message) {
                announceTTS(action.message);
            }
            break;

        case 'capture':
            captureEvidence();
            break;

        case 'recalibrate':
            startCalibration();
            break;

        case 'end_session':
            if (action.reason) {
                endSession(action.reason);
            }
            break;

        default:
            console.warn('Unknown operator action:', action.type);
    }
}

/**
 * Report operator action to backend
 */
async function reportOperatorAction(actionType, details) {
    try {
        const payload = {
            session_id: state.sessionId,
            action_type: actionType,
            timestamp: new Date().toISOString(),
            details: details || {}
        };

        return await fetchWithRetry(
            `${WEBHOOK_CONFIG.baseUrl}${WEBHOOK_CONFIG.endpoints.operatorAction}`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Session-ID': state.sessionId,
                    'Authorization': `Bearer ${webhookState.sessionToken}`
                },
                body: JSON.stringify(payload)
            }
        );
    } catch (error) {
        console.error('❌ Operator action reporting failed:', error);
        return null;
    }
}

// ============================================================================
// RETRY & HTTP UTILITIES
// ============================================================================

/**
 * Fetch with exponential backoff retry
 */
async function fetchWithRetry(url, options, attempt = 1) {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), WEBHOOK_CONFIG.requestTimeout);

        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    } catch (error) {
        if (attempt < WEBHOOK_CONFIG.maxRetries) {
            const delay = WEBHOOK_CONFIG.retryDelay * Math.pow(WEBHOOK_CONFIG.retryBackoff, attempt - 1);
            console.log(`🔄 Retry attempt ${attempt}/${WEBHOOK_CONFIG.maxRetries} in ${delay}ms...`);
            await new Promise(r => setTimeout(r, delay));
            return fetchWithRetry(url, options, attempt + 1);
        }
        throw error;
    }
}

// ============================================================================
// CRYPTO UTILITIES
// ============================================================================

/**
 * Compute SHA256 checksum of image data
 */
async function computeChecksum(imageData) {
    try {
        // Convert data URL to ArrayBuffer
        const binaryString = atob(imageData.split(',')[1]);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        // Compute SHA256
        const hashBuffer = await crypto.subtle.digest('SHA-256', bytes);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    } catch (error) {
        console.error('Checksum computation failed:', error);
        return 'error';
    }
}

/**
 * Convert data URL to Blob
 */
async function dataURLtoBlob(dataURL) {
    const parts = dataURL.split(',');
    const bstr = atob(parts[1]);
    const bytes = new Uint8Array(bstr.length);
    for (let i = 0; i < bstr.length; i++) {
        bytes[i] = bstr.charCodeAt(i);
    }
    return new Blob([bytes], { type: 'image/jpeg' });
}

// ============================================================================
// UI INTEGRATION
// ============================================================================

/**
 * Update evidence status in gallery
 */
function updateEvidenceStatus(evidenceId, status, latency) {
    const thumbs = document.querySelectorAll('.evidence-thumb');
    for (const thumb of thumbs) {
        if (thumb.dataset.evidenceId === evidenceId) {
            thumb.classList.add(`status-${status}`);
            if (latency) {
                thumb.title = `Uploaded in ${latency}ms`;
            }
        }
    }
}

/**
 * Display webhook statistics
 */
function displayWebhookStats() {
    const stats = webhookState.statistics;
    const avgLatency = stats.evidenceUploaded > 0 ? (stats.totalLatency / stats.evidenceUploaded).toFixed(0) : 0;

    const statsHtml = `
        <div style="font-size: 11px; color: var(--text-secondary);">
            <div>Events: ${stats.eventsSent}</div>
            <div>Evidence: ${stats.evidenceUploaded}↑ ${stats.failedUploads}✗</div>
            <div>Latency: ${avgLatency}ms avg</div>
        </div>
    `;

    // Update a stats display element if it exists
    const statsElement = document.getElementById('webhookStats');
    if (statsElement) {
        statsElement.innerHTML = statsHtml;
    }
}

// ============================================================================
// INTEGRATION WITH CORE LOGIC
// ============================================================================

/**
 * Hook into alarm escalation
 */
function integrateAlarmWebhooks() {
    // Override alarm tick to report events
    const originalAlarmTick = window.alarmTick;
    window.alarmTick = function(score, events) {
        // Call original function
        originalAlarmTick.call(this, score, events);

        // Report to webhook
        if (webhookState.connected) {
            reportAlarmEvent(state.currentLevel, score, events);
        }
    };

    // Override evidence capture
    const originalCaptureEvidence = window.captureEvidence;
    window.captureEvidence = async function() {
        originalCaptureEvidence.call(this);

        // Queue for upload
        const canvas = elements.videoCanvas;
        canvas.toBlob((blob) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                queueEvidence(e.target.result, state.currentLevel, state.currentScore);
            };
            reader.readAsDataURL(blob);
        }, 'image/jpeg', WEBHOOK_CONFIG.evidenceQuality);
    };
}

/**
 * Initialize webhook subsystem
 */
async function initializeWebhooks(studentName, examName) {
    console.log('🌐 Initializing webhook system...');

    try {
        // Initialize session
        await initializeSession(studentName, examName);

        // Start auto-upload
        startEvidenceAutoUpload();

        // Integrate with core logic
        integrateAlarmWebhooks();

        // Display stats
        setInterval(displayWebhookStats, 5000);

        console.log('✅ Webhook system ready');
        return true;
    } catch (error) {
        console.error('❌ Webhook initialization failed:', error);
        console.log('⚠️  Running in offline mode - evidence saved locally only');
        return false;
    }
}

// ============================================================================
// EXPORT
// ============================================================================

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeWebhooks,
        reportAlarmEvent,
        queueEvidence,
        flushEvidenceQueue,
        endSession,
        handleOperatorAction,
        reportOperatorAction,
        WEBHOOK_CONFIG,
        webhookState
    };
}
