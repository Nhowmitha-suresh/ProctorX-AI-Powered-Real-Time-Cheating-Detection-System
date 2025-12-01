"""
Advanced UI Dashboard for Cheating Detection System
Provides professional visualization with real-time metrics and analytics
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import deque
import time
from cheating_detection_engine import SuspicionLevel, EventType, CheatingAnalysis


class UIColors:
    """Color palette for the dashboard"""
    # BGR format for OpenCV
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    DARK_GRAY = (40, 40, 40)
    LIGHT_GRAY = (200, 200, 200)
    
    # Status colors
    GREEN = (0, 255, 0)
    YELLOW = (0, 255, 255)
    ORANGE = (0, 165, 255)
    RED = (0, 0, 255)
    DARK_RED = (0, 0, 139)
    
    # Accent colors
    CYAN = (255, 255, 0)
    MAGENTA = (255, 0, 255)
    LIME = (0, 255, 128)
    
    @staticmethod
    def get_severity_color(severity: int) -> Tuple[int, int, int]:
        """Get color based on severity (1-10)"""
        if severity >= 8:
            return UIColors.RED
        elif severity >= 5:
            return UIColors.ORANGE
        elif severity >= 3:
            return UIColors.YELLOW
        else:
            return UIColors.GREEN


class DashboardPanel:
    """Base class for dashboard panels"""
    
    def __init__(self, x: int, y: int, width: int, height: int, title: str = ""):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.title = title
        self.background = None
    
    def draw_border(self, canvas: np.ndarray, color: Tuple[int, int, int] = UIColors.LIGHT_GRAY, thickness: int = 2):
        """Draw panel border"""
        cv2.rectangle(
            canvas,
            (self.x, self.y),
            (self.x + self.width, self.y + self.height),
            color, thickness
        )
    
    def draw_title(self, canvas: np.ndarray, color: Tuple[int, int, int] = UIColors.WHITE):
        """Draw panel title"""
        if self.title:
            cv2.putText(
                canvas, self.title,
                (self.x + 10, self.y + 25),
                cv2.FONT_HERSHEY_DUPLEX, 0.8, color, 1
            )
    
    def draw_background(self, canvas: np.ndarray, color: Tuple[int, int, int] = UIColors.DARK_GRAY):
        """Draw panel background"""
        cv2.rectangle(
            canvas,
            (self.x, self.y),
            (self.x + self.width, self.y + self.height),
            color, -1
        )


class ScorePanel(DashboardPanel):
    """Panel displaying cheating score"""
    
    def draw(self, canvas: np.ndarray, score: float, suspicion_level: SuspicionLevel):
        """Draw score panel"""
        self.draw_background(canvas)
        self.draw_border(canvas, UIColors.LIGHT_GRAY, 2)
        
        # Title
        self.draw_title(canvas)
        
        # Get color based on level
        color_map = {
            SuspicionLevel.LOW: UIColors.GREEN,
            SuspicionLevel.MEDIUM: UIColors.YELLOW,
            SuspicionLevel.HIGH: UIColors.ORANGE,
            SuspicionLevel.CRITICAL: UIColors.RED,
        }
        score_color = color_map[suspicion_level]
        
        # Score circle
        center_x = self.x + self.width // 2
        center_y = self.y + self.height // 2
        radius = 50
        
        # Draw circle background
        cv2.circle(canvas, (center_x, center_y), radius, UIColors.DARK_GRAY, -1)
        # Draw circle border
        cv2.circle(canvas, (center_x, center_y), radius, score_color, 3)
        
        # Draw score value
        score_text = f"{score:.1f}"
        font_scale = 1.5
        text_size = cv2.getTextSize(score_text, cv2.FONT_HERSHEY_DUPLEX, font_scale, 2)[0]
        cv2.putText(
            canvas, score_text,
            (center_x - text_size[0]//2, center_y + text_size[1]//2),
            cv2.FONT_HERSHEY_DUPLEX, font_scale, score_color, 2
        )
        
        # Draw level label
        level_text = f"Level: {suspicion_level.value}"
        cv2.putText(
            canvas, level_text,
            (self.x + 15, self.y + self.height - 15),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, score_color, 1
        )


class TimelinePanel(DashboardPanel):
    """Panel displaying event timeline graph"""
    
    def __init__(self, x: int, y: int, width: int, height: int, title: str = ""):
        super().__init__(x, y, width, height, title)
        self.score_history: deque = deque(maxlen=100)
        self.max_score = 100.0
    
    def add_score(self, score: float):
        """Add score to history"""
        self.score_history.append(score)
    
    def draw(self, canvas: np.ndarray):
        """Draw timeline panel"""
        self.draw_background(canvas)
        self.draw_border(canvas, UIColors.LIGHT_GRAY, 2)
        self.draw_title(canvas)
        
        if len(self.score_history) < 2:
            return
        
        # Calculate graph dimensions
        graph_x = self.x + 30
        graph_y = self.y + 35
        graph_width = self.width - 40
        graph_height = self.height - 50
        
        # Draw grid lines
        for i in range(0, 6):
            y_pos = graph_y + (graph_height * i // 5)
            cv2.line(canvas, (graph_x, y_pos), (graph_x + graph_width, y_pos),
                    (60, 60, 60), 1)
        
        # Draw threshold lines
        # Low threshold (10)
        low_y = graph_y + graph_height - (10 / self.max_score) * graph_height
        cv2.line(canvas, (graph_x, int(low_y)), (graph_x + graph_width, int(low_y)),
                UIColors.GREEN, 1)
        # Medium threshold (20)
        med_y = graph_y + graph_height - (20 / self.max_score) * graph_height
        cv2.line(canvas, (graph_x, int(med_y)), (graph_x + graph_width, int(med_y)),
                UIColors.YELLOW, 1)
        # High threshold (35)
        high_y = graph_y + graph_height - (35 / self.max_score) * graph_height
        cv2.line(canvas, (graph_x, int(high_y)), (graph_x + graph_width, int(high_y)),
                UIColors.ORANGE, 1)
        # Critical threshold (50)
        crit_y = graph_y + graph_height - (50 / self.max_score) * graph_height
        cv2.line(canvas, (graph_x, int(crit_y)), (graph_x + graph_width, int(crit_y)),
                UIColors.RED, 2)
        
        # Draw score history
        points = []
        for i, score in enumerate(self.score_history):
            x_pos = graph_x + (i / max(len(self.score_history) - 1, 1)) * graph_width
            y_pos = graph_y + graph_height - (score / self.max_score) * graph_height
            points.append((int(x_pos), int(y_pos)))
        
        # Draw line connecting points
        for i in range(len(points) - 1):
            color = UIColors.get_severity_color(int(self.score_history[i] / 10))
            cv2.line(canvas, points[i], points[i+1], color, 2)
        
        # Draw points
        for point, score in zip(points, self.score_history):
            color = UIColors.get_severity_color(int(score / 10))
            cv2.circle(canvas, point, 3, color, -1)


class EventListPanel(DashboardPanel):
    """Panel displaying recent events"""
    
    def draw(self, canvas: np.ndarray, events: List, max_events: int = 5):
        """Draw event list panel"""
        self.draw_background(canvas)
        self.draw_border(canvas, UIColors.LIGHT_GRAY, 2)
        self.draw_title(canvas)
        
        y_offset = self.y + 35
        line_height = 30
        
        recent_events = events[-max_events:] if events else []
        
        if not recent_events:
            cv2.putText(
                canvas, "No suspicious events",
                (self.x + 15, y_offset + line_height),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, UIColors.GREEN, 1
            )
            return
        
        for i, event in enumerate(recent_events):
            y_pos = y_offset + i * line_height
            
            # Event color based on severity
            color = UIColors.get_severity_color(event.severity)
            
            # Event type
            event_text = f"• {event.event_type.value}"
            cv2.putText(
                canvas, event_text,
                (self.x + 15, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1
            )
            
            # Severity indicator
            severity_text = f"[S:{event.severity}] {event.description[:30]}"
            cv2.putText(
                canvas, severity_text,
                (self.x + 20, y_pos + 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, UIColors.LIGHT_GRAY, 1
            )


class StatsPanel(DashboardPanel):
    """Panel displaying statistics"""
    
    def draw(self, canvas: np.ndarray, stats: Dict):
        """Draw statistics panel"""
        self.draw_background(canvas)
        self.draw_border(canvas, UIColors.LIGHT_GRAY, 2)
        self.draw_title(canvas)
        
        y_offset = self.y + 35
        line_height = 22
        
        # Stat items
        stat_items = [
            ("Total Events", str(stats.get('total_events', 0))),
            ("Critical Events", str(stats.get('critical_events', 0))),
            ("Avg Events/Min", f"{stats.get('avg_events_per_min', 0):.1f}"),
            ("Duration", f"{stats.get('duration_sec', 0):.0f}s"),
        ]
        
        for i, (label, value) in enumerate(stat_items):
            y_pos = y_offset + i * line_height
            
            # Label
            cv2.putText(
                canvas, f"{label}:",
                (self.x + 15, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, UIColors.LIGHT_GRAY, 1
            )
            
            # Value
            cv2.putText(
                canvas, value,
                (self.x + self.width - 50, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, UIColors.CYAN, 1
            )


class ActionPanel(DashboardPanel):
    """Panel displaying recommended action"""
    
    def draw(self, canvas: np.ndarray, action: str, severity: SuspicionLevel):
        """Draw action panel"""
        self.draw_background(canvas)
        
        # Color border based on severity
        color_map = {
            SuspicionLevel.LOW: UIColors.GREEN,
            SuspicionLevel.MEDIUM: UIColors.YELLOW,
            SuspicionLevel.HIGH: UIColors.ORANGE,
            SuspicionLevel.CRITICAL: UIColors.RED,
        }
        color = color_map[severity]
        self.draw_border(canvas, color, 3)
        
        self.draw_title(canvas, color)
        
        # Wrap action text
        y_offset = self.y + 35
        words = action.split()
        lines = []
        current_line = ""
        max_width = 70
        
        for word in words:
            if len(current_line) + len(word) + 1 > max_width:
                lines.append(current_line)
                current_line = word
            else:
                current_line += " " + word if current_line else word
        if current_line:
            lines.append(current_line)
        
        for i, line in enumerate(lines[:3]):  # Max 3 lines
            cv2.putText(
                canvas, line,
                (self.x + 15, y_offset + i * 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1
            )


class CheatingDetectionDashboard:
    """Main dashboard combining all panels"""
    
    def __init__(self, width: int = 1920, height: int = 1440):
        """Initialize dashboard"""
        self.width = width
        self.height = height
        self.canvas = np.zeros((height, width, 3), dtype=np.uint8)
        self.canvas[:] = UIColors.BLACK
        
        # Initialize panels
        self.score_panel = ScorePanel(10, 10, 300, 200, "CHEATING SCORE")
        self.timeline_panel = TimelinePanel(320, 10, 800, 200, "SCORE TIMELINE")
        self.stats_panel = StatsPanel(1130, 10, 280, 200, "STATISTICS")
        
        self.action_panel = ActionPanel(10, 220, 1400, 120, "RECOMMENDED ACTION")
        
        self.event_panel = EventListPanel(10, 350, 700, 250, "RECENT EVENTS")
        self.details_panel = DashboardPanel(720, 350, 690, 250, "DETECTION DETAILS")
        
        # Webcam feed area
        self.webcam_area_x = 10
        self.webcam_area_y = 610
        self.webcam_area_width = 1400
        self.webcam_area_height = 800
    
    def update(
        self,
        frame: np.ndarray,
        analysis: CheatingAnalysis,
        stats: Dict
    ) -> np.ndarray:
        """
        Update dashboard with new data
        
        Args:
            frame: Video frame from webcam
            analysis: CheatingAnalysis result
            stats: Statistics dictionary
            
        Returns:
            Rendered dashboard frame
        """
        # Create fresh canvas
        self.canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self.canvas[:] = UIColors.BLACK
        
        # Draw panels
        self.score_panel.draw(self.canvas, analysis.cheating_score, analysis.suspicion_level)
        self.timeline_panel.add_score(analysis.cheating_score)
        self.timeline_panel.draw(self.canvas)
        self.stats_panel.draw(self.canvas, stats)
        self.action_panel.draw(self.canvas, analysis.recommended_action, analysis.suspicion_level)
        self.event_panel.draw(self.canvas, analysis.events, max_events=5)
        
        # Draw details panel
        self._draw_details_panel(self.canvas, analysis)
        
        # Resize and embed webcam frame
        if frame is not None:
            resized_frame = cv2.resize(frame, (self.webcam_area_width, self.webcam_area_height))
            self.canvas[
                self.webcam_area_y:self.webcam_area_y + self.webcam_area_height,
                self.webcam_area_x:self.webcam_area_x + self.webcam_area_width
            ] = resized_frame
            
            # Draw frame border
            cv2.rectangle(
                self.canvas,
                (self.webcam_area_x, self.webcam_area_y),
                (self.webcam_area_x + self.webcam_area_width, self.webcam_area_y + self.webcam_area_height),
                UIColors.LIGHT_GRAY, 2
            )
        
        # Draw header
        self._draw_header()
        
        return self.canvas
    
    def _draw_details_panel(self, canvas: np.ndarray, analysis: CheatingAnalysis):
        """Draw details panel with event breakdown"""
        panel = self.details_panel
        panel.draw_background(canvas)
        panel.draw_border(canvas, UIColors.LIGHT_GRAY, 2)
        panel.draw_title(canvas)
        
        y_offset = panel.y + 35
        line_height = 25
        
        # Count events by type
        event_counts = {}
        for event in analysis.events:
            event_type = event.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        # Display top 5 event types
        sorted_events = sorted(event_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        for i, (event_type, count) in enumerate(sorted_events):
            y_pos = y_offset + i * line_height
            
            # Event type
            cv2.putText(
                canvas, event_type[:20],
                (panel.x + 15, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, UIColors.LIGHT_GRAY, 1
            )
            
            # Count bar
            bar_width = 100
            bar_height = 8
            max_count = max(c for _, c in sorted_events)
            filled_width = int((count / max_count) * bar_width)
            
            cv2.rectangle(
                canvas,
                (panel.x + 200, y_pos - 5),
                (panel.x + 200 + bar_width, y_pos + bar_height - 5),
                UIColors.DARK_GRAY, -1
            )
            
            color = UIColors.get_severity_color(count)
            cv2.rectangle(
                canvas,
                (panel.x + 200, y_pos - 5),
                (panel.x + 200 + filled_width, y_pos + bar_height - 5),
                color, -1
            )
            
            # Count
            cv2.putText(
                canvas, str(count),
                (panel.x + 310, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, UIColors.CYAN, 1
            )
    
    def _draw_header(self):
        """Draw dashboard header"""
        header_height = 50
        cv2.rectangle(
            self.canvas,
            (0, 0),
            (self.width, header_height),
            UIColors.DARK_GRAY, -1
        )
        
        title_text = "ADVANCED CHEATING DETECTION & PROCTORING DASHBOARD"
        cv2.putText(
            self.canvas, title_text,
            (20, 35),
            cv2.FONT_HERSHEY_DUPLEX, 1.2, UIColors.CYAN, 2
        )
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            self.canvas, timestamp,
            (self.width - 250, 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, UIColors.WHITE, 1
        )


def create_simple_ui(frame: np.ndarray, analysis: CheatingAnalysis) -> np.ndarray:
    """
    Create a simpler UI overlay for video frame
    
    Args:
        frame: Video frame
        analysis: CheatingAnalysis result
        
    Returns:
        Frame with UI overlay
    """
    output = frame.copy()
    h, w = frame.shape[:2]
    
    # Color based on severity
    color_map = {
        SuspicionLevel.LOW: UIColors.GREEN,
        SuspicionLevel.MEDIUM: UIColors.YELLOW,
        SuspicionLevel.HIGH: UIColors.ORANGE,
        SuspicionLevel.CRITICAL: UIColors.RED,
    }
    color = color_map[analysis.suspicion_level]
    
    # Draw thick border
    cv2.rectangle(output, (5, 5), (w-5, h-5), color, 5)
    
    # Top-left: Score
    score_bg = np.zeros((100, 200, 3), dtype=np.uint8)
    score_bg[:] = UIColors.DARK_GRAY
    output[5:105, 5:205] = score_bg
    cv2.putText(output, f"SCORE: {analysis.cheating_score:.1f}", (15, 35),
                cv2.FONT_HERSHEY_DUPLEX, 1.2, color, 2)
    cv2.putText(output, f"Level: {analysis.suspicion_level.value}", (15, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 1)
    
    # Top-right: Status
    status_text = "🔴 ALERT" if analysis.cheating_score >= 35 else "🟡 WATCH" if analysis.cheating_score >= 20 else "🟢 OK"
    cv2.putText(output, status_text, (w - 180, 35),
                cv2.FONT_HERSHEY_DUPLEX, 1.2, color, 2)
    
    # Bottom: Recent events
    event_bg_height = 120
    output[h - event_bg_height:h, :] = UIColors.DARK_GRAY
    
    cv2.putText(output, "RECENT EVENTS:", (10, h - event_bg_height + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, UIColors.WHITE, 1)
    
    recent_events = analysis.events[-3:]
    for i, event in enumerate(recent_events):
        event_color = UIColors.get_severity_color(event.severity)
        cv2.putText(output, f"• {event.event_type.value}", (10, h - event_bg_height + 50 + i*20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, event_color, 1)
    
    # Bottom-right: Action
    cv2.putText(output, "ACTION:", (w - 400, h - event_bg_height + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
    cv2.putText(output, analysis.recommended_action[:60], (w - 400, h - event_bg_height + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    
    return output
