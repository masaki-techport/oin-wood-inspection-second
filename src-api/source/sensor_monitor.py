"""
Sensor Monitor
Based on OiN_Direction_Acquisition_Shooting sensor monitoring logic

This module provides sensor monitoring with support for:
- Real sensor hardware (DIO/SiO)
- Simulation mode for development/testing
"""

import threading
import time
import logging
from typing import Callable, Optional
import random
import sys
import os
import importlib.util
from sensor_state_machine import SensorStateMachine, SensorEvent, SensorResult

# Add OiN directory to path to import their modules
OIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'OiN_Direction_Acquisition_Shooting')
if OIN_DIR not in sys.path:
    sys.path.append(OIN_DIR)
    sys.path.append(os.path.join(OIN_DIR, 'src'))

# Import dynamically for better error handling
logger = logging.getLogger(__name__)

try:
    import cdio
    logger.info("cdio module imported successfully")
except ImportError as e:
    logger.warning(f"Failed to import cdio module: {e}")
    cdio = None


class SensorStatusTracker:
    """
    Tracks sensor status and state transitions for frontend consumption
    This mimics the original OiN display update system
    """
    
    def __init__(self):
        self.current_state = "IDLE"
        self.last_result = None
        self.last_update_time = time.time()
        self.sensor_a_state = False
        self.sensor_b_state = False
        self.clear_requested = False  # Flag to indicate clearing was requested
        self._lock = threading.Lock()
        
    def update_sensor_states(self, sensor_a: bool, sensor_b: bool):
        """Update sensor states"""
        with self._lock:
            self.sensor_a_state = sensor_a
            self.sensor_b_state = sensor_b
            self.last_update_time = time.time()
            
    def update_state_transition(self, result: Optional[str], state: str):
        """Update state transition (called from state machine)"""
        with self._lock:
            self.current_state = state
            if result is not None:
                self.last_result = result
                # Set clear flag if CLEAR_RESULTS was sent
                if result == "CLEAR_RESULTS":
                    self.clear_requested = True
            self.last_update_time = time.time()
            logger.debug(f"Status updated: state={state}, result={result}")
            
    def get_status(self) -> dict:
        """Get current status for frontend"""
        with self._lock:
            return {
                "current_state": self.current_state,
                "last_result": self.last_result,
                "sensor_a": self.sensor_a_state,
                "sensor_b": self.sensor_b_state,
                "last_update_time": self.last_update_time,
                "clear_requested": self.clear_requested
            }
    
    def clear_requested_flag(self):
        """Clear the clear_requested flag after processing"""
        with self._lock:
            self.clear_requested = False


class SensorSimulator:
    """
    Simulates sensor behavior for development/testing with manual control
    """
    
    def __init__(self):
        self.sensor_a_state = False
        self.sensor_b_state = False
        self._running = False
        self._thread = None
        self._callback = None
        self._lock = threading.Lock()  # Thread safety for manual control
        
    def start_simulation(self, callback: Callable[[bool, bool], None]):
        """Start sensor simulation (manual control mode)"""
        self._callback = callback
        self._running = True
        # Send initial state
        if self._callback:
            self._callback(self.sensor_a_state, self.sensor_b_state)
        logger.info("Simulator manual sensor control started")
        
    def stop_simulation(self):
        """Stop sensor simulation"""
        self._running = False
        logger.info("Simulator manual sensor control stopped")
        
    def toggle_sensor_a(self) -> bool:
        """Toggle sensor A state manually and return new state"""
        with self._lock:
            self.sensor_a_state = not self.sensor_a_state
            logger.debug(f"Simulator sensor A toggled to: {self.sensor_a_state}")
            if self._callback and self._running:
                self._callback(self.sensor_a_state, self.sensor_b_state)
            return self.sensor_a_state
            
    def toggle_sensor_b(self) -> bool:
        """Toggle sensor B state manually and return new state"""
        with self._lock:
            self.sensor_b_state = not self.sensor_b_state
            logger.debug(f"Simulator sensor B toggled to: {self.sensor_b_state}")
            if self._callback and self._running:
                self._callback(self.sensor_a_state, self.sensor_b_state)
            return self.sensor_b_state
        
    def trigger_left_to_right_pass(self):
        """Simulate a left-to-right object pass (should trigger SAVE)"""
        logger.debug("Simulator left-to-right pass")
        threading.Thread(target=self._simulate_pass_sequence, daemon=True).start()
        
    def _simulate_pass_sequence(self):
        """Simulate a typical left-to-right pass sequence"""
        with self._lock:
            # Reset sensors
            self.sensor_a_state = False
            self.sensor_b_state = False
            if self._callback and self._running:
                self._callback(False, False)
            
        time.sleep(0.5)
        
        with self._lock:
            # B sensor activates first (object approaching from left)
            self.sensor_b_state = True
            if self._callback and self._running:
                self._callback(self.sensor_a_state, self.sensor_b_state)
                
        time.sleep(0.5)
        
        with self._lock:
            # A sensor activates (object between sensors)
            self.sensor_a_state = True
            if self._callback and self._running:
                self._callback(self.sensor_a_state, self.sensor_b_state)
                
        time.sleep(0.5)
        
        with self._lock:
            # B sensor deactivates (object passed B)
            self.sensor_b_state = False
            if self._callback and self._running:
                self._callback(self.sensor_a_state, self.sensor_b_state)
                
        time.sleep(0.5)
        
        with self._lock:
            # A sensor deactivates (object completely passed) → Should trigger SAVE
            self.sensor_a_state = False
            if self._callback and self._running:
                self._callback(self.sensor_a_state, self.sensor_b_state)


