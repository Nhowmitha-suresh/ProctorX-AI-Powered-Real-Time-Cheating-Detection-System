"""
Proctor+ Flask Backend API
Handles webhook endpoints for session management, alarm events, evidence upload
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from functools import wraps
import json
import logging
import hashlib
import os
from datetime import datetime, timedelta
from uuid import uuid4
import sqlite3
from pathlib import Path

# ============================================================================
# INITIALIZATION
# ============================================================================

app = Flask(__name__)
CORS(app)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload
UPLOAD_FOLDER = Path('evidence_storage')
DATABASE_PATH = Path('proctor_sessions.db')
LOG_PATH = Path('log/api.log')

# Ensure directories exist
UPLOAD_FOLDER.mkdir(exist_ok=True)
LOG_PATH.parent.mkdir(exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE
# ============================================================================

def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    # Sessions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            student_name TEXT,
            exam_name TEXT,
            user_id TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            reason TEXT,
            final_score REAL,
            final_level TEXT,
            token TEXT UNIQUE,
            status TEXT
        )
    ''')

    # Alarms table
    c.execute('''
        CREATE TABLE IF NOT EXISTS alarms (
            alarm_id TEXT PRIMARY KEY,
            session_id TEXT,
            level TEXT,
            score REAL,
            timestamp TIMESTAMP,
            event_count INTEGER,
            frame_number INTEGER,
            corroboration TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    ''')

    # Evidence table
    c.execute('''
        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY,
            session_id TEXT,
            alarm_id TEXT,
            event_type TEXT,
            severity REAL,
            timestamp TIMESTAMP,
            frame_number INTEGER,
            checksum TEXT,
            file_path TEXT,
            file_size INTEGER,
            uploaded_at TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id),
            FOREIGN KEY (alarm_id) REFERENCES alarms(alarm_id)
        )
    ''')

    # Operator actions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS operator_actions (
            action_id TEXT PRIMARY KEY,
            session_id TEXT,
            action_type TEXT,
            timestamp TIMESTAMP,
            details TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    ''')

    conn.commit()
    conn.close()
    logger.info('Database initialized')

# ============================================================================
# TOKEN MANAGEMENT
# ============================================================================

def generate_session_token(session_id):
    """Generate secure session token"""
    token = hashlib.sha256(f"{session_id}{uuid4()}".encode()).hexdigest()
    return token

def verify_token(session_id, token):
    """Verify session token"""
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('SELECT token FROM sessions WHERE session_id = ?', (session_id,))
    row = c.fetchone()
    conn.close()

    if row and row[0] == token:
        return True
    return False

def token_required(f):
    """Decorator to require valid session token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        session_id = request.headers.get('X-Session-ID')
        token = request.headers.get('Authorization', '').replace('Bearer ', '')

        if not session_id or not token:
            return jsonify({'error': 'Missing authentication'}), 401

        if not verify_token(session_id, token):
            return jsonify({'error': 'Invalid token'}), 403

        return f(*args, **kwargs)
    return decorated

# ============================================================================
# SESSION ENDPOINTS
# ============================================================================

