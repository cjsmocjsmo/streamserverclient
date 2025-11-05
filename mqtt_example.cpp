/*
 * MQTT Client Example for C++
 * Shows how to integrate Paho MQTT C++ with your RTSP client
 * 
 * This demonstrates:
 * - Connecting to MQTT broker
 * - Publishing camera status updates
 * - Subscribing to camera control commands
 * - Asynchronous message handling
 */

#include <iostream>
#include <string>
#include <chrono>
#include <thread>
#include "mqtt/async_client.h"

class MqttManager {
private:
    mqtt::async_client client_;
    mqtt::connect_options conn_opts_;
    std::string topic_prefix_;
    
public:
    MqttManager(const std::string& server_uri, const std::string& client_id, const std::string& topic_prefix = "rtsp_client") 
        : client_(server_uri, client_id), topic_prefix_(topic_prefix) {
        
        // Set connection options
        conn_opts_.set_keep_alive_interval(20);
        conn_opts_.set_clean_session(true);
        
        // Set up connection callback
        client_.set_connection_lost_handler([this](const std::string& cause) {
            std::cout << "🔌 MQTT connection lost: " << cause << std::endl;
            // Implement reconnection logic here
        });
        
        // Set up message callback
        client_.set_message_callback([this](mqtt::const_message_ptr msg) {
            handle_message(msg);
        });
    }
    
    bool connect() {
        try {
            std::cout << "🔌 Connecting to MQTT broker..." << std::endl;
            auto token = client_.connect(conn_opts_);
            token->wait();
            std::cout << "✅ Connected to MQTT broker" << std::endl;
            
            // Subscribe to control topics
            std::string control_topic = topic_prefix_ + "/control/+";
            client_.subscribe(control_topic, 1);
            std::cout << "📡 Subscribed to: " << control_topic << std::endl;
            
            return true;
        } catch (const mqtt::exception& exc) {
            std::cerr << "❌ MQTT connection failed: " << exc.what() << std::endl;
            return false;
        }
    }
    
    void disconnect() {
        try {
            std::cout << "🔌 Disconnecting from MQTT broker..." << std::endl;
            auto token = client_.disconnect();
            token->wait();
            std::cout << "✅ Disconnected from MQTT broker" << std::endl;
        } catch (const mqtt::exception& exc) {
            std::cerr << "❌ MQTT disconnect failed: " << exc.what() << std::endl;
        }
    }
    
    void publish_camera_status(const std::string& camera_name, const std::string& status) {
        if (!client_.is_connected()) {
            std::cerr << "⚠️ MQTT not connected, cannot publish" << std::endl;
            return;
        }
        
        std::string topic = topic_prefix_ + "/status/" + camera_name;
        std::string payload = "{\"status\":\"" + status + "\",\"timestamp\":" + 
                             std::to_string(std::chrono::duration_cast<std::chrono::seconds>(
                                 std::chrono::system_clock::now().time_since_epoch()).count()) + "}";
        
        try {
            auto msg = mqtt::make_message(topic, payload);
            msg->set_qos(1);
            client_.publish(msg);
            std::cout << "📤 Published: " << topic << " -> " << payload << std::endl;
        } catch (const mqtt::exception& exc) {
            std::cerr << "❌ MQTT publish failed: " << exc.what() << std::endl;
        }
    }
    
    void publish_stream_stats(const std::string& camera_name, int fps, const std::string& resolution) {
        if (!client_.is_connected()) return;
        
        std::string topic = topic_prefix_ + "/stats/" + camera_name;
        std::string payload = "{\"fps\":" + std::to_string(fps) + 
                             ",\"resolution\":\"" + resolution + "\",\"timestamp\":" + 
                             std::to_string(std::chrono::duration_cast<std::chrono::seconds>(
                                 std::chrono::system_clock::now().time_since_epoch()).count()) + "}";
        
        try {
            auto msg = mqtt::make_message(topic, payload);
            msg->set_qos(0);  // QoS 0 for stats (fire and forget)
            client_.publish(msg);
            std::cout << "📊 Stats: " << camera_name << " - " << fps << "fps @ " << resolution << std::endl;
        } catch (const mqtt::exception& exc) {
            std::cerr << "❌ MQTT stats publish failed: " << exc.what() << std::endl;
        }
    }

private:
    void handle_message(mqtt::const_message_ptr msg) {
        std::string topic = msg->get_topic();
        std::string payload = msg->to_string();
        
        std::cout << "📥 MQTT Message: " << topic << " -> " << payload << std::endl;
        
        // Parse control commands
        if (topic.find("/control/") != std::string::npos) {
            if (payload == "connect") {
                std::cout << "🎥 MQTT Command: Connect camera" << std::endl;
                // Trigger camera connection in your RTSP client
            } else if (payload == "disconnect") {
                std::cout << "🛑 MQTT Command: Disconnect camera" << std::endl;
                // Trigger camera disconnection in your RTSP client
            } else if (payload == "snapshot") {
                std::cout << "📸 MQTT Command: Take snapshot" << std::endl;
                // Trigger snapshot capture
            }
        }
    }
};

// Example usage
int main() {
    // Create MQTT manager
    MqttManager mqtt("tcp://localhost:1883", "rtsp_client_001");
    
    // Connect to broker
    if (!mqtt.connect()) {
        return 1;
    }
    
    // Simulate camera operations
    mqtt.publish_camera_status("piir_shed", "connected");
    mqtt.publish_stream_stats("piir_shed", 30, "1280x720");
    
    // Keep running to receive messages
    std::cout << "🔄 Running MQTT client. Press Ctrl+C to exit..." << std::endl;
    
    // Simulate some activity
    for (int i = 0; i < 10; ++i) {
        std::this_thread::sleep_for(std::chrono::seconds(5));
        mqtt.publish_stream_stats("piir_shed", 28 + (i % 5), "1280x720");
    }
    
    mqtt.disconnect();
    return 0;
}