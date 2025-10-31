#!/usr/bin/env python3
"""
Minimal HTTP Server for displaying three video streams from remote Raspberry Pi devices
with OpenCV motion detection for human-sized objects.
"""

import http.server
import socketserver
import os
import json
import threading
import time
import cv2
import numpy as np
import requests
from urllib.parse import urlparse, parse_qs
from datetime import datetime

class MotionDetector:
    def __init__(self, stream_id, stream_url):
        self.stream_id = stream_id
        self.stream_url = stream_url
        self.is_active = False
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(detectShadows=True)
        self.motion_detected = False
        self.last_motion_time = None
        self.detection_thread = None
        self.running = False
        self.current_frame = None
        self.processed_frame = None
        self.frame_lock = threading.Lock()
        
        # Motion detection parameters for human-sized objects
        self.min_contour_area = 1500  # Minimum area for human detection
        self.max_contour_area = 50000  # Maximum area to avoid false positives
        self.motion_threshold = 30  # Motion sensitivity
        
    def start_detection(self):
        """Start motion detection in a separate thread"""
        if not self.is_active:
            self.is_active = True
            self.running = True
            self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
            self.detection_thread.start()
            print(f"🎯 Motion detection started for {self.stream_id}")
    
    def stop_detection(self):
        """Stop motion detection"""
        self.is_active = False
        self.running = False
        if self.detection_thread:
            self.detection_thread.join(timeout=2)
        print(f"⏹️ Motion detection stopped for {self.stream_id}")
    
    def _detection_loop(self):
        """Main detection loop running in separate thread"""
        cap = None
        try:
            # Try to open the stream
            cap = cv2.VideoCapture(self.stream_url)
            if not cap.isOpened():
                print(f"❌ Cannot open stream {self.stream_id}: {self.stream_url}")
                return
            
            print(f"📹 Connected to stream {self.stream_id}")
            
            while self.running and self.is_active:
                ret, frame = cap.read()
                if not ret:
                    print(f"⚠️ No frame received from {self.stream_id}")
                    time.sleep(1)
                    continue
                
                # Resize frame for faster processing
                frame = cv2.resize(frame, (640, 480))
                
                # Store original frame
                with self.frame_lock:
                    self.current_frame = frame.copy()
                
                # Apply background subtraction
                fg_mask = self.background_subtractor.apply(frame)
                
                # Remove noise and fill holes
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
                
                # Find contours
                contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Create a copy of the frame for drawing
                processed_frame = frame.copy()
                
                # Check for human-sized motion and draw bounding boxes
                motion_found = False
                motion_boxes = []
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if self.min_contour_area <= area <= self.max_contour_area:
                        # Check if contour has human-like aspect ratio
                        x, y, w, h = cv2.boundingRect(contour)
                        aspect_ratio = h / w if w > 0 else 0
                        
                        # Human-like aspect ratio (taller than wide)
                        if 1.2 <= aspect_ratio <= 4.0:
                            motion_found = True
                            motion_boxes.append((x, y, w, h, area))
                            self.last_motion_time = datetime.now()
                
                # Draw bounding boxes for detected motion
                for x, y, w, h, area in motion_boxes:
                    # Draw rectangle around detected motion
                    cv2.rectangle(processed_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    
                    # Add label with confidence/area info
                    label = f"Motion: {int(area)}"
                    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                    cv2.rectangle(processed_frame, (x, y - label_size[1] - 10), 
                                (x + label_size[0], y), (0, 0, 255), -1)
                    cv2.putText(processed_frame, label, (x, y - 5), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                
                # Add motion detection status overlay
                status_text = f"Motion Detection: {'ACTIVE' if motion_found else 'MONITORING'}"
                status_color = (0, 0, 255) if motion_found else (0, 255, 0)
                cv2.putText(processed_frame, status_text, (10, 30), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
                
                # Add timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(processed_frame, timestamp, (10, processed_frame.shape[0] - 10), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Store processed frame
                with self.frame_lock:
                    self.processed_frame = processed_frame
                
                self.motion_detected = motion_found
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.1)
                
        except Exception as e:
            print(f"❌ Motion detection error for {self.stream_id}: {e}")
        finally:
            if cap:
                cap.release()
    
    def get_status(self):
        """Get current motion detection status"""
        return {
            'active': self.is_active,
            'motion_detected': self.motion_detected,
            'last_motion': self.last_motion_time.isoformat() if self.last_motion_time else None
        }
    
    def get_processed_frame(self):
        """Get the current processed frame with bounding boxes"""
        with self.frame_lock:
            if self.processed_frame is not None:
                return self.processed_frame.copy()
            elif self.current_frame is not None:
                return self.current_frame.copy()
            return None

class VideoStreamHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Load video stream URLs from config file
        self.video_streams = self.load_config()
        # Initialize motion detectors
        self.motion_detectors = {}
        for stream_id, stream_url in self.video_streams.items():
            self.motion_detectors[stream_id] = MotionDetector(stream_id, stream_url)
        super().__init__(*args, **kwargs)
    
    def load_config(self):
        """Load stream configuration from config.json"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Extract just the URLs for the streams
            streams = {}
            for stream_id, stream_info in config['streams'].items():
                streams[stream_id] = stream_info['url']
            
            return streams
        except FileNotFoundError:
            print("⚠️  config.json not found, using default URLs")
            return {
                'stream1': 'http://192.168.1.100:8080/stream',
                'stream2': 'http://192.168.1.101:8080/stream', 
                'stream3': 'http://192.168.1.102:8080/stream'
            }
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return {}
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/':
            self.serve_main_page()
        elif parsed_path.path == '/api/streams':
            self.serve_stream_config()
        elif parsed_path.path.startswith('/api/motion/'):
            self.handle_motion_api(parsed_path)
        elif parsed_path.path.startswith('/motion_feed/'):
            self.serve_motion_feed(parsed_path)
        else:
            super().do_GET()
    
    def do_POST(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path.startswith('/api/motion/'):
            self.handle_motion_api(parsed_path)
        else:
            self.send_response(404)
            self.end_headers()
    
    def handle_motion_api(self, parsed_path):
        """Handle motion detection API requests"""
        path_parts = parsed_path.path.split('/')
        
        if len(path_parts) >= 4:
            stream_id = path_parts[3]
            
            if stream_id in self.motion_detectors:
                if len(path_parts) >= 5:
                    action = path_parts[4]
                    
                    if action == 'start' and self.command == 'POST':
                        self.motion_detectors[stream_id].start_detection()
                        self.send_json_response({'status': 'started'})
                    elif action == 'stop' and self.command == 'POST':
                        self.motion_detectors[stream_id].stop_detection()
                        self.send_json_response({'status': 'stopped'})
                    elif action == 'status' and self.command == 'GET':
                        status = self.motion_detectors[stream_id].get_status()
                        self.send_json_response(status)
                    else:
                        self.send_response(400)
                        self.end_headers()
                else:
                    # Get status for stream
                    status = self.motion_detectors[stream_id].get_status()
                    self.send_json_response(status)
            else:
                self.send_response(404)
                self.end_headers()
        else:
            # Get status for all streams
            all_status = {}
            for stream_id, detector in self.motion_detectors.items():
                all_status[stream_id] = detector.get_status()
            self.send_json_response(all_status)
    
    def send_json_response(self, data):
        """Send JSON response"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        json_data = json.dumps(data, indent=2)
        self.wfile.write(json_data.encode())
    
    def serve_motion_feed(self, parsed_path):
        """Serve processed video frame with motion detection overlays"""
        path_parts = parsed_path.path.split('/')
        
        if len(path_parts) >= 3:
            stream_id = path_parts[2]
            
            if stream_id in self.motion_detectors:
                detector = self.motion_detectors[stream_id]
                
                if detector.is_active:
                    # Get processed frame with bounding boxes
                    frame = detector.get_processed_frame()
                    
                    if frame is not None:
                        # Encode frame as JPEG
                        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        
                        if ret:
                            self.send_response(200)
                            self.send_header('Content-type', 'image/jpeg')
                            self.send_header('Content-Length', str(len(buffer)))
                            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                            self.send_header('Pragma', 'no-cache')
                            self.send_header('Expires', '0')
                            self.end_headers()
                            self.wfile.write(buffer.tobytes())
                            return
                
                # If motion detection is not active or no frame available, serve placeholder
                self.serve_placeholder_image("Motion detection not active")
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(400)
            self.end_headers()
    
    def serve_placeholder_image(self, message):
        """Serve a placeholder image with a message"""
        # Create a simple placeholder image
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img.fill(50)  # Dark gray background
        
        # Add text message
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(message, font, 1, 2)[0]
        text_x = (img.shape[1] - text_size[0]) // 2
        text_y = (img.shape[0] + text_size[1]) // 2
        
        cv2.putText(img, message, (text_x, text_y), font, 1, (255, 255, 255), 2)
        
        # Encode as JPEG
        ret, buffer = cv2.imencode('.jpg', img)
        
        if ret:
            self.send_response(200)
            self.send_header('Content-type', 'image/jpeg')
            self.send_header('Content-Length', str(len(buffer)))
            self.end_headers()
            self.wfile.write(buffer.tobytes())
    
    def serve_main_page(self):
        """Serve the main HTML page with video streams"""
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Raspberry Pi Video Streams</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #2c3e50;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .header h1 {
            color: #000000;
            margin-bottom: 10px;
        }
        
        .streams-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .stream-box {
            background: #34495e;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        
        .stream-box:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }
        
        .stream-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #ecf0f1;
            text-align: center;
        }
        
        .video-container {
            position: relative;
            width: 100%;
            height: 300px;
            background: #000;
            border-radius: 4px;
            overflow: hidden;
        }
        
        .video-stream {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .stream-status {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
        }
        
        .status-online {
            background: rgba(0,200,0,0.8);
        }
        
        .status-offline {
            background: rgba(200,0,0,0.8);
        }
        
        .controls {
            margin-top: 10px;
            text-align: center;
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            justify-content: center;
        }
        
        .btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            flex: 1;
            min-width: 80px;
        }
        
        .btn:hover {
            background: #0056b3;
        }
        
        .btn-motion {
            background: #28a745;
        }
        
        .btn-motion:hover {
            background: #218838;
        }
        
        .btn-motion.active {
            background: #dc3545;
        }
        
        .btn-toggle {
            background: #6c757d;
        }
        
        .btn-toggle:hover {
            background: #545b62;
        }
        
        .btn-toggle.active {
            background: #ffc107;
            color: #000;
        }
        
        .btn-toggle.active:hover {
            background: #e0a800;
        }
        
        .motion-status {
            margin-top: 8px;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
            font-weight: bold;
            text-align: center;
        }
        
        .motion-inactive {
            background: rgba(108, 117, 125, 0.2);
            color: #6c757d;
        }
        
        .motion-active {
            background: rgba(40, 167, 69, 0.2);
            color: #28a745;
        }
        
        .motion-detected {
            background: rgba(220, 53, 69, 0.2);
            color: #dc3545;
            animation: pulse 1s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .error-message {
            color: #dc3545;
            text-align: center;
            padding: 20px;
            background: rgba(220,53,69,0.1);
            border-radius: 4px;
            margin-top: 10px;
        }
        
        @media (max-width: 768px) {
            .streams-container {
                grid-template-columns: 1fr;
            }
            
            .video-container {
                height: 250px;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🍓 Raspberry Pi Video Streams</h1>
        <p>Live video feeds from remote Raspberry Pi devices</p>
    </div>
    
    <div class="streams-container">
        <div class="stream-box">
            <div class="stream-title">📹 Shed - piir</div>
            <div class="video-container">
                <img id="stream1" class="video-stream" src="" alt="Video Stream 1">
                <div id="status1" class="stream-status status-offline">Offline</div>
            </div>
            <div class="controls">
                <button class="btn" onclick="toggleStream('stream1')">Toggle Stream</button>
                <button class="btn" onclick="refreshStream('stream1')">Refresh</button>
                <button id="motion1" class="btn btn-motion" onclick="toggleMotionDetection('stream1')">Start Motion</button>
                <button id="view1" class="btn btn-toggle" onclick="toggleView('stream1')">Motion View</button>
            </div>
            <div id="motion-status1" class="motion-status motion-inactive">Motion Detection: Inactive</div>
            <div id="error1" class="error-message" style="display: none;"></div>
        </div>
        
        <div class="stream-box">
            <div class="stream-title">📹 BackDoor - pipiw</div>
            <div class="video-container">
                <img id="stream2" class="video-stream" src="" alt="Video Stream 2">
                <div id="status2" class="stream-status status-offline">Offline</div>
            </div>
            <div class="controls">
                <button class="btn" onclick="toggleStream('stream2')">Toggle Stream</button>
                <button class="btn" onclick="refreshStream('stream2')">Refresh</button>
                <button id="motion2" class="btn btn-motion" onclick="toggleMotionDetection('stream2')">Start Motion</button>
                <button id="view2" class="btn btn-toggle" onclick="toggleView('stream2')">Motion View</button>
            </div>
            <div id="motion-status2" class="motion-status motion-inactive">Motion Detection: Inactive</div>
            <div id="error2" class="error-message" style="display: none;"></div>
        </div>
        
        <div class="stream-box">
            <div class="stream-title">📹 FrontDoor - picam</div>
            <div class="video-container">
                <img id="stream3" class="video-stream" src="" alt="Video Stream 3">
                <div id="status3" class="stream-status status-offline">Offline</div>
            </div>
            <div class="controls">
                <button class="btn" onclick="toggleStream('stream3')">Toggle Stream</button>
                <button class="btn" onclick="refreshStream('stream3')">Refresh</button>
                <button id="motion3" class="btn btn-motion" onclick="toggleMotionDetection('stream3')">Start Motion</button>
                <button id="view3" class="btn btn-toggle" onclick="toggleView('stream3')">Motion View</button>
            </div>
            <div id="motion-status3" class="motion-status motion-inactive">Motion Detection: Inactive</div>
            <div id="error3" class="error-message" style="display: none;"></div>
        </div>
        <audio id="backgroundAudio" autoplay loop controls style="position: fixed; bottom: 10px; right: 10px; z-index: 1000; opacity: 0.8;">
            <source src="https://playerservices.streamtheworld.com/api/livestream-redirect/KPLZFMAAC.aac" type="audio/aac">
            <source src="https://playerservices.streamtheworld.com/api/livestream-redirect/KPLZFM.mp3" type="audio/mpeg">
            <source src="https://playerservices.streamtheworld.com/api/livestream-redirect/KMADFMAAC.aac" type="audio/aac">
            <source src="https://playerservices.streamtheworld.com/api/livestream-redirect/KMADFM.mp3" type="audio/mpeg">
            <source src="https://ice42.securenetsystems.net/KPLZ" type="audio/mpeg">
            <source src="https://ice42.securenetsystems.net/KMAD" type="audio/mpeg">
            Your browser does not support the audio element.
        </audio>
    </div>

    <script>
        let streamUrls = {};
        let streamStates = {
            stream1: false,
            stream2: false,
            stream3: false
        };

        // Load stream configuration
        async function loadStreamConfig() {
            try {
                const response = await fetch('/api/streams');
                streamUrls = await response.json();
                console.log('Stream URLs loaded:', streamUrls);
            } catch (error) {
                console.error('Failed to load stream configuration:', error);
            }
        }

        // Initialize streams
        function initializeStreams() {
            Object.keys(streamStates).forEach(streamId => {
                if (streamUrls[streamId]) {
                    startStream(streamId);
                }
            });
        }

        // Start a video stream
        function startStream(streamId) {
            const imgElement = document.getElementById(streamId);
            const statusElement = document.getElementById(`status${streamId.slice(-1)}`);
            const errorElement = document.getElementById(`error${streamId.slice(-1)}`);
            
            if (!streamUrls[streamId]) {
                showError(streamId, 'Stream URL not configured');
                return;
            }

            // Add timestamp to prevent caching
            const streamUrl = streamUrls[streamId] + '?t=' + new Date().getTime();
            
            imgElement.onload = function() {
                statusElement.textContent = 'Online';
                statusElement.className = 'stream-status status-online';
                hideError(streamId);
                streamStates[streamId] = true;
            };
            
            imgElement.onerror = function() {
                statusElement.textContent = 'Offline';
                statusElement.className = 'stream-status status-offline';
                showError(streamId, 'Failed to load stream. Check if Raspberry Pi is online.');
                streamStates[streamId] = false;
                
                // Retry after 5 seconds
                setTimeout(() => {
                    if (streamStates[streamId] === false) {
                        refreshStream(streamId);
                    }
                }, 5000);
            };
            
            imgElement.src = streamUrl;
        }

        // Stop a video stream
        function stopStream(streamId) {
            const imgElement = document.getElementById(streamId);
            const statusElement = document.getElementById(`status${streamId.slice(-1)}`);
            
            imgElement.src = '';
            statusElement.textContent = 'Offline';
            statusElement.className = 'stream-status status-offline';
            streamStates[streamId] = false;
            hideError(streamId);
        }

        // Toggle stream on/off
        function toggleStream(streamId) {
            if (streamStates[streamId]) {
                stopStream(streamId);
            } else {
                startStream(streamId);
            }
        }

        // Refresh a stream
        function refreshStream(streamId) {
            if (streamStates[streamId]) {
                stopStream(streamId);
                setTimeout(() => startStream(streamId), 500);
            } else {
                startStream(streamId);
            }
        }

        // Show error message
        function showError(streamId, message) {
            const errorElement = document.getElementById(`error${streamId.slice(-1)}`);
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        }

        // Hide error message
        function hideError(streamId) {
            const errorElement = document.getElementById(`error${streamId.slice(-1)}`);
            errorElement.style.display = 'none';
        }

        // Auto-refresh streams every 30 seconds if they're offline
        function autoRefresh() {
            Object.keys(streamStates).forEach(streamId => {
                if (!streamStates[streamId]) {
                    refreshStream(streamId);
                }
            });
        }

        // Motion detection functions
        let motionStates = {
            stream1: false,
            stream2: false,
            stream3: false
        };

        let viewStates = {
            stream1: false, // false = original, true = motion view
            stream2: false,
            stream3: false
        };

        // Toggle motion detection for a stream
        async function toggleMotionDetection(streamId) {
            const isActive = motionStates[streamId];
            const action = isActive ? 'stop' : 'start';
            
            try {
                const response = await fetch(`/api/motion/${streamId}/${action}`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    motionStates[streamId] = !isActive;
                    updateMotionUI(streamId);
                } else {
                    showError(streamId, `Failed to ${action} motion detection`);
                }
            } catch (error) {
                showError(streamId, `Error toggling motion detection: ${error.message}`);
            }
        }

        // Update motion detection UI
        function updateMotionUI(streamId) {
            const streamNumber = streamId.slice(-1);
            const buttonElement = document.getElementById(`motion${streamNumber}`);
            const statusElement = document.getElementById(`motion-status${streamNumber}`);
            const isActive = motionStates[streamId];
            
            if (isActive) {
                buttonElement.textContent = 'Stop Motion';
                buttonElement.classList.add('active');
                statusElement.textContent = 'Motion Detection: Active';
                statusElement.className = 'motion-status motion-active';
            } else {
                buttonElement.textContent = 'Start Motion';
                buttonElement.classList.remove('active');
                statusElement.textContent = 'Motion Detection: Inactive';
                statusElement.className = 'motion-status motion-inactive';
            }
        }

        // Check motion detection status for all streams
        async function checkMotionStatus() {
            try {
                const response = await fetch('/api/motion/');
                if (response.ok) {
                    const statusData = await response.json();
                    
                    Object.keys(statusData).forEach(streamId => {
                        const status = statusData[streamId];
                        const streamNumber = streamId.slice(-1);
                        const statusElement = document.getElementById(`motion-status${streamNumber}`);
                        
                        motionStates[streamId] = status.active;
                        updateMotionUI(streamId);
                        
                        // Update motion detection status
                        if (status.active && status.motion_detected) {
                            statusElement.textContent = 'Motion Detection: MOTION DETECTED!';
                            statusElement.className = 'motion-status motion-detected';
                        } else if (status.active) {
                            statusElement.textContent = 'Motion Detection: Active';
                            statusElement.className = 'motion-status motion-active';
                        }
                        
                        // Update motion view if active
                        if (viewStates[streamId] && status.active) {
                            refreshMotionView(streamId);
                        }
                    });
                }
            } catch (error) {
                console.error('Error checking motion status:', error);
            }
        }

        // Toggle between original and motion-processed view
        function toggleView(streamId) {
            const streamNumber = streamId.slice(-1);
            const viewButton = document.getElementById(`view${streamNumber}`);
            const imgElement = document.getElementById(streamId);
            
            viewStates[streamId] = !viewStates[streamId];
            
            if (viewStates[streamId]) {
                // Switch to motion view
                if (motionStates[streamId]) {
                    imgElement.src = `/motion_feed/${streamId}?t=${new Date().getTime()}`;
                    viewButton.textContent = 'Original View';
                    viewButton.classList.add('active');
                } else {
                    showError(streamId, 'Motion detection must be active to view motion feed');
                    viewStates[streamId] = false;
                }
            } else {
                // Switch back to original view
                if (streamUrls[streamId]) {
                    imgElement.src = streamUrls[streamId] + '?t=' + new Date().getTime();
                }
                viewButton.textContent = 'Motion View';
                viewButton.classList.remove('active');
            }
        }

        // Refresh motion view
        function refreshMotionView(streamId) {
            if (viewStates[streamId] && motionStates[streamId]) {
                const imgElement = document.getElementById(streamId);
                imgElement.src = `/motion_feed/${streamId}?t=${new Date().getTime()}`;
            }
        }

        // Initialize when page loads
        window.onload = async function() {
            await loadStreamConfig();
            initializeStreams();
            
            // Set up auto-refresh
            setInterval(autoRefresh, 30000);
            
            // Set up motion status checking
            setInterval(checkMotionStatus, 2000); // Check every 2 seconds
            
            // Set up motion view refresh for real-time bounding boxes
            setInterval(() => {
                Object.keys(viewStates).forEach(streamId => {
                    if (viewStates[streamId] && motionStates[streamId]) {
                        refreshMotionView(streamId);
                    }
                });
            }, 1000); // Refresh motion view every second
        };
    </script>
</body>
</html>"""
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.send_header('Content-Length', len(html_content.encode()))
        self.end_headers()
        self.wfile.write(html_content.encode())
    
    def serve_stream_config(self):
        """Serve the stream configuration as JSON"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        config_json = json.dumps(self.video_streams, indent=2)
        self.wfile.write(config_json.encode())

def main():
    """Main function to start the HTTP server"""
    # Load server configuration
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        PORT = config.get('server', {}).get('port', 8000)
        HOST = config.get('server', {}).get('host', '0.0.0.0')
    except:
        PORT = 8000
        HOST = '0.0.0.0'
    
    print(f"🚀 Starting Video Stream Server on {HOST}:{PORT}")
    print(f"📺 Open your browser and go to: http://localhost:{PORT}")
    print(f"🔧 Configure your Raspberry Pi stream URLs in config.json")
    print(f"⏹️  Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        with socketserver.TCPServer((HOST, PORT), VideoStreamHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")

if __name__ == "__main__":
    main()