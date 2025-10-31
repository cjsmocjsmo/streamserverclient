#!/usr/bin/env python3
"""
Minimal HTTP Server for displaying three video streams from remote Raspberry Pi devices.
"""

import http.server
import socketserver
import os
import json
from urllib.parse import urlparse, parse_qs

class VideoStreamHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Load video stream URLs from config file
        self.video_streams = self.load_config()
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
        else:
            super().do_GET()
    
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
        }
        
        .btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            margin: 0 5px;
            font-size: 14px;
        }
        
        .btn:hover {
            background: #0056b3;
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
            </div>
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
            </div>
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
            </div>
            <div id="error3" class="error-message" style="display: none;"></div>
        </div>
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

        // Initialize when page loads
        window.onload = async function() {
            await loadStreamConfig();
            initializeStreams();
            
            // Set up auto-refresh
            setInterval(autoRefresh, 30000);
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