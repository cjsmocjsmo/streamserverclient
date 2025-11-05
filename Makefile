# Makefile for RTSP Stream Client - C++ Version
# Requires: GTK3, GStreamer, jsoncpp

CXX = g++
TARGET = rtsp_stream_client
SOURCES = main.cpp

# Compiler flags
CXXFLAGS = -std=c++11 -Wall -Wextra -O2

# Package config for dependencies
PKG_CONFIG = pkg-config
GTK_FLAGS = $(shell $(PKG_CONFIG) --cflags --libs gtk+-3.0)
GST_FLAGS = $(shell $(PKG_CONFIG) --cflags --libs gstreamer-1.0 gstreamer-video-1.0)
JSON_FLAGS = $(shell $(PKG_CONFIG) --cflags --libs jsoncpp)

# All flags combined
ALL_FLAGS = $(CXXFLAGS) $(GTK_FLAGS) $(GST_FLAGS) $(JSON_FLAGS)

# Build target
$(TARGET): $(SOURCES)
	@echo "🔨 Building RTSP Stream Client (C++)..."
	@echo "📦 Checking dependencies..."
	@$(PKG_CONFIG) --exists gtk+-3.0 || (echo "❌ GTK3 development files not found. Install with: sudo apt install libgtk-3-dev" && exit 1)
	@$(PKG_CONFIG) --exists gstreamer-1.0 || (echo "❌ GStreamer development files not found. Install with: sudo apt install libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev" && exit 1)
	@$(PKG_CONFIG) --exists jsoncpp || (echo "❌ JsonCpp development files not found. Install with: sudo apt install libjsoncpp-dev" && exit 1)
	@echo "✅ All dependencies found"
	$(CXX) -o $(TARGET) $(SOURCES) $(ALL_FLAGS)
	@echo "✅ Build complete: $(TARGET)"

# Install dependencies (Debian/Ubuntu)
install-deps:
	@echo "📦 Installing dependencies..."
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
	@echo "✅ Dependencies installed"

# Clean build artifacts
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -f $(TARGET)
	@echo "✅ Clean complete"

# Run the application
run: $(TARGET)
	@echo "🚀 Running RTSP Stream Client..."
	./$(TARGET)

# Debug build
debug: CXXFLAGS += -g -DDEBUG
debug: $(TARGET)

# Show help
help:
	@echo "RTSP Stream Client - C++ Build System"
	@echo ""
	@echo "Available targets:"
	@echo "  make              - Build the application"
	@echo "  make install-deps - Install required dependencies"
	@echo "  make run          - Build and run the application"
	@echo "  make debug        - Build with debug symbols"
	@echo "  make clean        - Remove build artifacts"
	@echo "  make help         - Show this help"
	@echo ""
	@echo "Dependencies:"
	@echo "  - GTK3 development files"
	@echo "  - GStreamer development files"
	@echo "  - JsonCpp development files"

.PHONY: install-deps clean run debug help
.DEFAULT_GOAL := $(TARGET)