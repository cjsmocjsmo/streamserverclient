#!/usr/bin/env python3
"""
Multi-camera MQTT test sender
"""

import paho.mqtt.client as mqtt
import json
from datetime import datetime
import time
import random

BROKER_HOST = "10.0.4.40"
BROKER_PORT = 1883

cameras = [
    {"name": "piir - Shed", "type": "piir"},
    {"name": "picam - FrontDoor", "type": "picam"},
    {"name": "pipiw - BackDoor", "type": "pipiw"}
]

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connected to MQTT broker")
    else:
        print(f"❌ Failed to connect. Return code: {rc}")

def on_publish(client, userdata, mid):
    print(f"📤 Message {mid} published")

def send_event(client, camera_name, camera_type):
    now = datetime.now()
    
    event_data = {
        "type": "motion_detected",
        "camera_name": camera_name,
        "camera_type": camera_type,
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "video_path": f"/videos/{camera_type}_{now.strftime('%Y%m%d_%H%M%S')}.mp4",
        "confidence": round(random.uniform(0.7, 0.95), 2),
        "duration": random.randint(10, 30),
        "viewed": False
    }
    
    topic = f"camera/{camera_type}/events"
    message = json.dumps(event_data, indent=2)
    
    print(f"📡 Sending event for {camera_name}")
    print(f"   Topic: {topic}")
    print(f"   Timestamp: {event_data['timestamp']}")
    
    result = client.publish(topic, message, qos=1)
    return result.rc == mqtt.MQTT_ERR_SUCCESS

client = mqtt.Client("multi_test_sender")
client.on_connect = on_connect
client.on_publish = on_publish

print("🧪 Multi-camera test sequence starting...")
print(f"🌐 Connecting to {BROKER_HOST}:{BROKER_PORT}")

try:
    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_start()
    
    time.sleep(2)
    
    print("\n🎬 Sending events for all cameras...")
    
    # Send one event for each camera
    for i, camera in enumerate(cameras):
        print(f"\n📹 Camera {i+1}/3: {camera['name']}")
        
        if send_event(client, camera["name"], camera["type"]):
            print("✅ Event sent successfully")
        else:
            print("❌ Failed to send event")
        
        time.sleep(2)
    
    print("\n🔥 Sending additional events for testing...")
    
    # Send a few more random events
    for i in range(3):
        camera = random.choice(cameras)
        print(f"\n📹 Additional event {i+1}: {camera['name']}")
        
        if send_event(client, camera["name"], camera["type"]):
            print("✅ Event sent successfully")
        else:
            print("❌ Failed to send event")
        
        time.sleep(1.5)
    
    print("\n✨ Test sequence completed!")
    time.sleep(2)
    
except Exception as e:
    print(f"❌ Error: {e}")
    
finally:
    client.loop_stop()
    client.disconnect()
    print("🔌 Disconnected from MQTT broker")