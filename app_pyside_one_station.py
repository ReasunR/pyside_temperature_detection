import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout,
                             QScrollArea, QFileDialog, QMessageBox, QCheckBox, 
                             QLineEdit, QSpinBox, QGroupBox, QFormLayout, QSizePolicy)
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QFont, QPalette, QColor
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import pandas as pd
from datetime import datetime
from temperature_station import TemperatureStation


class TemperatureChart(FigureCanvas):
    """Custom matplotlib widget for temperature charts"""
    
    def __init__(self, station_name):
        self.figure = Figure(figsize=(10, 6), dpi=100)
        super().__init__(self.figure)
        self.station_name = station_name
        self.ax = self.figure.add_subplot(111)
        self.setup_chart()
        
        # Set size policy to expand in both directions
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
    def setup_chart(self):
        """Initialize the chart appearance"""
        self.ax.set_title(f'{self.station_name} Temperature Trend', fontsize=14, fontweight='bold')
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('Temperature (°C)')
        self.ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
        
    def update_chart(self, history, threshold_difference):
        """Update the chart with new data from both channels and temperature difference"""
        self.ax.clear()
        self.setup_chart()
        
        if history and len(history) > 0:
            # Prepare data for both channels
            times = [reading['timestamp'] for reading in history]
            channel1_temps = [reading['channel1_temperature'] for reading in history]
            channel2_temps = [reading['channel2_temperature'] for reading in history]
            
            # Plot temperature lines for both channels with different colors
            self.ax.plot(times, channel1_temps, linewidth=2, label='Channel 1 Temperature', color='#B39DDB')
            self.ax.plot(times, channel2_temps, linewidth=2, label='Channel 2 Temperature', color='#2196F3')
            
            # Add vertical lines between channels for each reading
            for i, (time, temp1, temp2) in enumerate(zip(times, channel1_temps, channel2_temps)):
                difference = temp2 - temp1
                # Green if difference >= threshold (normal), red if < threshold (abnormal)
                line_color = '#4CAF50' if difference >= threshold_difference else '#f44336'
                self.ax.plot([time, time], [temp1, temp2], color=line_color, linewidth=1.5, alpha=0.7)
            
            # Add legend entries for the vertical lines
            from matplotlib.lines import Line2D
            legend_elements = [
                Line2D([0], [0], color='#B39DDB', linewidth=2, label='Channel 1 Temperature'),
                Line2D([0], [0], color='#2196F3', linewidth=2, label='Channel 2 Temperature'),
                Line2D([0], [0], color='#4CAF50', linewidth=1.5, label='Normal Difference (≥10°C)'),
                Line2D([0], [0], color='#f44336', linewidth=1.5, label='Abnormal Difference (<10°C)')
            ]
            self.ax.legend(handles=legend_elements, loc='lower left', fontsize=6, 
                          markerscale=0.5, handlelength=1.0, handletextpad=0.3, 
                          columnspacing=0.5, borderpad=0.3)
            
            # Format x-axis for time display
            self.ax.tick_params(axis='x', rotation=45)
            
            # Set y-axis limits with some padding
            all_temperatures = channel1_temps + channel2_temps
            if all_temperatures:
                min_temp = min(all_temperatures)
                max_temp = max(all_temperatures)
                padding = (max_temp - min_temp) * 0.1 if max_temp != min_temp else 1
                self.ax.set_ylim(min_temp - padding, max_temp + padding)
        else:
            # Show empty chart with message
            self.ax.text(0.5, 0.5, 'No data available\nStart station to see trends', 
                        transform=self.ax.transAxes, ha='center', va='center',
                        fontsize=14, alpha=0.6)
            
        self.figure.tight_layout()
        self.draw()

    def resizeEvent(self, event):
        """Handle resize events to maintain proper chart proportions"""
        super().resizeEvent(event)
        self.figure.tight_layout()
        self.draw()


