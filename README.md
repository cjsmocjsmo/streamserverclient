# RTSP Stream Client

A professional C++ GTK3 application for managing and viewing RTSP camera streams with real-time event management, MQTT integration, and SQLite database persistence.

## Features

- 🎥 **RTSP Stream Viewing**: Connect to and display RTSP camera streams using GStreamer
- 📱 **Multi-Camera Support**: Switch between multiple configured cameras
- 🗄️ **Event Management**: View and manage camera events with SQLite3 database persistence
- 📡 **MQTT Integration**: Real-time event processing and status updates via MQTT
- 🌑 **Dark Theme**: Professional dark UI with white text for optimal viewing
- 📊 **Database Persistence**: Events persist across application restarts
- 🔄 **Real-time Updates**: Live sidebar counts and event notifications
- 📋 **Paginated UI**: Clean page switching between main view and camera-specific event pages

## Quick Start

1. **Configure your cameras** in `config.json`:
   ```json
   {
     "cameras": [
       {
         "name": "piir - Shed",
         "url": "rtsp://10.0.4.67:8554/stream",
         "description": "Shed Camera"
       },
       {
         "name": "picam - FrontDoor", 
         "url": "rtsp://10.0.4.60:8554/stream",
         "description": "Front Door Camera"
       }
     ]
   }
   ```

2. **Build and run**:
   ```bash
   make
   ./rtsp_stream_client
   ```

## Dependencies

The application requires the following libraries and development packages:

### Core Dependencies
- **GTK3**: GUI framework (`libgtk-3-dev`)
- **GStreamer**: Video streaming and processing (`libgstreamer1.0-dev`, `libgstreamer-plugins-base1.0-dev`)
- **JsonCpp**: JSON configuration parsing (`libjsoncpp-dev`)
- **Paho MQTT C++**: MQTT client communication (`libpaho-mqtt-dev`)
- **SQLite3**: Database for event persistence (`libsqlite3-dev`)

### Build Tools
- **GCC/G++**: C++ compiler with C++17 support (`build-essential`)
- **Make**: Build system (`make`)
- **pkg-config**: Package configuration (`pkg-config`)

### Install on Debian/Ubuntu (AMD64):
```bash
sudo apt update
sudo apt install build-essential make pkg-config \
                 libgtk-3-dev \
                 libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
                 gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
                 gstreamer1.0-plugins-ugly gstreamer1.0-libav \
                 libjsoncpp-dev \
                 libpaho-mqtt-dev \
                 libsqlite3-dev
```

### Install on Fedora/CentOS/RHEL (AMD64):
```bash
sudo dnf install gcc-c++ make pkgconfig \
                 gtk3-devel \
                 gstreamer1-devel gstreamer1-plugins-base-devel \
                 gstreamer1-plugins-good gstreamer1-plugins-bad-free \
                 gstreamer1-plugins-ugly-free gstreamer1-libav \
                 jsoncpp-devel \
                 paho-c-devel \
                 sqlite-devel
```

### Install on Arch Linux (AMD64):
```bash
sudo pacman -S base-devel \
               gtk3 \
               gstreamer gst-plugins-base gst-plugins-good \
               gst-plugins-bad gst-plugins-ugly gst-libav \
               jsoncpp \
               paho-mqtt-cpp \
               sqlite
```

### Additional GStreamer Plugins (Recommended)
For full RTSP support and codec compatibility:
```bash
# Ubuntu/Debian
sudo apt install gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
                 gstreamer1.0-plugins-ugly gstreamer1.0-libav

# Fedora/RHEL
sudo dnf install gstreamer1-plugins-good gstreamer1-plugins-bad-free \
                 gstreamer1-plugins-ugly-free gstreamer1-libav

# Arch Linux
sudo pacman -S gst-plugins-good gst-plugins-bad gst-plugins-ugly gst-libav
```

### Verify Installation
Test that all dependencies are properly installed:
```bash
# Check GTK3
pkg-config --cflags gtk+-3.0

# Check GStreamer
pkg-config --cflags gstreamer-1.0

# Check JsonCpp
pkg-config --cflags jsoncpp

# Test RTSP pipeline
gst-launch-1.0 rtspsrc location=rtsp://example.com/stream ! fakesink
```

## Configuration

### Camera Setup
Edit `config.json` to configure your RTSP camera streams. Each camera requires:
- `name`: Display name for the camera
- `url`: RTSP stream URL (typically `rtsp://IP:PORT/stream`)
- `description`: Human-readable description

