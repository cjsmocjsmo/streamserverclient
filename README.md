# RTSP Video Stream Client (PyQt6)

A desktop application built with PyQt6 for displaying three RTSP video streams from IP cameras, Raspberry Pi devices, or other RTSP sources.

## Features

- 🎥 **Desktop Application**: Native PyQt6 GUI with professional dark theme
- 📺 **Triple Stream Display**: View up to 3 RTSP streams simultaneously
- � **RTSP Protocol Support**: Compatible with IP cameras, Raspberry Pi, and RTSP servers
- ⚙️ **Individual Stream Controls**: Connect/disconnect and configure each stream independently
- 🎛️ **Settings Dialog**: Easy configuration of stream names and RTSP URLs
- � **Real-time Status**: Live connection status with color-coded indicators
- 💾 **Configuration Persistence**: Automatically saves and loads stream settings
- 🎨 **Modern UI**: Professional dark theme with responsive layout
- 🔧 **Global Controls**: Connect/disconnect all streams with single click

## Quick Start

### Option 1: Automated Installation (Recommended)
```bash
chmod +x install.sh
./install.sh
```

### Option 2: Manual Installation

1. **Install dependencies using Debian packages** (recommended):
   ```bash
   # Update package list
   sudo apt update
   
   # Install PyQt6 and OpenCV from Debian repositories
   sudo apt install python3-pyqt6 python3-opencv python3-numpy
   ```

   **Alternative - if packages not available in your Debian version:**
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   python3 streamserverclient.py
   ```

3. **Configure RTSP streams**: 
   - Click "Settings" on each stream widget
   - Enter stream name and RTSP URL
   - Click "OK" to save

4. **Connect streams**: Click "Connect" or use "Connect All" button

## RTSP URL Examples
## RTSP URL Examples

### IP Cameras
```
rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0
rtsp://192.168.1.100:554/stream1
rtsp://user:pass@camera.local/live/main
```

### Raspberry Pi with RTSP Server
```
rtsp://192.168.1.100:8554/stream
rtsp://pi:raspberry@raspberrypi.local:8554/camera
```

### VLC RTSP Stream
```
rtsp://192.168.1.100:8080/stream.sdp
```

## Configuration

The application automatically creates and manages a `rtsp_config.json` file:

```json
{
    "streams": {
        "stream1": {
            "name": "Front Door Camera",
            "url": "rtsp://admin:password@192.168.1.100:554/stream1"
        },
        "stream2": {
            "name": "Back Yard Camera", 
            "url": "rtsp://admin:password@192.168.1.101:554/stream1"
        },
        "stream3": {
            "name": "Garage Camera",
            "url": "rtsp://admin:password@192.168.1.102:554/stream1"
        }
    }
}
```

## Technical Details

### Dependencies
- **PyQt6**: Modern GUI framework
- **OpenCV**: Video processing and RTSP handling
- **NumPy**: Array operations for video frames

### Installation Methods

**Preferred - Debian/Ubuntu packages:**
```bash
sudo apt install python3-pyqt6 python3-opencv python3-numpy
```

**Alternative - pip3 (if not available in repositories):**
```bash
pip3 install PyQt6 opencv-python numpy
```

### Architecture
- **Threaded Processing**: Each stream runs in its own thread for smooth performance
- **Signal-Slot Communication**: Qt signals for thread-safe UI updates
- **Automatic Reconnection**: Streams automatically retry on connection loss
- **Memory Management**: Proper cleanup and resource management

### Performance Optimization
- **Buffer Management**: Minimal buffering for real-time display
- **Frame Scaling**: Automatic resize for optimal display
- **CPU Efficient**: Multi-threaded processing prevents UI blocking

## Controls

### Individual Stream Controls
- **Connect/Disconnect**: Toggle RTSP connection for each stream
- **Settings**: Configure stream name and RTSP URL

### Global Controls
- **Connect All**: Start all three streams simultaneously  
- **Disconnect All**: Stop all streams at once
- **Save Config**: Persist current settings to configuration file

### Status Indicators
- 🟢 **Connected/Streaming**: Stream is active and receiving video
- 🟡 **Connecting**: Attempting to establish RTSP connection
- 🔴 **Disconnected/Error**: Stream is offline or failed to connect

## Troubleshooting

### Connection Issues
- Verify RTSP URL format and credentials
- Check network connectivity to camera/device
- Ensure RTSP server is running on target device
- Try different RTSP URL formats for your specific camera

### Performance Issues
- Reduce video resolution on camera/source
- Close unnecessary applications to free CPU/memory
- Check network bandwidth for multiple streams

### Common RTSP URL Patterns
- **Default RTSP port**: 554
- **Authentication**: `rtsp://username:password@ip:port/path`
- **No auth**: `rtsp://ip:port/path`
- **Custom ports**: `rtsp://ip:8554/stream`

## Camera Setup

### Raspberry Pi RTSP Server
```bash
# Install GStreamer RTSP server
sudo apt update
sudo apt install gstreamer1.0-rtsp

# Run RTSP server
gst-launch-1.0 -v rpicamsrc ! video/x-raw,width=640,height=480,framerate=30/1 ! \
videoconvert ! x264enc tune=zerolatency bitrate=500 speed-preset=superfast ! \
rtph264pay config-interval=1 pt=96 ! gdppay ! tcpserversink host=0.0.0.0 port=8554
```

### IP Camera Configuration
- Enable RTSP in camera settings
- Set appropriate resolution and bitrate
- Configure authentication if required
- Note the RTSP stream path from camera documentation

## System Requirements

- **Python 3.8+**
- **Debian/Ubuntu packages** (recommended):
  - `python3-pyqt6` - Qt6 GUI framework
  - `python3-opencv` - Computer vision and video processing
  - `python3-numpy` - Numerical computing
- **Qt6 libraries** (automatically included with python3-pyqt6)
- **Network access** to RTSP sources
- **Sufficient CPU/RAM** for multiple video streams

### Package Installation Commands

**Debian/Ubuntu/Raspberry Pi OS:**
```bash
sudo apt update
sudo apt install python3-pyqt6 python3-opencv python3-numpy
```

**Fallback (pip3) if packages unavailable:**
```bash
pip3 install PyQt6>=6.5.0 opencv-python>=4.8.0 numpy>=1.24.0
```

## License

This project is open source and available under the MIT License.