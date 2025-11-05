# RTSP Stream Client - C++ Version

A high-performance RTSP video stream client built with C++, GTK3, and GStreamer. This application provides a clean GUI for viewing multiple RTSP camera streams with embedded video display.

## Features

- **Multi-camera support**: Load multiple camera configurations from JSON
- **Embedded video display**: Uses GTK3 + GStreamer integration with gtksink
- **RTSP streaming**: Full support for RTSP protocol with TCP transport
- **Test pattern**: Built-in test pattern for verification
- **Clean resource management**: Proper pipeline cleanup and memory management
- **Native performance**: Direct GStreamer C API for optimal performance

## Architecture

This C++ implementation solves the Python GStreamer binding issues by using:

- **Direct GStreamer C API**: No binding layer overhead
- **Native GTK3**: Seamless widget integration
- **Manual memory management**: Full control over resource lifecycle
- **Native threading**: No GIL or Python threading complications

## Prerequisites

### System Requirements
- Linux with GTK3 support
- GStreamer 1.0 or later
- C++11 compatible compiler

### Dependencies
```bash
# Install all dependencies at once
make install-deps

# Or install manually:
sudo apt update
sudo apt install -y \
    build-essential \
    pkg-config \
    libgtk-3-dev \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-good1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    libjsoncpp-dev \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav
```

## Building

```bash
# Build the application
make

# Build with debug symbols
make debug

# Clean build artifacts
make clean
```

## Configuration

Create or edit `config.json`:

```json
{
  "cameras": [
    {
      "name": "Camera 1",
      "url": "rtsp://10.0.4.67:8554/stream",
      "description": "Main camera"
    },
    {
      "name": "Camera 2", 
      "url": "rtsp://10.0.4.60:8554/stream",
      "description": "Secondary camera"
    }
  ]
}
```

## Running

```bash
# Run directly
./rtsp_stream_client

# Or use make
make run
```

## Usage

1. **Start the application**: Launch with `./rtsp_stream_client`
2. **Test functionality**: Click "Test Pattern" to verify video display
3. **Connect to cameras**: Click any camera button to start streaming
4. **Switch cameras**: Click different camera buttons to switch streams
5. **Disconnect**: Click "Disconnect" to stop current stream

## Troubleshooting

### Common Issues

**Build errors about missing packages:**
```bash
make install-deps
```

**Video doesn't display:**
- Check that your RTSP URLs are correct
- Verify cameras are accessible: `vlc rtsp://your.camera.url`
- Check GStreamer plugins: `gst-inspect-1.0 rtspsrc`

**Application crashes:**
- Run with debug build: `make debug && ./rtsp_stream_client`
- Check GStreamer debug: `GST_DEBUG=3 ./rtsp_stream_client`

### Testing RTSP Streams

Test your RTSP streams work:
```bash
# Test with GStreamer directly
gst-launch-1.0 rtspsrc location=rtsp://your.camera.url protocols=tcp ! \
    rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink

# Test with VLC
vlc rtsp://your.camera.url
```

## Development

### Code Structure

- `main.cpp`: Complete application implementation
- `RTSPStreamClient` class: Main application logic
- Static callbacks: GTK and GStreamer event handling
- `CameraConfig` struct: Camera configuration data

### Key Components

1. **UI Setup**: GTK3 window with video area and camera buttons
2. **Video Integration**: gtksink widget embedded in GTK container
3. **Pipeline Management**: GStreamer pipeline creation and state management
4. **Event Handling**: GTK callbacks and GStreamer bus messages
5. **Resource Management**: Proper cleanup and memory management

### Debugging

Enable GStreamer debug output:
```bash
export GST_DEBUG=rtspsrc:4,rtsp:3
./rtsp_stream_client
```

Build with debug symbols:
```bash
make debug
gdb ./rtsp_stream_client
```

## Comparison with Python Version

| Aspect | Python | C++ |
|--------|--------|-----|
| Performance | Slower (binding overhead) | Native speed |
| Memory | Garbage collected | Manual management |
| Threading | GIL limitations | Native threads |
| GStreamer | PyGObject bindings | Direct C API |
| State management | Binding issues | Direct control |
| Build complexity | Simple | Requires compilation |

The C++ version resolves the Python GStreamer binding issues that prevented RTSP streams from reaching the PLAYING state.

## License

This project is part of the streamserverclient repository.