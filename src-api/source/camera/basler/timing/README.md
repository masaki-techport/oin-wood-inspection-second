# BaslerCamera Timing Report System

## Overview

The BaslerCamera Timing Report System provides comprehensive performance monitoring and timing analysis for all major operations in the Basler camera system. It tracks timing for image capture, analysis, saving, and presentation image selection processes.

## Features

- **Comprehensive Timing Tracking**: Monitors all major operations including frame capture, image analysis, database operations, and presentation selection
- **Session Management**: Tracks complete processing sessions from sensor trigger to final report generation
- **Phase Analysis**: Breaks down processing into logical phases (capture, analysis, save, presentation)
- **Performance Metrics**: Calculates throughput, efficiency, and trend analysis
- **Dual Report Formats**: Generates both JSON and human-readable text reports with complete timing data and analysis
- **Image ID Tracking**: Associates timing measurements with specific image IDs (No_XXXX pattern)
- **Attractive Formatting**: Text reports include emojis, organized sections, and easy-to-read formatting
- **Thread-Safe**: Designed for multi-threaded camera operations
- **Memory Efficient**: Uses configurable limits and cleanup mechanisms

## Architecture

### Core Components

1. **TimingCollector**: Main class for collecting and managing timing measurements
2. **TimingReport**: Generates comprehensive JSON reports from collected timing data
3. **TextReportGenerator**: Generates human-readable text reports with attractive formatting
4. **SessionTiming**: Represents a complete processing session
5. **TimingMeasurement**: Individual timing measurement for specific operations
6. **OperationTiming**: Statistics for repeated operations

### Integration Points

The timing system is integrated into the following components:

- **Frame Capture**: `grab_loop.py` - Tracks frame grab and buffer operations
- **Image Analysis**: `image_analyzer.py` - Tracks inference and database operations
- **Memory Analysis**: `analysis_processor.py` - Tracks real-time analysis
- **Image Saving**: `event_processor.py` - Tracks save operations
- **Presentation Selection**: `memory_presentation_processor.py` - Tracks selection logic
- **Camera Buffer**: `camera_buffer.py` - Manages session lifecycle

## Usage

### Basic Usage

```python
from camera.basler.timing import TimingCollector, TimingReport

# Create timing collector
collector = TimingCollector()

# Start a session
session = collector.start_session("session_001", sensor_trigger_time=time.time())

# Mark phases
collector.mark_phase_start("capture")
# ... capture operations ...
collector.mark_phase_end("capture")

# Add detailed measurements
measurement_id = collector.start_measurement("image_analysis", {"image_path": "test.jpg"})
# ... analysis operations ...
collector.end_measurement("image_analysis", measurement_id)

# Set session metadata
collector.set_session_metadata(
    image_count=10,
    output_directory="/output/path",
    inspection_id=12345
)

# Finalize session
completed_session = collector.finalize_current_session()

# Generate report
timing_report = TimingReport(collector)
report_path = timing_report.generate_session_report(completed_session, "/output/path")
```

### Integration with BaslerCamera

The timing system is automatically integrated into the BaslerCamera class:

```python
# Timing collector is automatically initialized
camera = BaslerCamera()
assert camera.timing_collector is not None

# Sessions are automatically managed during pass_L_to_R events
# Reports are automatically generated in the save directory
```

## Report Structure

### Session Report

Each session generates a comprehensive JSON report containing:

```json
{
  "report_info": {
    "generated_at": 1695628800.123,
    "generated_by": "BaslerCamera TimingReport",
    "version": "1.0"
  },
  "session_summary": {
    "session_id": "pass_L_to_R_1695628800",
    "start_time": 1695628800.000,
    "end_time": 1695628805.123,
    "total_duration": 5.123,
    "phases": {
      "capture": {
        "start": 1695628800.000,
        "end": 1695628801.000,
        "duration": 1.000
      },
      "analysis": {
        "start": 1695628801.000,
        "end": 1695628803.000,
        "duration": 2.000
      },
      "save": {
        "start": 1695628803.000,
        "end": 1695628804.000,
        "duration": 1.000
      },
      "presentation": {
        "start": 1695628804.000,
        "end": 1695628805.123,
        "duration": 1.123
      }
    },
    "metadata": {
      "image_count": 10,
      "output_directory": "/output/path",
      "inspection_id": 12345,
      "sensor_trigger_time": 1695628800.000
    }
  },
  "detailed_measurements": [
    {
      "operation_name": "frame_grab",
      "start_time": 1695628800.100,
      "end_time": 1695628800.150,
      "duration": 0.050,
      "metadata": {
        "timeout_ms": 250,
        "frame_index": 0
      }
    }
  ],
  "phase_analysis": {
    "capture": {
      "duration": 1.000,
      "percentage": 19.5
    },
    "analysis": {
      "duration": 2.000,
      "percentage": 39.0
    }
  },
  "performance_metrics": {
    "throughput": {
      "images_per_second": 1.95,
      "total_images": 10,
      "total_time": 5.123
    },
    "analysis_efficiency": {
      "total_analysis_time": 2.000,
      "analysis_operations": 10,
      "average_analysis_time": 0.200
    }
  }
}
```

