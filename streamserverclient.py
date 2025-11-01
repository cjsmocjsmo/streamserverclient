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
import argparse

# Detect desktop environment
def detect_desktop_environment():
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    session = os.environ.get('DESKTOP_SESSION', '').lower()
    gdm = os.environ.get('GDMSESSION', '').lower()
    wayland = os.environ.get('WAYLAND_DISPLAY', '')
    
    # Check for GNOME in various ways
    if ('gnome' in desktop or 'gnome' in session or 'gnome' in gdm or 
        desktop == 'ubuntu:gnome' or 'gnome-session' in os.environ.get('XDG_SESSION_DESKTOP', '').lower()):
        return 'gnome'
    elif 'kde' in desktop or 'plasma' in desktop:
        return 'kde'
    elif 'xfce' in desktop:
        return 'xfce'
    elif 'lxde' in desktop or 'lxqt' in desktop:
        return 'lxde'
    elif wayland:
        # If running on Wayland, likely GNOME
        return 'gnome'
    else:
        return 'unknown'

# Set Qt platform and desktop-specific compatibility
desktop_env = detect_desktop_environment()
print(f"Detected desktop environment: {desktop_env}")

os.environ['QT_QPA_PLATFORM'] = 'xcb'
if desktop_env == 'gnome':
    # GNOME-specific settings
    os.environ['QT_QPA_PLATFORMTHEME'] = 'gtk3'
    os.environ['QT_SCALE_FACTOR'] = '1'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    os.environ['QT_WAYLAND_DISABLE_WINDOWDECORATION'] = '1'
else:
    # Generic settings for other desktops
    os.environ['QT_QPA_PLATFORMTHEME'] = 'gtk3'
    os.environ['QT_SCALE_FACTOR'] = '1'

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QGridLayout,
                            QFrame, QMessageBox, QMenuBar, QToolBar)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QPixmap, QImage, QAction, QFont, QScreen
from PyQt6.QtWidgets import QSizePolicy

