"""
Sensor State Machine
Based on OiN_Direction_Acquisition_Shooting sensor_pass_detector.py

This module implements the sensor logic for detecting object direction
using two sensors (A and B) and triggering image capture accordingly.
"""

import threading
import time
from typing import Callable, Optional, List
from enum import Enum


class SensorEvent(Enum):
    """Sensor event types"""
    A_ON = "A_ON"
    A_OFF = "A_OFF"
    B_ON = "B_ON"
    B_OFF = "B_OFF"


class SensorState(Enum):
    """Sensor state machine states"""
    IDLE = "IDLE"
    A_ACTIVE = "A_ACTIVE"
    B_ACTIVE = "B_ACTIVE"
    A_THEN_B = "A_THEN_B"
    B_THEN_A = "B_THEN_A"
    A_ONLY = "A_ONLY"
    B_ONLY = "B_ONLY"
    A_ONLY_RETURN = "A_ONLY_return"
    B_ONLY_RETURN = "B_ONLY_return"


class SensorResult(Enum):
    """Sensor detection results"""
    PASS_L_TO_R = "pass_L_to_R"        # Object passed left to right → SAVE
    PASS_R_TO_L = "pass_R_to_L"        # Object passed right to left
    RETURN_FROM_L = "return_from_L"     # Object returned from left → DISCARD
    RETURN_FROM_R = "return_from_R"     # Object returned from right → DISCARD
    ERROR = "error"                     # Error condition → DISCARD
    TIMEOUT = "timeout_or_manual_reset" # Timeout → DISCARD


