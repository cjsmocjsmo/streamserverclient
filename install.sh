#!/bin/bash
# Installation script for RTSP Video Stream Client
# Prioritizes Debian packages over pip3

echo "🎥 RTSP Video Stream Client - Installation Script"
echo "=================================================="

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a Debian package is available
package_available() {
    apt-cache show "$1" >/dev/null 2>&1
}

# Check if we're on a Debian-based system
if command_exists apt; then
    echo "✅ Debian-based system detected"
    
    # Update package list
    echo "📦 Updating package list..."
    sudo apt update
    
    # Check and install dependencies
    packages_to_install=""
    pip_packages=""
    
    # Check PyQt6
    if package_available python3-pyqt6; then
        echo "✅ python3-pyqt6 available in repositories"
        packages_to_install="$packages_to_install python3-pyqt6"
    else
        echo "⚠️  python3-pyqt6 not available, will use pip3"
        pip_packages="$pip_packages PyQt6"
    fi
    
    # Check OpenCV
    if package_available python3-opencv; then
        echo "✅ python3-opencv available in repositories"
        packages_to_install="$packages_to_install python3-opencv"
    else
        echo "⚠️  python3-opencv not available, will use pip3"
        pip_packages="$pip_packages opencv-python"
    fi
    
    # Check NumPy
    if package_available python3-numpy; then
        echo "✅ python3-numpy available in repositories"
        packages_to_install="$packages_to_install python3-numpy"
    else
        echo "⚠️  python3-numpy not available, will use pip3"
        pip_packages="$pip_packages numpy"
    fi
    
    # Install Debian packages
    if [ -n "$packages_to_install" ]; then
        echo "📦 Installing Debian packages:$packages_to_install"
        sudo apt install -y $packages_to_install
    fi
    
    # Install pip packages if needed
    if [ -n "$pip_packages" ]; then
        echo "🐍 Installing pip packages:$pip_packages"
        pip3 install $pip_packages
    fi
    
else
    echo "⚠️  Non-Debian system detected, using pip3 for all packages"
    pip3 install -r requirements.txt
fi

echo ""
echo "✅ Installation complete!"
echo "🚀 Run the application with: python3 streamserverclient.py"