class SensorMonitor:
    """
    Main sensor monitoring class
    Handles both real sensors and simulation
    """
    
    def __init__(self, simulation_mode=True):
        """
        Initialize sensor monitor
        
        Args:
            simulation_mode: If True, use simulation instead of real sensors
        """
        self.simulation_mode = simulation_mode
        self.state_machine = None
        self.monitoring_thread = None
        self.running = False
        self.simulator = SensorSimulator() if simulation_mode else None
        self.status_tracker = SensorStatusTracker()
        
        # Previous sensor states (for edge detection)
        self.prev_sensor_a = False
        self.prev_sensor_b = False
        
        # DIO device connection status and ID
        self.dio_connected = False
        self.dio_id = None
        
        logger.info(f"Initialized SensorMonitor in {'simulation' if simulation_mode else 'real'} mode")
        
    def start_monitoring(self, on_decision: Callable[[Optional[str], str], None]):
        """
        Start sensor monitoring
        
        Args:
            on_decision: Callback function for sensor decisions (camera system)
        """
        if self.running:
            logger.warning("SensorMonitor already running")
            return
            
        # Create combined callback that updates both status tracker and camera system
        def combined_callback(result: Optional[str], state: str):
            # Update status tracker for frontend
            self.status_tracker.update_state_transition(result, state)
            # Call original callback for camera system
            if on_decision:
                on_decision(result, state)
                
        self.state_machine = SensorStateMachine(on_decision=combined_callback)
        self.running = True
        
        if self.simulation_mode:
            # Start simulation
            self.simulator.start_simulation(self._on_sensor_change)
        else:
            # Start real sensor monitoring
            self._initialize_real_sensors()
            
        # Start monitoring thread
        self.monitoring_thread = threading.Thread(target=self._monitor_sensors, daemon=True)
        self.monitoring_thread.start()
        
        logger.info("Monitoring started")
        
    def stop_monitoring(self):
        """Stop sensor monitoring"""
        self.running = False
        
        if self.simulation_mode and self.simulator:
            self.simulator.stop_simulation()
            
        if self.monitoring_thread:
            self.monitoring_thread.join()
            
        logger.info("Monitoring stopped")
        
    def trigger_test_sequence(self):
        """Trigger a test sequence (simulation mode only)"""
        if self.simulation_mode and self.simulator:
            self.simulator.trigger_left_to_right_pass()
        else:
            logger.warning("Test sequence only available in simulation mode")
            
    def toggle_sensor_a(self) -> bool:
        """Toggle sensor A state manually (simulation mode only)"""
        if self.simulation_mode and self.simulator:
            return self.simulator.toggle_sensor_a()
        else:
            logger.warning("Manual control only available in simulation mode")
            return False
            
    def toggle_sensor_b(self) -> bool:
        """Toggle sensor B state manually (simulation mode only)"""
        if self.simulation_mode and self.simulator:
            return self.simulator.toggle_sensor_b()
        else:
            logger.warning("Manual control only available in simulation mode")
            return False
            
    def get_sensor_states(self) -> tuple[bool, bool]:
        """Get current sensor states (A, B)"""
        if self.simulation_mode and self.simulator:
            return (self.simulator.sensor_a_state, self.simulator.sensor_b_state)
        else:
            return self._read_real_sensors()
            
    def get_current_state(self) -> str:
        """Get current state machine state"""
        return self.status_tracker.get_status()["current_state"]
        
    def get_detailed_status(self) -> dict:
        """Get detailed status for frontend including all state information"""
        status = self.status_tracker.get_status()
        sensor_a, sensor_b = self.get_sensor_states()
        
        return {
            "current_state": status["current_state"],
            "last_result": status["last_result"],
            "sensor_a": sensor_a,
            "sensor_b": sensor_b,
            "last_update_time": status["last_update_time"],
            "simulation_mode": self.simulation_mode,
            "clear_requested": status.get("clear_requested", False)
        }
        
    def _on_sensor_change(self, sensor_a: bool, sensor_b: bool):
        """Handle sensor state changes"""
        logger.debug(f"Sensor change: A={sensor_a}, B={sensor_b} (prev: A={self.prev_sensor_a}, B={self.prev_sensor_b})")
        
        # Update status tracker with current sensor states
        self.status_tracker.update_sensor_states(sensor_a, sensor_b)
        
        # Detect edges and send events to state machine
        if sensor_a != self.prev_sensor_a:
            event = SensorEvent.A_ON if sensor_a else SensorEvent.A_OFF
            logger.debug(f"Sensor A edge: {event}")
            if self.state_machine:
                result = self.state_machine.on_event(event)
                logger.debug(f"State machine result for A event: {result}")
            self.prev_sensor_a = sensor_a
            
        if sensor_b != self.prev_sensor_b:
            event = SensorEvent.B_ON if sensor_b else SensorEvent.B_OFF
            logger.debug(f"Sensor B edge: {event}")
            if self.state_machine:
                result = self.state_machine.on_event(event)
                logger.debug(f"State machine result for B event: {result}")
            self.prev_sensor_b = sensor_b
            
    def _monitor_sensors(self):
        """Main sensor monitoring loop"""
        while self.running:
            if not self.simulation_mode:
                # Read real sensors and detect changes
                sensor_a, sensor_b = self._read_real_sensors()
                if sensor_a is not None and sensor_b is not None:  # Only process valid readings
                    self._on_sensor_change(sensor_a, sensor_b)
                
            time.sleep(0.1)  # 50Hz monitoring rate
            
    def _initialize_real_sensors(self):
        """Initialize real sensor hardware (DIO/SiO)"""
        if cdio is None:
            logger.warning("cdio module not available, falling back to simulation mode")
            self.simulation_mode = True
            self.simulator = SensorSimulator()
            return
            
        try:
            logger.info("Attempting to initialize real sensors")
            
            # First, try to load settings from project config
            from __init__ import DIO_CONFIG_FILE
            dev_name = "DIO000"  # Default name
            
            try:
                import yaml
                with open(file=DIO_CONFIG_FILE, mode='r', encoding='utf-8') as file:
                    DIO_params = yaml.safe_load(file)
                    dev_name = DIO_params.get('dev_name', dev_name)
                logger.info(f"Using device name from config: {dev_name}")
            except Exception as e:
                logger.warning(f"Failed to load DIO config, using default device name: {e}")
            
            # Initialize DIO device
            import ctypes
            self.dio_id = ctypes.c_short()
            err_str = ctypes.create_string_buffer(256)
            
            # Try to initialize with specified device name
            logger.info(f"Initializing DIO with device name: {dev_name}")
            lret = cdio.DioInit(dev_name.encode(), ctypes.byref(self.dio_id))
            
            if lret != 0:  # DIO_ERR_SUCCESS
                logger.warning(f"Failed to initialize with {dev_name}, trying default")
                default_name = "DIO000"
                lret = cdio.DioInit(default_name.encode(), ctypes.byref(self.dio_id))
                
            if lret != 0:  # DIO_ERR_SUCCESS
                cdio.DioGetErrorString(lret, err_str)
                error_msg = err_str.value.decode('sjis') if hasattr(err_str.value, 'decode') else str(err_str.value)
                logger.error(f"DioInit error: {lret}, {error_msg}")
                logger.error("Failed to initialize DIO, falling back to simulation mode")
                self.simulation_mode = True
                self.simulator = SensorSimulator()
            else:
                logger.info(f"Successfully initialized DIO device, ID: {self.dio_id.value}")
                self.dio_connected = True
                
        except Exception as e:
            logger.exception(f"Failed to initialize real sensors: {e}")
            logger.warning("Falling back to simulation mode")
            self.simulation_mode = True
            self.simulator = SensorSimulator()
            
    def _read_real_sensors(self) -> tuple[bool, bool]:
        """Read real sensor states"""
        if not self.dio_connected or cdio is None:
            logger.warning("DIO not connected, cannot read sensors")
            return None, None
            
        try:
            import ctypes
            io_data_a = ctypes.c_ubyte()
            io_data_b = ctypes.c_ubyte()
            
            # Read bit 0 (sensor A)
            bit_a = ctypes.c_short(0)  # Bit 0 for sensor A
            lret_a = cdio.DioInpBit(self.dio_id, bit_a, ctypes.byref(io_data_a))
            
            # Read bit 1 (sensor B)
            bit_b = ctypes.c_short(1)  # Bit 1 for sensor B
            lret_b = cdio.DioInpBit(self.dio_id, bit_b, ctypes.byref(io_data_b))
            
            if lret_a == 0 and lret_b == 0:  # DIO_ERR_SUCCESS
                sensor_a = bool(io_data_a.value)
                sensor_b = bool(io_data_b.value)
                return sensor_a, sensor_b
            else:
                err_str = ctypes.create_string_buffer(256)
                if lret_a != 0:
                    cdio.DioGetErrorString(lret_a, err_str)
                    logger.error(f"Error reading sensor A: {err_str.value.decode('sjis')}")
                if lret_b != 0:
                    cdio.DioGetErrorString(lret_b, err_str)
                    logger.error(f"Error reading sensor B: {err_str.value.decode('sjis')}")
                return None, None
                
        except Exception as e:
            logger.exception(f"Error reading sensors: {e}")
            return None, None 