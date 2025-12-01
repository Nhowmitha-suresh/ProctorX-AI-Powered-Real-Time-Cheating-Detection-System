"""
Advanced AI Cheating Detection and Proctoring Engine

This module analyzes multiple modalities including:
- Facial expressions and eye behavior
- Head movements and orientation
- Hand gestures and proximity to face
- Gadget/device detection
- Audio analysis
- Environmental factors
- Behavioral patterns

Author: AI Proctoring System
Date: 2025
"""

import cv2
import numpy as np
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum


class SuspicionLevel(Enum):
    """Severity levels for cheating suspicion"""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class EventType(Enum):
    """Types of cheating events"""
    EYE_GAZE_DEVIATION = "Eye Gaze Deviation"
    DOWNWARD_GAZE = "Downward Gaze"
    RAPID_SACCADE = "Rapid Saccade"
    HEAD_TURN = "Head Turn"
    EXTREME_HEAD_TURN = "Extreme Head Turn"
    FACE_MISSING = "Face Missing"
    HAND_NEAR_FACE = "Hand Near Face"
    HAND_COVERING_FACE = "Hand Covering Face"
    PHONE_DETECTED = "Phone Detected"
    EARPHONE_DETECTED = "Earphone Detected"
    NOTES_DETECTED = "Notes/Paper Detected"
    WHISPERING = "Whispering"
    EXTERNAL_VOICE = "External Voice"
    LIP_MOVEMENT_NO_AUDIO = "Lip Movement Without Audio"
    BACKGROUND_CHANGE = "Background Change"
    CAMERA_OBSTRUCTION = "Camera Obstruction"
    SUSPICIOUS_PATTERN = "Suspicious Pattern"


@dataclass
class CheatEvent:
    """Represents a single cheating event"""
    event_type: EventType
    timestamp: float
    severity: int  # 1-10
    description: str
    confidence: float  # 0-1
    frame_number: int = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class CheatingAnalysis:
    """Final analysis output"""
    cheating_score: float  # 0-100
    suspicion_level: SuspicionLevel
    events: List[CheatEvent]
    reasoning: str
    recommended_action: str
    timestamp: float = field(default_factory=time.time)


