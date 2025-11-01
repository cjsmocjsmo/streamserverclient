# Use Debian bookworm as base image
FROM debian:bookworm-slim

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Set timezone
ENV TZ=UTC

# Update package list and install system dependencies
RUN apt-get update && apt-get install -y \
    # Python and core tools
    python3 \
    python3-dev \
    python3-venv \
    # PyQt6 and GUI dependencies (all PyQt6 components)
    python3-pyqt6 \
    python3-pyqt6.qtcore \
    python3-pyqt6.qtgui \
    python3-pyqt6.qtwidgets \
    python3-pyqt6.qtnetwork \
    # Python scientific libraries
    python3-numpy \
    python3-opencv \
    # Additional Python libraries for the application
    python3-json5 \
    python3-subprocess32 || true \
    # X11 and display dependencies
    xvfb \
    x11-apps \
    x11-utils \
    x11-xserver-utils \
    dbus-x11 \
    # Media and streaming dependencies
    ffmpeg \
    ffprobe \
    # System libraries for Qt and OpenGL
    libgl1-mesa-glx \
    libglib2.0-0 \
    libfontconfig1 \
    libxrender1 \
    libdbus-1-3 \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    # Audio support (for potential future use)
    pulseaudio \
    alsa-utils \
    # Network utilities
    curl \
    wget \
    net-tools \
    # Clean up to reduce image size
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create application directory
WORKDIR /app

# Create a non-root user for running the application
RUN useradd -m -s /bin/bash streamuser && \
    mkdir -p /home/streamuser/.config && \
    chown -R streamuser:streamuser /home/streamuser && \
    chown -R streamuser:streamuser /app

# Copy application files
COPY --chown=streamuser:streamuser streamserverclient.py /app/
COPY --chown=streamuser:streamuser config.json /app/

# Set up environment variables for Qt and X11
ENV DISPLAY=:99
ENV QT_QPA_PLATFORM=xcb
ENV QT_QPA_PLATFORMTHEME=gtk3
ENV QT_X11_NO_MITSHM=1
ENV QT_SCALE_FACTOR=1
ENV QT_AUTO_SCREEN_SCALE_FACTOR=0

# Create startup script with better error handling
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "=== RTSP Stream Client Container Starting ==="\n\
\n\
# Check if running with GUI (DISPLAY forwarded from host)\n\
if [ -n "$DISPLAY" ] && [ "$DISPLAY" != ":99" ]; then\n\
    echo "Using host DISPLAY: $DISPLAY"\n\
    # Test X11 connection\n\
    if ! xdpyinfo >/dev/null 2>&1; then\n\
        echo "Warning: Cannot connect to X11 display. GUI may not work."\n\
        echo "Make sure to run: xhost +local:docker"\n\
    fi\n\
else\n\
    # Start Xvfb for headless operation\n\
    echo "Starting Xvfb for headless operation..."\n\
    Xvfb :99 -screen 0 1600x900x24 -ac +extension GLX +render -noreset &\n\
    export DISPLAY=:99\n\
    sleep 3\n\
    echo "Xvfb started on display :99"\n\
fi\n\
\n\
# Navigate to app directory\n\
cd /app\n\
\n\
# Start the application with any passed arguments\n\
echo "Starting RTSP Stream Client..."\n\
echo "Arguments: $@"\n\
\n\
exec python3 streamserverclient.py "$@"\n\
' > /app/start.sh && chmod +x /app/start.sh

# Switch to non-root user
USER streamuser

# Expose port for any web interface
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD pgrep -f streamserverclient.py || exit 1

# Default command
CMD ["/app/start.sh"]