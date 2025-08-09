import minimalmodbus
import time
from datetime import datetime
from typing import Optional, Dict, Any
import logging

class RealTemperatureSensor:
    """
    Real temperature sensor class that interfaces with Modbus RTU sensor.
    Supports reading from multiple channels (Channel 1 and Channel 2).
    """
    
    def __init__(self, com_port: str = 'COM4', slave_address: int = 1, 
                 baudrate: int = 9600, timeout: float = 1.0):
        """
        Initialize the real temperature sensor.
        
        Args:
            com_port: Serial port for communication (e.g., 'COM4' on Windows, '/dev/ttyUSB0' on Linux)
            slave_address: Modbus slave address
            baudrate: Communication baud rate
            timeout: Communication timeout in seconds
        """
        self.com_port = com_port
        self.slave_address = slave_address
        self.baudrate = baudrate
        self.timeout = timeout
        self.instrument = None
        self.is_connected = False
        self.last_error = None
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def setup_sensor(self) -> bool:
        """
        Initialize Modbus RTU instrument with proper settings.
        
        Returns:
            bool: True if setup successful, False otherwise
        """
        try:
            # Initialize Modbus RTU instrument
            self.instrument = minimalmodbus.Instrument(self.com_port, self.slave_address)
            
            # Serial settings
            self.instrument.serial.baudrate = self.baudrate
            self.instrument.serial.bytesize = 8
            self.instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
            self.instrument.serial.stopbits = 1
            self.instrument.serial.timeout = self.timeout
            
            # Modbus RTU mode
            self.instrument.mode = minimalmodbus.MODE_RTU
            self.instrument.clear_buffers_before_each_transaction = True
            
            # Test connection by trying to read from register 0
            test_reading = self.instrument.read_register(
                registeraddress=0, 
                number_of_decimals=1, 
                functioncode=3, 
                signed=True
            )
            
            self.is_connected = True
            self.last_error = None
            self.logger.info(f"Sensor connected successfully on {self.com_port}")
            return True
            
        except Exception as e:
            self.is_connected = False
            self.last_error = str(e)
            self.logger.error(f"Failed to setup sensor: {e}")
            return False
    
    def read_temperature(self, channel: int = 1) -> Optional[float]:
        """
        Read temperature from specified channel.
        
        Args:
            channel: Channel number (1 or 2)
            
        Returns:
            float: Temperature in Celsius, or None if reading failed
        """
        if not self.is_connected or self.instrument is None:
            if not self.setup_sensor():
                return None
        
        try:
            # Channel 1 = register 0, Channel 2 = register 1
            register_address = channel - 1
            
            temperature = self.instrument.read_register(
                registeraddress=register_address,
                number_of_decimals=1,
                functioncode=3,
                signed=True
            )
            
            self.last_error = None
            return float(temperature)
            
        except Exception as e:
            self.last_error = str(e)
            self.logger.error(f"Failed to read temperature from channel {channel}: {e}")
            self.is_connected = False  # Mark as disconnected to retry setup next time
            return None
    
    def read_all_temperatures(self) -> Dict[str, Optional[float]]:
        """
        Read temperatures from both channels.
        
        Returns:
            dict: Dictionary with channel1 and channel2 temperatures
        """
        return {
            'channel1': self.read_temperature(1),
            'channel2': self.read_temperature(2)
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get sensor connection status and last error.
        
        Returns:
            dict: Status information
        """
        return {
            'is_connected': self.is_connected,
            'com_port': self.com_port,
            'slave_address': self.slave_address,
            'last_error': self.last_error
        }
    
    def disconnect(self):
        """Disconnect from the sensor."""
        if self.instrument and hasattr(self.instrument, 'serial') and self.instrument.serial:
            try:
                self.instrument.serial.close()
            except:
                pass
        self.is_connected = False
        self.instrument = None


# Test function for debugging
def test_sensor():
    """Test function to verify sensor connectivity and readings."""
    sensor = RealTemperatureSensor()
    
    if sensor.setup_sensor():
        print("Sensor setup successful!")
        print("-" * 40)
        
        try:
            for i in range(5):
                temps = sensor.read_all_temperatures()
                print(f"Reading #{i+1}:")
                print(f"Channel 1 Temperature: {temps['channel1']}°C")
                print(f"Channel 2 Temperature: {temps['channel2']}°C")
                print("-" * 40)
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("Test interrupted by user")
        finally:
            sensor.disconnect()
            print("Sensor disconnected")
    else:
        print(f"Failed to setup sensor: {sensor.last_error}")


if __name__ == "__main__":
    test_sensor() 