class FFmpegRTSPBridge:
    """FFmpeg RTSP bridge for reliable video streaming with preserved aspect ratio"""
    
    def __init__(self, rtsp_url, callback, max_width=1280, max_height=720):
        self.rtsp_url = rtsp_url
        self.callback = callback  # Callback function to send frames to
        self.max_width = max_width
        self.max_height = max_height
        self.actual_width = None
        self.actual_height = None
        self.process = None
        self.running = False
        self.thread = None
        
    def start(self):
        # First, probe the stream to get its original resolution
        try:
            probe_result = self._probe_stream_resolution()
            if probe_result:
                orig_width, orig_height = probe_result
                print(f"Using original resolution: {orig_width}x{orig_height}")
                self.actual_width = orig_width
                self.actual_height = orig_height
            else:
                # Fallback to default resolution
                self.actual_width = 640
                self.actual_height = 480
                
            print(f"Using resolution: {self.actual_width}x{self.actual_height}")
            
        except Exception as e:
            print(f"Resolution detection failed: {e}, using default 640x480")
            self.actual_width = 640
            self.actual_height = 480
        
        # Use FFmpeg with original resolution (no scaling)
        command = [
            'ffmpeg',
            '-i', self.rtsp_url,
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
    
    def _probe_stream_resolution(self):
        """Probe the stream to get its original resolution"""
        try:
            probe_cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-select_streams', 'v:0',
                self.rtsp_url
            ]
            
            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                if 'streams' in data and len(data['streams']) > 0:
                    stream = data['streams'][0]
                    width = stream.get('width')
                    height = stream.get('height')
                    if width and height:
                        return width, height
            return None
            
        except Exception as e:
            print(f"Stream probing failed: {e}")
            return None
    
    def _read_frames(self):
        frame_size = self.actual_width * self.actual_height * 3
        
        while self.running:
            try:
                raw_frame = self.process.stdout.read(frame_size)
                if len(raw_frame) != frame_size:
                    break
                
                frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((self.actual_height, self.actual_width, 3))
                self.callback(frame)
                
            except Exception as e:
                print(f"Frame reading error: {e}")
                break
    
    def stop(self):
        """Stop the FFmpeg bridge and cleanup resources"""
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)

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
        
    def frame_received(self, frame):
        """Callback for when a frame is received from the FFmpeg bridge"""
        if self.running:
            self.frameReady.emit(frame, self.stream_id)
        
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
            
            self.bridge = FFmpegRTSPBridge(
                url, 
                self.frame_received,
                max_width=1280,  # Use original camera resolution
                max_height=720   # Use original camera resolution
            )
            
            if self.bridge.start():
                self.statusChanged.emit(self.stream_id, f"Connected ({url_type})")
                print(f"Stream {self.stream_id}: Connected via {url_type}")
                
                # Keep the connection alive while streaming
                while self.running and self.bridge.running:
                    self.statusChanged.emit(self.stream_id, f"Streaming ({url_type})")
                    self.msleep(1000)  # Check every second
                
                self.bridge.stop()
                break  # Successfully connected, don't try fallback
            else:
                print(f"Stream {self.stream_id}: Failed to connect to {url_type}")
                if self.bridge:
                    self.bridge.stop()
                
        else:
            self.statusChanged.emit(self.stream_id, "All connection attempts failed")
        
        if self.bridge:
            self.bridge.stop()
        self.statusChanged.emit(self.stream_id, "Disconnected")
    
    def stop(self):
        self.running = False
        if self.bridge:
            self.bridge.stop()
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
        self.video_label.setMinimumSize(320, 240)  # Smaller minimum size for better responsiveness
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_label.setScaledContents(False)  # Maintain aspect ratio
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
    
    def __init__(self, desktop_env=None):
        super().__init__()
        self.stream_widgets = []
        self.config_file = "config.json"
        self.desktop_env = desktop_env or detect_desktop_environment()
        
        self.setup_ui()
        self.load_config()
        
    def setup_ui(self):
        self.setWindowTitle("RTSP Video Stream Client")
        
        # Desktop environment specific window flags
        if self.desktop_env == 'gnome':
            # GNOME-specific window flags
            self.setWindowFlags(
                Qt.WindowType.Window |
                Qt.WindowType.WindowTitleHint |
                Qt.WindowType.WindowSystemMenuHint |
                Qt.WindowType.WindowMinMaxButtonsHint |
                Qt.WindowType.WindowCloseButtonHint
            )
        else:
            # Default window flags for other environments
            self.setWindowFlags(Qt.WindowType.Window)
        
        # Detect screen size and set window geometry
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        
        print(f"Detected screen size: {screen_width}x{screen_height}")
        
        # Set initial size for windowed mode (used when toggling out of fullscreen)
        window_width = int(screen_width * 0.9)
        window_height = int(screen_height * 0.9)
        
        # Center the window for windowed mode
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Store windowed geometry for later use
        self.windowed_geometry = (x, y, window_width, window_height)
        
        # Set initial geometry for GNOME compatibility
        self.setGeometry(x, y, window_width, window_height)
        
        print(f"Window geometry set to: {window_width}x{window_height} at ({x}, {y})")
        print("Press F11 or Escape to toggle fullscreen mode")
        
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
        
        # View menu
        view_menu = menubar.addMenu('View')
        
        # Window controls
        minimize_action = QAction('Minimize Window', self)
        minimize_action.triggered.connect(self.showMinimized)
        view_menu.addAction(minimize_action)
        
        maximize_action = QAction('Maximize Window', self)
        maximize_action.triggered.connect(self.toggle_maximize)
        view_menu.addAction(maximize_action)
        
        view_menu.addSeparator()
        
        fullscreen_action = QAction('Toggle Fullscreen', self)
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
    
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
        
        # Add all streams horizontally with equal stretch
        for widget in self.stream_widgets:
            self.main_layout.addWidget(widget, 1)  # Equal stretch factor
            
        # Ensure equal spacing and margins that respect screen boundaries
        self.main_layout.setSpacing(5)  # Smaller spacing to fit better
        self.main_layout.setContentsMargins(5, 5, 5, 5)  # Smaller margins
        
        # Ensure the main window respects screen boundaries
        self.adjust_window_size()
    
    def adjust_window_size(self):
        """Adjust window size to fit content within screen boundaries"""
        screen = QApplication.primaryScreen()
        available_geometry = screen.availableGeometry()
        
        # Calculate preferred size based on number of streams
        num_streams = len(self.stream_widgets)
        if num_streams > 0:
            # Calculate width that fits all streams comfortably
            min_stream_width = 320  # Minimum width per stream
            preferred_width = min(
                num_streams * (min_stream_width + 20),  # Stream width + margins
                available_geometry.width() - 40  # Leave some screen margin
            )
            
            # Set reasonable height
            preferred_height = min(
                int(preferred_width * 0.6),  # Maintain reasonable aspect ratio
                available_geometry.height() - 80  # Leave space for title bar, etc.
            )
            
            # Only resize if not maximized or fullscreen
            if not self.isMaximized() and not self.isFullScreen():
                self.resize(preferred_width, preferred_height)
                # Center the window
                x = (available_geometry.width() - preferred_width) // 2
                y = (available_geometry.height() - preferred_height) // 2
                self.move(x, y)
    
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
    
    def toggle_maximize(self):
        """Toggle between maximized and normal window state"""
        if self.isMaximized():
            self.showNormal()
            print("Window restored to normal size")
        else:
            self.showMaximized()
            print("Window maximized")
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
            # Restore windowed geometry
            x, y, width, height = self.windowed_geometry
            self.setGeometry(x, y, width, height)
            print("Exited fullscreen mode")
        else:
            self.showFullScreen()
            print("Entered fullscreen mode")
    
    def keyPressEvent(self, event):
        """Handle keyboard events"""
        if event.key() == Qt.Key.Key_Escape:
            # Toggle between fullscreen and windowed mode
            if self.isFullScreen():
                self.showNormal()
                # Restore windowed geometry
                x, y, width, height = self.windowed_geometry
                self.setGeometry(x, y, width, height)
                print("Exited fullscreen mode")
            else:
                self.showFullScreen()
                print("Entered fullscreen mode")
        elif event.key() == Qt.Key.Key_F11:
            # F11 also toggles fullscreen
            if self.isFullScreen():
                self.showNormal()
                # Restore windowed geometry
                x, y, width, height = self.windowed_geometry
                self.setGeometry(x, y, width, height)
                print("Exited fullscreen mode")
            else:
                self.showFullScreen()
                print("Entered fullscreen mode")
        else:
            super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """Clean up when closing"""
        self.disconnect_all_streams()
        event.accept()

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='RTSP Video Stream Client')
    parser.add_argument('--force-gnome', action='store_true', 
                       help='Force GNOME window management mode')
    parser.add_argument('--desktop', choices=['gnome', 'kde', 'xfce', 'auto'],
                       default='auto', help='Force specific desktop environment handling')
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Detect and log screen information
    screen = app.primaryScreen()
    screen_geometry = screen.availableGeometry()
    screen_size = screen.size()
    dpi = screen.logicalDotsPerInch()
    
    print(f"=== Screen Detection ===")
    print(f"Screen size: {screen_size.width()}x{screen_size.height()}")
    print(f"Available area: {screen_geometry.width()}x{screen_geometry.height()}")
    print(f"DPI: {dpi}")
    print(f"Device pixel ratio: {screen.devicePixelRatio()}")
    print("========================")
    
    # Set application properties
    app.setApplicationName("RTSP Stream Client")
    app.setApplicationVersion("1.0")
    
    # Desktop environment detection with command line override
    if args.force_gnome or args.desktop == 'gnome':
        desktop_env = 'gnome'
        print("Forced GNOME mode via command line")
    elif args.desktop != 'auto':
        desktop_env = args.desktop
        print(f"Forced {args.desktop} mode via command line")
    else:
        desktop_env = detect_desktop_environment()
    
    print(f"Using desktop environment: {desktop_env}")
    
    window = RTSPClientMainWindow(desktop_env)
    
    if desktop_env == 'gnome':
        # GNOME-specific sequence for proper window handling
        print("Applying GNOME window management...")
        window.show()
        QApplication.processEvents()
        
        # For GNOME, we need to wait a bit before maximizing
        QTimer.singleShot(100, lambda: gnome_window_setup(window))
    else:
        # Standard sequence for other desktop environments
        print("Applying standard window management...")
        window.show()
        QApplication.processEvents()
        window.showMaximized()
    
    sys.exit(app.exec())

def gnome_window_setup(window):
    """Special window setup for GNOME desktop environment"""
    # Ensure window is properly centered and maximized in GNOME
    screen = QApplication.primaryScreen()
    available_rect = screen.availableGeometry()
    
    # Move to center first
    window.move(available_rect.center() - window.rect().center())
    QApplication.processEvents()
    
    # Then maximize
    window.showMaximized()
    print("GNOME window setup completed")

if __name__ == "__main__":
    main()