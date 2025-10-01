"""
Text Report Generator for BaslerCamera Performance Monitoring.

This module provides human-readable text-based timing reports with attractive
formatting and organized presentation of timing data.
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from .timing_report import SessionTiming, TimingMeasurement

logger = logging.getLogger('BaslerCamera.TextReport')

class TextReportGenerator:
    """Generates attractive, human-readable text-based timing reports."""
    
    def __init__(self):
        """Initialize text report generator."""
        logger.info("TextReportGenerator initialized")
    
    def generate_session_report(self, session: SessionTiming, output_dir: str) -> str:
        """Generate a detailed text report for a specific session."""
        try:
            # Create report filename
            if session.start_time:
                start_dt = datetime.strptime(session.start_time, "%Y-%m-%d %H:%M:%S.%f")
                timestamp = start_dt.strftime("%Y%m%d_%H%M%S")
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            report_filename = f"timing_report_{session.session_id}_{timestamp}.txt"
            report_path = os.path.join(output_dir, report_filename)
            
            # Generate comprehensive text report
            report_content = self._create_text_report(session)
            
            # Write report to file
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"Generated text timing report: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Error generating text timing report: {e}")
            return ""
    
    def _create_text_report(self, session: SessionTiming) -> str:
        """Create the complete text report content."""
        lines = []
        
        # Header
        lines.extend(self._create_header(session))
        lines.append("")
        
        # Session Summary
        lines.extend(self._create_session_summary(session))
        lines.append("")
        
        # Phase Analysis
        lines.extend(self._create_phase_analysis(session))
        lines.append("")
        
        # Image Processing Details
        lines.extend(self._create_image_processing_details(session))
        lines.append("")
        
        # Operation Timeline
        lines.extend(self._create_operation_timeline(session))
        lines.append("")
        
        # Performance Metrics
        lines.extend(self._create_performance_metrics(session))
        lines.append("")
        
        # Footer
        lines.extend(self._create_footer(session))
        
        return "\n".join(lines)
    
    def _create_header(self, session: SessionTiming) -> List[str]:
        """Create the report header."""
        lines = []
        lines.append("=" * 80)
        lines.append("🔍 BASLER CAMERA TIMING REPORT")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"📋 Session ID: {session.session_id}")
        lines.append(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"📁 Output Directory: {session.output_directory}")
        lines.append(f"🆔 Inspection ID: {session.inspection_id or 'N/A'}")
        lines.append(f"📸 Total Images: {session.image_count}")
        lines.append("")
        return lines
    
    def _create_session_summary(self, session: SessionTiming) -> List[str]:
        """Create session summary section."""
        lines = []
        lines.append("📊 SESSION SUMMARY")
        lines.append("-" * 40)
        lines.append("")
        
        if session.start_time and session.end_time:
            lines.append(f"⏰ Start Time:    {session.start_time}")
            lines.append(f"⏰ End Time:      {session.end_time}")
            lines.append(f"⏱️  Total Duration: {session.total_duration_with_unit}")
        else:
            lines.append("⏰ Start Time:    N/A")
            lines.append("⏰ End Time:      N/A")
            lines.append("⏱️  Total Duration: N/A")
        
        if session.sensor_trigger_time:
            lines.append(f"🎯 Sensor Trigger: {session.sensor_trigger_time}")
        
        lines.append(f"📈 Total Operations: {len(session.measurements)}")
        lines.append("")
        return lines
    
    def _create_phase_analysis(self, session: SessionTiming) -> List[str]:
        """Create phase analysis section."""
        lines = []
        lines.append("🔄 PHASE ANALYSIS")
        lines.append("-" * 40)
        lines.append("")
        
        phases = [
            ("📷 Capture", session.capture_start, session.capture_end, 
             session.capture_duration, session.capture_duration_with_unit),
            ("🔍 Analysis", session.analysis_start, session.analysis_end, 
             session.analysis_duration, session.analysis_duration_with_unit),
            ("💾 Save", session.save_start, session.save_end, 
             session.save_duration, session.save_duration_with_unit),
            ("🎨 Presentation", session.presentation_start, session.presentation_end, 
             session.presentation_duration, session.presentation_duration_with_unit)
        ]
        
        total_duration = session.total_duration or 0
        
        for phase_name, start_time, end_time, duration, duration_with_unit in phases:
            if start_time and end_time:
                percentage = (duration / total_duration * 100) if total_duration > 0 else 0
                lines.append(f"{phase_name:12} │ {start_time} → {end_time}")
                lines.append(f"{'':12} │ Duration: {duration_with_unit} ({percentage:.1f}%)")
                lines.append("")
            else:
                lines.append(f"{phase_name:12} │ Not recorded")
                lines.append("")
        
        return lines
    
    def _create_image_processing_details(self, session: SessionTiming) -> List[str]:
        """Create image processing details section."""
        lines = []
        lines.append("🖼️  IMAGE PROCESSING DETAILS")
        lines.append("-" * 40)
        lines.append("")
        
        # Group measurements by image
        image_operations = self._group_operations_by_image(session.measurements)
        
        if image_operations:
            for image_id, operations in image_operations.items():
                lines.append(f"📸 Image {image_id}:")
                for operation in operations:
                    lines.append(f"   • {operation['name']:20} │ {operation['duration']}")
                lines.append("")
        else:
            lines.append("No image-specific operations recorded")
            lines.append("")
        
        return lines
    
    def _create_operation_timeline(self, session: SessionTiming) -> List[str]:
        """Create operation timeline section."""
        lines = []
        lines.append("⏱️  OPERATION TIMELINE")
        lines.append("-" * 40)
        lines.append("")
        
        # Sort measurements by start time
        sorted_measurements = sorted(session.measurements, 
                                   key=lambda m: m.start_time if m.start_time else "")
        
        # Index memory_inference by image_index for quick matching
        inference_index: Dict[Any, List[TimingMeasurement]] = {}
        for m in sorted_measurements:
            if m.operation_name == "memory_inference":
                img_idx = (m.metadata or {}).get('image_index')
                if img_idx is not None:
                    inference_index.setdefault(img_idx, []).append(m)

        for i, measurement in enumerate(sorted_measurements, 1):
            if measurement.operation_name == "memory_analysis":
                img_idx = (measurement.metadata or {}).get('image_index')
                is_pre = bool((measurement.metadata or {}).get('pre_analyzed', False))
                analysis_type = "pre-analyzed" if is_pre else "runtime"
                lines.append(f"{i:2d}. memory_analysis ({analysis_type})")
                lines.append(f"    Start:  {measurement.start_time}")
                lines.append(f"    End:    {measurement.end_time}")
                lines.append(f"    Duration: {measurement.duration_with_unit}")
                
                # Show breakdown of memory_inference inside analysis (hierarchy)
                inference_dur = None
                if measurement.metadata and 'inference_duration' in measurement.metadata:
                    inference_dur = measurement.metadata['inference_duration']
                else:
                    # Try to match a memory_inference by image_index overlapping in time
                    if img_idx is not None and img_idx in inference_index:
                        for inf in inference_index[img_idx]:
                            # Simple overlap check using strings (times are sorted; best effort)
                            # If present, show first found
                            inference_dur = inf.duration
                            break
                if inference_dur is not None:
                    lines.append(f"    └─ memory_inference: {self._format_duration(inference_dur)}")

                # Add metadata (excluding fields we already displayed)
                if measurement.metadata:
                    md = dict(measurement.metadata)
                    md.pop('inference_duration', None)
                    metadata_str = self._format_metadata(md)
                    if metadata_str:
                        lines.append(f"    Details: {metadata_str}")
                lines.append("")
                continue

            # Default rendering for other operations
            lines.append(f"{i:2d}. {measurement.operation_name}")
            lines.append(f"    Start:  {measurement.start_time}")
            lines.append(f"    End:    {measurement.end_time}")
            lines.append(f"    Duration: {measurement.duration_with_unit}")
            if measurement.metadata:
                metadata_str = self._format_metadata(measurement.metadata)
                if metadata_str:
                    lines.append(f"    Details: {metadata_str}")
            lines.append("")
        
        return lines
    
    def _create_performance_metrics(self, session: SessionTiming) -> List[str]:
        """Create performance metrics section."""
        lines = []
        lines.append("📈 PERFORMANCE METRICS")
        lines.append("-" * 40)
        lines.append("")
        
        # Throughput
        if session.image_count > 0 and session.total_duration:
            throughput = session.image_count / session.total_duration
            lines.append(f"🚀 Throughput: {throughput:.2f} images/second")
            lines.append(f"📊 Total Images: {session.image_count}")
            lines.append(f"⏱️  Total Time: {session.total_duration_with_unit}")
            lines.append("")
        
        # Operation statistics
        operation_stats = self._calculate_operation_statistics(session.measurements)
        if operation_stats:
            lines.append("📋 Operation Statistics:")
            lines.append("")
            for operation_name, stats in operation_stats.items():
                lines.append(f"   {operation_name}:")
                lines.append(f"     • Calls: {stats['calls']}")
                lines.append(f"     • Total Time: {stats['total_time']}")
                lines.append(f"     • Average: {stats['average']}")
                lines.append(f"     • Min: {stats['min']}")
                lines.append(f"     • Max: {stats['max']}")
                lines.append("")
        
        return lines
    
    def _create_footer(self, session: SessionTiming) -> List[str]:
        """Create the report footer."""
        lines = []
        lines.append("=" * 80)
        lines.append("📝 Report generated by BaslerCamera Timing System")
        lines.append(f"🔧 Version: 1.0 | Session: {session.session_id}")
        lines.append("=" * 80)
        return lines
    
    def _group_operations_by_image(self, measurements: List[TimingMeasurement]) -> Dict[str, List[Dict[str, Any]]]:
        """Group operations by image ID."""
        image_operations = {}
        
        for measurement in measurements:
            image_id = self._extract_image_id_from_metadata(measurement.metadata)
            if image_id:
                if image_id not in image_operations:
                    image_operations[image_id] = []
                image_operations[image_id].append({
                    'name': measurement.operation_name,
                    'duration': measurement.duration_with_unit,
                    'start_time': measurement.start_time,
                    'end_time': measurement.end_time
                })
        
        return image_operations
    
    def _extract_image_id_from_metadata(self, metadata: Dict[str, Any]) -> Optional[str]:
        """Extract image ID from measurement metadata."""
        if not metadata:
            return None
        
        # Check for image_path in metadata
        image_path = metadata.get('image_path', '')
        if image_path:
            # Extract No_XXXX pattern from path
            import re
            match = re.search(r'No_(\d{4})', image_path)
            if match:
                return f"No_{match.group(1)}"
        
        # Check for direct image_no in metadata
        image_no = metadata.get('image_no')
        if image_no is not None:
            return f"No_{image_no:04d}"
        
        return None
    
    def _format_metadata(self, metadata: Dict[str, Any]) -> str:
        """Format metadata for display."""
        if not metadata:
            return ""
        
        formatted_items = []
        for key, value in metadata.items():
            if key in ['image_path', 'image_no']:
                continue  # Skip these as they're handled separately
            formatted_items.append(f"{key}={value}")
        
        return ", ".join(formatted_items)
    
    def _calculate_operation_statistics(self, measurements: List[TimingMeasurement]) -> Dict[str, Dict[str, Any]]:
        """Calculate statistics for each operation type."""
        operation_stats = {}
        
        for measurement in measurements:
            op_name = measurement.operation_name
            if op_name not in operation_stats:
                operation_stats[op_name] = {
                    'calls': 0,
                    'total_time': 0.0,
                    'min_time': float('inf'),
                    'max_time': 0.0,
                    'times': []
                }
            
            stats = operation_stats[op_name]
            stats['calls'] += 1
            stats['total_time'] += measurement.duration
            stats['min_time'] = min(stats['min_time'], measurement.duration)
            stats['max_time'] = max(stats['max_time'], measurement.duration)
            stats['times'].append(measurement.duration)
        
        # Format the statistics
        formatted_stats = {}
        for op_name, stats in operation_stats.items():
            if stats['calls'] > 0:
                avg_time = stats['total_time'] / stats['calls']
                formatted_stats[op_name] = {
                    'calls': stats['calls'],
                    'total_time': self._format_duration(stats['total_time']),
                    'average': self._format_duration(avg_time),
                    'min': self._format_duration(stats['min_time']),
                    'max': self._format_duration(stats['max_time'])
                }
        
        return formatted_stats
    
    def _format_duration(self, duration: float) -> str:
        """Format duration with appropriate unit."""
        if duration < 0.001:
            return f"{duration * 1000000:.2f} μs"
        elif duration < 1.0:
            return f"{duration * 1000:.2f} ms"
        else:
            return f"{duration:.3f} s"
