#!/usr/bin/env python3
"""
RTSP Video Stream Client using PyQt6
Displays three video feeds from RTSP sources (Raspberry Pi cameras, IP cameras, etc.)
"""

import sys
import json
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QGridLayout,
                            QFrame, QMessageBox, QLineEdit, QFormLayout,
                            QDialog, QCheckBox, QSpinBox)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt, QSize
from PyQt6.QtGui import QPixmap, QImage, QPalette, QColor, QFont
import cv2
import numpy as np
from datetime import datetime

class RTSPStreamWorker(QThread):
    """Worker thread for handling RTSP stream processing"""
    frameReady = pyqtSignal(np.ndarray, str)
    statusChanged = pyqtSignal(str, str)  # stream_id, status
    
    def __init__(self, stream_id, rtsp_url):
        super().__init__()
        self.stream_id = stream_id
        self.rtsp_url = rtsp_url
        self.running = False
        self.cap = None
        
    def run(self):
        """Main thread loop for RTSP stream processing"""
        self.running = True
        self.statusChanged.emit(self.stream_id, "Connecting...")
        
        try:
            # Configure OpenCV for RTSP
            self.cap = cv2.VideoCapture(self.rtsp_url)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer for real-time
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            if not self.cap.isOpened():
                self.statusChanged.emit(self.stream_id, "Failed to connect")
                return
                
            self.statusChanged.emit(self.stream_id, "Connected")
            
            while self.running:
                ret, frame = self.cap.read()
                
                if ret:
                    # Resize frame for display
                    frame = cv2.resize(frame, (640, 480))
                    self.frameReady.emit(frame, self.stream_id)
                    self.statusChanged.emit(self.stream_id, "Streaming")
                else:
                    self.statusChanged.emit(self.stream_id, "No signal")
                    self.msleep(1000)  # Wait 1 second before retry
                    
        except Exception as e:
            self.statusChanged.emit(self.stream_id, f"Error: {str(e)}")
        finally:
            if self.cap:
                self.cap.release()
            self.statusChanged.emit(self.stream_id, "Disconnected")
    
    def stop(self):
        """Stop the stream processing"""
        self.running = False
        if self.cap:
            self.cap.release()
        self.quit()
        self.wait()

class StreamWidget(QFrame):
    """Widget for displaying a single RTSP stream"""
    
    def __init__(self, stream_id, stream_name, rtsp_url):
        super().__init__()
        self.stream_id = stream_id
        self.stream_name = stream_name
        self.rtsp_url = rtsp_url
        self.worker = None
        self.is_connected = False
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI for this stream widget"""
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            QFrame {
                background-color: #34495e;
                border: 2px solid #2c3e50;
                border-radius: 10px;
                margin: 5px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Title
        self.title_label = QLabel(f"📹 {self.stream_name}")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("""
            QLabel {
                color: #ecf0f1;
                font-size: 16px;
                font-weight: bold;
                background: transparent;
                border: none;
                padding: 5px;
            }
        """)
        layout.addWidget(self.title_label)
        
        # Video display area
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #000000;
                border: 1px solid #555;
                border-radius: 5px;
            }
        """)
        self.video_label.setText("📺 No Signal")
        layout.addWidget(self.video_label)
        
        # Status label
        self.status_label = QLabel("Disconnected")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #e74c3c;
                background: transparent;
                border: none;
                padding: 5px;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.status_label)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.show_settings)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        
        button_layout.addWidget(self.connect_btn)
        button_layout.addWidget(self.settings_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def toggle_connection(self):
        """Toggle stream connection"""
        if self.is_connected:
            self.disconnect_stream()
        else:
            self.connect_stream()
    
    def connect_stream(self):
        """Start the RTSP stream"""
        if not self.rtsp_url:
            QMessageBox.warning(self, "Warning", "Please configure RTSP URL in settings")
            return
            
        self.worker = RTSPStreamWorker(self.stream_id, self.rtsp_url)
        self.worker.frameReady.connect(self.update_frame)
        self.worker.statusChanged.connect(self.update_status)
        self.worker.start()
        
        self.is_connected = True
        self.connect_btn.setText("Disconnect")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """)
    
    def disconnect_stream(self):
        """Stop the RTSP stream"""
        if self.worker:
            self.worker.stop()
            self.worker = None
        
        self.is_connected = False
        self.connect_btn.setText("Connect")
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        
        self.video_label.setText("📺 Disconnected")
        self.update_status(self.stream_id, "Disconnected")
    
    def update_frame(self, frame, stream_id):
        """Update the video frame display"""
        if stream_id != self.stream_id:
            return
            
        # Convert OpenCV frame to Qt format
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        
        # Scale to fit widget
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(
            self.video_label.size(), 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.video_label.setPixmap(scaled_pixmap)
    
    def update_status(self, stream_id, status):
        """Update the status label"""
        if stream_id != self.stream_id:
            return
            
        self.status_label.setText(status)
        
        # Color-code status
        if status in ["Connected", "Streaming"]:
            color = "#27ae60"  # Green
        elif status == "Connecting...":
            color = "#f39c12"  # Orange
        else:
            color = "#e74c3c"  # Red
            
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background: transparent;
                border: none;
                padding: 5px;
                font-size: 12px;
            }}
        """)
    
    def show_settings(self):
        """Show settings dialog for this stream"""
        dialog = StreamSettingsDialog(self.stream_name, self.rtsp_url)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.stream_name = dialog.get_name()
            self.rtsp_url = dialog.get_url()
            self.title_label.setText(f"📹 {self.stream_name}")
    
    def get_config(self):
        """Get current configuration"""
        return {
            'name': self.stream_name,
            'url': self.rtsp_url
        }
