# Raspberry Pi Video Stream Server with Motion Detection

A minimal HTTP server that displays three video streams from remote Raspberry Pi devices using HTML, CSS, and JavaScript, with integrated OpenCV motion detection for human-sized objects.

## Features

- 📺 Display up to 3 video streams simultaneously
- 🎯 **Motion Detection**: OpenCV-based motion detection for human-sized objects
- � **Bounding Boxes**: Visual rectangles drawn around detected motion
- �🔄 Auto-refresh offline streams every 30 seconds
- 📱 Responsive design that works on mobile and desktop
- ⚙️ Easy configuration via JSON file
- 🎛️ Individual stream controls (toggle, refresh, motion detection, view toggle)
- 🔍 Real-time connection status indicators
- 🚨 Motion detection alerts with visual indicators
- 👁️ **Dual View Modes**: Switch between original and motion-processed feeds
- ❌ Error handling and retry mechanisms

## Quick Start

1. **Install dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Configure your Raspberry Pi stream URLs** in `config.json`:
   ```json
   {
     "streams": {
       "stream1": {
         "name": "Raspberry Pi 1 - Living Room",
         "url": "http://192.168.1.100:8080/stream",
         "description": "Main living room camera"
       }
     }
   }
   ```

3. **Run the server**:
   ```bash
   python3 streamserverclient.py
   ```

4. **Open your browser** and go to: `http://localhost:8000`

5. **Enable motion detection**: Click the "Start Motion" button for any stream to begin detecting human-sized objects

## Motion Detection

### Features
- **Human-sized object detection**: Optimized for detecting people (not small animals or objects)
- **Visual bounding boxes**: Red rectangles drawn around detected motion with area information
- **Background subtraction**: Uses MOG2 algorithm for robust motion detection
- **Configurable sensitivity**: Adjustable thresholds for different environments
- **Real-time alerts**: Visual indicators when motion is detected
- **Dual view modes**: Switch between original video and motion-processed feed
- **Live overlays**: Timestamp, status, and detection information overlaid on video
- **Individual control**: Enable/disable motion detection per stream

### How It Works
1. **Background Learning**: The system learns the background of each video stream
2. **Motion Analysis**: Detects moving objects and filters by size and aspect ratio
3. **Human Detection**: Focuses on objects with human-like proportions (height > width)
4. **Bounding Box Drawing**: Draws red rectangles around detected motion with area labels
5. **Real-time Processing**: Motion processing and overlay generation in real-time
6. **View Toggle**: Switch between original video and motion-processed feed with overlays
7. **Status Updates**: Motion status updates every 2 seconds, video refreshes every second

### API Endpoints
- `GET /api/motion/` - Get motion status for all streams
- `GET /api/motion/{stream_id}/status` - Get motion status for specific stream
- `POST /api/motion/{stream_id}/start` - Start motion detection for stream
- `POST /api/motion/{stream_id}/stop` - Stop motion detection for stream
- `GET /motion_feed/{stream_id}` - Get processed video frame with bounding boxes

## Configuration

### Dependencies
Install required Python packages:
```bash
pip3 install opencv-python numpy requests
```

Or use the requirements file:
```bash
pip3 install -r requirements.txt
```

### Stream URLs
Edit `config.json` to set your Raspberry Pi stream URLs. Common formats:
- **Motion JPEG**: `http://PI_IP:8080/stream`
- **MJPEG streamer**: `http://PI_IP:8080/?action=stream`
- **VLC HTTP**: `http://PI_IP:8080/stream.mjpeg`

### Server Settings
You can also configure the server host and port in `config.json`:
```json
{
  "server": {
    "port": 8000,
    "host": "0.0.0.0"
  }
}
```

## Raspberry Pi Setup

To set up video streaming on your Raspberry Pi devices:

### Option 1: Using Motion
```bash
sudo apt update
sudo apt install motion
sudo nano /etc/motion/motion.conf
```

Key settings in motion.conf:
```
daemon on
webcontrol_localhost off
webcontrol_port 8080
stream_localhost off
stream_port 8081
```

Start Motion:
```bash
sudo systemctl start motion
sudo systemctl enable motion
```

### Option 2: Using MJPG-streamer
```bash
sudo apt update
sudo apt install cmake libjpeg8-dev gcc g++
git clone https://github.com/jacksonliam/mjpg-streamer.git
cd mjpg-streamer/mjpg-streamer-experimental
make
sudo make install
```

Run MJPG-streamer:
```bash
mjpg_streamer -i "input_uvc.so -d /dev/video0 -r 640x480 -f 10" -o "output_http.so -p 8080 -w /usr/local/share/mjpg-streamer/www"
```

## Network Requirements

- All Raspberry Pi devices should be on the same network as the server
- Ensure firewall allows HTTP traffic on the configured ports
- For external access, configure port forwarding on your router

## Troubleshooting

### Stream Not Loading
1. Check if the Raspberry Pi is online: `ping PI_IP_ADDRESS`
2. Verify the stream URL in a browser: `http://PI_IP:8080/stream`
3. Check firewall settings on both server and Pi
4. Ensure the camera service is running on the Pi

### Motion Detection Issues
- **High CPU usage**: Motion detection is CPU-intensive; consider reducing resolution or frame rate
- **False positives**: Adjust motion detection parameters in the code (`min_contour_area`, `max_contour_area`)
- **Not detecting people**: Ensure good lighting and check if the stream resolution is adequate
- **Detection too sensitive**: Increase `min_contour_area` or `motion_threshold` values

### Performance Issues
- Reduce video resolution on the Raspberry Pi
- Lower the frame rate (fps)
- Ensure good network connectivity
- Consider using a wired connection for better stability

### Common Raspberry Pi Stream URLs
- **Motion**: `http://PI_IP:8081`
- **MJPG-streamer**: `http://PI_IP:8080/?action=stream`
- **VLC**: `http://PI_IP:8080/stream.mjpeg`
- **RPiCam Web Interface**: `http://PI_IP/html/cam_pic_new.php`

## Technical Details

- Built with Python's built-in `http.server` module
- No external dependencies required
- Uses MJPEG streaming for real-time video
- Responsive CSS Grid layout
- JavaScript handles stream management and error handling

## License

This project is open source and available under the MIT License.