#!/usr/bin/env python3
"""
MQTT Test Script for RTSP Stream Client
Sends test messages to simulate camera events and test dynamic UI updates
"""

import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime, timedelta
import random

# MQTT Configuration
BROKER_HOST = "10.0.4.40"
BROKER_PORT = 1883
CLIENT_ID = "rtsp_test_client"

# Camera configurations matching config.json
CAMERAS = [
    {"name": "piir - Shed", "type": "piir"},
    {"name": "picam - FrontDoor", "type": "picam"}, 
    {"name": "pipiw - BackDoor", "type": "pipiw"}
]

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connected to MQTT broker at {BROKER_HOST}:{BROKER_PORT}")
    else:
        print(f"❌ Failed to connect to MQTT broker. Return code: {rc}")

def on_publish(client, userdata, mid):
    print(f"📤 Message {mid} published successfully")

def generate_event_message(camera_name, camera_type):
    """Generate a test event message for a camera"""
    now = datetime.now()
    
    # Create realistic video filename
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    video_filename = f"{camera_type}_{timestamp}.mp4"
    
    event_data = {
        "type": "motion_detected",
        "camera_name": camera_name,
        "camera_type": camera_type,
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "video_path": f"/videos/{video_filename}",
        "confidence": random.uniform(0.7, 0.95),
        "duration": random.randint(5, 30),
        "viewed": False
    }
    
    return json.dumps(event_data, indent=2)

def send_test_messages(client):
    """Send test messages for each camera"""
    print("\n🧪 Starting MQTT test sequence...")
    
    for i, camera in enumerate(CAMERAS):
        camera_name = camera["name"]
        camera_type = camera["type"]
        
        print(f"\n📹 Testing camera {i+1}/3: {camera_name}")
        
        # Send event message
        topic = f"camera/{camera_type}/events"
        message = generate_event_message(camera_name, camera_type)
        
        print(f"📡 Publishing to topic: {topic}")
        print(f"📄 Message content:")
        print(message)
        
        result = client.publish(topic, message, qos=1)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"✅ Message queued for {camera_name}")
        else:
            print(f"❌ Failed to queue message for {camera_name}")
        
        # Wait between messages
        time.sleep(2)
    
    # Send a status update message
    print(f"\n📊 Sending status update...")
    status_topic = "rtsp_client/status"
    status_message = {
        "type": "client_status",
        "status": "running",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "active_cameras": len(CAMERAS),
        "test_sequence": "completed"
    }
    
    client.publish(status_topic, json.dumps(status_message, indent=2), qos=1)
    print(f"📤 Status update sent to {status_topic}")

def send_bulk_events(client, count=5):
    """Send multiple events to test UI updates with higher counts"""
    print(f"\n🔥 Sending {count} bulk events to test UI updates...")
    
    for i in range(count):
        # Pick random camera
        camera = random.choice(CAMERAS)
        camera_name = camera["name"]
        camera_type = camera["type"]
        
        # Vary the timestamp to test 24h filtering
        base_time = datetime.now()
        if i % 3 == 0:
            # Some events from earlier today
            event_time = base_time - timedelta(hours=random.randint(1, 12))
        else:
            # Recent events
            event_time = base_time - timedelta(minutes=random.randint(1, 60))
        
        event_data = {
            "type": "motion_detected",
            "camera_name": camera_name,
            "camera_type": camera_type,
            "timestamp": event_time.strftime("%Y-%m-%d %H:%M:%S"),
            "video_path": f"/videos/{camera_type}_{event_time.strftime('%Y%m%d_%H%M%S')}.mp4",
            "confidence": random.uniform(0.6, 0.98),
            "duration": random.randint(3, 45),
            "viewed": random.choice([True, False])  # Mix of viewed/unviewed
        }
        
        topic = f"camera/{camera_type}/events"
        message = json.dumps(event_data, indent=2)
        
        print(f"📡 Bulk event {i+1}/{count}: {camera_name} at {event_time.strftime('%H:%M:%S')}")
        client.publish(topic, message, qos=1)
        
        time.sleep(0.5)  # Shorter delay for bulk

def main():
    print("🚀 MQTT Test Script for RTSP Stream Client")
    print("=" * 50)
    print(f"🌐 Broker: {BROKER_HOST}:{BROKER_PORT}")
    print(f"📹 Testing {len(CAMERAS)} cameras")
    print("=" * 50)
    
    # Create MQTT client
    client = mqtt.Client(CLIENT_ID)
    client.on_connect = on_connect
    client.on_publish = on_publish
    
    try:
        # Connect to broker
        print(f"🔌 Connecting to MQTT broker...")
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        
        # Start the loop
        client.loop_start()
        
        # Wait for connection
        time.sleep(2)
        
        while True:
            print("\n" + "=" * 50)
            print("📋 Test Options:")
            print("1. Send single event per camera (3 messages)")
            print("2. Send bulk events (5 random events)")
            print("3. Send continuous events (every 10 seconds)")
            print("4. Send status ping")
            print("5. Exit")
            print("=" * 50)
            
            choice = input("Enter your choice (1-5): ").strip()
            
            if choice == "1":
                send_test_messages(client)
                
            elif choice == "2":
                send_bulk_events(client)
                
            elif choice == "3":
                print("🔄 Starting continuous event sending (Ctrl+C to stop)...")
                try:
                    while True:
                        camera = random.choice(CAMERAS)
                        topic = f"camera/{camera['type']}/events"
                        message = generate_event_message(camera["name"], camera["type"])
                        client.publish(topic, message, qos=1)
                        print(f"📡 Sent event for {camera['name']}")
                        time.sleep(10)
                except KeyboardInterrupt:
                    print("\n⏹️ Stopped continuous sending")
                    
            elif choice == "4":
                ping_message = {
                    "type": "ping",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "test_script"
                }
                client.publish("rtsp_client/ping", json.dumps(ping_message), qos=1)
                print("📤 Ping sent")
                
            elif choice == "5":
                print("👋 Exiting...")
                break
                
            else:
                print("❌ Invalid choice. Please enter 1-5.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        client.loop_stop()
        client.disconnect()
        print("🔌 Disconnected from MQTT broker")

if __name__ == "__main__":
    main()