### Summary Report

Summary reports aggregate data from multiple sessions:

```json
{
  "report_info": {
    "generated_at": 1695628800.123,
    "session_count": 10
  },
  "session_summaries": [...],
  "operation_statistics": {
    "frame_grab": {
      "total_calls": 100,
      "total_time": 5.000,
      "average_time": 0.050,
      "min_time": 0.030,
      "max_time": 0.080,
      "recent_average": 0.045
    }
  },
  "trend_analysis": {
    "total_duration": {
      "first": 5.500,
      "last": 4.800,
      "average": 5.100,
      "trend": "improving"
    }
  }
}
```

## Configuration

### TimingCollector Configuration

```python
collector = TimingCollector(
    max_sessions=50,  # Maximum number of completed sessions to keep
)
```

### Performance Settings

The timing system is designed to have minimal performance impact:

- **Non-blocking**: All timing operations are non-blocking
- **Memory efficient**: Configurable limits prevent memory leaks
- **Thread-safe**: Uses RLock for thread safety
- **Minimal overhead**: Timing operations add <1ms overhead per measurement

## File Locations

### Generated Reports

Timing reports are automatically saved to the same directory as saved images:

```
/output_directory/
├── No_0001.bmp
├── No_0002.bmp
├── ...
├── timing_report_pass_L_to_R_1695628800_20250925_091949.json
├── timing_report_pass_L_to_R_1695628800_20250925_091949.txt
└── timing_summary_20250925_091950.json
```

### Report Naming Convention

- **JSON Session Reports**: `timing_report_{session_id}_{timestamp}.json`
- **Text Session Reports**: `timing_report_{session_id}_{timestamp}.txt`
- **Summary Reports**: `timing_summary_{timestamp}.json`

### Text Report Format

The text reports provide human-readable output with:

- **Header Section**: Session information, inspection ID, and metadata
- **Session Summary**: Start/end times, total duration, and operation counts
- **Phase Analysis**: Detailed breakdown of capture, analysis, save, and presentation phases
- **Image Processing Details**: Individual image operations with specific image IDs (No_XXXX)
- **Operation Timeline**: Chronological list of all operations with timestamps
- **Performance Metrics**: Throughput, efficiency, and operation statistics
- **Attractive Formatting**: Emojis, organized sections, and clear visual hierarchy

## Monitoring and Debugging

### Logging

The timing system uses the `BaslerCamera.TimingReport` logger:

```python
import logging
logger = logging.getLogger('BaslerCamera.TimingReport')
```

### Performance Monitoring

Access timing statistics programmatically:

```python
# Get current session summary
summary = camera.timing_collector.get_session_summary()

# Get operation statistics
stats = camera.timing_collector.get_operation_statistics()

# Get current session
current_session = camera.timing_collector.get_current_session()
```

## Error Handling

The timing system is designed to be robust:

- **Graceful degradation**: If timing fails, camera operations continue normally
- **Error logging**: All timing errors are logged but don't affect main operations
- **Fallback mechanisms**: Missing timing data doesn't break report generation
- **Resource cleanup**: Automatic cleanup prevents memory leaks

## Testing

The timing system includes comprehensive tests covering:

- TimingCollector functionality
- Report generation
- Operation statistics
- Summary reports
- Camera integration
- Error handling

Run tests with:

```bash
cd src-api
python test_timing_report.py
```

## Performance Impact

The timing system is designed for minimal performance impact:

- **Overhead**: <1ms per measurement
- **Memory**: <1MB for typical sessions
- **CPU**: <0.1% additional CPU usage
- **Storage**: ~2-5KB per report

## Future Enhancements

Potential future improvements:

1. **Real-time monitoring**: Web dashboard for live timing data
2. **Alerting**: Performance threshold alerts
3. **Historical analysis**: Long-term trend analysis
4. **Export formats**: CSV, Excel export options
5. **Custom metrics**: User-defined performance metrics
6. **Integration**: Integration with external monitoring systems

## Troubleshooting

### Common Issues

1. **No timing reports generated**
   - Check if timing_collector is initialized
   - Verify pass_L_to_R events are triggering
   - Check file permissions for output directory

2. **Missing timing data**
   - Ensure timing measurements are properly started/ended
   - Check for exceptions in timing code
   - Verify session lifecycle is complete

3. **Performance impact**
   - Reduce max_sessions limit
   - Disable detailed measurements for high-frequency operations
   - Check for memory leaks in long-running sessions

### Debug Mode

Enable debug logging for detailed timing information:

```python
import logging
logging.getLogger('BaslerCamera.TimingReport').setLevel(logging.DEBUG)
```