class SensorStateMachine:
    """
    Sensor state machine for detecting object direction
    Based on OiN_Direction_Acquisition_Shooting logic
    """
    
    TIMEOUT_SEC = 30.0  # Operation timeout (seconds)
    
    def __init__(self, on_decision: Optional[Callable[[Optional[str], str], None]] = None):
        """
        Initialize sensor state machine
        
        Args:
            on_decision: Callback function called when decision is made
                        (result: str or None, state: str)
        """
        self.state = SensorState.IDLE
        self.last_event_time = time.time()
        self.sequence: List[SensorEvent] = []
        self.result: Optional[SensorResult] = None
        self.on_decision = on_decision
        self._lock = threading.Lock()
        self.debug_mode = True  # Enable detailed logging
        
        # Send initial state to callback
        if self.on_decision:
            self._safe_callback(None, self.state.value)
            print(f"[SENSOR_SM] Initialized: state={self.state.value}")
    
    def reset(self):
        """Reset state machine to initial state"""
        if self.result is not None and self.on_decision:
            print(f"[SENSOR_SM] 🔴 Calling callback with result={self.result.value}, state={self.state.value}")
            self._safe_callback(self.result.value, self.state.value)
        
        # Reset to initial state
        old_state = self.state
        self.state = SensorState.IDLE
        self.last_event_time = time.time()
        self.sequence = []
        self.result = None
        print(f"[SENSOR_SM] Reset: {old_state.value} → {self.state.value}")
        
        # Send IDLE state callback after reset
        if self.on_decision:
            self._safe_callback(None, self.state.value)
    
    def on_event(self, event: SensorEvent) -> Optional[SensorResult]:
        """
        Process sensor event and return result if any
        
        Args:
            event: Sensor event (A_ON, A_OFF, B_ON, B_OFF)
            
        Returns:
            SensorResult if decision is made, None otherwise
        """
        with self._lock:
            now = time.time()
            old_state = self.state
            
            # Timeout check
            if now - self.last_event_time > self.TIMEOUT_SEC:
                print(f"[SENSOR_SM] Timeout detected")
                self.result = SensorResult.ERROR
                self.reset()
                return SensorResult.ERROR
            
            self.last_event_time = now
            self.sequence.append(event)
            
            print(f"[SENSOR_SM] Event: {event.value}, State: {self.state.value}")
            
            # State transition logic
            if self.state == SensorState.IDLE:
                if event == SensorEvent.A_ON:
                    self.state = SensorState.A_ACTIVE
                    self._state_changed(old_state)
                elif event == SensorEvent.B_ON:
                    self.state = SensorState.B_ACTIVE
                    self._state_changed(old_state)
                        
            elif self.state == SensorState.A_ACTIVE:
                if event == SensorEvent.B_ON:
                    self.state = SensorState.A_THEN_B
                    self._state_changed(old_state)
                elif event == SensorEvent.A_OFF:
                    self.result = SensorResult.RETURN_FROM_R
                    self.reset()
                    return SensorResult.RETURN_FROM_R
                elif event == SensorEvent.B_OFF:
                    self.result = SensorResult.ERROR
                    self.reset()
                    return SensorResult.ERROR
                    
            elif self.state == SensorState.B_ACTIVE:
                if event == SensorEvent.A_ON:
                    self.state = SensorState.B_THEN_A
                    self._state_changed(old_state)
                elif event == SensorEvent.B_OFF:
                    self.result = SensorResult.RETURN_FROM_L
                    self.reset()
                    return SensorResult.RETURN_FROM_L
                elif event == SensorEvent.A_OFF:
                    self.result = SensorResult.ERROR
                    self.reset()
                    return SensorResult.ERROR
                    
            elif self.state == SensorState.A_THEN_B:
                if event == SensorEvent.A_OFF:
                    self.state = SensorState.B_ONLY
                    self._state_changed(old_state)
                elif event == SensorEvent.B_OFF:
                    self.state = SensorState.A_ONLY_RETURN
                    self._state_changed(old_state)
                        
            elif self.state == SensorState.B_THEN_A:
                if event == SensorEvent.B_OFF:
                    self.state = SensorState.A_ONLY
                    self._state_changed(old_state)
                elif event == SensorEvent.A_OFF:
                    self.state = SensorState.B_ONLY_RETURN
                    self._state_changed(old_state)
                        
            elif self.state == SensorState.A_ONLY:
                if event == SensorEvent.A_OFF:
                    # This is the key condition for saving images (left to right pass)
                    self.result = SensorResult.PASS_L_TO_R
                    print(f"[SENSOR_SM] 🔴 SAVE CONDITION DETECTED: {self.result.value}")
                    self.reset()
                    return SensorResult.PASS_L_TO_R
                elif event == SensorEvent.B_ON:
                    self.result = SensorResult.RETURN_FROM_L
                    self.reset()
                    return SensorResult.RETURN_FROM_L
                    
            elif self.state == SensorState.B_ONLY:
                if event == SensorEvent.B_OFF:
                    self.result = SensorResult.PASS_R_TO_L
                    self.reset()
                    return SensorResult.PASS_R_TO_L
                elif event == SensorEvent.A_ON:
                    self.result = SensorResult.RETURN_FROM_R
                    self.reset()
                    return SensorResult.RETURN_FROM_R
                    
            elif self.state == SensorState.A_ONLY_RETURN:
                if event == SensorEvent.A_OFF:
                    self.result = SensorResult.RETURN_FROM_R
                    self.reset()
                    return SensorResult.RETURN_FROM_R
                elif event == SensorEvent.B_ON:
                    self.result = SensorResult.ERROR
                    self.reset()
                    return SensorResult.ERROR
                    
            elif self.state == SensorState.B_ONLY_RETURN:
                if event == SensorEvent.B_OFF:
                    self.result = SensorResult.RETURN_FROM_L
                    self.reset()
                    return SensorResult.RETURN_FROM_L
                elif event == SensorEvent.A_ON:
                    self.result = SensorResult.ERROR
                    self.reset()
                    return SensorResult.ERROR
            
            # Check for both sensors OFF (reset condition)
            if self.state != SensorState.IDLE and len(self.sequence) >= 2:
                last_two = self.sequence[-2:]
                if (SensorEvent.A_OFF in last_two and SensorEvent.B_OFF in last_two and
                    last_two[0] != last_two[1]):
                    self.result = SensorResult.TIMEOUT
                    self.reset()
                    return SensorResult.TIMEOUT
            
            # Error if too many events
            if len(self.sequence) > 5:
                self.result = SensorResult.ERROR
                self.reset()
                return SensorResult.ERROR
            
            return None
    
    def _state_changed(self, old_state: SensorState):
        """Handle state change and call callback"""
        if self.on_decision and old_state != self.state:
            print(f"[SENSOR_SM] State changed: {old_state.value} → {self.state.value}")
            self._safe_callback(None, self.state.value)
            
    def _safe_callback(self, result: Optional[str], state: str):
        """Thread-safe callback invocation with error handling"""
        if not self.on_decision:
            return
            
        try:
            # Create a local copy of the callback to avoid race conditions
            callback_fn = self.on_decision
            if callback_fn:
                # For critical results (PASS_L_TO_R), wait for callback completion
                # to prevent race conditions with subsequent captures
                if result == "pass_L_to_R":
                    print(f"[SENSOR_SM] 🔴 Executing synchronous callback for critical result: {result}")
                    self._do_callback(callback_fn, result, state)
                else:
                    # Call in a separate thread for non-critical callbacks
                    callback_thread = threading.Thread(
                        target=lambda: self._do_callback(callback_fn, result, state),
                        daemon=True
                    )
                    callback_thread.start()
        except Exception as e:
            print(f"[SENSOR_SM] Error preparing callback: {e}")
    
    def _do_callback(self, callback_fn, result: Optional[str], state: str):
        """Execute callback in a separate thread with error handling"""
        try:
            print(f"[SENSOR_SM] 🔴 Executing callback with result={result}, state={state}")
            start_time = time.time()
            callback_fn(result, state)
            elapsed = (time.time() - start_time) * 1000
            print(f"[SENSOR_SM] 🔴 Callback completed in {elapsed:.1f}ms")
            if elapsed > 100:  # Log slow callbacks (>100ms)
                print(f"[SENSOR_SM] WARNING: Slow callback ({elapsed:.1f}ms) for state={state}, result={result}")
        except Exception as e:
            print(f"[SENSOR_SM] Callback error: {e}")
            import traceback
            traceback.print_exc()
            
    def get_current_state(self) -> str:
        """Get current state as string"""
        return self.state.value
    
    def get_sequence(self) -> List[str]:
        """Get event sequence as string list"""
        return [event.value for event in self.sequence]
        
    def process_sensor_states(self, sensor_a: bool, sensor_b: bool, prev_sensor_a: bool, prev_sensor_b: bool):
        """
        Process sensor state changes and generate appropriate events
        
        Args:
            sensor_a: Current state of sensor A
            sensor_b: Current state of sensor B
            prev_sensor_a: Previous state of sensor A
            prev_sensor_b: Previous state of sensor B
            
        Returns:
            tuple: (result, changed) - result of processing, whether states changed
        """
        changed = False
        result = None
        
        # Check for sensor A state change
        if sensor_a != prev_sensor_a:
            event = SensorEvent.A_ON if sensor_a else SensorEvent.A_OFF
            result = self.on_event(event)
            changed = True
            
        # Check for sensor B state change
        if sensor_b != prev_sensor_b:
            event = SensorEvent.B_ON if sensor_b else SensorEvent.B_OFF
            result = self.on_event(event)
            changed = True
            
        return result, changed 