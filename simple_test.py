#!/usr/bin/env python3
"""
Simple MQTT test message sender
"""

import paho.mqtt.client as mqtt
import json
from datetime import datetime
import time

BROKER_HOST = "10.0.4.40"
BROKER_PORT = 1883

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connected to MQTT broker")
    else:
        print(f"❌ Failed to connect. Return code: {rc}")

def on_publish(client, userdata, mid):
    print(f"📤 Message {mid} published successfully")

# Create event message
event_data = {
    "type": "motion_detected",
    "camera_name": "piir - Shed", 
    "camera_type": "piir",
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "video_path": f"/videos/piir_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4",
    "confidence": 0.92,
    "duration": 15,
    "viewed": False
}

client = mqtt.Client("test_sender")
client.on_connect = on_connect
client.on_publish = on_publish

print("🧪 Sending single test event...")
print(f"🌐 Connecting to {BROKER_HOST}:{BROKER_PORT}")

try:
    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_start()
    
    time.sleep(2)  # Wait for connection
    
    topic = "camera/piir/events"
    message = json.dumps(event_data, indent=2)
    
    print(f"📡 Publishing to: {topic}")
    print(f"📄 Message: {message}")
    
    result = client.publish(topic, message, qos=1)
    
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print("✅ Message queued successfully")
        time.sleep(2)  # Wait for delivery
    else:
        print(f"❌ Failed to publish: {result.rc}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    
finally:
    client.loop_stop()
    client.disconnect()
    print("🔌 Disconnected")