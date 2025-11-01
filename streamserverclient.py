#!/usr/bin/env python3
"""
Complete RTSP Video Stream Client using PyQt6
Displays multiple video feeds from RTSP sources using FFmpeg bridge
"""

import sys
import os
import json
import subprocess
import threading
import queue
import numpy as np
import cv2

# Set Qt platform before importing PyQt6
os.environ['QT_QPA_PLATFORM'] = 'xcb'

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QGridLayout,
                            QFrame, QMessageBox, QMenuBar, QToolBar)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QPixmap, QImage, QAction, QFont
from PyQt6.QtWidgets import QSizePolicy

class FFmpegRTSPBridge:
    """FFmpeg RTSP bridge for reliable video streaming"""
    
    def __init__(self, rtsp_url, width=640, height=480):
        self.rtsp_url = rtsp_url
        self.width = width
        self.height = height
        self.process = None
        self.frame_queue = queue.Queue(maxsize=3)
        self.running = False
        self.thread = None
        
    def start(self):
        command = [
            'ffmpeg',
            '-i', self.rtsp_url,
            '-vf', f'scale={self.width}:{self.height}',
            '-pix_fmt', 'bgr24',
            '-f', 'rawvideo',
            '-an',
            '-loglevel', 'error',
            '-'
        ]
        
        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**6
            )
            
            self.running = True
            self.thread = threading.Thread(target=self._read_frames, daemon=True)
            self.thread.start()
            return True
            
        except Exception as e:
            print(f"FFmpeg start error: {e}")
            return False
    
    def _read_frames(self):
        frame_size = self.width * self.height * 3
        
        while self.running and self.process:
            try:
                raw_frame = self.process.stdout.read(frame_size)
                if len(raw_frame) != frame_size:
                    break
                
                frame = np.frombuffer(raw_frame, dtype=np.uint8)
                frame = frame.reshape((self.height, self.width, 3))
                
                try:
                    self.frame_queue.put_nowait(frame)
                except queue.Full:
                    try:
                        self.frame_queue.get_nowait()
                        self.frame_queue.put_nowait(frame)
                    except queue.Empty:
                        pass
                        
            except Exception as e:
                if self.running:
                    print(f"Frame read error: {e}")
                break
    
    def read(self):
        try:
            frame = self.frame_queue.get_nowait()
            return True, frame
        except queue.Empty:
            return False, None
    
    def isOpened(self):
        return self.running and self.process and self.process.poll() is None
    
    def release(self):
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                pass

class RTSPStreamWorker(QThread):
    """Worker thread for RTSP stream processing using FFmpeg bridge"""
    frameReady = pyqtSignal(object, str)  # frame, stream_id
    statusChanged = pyqtSignal(str, str)  # stream_id, status
    
    def __init__(self, stream_id, rtsp_url, fallback_url=None):
        super().__init__()
        self.stream_id = stream_id
        self.rtsp_url = rtsp_url
        self.fallback_url = fallback_url
        self.running = False
        self.bridge = None
        
    def run(self):
        self.running = True
        self.statusChanged.emit(self.stream_id, "Connecting...")
        
        # Try primary URL first
        urls_to_try = [(self.rtsp_url, "Primary")]
        if self.fallback_url:
            urls_to_try.append((self.fallback_url, "Fallback"))
        
        for url, url_type in urls_to_try:
            if not self.running:
                break
                
            print(f"Stream {self.stream_id}: Trying {url_type} URL: {url}")
            self.statusChanged.emit(self.stream_id, f"Connecting to {url_type.lower()}...")
            
            self.bridge = FFmpegRTSPBridge(url, 640, 480)
            
            if self.bridge.start():
                self.statusChanged.emit(self.stream_id, f"Connected ({url_type})")
                print(f"Stream {self.stream_id}: Connected via {url_type}")
                
                # Wait for FFmpeg to start
                self.msleep(1000)
                
                # Main streaming loop
                frame_count = 0
                no_frame_count = 0
                
                while self.running and self.bridge.isOpened():
                    ret, frame = self.bridge.read()
                    
                    if ret and frame is not None:
                        self.frameReady.emit(frame, self.stream_id)
                        self.statusChanged.emit(self.stream_id, f"Streaming ({url_type})")
                        frame_count += 1
                        no_frame_count = 0
                        
                        if frame_count % 60 == 0:  # Log every 2 seconds
                            print(f"Stream {self.stream_id}: {frame_count} frames")
                    else:
                        no_frame_count += 1
                        if no_frame_count > 150:  # 5 seconds without frames
                            print(f"Stream {self.stream_id}: No frames for 5 seconds")
                            break
                    
                    self.msleep(33)  # ~30 FPS
                
                self.bridge.release()
                break  # Successfully connected, don't try fallback
            else:
                print(f"Stream {self.stream_id}: Failed to connect to {url_type}")
                if self.bridge:
                    self.bridge.release()
                
        else:
            self.statusChanged.emit(self.stream_id, "All connection attempts failed")
        
        if self.bridge:
            self.bridge.release()
        self.statusChanged.emit(self.stream_id, "Disconnected")
    
    def stop(self):
        self.running = False
        if self.bridge:
            self.bridge.release()
        self.quit()
        self.wait()

