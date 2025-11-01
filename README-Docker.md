# RTSP Stream Client - Docker Deployment

This document describes how to deploy and run the RTSP Stream Client using Docker and Docker Compose with Debian as the base image.

## Prerequisites

- Docker (version 20.10 or later)
- Docker Compose (version 2.0 or later)
- X11 server (for GUI applications on Linux)

### Installing Docker on Debian/Ubuntu

```bash
# Update package index
sudo apt update

# Install Docker
sudo apt install docker.io docker-compose

# Add user to docker group (logout/login required)
sudo usermod -aG docker $USER

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker
```

## Quick Start

### 1. Setup and Build

```bash
# Make deployment script executable
chmod +x deploy.sh

# Run initial setup
./deploy.sh setup
```

### 2. Start the Application

```bash
# Start in normal mode
./deploy.sh start

# Start with GNOME desktop mode (for Debian Bookworm/GNOME)
./deploy.sh start gnome

# Start in development mode
./deploy.sh start dev

# Start in headless mode (no GUI)
./deploy.sh start headless
```

### 3. View Logs

```bash
./deploy.sh logs
```

### 4. Stop the Application

```bash
./deploy.sh stop
```

## Manual Docker Commands

If you prefer to use Docker commands directly:

### Build the Image

```bash
docker-compose build
```

### Run with GUI (Linux)

```bash
# Allow X11 forwarding
xhost +local:docker

# Run the application
docker-compose up rtsp-client
```

### Run in Headless Mode

```bash
docker-compose run --rm -e DISPLAY=:99 rtsp-client
```

### Run with GNOME Mode

```bash
docker-compose run --rm rtsp-client --force-gnome
```

## Configuration

### Camera Configuration

Edit the `config.json` file to configure your RTSP camera streams:

```json
{
  "streams": {
    "stream1": {
      "name": "Camera 1",
      "url": "rtsp://your-camera-ip:8554/stream",
      "fallback_url": "http://fallback-url",
      "description": "Camera description"
    }
  }
}
```

### Environment Variables

You can override environment variables in the `docker-compose.yml` file:

```yaml
environment:
  - DISPLAY=${DISPLAY:-:99}
  - QT_QPA_PLATFORM=xcb
  - QT_QPA_PLATFORMTHEME=gtk3
```

## Desktop Environment Support

The application automatically detects the desktop environment and adjusts accordingly:

- **GNOME** (Debian Bookworm): Uses specific window management
- **Other DEs**: Uses standard window management
- **Force Mode**: Use `--force-gnome` flag to force GNOME mode

## Troubleshooting

### GUI Not Displaying

1. **Check X11 forwarding:**
   ```bash
   echo $DISPLAY
   xhost +local:docker
   ```

2. **Test X11 connection:**
   ```bash
   docker run --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:rw debian:bookworm-slim xeyes
   ```

3. **Use headless mode if GUI fails:**
   ```bash
   ./deploy.sh start headless
   ```

### Network Issues

1. **Check camera connectivity:**
   ```bash
   # Test from host
   ffprobe rtsp://your-camera-ip:8554/stream
   
   # Test from container
   docker-compose exec rtsp-client ffprobe rtsp://your-camera-ip:8554/stream
   ```

2. **Use host networking:**
   The compose file uses `network_mode: host` for direct network access.

### Permission Issues

1. **Docker permissions:**
   ```bash
   sudo usermod -aG docker $USER
   # Logout and login again
   ```

2. **X11 permissions:**
   ```bash
   xhost +local:docker
   ```

## Development Mode

For live development with code changes:

```bash
# Start development mode
./deploy.sh start dev

# This mounts your source code into the container
# Changes to streamserverclient.py will be reflected immediately
```

## Container Management

### View Running Containers

```bash
docker ps
```

### Access Container Shell

```bash
docker-compose exec rtsp-client bash
```

### View Container Logs

```bash
docker-compose logs rtsp-client
```

### Clean Up Resources

```bash
# Stop and remove containers
./deploy.sh cleanup

# Or manually
docker-compose down --volumes --remove-orphans
docker system prune -f
```

## Advanced Configuration

### Custom Dockerfile

To modify the container image, edit the `Dockerfile`:

- Change base image
- Add additional packages
- Modify environment setup

### Custom Compose Configuration

Edit `docker-compose.yml` to:

- Add volume mounts
- Modify environment variables
- Change network configuration
- Add additional services

### Hardware Acceleration

The compose file includes GPU device mounting for hardware acceleration:

```yaml
devices:
  - /dev/dri:/dev/dri
```

## Security Considerations

- The container runs as a non-root user (`streamuser`)
- X11 forwarding requires host access (security trade-off for GUI)
- Network access is required for RTSP streams
- Consider using VPN for remote camera access

## Support

For issues and questions:

1. Check container logs: `./deploy.sh logs`
2. Test with headless mode: `./deploy.sh start headless`
3. Verify camera connectivity from host
4. Check Docker and X11 setup