### MQTT Configuration
The application connects to an MQTT broker for real-time event processing:
- **Broker**: `tcp://10.0.4.40:1883`
- **Topics**: Subscribes to camera-specific topics for event notifications
- **Status Publishing**: Publishes connection status and application events

## Camera Software Requirements

This application is designed to work with **your custom camera software** that provides:
- **RTSP streams** on port 8554
- **MQTT event publishing** to the configured broker
- **Event format**: JSON messages with camera name, timestamp, and video file paths

### Expected RTSP Stream Format
```
rtsp://CAMERA_IP:8554/stream
```

### Expected MQTT Event Format
```json
{
  "camera_name": "piir - Shed",
  "date": "2025-11-05 06:40:48", 
  "video_path": "/path/to/video/file.mp4",
  "viewed": false
}
```

## Application Architecture

### Core Components
- **RTSPStreamClient**: Main application class managing UI and streaming
- **Database Layer**: SQLite3 integration for event persistence
- **MQTT Client**: Real-time event processing and status updates
- **GStreamer Pipeline**: RTSP stream decoding and display
- **Multi-Page UI**: Sidebar navigation with camera-specific event filtering

### Window Structure
- **Sidebar**: Camera navigation buttons with event counts
- **Main Page**: Video display area with camera controls
- **Events Pages**: Camera-specific event lists with tree view display
- **Status Indicators**: MQTT connection and application status

### Event Management
- Events are received via MQTT and stored in SQLite3 database
- Sidebar buttons show unviewed event counts and 24-hour totals
- Events pages display filtered lists per camera
- Tree view shows: Camera, Date, Video Path, Viewed status

## Building and Running

### Quick Build (AMD64/x86_64)
```bash
# Clone or download the project
cd streamserverclient

# Install dependencies (Ubuntu/Debian)
sudo apt update && sudo apt install build-essential make pkg-config \
                   libgtk-3-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
                   gstreamer1.0-plugins-good libjsoncpp-dev \
                   libpaho-mqtt-dev libsqlite3-dev

# Build the application
make clean
make

# Run the application
./rtsp_stream_client
```

### Build System
Uses a Makefile with automatic dependency detection:
```bash
make clean  # Clean build artifacts
make        # Build the application
```

### Cross-Platform Compatibility
- **Raspberry Pi ARM64**: Tested and working
- **AMD64/x86_64 Linux**: Fully supported
- **Other architectures**: Should work with proper dependencies

### Debug Mode
The application includes comprehensive debug output for troubleshooting:
- Database operations
- MQTT message processing  
- UI state changes
- GStreamer pipeline status

## Usage

1. **Launch Application**: Main page displays with video area
2. **Connect to Camera**: Click camera buttons to connect to RTSP streams
3. **View Events**: Click sidebar buttons to view camera-specific events
4. **Event Management**: Events update in real-time via MQTT
5. **Database Persistence**: All events persist across application restarts

## Network Requirements

- **RTSP Access**: Application must reach camera RTSP streams on port 8554
- **MQTT Broker**: Connection to MQTT broker at `10.0.4.40:1883`
- **UDP Protocol**: RTSP streams use UDP for reliable transmission
- **Local Network**: Cameras and broker should be on same network segment

## Troubleshooting

### Video Stream Issues
- Verify RTSP URL accessibility: `gst-launch-1.0 rtspsrc location=rtsp://IP:8554/stream ! fakesink`
- Check camera software is running and serving RTSP
- Ensure UDP port 8554 is open on camera devices

### MQTT Connectivity
- Test broker connection: `mosquitto_pub -h 10.0.4.40 -t test -m "hello"`
- Verify camera software is publishing to correct topics
- Check broker logs for connection issues

### Database Problems
- Database file: `rtsp_events.db` (created automatically)
- Check file permissions in application directory
- Debug output shows database operations

### Build Issues
- Verify all development packages are installed
- Check pkg-config output: `pkg-config --cflags gtk+-3.0`
- Ensure C++17 compiler support

## Technical Details

- **Language**: C++17 with GTK3 bindings
- **Video Backend**: GStreamer with RTSP source and GTK sink
- **Database**: SQLite3 with custom schema for event storage
- **Messaging**: Paho MQTT C++ client library
- **UI Framework**: GTK3 with custom dark theme CSS
- **Threading**: MQTT callbacks with GTK main thread integration

## License

This project is open source and available under the MIT License.