class StreamSettingsDialog(QDialog):
    """Dialog for configuring stream settings"""
    
    def __init__(self, name, url):
        super().__init__()
        self.setWindowTitle("Stream Settings")
        self.setFixedSize(400, 200)
        
        layout = QFormLayout()
        
        self.name_edit = QLineEdit(name)
        self.url_edit = QLineEdit(url)
        
        layout.addRow("Stream Name:", self.name_edit)
        layout.addRow("RTSP URL:", self.url_edit)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addRow(button_layout)
        self.setLayout(layout)
    
    def get_name(self):
        return self.name_edit.text()
    
    def get_url(self):
        return self.url_edit.text()

class RTSPClientMainWindow(QMainWindow):
    """Main window for the RTSP client application"""
    
    def __init__(self):
        super().__init__()
        self.stream_widgets = []
        self.config_file = "rtsp_config.json"
        
        self.setup_ui()
        self.load_config()
        
    def setup_ui(self):
        """Setup the main window UI"""
        self.setWindowTitle("🎥 RTSP Video Stream Client")
        self.setGeometry(100, 100, 1400, 800)
        
        # Set dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2c3e50;
            }
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("🎥 RTSP Video Stream Client")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #ecf0f1;
                font-size: 24px;
                font-weight: bold;
                padding: 20px;
                background: transparent;
            }
        """)
        main_layout.addWidget(title_label)
        
        # Stream grid
        stream_layout = QGridLayout()
        
        # Create three stream widgets
        stream_configs = [
            ("stream1", "Camera 1", ""),
            ("stream2", "Camera 2", ""),
            ("stream3", "Camera 3", "")
        ]
        
        for i, (stream_id, name, url) in enumerate(stream_configs):
            widget = StreamWidget(stream_id, name, url)
            self.stream_widgets.append(widget)
            
            # Arrange in grid: 2 on top, 1 centered below
            if i < 2:
                stream_layout.addWidget(widget, 0, i)
            else:
                stream_layout.addWidget(widget, 1, 0, 1, 2)  # Span 2 columns
        
        main_layout.addLayout(stream_layout)
        
        # Control panel
        control_layout = QHBoxLayout()
        
        # Global controls
        connect_all_btn = QPushButton("Connect All")
        connect_all_btn.clicked.connect(self.connect_all_streams)
        connect_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
        """)
        
        disconnect_all_btn = QPushButton("Disconnect All")
        disconnect_all_btn.clicked.connect(self.disconnect_all_streams)
        disconnect_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        
        save_config_btn = QPushButton("Save Config")
        save_config_btn.clicked.connect(self.save_config)
        save_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        control_layout.addWidget(connect_all_btn)
        control_layout.addWidget(disconnect_all_btn)
        control_layout.addStretch()
        control_layout.addWidget(save_config_btn)
        
        main_layout.addLayout(control_layout)
        
        # Status bar
        self.statusBar().showMessage("Ready - Configure RTSP URLs and click Connect")
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #34495e;
                color: #ecf0f1;
                border-top: 1px solid #2c3e50;
            }
        """)
        
        central_widget.setLayout(main_layout)
    
    def connect_all_streams(self):
        """Connect all streams"""
        for widget in self.stream_widgets:
            if not widget.is_connected:
                widget.connect_stream()
        self.statusBar().showMessage("Connecting all streams...")
    
    def disconnect_all_streams(self):
        """Disconnect all streams"""
        for widget in self.stream_widgets:
            if widget.is_connected:
                widget.disconnect_stream()
        self.statusBar().showMessage("All streams disconnected")
    
    def save_config(self):
        """Save current configuration to JSON file"""
        config = {
            "streams": {}
        }
        
        for i, widget in enumerate(self.stream_widgets):
            stream_config = widget.get_config()
            config["streams"][f"stream{i+1}"] = stream_config
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            self.statusBar().showMessage("Configuration saved successfully")
            QMessageBox.information(self, "Success", "Configuration saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                
                streams = config.get("streams", {})
                for i, widget in enumerate(self.stream_widgets):
                    stream_key = f"stream{i+1}"
                    if stream_key in streams:
                        stream_config = streams[stream_key]
                        widget.stream_name = stream_config.get("name", f"Camera {i+1}")
                        widget.rtsp_url = stream_config.get("url", "")
                        widget.title_label.setText(f"📹 {widget.stream_name}")
                
                self.statusBar().showMessage("Configuration loaded successfully")
            else:
                # Create default config
                self.save_config()
                
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to load configuration: {str(e)}")
    
    def closeEvent(self, event):
        """Handle application close event"""
        # Disconnect all streams before closing
        self.disconnect_all_streams()
        event.accept()

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("RTSP Stream Client")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("StreamClient")
    
    # Create and show main window
    window = RTSPClientMainWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()