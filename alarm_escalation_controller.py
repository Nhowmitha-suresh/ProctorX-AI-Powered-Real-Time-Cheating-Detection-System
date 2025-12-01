"""
Alarm & Escalation Controller for Real-Time Exam Proctoring System

Manages:
- Alarm level transitions (NOTICE → LOW → MEDIUM → HIGH → CRITICAL)
- Debounce, cooldown, and corroboration rules
- Evidence capture and audit trail
- Operator overrides and workflows
- Multi-channel notifications (webhook, email, SMS)
- Privacy safeguards and false-positive mitigation
"""

import time
import json
import hashlib
import os
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
from collections import deque
from datetime import datetime, timedelta
import threading
import requests


def ev_get(event, key, default=None):
    """
    Universal accessor for event data that works with both dicts and objects.
    
    Handles both:
    - Dictionary events: event.get(key, default)
    - Object events (CheatEvent): getattr(event, key, default)
    
    Args:
        event: Event as dict or object
        key: Field/attribute name
        default: Default value if not found
        
    Returns:
        Value of field/attribute, or default if not found
    """
    if isinstance(event, dict):
        return event.get(key, default)
    return getattr(event, key, default)


class AlarmLevel(Enum):
    """Alarm severity levels"""
    NONE = 0
    NOTICE = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5
    
    def __lt__(self, other):
        """Less than comparison"""
        if isinstance(other, AlarmLevel):
            return self.value < other.value
        return self.value < other
    
    def __le__(self, other):
        """Less than or equal comparison"""
        if isinstance(other, AlarmLevel):
            return self.value <= other.value
        return self.value <= other
    
    def __gt__(self, other):
        """Greater than comparison"""
        if isinstance(other, AlarmLevel):
            return self.value > other.value
        return self.value > other
    
    def __ge__(self, other):
        """Greater than or equal comparison"""
        if isinstance(other, AlarmLevel):
            return self.value >= other.value
        return self.value >= other


class OperatorAction(Enum):
    """Operator override actions"""
    ACKNOWLEDGE = "acknowledge"
    MARK_FALSE_POSITIVE = "false_positive"
    LOCK_EXAM = "lock_exam"
    UNLOCK_EXAM = "unlock_exam"
    REQUEST_LIVE_VIEW = "live_view"
    REQUEST_STUDENT_RESPONSE = "student_response"


@dataclass
class AlarmConfig:
    """Configurable alarm parameters"""
    # Score thresholds
    thresholds: Dict[str, float] = field(default_factory=lambda: {
        "notice": 6.0,
        "low": 15.0,
        "medium": 25.0,
        "high": 40.0,
        "critical": 60.0,
    })
    
    # Debounce windows (seconds)
    debounce: Dict[str, float] = field(default_factory=lambda: {
        "notice": 0.4,
        "low": 0.6,
        "medium": 1.2,
        "high": 0.8,
    })
    
    # Cooldown periods (seconds)
    cooldown: Dict[str, float] = field(default_factory=lambda: {
        "low": 4.0,
        "medium": 6.0,
        "high": 12.0,
        "critical": 30.0,
    })
    
    # Phone detection persistence
    phone_persist_frames: int = 5
    phone_persist_time_s: float = 1.0
    
    # Face missing thresholds
    face_missing_warn_s: float = 0.6
    face_missing_high_s: float = 2.0
    
    # Evidence retention
    retain_evidence_days: int = 90
    
    # Notification channels
    notify_webhook_on: List[str] = field(default_factory=lambda: ["medium", "high", "critical"])
    notify_email_on: List[str] = field(default_factory=lambda: ["high", "critical"])
    notify_sms_on: List[str] = field(default_factory=lambda: ["critical"])
    
    # Exam policy
    auto_pause_on_critical: bool = True
    require_multi_modal_corroboration: bool = True
    
    # Test/production modes
    test_mode: bool = False
    verbose_logging: bool = False


@dataclass
class AlarmEvent:
    """Alarm event with metadata"""
    timestamp: float
    frame_index: int
    level: AlarmLevel
    score: float
    events: List[Dict]
    session_id: str
    user_id: str
    exam_id: str
    device_metadata: Dict = field(default_factory=dict)
    evidence_files: List[str] = field(default_factory=list)
    corroborated: bool = False
    incident_id: str = ""