@app.route('/api/v1/sessions/start', methods=['POST'])
def session_start():
    """Start new proctoring session"""
    try:
        data = request.get_json()

        session_id = data.get('session_id')
        student_name = data.get('student_name', 'Unknown')
        exam_name = data.get('exam_name', 'Exam')
        user_id = data.get('user_id')

        # Generate token
        token = generate_session_token(session_id)

        # Store in database
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO sessions 
            (session_id, student_name, exam_name, user_id, start_time, token, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, student_name, exam_name, user_id, datetime.now(), token, 'active'))
        conn.commit()
        conn.close()

        logger.info(f"Session started: {session_id} - {student_name} - {exam_name}")

        return jsonify({
            'success': True,
            'session_id': session_id,
            'token': token,
            'status': 'active'
        }), 200

    except Exception as e:
        logger.error(f"Error starting session: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/v1/sessions/end', methods=['POST'])
@token_required
def session_end():
    """End proctoring session"""
    try:
        data = request.get_json()
        session_id = request.headers.get('X-Session-ID')

        reason = data.get('reason', 'unknown')
        final_score = data.get('final_score', 0)
        final_level = data.get('final_level', 'NONE')
        total_events = data.get('total_events', 0)
        duration = data.get('duration_seconds', 0)
        evidence_count = data.get('evidence_count', 0)

        # Update database
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('''
            UPDATE sessions
            SET end_time = ?, reason = ?, final_score = ?, final_level = ?, status = ?
            WHERE session_id = ?
        ''', (datetime.now(), reason, final_score, final_level, 'completed', session_id))
        conn.commit()
        conn.close()

        logger.info(
            f"Session ended: {session_id} | Score: {final_score:.1f} | Level: {final_level} | "
            f"Duration: {duration}s | Events: {total_events} | Evidence: {evidence_count}"
        )

        return jsonify({
            'success': True,
            'session_id': session_id,
            'session_duration': duration,
            'evidence_processed': evidence_count
        }), 200

    except Exception as e:
        logger.error(f"Error ending session: {e}")
        return jsonify({'error': str(e)}), 400

# ============================================================================
# ALARM ENDPOINTS
# ============================================================================

@app.route('/api/v1/alarms/event', methods=['POST'])
@token_required
def alarm_event():
    """Report alarm event from client"""
    try:
        data = request.get_json()
        session_id = request.headers.get('X-Session-ID')

        alarm_id = f"alm_{uuid4().hex[:12]}"
        level = data.get('level', 'UNKNOWN')
        score = data.get('score', 0)
        frame_number = data.get('frame_number', 0)
        corroboration = data.get('corroboration', {})
        action_required = data.get('action_required', False)

        # Store in database
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO alarms
            (alarm_id, session_id, level, score, timestamp, event_count, frame_number, corroboration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            alarm_id,
            session_id,
            level,
            score,
            datetime.now(),
            corroboration.get('event_count', 0),
            frame_number,
            json.dumps(corroboration)
        ))
        conn.commit()
        conn.close()

        logger.info(
            f"Alarm {level}: {session_id} | Score: {score:.1f} | Frame: {frame_number} | "
            f"Events: {corroboration.get('event_count', 0)}"
        )

        # Generate operator actions if critical
        actions = []
        if level == 'CRITICAL':
            actions.append({
                'type': 'capture',
                'reason': 'Critical alarm - evidence capture'
            })
        elif level == 'HIGH':
            actions.append({
                'type': 'message',
                'message': 'Please ensure camera is visible and you are focused on the exam.'
            })

        return jsonify({
            'success': True,
            'alarm_id': alarm_id,
            'status': 'recorded',
            'actions': actions
        }), 200

    except Exception as e:
        logger.error(f"Error recording alarm: {e}")
        return jsonify({'error': str(e)}), 400

# ============================================================================
# EVIDENCE ENDPOINTS
# ============================================================================