class StreamWidget(QFrame):
    """Widget for displaying a single RTSP stream"""
    
    def __init__(self, stream_id, stream_name, rtsp_url, fallback_url=None):
        super().__init__()
        self.stream_id = stream_id
        self.stream_name = stream_name
        self.rtsp_url = rtsp_url
        self.fallback_url = fallback_url
        self.worker = None
        self.is_connected = False
        
        self.setup_ui()
        
    def setup_ui(self):
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
                padding: 8px;
            }
        """)
        layout.addWidget(self.title_label)
        
        # Video display area
        self.video_label = QLabel("Click Connect to start streaming")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(480, 360)  # Better aspect ratio for horizontal layout
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #000000;
                border: 2px solid #555;
                border-radius: 8px;
                color: #bdc3c7;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.video_label, 1)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #95a5a6;
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
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:pressed {
                background-color: #229954;
            }
        """)
        button_layout.addWidget(self.connect_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def toggle_connection(self):
        if self.is_connected:
            self.disconnect_stream()
        else:
            self.connect_stream()
    
    def connect_stream(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        
        self.worker = RTSPStreamWorker(self.stream_id, self.rtsp_url, self.fallback_url)
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
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """)
    
    def disconnect_stream(self):
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
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:pressed {
                background-color: #229954;
            }
        """)
        
        self.video_label.setText("📺 Disconnected")
        self.update_status(self.stream_id, "Disconnected")
    
    def update_frame(self, frame, stream_id):
        if stream_id != self.stream_id:
            return
        
        try:
            # Convert BGR to RGB (FFmpeg outputs BGR, Qt expects RGB)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            
            # Create QImage
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            
            # Convert to QPixmap and scale to fit
            pixmap = QPixmap.fromImage(qt_image)
            
            # Scale to fit widget with proper aspect ratio
            label_size = self.video_label.size()
            if label_size.width() > 0 and label_size.height() > 0:
                scaled_pixmap = pixmap.scaled(
                    label_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.video_label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            print(f"Frame display error for {stream_id}: {e}")
    
    def update_status(self, stream_id, status):
        if stream_id != self.stream_id:
            return
        
        self.status_label.setText(status)
        
        # Color-code status
        if "Streaming" in status:
            color = "#27ae60"  # Green
        elif "Connected" in status or "Connecting" in status:
            color = "#3498db"  # Blue
        elif "Failed" in status or "lost" in status:
            color = "#e74c3c"  # Red
        else:
            color = "#95a5a6"  # Gray
        
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background: transparent;
                border: none;
                padding: 5px;
                font-size: 12px;
            }}
        """)

class RTSPClientMainWindow(QMainWindow):
    """Main window for the RTSP client application"""
    
    def __init__(self):
        super().__init__()
        self.stream_widgets = []
        self.config_file = "config.json"
        
        self.setup_ui()
        self.load_config()
        
    def setup_ui(self):
        self.setWindowTitle("RTSP Video Stream Client")
        self.setGeometry(100, 100, 1800, 700)  # Wider window for horizontal layout
        
        # Dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2c3e50;
                color: #ecf0f1;
            }
        """)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Use horizontal layout for all streams
        self.main_layout = QHBoxLayout()
        central_widget.setLayout(self.main_layout)
        
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        connect_all_action = QAction('Connect All Streams', self)
        connect_all_action.triggered.connect(self.connect_all_streams)
        file_menu.addAction(connect_all_action)
        
        disconnect_all_action = QAction('Disconnect All Streams', self)
        disconnect_all_action.triggered.connect(self.disconnect_all_streams)
        file_menu.addAction(disconnect_all_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            streams = config.get('streams', {})
            
            # Create stream widgets
            for stream_id, stream_config in streams.items():
                stream_name = stream_config.get('name', f'Stream {stream_id}')
                rtsp_url = stream_config.get('url', '')
                fallback_url = stream_config.get('fallback_url', '')
                
                if rtsp_url:  # Only create widget if URL is configured
                    widget = StreamWidget(stream_id, stream_name, rtsp_url, fallback_url)
                    self.stream_widgets.append(widget)
            
            self.update_layout()
            
        except Exception as e:
            print(f"Error loading config: {e}")
            QMessageBox.warning(self, "Configuration Error", f"Failed to load configuration: {e}")
            
            # Create default streams
            self.create_default_streams()
    
    def create_default_streams(self):
        """Create default stream configuration"""
        default_streams = [
            ("stream1", "Camera 1", ""),
            ("stream2", "Camera 2", ""),
            ("stream3", "Camera 3", "")
        ]
        
        for stream_id, name, url in default_streams:
            widget = StreamWidget(stream_id, name, url)
            self.stream_widgets.append(widget)
        
        self.update_layout()
    
    def update_layout(self):
        """Update the layout to display all streams horizontally"""
        # Clear existing layout
        for i in reversed(range(self.main_layout.count())):
            item = self.main_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    widget.setParent(None)
        
        # Add all streams horizontally
        for widget in self.stream_widgets:
            self.main_layout.addWidget(widget)
            
        # Ensure equal spacing
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
    
    def connect_all_streams(self):
        """Connect all streams"""
        for widget in self.stream_widgets:
            if not widget.is_connected:
                widget.connect_stream()
    
    def disconnect_all_streams(self):
        """Disconnect all streams"""
        for widget in self.stream_widgets:
            if widget.is_connected:
                widget.disconnect_stream()
    
    def closeEvent(self, event):
        """Clean up when closing"""
        self.disconnect_all_streams()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Set application properties
    app.setApplicationName("RTSP Stream Client")
    app.setApplicationVersion("1.0")
    
    window = RTSPClientMainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()