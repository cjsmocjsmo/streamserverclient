#!/bin/bash

# Quick MQTT Test Script for RTSP Stream Client
# Uses mosquitto_pub to send test messages

BROKER="10.0.4.40"
PORT="1883"

echo "🚀 Quick MQTT Test for RTSP Stream Client"
echo "========================================="
echo "🌐 Broker: $BROKER:$PORT"
echo ""

# Function to send a test event
send_event() {
    local camera_type=$1
    local camera_name=$2
    local topic="camera/$camera_type/events"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local video_file="${camera_type}_$(date '+%Y%m%d_%H%M%S').mp4"
    
    local message=$(cat <<EOF
{
  "type": "motion_detected",
  "camera_name": "$camera_name",
  "camera_type": "$camera_type",
  "timestamp": "$timestamp",
  "video_path": "/videos/$video_file",
  "confidence": 0.85,
  "duration": 15,
  "viewed": false
}
EOF
)
    
    echo "📡 Sending event for $camera_name..."
    echo "📍 Topic: $topic"
    
    mosquitto_pub -h "$BROKER" -p "$PORT" -t "$topic" -m "$message" -q 1
    
    if [ $? -eq 0 ]; then
        echo "✅ Event sent successfully"
    else
        echo "❌ Failed to send event"
    fi
    echo ""
}

# Check if mosquitto_pub is available
if ! command -v mosquitto_pub &> /dev/null; then
    echo "❌ mosquitto_pub not found. Please install mosquitto-clients:"
    echo "   sudo apt-get install mosquitto-clients"
    exit 1
fi

echo "🧪 Sending test events for all cameras..."
echo ""

# Send events for each camera
send_event "piir" "piir - Shed"
sleep 1

send_event "picam" "picam - FrontDoor" 
sleep 1

send_event "pipiw" "pipiw - BackDoor"
sleep 1

# Send a status message
echo "📊 Sending status update..."
status_message=$(cat <<EOF
{
  "type": "client_status",
  "status": "test_completed",
  "timestamp": "$(date '+%Y-%m-%d %H:%M:%S')",
  "active_cameras": 3,
  "test_source": "bash_script"
}
EOF
)

mosquitto_pub -h "$BROKER" -p "$PORT" -t "rtsp_client/status" -m "$status_message" -q 1

if [ $? -eq 0 ]; then
    echo "✅ Status update sent"
else
    echo "❌ Failed to send status update"
fi

echo ""
echo "🎉 Test sequence completed!"
echo ""
echo "💡 Tips:"
echo "   - Check your RTSP client UI for updated button counts"
echo "   - Click camera buttons to see new events in the events page"
echo "   - Run this script multiple times to add more test events"
echo ""
echo "🔄 To send continuous events, run:"
echo "   watch -n 10 '$0'"