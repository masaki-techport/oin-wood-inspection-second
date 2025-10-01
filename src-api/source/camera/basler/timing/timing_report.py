"""
Timing Report Module for BaslerCamera Performance Monitoring.

This module provides comprehensive timing tracking for all major operations
in the Basler camera system including image capture, analysis, saving, and
presentation image selection.
"""

import os
import time
import json
import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict, deque

logger = logging.getLogger('BaslerCamera.TimingReport')

@dataclass
class TimingMeasurement:
    """Individual timing measurement for a specific operation."""
    operation_name: str
    start_time: str = ""
    end_time: str = ""
    duration: float = 0.0
    duration_with_unit: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        # Add duration with unit
        if self.duration > 0:
            if self.duration < 0.001:
                self.duration_with_unit = f"{self.duration * 1000000:.2f} μs"
            elif self.duration < 1.0:
                self.duration_with_unit = f"{self.duration * 1000:.2f} ms"
            else:
                self.duration_with_unit = f"{self.duration:.3f} s"

@dataclass
class OperationTiming:
    """Timing statistics for a specific operation type."""
    operation_name: str
    total_calls: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    average_time: float = 0.0
    recent_times: deque = None
    
    def __post_init__(self):
        if self.recent_times is None:
            self.recent_times = deque(maxlen=100)  # Keep last 100 measurements
    
    def add_measurement(self, duration: float):
        """Add a timing measurement."""
        self.total_calls += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.average_time = self.total_time / self.total_calls
        self.recent_times.append(duration)
    
    def get_recent_average(self, count: int = 10) -> float:
        """Get average of recent measurements."""
        recent = list(self.recent_times)[-count:]
        return sum(recent) / len(recent) if recent else 0.0

@dataclass
class SessionTiming:
    """Timing data for a complete processing session."""
    session_id: str
    start_time: str = ""
    end_time: str = ""
    total_duration: Optional[float] = None
    total_duration_with_unit: str = ""
    
    # Phase timings
    capture_start: str = ""
    capture_end: str = ""
    capture_duration: Optional[float] = None
    capture_duration_with_unit: str = ""
    
    analysis_start: str = ""
    analysis_end: str = ""
    analysis_duration: Optional[float] = None
    analysis_duration_with_unit: str = ""
    
    save_start: str = ""
    save_end: str = ""
    save_duration: Optional[float] = None
    save_duration_with_unit: str = ""
    
    presentation_start: str = ""
    presentation_end: str = ""
    presentation_duration: Optional[float] = None
    presentation_duration_with_unit: str = ""
    
    # Detailed measurements
    measurements: List[TimingMeasurement] = None
    operation_stats: Dict[str, OperationTiming] = None
    
    # Session metadata
    image_count: int = 0
    output_directory: str = ""
    inspection_id: Optional[int] = None
    sensor_trigger_time: str = ""
    
    def __post_init__(self):
        if self.measurements is None:
            self.measurements = []
        if self.operation_stats is None:
            self.operation_stats = {}
    
    def _format_duration_with_unit(self, duration: float) -> str:
        """Format duration with appropriate unit."""
        if duration is None or duration <= 0:
            return ""
        if duration < 0.001:
            return f"{duration * 1000000:.2f} μs"
        elif duration < 1.0:
            return f"{duration * 1000:.2f} ms"
        else:
            return f"{duration:.3f} s"
    
    def finalize(self):
        """Finalize the session timing."""
        if not self.end_time:
            self.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # Calculate total duration from start and end times
        if self.start_time and self.end_time:
            start_dt = datetime.strptime(self.start_time, "%Y-%m-%d %H:%M:%S.%f")
            end_dt = datetime.strptime(self.end_time, "%Y-%m-%d %H:%M:%S.%f")
            self.total_duration = (end_dt - start_dt).total_seconds()
            self.total_duration_with_unit = self._format_duration_with_unit(self.total_duration)
        
        # Calculate phase durations
        if self.capture_start and self.capture_end:
            start_dt = datetime.strptime(self.capture_start, "%Y-%m-%d %H:%M:%S.%f")
            end_dt = datetime.strptime(self.capture_end, "%Y-%m-%d %H:%M:%S.%f")
            self.capture_duration = (end_dt - start_dt).total_seconds()
            self.capture_duration_with_unit = self._format_duration_with_unit(self.capture_duration)
            
        if self.analysis_start and self.analysis_end:
            start_dt = datetime.strptime(self.analysis_start, "%Y-%m-%d %H:%M:%S.%f")
            end_dt = datetime.strptime(self.analysis_end, "%Y-%m-%d %H:%M:%S.%f")
            self.analysis_duration = (end_dt - start_dt).total_seconds()
            self.analysis_duration_with_unit = self._format_duration_with_unit(self.analysis_duration)
            
        if self.save_start and self.save_end:
            start_dt = datetime.strptime(self.save_start, "%Y-%m-%d %H:%M:%S.%f")
            end_dt = datetime.strptime(self.save_end, "%Y-%m-%d %H:%M:%S.%f")
            self.save_duration = (end_dt - start_dt).total_seconds()
            self.save_duration_with_unit = self._format_duration_with_unit(self.save_duration)
            
        if self.presentation_start and self.presentation_end:
            start_dt = datetime.strptime(self.presentation_start, "%Y-%m-%d %H:%M:%S.%f")
            end_dt = datetime.strptime(self.presentation_end, "%Y-%m-%d %H:%M:%S.%f")
            self.presentation_duration = (end_dt - start_dt).total_seconds()
            self.presentation_duration_with_unit = self._format_duration_with_unit(self.presentation_duration)