@app.route('/api/v1/evidence/upload', methods=['POST'])
@token_required
def evidence_upload():
    """Upload evidence snapshot"""
    try:
        session_id = request.headers.get('X-Session-ID')
        evidence_id = request.form.get('evidence_id')
        event_type = request.form.get('event_type', 'unknown')
        severity = request.form.get('severity', 0)
        timestamp = request.form.get('timestamp')
        frame_number = request.form.get('frame_number', 0)
        checksum = request.form.get('checksum')

        # Verify checksum if provided
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Read file
        file_data = file.read()

        # Verify checksum
        if checksum:
            computed = hashlib.sha256(file_data).hexdigest()
            if computed != checksum:
                logger.warning(f"Checksum mismatch for {evidence_id}")
                return jsonify({'error': 'Checksum mismatch'}), 400

        # Save file
        file_path = UPLOAD_FOLDER / session_id / event_type
        file_path.mkdir(parents=True, exist_ok=True)
        full_path = file_path / f"{evidence_id}.jpg"

        with open(full_path, 'wb') as f:
            f.write(file_data)

        file_size = len(file_data)

        # Store metadata in database
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO evidence
            (evidence_id, session_id, event_type, severity, timestamp, frame_number, 
             checksum, file_path, file_size, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            evidence_id,
            session_id,
            event_type,
            severity,
            timestamp,
            frame_number,
            checksum,
            str(full_path),
            file_size,
            datetime.now()
        ))
        conn.commit()
        conn.close()

        logger.info(
            f"Evidence uploaded: {evidence_id} | Session: {session_id} | "
            f"Type: {event_type} | Size: {file_size} bytes | Severity: {severity}"
        )

        return jsonify({
            'success': True,
            'evidence_id': evidence_id,
            'file_path': str(full_path),
            'size': file_size,
            'checksum': checksum
        }), 200

    except Exception as e:
        logger.error(f"Error uploading evidence: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/evidence/list/<session_id>', methods=['GET'])
@token_required
def evidence_list(session_id):
    """List all evidence for a session"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('''
            SELECT evidence_id, event_type, severity, timestamp, file_size
            FROM evidence
            WHERE session_id = ?
            ORDER BY timestamp DESC
        ''', (session_id,))

        rows = c.fetchall()
        conn.close()

        evidence = [
            {
                'evidence_id': r[0],
                'event_type': r[1],
                'severity': r[2],
                'timestamp': r[3],
                'file_size': r[4]
            }
            for r in rows
        ]

        logger.info(f"Listed {len(evidence)} evidence files for {session_id}")

        return jsonify({
            'success': True,
            'session_id': session_id,
            'evidence': evidence,
            'count': len(evidence)
        }), 200

    except Exception as e:
        logger.error(f"Error listing evidence: {e}")
        return jsonify({'error': str(e)}), 400

# ============================================================================
# CALIBRATION ENDPOINTS
# ============================================================================

@app.route('/api/v1/calibration/complete', methods=['POST'])
@token_required
def calibration_complete():
    """Report calibration completion"""
    try:
        data = request.get_json()
        session_id = request.headers.get('X-Session-ID')

        calibration_center = data.get('calibration_center')
        sample_count = data.get('sample_count', 0)

        logger.info(
            f"Calibration complete: {session_id} | Center: {calibration_center} | "
            f"Samples: {sample_count}"
        )

        return jsonify({
            'success': True,
            'session_id': session_id,
            'calibration_center': calibration_center
        }), 200

    except Exception as e:
        logger.error(f"Error processing calibration: {e}")
        return jsonify({'error': str(e)}), 400

# ============================================================================
# OPERATOR ACTION ENDPOINTS
# ============================================================================

@app.route('/api/v1/actions/operator', methods=['POST'])
@token_required
def operator_action():
    """Record operator action"""
    try:
        data = request.get_json()
        session_id = request.headers.get('X-Session-ID')

        action_id = f"act_{uuid4().hex[:12]}"
        action_type = data.get('action_type')
        details = data.get('details', {})

        # Store in database
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO operator_actions
            (action_id, session_id, action_type, timestamp, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (action_id, session_id, action_type, datetime.now(), json.dumps(details)))
        conn.commit()
        conn.close()

        logger.info(f"Operator action: {action_type} | Session: {session_id} | Details: {details}")

        return jsonify({
            'success': True,
            'action_id': action_id,
            'action_type': action_type
        }), 200

    except Exception as e:
        logger.error(f"Error recording operator action: {e}")
        return jsonify({'error': str(e)}), 400

# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

@app.route('/api/v1/analytics/session/<session_id>', methods=['GET'])
@token_required
def analytics_session(session_id):
    """Get session analytics"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()

        # Session info
        c.execute('SELECT * FROM sessions WHERE session_id = ?', (session_id,))
        session = c.fetchone()

        # Alarm summary
        c.execute('''
            SELECT level, COUNT(*) as count, AVG(score) as avg_score
            FROM alarms
            WHERE session_id = ?
            GROUP BY level
        ''', (session_id,))
        alarms = c.fetchall()

        # Evidence count
        c.execute('SELECT COUNT(*) FROM evidence WHERE session_id = ?', (session_id,))
        evidence_count = c.fetchone()[0]

        conn.close()

        return jsonify({
            'success': True,
            'session_id': session_id,
            'session': dict(session) if session else None,
            'alarms': [
                {'level': a[0], 'count': a[1], 'avg_score': a[2]}
                for a in alarms
            ],
            'evidence_count': evidence_count
        }), 200

    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        return jsonify({'error': str(e)}), 400

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    }), 200

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large"""
    return jsonify({'error': 'File too large (max 50MB)'}), 413

@app.errorhandler(404)
def not_found(error):
    """Handle 404"""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500"""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# INITIALIZATION
# ============================================================================

if __name__ == '__main__':
    # Initialize database
    init_database()

    # Run server
    logger.info('Starting Proctor+ API server on http://localhost:5000')
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )
