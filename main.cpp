/*
 * RTSP Stream Client - C++ GTK3 + GStreamer Implementation
 * 
 * This application provides a GUI for viewing multiple RTSP camera streams
 * using GTK3 for the interface and GStreamer for video playback.
 * 
 * Features:
 * - Multiple camera support with configuration from JSON
 * - Embedded video display using gtksink
 * - RTSP stream handling with automatic reconnection
 * - Clean shutdown and resource management
 */

#include <gtk/gtk.h>
#include <gst/gst.h>
#include <gst/video/videooverlay.h>
#include <json/json.h>
#include <mqtt/async_client.h>
#include <sqlite3.h>
#include <iostream>
#include <fstream>
#include <vector>
#include <memory>
#include <thread>
#include <chrono>
#include <string>
#include <iomanip>
#include <sstream>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <unistd.h>
#include <sys/resource.h>
#include <csignal>
#include <cstdlib>
#include <future>

struct CameraConfig {
    std::string name;
    std::string url;
    std::string description;
};

struct VideoEvent {
    std::string camera_name;
    std::string date;
    std::string video_path;
    bool viewed;
    
    VideoEvent() : viewed(false) {}
    VideoEvent(const std::string& cam, const std::string& dt, const std::string& path, bool view = false)
        : camera_name(cam), date(dt), video_path(path), viewed(view) {}
};

enum PageType {
    PAGE_MAIN,
    PAGE_EVENTS
};

class RTSPStreamClient {
private:
    GtkWidget* window;
    GtkWidget* main_container;  // Top-level horizontal container
    GtkWidget* sidebar;         // Left sidebar for camera buttons
    GtkWidget* page_stack;      // Container for switching between pages
    GtkWidget* content_area;    // Right content area (main or events)
    GtkWidget* main_box;        // Main streaming page content
    GtkWidget* button_box;
    GtkWidget* video_area;
    GtkWidget* status_label;
    GtkWidget* mqtt_status_label;
    
    // Events page widgets
    GtkWidget* events_page;
    GtkWidget* events_list;
    GtkWidget* back_button;
    std::string current_events_filter;  // Current camera filter for events page
    
    std::vector<CameraConfig> cameras;
    std::vector<GtkWidget*> camera_buttons;
    std::vector<GtkWidget*> sidebar_camera_buttons;  // Store camera buttons for updating
    std::vector<VideoEvent> events;           // All events storage
    
    PageType current_page;
    
    GstElement* pipeline;
    GstElement* video_sink;
    
    CameraConfig* current_camera;
    bool is_connected;
    
    // MQTT components
    std::unique_ptr<mqtt::async_client> mqtt_client_;
    std::string mqtt_broker_;
    std::string client_id_;
    bool mqtt_connected_;
    
    // Background processing
    std::queue<mqtt::const_message_ptr> message_queue_;
    std::mutex queue_mutex_;
    std::condition_variable queue_cv_;
    std::thread worker_thread_;
    std::atomic<bool> stop_worker_;
    
    // Database batching
    std::queue<VideoEvent> db_queue_;
    std::mutex db_mutex_;
    std::condition_variable db_cv_;
    std::thread db_thread_;
    std::atomic<bool> stop_db_worker_;
    
    // Database components
    sqlite3* db;
    std::string db_path;
    
public:
    RTSPStreamClient();
    ~RTSPStreamClient();
    
    bool initialize();
    void run();
    void shutdown();  // Public shutdown method for signal handler
    
private:
    bool load_camera_config();
    void setup_ui();
    void apply_dark_theme();
    void create_video_area();
    void create_camera_buttons();
    
    bool connect_to_camera(const CameraConfig& camera);
    void disconnect_from_camera();
    
    void update_status(const std::string& message);
    void update_mqtt_status(const std::string& status, bool connected);
    
    // Database methods
    bool init_database();
    bool save_event_to_db(const VideoEvent& event);
    bool load_events_from_db();
    void update_sidebar_counts();
    void refresh_events_page();
    
    // UI page methods
    void create_sidebar();
    void create_events_page();
    void show_page(PageType page);
    void load_events();
    int get_unviewed_events_count(const std::string& camera_name);
    int get_last24h_events_count(const std::string& camera_name);
    
    // MQTT methods
    void init_mqtt();
    void connect_mqtt();
    void handle_mqtt_message(mqtt::const_message_ptr msg);
    void publish_status(const std::string& message);
    void message_worker();
    void database_worker();
    void queue_event_for_db(const VideoEvent& event);
    void print_performance_stats();
    void apply_video_widget_dark_theme(GtkWidget* video_widget);
    bool try_create_pipeline(const CameraConfig& camera, const std::string& pipeline_desc);
    
    // GTK callbacks
    static void on_camera_button_clicked(GtkWidget* button, gpointer user_data);
    static void on_disconnect_clicked(GtkWidget* button, gpointer user_data);
    static void on_test_clicked(GtkWidget* button, gpointer user_data);
    static void on_sidebar_button_clicked(GtkWidget* button, gpointer user_data);
    static void on_window_destroy(GtkWidget* widget, gpointer user_data);
    
    // GStreamer callbacks
    static gboolean on_bus_message(GstBus* bus, GstMessage* message, gpointer user_data);
    static void on_pad_added(GstElement* src, GstPad* new_pad, gpointer user_data);
    static void on_element_added(GstBin* bin, GstElement* element, gpointer user_data);
};

RTSPStreamClient::RTSPStreamClient() 
    : window(nullptr), main_box(nullptr), button_box(nullptr), 
      video_area(nullptr), status_label(nullptr), mqtt_status_label(nullptr),
      pipeline(nullptr), video_sink(nullptr),
      current_camera(nullptr), is_connected(false),
      mqtt_broker_("tcp://10.0.4.40:1883"), 
      client_id_("rtsp_client_" + std::to_string(getpid())),
      mqtt_connected_(false), stop_worker_(false), stop_db_worker_(false),
      sidebar(nullptr), content_area(nullptr), events_page(nullptr), events_list(nullptr),
      current_page(PAGE_MAIN), current_events_filter(""),
      db(nullptr), db_path("rtsp_events.db") {
    
    // Start background worker threads
    worker_thread_ = std::thread(&RTSPStreamClient::message_worker, this);
    db_thread_ = std::thread(&RTSPStreamClient::database_worker, this);
}

RTSPStreamClient::~RTSPStreamClient() {
    // Stop worker threads
    stop_worker_ = true;
    stop_db_worker_ = true;
    
    // Wake up waiting threads
    queue_cv_.notify_all();
    db_cv_.notify_all();
    
    // Wait for threads to finish
    if (worker_thread_.joinable()) {
        worker_thread_.join();
    }
    if (db_thread_.joinable()) {
        db_thread_.join();
    }
    
    // Cleanup database
    if (db) {
        sqlite3_close(db);
        std::cout << "🗄️ Database closed" << std::endl;
    }
    
    // Cleanup MQTT
    if (mqtt_client_ && mqtt_client_->is_connected()) {
        try {
            mqtt_client_->disconnect()->wait();
        } catch (const mqtt::exception& exc) {
            std::cerr << "❌ MQTT disconnect error: " << exc.what() << std::endl;
        }
    }
    
    // Cleanup GStreamer
    if (pipeline) {
        gst_element_set_state(pipeline, GST_STATE_NULL);
        gst_object_unref(pipeline);
    }
}

void RTSPStreamClient::shutdown() {
    std::cout << "📞 Shutdown method called - starting graceful shutdown..." << std::endl;
    
    // Set up a timeout for forced shutdown
    std::atomic<bool> shutdown_complete{false};
    
    // Launch shutdown sequence in a separate thread with timeout
    auto shutdown_future = std::async(std::launch::async, [this, &shutdown_complete]() {
        if (window) {
            std::cout << "🪟 Destroying window to trigger cleanup..." << std::endl;
            // Trigger the window destroy handler which does proper cleanup
            gtk_widget_destroy(window);
        } else {
            std::cout << "🚪 No window found, calling gtk_main_quit directly..." << std::endl;
            // Direct GTK quit if no window
            gtk_main_quit();
        }
        shutdown_complete = true;
    });
    
    // Wait for shutdown with timeout
    auto timeout = std::chrono::seconds(5);
    if (shutdown_future.wait_for(timeout) == std::future_status::timeout) {
        std::cout << "⏰ Graceful shutdown timed out after 5 seconds, forcing exit..." << std::endl;
        
        // Force quit GTK main loop
        gtk_main_quit();
        
        // Give it another moment
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        
        if (!shutdown_complete) {
            std::cout << "💀 Forcing process termination with exit()..." << std::endl;
            std::exit(0);  // Force immediate termination
        }
    } else {
        std::cout << "✅ Graceful shutdown completed successfully" << std::endl;
    }
}

