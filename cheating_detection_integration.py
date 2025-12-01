"""
Integration module that connects the cheating detection engine with existing detection systems
"""

import cv2
import numpy as np
import time
from cheating_detection_engine import CheatingDetectionEngine, CheatingAnalysis, SuspicionLevel


class CheatingDetectionIntegration:
    """
    Integrates cheating detection engine with eye movement, head pose, and mobile detection modules
    """
    
    def __init__(self):
        """Initialize the integration system"""
        self.engine = CheatingDetectionEngine()
        self.previous_iris_position = None
        self.previous_frame_hash = None
        self.background_model = None
        self.baseline_brightness = None
        self.last_brightness = None
        self.fps_counter = 0
        self.fps_time = time.time()
        
    def analyze_frame(
        self,
        frame: np.ndarray,
        gaze_direction: str,
        head_direction: str,
        iris_position: tuple = None,
        mobile_detected: bool = False,
        face_detected: bool = True
    ) -> CheatingAnalysis:
        """
        Analyze a frame with all available detection results
        
        Args:
            frame: Video frame
            gaze_direction: Eye gaze direction from eye_movement module
            head_direction: Head direction from head_pose module
            iris_position: Normalized iris position (x, y)
            mobile_detected: Whether mobile phone is detected
            face_detected: Whether face is detected
            
        Returns:
            CheatingAnalysis with scores and recommendations
        """
        
        # Extract environmental features
        brightness_change = self._detect_brightness_change(frame)
        background_change = self._detect_background_change(frame)
        camera_obstructed = self._detect_camera_obstruction(frame)
        
        # Prepare detection results
        detection_results = {
            'gaze_direction': gaze_direction,
            'head_direction': head_direction,
            'iris_position': iris_position,
            'previous_iris_position': self.previous_iris_position,
            'face_detected': face_detected,
            'phone_detected': mobile_detected,
            'brightness_change_detected': brightness_change,
            'background_change_detected': background_change,
            'camera_obstructed': camera_obstructed,
        }
        
        # Process through engine
        analysis = self.engine.process_frame(**detection_results)
        
        # Update tracking variables
        self.previous_iris_position = iris_position
        
        return analysis
    
    def _detect_brightness_change(self, frame: np.ndarray, threshold: float = 0.2) -> bool:
        """
        Detect sudden brightness changes
        
        Args:
            frame: Video frame
            threshold: Brightness change threshold (0-1)
            
        Returns:
            True if significant brightness change detected
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        current_brightness = np.mean(gray) / 255.0
        
        if self.baseline_brightness is None:
            self.baseline_brightness = current_brightness
            self.last_brightness = current_brightness
            return False
        
        brightness_change = abs(current_brightness - self.last_brightness)
        self.last_brightness = current_brightness
        
        return brightness_change > threshold
    
    def _detect_background_change(self, frame: np.ndarray, threshold: float = 0.1) -> bool:
        """
        Detect background changes using frame differentiation
        
        Args:
            frame: Video frame
            threshold: Change threshold (0-1)
            
        Returns:
            True if significant background change detected
        """
        # Simple hash-based change detection
        current_hash = self._compute_frame_hash(frame)
        
        if self.previous_frame_hash is None:
            self.previous_frame_hash = current_hash
            return False
        
        # Calculate similarity (0-1, 1 = identical)
        similarity = self._compare_hashes(self.previous_frame_hash, current_hash)
        
        self.previous_frame_hash = current_hash
        
        return similarity < (1.0 - threshold)
    
    def _detect_camera_obstruction(self, frame: np.ndarray, threshold: float = 0.8) -> bool:
        """
        Detect if camera is obstructed or blocked
        
        Args:
            frame: Video frame
            threshold: Obstruction threshold
            
        Returns:
            True if camera appears obstructed
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate variance - very low variance indicates uniform/blocked camera
        variance = np.var(gray)
        
        # Normalize variance (for typical video frames)
        # Very low variance indicates obstruction
        return variance < 100  # Typical threshold
    
    def _compute_frame_hash(self, frame: np.ndarray, size: int = 8) -> np.ndarray:
        """
        Compute a perceptual hash of the frame
        
        Args:
            frame: Video frame
            size: Hash grid size
            
        Returns:
            Hash array
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (size, size))
        return resized
    
    def _compare_hashes(self, hash1: np.ndarray, hash2: np.ndarray) -> float:
        """
        Compare two frame hashes
        
        Args:
            hash1: First hash
            hash2: Second hash
            
        Returns:
            Similarity score (0-1, 1 = identical)
        """
        if hash1 is None or hash2 is None:
            return 1.0
        
        # Mean squared error normalized
        mse = np.mean((hash1.astype(float) - hash2.astype(float)) ** 2)
        # Normalize to 0-1
        max_mse = 255.0 ** 2
        similarity = 1.0 - (mse / max_mse)
        
        return max(0.0, min(1.0, similarity))
    
    def render_analysis(
        self,
        frame: np.ndarray,
        analysis: CheatingAnalysis
    ) -> np.ndarray:
        """
        Render analysis results on frame
        
        Args:
            frame: Video frame
            analysis: CheatingAnalysis result
            
        Returns:
            Frame with visualization
        """
        output = frame.copy()
        
        # Determine color based on suspicion level
        color_map = {
            SuspicionLevel.LOW: (0, 255, 0),      # Green
            SuspicionLevel.MEDIUM: (0, 255, 255),  # Yellow
            SuspicionLevel.HIGH: (0, 165, 255),    # Orange
            SuspicionLevel.CRITICAL: (0, 0, 255),  # Red
        }
        
        color = color_map[analysis.suspicion_level]
        
        # Draw border
        cv2.rectangle(output, (5, 5), (output.shape[1]-5, output.shape[0]-5), color, 3)
        
        # Draw cheating score
        score_text = f"Cheating Score: {analysis.cheating_score:.1f}"
        cv2.putText(
            output, score_text, (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2
        )
        
        # Draw suspicion level
        level_text = f"Level: {analysis.suspicion_level.value}"
        cv2.putText(
            output, level_text, (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2
        )
        
        # Draw recent events
        y_offset = 100
        recent_events = [e for e in analysis.events[-5:]]  # Last 5 events
        
        cv2.putText(
            output, "Recent Events:", (20, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1
        )
        
        for i, event in enumerate(recent_events):
            event_text = f"• {event.event_type.value} (S:{event.severity})"
            cv2.putText(
                output, event_text, (25, y_offset + 25 + i*20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1
            )
        
        # Draw recommendation (bottom)
        recommendation_y = output.shape[0] - 50
        cv2.putText(
            output, "Action:", (20, recommendation_y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1
        )
        
        # Wrap recommendation text
        words = analysis.recommended_action.split()
        line = ""
        for word in words:
            if len(line) + len(word) + 1 > 80:
                cv2.putText(
                    output, line, (20, recommendation_y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1
                )
                recommendation_y += 20
                line = word
            else:
                line += " " + word if line else word
        
        if line:
            cv2.putText(
                output, line, (20, recommendation_y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1
            )
        
        return output
    
    def get_session_report(self) -> str:
        """
        Generate a text report of the session
        
        Returns:
            Report string
        """
        summary = self.engine.get_summary()
        
        report = f"""
{'='*60}
CHEATING DETECTION SESSION REPORT
{'='*60}

Session Summary:
  • Total Frames Analyzed: {summary['total_frames_analyzed']}
  • Session Duration: {summary['session_duration_seconds']:.1f} seconds
  • Total Events Detected: {summary['total_events_detected']}
  • Average Events/Minute: {summary['average_events_per_minute']:.1f}
  • Critical Events: {summary['critical_event_count']}
  • High Severity Events: {summary['high_event_count']}
  • Final Score: {summary.get('current_cheating_score', 0):.1f}

Event Breakdown:
"""
        
        event_type_counts = {}
        for event in self.engine.event_history:
            event_type = event.event_type.value
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        
        for event_type, count in sorted(event_type_counts.items(), key=lambda x: x[1], reverse=True):
            report += f"  • {event_type}: {count}\n"
        
        report += f"{'='*60}\n"
        
        return report
