#!/bin/bash

# RTSP Stream Client Docker Deployment Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is installed and running
check_docker() {
    print_status "Checking Docker installation..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker service."
        exit 1
    fi
    
    print_success "Docker is installed and running"
}

# Function to check if Docker Compose is installed
check_docker_compose() {
    print_status "Checking Docker Compose installation..."
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "Docker Compose is available"
}

# Function to setup X11 forwarding for GUI
setup_x11() {
    print_status "Setting up X11 forwarding for GUI..."
    
    if [ -z "$DISPLAY" ]; then
        print_warning "No DISPLAY environment variable set. GUI may not work."
        export DISPLAY=:0
    fi
    
    # Allow local connections to X server (Linux only)
    if command -v xhost &> /dev/null; then
        xhost +local:docker 2>/dev/null || print_warning "Could not set xhost permissions"
        print_success "X11 forwarding configured"
    else
        print_warning "xhost not found. GUI forwarding may not work on this system."
    fi
}

# Function to build the Docker image
build_image() {
    print_status "Building Docker image..."
    
    if docker-compose build; then
        print_success "Docker image built successfully"
    else
        print_error "Failed to build Docker image"
        exit 1
    fi
}

# Function to start the application
start_application() {
    local mode=${1:-"normal"}
    
    print_status "Starting RTSP Stream Client..."
    
    case $mode in
        "gnome")
            print_status "Starting with GNOME desktop mode..."
            docker-compose run --rm rtsp-client --force-gnome
            ;;
        "dev")
            print_status "Starting development mode..."
            docker-compose --profile development up rtsp-client-dev
            ;;
        "headless")
            print_status "Starting headless mode..."
            docker-compose run --rm -e DISPLAY=:99 rtsp-client
            ;;
        *)
            print_status "Starting normal mode..."
            docker-compose up rtsp-client
            ;;
    esac
}

# Function to stop the application
stop_application() {
    print_status "Stopping RTSP Stream Client..."
    docker-compose down
    print_success "Application stopped"
}

# Function to show logs
show_logs() {
    print_status "Showing application logs..."
    docker-compose logs -f rtsp-client
}

# Function to clean up Docker resources
cleanup() {
    print_status "Cleaning up Docker resources..."
    docker-compose down --volumes --remove-orphans
    docker system prune -f
    print_success "Cleanup completed"
}

# Main script logic
case "${1:-help}" in
    "setup")
        check_docker
        check_docker_compose
        setup_x11
        build_image
        print_success "Setup completed! Use './deploy.sh start' to run the application."
        ;;
    "build")
        check_docker
        check_docker_compose
        build_image
        ;;
    "start")
        check_docker
        check_docker_compose
        setup_x11
        start_application "${2:-normal}"
        ;;
    "stop")
        stop_application
        ;;
    "restart")
        stop_application
        setup_x11
        start_application "${2:-normal}"
        ;;
    "logs")
        show_logs
        ;;
    "cleanup")
        cleanup
        ;;
    "help"|*)
        echo "RTSP Stream Client Docker Deployment Script"
        echo ""
        echo "Usage: $0 [COMMAND] [OPTIONS]"
        echo ""
        echo "Commands:"
        echo "  setup           - Initial setup (check dependencies, build image)"
        echo "  build           - Build Docker image only"
        echo "  start [MODE]    - Start the application"
        echo "  stop            - Stop the application"
        echo "  restart [MODE]  - Restart the application"
        echo "  logs            - Show application logs"
        echo "  cleanup         - Clean up Docker resources"
        echo "  help            - Show this help message"
        echo ""
        echo "Start Modes:"
        echo "  normal          - Standard mode (default)"
        echo "  gnome           - Force GNOME desktop mode"
        echo "  dev             - Development mode with live code mounting"
        echo "  headless        - Headless mode (no GUI)"
        echo ""
        echo "Examples:"
        echo "  $0 setup                    # Initial setup"
        echo "  $0 start                    # Start in normal mode"
        echo "  $0 start gnome             # Start with GNOME mode"
        echo "  $0 start dev               # Start in development mode"
        echo "  $0 logs                     # View logs"
        echo "  $0 stop                     # Stop application"
        ;;
esac