bool RTSPStreamClient::load_camera_config() {
    std::ifstream config_file("config.json");
    if (!config_file.is_open()) {
        std::cerr << "❌ Failed to open config.json" << std::endl;
        return false;
    }
    
    Json::Value root;
    Json::Reader reader;
    
    if (!reader.parse(config_file, root)) {
        std::cerr << "❌ Failed to parse config.json" << std::endl;
        return false;
    }
    
    const Json::Value cameras_json = root["cameras"];
    if (!cameras_json.isArray()) {
        std::cerr << "❌ No cameras array found in config.json" << std::endl;
        return false;
    }
    
    cameras.clear();
    for (const auto& camera_json : cameras_json) {
        CameraConfig camera;
        camera.name = camera_json["name"].asString();
        camera.url = camera_json["url"].asString();
        camera.description = camera_json["description"].asString();
        cameras.push_back(camera);
    }
    
    std::cout << "📸 Loaded " << cameras.size() << " camera configurations" << std::endl;
    return !cameras.empty();
}

void RTSPStreamClient::setup_ui() {
    // Apply dark theme CSS
    apply_dark_theme();
    
    // Create main window
    window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(window), "RTSP Stream Client - C++");
    gtk_window_set_default_size(GTK_WINDOW(window), 358, 250);
    gtk_window_set_position(GTK_WINDOW(window), GTK_WIN_POS_CENTER);
    
    // Set dark window background
    GdkRGBA window_color;
    gdk_rgba_parse(&window_color, "#1e1e1e");
    gtk_widget_override_background_color(window, GTK_STATE_FLAG_NORMAL, &window_color);
    
    // Connect destroy signal
    g_signal_connect(window, "destroy", G_CALLBACK(on_window_destroy), this);
    
    // Create main horizontal box to hold sidebar and content
    main_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0);
    gtk_widget_override_background_color(main_box, GTK_STATE_FLAG_NORMAL, &window_color);
    gtk_container_add(GTK_CONTAINER(window), main_box);
    
    // Create sidebar
    create_sidebar();
    
    // Create a stack container to hold different pages
    page_stack = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_box_pack_start(GTK_BOX(main_box), page_stack, TRUE, TRUE, 0);
    
    // Create content area
    content_area = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_container_set_border_width(GTK_CONTAINER(content_area), 10);
    gtk_widget_override_background_color(content_area, GTK_STATE_FLAG_NORMAL, &window_color);
    gtk_box_pack_start(GTK_BOX(page_stack), content_area, TRUE, TRUE, 0);
    
    // Create camera buttons (moved to top of content area)
    create_camera_buttons();
    
    // Create video area
    create_video_area();
    
    // Create status label
    status_label = gtk_label_new("Ready to connect to camera");
    
    // Style status label with white text
    GdkRGBA white_text;
    gdk_rgba_parse(&white_text, "#ffffff");
    gtk_widget_override_color(status_label, GTK_STATE_FLAG_NORMAL, &white_text);
    
    gtk_box_pack_start(GTK_BOX(content_area), status_label, FALSE, FALSE, 0);
    
    // Create MQTT status label
    mqtt_status_label = gtk_label_new("MQTT: Disconnected");
    gtk_widget_override_color(mqtt_status_label, GTK_STATE_FLAG_NORMAL, &white_text);
    gtk_box_pack_start(GTK_BOX(content_area), mqtt_status_label, FALSE, FALSE, 0);
    
    // Create events page
    create_events_page();
    
    // Add events page to the page stack
    gtk_box_pack_start(GTK_BOX(page_stack), events_page, TRUE, TRUE, 0);
    
    // Initialize database and load events
    if (!init_database()) {
        std::cerr << "❌ Failed to initialize database" << std::endl;
        // Fall back to loading sample events
        load_events();
    } else {
        // Load events from database
        if (!load_events_from_db()) {
            std::cout << "📅 No events in database, loading sample data" << std::endl;
            load_events();
            // Save sample events to database
            for (const auto& event : events) {
                save_event_to_db(event);
            }
        }
    }
    
    // Update sidebar counts after loading events
    update_sidebar_counts();
    
    // Initialize MQTT
    init_mqtt();
    
    // Ensure main page is displayed initially
    show_page(PAGE_MAIN);
    
    std::cout << "📺 UI setup complete with " << cameras.size() << " cameras" << std::endl;
}

void RTSPStreamClient::apply_dark_theme() {
    // Create CSS provider for dark theme
    GtkCssProvider* css_provider = gtk_css_provider_new();
    
    const char* css_data = 
        "* {"
        "  background-color: #1e1e1e;"
        "  color: #ffffff;"
        "}"
        "window {"
        "  background-color: #1e1e1e;"
        "}"
        "box {"
        "  background-color: #1e1e1e;"
        "}"
        "frame {"
        "  background-color: #1e1e1e;"
        "  border: 1px solid #404040;"
        "  border-radius: 4px;"
        "}"
        "frame > border {"
        "  background-color: #1e1e1e;"
        "}"
        "frame > label {"
        "  color: #ffffff;"
        "  background-color: #1e1e1e;"
        "  padding: 4px 8px;"
        "  font-weight: bold;"
        "}"
        "button {"
        "  background: linear-gradient(to bottom, #404040, #303030);"
        "  border: 1px solid #555555;"
        "  border-radius: 4px;"
        "  color: #ffffff;"
        "  padding: 8px 16px;"
        "  margin: 2px;"
        "  font-weight: bold;"
        "}"
        "button:hover {"
        "  background: linear-gradient(to bottom, #505050, #404040);"
        "  border: 1px solid #666666;"
        "  box-shadow: 0 2px 4px rgba(255,255,255,0.1);"
        "}"
        "button:active {"
        "  background: linear-gradient(to bottom, #303030, #404040);"
        "  border: 1px solid #777777;"
        "  box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);"
        "}"
        "label {"
        "  color: #ffffff;"
        "  background-color: transparent;"
        "}"
        "drawingarea {"
        "  background-color: #000000;"
        "  border: 1px solid #404040;"
        "}"
        "treeview {"
        "  background-color: #1e1e1e;"
        "  color: #ffffff;"
        "  border: 1px solid #404040;"
        "}"
        "treeview.view {"
        "  background-color: #1e1e1e;"
        "  color: #ffffff;"
        "}"
        "treeview.view:selected {"
        "  background-color: #404040;"
        "  color: #ffffff;"
        "}"
        "treeview header {"
        "  background-color: #2d2d2d;"
        "  color: #ffffff;"
        "  border: 1px solid #404040;"
        "  font-weight: bold;"
        "}"
        "treeview header button {"
        "  background-color: #2d2d2d;"
        "  color: #ffffff;"
        "  border: 1px solid #404040;"
        "}"
        "scrolledwindow {"
        "  background-color: #1e1e1e;"
        "  border: 1px solid #404040;"
        "}";

    gtk_css_provider_load_from_data(css_provider, css_data, -1, NULL);
    
    // Apply to default screen
    GdkScreen* screen = gdk_screen_get_default();
    gtk_style_context_add_provider_for_screen(screen,
                                               GTK_STYLE_PROVIDER(css_provider),
                                               GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    
    g_object_unref(css_provider);
    std::cout << "🎨 Dark theme applied" << std::endl;
}

void RTSPStreamClient::create_video_area() {
    // Create frame for video
    GtkWidget* video_frame = gtk_frame_new("Video Stream");
    gtk_box_pack_start(GTK_BOX(content_area), video_frame, TRUE, TRUE, 0);
    
    // Create video area - this will be used for video display
    video_area = gtk_drawing_area_new();
    gtk_widget_set_size_request(video_area, 286, 162);
    gtk_widget_set_hexpand(video_area, TRUE);
    gtk_widget_set_vexpand(video_area, TRUE);
    
    // Set black background
    GdkRGBA color;
    gdk_rgba_parse(&color, "#000000");
    gtk_widget_override_background_color(video_area, GTK_STATE_FLAG_NORMAL, &color);
    
    gtk_container_add(GTK_CONTAINER(video_frame), video_area);
    
    std::cout << "🎬 Video area created (286x162)" << std::endl;
}

void RTSPStreamClient::create_camera_buttons() {
    // Create horizontal box for buttons
    button_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 5);
    gtk_box_pack_start(GTK_BOX(content_area), button_box, FALSE, FALSE, 0);
    
    // Create camera buttons
    for (size_t i = 0; i < cameras.size(); ++i) {
        std::string button_text = cameras[i].name;
        GtkWidget* button = gtk_button_new_with_label(button_text.c_str());
        
        // Store camera index in button data
        g_object_set_data(G_OBJECT(button), "camera_index", GINT_TO_POINTER(i));
        g_signal_connect(button, "clicked", G_CALLBACK(on_camera_button_clicked), this);
        
        gtk_box_pack_start(GTK_BOX(button_box), button, TRUE, TRUE, 0);
        camera_buttons.push_back(button);
    }
    
    // Add disconnect button
    GtkWidget* disconnect_button = gtk_button_new_with_label("Disconnect");
    g_signal_connect(disconnect_button, "clicked", G_CALLBACK(on_disconnect_clicked), this);
    gtk_box_pack_start(GTK_BOX(button_box), disconnect_button, TRUE, TRUE, 0);
    
    // Add test button
    GtkWidget* test_button = gtk_button_new_with_label("Test Pattern");
    g_signal_connect(test_button, "clicked", G_CALLBACK(on_test_clicked), this);
    gtk_box_pack_start(GTK_BOX(button_box), test_button, TRUE, TRUE, 0);
    
    std::cout << "🔘 Created " << cameras.size() << " camera buttons" << std::endl;
}

bool RTSPStreamClient::connect_to_camera(const CameraConfig& camera) {
    std::cout << "🎥 Connecting to " << camera.name << " at " << camera.url << std::endl;
    
    // Disconnect any existing stream
    if (pipeline) {
        disconnect_from_camera();
    }
    
    // Try multiple pipeline configurations for maximum compatibility
    std::vector<std::string> pipeline_configs = {
        // Configuration 1: TCP+UDP with high timeout (VLC-like)
        "rtspsrc location=" + camera.url + " protocols=tcp+udp+http latency=2000 timeout=10000000 tcp-timeout=10000000 "
        "retry=3 do-retransmission=true buffer-mode=auto ! "
        "queue max-size-buffers=5 max-size-bytes=0 max-size-time=2000000000 ! "
        "rtph264depay ! h264parse ! "
        "avdec_h264 max-threads=2 output-corrupt=false ! "
        "videorate drop-only=true ! video/x-raw,framerate=15/1 ! "
        "videoconvert ! "
        "videoscale method=1 ! video/x-raw,width=640,height=360 ! "
        "gtksink sync=false async=false",
        
        // Configuration 2: TCP only with basic settings
        "rtspsrc location=" + camera.url + " protocols=tcp latency=500 timeout=5000000 ! "
        "queue ! rtph264depay ! h264parse ! avdec_h264 ! "
        "videoconvert ! videoscale ! video/x-raw,width=640,height=360 ! "
        "gtksink sync=false",
        
        // Configuration 3: UDP only (original working config)
        "rtspsrc location=" + camera.url + " protocols=udp latency=0 ! "
        "queue ! rtph264depay ! h264parse ! avdec_h264 ! "
        "videoconvert ! gtksink sync=false",
        
        // Configuration 4: Minimal pipeline for maximum compatibility
        "rtspsrc location=" + camera.url + " ! "
        "decodebin ! videoconvert ! autovideosink sync=false"
    };
    
    // Try each configuration until one works
    for (size_t i = 0; i < pipeline_configs.size(); i++) {
        std::cout << "� Trying pipeline configuration " << (i + 1) << "/" << pipeline_configs.size() << std::endl;
        
        if (try_create_pipeline(camera, pipeline_configs[i])) {
            std::cout << "✅ Successfully connected with configuration " << (i + 1) << std::endl;
            current_camera = const_cast<CameraConfig*>(&camera);
            is_connected = true;
            
            std::string status = "Connected to " + camera.name;
            update_status(status);
            publish_status("Connected to camera: " + camera.name);
            
            return true;
        }
        
        std::cout << "❌ Configuration " << (i + 1) << " failed, trying next..." << std::endl;
    }
    
    std::cerr << "❌ All pipeline configurations failed for " << camera.name << std::endl;
    update_status("Connection failed: " + camera.name);
    return false;
}

bool RTSPStreamClient::try_create_pipeline(const CameraConfig& camera, const std::string& pipeline_desc) {
    std::cout << "🚀 Trying pipeline: " << pipeline_desc.substr(0, 80) << "..." << std::endl;
    
    GError* error = nullptr;
    GstElement* test_pipeline = gst_parse_launch(pipeline_desc.c_str(), &error);
    
    if (!test_pipeline) {
        std::cerr << "❌ Failed to create pipeline: " << (error ? error->message : "Unknown error") << std::endl;
        if (error) g_error_free(error);
        return false;
    }
    
    // Test if pipeline can be started
    GstStateChangeReturn ret = gst_element_set_state(test_pipeline, GST_STATE_READY);
    if (ret == GST_STATE_CHANGE_FAILURE) {
        std::cerr << "❌ Pipeline failed to reach READY state" << std::endl;
        gst_object_unref(test_pipeline);
        return false;
    }
    
    // If we get here, the pipeline is good - make it our main pipeline
    pipeline = test_pipeline;
    
    // Get the video sink and apply dark theming
    video_sink = gst_bin_get_by_name(GST_BIN(pipeline), "gtksink0");
    if (!video_sink) {
        std::cout << "⚠️ Could not get gtksink element, trying fallback" << std::endl;
        // Try to get it by interface
        GstBin* bin = GST_BIN(pipeline);
        GstIterator* iter = gst_bin_iterate_sinks(bin);
        GValue value = G_VALUE_INIT;
        gboolean done = FALSE;
        
        while (!done) {
            switch (gst_iterator_next(iter, &value)) {
                case GST_ITERATOR_OK: {
                    GstElement* element = GST_ELEMENT(g_value_get_object(&value));
                    if (g_str_has_prefix(GST_ELEMENT_NAME(element), "gtksink")) {
                        video_sink = GST_ELEMENT(gst_object_ref(element));
                        done = TRUE;
                    }
                    g_value_reset(&value);
                    break;
                }
                case GST_ITERATOR_RESYNC:
                    gst_iterator_resync(iter);
                    break;
                case GST_ITERATOR_ERROR:
                case GST_ITERATOR_DONE:
                    done = TRUE;
                    break;
            }
        }
        g_value_unset(&value);
        gst_iterator_free(iter);
    }
    
    // If we found gtksink, get its widget and apply dark theme
    if (video_sink) {
        GtkWidget* video_widget;
        g_object_get(video_sink, "widget", &video_widget, NULL);
        
        if (video_widget) {
            std::cout << "✅ Got video widget from gtksink" << std::endl;
            
            // Apply dark theme to video widget
            apply_video_widget_dark_theme(video_widget);
            
            // Set explicit size for the video widget
            gtk_widget_set_size_request(video_widget, 640, 360);
            gtk_widget_set_hexpand(video_widget, TRUE);
            gtk_widget_set_vexpand(video_widget, TRUE);
            
            // Replace the drawing area with the video widget
            GtkWidget* parent = gtk_widget_get_parent(video_area);
            if (parent) {
                gtk_container_remove(GTK_CONTAINER(parent), video_area);
                gtk_container_add(GTK_CONTAINER(parent), video_widget);
                gtk_widget_show_all(video_widget);
                std::cout << "✅ Video widget added to container with dark theme" << std::endl;
            } else {
                std::cerr << "❌ No parent container found for video area" << std::endl;
            }
            
            video_area = video_widget;
        } else {
            std::cout << "⚠️ Could not get widget from gtksink" << std::endl;
        }
    }
    
    // Set up bus monitoring
    GstBus* bus = gst_element_get_bus(pipeline);
    gst_bus_add_watch(bus, on_bus_message, this);
    gst_object_unref(bus);
    
    // Connect to element-added signal to catch gtksink widget creation
    g_signal_connect(pipeline, "element-added", G_CALLBACK(on_element_added), this);
    
    // Start the pipeline
    std::cout << "🚀 Starting pipeline..." << std::endl;
    GstStateChangeReturn start_ret = gst_element_set_state(pipeline, GST_STATE_PLAYING);
    
    if (start_ret == GST_STATE_CHANGE_FAILURE) {
        std::cerr << "❌ Failed to start pipeline" << std::endl;
        gst_object_unref(video_sink);
        gst_object_unref(pipeline);
        video_sink = nullptr;
        pipeline = nullptr;
        return false;
    }
    
    std::cout << "🔄 Pipeline start return: " << ret << std::endl;
    
    current_camera = const_cast<CameraConfig*>(&camera);
    is_connected = true;
    
    std::string status = "Connected to " + camera.name;
    update_status(status);
    publish_status("Connected to camera: " + camera.name);
    
    std::cout << "✅ Successfully connected to " << camera.name << std::endl;
    
    // Add a timeout check to see if we reach PLAYING state
    g_timeout_add_seconds(5, [](gpointer user_data) -> gboolean {
        RTSPStreamClient* self = static_cast<RTSPStreamClient*>(user_data);
        if (self->pipeline) {
            GstState current_state, pending_state;
            GstStateChangeReturn ret = gst_element_get_state(self->pipeline, &current_state, &pending_state, 0);
            std::cout << "🔍 After 5s - Current: " << gst_element_state_get_name(current_state) 
                     << ", Pending: " << gst_element_state_get_name(pending_state) 
                     << ", Return: " << ret << std::endl;
        }
        return FALSE; // Don't repeat
    }, this);
    
    return true;
}

void RTSPStreamClient::disconnect_from_camera() {
    if (!pipeline) return;
    
    std::cout << "🛑 Disconnecting from camera..." << std::endl;
    
    // Stop pipeline
    gst_element_set_state(pipeline, GST_STATE_NULL);
    
    // Wait for state change
    gst_element_get_state(pipeline, nullptr, nullptr, GST_CLOCK_TIME_NONE);
    
    // Clean up
    if (video_sink) {
        gst_object_unref(video_sink);
        video_sink = nullptr;
    }
    
    gst_object_unref(pipeline);
    pipeline = nullptr;
    
    current_camera = nullptr;
    is_connected = false;
    
    update_status("Disconnected");
    publish_status("Disconnected from camera");
    std::cout << "✅ Disconnected successfully" << std::endl;
}

void RTSPStreamClient::update_status(const std::string& message) {
    if (status_label) {
        gtk_label_set_text(GTK_LABEL(status_label), message.c_str());
    }
}

void RTSPStreamClient::update_mqtt_status(const std::string& status, bool connected) {
    if (mqtt_status_label) {
        std::string display_text = "MQTT: " + status;
        gtk_label_set_text(GTK_LABEL(mqtt_status_label), display_text.c_str());
        
        // Change color based on connection status
        GdkRGBA color;
        if (connected) {
            gdk_rgba_parse(&color, "#00ff00"); // Green for connected
        } else {
            gdk_rgba_parse(&color, "#ff6666"); // Light red for disconnected
        }
        gtk_widget_override_color(mqtt_status_label, GTK_STATE_FLAG_NORMAL, &color);
    }
    mqtt_connected_ = connected;
}

void RTSPStreamClient::init_mqtt() {
    try {
        mqtt_client_.reset(new mqtt::async_client(mqtt_broker_, client_id_));
        
        // Set up connection lost handler
        mqtt_client_->set_connection_lost_handler([this](const std::string& cause) {
            std::cout << "🔌 MQTT connection lost: " << cause << std::endl;
            update_mqtt_status("Connection Lost", false);
        });
        
        // Set up message callback - queue messages for background processing
        mqtt_client_->set_message_callback([this](mqtt::const_message_ptr msg) {
            std::lock_guard<std::mutex> lock(queue_mutex_);
            message_queue_.push(msg);
            queue_cv_.notify_one();
        });
        
        std::cout << "📡 MQTT client initialized for broker: " << mqtt_broker_ << std::endl;
        connect_mqtt();
        
    } catch (const mqtt::exception& exc) {
        std::cerr << "❌ MQTT initialization failed: " << exc.what() << std::endl;
        update_mqtt_status("Init Failed", false);
    }
}

void RTSPStreamClient::connect_mqtt() {
    try {
        mqtt::connect_options conn_opts;
        conn_opts.set_keep_alive_interval(20);
        conn_opts.set_clean_session(true);
        conn_opts.set_automatic_reconnect(true);
        
        update_mqtt_status("Connecting...", false);
        
        auto token = mqtt_client_->connect(conn_opts);
        token->wait();
        
        // Subscribe to camera topics
        mqtt_client_->subscribe("camera/+/status", 1);
        mqtt_client_->subscribe("camera/+/alert", 1);
        mqtt_client_->subscribe("camera/+/events", 1);  // Subscribe to events
        mqtt_client_->subscribe("rtsp_client/control", 1);
        
        update_mqtt_status("Connected", true);
        std::cout << "✅ MQTT connected and subscribed to camera topics" << std::endl;
        
        // Publish client status
        publish_status("RTSP Client Started");
        
    } catch (const mqtt::exception& exc) {
        std::cerr << "❌ MQTT connection failed: " << exc.what() << std::endl;
        update_mqtt_status("Connection Failed", false);
    }
}

void RTSPStreamClient::handle_mqtt_message(mqtt::const_message_ptr msg) {
    std::string topic = msg->get_topic();
    std::string payload = msg->to_string();
    
    std::cout << "📥 MQTT Message: " << topic << " -> " << payload.substr(0, 100) << "..." << std::endl;
    
    // Handle different message types
    if (topic.find("camera/") == 0 && topic.find("/events") != std::string::npos) {
        // Camera event messages - parse JSON and save to database
        try {
            Json::Value root;
            Json::Reader reader;
            
            if (reader.parse(payload, root)) {
                VideoEvent event;
                event.camera_name = root["camera_name"].asString();
                event.date = root["timestamp"].asString();
                event.video_path = root["video_path"].asString();
                event.viewed = root.get("viewed", false).asBool();
                
                // Add to events vector for immediate UI response
                events.insert(events.begin(), event); // Add to front for most recent first
                
                // Queue for database processing in background
                queue_event_for_db(event);
                
                std::cout << "✅ Event queued for processing: " << event.camera_name << std::endl;
            } else {
                std::cerr << "❌ Failed to parse event JSON" << std::endl;
            }
        } catch (const std::exception& e) {
            std::cerr << "❌ Error processing event: " << e.what() << std::endl;
        }
        
    } else if (topic.find("camera/") == 0 && topic.find("/status") != std::string::npos) {
        // Camera status messages
        std::string camera_name = topic.substr(7, topic.find("/status") - 7);
        update_status("Camera " + camera_name + ": " + payload);
        
    } else if (topic.find("camera/") == 0 && topic.find("/alert") != std::string::npos) {
        // Camera alert messages
        std::string camera_name = topic.substr(7, topic.find("/alert") - 7);
        update_status("🚨 ALERT from " + camera_name + ": " + payload);
        
    } else if (topic == "rtsp_client/control") {
        // Control messages for this client
        if (payload == "disconnect") {
            if (is_connected) {
                disconnect_from_camera();
            }
        } else if (payload == "connect" && !cameras.empty()) {
            if (!is_connected) {
                connect_to_camera(cameras[0]); // Connect to first camera
            }
        }
    }
}

void RTSPStreamClient::publish_status(const std::string& message) {
    if (!mqtt_client_ || !mqtt_connected_) {
        return;
    }
    
    try {
        std::string topic = "rtsp_client/" + client_id_ + "/status";
        auto mqtt_msg = mqtt::make_message(topic, message);
        mqtt_msg->set_qos(1);
        mqtt_client_->publish(mqtt_msg);
        std::cout << "📤 Published status: " << message << std::endl;
    } catch (const mqtt::exception& exc) {
        std::cerr << "❌ MQTT publish failed: " << exc.what() << std::endl;
    }
}

bool RTSPStreamClient::initialize() {
    std::cout << "🚀 Starting RTSP Client application..." << std::endl;
    
    // Initialize GTK
    if (!gtk_init_check(nullptr, nullptr)) {
        std::cerr << "❌ Failed to initialize GTK" << std::endl;
        return false;
    }
    
    // Initialize GStreamer
    gst_init(nullptr, nullptr);
    
    // Load camera configuration
    if (!load_camera_config()) {
        return false;
    }
    
    // Setup UI
    setup_ui();
    
    std::cout << "✅ Application initialized successfully" << std::endl;
    return true;
}

void RTSPStreamClient::run() {
    gtk_widget_show_all(window);
    
    // After show_all, ensure the correct page is visible
    show_page(PAGE_MAIN);
    
    std::cout << "👁️ UI shown, entering main loop..." << std::endl;
    gtk_main();
}

// Static callback implementations
void RTSPStreamClient::on_camera_button_clicked(GtkWidget* button, gpointer user_data) {
    RTSPStreamClient* self = static_cast<RTSPStreamClient*>(user_data);
    gint camera_index = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(button), "camera_index"));
    
    if (camera_index >= 0 && camera_index < static_cast<gint>(self->cameras.size())) {
        std::cout << "🔘 Camera button clicked: " << self->cameras[camera_index].name << std::endl;
        self->connect_to_camera(self->cameras[camera_index]);
    }
}

void RTSPStreamClient::on_disconnect_clicked(GtkWidget* button, gpointer user_data) {
    RTSPStreamClient* self = static_cast<RTSPStreamClient*>(user_data);
    std::cout << "🔘 Disconnect button clicked!" << std::endl;
    self->disconnect_from_camera();
}

void RTSPStreamClient::on_test_clicked(GtkWidget* button, gpointer user_data) {
    RTSPStreamClient* self = static_cast<RTSPStreamClient*>(user_data);
    std::cout << "🔘 Test button clicked!" << std::endl;
    
    // Create test pattern
    CameraConfig test_camera;
    test_camera.name = "Test Pattern";
    test_camera.url = "videotestsrc pattern=smpte ! video/x-raw,width=320,height=240,framerate=30/1";
    test_camera.description = "Test pattern";
    
    // Modify pipeline creation for test pattern
    if (self->pipeline) {
        self->disconnect_from_camera();
    }
    
    std::string pipeline_str = test_camera.url + " ! videoconvert ! autovideosink sync=false";
    std::cout << "🧪 Creating test pipeline: " << pipeline_str << std::endl;
    
    GError* error = nullptr;
    self->pipeline = gst_parse_launch(pipeline_str.c_str(), &error);
    
    if (self->pipeline) {
        // Get video sink and widget
        self->video_sink = gst_bin_get_by_name(GST_BIN(self->pipeline), "autovideosink0");
        /*
        if (self->video_sink) {
            GtkWidget* video_widget;
            g_object_get(self->video_sink, "widget", &video_widget, NULL);
            
            if (video_widget) {
                GtkWidget* parent = gtk_widget_get_parent(self->video_area);
                gtk_container_remove(GTK_CONTAINER(parent), self->video_area);
                gtk_container_add(GTK_CONTAINER(parent), video_widget);
                gtk_widget_show(video_widget);
                self->video_area = video_widget;
            }
        }
        */
        
        // Set up bus and start
        GstBus* bus = gst_element_get_bus(self->pipeline);
        gst_bus_add_watch(bus, on_bus_message, self);
        gst_object_unref(bus);
        
        gst_element_set_state(self->pipeline, GST_STATE_PLAYING);
        self->update_status("Playing test pattern");
    }
}

void RTSPStreamClient::on_window_destroy(GtkWidget* widget, gpointer user_data) {
    RTSPStreamClient* self = static_cast<RTSPStreamClient*>(user_data);
    std::cout << "👋 Application shutting down..." << std::endl;
    
    // Stop background worker threads first
    self->stop_worker_ = true;
    self->stop_db_worker_ = true;
    
    // Wake up waiting threads
    self->queue_cv_.notify_all();
    self->db_cv_.notify_all();
    
    // Wait for worker threads to complete
    if (self->worker_thread_.joinable()) {
        std::cout << "🛑 Stopping MQTT worker thread..." << std::endl;
        self->worker_thread_.join();
        std::cout << "✅ MQTT worker thread stopped" << std::endl;
    }
    
    if (self->db_thread_.joinable()) {
        std::cout << "🛑 Stopping database worker thread..." << std::endl;
        self->db_thread_.join();
        std::cout << "✅ Database worker thread stopped" << std::endl;
    }
    
    // Disconnect MQTT client
    if (self->mqtt_client_ && self->mqtt_client_->is_connected()) {
        std::cout << "🔌 Disconnecting MQTT client..." << std::endl;
        try {
            self->mqtt_client_->disconnect();
            std::cout << "✅ MQTT client disconnected" << std::endl;
        } catch (const std::exception& e) {
            std::cerr << "⚠️ Error disconnecting MQTT: " << e.what() << std::endl;
        }
    }
    
    // Disconnect from camera and clean up pipeline
    if (self->pipeline) {
        self->disconnect_from_camera();
    }
    
    // Close database connection
    if (self->db) {
        std::cout << "🗄️ Closing database connection..." << std::endl;
        sqlite3_close(self->db);
        self->db = nullptr;
        std::cout << "✅ Database closed" << std::endl;
    }
    
    std::cout << "🔚 Application cleanup complete, quitting GTK main loop..." << std::endl;
    gtk_main_quit();
    
    // Add a timeout to force exit if GTK doesn't quit properly
    std::thread([]{
        std::this_thread::sleep_for(std::chrono::seconds(3));
        std::cout << "⚠️ GTK main loop didn't quit in 3 seconds, forcing exit..." << std::endl;
        std::exit(0);
    }).detach();
}

gboolean RTSPStreamClient::on_bus_message(GstBus* bus, GstMessage* message, gpointer user_data) {
    RTSPStreamClient* self = static_cast<RTSPStreamClient*>(user_data);
    
    switch (GST_MESSAGE_TYPE(message)) {
        case GST_MESSAGE_ERROR: {
            GError* error;
            gchar* debug;
            gst_message_parse_error(message, &error, &debug);
            std::cerr << "❌ GStreamer Error: " << error->message << std::endl;
            if (debug) {
                std::cerr << "❌ Debug info: " << debug << std::endl;
                g_free(debug);
            }
            g_error_free(error);
            break;
        }
        case GST_MESSAGE_WARNING: {
            GError* warning;
            gchar* debug;
            gst_message_parse_warning(message, &warning, &debug);
            std::cout << "⚠️ GStreamer Warning: " << warning->message << std::endl;
            if (debug) {
                g_free(debug);
            }
            g_error_free(warning);
            break;
        }
        case GST_MESSAGE_EOS:
            std::cout << "🔚 End of stream" << std::endl;
            break;
        case GST_MESSAGE_STATE_CHANGED:
            if (GST_MESSAGE_SRC(message) == GST_OBJECT(self->pipeline)) {
                GstState old_state, new_state, pending_state;
                gst_message_parse_state_changed(message, &old_state, &new_state, &pending_state);
                std::cout << "🔄 State changed: " << gst_element_state_get_name(old_state) 
                         << " -> " << gst_element_state_get_name(new_state) << std::endl;
                
                if (new_state == GST_STATE_PLAYING) {
                    std::cout << "▶️ Pipeline is now playing" << std::endl;
                    // Check video widget size when playing
                    if (self->video_area) {
                        GtkAllocation allocation;
                        gtk_widget_get_allocation(self->video_area, &allocation);
                        std::cout << "📺 Video widget size: " << allocation.width << "x" << allocation.height << std::endl;
                        
                        // Force widget to be visible and properly sized
                        gtk_widget_show_all(self->video_area);
                        gtk_widget_queue_draw(self->video_area);
                    }
                } else if (new_state == GST_STATE_PAUSED) {
                    std::cout << "⏸️ Pipeline paused" << std::endl;
                }
            }
            break;
        case GST_MESSAGE_ASYNC_DONE:
            std::cout << "🔄 Async done - pipeline ready" << std::endl;
            break;
        case GST_MESSAGE_NEW_CLOCK: {
            GstClock* clock;
            gst_message_parse_new_clock(message, &clock);
            std::cout << "🕐 New clock: " << GST_OBJECT_NAME(clock) << std::endl;
            break;
        }
        case GST_MESSAGE_STREAM_START:
            std::cout << "🌊 Stream started" << std::endl;
            break;
        case GST_MESSAGE_PROGRESS: {
            GstProgressType type;
            gchar* code, *text;
            gst_message_parse_progress(message, &type, &code, &text);
            std::cout << "📈 Progress: " << text << std::endl;
            g_free(code);
            g_free(text);
            break;
        }
        default:
            break;
    }
    
    return TRUE; // Continue watching
}

// UI page methods implementation
void RTSPStreamClient::create_sidebar() {
    sidebar = gtk_box_new(GTK_ORIENTATION_VERTICAL, 5);
    gtk_widget_set_size_request(sidebar, 150, -1);
    gtk_container_set_border_width(GTK_CONTAINER(sidebar), 10);
    
    // Set dark background
    GdkRGBA sidebar_color;
    gdk_rgba_parse(&sidebar_color, "#2d2d2d");
    gtk_widget_override_background_color(sidebar, GTK_STATE_FLAG_NORMAL, &sidebar_color);
    
    gtk_box_pack_start(GTK_BOX(main_box), sidebar, FALSE, FALSE, 0);
    
    // Add main view button
    GtkWidget* main_button = gtk_button_new_with_label("Main View");
    g_object_set_data_full(G_OBJECT(main_button), "page_type", 
                          g_strdup("main"), g_free);
    g_signal_connect(main_button, "clicked", G_CALLBACK(on_sidebar_button_clicked), this);
    gtk_box_pack_start(GTK_BOX(sidebar), main_button, FALSE, FALSE, 0);
    
    // Add separator
    GtkWidget* separator = gtk_separator_new(GTK_ORIENTATION_HORIZONTAL);
    gtk_box_pack_start(GTK_BOX(sidebar), separator, FALSE, FALSE, 5);
    
    // Create sidebar buttons for cameras with unviewed and 24h counts
    for (const auto& camera : cameras) {
        int unviewed_count = get_unviewed_events_count(camera.name);
        int last24h_count = get_last24h_events_count(camera.name);
        
        // Extract camera type (piir, picam, pipiw) from camera name
        std::string camera_type = camera.name.substr(0, camera.name.find(" "));
        
        std::string button_text = camera_type + "\n" + 
                                 std::to_string(unviewed_count) + " unviewed\n" +
                                 std::to_string(last24h_count) + " last 24h";
        GtkWidget* button = gtk_button_new_with_label(button_text.c_str());
        
        // Store camera name in button data
        g_object_set_data_full(G_OBJECT(button), "camera_name", 
                              g_strdup(camera.name.c_str()), g_free);
        g_object_set_data_full(G_OBJECT(button), "page_type", 
                              g_strdup("events"), g_free);
        g_signal_connect(button, "clicked", G_CALLBACK(on_sidebar_button_clicked), this);
        
        gtk_box_pack_start(GTK_BOX(sidebar), button, FALSE, FALSE, 0);
        
        // Store reference for updating later
        sidebar_camera_buttons.push_back(button);
    }
}

void RTSPStreamClient::create_events_page() {
    events_page = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_container_set_border_width(GTK_CONTAINER(events_page), 10);
    
    // Set dark background
    GdkRGBA page_color;
    gdk_rgba_parse(&page_color, "#1e1e1e");
    gtk_widget_override_background_color(events_page, GTK_STATE_FLAG_NORMAL, &page_color);
    
    // Create scrolled window for events list
    GtkWidget* scrolled = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scrolled), 
                                   GTK_POLICY_AUTOMATIC, GTK_POLICY_AUTOMATIC);
    gtk_widget_set_size_request(scrolled, -1, 300);
    
    // Create list store for events
    GtkListStore* store = gtk_list_store_new(4, G_TYPE_STRING, G_TYPE_STRING, 
                                           G_TYPE_STRING, G_TYPE_BOOLEAN);
    
    // Create tree view
    events_list = gtk_tree_view_new_with_model(GTK_TREE_MODEL(store));
    gtk_widget_override_background_color(events_list, GTK_STATE_FLAG_NORMAL, &page_color);
    
    // Set white text color for the entire tree view
    GdkRGBA white_text;
    gdk_rgba_parse(&white_text, "#ffffff");
    gtk_widget_override_color(events_list, GTK_STATE_FLAG_NORMAL, &white_text);
    
    // Add columns with separate renderers for each column
    GtkCellRenderer* camera_renderer = gtk_cell_renderer_text_new();
    g_object_set(camera_renderer, "foreground", "#ffffff", NULL);
    GtkTreeViewColumn* camera_column = gtk_tree_view_column_new_with_attributes("Camera", camera_renderer, "text", 0, NULL);
    gtk_tree_view_column_set_resizable(camera_column, TRUE);
    gtk_tree_view_column_set_min_width(camera_column, 100);
    gtk_tree_view_append_column(GTK_TREE_VIEW(events_list), camera_column);
    
    GtkCellRenderer* date_renderer = gtk_cell_renderer_text_new();
    g_object_set(date_renderer, "foreground", "#ffffff", NULL);
    GtkTreeViewColumn* date_column = gtk_tree_view_column_new_with_attributes("Date", date_renderer, "text", 1, NULL);
    gtk_tree_view_column_set_resizable(date_column, TRUE);
    gtk_tree_view_column_set_min_width(date_column, 150);
    gtk_tree_view_append_column(GTK_TREE_VIEW(events_list), date_column);
    
    GtkCellRenderer* path_renderer = gtk_cell_renderer_text_new();
    g_object_set(path_renderer, "foreground", "#ffffff", NULL);
    GtkTreeViewColumn* path_column = gtk_tree_view_column_new_with_attributes("Video Path", path_renderer, "text", 2, NULL);
    gtk_tree_view_column_set_resizable(path_column, TRUE);
    gtk_tree_view_column_set_min_width(path_column, 200);
    gtk_tree_view_append_column(GTK_TREE_VIEW(events_list), path_column);
    
    // Style the column headers
    GList* columns = gtk_tree_view_get_columns(GTK_TREE_VIEW(events_list));
    for (GList* l = columns; l != NULL; l = l->next) {
        GtkTreeViewColumn* column = GTK_TREE_VIEW_COLUMN(l->data);
        GtkWidget* header = gtk_tree_view_column_get_button(column);
        if (header) {
            gtk_widget_override_color(header, GTK_STATE_FLAG_NORMAL, &white_text);
        }
    }
    g_list_free(columns);
    
    gtk_container_add(GTK_CONTAINER(scrolled), events_list);
    gtk_box_pack_start(GTK_BOX(events_page), scrolled, TRUE, TRUE, 0);
    
    // Initially hide the events page
    gtk_widget_set_visible(events_page, FALSE);
    
    // Don't unref store - let the tree view manage it
    // g_object_unref(store);
}

void RTSPStreamClient::show_page(PageType page) {
    current_page = page;
    
    switch (page) {
        case PAGE_MAIN:
            gtk_widget_set_visible(content_area, TRUE);
            gtk_widget_set_visible(events_page, FALSE);
            std::cout << "📺 Showing main page" << std::endl;
            break;
        case PAGE_EVENTS:
            gtk_widget_set_visible(content_area, FALSE);
            gtk_widget_set_visible(events_page, TRUE);
            std::cout << "📋 Showing events page" << std::endl;
            break;
    }
}

// Database methods implementation
bool RTSPStreamClient::init_database() {
    int rc = sqlite3_open(db_path.c_str(), &db);
    
    if (rc) {
        std::cerr << "❌ Can't open database: " << sqlite3_errmsg(db) << std::endl;
        return false;
    }
    
    std::cout << "🗄️ Database opened: " << db_path << std::endl;
    
    // Create events table if it doesn't exist
    const char* sql = R"(
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_name TEXT NOT NULL,
            date TEXT NOT NULL,
            video_path TEXT NOT NULL,
            viewed INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_camera_name ON events(camera_name);
        CREATE INDEX IF NOT EXISTS idx_date ON events(date);
        CREATE INDEX IF NOT EXISTS idx_viewed ON events(viewed);
    )";
    
    char* err_msg = 0;
    rc = sqlite3_exec(db, sql, 0, 0, &err_msg);
    
    if (rc != SQLITE_OK) {
        std::cerr << "❌ SQL error: " << err_msg << std::endl;
        sqlite3_free(err_msg);
        return false;
    }
    
    std::cout << "✅ Database initialized successfully" << std::endl;
    return true;
}

bool RTSPStreamClient::save_event_to_db(const VideoEvent& event) {
    const char* sql = "INSERT INTO events (camera_name, date, video_path, viewed) VALUES (?, ?, ?, ?)";
    sqlite3_stmt* stmt;
    
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        std::cerr << "❌ Failed to prepare statement: " << sqlite3_errmsg(db) << std::endl;
        return false;
    }
    
    sqlite3_bind_text(stmt, 1, event.camera_name.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, event.date.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 3, event.video_path.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int(stmt, 4, event.viewed ? 1 : 0);
    
    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    
    if (rc != SQLITE_DONE) {
        std::cerr << "❌ Failed to insert event: " << sqlite3_errmsg(db) << std::endl;
        return false;
    }
    
    std::cout << "💾 Event saved to database: " << event.camera_name << std::endl;
    return true;
}

bool RTSPStreamClient::load_events_from_db() {
    const char* sql = "SELECT camera_name, date, video_path, viewed FROM events ORDER BY date DESC";
    sqlite3_stmt* stmt;
    
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        std::cerr << "❌ Failed to prepare select statement: " << sqlite3_errmsg(db) << std::endl;
        return false;
    }
    
    events.clear();
    
    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        VideoEvent event;
        event.camera_name = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
        event.date = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        event.video_path = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        event.viewed = sqlite3_column_int(stmt, 3) == 1;
        
        events.push_back(event);
    }
    
    sqlite3_finalize(stmt);
    
    if (rc != SQLITE_DONE) {
        std::cerr << "❌ Failed to load events: " << sqlite3_errmsg(db) << std::endl;
        return false;
    }
    
    std::cout << "📅 Loaded " << events.size() << " events from database" << std::endl;
    return true;
}

void RTSPStreamClient::update_sidebar_counts() {
    // Update button labels without recreating the sidebar
    for (size_t i = 0; i < sidebar_camera_buttons.size() && i < cameras.size(); i++) {
        GtkWidget* button = sidebar_camera_buttons[i];
        const auto& camera = cameras[i];
        
        int unviewed_count = get_unviewed_events_count(camera.name);
        int last24h_count = get_last24h_events_count(camera.name);
        
        // Extract camera type (piir, picam, pipiw) from camera name
        std::string camera_type = camera.name.substr(0, camera.name.find(" "));
        
        std::string button_text = camera_type + "\n" + 
                                 std::to_string(unviewed_count) + " unviewed\n" +
                                 std::to_string(last24h_count) + " last 24h";
        
        gtk_button_set_label(GTK_BUTTON(button), button_text.c_str());
    }
    
    std::cout << "🔄 Sidebar button labels updated" << std::endl;
}

void RTSPStreamClient::refresh_events_page() {
    if (current_page == PAGE_EVENTS && events_list && !current_events_filter.empty()) {
        // Reload events from database to get the latest data
        load_events_from_db();
        
        GtkListStore* store = GTK_LIST_STORE(gtk_tree_view_get_model(GTK_TREE_VIEW(events_list)));
        gtk_list_store_clear(store);
        
        // Repopulate with current filter
        for (const auto& event : events) {
            if (event.camera_name == current_events_filter) {
                GtkTreeIter iter;
                gtk_list_store_append(store, &iter);
                gtk_list_store_set(store, &iter,
                                  0, event.camera_name.c_str(),
                                  1, event.date.c_str(),
                                  2, event.video_path.c_str(),
                                  3, event.viewed,
                                  -1);
            }
        }
        
        std::cout << "🔄 Events page refreshed with latest database data" << std::endl;
    }
}

void RTSPStreamClient::load_events() {
    // Sample events - in a real application, these would be loaded from a database or file
    events.push_back({"picam - FrontDoor", "2024-11-05 14:30:22", "/videos/front_door_20241105_143022.mp4", false});
    events.push_back({"pipiw - BackDoor", "2024-11-05 16:45:10", "/videos/back_door_20241105_164510.mp4", false});
    events.push_back({"picam - FrontDoor", "2024-11-05 09:15:33", "/videos/front_door_20241105_091533.mp4", true});
    events.push_back({"piir - Shed", "2024-11-04 11:22:45", "/videos/shed_20241104_112245.mp4", false});
    events.push_back({"pipiw - BackDoor", "2024-11-03 18:30:12", "/videos/back_door_20241103_183012.mp4", false});
    events.push_back({"piir - Shed", "2024-11-05 20:15:30", "/videos/shed_20241105_201530.mp4", false});
    events.push_back({"picam - FrontDoor", "2024-11-05 22:45:15", "/videos/front_door_20241105_224515.mp4", false});
    
    std::cout << "📅 Loaded " << events.size() << " events" << std::endl;
}

int RTSPStreamClient::get_unviewed_events_count(const std::string& camera_name) {
    int count = 0;
    for (const auto& event : events) {
        if (event.camera_name == camera_name && !event.viewed) {
            count++;
        }
    }
    return count;
}

int RTSPStreamClient::get_last24h_events_count(const std::string& camera_name) {
    int count = 0;
    
    // Get current time
    auto now = std::chrono::system_clock::now();
    auto time_24h_ago = now - std::chrono::hours(24);
    
    for (const auto& event : events) {
        if (event.camera_name == camera_name) {
            // Parse event date string (format: "YYYY-MM-DD HH:MM:SS")
            std::tm tm = {};
            std::istringstream ss(event.date);
            ss >> std::get_time(&tm, "%Y-%m-%d %H:%M:%S");
            
            if (!ss.fail()) {
                auto event_time = std::chrono::system_clock::from_time_t(std::mktime(&tm));
                if (event_time >= time_24h_ago) {
                    count++;
                }
            }
        }
    }
    return count;
}

// New callback for sidebar buttons
void RTSPStreamClient::on_sidebar_button_clicked(GtkWidget* button, gpointer user_data) {
    RTSPStreamClient* self = static_cast<RTSPStreamClient*>(user_data);
    
    const char* page_type = static_cast<const char*>(g_object_get_data(G_OBJECT(button), "page_type"));
    
    if (std::string(page_type) == "main") {
        std::cout << "📺 Switching to main view" << std::endl;
        self->show_page(PAGE_MAIN);
        return;
    }
    
    const char* camera_name = static_cast<const char*>(g_object_get_data(G_OBJECT(button), "camera_name"));
    
    std::cout << "📋 Showing events for: " << camera_name << std::endl;
    
    // Store current filter
    self->current_events_filter = camera_name;
    
    // Switch to events page
    self->show_page(PAGE_EVENTS);
    
    // Reload events from database to ensure we have the latest data
    self->load_events_from_db();
    
    // Filter events list by camera name
    GtkListStore* store = GTK_LIST_STORE(gtk_tree_view_get_model(GTK_TREE_VIEW(self->events_list)));
    gtk_list_store_clear(store);
    
    int events_added = 0;
    for (const auto& event : self->events) {
        std::cout << "🔍 Checking event: " << event.camera_name << " vs filter: " << camera_name << std::endl;
        if (event.camera_name == camera_name) {
            GtkTreeIter iter;
            gtk_list_store_append(store, &iter);
            gtk_list_store_set(store, &iter,
                              0, event.camera_name.c_str(),
                              1, event.date.c_str(),
                              2, event.video_path.c_str(),
                              3, event.viewed,
                              -1);
            events_added++;
            std::cout << "✅ Added event: " << event.camera_name << " - " << event.date << std::endl;
        }
    }
    
    std::cout << "📊 Added " << events_added << " events to the tree view for " << camera_name << std::endl;
    
    // Force tree view refresh to ensure events are visible
    gtk_widget_queue_draw(self->events_list);
    gtk_widget_show_all(self->events_list);
    
    // Check how many rows are in the model for debugging
    GtkTreeModel* model = gtk_tree_view_get_model(GTK_TREE_VIEW(self->events_list));
    gint row_count = gtk_tree_model_iter_n_children(model, NULL);
    std::cout << "🔄 Tree view refreshed and shown - Model has " << row_count << " rows" << std::endl;
    
    // Additional debugging - check if tree view is visible and has columns
    gboolean is_visible = gtk_widget_get_visible(self->events_list);
    GList* columns = gtk_tree_view_get_columns(GTK_TREE_VIEW(self->events_list));
    gint column_count = g_list_length(columns);
    g_list_free(columns);
    std::cout << "🔍 Tree view visible: " << (is_visible ? "YES" : "NO") << ", columns: " << column_count << std::endl;
}

void RTSPStreamClient::message_worker() {
    std::cout << "📨 Message worker thread started" << std::endl;
    auto last_stats_time = std::chrono::steady_clock::now();
    
    while (!stop_worker_) {
        std::unique_lock<std::mutex> lock(queue_mutex_);
        queue_cv_.wait_for(lock, std::chrono::seconds(5), [this] { return !message_queue_.empty() || stop_worker_; });
        
        while (!message_queue_.empty() && !stop_worker_) {
            auto msg = message_queue_.front();
            message_queue_.pop();
            lock.unlock();
            
            // Process message in background thread
            handle_mqtt_message(msg);
            
            lock.lock();
        }
        
        // Print performance stats every 30 seconds
        auto now = std::chrono::steady_clock::now();
        if (std::chrono::duration_cast<std::chrono::seconds>(now - last_stats_time).count() >= 30) {
            print_performance_stats();
            last_stats_time = now;
        }
    }
    
    std::cout << "📨 Message worker thread stopped" << std::endl;
}

void RTSPStreamClient::database_worker() {
    std::cout << "🗄️ Database worker thread started" << std::endl;
    
    while (!stop_db_worker_) {
        std::unique_lock<std::mutex> lock(db_mutex_);
        db_cv_.wait(lock, [this] { return !db_queue_.empty() || stop_db_worker_; });
        
        std::vector<VideoEvent> batch;
        while (!db_queue_.empty() && !stop_db_worker_) {
            batch.push_back(db_queue_.front());
            db_queue_.pop();
            if (batch.size() >= 10) break; // Process in batches of 10
        }
        lock.unlock();
        
        // Process batch
        for (const auto& event : batch) {
            if (save_event_to_db(event)) {
                // Update UI in main thread
                g_idle_add([](gpointer user_data) -> gboolean {
                    RTSPStreamClient* self = static_cast<RTSPStreamClient*>(user_data);
                    self->update_sidebar_counts();
                    self->refresh_events_page();
                    return G_SOURCE_REMOVE;
                }, this);
            }
        }
        
        // Small delay to batch more efficiently
        if (!stop_db_worker_) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
    
    std::cout << "🗄️ Database worker thread stopped" << std::endl;
}

void RTSPStreamClient::queue_event_for_db(const VideoEvent& event) {
    std::lock_guard<std::mutex> lock(db_mutex_);
    db_queue_.push(event);
    db_cv_.notify_one();
}

void RTSPStreamClient::print_performance_stats() {
    struct rusage usage;
    if (getrusage(RUSAGE_SELF, &usage) == 0) {
        // Convert to percentages (rough estimate)
        double cpu_time = usage.ru_utime.tv_sec + usage.ru_utime.tv_usec / 1000000.0;
        long memory_kb = usage.ru_maxrss; // Peak memory usage in KB
        
        std::cout << "📊 Performance: CPU time: " << std::fixed << std::setprecision(2) 
                  << cpu_time << "s, Peak Memory: " << memory_kb << " KB" << std::endl;
        
        // Queue status
        size_t mqtt_queue_size, db_queue_size;
        {
            std::lock_guard<std::mutex> lock1(queue_mutex_);
            mqtt_queue_size = message_queue_.size();
        }
        {
            std::lock_guard<std::mutex> lock2(db_mutex_);
            db_queue_size = db_queue_.size();
        }
        
        std::cout << "📈 Queues: MQTT=" << mqtt_queue_size << ", DB=" << db_queue_size << std::endl;
    }
}

void RTSPStreamClient::apply_video_widget_dark_theme(GtkWidget* video_widget) {
    if (!video_widget) return;
    
    std::cout << "🎨 Applying dark theme to video widget" << std::endl;
    
    // Create specific CSS for this video widget
    GtkCssProvider* css_provider = gtk_css_provider_new();
    
    const char* video_css = 
        "* {"
        "  background-color: #000000;"
        "  color: #ffffff;"
        "}"
        "button {"
        "  background-color: #404040;"
        "  color: #ffffff;"
        "  border: 1px solid #555555;"
        "}"
        "button:hover {"
        "  background-color: #505050;"
        "}"
        "button:active {"
        "  background-color: #303030;"
        "}"
        "scale, progressbar {"
        "  background-color: #404040;"
        "  color: #ffffff;"
        "}"
        "label {"
        "  color: #ffffff;"
        "}";    gtk_css_provider_load_from_data(css_provider, video_css, -1, NULL);
    
    // Apply CSS to the video widget's style context
    GtkStyleContext* context = gtk_widget_get_style_context(video_widget);
    gtk_style_context_add_provider(context, 
                                   GTK_STYLE_PROVIDER(css_provider),
                                   GTK_STYLE_PROVIDER_PRIORITY_USER);
    
    // Set background color directly
    GdkRGBA black_color;
    gdk_rgba_parse(&black_color, "#000000");
    gtk_widget_override_background_color(video_widget, GTK_STATE_FLAG_NORMAL, &black_color);
    
    // Apply to all child widgets recursively
    if (GTK_IS_CONTAINER(video_widget)) {
        GList* children = gtk_container_get_children(GTK_CONTAINER(video_widget));
        for (GList* iter = children; iter != NULL; iter = g_list_next(iter)) {
            GtkWidget* child = GTK_WIDGET(iter->data);
            
            // Apply CSS to child
            GtkStyleContext* child_context = gtk_widget_get_style_context(child);
            gtk_style_context_add_provider(child_context,
                                           GTK_STYLE_PROVIDER(css_provider),
                                           GTK_STYLE_PROVIDER_PRIORITY_USER);
            
            // Force dark colors on child widgets
            gtk_widget_override_background_color(child, GTK_STATE_FLAG_NORMAL, &black_color);
            
            GdkRGBA white_color;
            gdk_rgba_parse(&white_color, "#ffffff");
            gtk_widget_override_color(child, GTK_STATE_FLAG_NORMAL, &white_color);
            
            // Recursively apply to container children
            if (GTK_IS_CONTAINER(child)) {
                apply_video_widget_dark_theme(child);
            }
        }
        g_list_free(children);
    }
    
    g_object_unref(css_provider);
    std::cout << "🎨 Video widget dark theme applied" << std::endl;
}

void RTSPStreamClient::on_element_added(GstBin* bin, GstElement* element, gpointer user_data) {
    RTSPStreamClient* self = static_cast<RTSPStreamClient*>(user_data);
    
    // Check if this is a gtksink element
    if (g_str_has_prefix(GST_ELEMENT_NAME(element), "gtksink")) {
        std::cout << "🔍 Found gtksink element: " << GST_ELEMENT_NAME(element) << std::endl;
        
        // Wait a bit for the widget to be created
        g_timeout_add(100, [](gpointer user_data) -> gboolean {
            RTSPStreamClient* self = static_cast<RTSPStreamClient*>(user_data);
            
            // Try to get all gtksink elements and apply theming
            GstBin* pipeline_bin = GST_BIN(self->pipeline);
            GstIterator* iter = gst_bin_iterate_sinks(pipeline_bin);
            GValue value = G_VALUE_INIT;
            gboolean done = FALSE;
            
            while (!done) {
                switch (gst_iterator_next(iter, &value)) {
                    case GST_ITERATOR_OK: {
                        GstElement* sink = GST_ELEMENT(g_value_get_object(&value));
                        if (g_str_has_prefix(GST_ELEMENT_NAME(sink), "gtksink")) {
                            GtkWidget* video_widget;
                            g_object_get(sink, "widget", &video_widget, NULL);
                            
                            if (video_widget) {
                                std::cout << "🎨 Applying delayed dark theme to video widget" << std::endl;
                                self->apply_video_widget_dark_theme(video_widget);
                            }
                        }
                        g_value_reset(&value);
                        break;
                    }
                    case GST_ITERATOR_RESYNC:
                        gst_iterator_resync(iter);
                        break;
                    case GST_ITERATOR_ERROR:
                    case GST_ITERATOR_DONE:
                        done = TRUE;
                        break;
                }
            }
            g_value_unset(&value);
            gst_iterator_free(iter);
            
            return G_SOURCE_REMOVE; // Remove this timeout
        }, self);
    }
}

#include <csignal>

// Global pointer for signal handling
RTSPStreamClient* g_app_instance = nullptr;
std::atomic<bool> g_shutdown_in_progress{false};

void signal_handler(int signal) {
    std::cout << "\n🛑 Received signal " << signal << ", shutting down gracefully..." << std::endl;
    
    // If we already started shutdown, force exit immediately
    if (g_shutdown_in_progress.exchange(true)) {
        std::cout << "💀 Second signal received, forcing immediate exit!" << std::endl;
        std::exit(signal);
    }
    
    if (g_app_instance) {
        g_app_instance->shutdown();
    } else {
        // Direct GTK quit if no app instance
        std::cout << "🚪 No app instance, calling gtk_main_quit directly..." << std::endl;
        gtk_main_quit();
        
        // Force exit after a moment if GTK doesn't quit
        std::this_thread::sleep_for(std::chrono::seconds(2));
        std::cout << "💀 GTK didn't quit, forcing exit..." << std::endl;
        std::exit(signal);
    }
}

int main(int argc, char* argv[]) {
    // Set up signal handlers for graceful shutdown
    signal(SIGINT, signal_handler);   // Ctrl+C
    signal(SIGTERM, signal_handler);  // Termination signal
    signal(SIGHUP, signal_handler);   // Hangup signal
    
    RTSPStreamClient app;
    g_app_instance = &app;  // Set global pointer for signal handler
    
    if (!app.initialize()) {
        std::cerr << "❌ Failed to initialize application" << std::endl;
        return 1;
    }
    
    app.run();
    
    // Clear global pointer
    g_app_instance = nullptr;
    
    return 0;
}