@dataclass
class OperatorOverride:
    """Operator intervention record"""
    timestamp: float
    operator_id: str
    action: OperatorAction
    reason: str
    session_id: str
    incident_id: Optional[str] = None
    is_false_positive: bool = False


class EvidenceManager:
    """Manages evidence capture, storage, and checksums"""
    
    def __init__(self, base_path: str = "log/evidence"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
        self.manifest = []
    
    def capture_frame(
        self,
        frame,
        session_id: str,
        timestamp: float,
        event_type: str,
        score: float,
        frame_index: int
    ) -> Tuple[str, str]:
        """
        Capture and save frame with checksum
        
        Returns:
            (filepath, sha256_hash)
        """
        import cv2
        
        ts_str = datetime.fromtimestamp(timestamp).strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"{session_id}_{ts_str}_{event_type}_{score:.1f}_{frame_index}.png"
        filepath = os.path.join(self.base_path, filename)
        
        cv2.imwrite(filepath, frame)
        checksum = self._compute_sha256(filepath)
        
        self.manifest.append({
            'type': 'frame',
            'filepath': filepath,
            'session_id': session_id,
            'timestamp': timestamp,
            'event_type': event_type,
            'sha256': checksum,
            'frame_index': frame_index,
        })
        
        return filepath, checksum
    
    def _compute_sha256(self, filepath: str) -> str:
        """Compute SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def export_manifest(self, session_id: str) -> str:
        """Export evidence manifest for audit"""
        session_evidence = [e for e in self.manifest if e['session_id'] == session_id]
        manifest_file = os.path.join(self.base_path, f"{session_id}_manifest.json")
        
        with open(manifest_file, 'w') as f:
            json.dump(session_evidence, f, indent=2)
        
        return manifest_file
    
    def cleanup_old_evidence(self, retention_days: int):
        """Delete evidence older than retention period"""
        cutoff_time = time.time() - (retention_days * 86400)
        
        for evidence in self.manifest[:]:
            if evidence['timestamp'] < cutoff_time:
                try:
                    os.remove(evidence['filepath'])
                    self.manifest.remove(evidence)
                except Exception as e:
                    print(f"Failed to delete old evidence: {e}")


class NotificationManager:
    """Manages multi-channel notifications"""
    
    def __init__(self, config: AlarmConfig):
        self.config = config
        self.webhook_url = os.getenv("PROCTOR_WEBHOOK_URL", "")
        self.email_config = {
            'smtp_server': os.getenv("SMTP_SERVER", ""),
            'smtp_port': int(os.getenv("SMTP_PORT", "587")),
            'sender_email': os.getenv("SENDER_EMAIL", ""),
            'sender_password': os.getenv("SENDER_PASSWORD", ""),
        }
        self.sms_config = {
            'api_key': os.getenv("SMS_API_KEY", ""),
            'api_url': os.getenv("SMS_API_URL", ""),
        }
    
    def send_webhook(self, alarm_event: AlarmEvent, evidence_urls: List[str]):
        """Send webhook notification to monitoring dashboard"""
        if not self.webhook_url:
            return
        
        payload = {
            'timestamp': datetime.fromtimestamp(alarm_event.timestamp).isoformat(),
            'session_id': alarm_event.session_id,
            'user_id': alarm_event.user_id,
            'exam_id': alarm_event.exam_id,
            'level': alarm_event.level.name,
            'score': alarm_event.score,
            'incident_id': alarm_event.incident_id,
            'event_summary': [
                {
                    'type': ev_get(e, 'event_type', 'unknown'),
                    'severity': ev_get(e, 'severity', 0),
                    'description': ev_get(e, 'description', ''),
                }
                for e in alarm_event.events[:5]  # Top 5 events
            ],
            'evidence_urls': evidence_urls,
            'corroborated': alarm_event.corroborated,
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5,
                headers={'Content-Type': 'application/json'}
            )
            if self.config.verbose_logging:
                print(f"Webhook sent: {response.status_code}")
        except Exception as e:
            print(f"Webhook error: {e}")
    
    def send_email(
        self,
        recipient_email: str,
        level: AlarmLevel,
        alarm_event: AlarmEvent
    ):
        """Send email notification"""
        subject_map = {
            AlarmLevel.HIGH: "⚠️  High Suspicion - Exam Proctoring Alert",
            AlarmLevel.CRITICAL: "🚨 CRITICAL - Exam Halted - Immediate Action Required",
        }
        
        body_map = {
            AlarmLevel.HIGH: f"""
Exam Proctoring Alert

Session ID: {alarm_event.session_id}
User ID: {alarm_event.user_id}
Score: {alarm_event.score:.1f}

High suspicion indicators detected. Please review immediately.
Incident ID: {alarm_event.incident_id}
""",
            AlarmLevel.CRITICAL: f"""
CRITICAL ALERT - EXAM HALTED

Session ID: {alarm_event.session_id}
User ID: {alarm_event.user_id}
Score: {alarm_event.score:.1f}

CRITICAL cheating indicators detected.
Exam has been automatically halted.
Manual intervention required.

Incident ID: {alarm_event.incident_id}
Timestamp: {datetime.fromtimestamp(alarm_event.timestamp).isoformat()}
""",
        }
        
        subject = subject_map.get(level, "Exam Proctoring Alert")
        body = body_map.get(level, "Alert generated by proctoring system")
        
        # TODO: Implement actual email sending
        if self.config.verbose_logging:
            print(f"[EMAIL] To: {recipient_email}\nSubject: {subject}\n{body}")
    
    def send_sms(self, phone_number: str, level: AlarmLevel, session_id: str):
        """Send SMS notification for critical alerts"""
        message_map = {
            AlarmLevel.CRITICAL: f"CRITICAL: Exam {session_id} halted. Cheating detected. Proctor intervention needed.",
        }
        
        message = message_map.get(level, "Exam alert")
        
        # TODO: Implement actual SMS sending
        if self.config.verbose_logging:
            print(f"[SMS] To: {phone_number}\nMessage: {message}")


class CorroborationEngine:
    """Validates events through multi-modal corroboration"""
    
    def __init__(self, config: AlarmConfig):
        self.config = config
        self.event_history: deque = deque(maxlen=300)  # 10 seconds @ 30fps
    
    def add_event(self, event: Dict):
        """Track event"""
        self.event_history.append({
            'timestamp': time.time(),
            'type': ev_get(event, 'event_type'),
            'severity': ev_get(event, 'severity', 1),
            'metadata': ev_get(event, 'metadata', {}),
        })
    
    def require_corroboration(
        self,
        level: AlarmLevel,
        current_events: List[Dict],
        current_score: float
    ) -> bool:
        """
        Check if current alert requires corroboration and if it's met
        
        Returns:
            True if corroboration requirement is satisfied (or not required)
        """
        if level in [AlarmLevel.NOTICE, AlarmLevel.LOW]:
            # Lower levels don't require corroboration
            return True
        
        if not self.config.require_multi_modal_corroboration:
            return True
        
        current_time = time.time()
        
        # Check for multi-modal corroboration within last 3 seconds
        recent_events = [
            e for e in self.event_history
            if current_time - e['timestamp'] < 3.0
        ]
        
        # Count unique modalities
        modalities = set()
        
        # Check for phone/object detection persistence
        phone_events = []
        for e in recent_events:
            event_type = ev_get(e, 'type', '')
            if event_type:
                event_type_str = str(event_type).lower()
                if 'phone' in event_type_str or 'object' in event_type_str:
                    phone_events.append(e)
        if len(phone_events) >= self.config.phone_persist_frames:
            modalities.add('object')
        
        # Check for hand-to-face
        hand_events = []
        for e in recent_events:
            event_type = ev_get(e, 'type', '')
            if event_type:
                event_type_str = str(event_type).lower()
                if 'hand' in event_type_str:
                    hand_events.append(e)
        if len(hand_events) >= 3:
            modalities.add('hand')
        
        # Check for audio/speech
        audio_events = []
        for e in recent_events:
            event_type = ev_get(e, 'type', '')
            if event_type:
                event_type_str = str(event_type).lower()
                if 'audio' in event_type_str or 'whisper' in event_type_str or 'voice' in event_type_str:
                    audio_events.append(e)
        if audio_events:
            modalities.add('audio')
        
        # Check for head/eye movement patterns
        movement_events = []
        for e in recent_events:
            event_type = ev_get(e, 'type', '')
            if event_type:
                event_type_str = str(event_type).lower()
                if any(x in event_type_str for x in ['head', 'eye', 'gaze']):
                    movement_events.append(e)
        if len(movement_events) >= 3:
            modalities.add('movement')
        
        # For MEDIUM/HIGH, require at least 1 corroborating modality
        # For CRITICAL, require at least 2 modalities or sustained high score
        if level == AlarmLevel.MEDIUM or level == AlarmLevel.HIGH:
            return len(modalities) >= 1 or current_score > level.value * 20
        elif level == AlarmLevel.CRITICAL:
            return len(modalities) >= 2 or current_score > 70
        
        return True
    
    def check_suspicious_sequence(self) -> Optional[AlarmLevel]:
        """
        Check for composite suspicious sequences
        (head-turn + phone + whispering within 4s) → CRITICAL
        """
        current_time = time.time()
        recent = [
            e for e in self.event_history
            if current_time - e['timestamp'] < 4.0
        ]
        
        # Safely convert event types to lowercase strings
        event_types = []
        for e in recent:
            event_type = e['type']
            if event_type is None:
                continue
            # Convert to string if it's not already, then lowercase
            event_type_str = str(event_type).lower()
            event_types.append(event_type_str)
        
        # Suspicious sequence: head turn + phone + audio
        has_head = any('head' in t for t in event_types)
        has_phone = any('phone' in t for t in event_types)
        has_audio = any(x in str(event_types) for x in ['audio', 'whisper', 'voice'])
        
        if has_head and has_phone and has_audio:
            return AlarmLevel.CRITICAL
        
        # Suspicious sequence: extreme head turn + phone
        extreme_head = any('extreme' in t for t in event_types)
        if extreme_head and has_phone:
            return AlarmLevel.CRITICAL
        
        return None


class AlarmAndEscalationController:
    """Main alarm and escalation control system"""
    
    def __init__(
        self,
        config: AlarmConfig,
        session_id: str,
        user_id: str,
        exam_id: str,
        device_metadata: Dict = None,
    ):
        self.config = config
        self.session_id = session_id
        self.user_id = user_id
        self.exam_id = exam_id
        self.device_metadata = device_metadata or {}
        
        # State tracking
        self.current_level = AlarmLevel.NONE
        self.last_level_change = time.time()
        self.last_alarm_emit_time: Dict[AlarmLevel, float] = {
            level: 0 for level in AlarmLevel
        }
        
        # Debounce tracking
        self.level_transition_time: Dict[AlarmLevel, float] = {
            level: 0 for level in AlarmLevel
        }
        
        # Evidence and history
        self.evidence_manager = EvidenceManager()
        self.notification_manager = NotificationManager(config)
        self.corroboration_engine = CorroborationEngine(config)
        
        self.alarm_history: List[AlarmEvent] = []
        self.operator_overrides: List[OperatorOverride] = []
        
        # Callbacks for external integrations
        self.on_alarm_callback: Optional[Callable] = None
        self.on_exam_pause_callback: Optional[Callable] = None
        
        # Face missing tracking
        self.face_missing_start: Optional[float] = None
        self.face_missing_warned = False
        
        # Operator acknowledgment
        self.acknowledged_until: float = 0
        
        # Generate incident ID
        self.incident_id_counter = 0
    
    def process_frame(
        self,
        frame,
        cheating_score: float,
        events: List[Dict],
        face_detected: bool,
        frame_index: int,
    ) -> Optional[AlarmEvent]:
        """
        Main tick function - process frame and decide on alarms
        
        Args:
            frame: Video frame
            cheating_score: Computed cheating score (0-100)
            events: List of detected events
            face_detected: Whether face is detected
            frame_index: Frame counter
            
        Returns:
            AlarmEvent if alarm was emitted, None otherwise
        """
        current_time = time.time()
        
        # Add events to corroboration engine
        for event in events:
            self.corroboration_engine.add_event(event)
        
        # Handle face missing
        self._update_face_missing_state(face_detected, frame_index, frame)
        
        # Map score to alarm level
        new_level = self._score_to_level(cheating_score)
        
        # Check if we're in operator acknowledgment window
        if current_time < self.acknowledged_until:
            return None
        
        # Check cooldown for current level
        if new_level in self.config.cooldown:
            cooldown_duration = self.config.cooldown[new_level.name.lower()]
            if current_time - self.last_alarm_emit_time[new_level] < cooldown_duration:
                # In cooldown, don't emit alarm
                return None
        
        # Level transition logic
        if new_level > self.current_level:
            # Escalating
            return self._handle_level_escalation(
                new_level, cheating_score, events, face_detected, frame, frame_index, current_time
            )
        elif new_level < self.current_level:
            # De-escalating
            self.current_level = new_level
        
        return None
    
    def _handle_level_escalation(
        self,
        new_level: AlarmLevel,
        cheating_score: float,
        events: List[Dict],
        face_detected: bool,
        frame,
        frame_index: int,
        current_time: float,
    ) -> Optional[AlarmEvent]:
        """Handle upward level transition with debounce and corroboration"""
        
        # Check if we're still in debounce window from previous attempt
        debounce_key = new_level.name.lower()
        if debounce_key in self.config.debounce:
            debounce_duration = self.config.debounce[debounce_key]
            if current_time - self.level_transition_time[new_level] < debounce_duration:
                # Still in debounce window, don't escalate yet
                return None
        
        # Check corroboration
        if not self.corroboration_engine.require_corroboration(new_level, events, cheating_score):
            # Record that we attempted this level
            self.level_transition_time[new_level] = current_time
            return None
        
        # Check for composite suspicious sequences
        sequence_level = self.corroboration_engine.check_suspicious_sequence()
        if sequence_level and sequence_level > new_level:
            new_level = sequence_level
        
        # All checks passed, emit alarm
        return self._emit_alarm(
            new_level, cheating_score, events, face_detected, frame, frame_index, current_time
        )
    
    def _emit_alarm(
        self,
        level: AlarmLevel,
        cheating_score: float,
        events: List[Dict],
        face_detected: bool,
        frame,
        frame_index: int,
        current_time: float,
    ) -> AlarmEvent:
        """Emit alarm and trigger actions"""
        
        self.current_level = level
        self.last_level_change = current_time
        self.last_alarm_emit_time[level] = current_time
        
        # Generate incident ID
        self.incident_id_counter += 1
        incident_id = f"{self.session_id}_{self.incident_id_counter}"
        
        # Capture evidence based on level
        evidence_files = self._capture_evidence(
            frame, level, cheating_score, incident_id, frame_index, current_time
        )
        
        # Create alarm event
        alarm_event = AlarmEvent(
            timestamp=current_time,
            frame_index=frame_index,
            level=level,
            score=cheating_score,
            events=events,
            session_id=self.session_id,
            user_id=self.user_id,
            exam_id=self.exam_id,
            device_metadata=self.device_metadata,
            evidence_files=evidence_files,
            corroborated=self.corroboration_engine.require_corroboration(level, events, cheating_score),
            incident_id=incident_id,
        )
        
        self.alarm_history.append(alarm_event)
        
        # Send notifications
        self._send_notifications(alarm_event, level)
        
        # Take exam action
        if level == AlarmLevel.CRITICAL and self.config.auto_pause_on_critical:
            self._pause_exam(incident_id)
        
        # Call external callback
        if self.on_alarm_callback:
            self.on_alarm_callback(alarm_event)
        
        if not self.config.test_mode:
            self._log_alarm(alarm_event)
        
        return alarm_event
    
    def _update_face_missing_state(self, face_detected: bool, frame_index: int, frame):
        """Track face missing duration and escalate if needed"""
        current_time = time.time()
        
        if not face_detected:
            if self.face_missing_start is None:
                self.face_missing_start = current_time
            
            duration = current_time - self.face_missing_start
            
            # HIGH threshold: 2 seconds
            if duration > self.config.face_missing_high_s and not self.face_missing_warned:
                self.face_missing_warned = True
                # This will be caught by next process_frame call with low score
            
            # LOW threshold: 0.6 seconds
            elif duration > self.config.face_missing_warn_s and not self.face_missing_warned:
                self.face_missing_warned = True
        else:
            # Face is detected
            if self.face_missing_start is not None:
                duration = current_time - self.face_missing_start
                if duration > self.config.face_missing_high_s:
                    # Create face missing event
                    if self.on_alarm_callback:
                        print(f"Face was missing for {duration:.1f}s")
            
            # Reset
            self.face_missing_start = None
            self.face_missing_warned = False
    
    def _score_to_level(self, score: float) -> AlarmLevel:
        """Map score to alarm level"""
        if score >= self.config.thresholds['critical']:
            return AlarmLevel.CRITICAL
        elif score >= self.config.thresholds['high']:
            return AlarmLevel.HIGH
        elif score >= self.config.thresholds['medium']:
            return AlarmLevel.MEDIUM
        elif score >= self.config.thresholds['low']:
            return AlarmLevel.LOW
        elif score >= self.config.thresholds['notice']:
            return AlarmLevel.NOTICE
        else:
            return AlarmLevel.NONE
    
    def _capture_evidence(
        self,
        frame,
        level: AlarmLevel,
        cheating_score: float,
        incident_id: str,
        frame_index: int,
        timestamp: float,
    ) -> List[str]:
        """Capture evidence based on alarm level"""
        evidence_files = []
        
        if level == AlarmLevel.NOTICE:
            # Minimal evidence
            pass
        
        elif level == AlarmLevel.LOW:
            # Single snapshot
            if frame is not None:
                filepath, checksum = self.evidence_manager.capture_frame(
                    frame, self.session_id, timestamp, "low_alert", cheating_score, frame_index
                )
                evidence_files.append(filepath)
        
        elif level == AlarmLevel.MEDIUM:
            # Snapshot + timeline entry
            if frame is not None:
                filepath, checksum = self.evidence_manager.capture_frame(
                    frame, self.session_id, timestamp, "medium_alert", cheating_score, frame_index
                )
                evidence_files.append(filepath)
        
        elif level == AlarmLevel.HIGH:
            # High-resolution snapshots (2)
            if frame is not None:
                filepath1, _ = self.evidence_manager.capture_frame(
                    frame, self.session_id, timestamp, "high_alert_1", cheating_score, frame_index
                )
                filepath2, _ = self.evidence_manager.capture_frame(
                    frame, self.session_id, timestamp, "high_alert_2", cheating_score, frame_index
                )
                evidence_files.extend([filepath1, filepath2])
        
        elif level == AlarmLevel.CRITICAL:
            # Maximum evidence capture
            if frame is not None:
                # Multiple snapshots
                for i in range(3):
                    filepath, _ = self.evidence_manager.capture_frame(
                        frame, self.session_id, timestamp, f"critical_alert_{i}", cheating_score, frame_index
                    )
                    evidence_files.append(filepath)
        
        return evidence_files
    
    def _send_notifications(self, alarm_event: AlarmEvent, level: AlarmLevel):
        """Send notifications based on level"""
        level_name = level.name.lower()
        
        # Webhook
        if level_name in self.config.notify_webhook_on:
            self.notification_manager.send_webhook(alarm_event, alarm_event.evidence_files)
        
        # Email
        if level_name in self.config.notify_email_on:
            proctor_email = os.getenv("PROCTOR_EMAIL", "")
            if proctor_email:
                self.notification_manager.send_email(proctor_email, level, alarm_event)
        
        # SMS
        if level_name in self.config.notify_sms_on:
            proctor_phone = os.getenv("PROCTOR_PHONE", "")
            if proctor_phone:
                self.notification_manager.send_sms(proctor_phone, level, self.session_id)
    
    def _pause_exam(self, incident_id: str):
        """Pause/lock exam"""
        if self.on_exam_pause_callback:
            self.on_exam_pause_callback(incident_id)
        
        if self.config.verbose_logging:
            print(f"[EXAM PAUSED] Incident: {incident_id}")
    
    def _log_alarm(self, alarm_event: AlarmEvent):
        """Log alarm to persistent storage"""
        log_entry = {
            'timestamp': datetime.fromtimestamp(alarm_event.timestamp).isoformat(),
            'level': alarm_event.level.name,
            'score': alarm_event.score,
            'incident_id': alarm_event.incident_id,
            'session_id': alarm_event.session_id,
            'user_id': alarm_event.user_id,
            'evidence_files': alarm_event.evidence_files,
        }
        
        log_file = os.path.join(self.evidence_manager.base_path, f"{self.session_id}_alarms.jsonl")
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def operator_action(self, operator_id: str, action: OperatorAction, reason: str = ""):
        """Handle operator override"""
        override = OperatorOverride(
            timestamp=time.time(),
            operator_id=operator_id,
            action=action,
            reason=reason,
            session_id=self.session_id,
            incident_id=self.alarm_history[-1].incident_id if self.alarm_history else None,
        )
        
        self.operator_overrides.append(override)
        
        if action == OperatorAction.ACKNOWLEDGE:
            # Suppress alarms for 5 minutes
            self.acknowledged_until = time.time() + 300
        
        elif action == OperatorAction.MARK_FALSE_POSITIVE:
            # Mark last incident as false positive
            if self.alarm_history:
                # Annotate in logs
                pass
        
        if self.config.verbose_logging:
            print(f"[OPERATOR] {action.value}: {reason}")
    
    def get_session_report(self) -> Dict:
        """Generate session report"""
        # Convert alarm events into JSON-serializable dictionaries
        # Helper to normalize nested structures and convert Enum values to strings
        def _normalize(obj):
            if isinstance(obj, Enum):
                return obj.name
            if isinstance(obj, dict):
                return {k: _normalize(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_normalize(v) for v in obj]
            return obj

        alarm_timeline = []
        for a in self.alarm_history:
            d = asdict(a)
            d = _normalize(d)
            # Ensure level is a string (AlarmLevel)
            d['level'] = a.level.name if isinstance(a.level, AlarmLevel) else str(a.level)
            # Timestamp -> ISO format
            try:
                d['timestamp'] = datetime.fromtimestamp(a.timestamp).isoformat()
            except Exception:
                d['timestamp'] = str(a.timestamp)
            alarm_timeline.append(d)

        operator_actions_log = []
        for o in self.operator_overrides:
            od = asdict(o)
            od = _normalize(od)
            # OperatorAction enum -> name or value
            od['action'] = o.action.value if hasattr(o.action, 'value') else str(o.action)
            try:
                od['timestamp'] = datetime.fromtimestamp(o.timestamp).isoformat()
            except Exception:
                od['timestamp'] = str(o.timestamp)
            operator_actions_log.append(od)

        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'exam_id': self.exam_id,
            'total_alarms': len(self.alarm_history),
            'critical_alarms': sum(1 for a in self.alarm_history if a.level == AlarmLevel.CRITICAL),
            'high_alarms': sum(1 for a in self.alarm_history if a.level == AlarmLevel.HIGH),
            'medium_alarms': sum(1 for a in self.alarm_history if a.level == AlarmLevel.MEDIUM),
            'operator_actions': len(self.operator_overrides),
            'evidence_files': len(self.evidence_manager.manifest),
            'alarm_timeline': alarm_timeline,
            'operator_actions_log': operator_actions_log,
        }
    
    def export_session_evidence(self) -> str:
        """Export full session evidence package"""
        manifest_file = self.evidence_manager.export_manifest(self.session_id)
        report_file = os.path.join(
            self.evidence_manager.base_path,
            f"{self.session_id}_report.json"
        )
        
        with open(report_file, 'w') as f:
            json.dump(self.get_session_report(), f, indent=2)
        
        return report_file
    
    def cleanup_old_evidence(self):
        """Clean up evidence older than retention period"""
        self.evidence_manager.cleanup_old_evidence(self.config.retain_evidence_days)
