import threading
import time
import random
from typing import Dict, List, Optional
from datetime import datetime
from real_temperature_sensor import RealTemperatureSensor


class TemperatureStation:
    """
    Represents a temperature detection station that can run independently.
    Each station has its own thread and can be started/stopped independently.
    Now supports reading from both temperature channels.
    """
    
    def __init__(self, station_id: int, name: str, threshold_difference: float = 10.0, 
                 use_real_sensor: bool = False, com_port: str = 'COM4'):
        self.station_id = station_id
        self.name = name
        self.threshold_difference = threshold_difference
        self.use_real_sensor = use_real_sensor
        self.is_running = False
        self.thread = None
        self.current_temperatures = {'channel1': None, 'channel2': None}
        self.temperature_history = []
        self.lock = threading.Lock()
        
        # Initialize real sensor if requested
        self.real_sensor = None
        self.sensor_connection_error = None
        if self.use_real_sensor:
            self.real_sensor = RealTemperatureSensor(com_port=com_port)
            if not self.real_sensor.setup_sensor():
                self.sensor_connection_error = self.real_sensor.last_error
        
    def start_detection(self):
        """Start the temperature detection for this station."""
        if not self.is_running:
            # Clear previous data when starting fresh
            with self.lock:
                self.temperature_history.clear()
                self.current_temperatures = {'channel1': None, 'channel2': None}
            
            self.is_running = True
            self.thread = threading.Thread(target=self._detection_loop, daemon=True)
            self.thread.start()
            
    def stop_detection(self):
        """Stop the temperature detection for this station."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1)
        
        # Disconnect real sensor if it exists
        if self.real_sensor:
            self.real_sensor.disconnect()
            
    def _detection_loop(self):
        """
        Main detection loop that runs in a separate thread.
        Uses real sensor if configured, otherwise simulates temperature detection.
        Now reads from both channels.
        """
        while self.is_running:
            temperatures = {'channel1': None, 'channel2': None}
            
            if self.use_real_sensor and self.real_sensor:
                # Read from both channels using real sensor
                temperatures = self.real_sensor.read_all_temperatures()
                
                # Update sensor connection status
                sensor_status = self.real_sensor.get_status()
                if not sensor_status['is_connected']:
                    self.sensor_connection_error = sensor_status['last_error']
                else:
                    self.sensor_connection_error = None
                    
                # If sensor reading failed, fall back to simulation for demo purposes
                if temperatures['channel1'] is None or temperatures['channel2'] is None:
                    temperatures = self._get_simulated_temperatures()
            else:
                # Simulate temperature detection for both channels
                temperatures = self._get_simulated_temperatures()
            
            # Update temperature history
            if temperatures['channel1'] is not None and temperatures['channel2'] is not None:
                with self.lock:
                    self.current_temperatures = {
                        'channel1': round(temperatures['channel1'], 2),
                        'channel2': round(temperatures['channel2'], 2)
                    }
                    timestamp = datetime.now()
                    
                    # Keep only last 100 readings to prevent memory issues
                    self.temperature_history.append({
                        'timestamp': timestamp,
                        'channel1_temperature': self.current_temperatures['channel1'],
                        'channel2_temperature': self.current_temperatures['channel2']
                    })
                    if len(self.temperature_history) > 100:
                        self.temperature_history.pop(0)
            
            # Wait for 1 second before next reading
            time.sleep(1)
    
    def _get_simulated_temperatures(self) -> Dict[str, float]:
        """Generate simulated temperatures for both channels for demo/fallback purposes."""
        base_temp1 = 5.0  # Channel 1 base temperature
        base_temp2 = 24.0  # Channel 2 base temperature (slightly different)
        return {
            'channel1': base_temp1 + random.uniform(-5.0, 8.0),  # 17-30°C range
            'channel2': base_temp2 + random.uniform(-4.0, 7.0)   # 20-31°C range
        }
            
    def get_current_temperatures(self):
        """Get the current temperature readings from both channels."""
        with self.lock:
            return self.current_temperatures.copy()
            
    def get_temperature_history(self):
        """Get the temperature history for this station."""
        with self.lock:
            return self.temperature_history.copy()
            
    def get_status(self):
        """Get the current status of the station."""
        current_temps = self.get_current_temperatures()
        
        # Get sensor status if using real sensor
        sensor_status = {}
        if self.use_real_sensor and self.real_sensor:
            sensor_status = self.real_sensor.get_status()
        
        # Check if temperature difference is below threshold (abnormal if channel2 - channel1 < threshold)
        is_abnormal = False
        temperature_difference = None
        if current_temps['channel1'] is not None and current_temps['channel2'] is not None:
            temperature_difference = current_temps['channel2'] - current_temps['channel1']
            is_abnormal = temperature_difference < self.threshold_difference
        
        return {
            'station_id': self.station_id,
            'name': self.name,
            'is_running': self.is_running,
            'current_temperatures': current_temps,
            'readings_count': len(self.temperature_history),
            'threshold_difference': self.threshold_difference,
            'current_difference': temperature_difference,
            'is_abnormal': is_abnormal,
            'use_real_sensor': self.use_real_sensor,
            'sensor_connected': sensor_status.get('is_connected', False) if self.use_real_sensor else None,
            'sensor_error': self.sensor_connection_error
        }
    
    def export_to_csv(self):
        """Export temperature history to CSV format."""
        import io
        import csv
        from datetime import datetime
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Timestamp', 'Channel1_Temperature_Celsius', 'Channel2_Temperature_Celsius', 'Station_Name', 'Station_ID'])
        
        # Write data
        with self.lock:
            for reading in self.temperature_history:
                writer.writerow([
                    reading['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    reading['channel1_temperature'],
                    reading['channel2_temperature'],
                    self.name,
                    self.station_id
                ])
        
        return output.getvalue() 