class TemperatureDetectionApp(QMainWindow):
    """Main application window for single station monitoring"""
    
    def __init__(self):
        super().__init__()
        # Initialize with default simulated station, but allow configuration
        self.station = None
        self.setup_ui()
        self.setup_timer()
        # Create default station after UI is set up
        self.create_station()
        
    def setup_ui(self):
        """Setup the main UI"""
        self.setWindowTitle("🌡️ Temperature Detection System - Single Station")
        self.setGeometry(100, 100, 1000, 800)  # Slightly larger default size
        
        # Set minimum window size to prevent UI from becoming unusable
        self.setMinimumSize(800, 600)
        
        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QScrollArea {
                border: none;
                background-color: #f5f5f5;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        
        # Create scroll area as the central widget
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setCentralWidget(scroll_area)
        
        # Main widget and layout (now inside scroll area)
        main_widget = QWidget()
        scroll_area.setWidget(main_widget)
        
        # Set size policy for main widget
        main_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(15)  # Reduced spacing for better scaling
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("🌡️ Temperature Detection System")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #333; margin: 10px;")
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(title)
        

        
        # Configuration section
        config_group = QGroupBox("🔧 Configuration")
        config_group.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        config_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        config_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ccc;
                border-radius: 6px;
                margin: 5px 0px;
                padding-top: 8px;
                background-color: #f9f9f9;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 8px 0 8px;
                color: #333;
            }
        """)
        
        config_layout = QFormLayout(config_group)
        config_layout.setVerticalSpacing(5)
        config_layout.setContentsMargins(10, 5, 10, 10)
        
        # Real sensor checkbox
        self.use_real_sensor_cb = QCheckBox("Use Real Modbus Sensor")
        self.use_real_sensor_cb.setFont(QFont("Arial", 9))
        self.use_real_sensor_cb.stateChanged.connect(self.toggle_sensor_options)
        
        # COM port input
        self.com_port_input = QLineEdit("COM4")
        self.com_port_input.setEnabled(False)
        self.com_port_input.setFont(QFont("Arial", 9))
        self.com_port_input.setMaximumWidth(80)
        
        # Apply configuration button (smaller)
        self.apply_config_btn = QPushButton("🔄 Apply")
        self.apply_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.apply_config_btn.clicked.connect(self.apply_configuration)
        
        # Create horizontal layout for configuration controls
        sensor_row = QHBoxLayout()
        sensor_row.addWidget(self.use_real_sensor_cb)
        sensor_row.addStretch()
        
        port_config_row = QHBoxLayout()
        port_config_row.addWidget(QLabel("Port:"))
        port_config_row.addWidget(self.com_port_input)
        port_config_row.addWidget(self.apply_config_btn)
        port_config_row.addStretch()
        
        # Add to form layout
        config_layout.addRow(sensor_row)
        config_layout.addRow(port_config_row)
        
        layout.addWidget(config_group)
        
        # Station container - this is the main content area that should expand
        station_container = QWidget()
        station_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        station_container.setStyleSheet("""
            QWidget {
                border: 2px solid #ddd;
                border-radius: 8px;
                background-color: white;
                margin: 5px;
                padding: 15px;
            }
        """)
        
        station_layout = QVBoxLayout(station_container)
        station_layout.setSpacing(10)  # Reduced spacing for better scaling
        
        # Control buttons
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶️ Start")
        self.stop_btn = QPushButton("⏹️ Stop")
        
        # Set size policies for buttons
        self.start_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.stop_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        
        self.start_btn.clicked.connect(self.start_station)
        self.stop_btn.clicked.connect(self.stop_station)
        
        button_layout.addStretch()  # Center the buttons
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addStretch()  # Center the buttons
        station_layout.addLayout(button_layout)
        
        # Temperature display for both channels
        display_layout = QVBoxLayout()
        display_layout.setSpacing(5)
        
        # Temperature displays for both channels
        temp_channels_layout = QHBoxLayout()
        temp_channels_layout.setSpacing(20)  # Reduced spacing for better scaling
        
        # Channel 1 temperature display
        channel1_widget = QWidget()
        channel1_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        channel1_layout = QVBoxLayout(channel1_widget)
        channel1_layout.setSpacing(2)
        channel1_layout.setContentsMargins(0, 0, 0, 0)
        
        channel1_label = QLabel("📘 Channel 1")
        channel1_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        channel1_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        channel1_label.setStyleSheet("color: #B39DDB;")
        channel1_layout.addWidget(channel1_label)
        
        self.temp1_value = QLabel("No data")
        self.temp1_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.temp1_value.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.temp1_value.setMinimumHeight(40)  # Ensure minimum height
        channel1_layout.addWidget(self.temp1_value)
        
        temp_channels_layout.addWidget(channel1_widget)
        
        # Channel 2 temperature display
        channel2_widget = QWidget()
        channel2_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        channel2_layout = QVBoxLayout(channel2_widget)
        channel2_layout.setSpacing(2)
        channel2_layout.setContentsMargins(0, 0, 0, 0)
        
        channel2_label = QLabel("📗 Channel 2")
        channel2_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        channel2_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        channel2_label.setStyleSheet("color: #2196F3;")
        channel2_layout.addWidget(channel2_label)
        
        self.temp2_value = QLabel("No data")
        self.temp2_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.temp2_value.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.temp2_value.setMinimumHeight(40)  # Ensure minimum height
        channel2_layout.addWidget(self.temp2_value)
        
        temp_channels_layout.addWidget(channel2_widget)
        
        # Temperature difference display
        diff_widget = QWidget()
        diff_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        diff_layout = QVBoxLayout(diff_widget)
        diff_layout.setSpacing(2)
        diff_layout.setContentsMargins(0, 0, 0, 0)
        
        diff_label = QLabel("📊 Temperature Difference (Ch2-Ch1)")
        diff_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        diff_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        diff_label.setStyleSheet("color: #9C27B0;")
        diff_layout.addWidget(diff_label)
        
        self.diff_value = QLabel("No data")
        self.diff_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.diff_value.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.diff_value.setMinimumHeight(40)  # Ensure minimum height
        diff_layout.addWidget(self.diff_value)
        
        temp_channels_layout.addWidget(diff_widget)
        
        display_layout.addLayout(temp_channels_layout)
        
        station_layout.addLayout(display_layout)
        
        # Export button (smaller)
        export_layout = QHBoxLayout()
        export_layout.addStretch()
        
        self.export_btn = QPushButton("💾 Export CSV")
        self.export_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.export_btn.clicked.connect(self.export_csv)
        self.export_btn.setEnabled(False)
        export_layout.addWidget(self.export_btn)
        export_layout.addStretch()
        
        station_layout.addLayout(export_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        station_layout.addWidget(separator)
        
        # Temperature chart (this should take most of the available space)
        self.chart = TemperatureChart("Temperature Station")
        self.chart.setMinimumHeight(300)  # Minimum height for usability
        station_layout.addWidget(self.chart, 1)  # Give chart stretch factor of 1 (highest priority)
        
        # Add station container with stretch factor to make it expand
        layout.addWidget(station_container, 1)
        
        # Statistics at bottom
        stats_layout = QHBoxLayout()
        self.total_readings_label = QLabel("Total Readings\n--")
        self.normal_readings_label = QLabel("Normal Readings\n--")
        self.abnormal_readings_label = QLabel("Abnormal Readings\n--")
        
        for label in [self.total_readings_label, self.normal_readings_label, self.abnormal_readings_label]:
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFont(QFont("Arial", 11))
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            label.setMinimumHeight(60)  # Ensure minimum height
            label.setStyleSheet("""
                QLabel {
                    border: 1px solid #ddd;
                    padding: 10px;
                    border-radius: 6px;
                    background-color: #f9f9f9;
                    color: #333333;
                    margin: 5px;
                }
            """)
            stats_layout.addWidget(label)
        
        layout.addLayout(stats_layout)
        
        # Footer
        footer = QLabel("Single Station Temperature Monitoring System")
        footer.setFont(QFont("Arial", 10))
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #888; margin-top: 5px;")
        footer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(footer)
        
    def setup_timer(self):
        """Setup the timer for auto-refresh"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(1000)  # Update every 1 second
    
    def create_station(self):
        """Create a new station with current configuration"""
        use_real = self.use_real_sensor_cb.isChecked()
        com_port = self.com_port_input.text().strip() or "COM4"
        
        # Stop existing station if running
        if self.station:
            self.station.stop_detection()
        
        # Create new station
        self.station = TemperatureStation(
            station_id=1,
            name="Temperature Station",
            threshold_difference=10.0,  # Default threshold: channel2 - channel1 >= 10
            use_real_sensor=use_real,
            com_port=com_port
        )
        
        # Update UI labels
        self.update_station_info()
    
    def toggle_sensor_options(self):
        """Enable/disable sensor configuration options based on checkbox"""
        is_real_sensor = self.use_real_sensor_cb.isChecked()
        self.com_port_input.setEnabled(is_real_sensor)
    
    def apply_configuration(self):
        """Apply the current configuration by recreating the station"""
        try:
            self.create_station()
            QMessageBox.information(self, "Configuration Applied", 
                                  "Station configuration has been updated successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Configuration Error", 
                               f"Failed to apply configuration: {str(e)}")
    
    def update_station_info(self):
        """Update station info (placeholder for future sensor status updates)"""
        if not self.station:
            return
            
        # This method is kept for potential future sensor status updates
        # Currently no UI elements to update since labels were removed
        pass
        
    def start_station(self):
        """Start the temperature station"""
        self.station.start_detection()
        
    def stop_station(self):
        """Stop the temperature station"""
        self.station.stop_detection()
        
    def export_csv(self):
        """Export temperature data to CSV"""
        if self.station.get_status()['readings_count'] > 0:
            filename = f"{self.station.name.replace(' ', '_')}_temperature_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "Save Temperature Data", 
                filename, 
                "CSV Files (*.csv)"
            )
            
            if file_path:
                try:
                    csv_data = self.station.export_to_csv()
                    with open(file_path, 'w') as f:
                        f.write(csv_data)
                    QMessageBox.information(self, "Success", f"Data exported to {file_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to export data: {str(e)}")
        
    def update_display(self):
        """Update the display with current station data"""
        if not self.station:
            return
            
        status = self.station.get_status()
        
        # Update station info (sensor status, etc.)
        self.update_station_info()
        
        # Update temperature displays for both channels
        current_temps = status['current_temperatures']
        
        # Update Channel 1 display
        if current_temps['channel1'] is not None:
            temp1 = current_temps['channel1']
            self.temp1_value.setText(f"{temp1}°C")
            self.temp1_value.setStyleSheet("color: #B39DDB;")  # Keep channel color
        else:
            self.temp1_value.setText("No data")
            self.temp1_value.setStyleSheet("color: gray;")
        
        # Update Channel 2 display
        if current_temps['channel2'] is not None:
            temp2 = current_temps['channel2']
            self.temp2_value.setText(f"{temp2}°C")
            self.temp2_value.setStyleSheet("color: #2196F3;")  # Keep channel color
        else:
            self.temp2_value.setText("No data")
            self.temp2_value.setStyleSheet("color: gray;")
        
        # Update Temperature Difference display
        current_diff = status.get('current_difference')
        if current_diff is not None:
            self.diff_value.setText(f"{current_diff:.2f}°C")
            # Color based on threshold: green if >= threshold (normal), red if < threshold (abnormal)
            if status['is_abnormal']:
                self.diff_value.setStyleSheet("color: #f44336;")  # Red for abnormal (difference < threshold)
            else:
                self.diff_value.setStyleSheet("color: #4CAF50;")  # Green for normal (difference >= threshold)
        else:
            self.diff_value.setText("No data")
            self.diff_value.setStyleSheet("color: gray;")
        
        # Enable/disable export button
        self.export_btn.setEnabled(status['readings_count'] > 0)
        
        # Update chart
        history = self.station.get_temperature_history()
        self.chart.update_chart(history, status['threshold_difference'])
        
        # Update statistics (total, normal, abnormal readings)
        if history and len(history) > 0:
            total_readings = len(history)
            normal_readings = 0
            abnormal_readings = 0
            
            # Count normal and abnormal readings based on temperature difference
            for reading in history:
                temp_diff = reading['channel2_temperature'] - reading['channel1_temperature']
                if temp_diff >= status['threshold_difference']:
                    normal_readings += 1
                else:
                    abnormal_readings += 1
            
            self.total_readings_label.setText(f"Total Readings\n{total_readings}")
            self.normal_readings_label.setText(f"Normal Readings\n{normal_readings}")
            self.abnormal_readings_label.setText(f"Abnormal Readings\n{abnormal_readings}")
        else:
            self.total_readings_label.setText("Total Readings\n--")
            self.normal_readings_label.setText("Normal Readings\n--")
            self.abnormal_readings_label.setText("Abnormal Readings\n--")
    
    def closeEvent(self, event):
        """Handle application closing"""
        # Stop the station
        self.station.stop_detection()
        event.accept()


def main():
    """Main function to run the application"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Temperature Detection System - Single Station")
    app.setApplicationVersion("1.0")
    
    # Create and show main window
    window = TemperatureDetectionApp()
    window.show()
    
    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 