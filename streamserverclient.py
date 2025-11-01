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
                            QDialog, QCheckBox, QSpinBox, QSizePolicy)
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
            # Validate RTSP URL format
            if not self.rtsp_url or not self.rtsp_url.startswith('rtsp://'):
                self.statusChanged.emit(self.stream_id, "Invalid RTSP URL")
                return
            
            # Configure OpenCV for RTSP with better error handling
            print(f"Attempting to connect to: {self.rtsp_url}")
            
            # Try different backends for better compatibility
            backends_to_try = [
                cv2.CAP_GSTREAMER,  # GStreamer backend
                cv2.CAP_FFMPEG,     # FFmpeg backend
                cv2.CAP_ANY         # Any available backend
            ]
            
            self.cap = None
            for backend in backends_to_try:
                try:
                    print(f"Trying backend: {backend}")
                    self.cap = cv2.VideoCapture(self.rtsp_url, backend)
                    
                    # Configure capture properties
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer for real-time
                    self.cap.set(cv2.CAP_PROP_FPS, 25)  # Lower FPS for better stability
                    
                    # Set timeout properties if available
                    try:
                        self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)  # 5 second timeout
                        self.cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)   # 5 second read timeout
                    except:
                        pass  # These properties might not be available in all OpenCV versions
                    
                    # Test if we can actually read from the stream
                    if self.cap.isOpened():
                        ret, test_frame = self.cap.read()
                        if ret and test_frame is not None:
                            print(f"Successfully connected with backend: {backend}")
                            break
                        else:
                            print(f"Backend {backend} opened but couldn't read frame")
                            self.cap.release()
                            self.cap = None
                    else:
                        print(f"Backend {backend} failed to open")
                        if self.cap:
                            self.cap.release()
                        self.cap = None
                        
                except Exception as e:
                    print(f"Backend {backend} error: {e}")
                    if self.cap:
                        self.cap.release()
                    self.cap = None
                    continue
            
            if not self.cap or not self.cap.isOpened():
                self.statusChanged.emit(self.stream_id, "Failed to connect to RTSP stream")
                print(f"All backends failed for {self.rtsp_url}")
                return
                
            self.statusChanged.emit(self.stream_id, "Connected")
            print(f"Stream {self.stream_id} connected successfully")
            
            frame_count = 0
            consecutive_failures = 0
            max_consecutive_failures = 10
            
            while self.running:
                ret, frame = self.cap.read()
                
                if ret and frame is not None:
                    # Resize frame for display
                    frame = cv2.resize(frame, (640, 480))
                    self.frameReady.emit(frame, self.stream_id)
                    self.statusChanged.emit(self.stream_id, "Streaming")
                    consecutive_failures = 0
                    frame_count += 1
                else:
                    consecutive_failures += 1
                    print(f"Stream {self.stream_id} read failure {consecutive_failures}")
                    
                    if consecutive_failures >= max_consecutive_failures:
                        self.statusChanged.emit(self.stream_id, "Connection lost")
                        print(f"Stream {self.stream_id} lost after {consecutive_failures} failures")
                        break
                    else:
                        self.statusChanged.emit(self.stream_id, "No signal")
                        self.msleep(1000)  # Wait 1 second before retry
                    
        except Exception as e:
            error_msg = f"Stream error: {str(e)}"
            print(f"Stream {self.stream_id} exception: {error_msg}")
            self.statusChanged.emit(self.stream_id, error_msg)
        finally:
            if self.cap:
                self.cap.release()
                print(f"Stream {self.stream_id} released")
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
        self.retry_timer = QTimer()
        self.retry_timer.setSingleShot(True)
        self.retry_timer.timeout.connect(self.auto_retry)
        self.retry_count = 0
        self.max_retries = 5
        
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
        self.video_label.setMinimumSize(400, 300)
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, 
            QSizePolicy.Policy.Expanding
        )
        self.video_label.setScaledContents(False)  # We'll handle scaling manually
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #000000;
                border: 1px solid #555;
                border-radius: 5px;
            }
        """)
        self.video_label.setText("📺 No Signal")
        layout.addWidget(self.video_label, 1)  # Give it stretch factor
        
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
        
        # Scale to fit widget with proper aspect ratio
        pixmap = QPixmap.fromImage(qt_image)
        label_size = self.video_label.size()
        
        # Ensure we have a valid size
        if label_size.width() > 0 and label_size.height() > 0:
            scaled_pixmap = pixmap.scaled(
                label_size, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.video_label.setPixmap(scaled_pixmap)
        else:
            # Fallback for initial sizing
            scaled_pixmap = pixmap.scaled(
                400, 300, 
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
            self.retry_count = 0  # Reset retry count on success
        elif status == "Connecting...":
            color = "#f39c12"  # Orange
        else:
            color = "#e74c3c"  # Red
            # Schedule retry for connection failures
            if ("Failed" in status or "Error" in status or "lost" in status) and self.is_connected:
                if not self.retry_timer.isActive() and self.retry_count < self.max_retries:
                    retry_delay = min(5000 * (self.retry_count + 1), 30000)  # Exponential backoff, max 30s
                    print(f"Scheduling retry for stream {self.stream_id} in {retry_delay/1000}s (attempt {self.retry_count + 1}/{self.max_retries})")
                    self.retry_timer.start(retry_delay)
                elif self.retry_count >= self.max_retries:
                    print(f"Stream {self.stream_id} exceeded max retries")
                    self.status_label.setText(f"{status} - Max retries exceeded")
            
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background: transparent;
                border: none;
                padding: 5px;
                font-size: 12px;
            }}
        """)
    
    def auto_retry(self):
        """Automatically retry connection"""
        if self.is_connected and self.retry_count < self.max_retries:
            self.retry_count += 1
            print(f"Auto-retrying stream {self.stream_id} (attempt {self.retry_count}/{self.max_retries})")
            self.status_label.setText(f"Retrying... (attempt {self.retry_count}/{self.max_retries})")
            
            # Disconnect and reconnect
            if self.worker:
                self.worker.stop()
                self.worker = None
            
            # Start new connection
            self.worker = RTSPStreamWorker(self.stream_id, self.rtsp_url)
            self.worker.frameReady.connect(self.update_frame)
            self.worker.statusChanged.connect(self.update_status)
            self.worker.start()
    
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
        self.config_file = "config.json"  # Use the existing config.json file
        
        self.setup_ui()
        self.load_config()
        
    def setup_ui(self):
        """Setup the main window UI"""
        self.setWindowTitle("🎥 RTSP Video Stream Client")
        self.setGeometry(100, 100, 1400, 800)
        
        # Set minimum and maximum sizes for proper window controls
        self.setMinimumSize(800, 600)
        self.setMaximumSize(2560, 1440)  # Allow for large displays
        
        # Enable window controls (minimize, maximize, close)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowSystemMenuHint
        )
        
        # Set dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2c3e50;
            }
        """)
        
        # Create menu bar with window controls
        self.create_menu_bar()
        
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
        
        # Stream layout container
        self.stream_container = QWidget()
        self.update_stream_layout()
        main_layout.addWidget(self.stream_container)
        
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
        
        # Create stream widgets
        self.create_stream_widgets()
    
    def create_stream_widgets(self):
        """Create the three stream widgets"""
        # Try to load existing config first
        stream_configs = []
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                
                streams = config.get("streams", {})
                for i in range(1, 4):  # stream1, stream2, stream3
                    stream_key = f"stream{i}"
                    if stream_key in streams:
                        stream_data = streams[stream_key]
                        stream_configs.append((
                            stream_key,
                            stream_data.get("name", f"Camera {i}"),
                            stream_data.get("url", "")
                        ))
                    else:
                        stream_configs.append((stream_key, f"Camera {i}", ""))
            else:
                # Default configuration if no config file exists
                stream_configs = [
                    ("stream1", "Camera 1", ""),
                    ("stream2", "Camera 2", ""),
                    ("stream3", "Camera 3", "")
                ]
        except Exception as e:
            print(f"Error loading config during widget creation: {e}")
            # Fallback to default configuration
            stream_configs = [
                ("stream1", "Camera 1", ""),
                ("stream2", "Camera 2", ""),
                ("stream3", "Camera 3", "")
            ]
        
        for stream_id, name, url in stream_configs:
            widget = StreamWidget(stream_id, name, url)
            self.stream_widgets.append(widget)
    
    def update_stream_layout(self):
        """Update stream layout based on window size and state"""
        # Clear existing layout
        if self.stream_container.layout():
            layout = self.stream_container.layout()
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().setParent(None)
            layout.setParent(None)
        
        # Determine layout based on window size and state
        window_width = self.width()
        window_height = self.height()
        aspect_ratio = window_width / window_height if window_height > 0 else 1.0
        
        # Use horizontal layout when maximized or when window is wide
        use_horizontal = self.isMaximized() or self.isFullScreen() or aspect_ratio > 1.8
        
        if use_horizontal:
            # Horizontal layout - all streams in a row
            layout = QHBoxLayout()
            layout.setSpacing(10)
            layout.setContentsMargins(10, 10, 10, 10)
            
            for widget in self.stream_widgets:
                layout.addWidget(widget)
                # Set maximum width for each stream when in horizontal mode
                widget.setMaximumWidth(600)
                widget.setMinimumWidth(300)
                # Reset height constraints
                widget.setMaximumHeight(16777215)  # Default max
                widget.setMinimumHeight(250)
        else:
            # Grid layout - 2 on top, 1 below for normal/small windows
            layout = QGridLayout()
            layout.setSpacing(10)
            layout.setContentsMargins(10, 10, 10, 10)
            
            for i, widget in enumerate(self.stream_widgets):
                if i < 2:
                    layout.addWidget(widget, 0, i)
                else:
                    layout.addWidget(widget, 1, 0, 1, 2)  # Span 2 columns
                
                # Reset size constraints for grid mode
                widget.setMaximumWidth(16777215)  # Default max
                widget.setMaximumHeight(16777215)  # Default max
                widget.setMinimumWidth(250)
                widget.setMinimumHeight(250)
        
        self.stream_container.setLayout(layout)
    
    def resizeEvent(self, event):
        """Handle window resize events"""
        super().resizeEvent(event)
        if hasattr(self, 'stream_container'):
            # Use a timer to avoid excessive layout updates during resize
            if not hasattr(self, 'resize_timer'):
                self.resize_timer = QTimer()
                self.resize_timer.setSingleShot(True)
                self.resize_timer.timeout.connect(self.update_stream_layout)
            
            self.resize_timer.stop()
            self.resize_timer.start(100)  # 100ms delay
    
    def create_menu_bar(self):
        """Create menu bar with window controls and options"""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #34495e;
                color: #ecf0f1;
                border-bottom: 1px solid #2c3e50;
                padding: 4px;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 4px 8px;
                border-radius: 3px;
            }
            QMenuBar::item:selected {
                background-color: #3498db;
            }
            QMenu {
                background-color: #34495e;
                color: #ecf0f1;
                border: 1px solid #2c3e50;
            }
            QMenu::item {
                padding: 6px 20px;
            }
            QMenu::item:selected {
                background-color: #3498db;
            }
        """)
        
        # Window menu
        window_menu = menubar.addMenu("Window")
        
        # Minimize action
        minimize_action = window_menu.addAction("Minimize")
        minimize_action.setShortcut("Ctrl+M")
        minimize_action.triggered.connect(self.showMinimized)
        
        # Maximize/Restore action
        self.maximize_action = window_menu.addAction("Maximize")
        self.maximize_action.setShortcut("Ctrl+Shift+M")
        self.maximize_action.triggered.connect(self.toggle_maximize)
        
        # Fullscreen action
        fullscreen_action = window_menu.addAction("Toggle Fullscreen")
        fullscreen_action.setShortcut("F11")
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        
        window_menu.addSeparator()
        
        # Close action
        close_action = window_menu.addAction("Close")
        close_action.setShortcut("Ctrl+Q")
        close_action.triggered.connect(self.close)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        # Connect all action
        connect_all_action = view_menu.addAction("Connect All Streams")
        connect_all_action.setShortcut("Ctrl+A")
        connect_all_action.triggered.connect(self.connect_all_streams)
        
        # Disconnect all action
        disconnect_all_action = view_menu.addAction("Disconnect All Streams")
        disconnect_all_action.setShortcut("Ctrl+D")
        disconnect_all_action.triggered.connect(self.disconnect_all_streams)
        
        view_menu.addSeparator()
        
        # Save config action
        save_action = view_menu.addAction("Save Configuration")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_config)
    
    def toggle_maximize(self):
        """Toggle between maximized and normal window state"""
        if self.isMaximized():
            self.showNormal()
            self.maximize_action.setText("Maximize")
        else:
            self.showMaximized()
            self.maximize_action.setText("Restore")
        
        # Update layout after state change
        QTimer.singleShot(100, self.update_stream_layout)
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        
        # Update layout after state change
        QTimer.singleShot(100, self.update_stream_layout)
    
    def changeEvent(self, event):
        """Handle window state changes"""
        if event.type() == event.Type.WindowStateChange:
            if self.isMaximized():
                self.maximize_action.setText("Restore")
            else:
                self.maximize_action.setText("Maximize")
            
            # Update layout when window state changes
            QTimer.singleShot(100, self.update_stream_layout)
        
        super().changeEvent(event)
    
    def showEvent(self, event):
        """Handle window show event"""
        super().showEvent(event)
        # Update layout when window is first shown
        QTimer.singleShot(100, self.update_stream_layout)
    
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
        # Load existing config to preserve server settings and other fields
        existing_config = {}
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    existing_config = json.load(f)
        except Exception:
            pass
        
        # Update stream configurations while preserving existing structure
        if "streams" not in existing_config:
            existing_config["streams"] = {}
        
        for i, widget in enumerate(self.stream_widgets):
            stream_key = f"stream{i+1}"
            widget_config = widget.get_config()
            
            # Preserve description if it exists, otherwise use a default
            if stream_key in existing_config["streams"]:
                description = existing_config["streams"][stream_key].get("description", f"{widget_config['name']} camera")
            else:
                description = f"{widget_config['name']} camera"
            
            existing_config["streams"][stream_key] = {
                "name": widget_config["name"],
                "url": widget_config["url"],
                "description": description
            }
        
        # Preserve server settings if they exist
        if "server" not in existing_config:
            existing_config["server"] = {
                "port": 8000,
                "host": "0.0.0.0"
            }
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(existing_config, f, indent=2)
            self.statusBar().showMessage("Configuration saved successfully")
            QMessageBox.information(self, "Success", "Configuration saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_file):
                self.statusBar().showMessage("Configuration loaded successfully")
            else:
                # Create default config if it doesn't exist
                self.statusBar().showMessage("Created default configuration")
                
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to load configuration: {str(e)}")
            self.statusBar().showMessage("Using default configuration")
    
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