class TimingCollector:
    """Collects and manages timing measurements."""
    
    def __init__(self, max_sessions: int = 50):
        """Initialize timing collector."""
        self.max_sessions = max_sessions
        self.current_session: Optional[SessionTiming] = None
        self.completed_sessions: List[SessionTiming] = []
        self.operation_stats: Dict[str, OperationTiming] = defaultdict(lambda: OperationTiming(operation_name=""))
        
        # Active measurements stack for nested operations
        self.active_measurements: List[TimingMeasurement] = []
        
        logger.info("TimingCollector initialized")
    
    def start_session(self, session_id: str, sensor_trigger_time: Optional[float] = None) -> SessionTiming:
        """Start a new timing session."""
        if self.current_session:
            logger.warning(f"Starting new session {session_id} while session {self.current_session.session_id} is active")
            self.finalize_current_session()
        
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        sensor_trigger_str = ""
        if sensor_trigger_time:
            sensor_trigger_str = datetime.fromtimestamp(sensor_trigger_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        self.current_session = SessionTiming(
            session_id=session_id,
            start_time=current_time_str,
            sensor_trigger_time=sensor_trigger_str
        )
        
        logger.info(f"Started timing session: {session_id}")
        return self.current_session
    
    def finalize_current_session(self) -> Optional[SessionTiming]:
        """Finalize the current session."""
        if not self.current_session:
            return None
        
        self.current_session.finalize()

        # Inject synthetic phase measurements into Operation Timeline for clarity
        try:
            phase_defs = [
                ("phase_capture", self.current_session.capture_start, self.current_session.capture_end, self.current_session.capture_duration),
                ("phase_analysis", self.current_session.analysis_start, self.current_session.analysis_end, self.current_session.analysis_duration),
                ("phase_save", self.current_session.save_start, self.current_session.save_end, self.current_session.save_duration),
                ("phase_presentation", self.current_session.presentation_start, self.current_session.presentation_end, self.current_session.presentation_duration),
            ]
            for name, start_str, end_str, dur in phase_defs:
                if start_str and end_str and dur is not None and dur >= 0:
                    tm = TimingMeasurement(
                        operation_name=name,
                        start_time=start_str,
                        end_time=end_str,
                        duration=dur,
                        metadata={"phase": name.split("_", 1)[-1]}
                    )
                    self.current_session.measurements.append(tm)
        except Exception:
            pass
        self.completed_sessions.append(self.current_session)
        
        # Update operation statistics
        for measurement in self.current_session.measurements:
            if measurement.operation_name not in self.operation_stats:
                self.operation_stats[measurement.operation_name] = OperationTiming(
                    operation_name=measurement.operation_name
                )
            self.operation_stats[measurement.operation_name].add_measurement(measurement.duration)
        
        # Maintain max sessions limit
        if len(self.completed_sessions) > self.max_sessions:
            self.completed_sessions.pop(0)
        
        completed_session = self.current_session
        self.current_session = None
        
        logger.info(f"Finalized timing session: {completed_session.session_id}")
        return completed_session
    
    def start_measurement(self, operation_name: str, metadata: Dict[str, Any] = None) -> str:
        """Start timing a specific operation."""
        measurement_id = f"{operation_name}_{int(time.time() * 1000000)}"
        
        measurement = TimingMeasurement(
            operation_name=operation_name,
            start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            end_time="",
            duration=0.0,
            metadata=metadata or {}
        )
        
        self.active_measurements.append(measurement)
        
        if self.current_session:
            self.current_session.measurements.append(measurement)
        
        logger.debug(f"Started measurement: {operation_name} (ID: {measurement_id})")
        return measurement_id
    
    def end_measurement(self, operation_name: str, measurement_id: str = None) -> Optional[float]:
        """End timing a specific operation."""
        end_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # Find the most recent measurement for this operation
        measurement = None
        for i in range(len(self.active_measurements) - 1, -1, -1):
            if self.active_measurements[i].operation_name == operation_name:
                measurement = self.active_measurements.pop(i)
                break
        
        if not measurement:
            logger.warning(f"No active measurement found for operation: {operation_name}")
            return None
        
        measurement.end_time = end_time_str
        
        # Calculate duration from start and end time strings
        start_dt = datetime.strptime(measurement.start_time, "%Y-%m-%d %H:%M:%S.%f")
        end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S.%f")
        measurement.duration = (end_dt - start_dt).total_seconds()
        
        # Update duration with unit
        if measurement.duration < 0.001:
            measurement.duration_with_unit = f"{measurement.duration * 1000000:.2f} μs"
        elif measurement.duration < 1.0:
            measurement.duration_with_unit = f"{measurement.duration * 1000:.2f} ms"
        else:
            measurement.duration_with_unit = f"{measurement.duration:.3f} s"
        
        logger.debug(f"Ended measurement: {operation_name} (duration: {measurement.duration_with_unit})")
        return measurement.duration
    
    def mark_phase_start(self, phase: str):
        """Mark the start of a major phase."""
        if not self.current_session:
            logger.warning(f"Cannot mark phase start {phase} - no active session")
            return
        
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        if phase == "capture":
            self.current_session.capture_start = current_time_str
        elif phase == "analysis":
            self.current_session.analysis_start = current_time_str
        elif phase == "save":
            self.current_session.save_start = current_time_str
        elif phase == "presentation":
            self.current_session.presentation_start = current_time_str
        
        logger.debug(f"Marked {phase} phase start at {current_time_str}")
    
    def mark_phase_end(self, phase: str):
        """Mark the end of a major phase."""
        if not self.current_session:
            logger.warning(f"Cannot mark phase end {phase} - no active session")
            return
        
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        if phase == "capture":
            self.current_session.capture_end = current_time_str
        elif phase == "analysis":
            self.current_session.analysis_end = current_time_str
        elif phase == "save":
            self.current_session.save_end = current_time_str
        elif phase == "presentation":
            self.current_session.presentation_end = current_time_str
        
        logger.debug(f"Marked {phase} phase end at {current_time_str}")
    
    def set_session_metadata(self, **kwargs):
        """Set metadata for the current session."""
        if not self.current_session:
            logger.warning("Cannot set session metadata - no active session")
            return
        
        for key, value in kwargs.items():
            if hasattr(self.current_session, key):
                setattr(self.current_session, key, value)
            else:
                logger.warning(f"Unknown session metadata field: {key}")
    
    def get_current_session(self) -> Optional[SessionTiming]:
        """Get the current active session."""
        return self.current_session
    
    def get_session_summary(self, session_id: str = None) -> Optional[Dict[str, Any]]:
        """Get summary of a specific session or the current session."""
        if session_id:
            # Find specific session
            for session in self.completed_sessions:
                if session.session_id == session_id:
                    return self._create_session_summary(session)
            return None
        elif self.current_session:
            return self._create_session_summary(self.current_session)
        else:
            return None
    
    def _create_session_summary(self, session: SessionTiming) -> Dict[str, Any]:
        """Create a summary dictionary for a session."""
        return {
            "session_id": session.session_id,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "total_duration": session.total_duration,
            "total_duration_with_unit": session.total_duration_with_unit,
            "phases": {
                "capture": {
                    "start": session.capture_start,
                    "end": session.capture_end,
                    "duration": session.capture_duration,
                    "duration_with_unit": session.capture_duration_with_unit
                },
                "analysis": {
                    "start": session.analysis_start,
                    "end": session.analysis_end,
                    "duration": session.analysis_duration,
                    "duration_with_unit": session.analysis_duration_with_unit
                },
                "save": {
                    "start": session.save_start,
                    "end": session.save_end,
                    "duration": session.save_duration,
                    "duration_with_unit": session.save_duration_with_unit
                },
                "presentation": {
                    "start": session.presentation_start,
                    "end": session.presentation_end,
                    "duration": session.presentation_duration,
                    "duration_with_unit": session.presentation_duration_with_unit
                }
            },
            "metadata": {
                "image_count": session.image_count,
                "output_directory": session.output_directory,
                "inspection_id": session.inspection_id,
                "sensor_trigger_time": session.sensor_trigger_time
            },
            "measurement_count": len(session.measurements)
        }
    
    def get_operation_statistics(self) -> Dict[str, Any]:
        """Get statistics for all operations."""
        stats = {}
        
        def format_time_with_unit(time_val):
            if time_val < 0.001:
                return f"{time_val * 1000000:.2f} μs"
            elif time_val < 1.0:
                return f"{time_val * 1000:.2f} ms"
            else:
                return f"{time_val:.3f} s"
        
        for operation_name, operation_timing in self.operation_stats.items():
            if operation_timing.total_calls > 0:
                stats[operation_name] = {
                    "total_calls": operation_timing.total_calls,
                    "total_time": operation_timing.total_time,
                    "total_time_with_unit": format_time_with_unit(operation_timing.total_time),
                    "average_time": operation_timing.average_time,
                    "average_time_with_unit": format_time_with_unit(operation_timing.average_time),
                    "min_time": operation_timing.min_time,
                    "min_time_with_unit": format_time_with_unit(operation_timing.min_time),
                    "max_time": operation_timing.max_time,
                    "max_time_with_unit": format_time_with_unit(operation_timing.max_time),
                    "recent_average": operation_timing.get_recent_average(),
                    "recent_average_with_unit": format_time_with_unit(operation_timing.get_recent_average())
                }
        return stats

class TimingReport:
    """Generates comprehensive timing reports."""
    
    def __init__(self, collector: TimingCollector):
        """Initialize timing report generator."""
        self.collector = collector
        logger.info("TimingReport initialized")
    
    def generate_session_report(self, session: SessionTiming, output_dir: str) -> str:
        """Generate a detailed report for a specific session."""
        try:
            # Create report filename from start_time string
            if session.start_time:
                # Parse the start_time string to create timestamp
                start_dt = datetime.strptime(session.start_time, "%Y-%m-%d %H:%M:%S.%f")
                timestamp = start_dt.strftime("%Y%m%d_%H%M%S")
            else:
                # Fallback to current time
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            report_filename = f"timing_report_{session.session_id}_{timestamp}.json"
            report_path = os.path.join(output_dir, report_filename)
            
            # Generate comprehensive report
            report_data = {
                "report_info": {
                    "generated_at": time.time(),
                    "generated_by": "BaslerCamera TimingReport",
                    "version": "1.0"
                },
                "session_summary": self.collector._create_session_summary(session),
                "detailed_measurements": [
                    {
                        "operation_name": m.operation_name,
                        "start_time": m.start_time,
                        "end_time": m.end_time,
                        "duration": m.duration,
                        "duration_with_unit": m.duration_with_unit,
                        "metadata": m.metadata
                    }
                    for m in session.measurements
                ],
                "phase_analysis": self._analyze_phases(session),
                "performance_metrics": self._calculate_performance_metrics(session)
            }
            
            # Write report to file
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Generated timing report: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Error generating timing report: {e}")
            return ""
    
    def _analyze_phases(self, session: SessionTiming) -> Dict[str, Any]:
        """Analyze timing phases for the session."""
        phases = {}
        
        # Calculate phase durations and percentages
        total_duration = session.total_duration or 0
        
        if session.capture_duration:
            phases["capture"] = {
                "duration": session.capture_duration,
                "duration_with_unit": session.capture_duration_with_unit,
                "percentage": (session.capture_duration / total_duration * 100) if total_duration > 0 else 0
            }
        
        if session.analysis_duration:
            phases["analysis"] = {
                "duration": session.analysis_duration,
                "duration_with_unit": session.analysis_duration_with_unit,
                "percentage": (session.analysis_duration / total_duration * 100) if total_duration > 0 else 0
            }
        
        if session.save_duration:
            phases["save"] = {
                "duration": session.save_duration,
                "duration_with_unit": session.save_duration_with_unit,
                "percentage": (session.save_duration / total_duration * 100) if total_duration > 0 else 0
            }
        
        if session.presentation_duration:
            phases["presentation"] = {
                "duration": session.presentation_duration,
                "duration_with_unit": session.presentation_duration_with_unit,
                "percentage": (session.presentation_duration / total_duration * 100) if total_duration > 0 else 0
            }
        
        return phases
    
    def _calculate_performance_metrics(self, session: SessionTiming) -> Dict[str, Any]:
        """Calculate performance metrics for the session."""
        metrics = {}
        
        if session.image_count > 0 and session.total_duration:
            metrics["throughput"] = {
                "images_per_second": session.image_count / session.total_duration,
                "total_images": session.image_count,
                "total_time": session.total_duration,
                "total_time_with_unit": session.total_duration_with_unit
            }
        
        # Calculate analysis efficiency
        analysis_measurements = [m for m in session.measurements if "analysis" in m.operation_name.lower()]
        if analysis_measurements:
            total_analysis_time = sum(m.duration for m in analysis_measurements)
            avg_analysis_time = total_analysis_time / len(analysis_measurements) if analysis_measurements else 0
            
            # Format times with units
            def format_time_with_unit(time_val):
                if time_val < 0.001:
                    return f"{time_val * 1000000:.2f} μs"
                elif time_val < 1.0:
                    return f"{time_val * 1000:.2f} ms"
                else:
                    return f"{time_val:.3f} s"
            
            metrics["analysis_efficiency"] = {
                "total_analysis_time": total_analysis_time,
                "total_analysis_time_with_unit": format_time_with_unit(total_analysis_time),
                "analysis_operations": len(analysis_measurements),
                "average_analysis_time": avg_analysis_time,
                "average_analysis_time_with_unit": format_time_with_unit(avg_analysis_time)
            }
        
        return metrics
    
    def generate_summary_report(self, output_dir: str, session_count: int = 10) -> str:
        """Generate a summary report of recent sessions."""
        try:
            # Get recent sessions
            recent_sessions = self.collector.completed_sessions[-session_count:]
            
            if not recent_sessions:
                logger.warning("No completed sessions available for summary report")
                return ""
            
            # Create summary filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_filename = f"timing_summary_{timestamp}.json"
            summary_path = os.path.join(output_dir, summary_filename)
            
            # Generate summary data
            summary_data = {
                "report_info": {
                    "generated_at": time.time(),
                    "generated_by": "BaslerCamera TimingReport",
                    "version": "1.0",
                    "session_count": len(recent_sessions)
                },
                "session_summaries": [
                    self.collector._create_session_summary(session)
                    for session in recent_sessions
                ],
                "operation_statistics": self.collector.get_operation_statistics(),
                "trend_analysis": self._analyze_trends(recent_sessions)
            }
            
            # Write summary to file
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Generated timing summary: {summary_path}")
            return summary_path
            
        except Exception as e:
            logger.error(f"Error generating timing summary: {e}")
            return ""
    
    def _analyze_trends(self, sessions: List[SessionTiming]) -> Dict[str, Any]:
        """Analyze trends across multiple sessions."""
        if len(sessions) < 2:
            return {"message": "Insufficient data for trend analysis"}
        
        trends = {}
        
        # Analyze total duration trend
        durations = [s.total_duration for s in sessions if s.total_duration]
        if durations:
            trends["total_duration"] = {
                "first": durations[0],
                "last": durations[-1],
                "average": sum(durations) / len(durations),
                "trend": "improving" if durations[-1] < durations[0] else "degrading"
            }
        
        # Analyze image count trend
        image_counts = [s.image_count for s in sessions if s.image_count > 0]
        if image_counts:
            trends["image_count"] = {
                "first": image_counts[0],
                "last": image_counts[-1],
                "average": sum(image_counts) / len(image_counts)
            }
        
        return trends
