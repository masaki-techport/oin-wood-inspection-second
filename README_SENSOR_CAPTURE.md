# Sensor-Based Image Capture System

This document explains the sensor-based image capture system that automatically detects objects passing through sensors and captures images when specific conditions are met.

## Overview

The system uses two sensors (A and B) to detect objects moving in a specific direction. When an object passes through the sensors in the correct sequence, the system automatically saves buffered images. This allows for automated inspection without manual intervention.

![System Overview](https://via.placeholder.com/800x400?text=Sensor+Based+Capture+System)

## How It Works

### Sensor Configuration

The system uses two sensors connected to a Contec DIO-1616LN-ETH device:
- **Sensor A**: Connected to bit 0
- **Sensor B**: Connected to bit 1

### Detection Logic

The system detects object direction based on the sequence of sensor activations:

1. **Left-to-Right Pass (SAVE)**: 
   - Sensor B activates first
   - Then Sensor A activates while B is still active
   - Then Sensor B deactivates (object passing B)
   - Finally, Sensor A deactivates (object completely passed)
   - **Result**: Images are SAVED

2. **Return from Left (DISCARD)**:
   - Sensor A activates first
   - **Result**: Images are DISCARDED

3. **Error Condition (DISCARD)**:
   - Any unexpected sequence
   - **Result**: Images are DISCARDED

### Buffer System

The system continuously captures images from the camera and stores them in a circular buffer:
- Default buffer duration: 30 seconds
- Default capture rate: 10 frames per second
- When a valid object pass is detected, all buffered images are saved to disk

## Testing Scenarios

### 1. Left-to-Right Pass (Normal Operation)

**Expected Behavior**: Images are saved when an object passes from left to right.

**Test Steps**:
1. Start the sensor inspection system
2. Move an object from left to right through both sensors
3. Verify that images are saved to the output directory

**Sensor Sequence**:
```
1. Both sensors OFF
2. Sensor B turns ON (object approaching from left)
3. Sensor A turns ON (object between sensors)
4. Sensor B turns OFF (object passed B)
5. Sensor A turns OFF (object completely passed)
```

### 2. Right-to-Left Pass (Rejection)

**Expected Behavior**: No images are saved when an object passes from right to left.

**Test Steps**:
1. Start the sensor inspection system
2. Move an object from right to left through both sensors
3. Verify that no images are saved

**Sensor Sequence**:
```
1. Both sensors OFF
2. Sensor A turns ON (object approaching from right)
3. System immediately discards buffer
```

### 3. Partial Pass (Rejection)

**Expected Behavior**: No images are saved when an object partially enters the sensor area.

**Test Steps**:
1. Start the sensor inspection system
2. Move an object partially through sensor B, then back out
3. Verify that no images are saved

**Sensor Sequence**:
```
1. Both sensors OFF
2. Sensor B turns ON (object approaching from left)
3. Sensor B turns OFF without Sensor A ever activating
4. System discards buffer
```

## Simulation Mode

For testing without physical sensors, the system includes a simulation mode:

1. Start the system with simulation mode enabled
2. Use the "Test Sequence" button to simulate a left-to-right pass
3. Use the sensor toggle buttons to manually control individual sensors

## Configuration Options

### Sensor Settings

The sensor configuration is stored in `OiN_Direction_Acquisition_Shooting/config/DIO_setting.yaml`:
```yaml
# DIO device configuration
dev_name: "DIO001"
```

### Camera Buffer Settings

Camera buffer settings are configurable in the API:
```yaml
BUFFER_DURATION_SECONDS = 30   # Buffer duration
BUFFER_FPS = 10                 # Buffer capture rate
```

## Troubleshooting

### Sensor Connection Issues

If the sensors are not being detected:

1. Run the diagnostic script: `python test_dio_connection.py`
2. Verify the IP address in Contec Device Utility matches your configuration
3. Try the IP-specific test: `python test_dio_ip_connection.py 192.168.50.203`
4. Check that the DIO device name is correct (default: "DIO001")

### Camera Connection Issues

If the camera is not capturing images:

1. Verify the camera is properly connected
2. Check that the correct camera type is selected (webcam, USB, or Basler)
3. Inspect the logs for any connection errors

### Sensor State Issues

If the sensors are not triggering correctly:

1. Check the sensor status in the UI
2. Verify sensor wiring to the correct input bits
3. Test each sensor individually using the toggle buttons in simulation mode

## API Endpoints

The system provides the following API endpoints:

- `POST /api/sensor-inspection/start`: Start sensor-based inspection
- `POST /api/sensor-inspection/stop`: Stop sensor-based inspection
- `GET /api/sensor-inspection/status`: Get current sensor and buffer status
- `POST /api/sensor-inspection/trigger-test`: Trigger a test sequence (simulation mode only)
- `POST /api/sensor-inspection/toggle-sensor-a`: Toggle sensor A (simulation mode only)
- `POST /api/sensor-inspection/toggle-sensor-b`: Toggle sensor B (simulation mode only)

## Directory Structure

```
src-api/
├── source/
│   ├── camera/                # Camera interfaces
│   │   ├── basler_camera.py   # Basler camera implementation
│   │   └── webcam_camera.py   # Webcam camera implementation
│   ├── camera_buffer.py       # Image buffering system
│   ├── sensor_monitor.py      # Sensor monitoring system
│   ├── sensor_state_machine.py # Sensor state machine logic
│   └── endpoints/
│       └── sensor_inspection.py # API endpoints
├── data/
│   └── images/
│       └── inspection/        # Saved inspection images
└── test_dio_connection.py     # Diagnostic tool
```

## Starting the System

To start the sensor-based inspection system:

1. Run the start script: `start_sensor_inspection.bat`
2. Open the web interface
3. Navigate to the Inspection page
4. Select the camera type
5. Click "検査中" (Inspection) button
6. Monitor the sensor status indicators 