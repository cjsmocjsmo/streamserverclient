# MQTT Integration Guide for RTSP Client

## Overview

This guide shows how to integrate MQTT messaging into your C++ RTSP client using the **Paho MQTT C++** library. This enables:

- **Camera Status Updates**: Publish when cameras connect/disconnect
- **Stream Statistics**: Real-time FPS and quality metrics  
- **Remote Control**: Control cameras via MQTT commands
- **Event Notifications**: Motion detection, alerts, etc.

## 📦 Installation

The Makefile already includes MQTT support. Dependencies are installed with:

```bash
make install-deps
```

Or manually:
```bash
sudo apt install libpaho-mqttpp-dev libpaho-mqttpp3-1 libpaho-mqtt-dev
```

## 🔧 Quick Integration Steps

### 1. Add MQTT Headers to main.cpp

```cpp
#include "mqtt/async_client.h"
#include <memory>
```

### 2. Add MQTT Manager to RTSPStreamClient Class

```cpp
class RTSPStreamClient {
private:
    // Existing members...
    std::unique_ptr<mqtt::async_client> mqtt_client_;
    std::string mqtt_server_;
    std::string client_id_;
    
public:
    // Add MQTT initialization
    void init_mqtt(const std::string& broker_url = "tcp://localhost:1883") {
        client_id_ = "rtsp_client_" + std::to_string(getpid());
        mqtt_client_ = std::make_unique<mqtt::async_client>(broker_url, client_id_);
        
        // Set up callbacks
        mqtt_client_->set_connection_lost_handler([](const std::string& cause) {
            std::cout << "🔌 MQTT connection lost: " << cause << std::endl;
        });
        
        mqtt_client_->set_message_callback([this](mqtt::const_message_ptr msg) {
            handle_mqtt_message(msg);
        });
        
        connect_mqtt();
    }
};
```

### 3. Add MQTT Methods

```cpp
private:
    void connect_mqtt() {
        try {
            mqtt::connect_options conn_opts;
            conn_opts.set_keep_alive_interval(20);
            conn_opts.set_clean_session(true);
            
            auto token = mqtt_client_->connect(conn_opts);
            token->wait();
            
            // Subscribe to control topics
            mqtt_client_->subscribe("rtsp_client/control/+", 1);
            std::cout << "✅ MQTT connected and subscribed" << std::endl;
        } catch (const mqtt::exception& exc) {
            std::cerr << "❌ MQTT connection failed: " << exc.what() << std::endl;
        }
    }
    
    void handle_mqtt_message(mqtt::const_message_ptr msg) {
        std::string topic = msg->get_topic();
        std::string payload = msg->to_string();
        
        std::cout << "📥 MQTT: " << topic << " -> " << payload << std::endl;
        
        // Handle camera control commands
        if (topic.find("/control/") != std::string::npos) {
            if (payload == "connect_camera") {
                // Trigger camera connection
                on_camera_clicked(nullptr, this);
            } else if (payload == "disconnect_camera") {
                // Trigger disconnection
                disconnect_from_camera();
            }
        }
    }
    
public:
    void publish_camera_status(const std::string& camera_name, const std::string& status) {
        if (!mqtt_client_ || !mqtt_client_->is_connected()) return;
        
        std::string topic = "rtsp_client/status/" + camera_name;
        std::string payload = "{\"status\":\"" + status + "\",\"timestamp\":" + 
                             std::to_string(time(nullptr)) + "}";
        
        try {
            auto msg = mqtt::make_message(topic, payload);
            msg->set_qos(1);
            mqtt_client_->publish(msg);
            std::cout << "📤 Published: " << topic << std::endl;
        } catch (const mqtt::exception& exc) {
            std::cerr << "❌ MQTT publish failed: " << exc.what() << std::endl;
        }
    }
```

### 4. Integration Points

Update your existing methods to include MQTT notifications:

```cpp
bool connect_to_camera(const CameraConfig& camera) {
    // Existing connection logic...
    
    if (connection_successful) {
        // Publish success status
        publish_camera_status(camera.name, "connected");
    }
    
    return connection_successful;
}

void disconnect_from_camera() {
    if (current_camera_) {
        publish_camera_status(current_camera_->name, "disconnected");
    }
    
    // Existing disconnection logic...
}
```

### 5. Initialize in main()

```cpp
int main(int argc, char* argv[]) {
    // Existing initialization...
    
    RTSPStreamClient client;
    client.init_ui();
    client.init_mqtt("tcp://your-mqtt-broker:1883");  // Configure your broker
    
    // Existing main loop...
}
```

## 📡 MQTT Topics Structure

### Published by Client (Status Updates)

```
rtsp_client/status/[camera_name]     - Connection status
rtsp_client/stats/[camera_name]      - Stream statistics  
rtsp_client/events/[camera_name]     - Motion, alerts, etc.
rtsp_client/health                   - Client health status
```

### Subscribed by Client (Control Commands)

```
rtsp_client/control/connect          - Connect to camera
rtsp_client/control/disconnect       - Disconnect camera
rtsp_client/control/snapshot         - Take snapshot
rtsp_client/control/switch_camera    - Switch active camera
```

## 📊 Example Message Formats

### Status Update
```json
{
  "status": "connected",
  "timestamp": 1699123456,
  "camera": "piir_shed",
  "resolution": "1280x720"
}
```

### Statistics
```json
{
  "fps": 30,
  "resolution": "1280x720", 
  "bitrate": 1000000,
  "timestamp": 1699123456
}
```

### Control Command
```json
{
  "command": "connect",
  "camera": "piir_shed",
  "timestamp": 1699123456
}
```

## 🧪 Testing

1. **Build and Test MQTT Example**:
   ```bash
   make mqtt-example
   ./mqtt_example
   ```

2. **Install MQTT Broker** (for testing):
   ```bash
   sudo apt install mosquitto mosquitto-clients
   sudo systemctl start mosquitto
   ```

3. **Test with mosquitto_pub/sub**:
   ```bash
   # Subscribe to all topics
   mosquitto_sub -h localhost -t "rtsp_client/#" -v
   
   # Send control command
   mosquitto_pub -h localhost -t "rtsp_client/control/connect" -m "connect_camera"
   ```

## 🔄 Integration Benefits

- **Remote Monitoring**: Monitor camera status from anywhere
- **Automation**: Integrate with Home Assistant, Node-RED, etc.
- **Load Balancing**: Distribute cameras across multiple clients
- **Event-Driven**: React to external triggers (motion sensors, schedules)
- **Debugging**: Real-time diagnostics and logging

## 🚀 Next Steps

1. Add MQTT initialization to your `main.cpp`
2. Integrate status publishing in camera connect/disconnect methods
3. Add stream statistics publishing (FPS, quality metrics)
4. Implement remote control command handling
5. Test with your MQTT broker setup

The `mqtt_example.cpp` provides a complete working example you can reference for implementation details.