class CheatingDetectionEngine:
    """
    Main cheating detection engine that analyzes multiple modalities
    """
    
    def __init__(self, window_size: int = 300):
        """
        Initialize the cheating detection engine
        
        Args:
            window_size: Size of temporal window for pattern detection (frames)
        """
        self.window_size = window_size
        self.event_history: deque = deque(maxlen=window_size)
        self.cheating_score = 0.0
        self.frame_count = 0
        
        # Temporal tracking
        self.gaze_history: deque = deque(maxlen=30)
        self.head_turn_history: deque = deque(maxlen=30)
        self.face_presence_history: deque = deque(maxlen=60)
        self.hand_proximity_history: deque = deque(maxlen=30)
        self.audio_activity_history: deque = deque(maxlen=30)
        
        # Thresholds
        self.GAZE_DEVIATION_THRESHOLD = 0.3  # normalized
        self.EXTREME_HEAD_TURN_THRESHOLD = 45  # degrees
        self.MODERATE_HEAD_TURN_THRESHOLD = 25  # degrees
        self.FACE_MISSING_THRESHOLD = 0.6  # seconds
        self.PATTERN_WINDOW = 5  # events in 5 seconds
        
        # Scoring weights
        self.WEIGHTS = {
            EventType.EYE_GAZE_DEVIATION: 1,
            EventType.DOWNWARD_GAZE: 4,
            EventType.RAPID_SACCADE: 3,
            EventType.HEAD_TURN: 2,
            EventType.EXTREME_HEAD_TURN: 5,
            EventType.FACE_MISSING: 10,
            EventType.HAND_NEAR_FACE: 2,
            EventType.HAND_COVERING_FACE: 4,
            EventType.PHONE_DETECTED: 20,
            EventType.EARPHONE_DETECTED: 10,
            EventType.NOTES_DETECTED: 8,
            EventType.WHISPERING: 10,
            EventType.EXTERNAL_VOICE: 8,
            EventType.LIP_MOVEMENT_NO_AUDIO: 5,
            EventType.BACKGROUND_CHANGE: 3,
            EventType.CAMERA_OBSTRUCTION: 15,
            EventType.SUSPICIOUS_PATTERN: 12,
        }
        
        # Decay settings
        self.SCORE_DECAY_RATE = 0.02  # Decay per frame
        self.PATTERN_DECAY_TIME = 10  # seconds
        
    def detect_eye_behavior(
        self,
        gaze_direction: str,
        iris_position: Optional[Tuple[float, float]] = None,
        previous_iris_position: Optional[Tuple[float, float]] = None
    ) -> List[CheatEvent]:
        """
        Detect suspicious eye behavior
        
        Args:
            gaze_direction: "Looking at Screen", "Looking Left", "Looking Right", "Looking Up", "Looking Down"
            iris_position: Normalized iris position (x, y) in [0, 1]
            previous_iris_position: Previous frame's iris position for saccade detection
            
        Returns:
            List of detected events
        """
        events = []
        current_time = time.time()
        
        # Track gaze direction
        self.gaze_history.append({
            'direction': gaze_direction,
            'timestamp': current_time,
            'position': iris_position
        })
        
        # 1. Gaze Deviation Detection
        if gaze_direction != "Looking at Screen":
            event = CheatEvent(
                event_type=EventType.EYE_GAZE_DEVIATION,
                timestamp=current_time,
                severity=3 if gaze_direction in ["Looking Left", "Looking Right"] else 4,
                description=f"Eyes looking {gaze_direction}",
                confidence=0.8,
                frame_number=self.frame_count,
                metadata={'direction': gaze_direction}
            )
            events.append(event)
            
            # Special case: downward gaze (reading notes)
            if gaze_direction == "Looking Down":
                event = CheatEvent(
                    event_type=EventType.DOWNWARD_GAZE,
                    timestamp=current_time,
                    severity=4,
                    description="Long downward gaze detected - possibly reading notes",
                    confidence=0.75,
                    frame_number=self.frame_count
                )
                events.append(event)
        
        # 2. Rapid Saccade Detection
        if iris_position and previous_iris_position:
            distance = np.sqrt(
                (iris_position[0] - previous_iris_position[0])**2 +
                (iris_position[1] - previous_iris_position[1])**2
            )
            if distance > 0.15:  # Large movement
                event = CheatEvent(
                    event_type=EventType.RAPID_SACCADE,
                    timestamp=current_time,
                    severity=3,
                    description="Rapid eye movement detected",
                    confidence=0.7,
                    frame_number=self.frame_count,
                    metadata={'saccade_distance': float(distance)}
                )
                events.append(event)
        
        # 3. Repeated Glance Pattern Detection
        recent_deviations = [
            g for g in self.gaze_history
            if g['direction'] != "Looking at Screen" and
               current_time - g['timestamp'] < 5
        ]
        if len(recent_deviations) >= 3:
            event = CheatEvent(
                event_type=EventType.SUSPICIOUS_PATTERN,
                timestamp=current_time,
                severity=4,
                description=f"Repeated gaze deviations detected ({len(recent_deviations)} in 5 seconds)",
                confidence=0.8,
                frame_number=self.frame_count,
                metadata={'pattern_count': len(recent_deviations)}
            )
            events.append(event)
        
        return events
    
    def detect_head_behavior(
        self,
        head_direction: str,
        yaw: Optional[float] = None,
        pitch: Optional[float] = None,
        roll: Optional[float] = None
    ) -> List[CheatEvent]:
        """
        Detect suspicious head movements and orientation
        
        Args:
            head_direction: "Looking at Screen", "Looking Left", "Looking Right", "Looking Up", "Looking Down", "Tilted"
            yaw: Yaw angle in degrees (-90 to 90)
            pitch: Pitch angle in degrees (-90 to 90)
            roll: Roll angle in degrees (-180 to 180)
            
        Returns:
            List of detected events
        """
        events = []
        current_time = time.time()
        
        self.head_turn_history.append({
            'direction': head_direction,
            'yaw': yaw,
            'pitch': pitch,
            'roll': roll,
            'timestamp': current_time
        })
        
        # 1. Head Orientation Detection
        if head_direction != "Looking at Screen":
            if yaw and abs(yaw) > self.EXTREME_HEAD_TURN_THRESHOLD:
                event = CheatEvent(
                    event_type=EventType.EXTREME_HEAD_TURN,
                    timestamp=current_time,
                    severity=5,
                    description=f"Extreme head turn detected: {head_direction} ({abs(yaw):.1f}°)",
                    confidence=0.85,
                    frame_number=self.frame_count,
                    metadata={'direction': head_direction, 'angle': float(yaw)}
                )
                events.append(event)
            elif yaw and abs(yaw) > self.MODERATE_HEAD_TURN_THRESHOLD:
                event = CheatEvent(
                    event_type=EventType.HEAD_TURN,
                    timestamp=current_time,
                    severity=2,
                    description=f"Moderate head turn: {head_direction}",
                    confidence=0.8,
                    frame_number=self.frame_count,
                    metadata={'direction': head_direction, 'angle': float(yaw)}
                )
                events.append(event)
        
        # 2. Long-Duration Head Turn Detection
        head_turns = [
            h for h in self.head_turn_history
            if h['direction'] != "Looking at Screen" and
               current_time - h['timestamp'] < 3
        ]
        if len(head_turns) >= 15:  # Approximately 3 seconds at 30fps
            event = CheatEvent(
                event_type=EventType.SUSPICIOUS_PATTERN,
                timestamp=current_time,
                severity=5,
                description=f"Prolonged head turn detected for {len(head_turns)/30:.1f} seconds",
                confidence=0.85,
                frame_number=self.frame_count,
                metadata={'duration_frames': len(head_turns)}
            )
            events.append(event)
        
        # 3. Head & Eye Correlation
        if head_direction != "Looking at Screen" and self.gaze_history:
            last_gaze = self.gaze_history[-1]
            if last_gaze['direction'] != "Looking at Screen":
                if (head_direction == "Looking Left" and last_gaze['direction'] == "Looking Left") or \
                   (head_direction == "Looking Right" and last_gaze['direction'] == "Looking Right") or \
                   (head_direction == "Looking Down" and last_gaze['direction'] == "Looking Down"):
                    event = CheatEvent(
                        event_type=EventType.SUSPICIOUS_PATTERN,
                        timestamp=current_time,
                        severity=6,
                        description="Head and eyes moving together toward off-screen area",
                        confidence=0.9,
                        frame_number=self.frame_count,
                        metadata={'head_direction': head_direction, 'eye_direction': last_gaze['direction']}
                    )
                    events.append(event)
        
        return events
    
    def detect_face_presence(self, face_detected: bool) -> List[CheatEvent]:
        """
        Detect when face disappears from frame
        
        Args:
            face_detected: Whether face is detected in current frame
            
        Returns:
            List of detected events
        """
        events = []
        current_time = time.time()
        
        self.face_presence_history.append({
            'detected': face_detected,
            'timestamp': current_time
        })
        
        if not face_detected:
            # Calculate duration of absence
            recent_history = [
                h for h in self.face_presence_history
                if current_time - h['timestamp'] < 2
            ]
            
            absence_duration = 0
            for h in reversed(recent_history):
                if h['detected']:
                    break
                absence_duration = current_time - h['timestamp']
            
            if absence_duration > self.FACE_MISSING_THRESHOLD:
                severity = 5 if absence_duration < 2 else 10
                event = CheatEvent(
                    event_type=EventType.FACE_MISSING,
                    timestamp=current_time,
                    severity=min(10, severity),
                    description=f"Face missing from frame for {absence_duration:.1f} seconds",
                    confidence=0.95,
                    frame_number=self.frame_count,
                    metadata={'absence_duration': absence_duration}
                )
                events.append(event)
        
        return events
    
    def detect_hand_behavior(
        self,
        hand_detected: bool,
        hand_proximity_to_face: Optional[float] = None,
        hand_covering_face_ratio: Optional[float] = None
    ) -> List[CheatEvent]:
        """
        Detect suspicious hand behaviors
        
        Args:
            hand_detected: Whether hand is detected near face/head
            hand_proximity_to_face: Normalized distance (0-1, 0=touching, 1=far)
            hand_covering_face_ratio: Percentage of face covered by hand (0-1)
            
        Returns:
            List of detected events
        """
        events = []
        current_time = time.time()
        
        if hand_proximity_to_face is not None:
            self.hand_proximity_history.append({
                'proximity': hand_proximity_to_face,
                'timestamp': current_time
            })
        
        # 1. Hand Near Face Detection
        if hand_detected and hand_proximity_to_face is not None:
            if hand_proximity_to_face < 0.2:
                event = CheatEvent(
                    event_type=EventType.HAND_NEAR_FACE,
                    timestamp=current_time,
                    severity=2,
                    description="Hand detected near face (possible earphone usage)",
                    confidence=0.75,
                    frame_number=self.frame_count,
                    metadata={'proximity': float(hand_proximity_to_face)}
                )
                events.append(event)
        
        # 2. Hand Covering Face Detection
        if hand_covering_face_ratio is not None and hand_covering_face_ratio > 0.2:
            severity = 4 if hand_covering_face_ratio > 0.5 else 3
            event = CheatEvent(
                event_type=EventType.HAND_COVERING_FACE,
                timestamp=current_time,
                severity=severity,
                description=f"Hand covering {hand_covering_face_ratio*100:.0f}% of face",
                confidence=0.8,
                frame_number=self.frame_count,
                metadata={'coverage_ratio': float(hand_covering_face_ratio)}
            )
            events.append(event)
        
        # 3. Repeated Hand-to-Face Pattern
        recent_hand_events = [
            h for h in self.hand_proximity_history
            if h['proximity'] < 0.3 and current_time - h['timestamp'] < 10
        ]
        if len(recent_hand_events) >= 5:
            event = CheatEvent(
                event_type=EventType.SUSPICIOUS_PATTERN,
                timestamp=current_time,
                severity=4,
                description=f"Repeated hand-to-face gestures detected ({len(recent_hand_events)} times in 10s)",
                confidence=0.8,
                frame_number=self.frame_count,
                metadata={'gesture_count': len(recent_hand_events)}
            )
            events.append(event)
        
        return events
    
    def detect_gadgets(
        self,
        phone_detected: bool = False,
        earphone_detected: bool = False,
        notes_detected: bool = False,
        secondary_screen_detected: bool = False,
        confidence_scores: Optional[Dict[str, float]] = None
    ) -> List[CheatEvent]:
        """
        Detect presence of external gadgets/devices
        
        Args:
            phone_detected: Whether phone is in frame
            earphone_detected: Whether earphones are detected
            notes_detected: Whether notes/papers are detected
            secondary_screen_detected: Whether secondary screen is detected
            confidence_scores: Confidence scores for each detection
            
        Returns:
            List of detected events
        """
        events = []
        current_time = time.time()
        
        if confidence_scores is None:
            confidence_scores = {}
        
        if phone_detected:
            event = CheatEvent(
                event_type=EventType.PHONE_DETECTED,
                timestamp=current_time,
                severity=10,
                description="Mobile phone detected in frame",
                confidence=confidence_scores.get('phone', 0.8),
                frame_number=self.frame_count
            )
            events.append(event)
        
        if earphone_detected:
            event = CheatEvent(
                event_type=EventType.EARPHONE_DETECTED,
                timestamp=current_time,
                severity=8,
                description="Earphones/Bluetooth device detected",
                confidence=confidence_scores.get('earphone', 0.75),
                frame_number=self.frame_count
            )
            events.append(event)
        
        if notes_detected:
            event = CheatEvent(
                event_type=EventType.NOTES_DETECTED,
                timestamp=current_time,
                severity=7,
                description="Notes or printed materials detected",
                confidence=confidence_scores.get('notes', 0.8),
                frame_number=self.frame_count
            )
            events.append(event)
        
        if secondary_screen_detected:
            event = CheatEvent(
                event_type=EventType.PHONE_DETECTED,
                timestamp=current_time,
                severity=9,
                description="Secondary screen/display detected",
                confidence=confidence_scores.get('screen', 0.75),
                frame_number=self.frame_count
            )
            events.append(event)
        
        return events
    
    def detect_audio_behavior(
        self,
        audio_activity_level: float,
        external_voice_detected: bool = False,
        whispering_detected: bool = False,
        lip_movement_mismatch: bool = False
    ) -> List[CheatEvent]:
        """
        Detect suspicious audio patterns
        
        Args:
            audio_activity_level: Audio RMS level (0-1)
            external_voice_detected: Whether another voice is detected
            whispering_detected: Whether whispering is detected
            lip_movement_mismatch: Whether lips move without corresponding audio
            
        Returns:
            List of detected events
        """
        events = []
        current_time = time.time()
        
        self.audio_activity_history.append({
            'activity': audio_activity_level,
            'timestamp': current_time
        })
        
        if external_voice_detected:
            event = CheatEvent(
                event_type=EventType.EXTERNAL_VOICE,
                timestamp=current_time,
                severity=8,
                description="External voice detected in environment",
                confidence=0.85,
                frame_number=self.frame_count
            )
            events.append(event)
        
        if whispering_detected:
            event = CheatEvent(
                event_type=EventType.WHISPERING,
                timestamp=current_time,
                severity=10,
                description="Whispering detected",
                confidence=0.8,
                frame_number=self.frame_count
            )
            events.append(event)
        
        if lip_movement_mismatch:
            event = CheatEvent(
                event_type=EventType.LIP_MOVEMENT_NO_AUDIO,
                timestamp=current_time,
                severity=5,
                description="Lip movement detected without audio - silent speech",
                confidence=0.75,
                frame_number=self.frame_count
            )
            events.append(event)
        
        return events
    
    def detect_environment_issues(
        self,
        camera_obstructed: bool = False,
        brightness_change_detected: bool = False,
        background_change_detected: bool = False,
        another_person_detected: bool = False
    ) -> List[CheatEvent]:
        """
        Detect environmental anomalies and tampering attempts
        
        Args:
            camera_obstructed: Whether camera appears to be obstructed
            brightness_change_detected: Whether there's a sudden brightness change
            background_change_detected: Whether background has changed
            another_person_detected: Whether another person is in frame
            
        Returns:
            List of detected events
        """
        events = []
        current_time = time.time()
        
        if camera_obstructed:
            event = CheatEvent(
                event_type=EventType.CAMERA_OBSTRUCTION,
                timestamp=current_time,
                severity=10,
                description="Camera obstruction detected",
                confidence=0.9,
                frame_number=self.frame_count
            )
            events.append(event)
        
        if brightness_change_detected:
            event = CheatEvent(
                event_type=EventType.BACKGROUND_CHANGE,
                timestamp=current_time,
                severity=3,
                description="Sudden brightness change detected",
                confidence=0.7,
                frame_number=self.frame_count
            )
            events.append(event)
        
        if background_change_detected:
            event = CheatEvent(
                event_type=EventType.BACKGROUND_CHANGE,
                timestamp=current_time,
                severity=4,
                description="Background change detected",
                confidence=0.75,
                frame_number=self.frame_count
            )
            events.append(event)
        
        if another_person_detected:
            event = CheatEvent(
                event_type=EventType.SUSPICIOUS_PATTERN,
                timestamp=current_time,
                severity=8,
                description="Another person detected in frame",
                confidence=0.9,
                frame_number=self.frame_count
            )
            events.append(event)
        
        return events
    
    def process_frame(self, **detection_results) -> CheatingAnalysis:
        """
        Process a single frame with all detections and compute overall cheating score
        
        Args:
            **detection_results: Dictionary with detection results from various modules
                - gaze_direction: Eye gaze direction
                - head_direction: Head orientation
                - face_detected: Whether face is detected
                - iris_position: Current iris position
                - previous_iris_position: Previous iris position
                - hand_detected: Whether hand is near face
                - hand_proximity: Hand proximity to face
                - hand_covering_ratio: Hand covering ratio
                - phone_detected: Whether phone is detected
                - earphone_detected: Whether earphones detected
                - notes_detected: Whether notes detected
                - audio_activity: Audio activity level
                - external_voice_detected: Whether external voice detected
                - whispering_detected: Whether whispering detected
                - camera_obstructed: Whether camera is obstructed
                
        Returns:
            CheatingAnalysis with final score and recommendations
        """
        self.frame_count += 1
        current_time = time.time()
        frame_events = []
        
        # Run all detection modules
        if 'gaze_direction' in detection_results:
            frame_events.extend(self.detect_eye_behavior(
                detection_results.get('gaze_direction', 'Looking at Screen'),
                detection_results.get('iris_position'),
                detection_results.get('previous_iris_position')
            ))
        
        if 'head_direction' in detection_results:
            frame_events.extend(self.detect_head_behavior(
                detection_results.get('head_direction', 'Looking at Screen'),
                detection_results.get('yaw'),
                detection_results.get('pitch'),
                detection_results.get('roll')
            ))
        
        if 'face_detected' in detection_results:
            frame_events.extend(self.detect_face_presence(detection_results['face_detected']))
        
        frame_events.extend(self.detect_hand_behavior(
            detection_results.get('hand_detected', False),
            detection_results.get('hand_proximity'),
            detection_results.get('hand_covering_ratio')
        ))
        
        frame_events.extend(self.detect_gadgets(
            detection_results.get('phone_detected', False),
            detection_results.get('earphone_detected', False),
            detection_results.get('notes_detected', False),
            detection_results.get('secondary_screen_detected', False)
        ))
        
        frame_events.extend(self.detect_audio_behavior(
            detection_results.get('audio_activity', 0.0),
            detection_results.get('external_voice_detected', False),
            detection_results.get('whispering_detected', False),
            detection_results.get('lip_movement_mismatch', False)
        ))
        
        frame_events.extend(self.detect_environment_issues(
            detection_results.get('camera_obstructed', False),
            detection_results.get('brightness_change_detected', False),
            detection_results.get('background_change_detected', False),
            detection_results.get('another_person_detected', False)
        ))
        
        # Add events to history
        for event in frame_events:
            self.event_history.append(event)
        
        # Calculate cheating score
        self.cheating_score = self._calculate_score()
        
        # Determine suspicion level
        suspicion_level = self._get_suspicion_level(self.cheating_score)
        
        # Generate reasoning and recommendations
        reasoning, recommended_action = self._generate_recommendations(
            self.cheating_score,
            frame_events
        )
        
        return CheatingAnalysis(
            cheating_score=self.cheating_score,
            suspicion_level=suspicion_level,
            events=list(self.event_history),
            reasoning=reasoning,
            recommended_action=recommended_action,
            timestamp=current_time
        )
    
    def _calculate_score(self) -> float:
        """Calculate current cheating score based on event history"""
        score = 0.0
        current_time = time.time()
        
        # Sum weights of recent events (last 10 seconds)
        for event in self.event_history:
            if current_time - event.timestamp < 10:
                weight = self.WEIGHTS.get(event.event_type, 1)
                # Apply temporal decay
                time_decay = 1.0 - (current_time - event.timestamp) / 10.0
                score += weight * event.confidence * time_decay
        
        # Apply global decay
        score *= (1.0 - self.SCORE_DECAY_RATE)
        
        # Cap at 100
        return min(100.0, max(0.0, score))
    
    def _get_suspicion_level(self, score: float) -> SuspicionLevel:
        """Determine suspicion level based on score"""
        if score >= 50:
            return SuspicionLevel.CRITICAL
        elif score >= 35:
            return SuspicionLevel.HIGH
        elif score >= 20:
            return SuspicionLevel.MEDIUM
        else:
            return SuspicionLevel.LOW
    
    def _generate_recommendations(
        self,
        score: float,
        frame_events: List[CheatEvent]
    ) -> Tuple[str, str]:
        """
        Generate reasoning and recommendations based on analysis
        
        Args:
            score: Current cheating score
            frame_events: Events detected in current frame
            
        Returns:
            Tuple of (reasoning, recommended_action)
        """
        reasoning_parts = []
        
        # Analyze current frame events
        if frame_events:
            critical_events = [e for e in frame_events if e.severity >= 8]
            if critical_events:
                event_descriptions = [e.description for e in critical_events]
                reasoning_parts.append(
                    f"Critical indicators detected: {', '.join(event_descriptions)}"
                )
        
        # Analyze historical patterns
        recent_events = [
            e for e in self.event_history
            if time.time() - e.timestamp < 30
        ]
        
        if len(recent_events) > 0:
            event_type_counts = {}
            for event in recent_events:
                event_type_counts[event.event_type] = event_type_counts.get(event.event_type, 0) + 1
            
            for event_type, count in sorted(event_type_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
                reasoning_parts.append(f"{event_type.value}: {count} occurrences in last 30 seconds")
        
        # Determine action based on score
        if score >= 50:
            action = "IMMEDIATE ACTION: Mark as cheating, halt exam, flag recording for review"
        elif score >= 35:
            action = "HIGH SUSPICION: Flag for proctor review, increase monitoring intensity"
        elif score >= 20:
            action = "MODERATE SUSPICION: Monitor closely, document events"
        else:
            action = "LOW SUSPICION: Continue normal monitoring"
        
        reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Normal behavior detected"
        
        return reasoning, action
    
    def reset(self):
        """Reset the engine for a new session"""
        self.event_history.clear()
        self.cheating_score = 0.0
        self.frame_count = 0
        self.gaze_history.clear()
        self.head_turn_history.clear()
        self.face_presence_history.clear()
        self.hand_proximity_history.clear()
        self.audio_activity_history.clear()
    
    def get_summary(self) -> Dict:
        """Get summary statistics of current session"""
        return {
            'total_frames_analyzed': self.frame_count,
            'total_events_detected': len(self.event_history),
            'current_cheating_score': self.cheating_score,
            'average_events_per_minute': len(self.event_history) / max(1, self.frame_count / 1800),
            'critical_event_count': sum(1 for e in self.event_history if e.severity >= 8),
            'high_event_count': sum(1 for e in self.event_history if 5 <= e.severity < 8),
            'session_duration_seconds': self.frame_count / 30,  # Assuming 30 FPS
        }
