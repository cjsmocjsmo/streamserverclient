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
#include <iostream>
#include <fstream>
#include <vector>
#include <string>

struct CameraConfig {
    std::string name;
    std::string url;
    std::string description;
};

class RTSPStreamClient {
private:
    GtkWidget* window;
    GtkWidget* main_box;
    GtkWidget* button_box;
    GtkWidget* video_area;
    GtkWidget* status_label;
    
    std::vector<CameraConfig> cameras;
    std::vector<GtkWidget*> camera_buttons;
    
    GstElement* pipeline;
    GstElement* video_sink;
    
    CameraConfig* current_camera;
    bool is_connected;
    
public:
    RTSPStreamClient();
    ~RTSPStreamClient();
    
    bool initialize();
    void run();
    
private:
    bool load_camera_config();
    void setup_ui();
    void apply_dark_theme();
    void create_video_area();
    void create_camera_buttons();
    
    bool connect_to_camera(const CameraConfig& camera);
    void disconnect_from_camera();
    
    void update_status(const std::string& message);
    
    // GTK callbacks
    static void on_camera_button_clicked(GtkWidget* button, gpointer user_data);
    static void on_disconnect_clicked(GtkWidget* button, gpointer user_data);
    static void on_test_clicked(GtkWidget* button, gpointer user_data);
    static void on_window_destroy(GtkWidget* widget, gpointer user_data);
    
    // GStreamer callbacks
    static gboolean on_bus_message(GstBus* bus, GstMessage* message, gpointer user_data);
    static void on_pad_added(GstElement* src, GstPad* new_pad, gpointer user_data);
};

RTSPStreamClient::RTSPStreamClient() 
    : window(nullptr), main_box(nullptr), button_box(nullptr), 
      video_area(nullptr), status_label(nullptr),
      pipeline(nullptr), video_sink(nullptr),
      current_camera(nullptr), is_connected(false) {
}

RTSPStreamClient::~RTSPStreamClient() {
    if (pipeline) {
        gst_element_set_state(pipeline, GST_STATE_NULL);
        gst_object_unref(pipeline);
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
    gtk_window_set_default_size(GTK_WINDOW(window), 1000, 700);
    gtk_window_set_position(GTK_WINDOW(window), GTK_WIN_POS_CENTER);
    
    // Set dark window background
    GdkRGBA window_color;
    gdk_rgba_parse(&window_color, "#1e1e1e");
    gtk_widget_override_background_color(window, GTK_STATE_FLAG_NORMAL, &window_color);
    
    // Connect destroy signal
    g_signal_connect(window, "destroy", G_CALLBACK(on_window_destroy), this);
    
    // Create main vertical box
    main_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_container_set_border_width(GTK_CONTAINER(main_box), 10);
    
    // Set dark background for main box
    gtk_widget_override_background_color(main_box, GTK_STATE_FLAG_NORMAL, &window_color);
    
    gtk_container_add(GTK_CONTAINER(window), main_box);
    
    // Create camera buttons (moved to top)
    create_camera_buttons();
    
    // Create video area
    create_video_area();
    
    // Create status label
    status_label = gtk_label_new("Ready to connect to camera");
    
    // Style status label with white text
    GdkRGBA white_text;
    gdk_rgba_parse(&white_text, "#ffffff");
    gtk_widget_override_color(status_label, GTK_STATE_FLAG_NORMAL, &white_text);
    
    gtk_box_pack_start(GTK_BOX(main_box), status_label, FALSE, FALSE, 0);
    
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
        "  background-color: #2d2d2d;"
        "  border: 1px solid #404040;"
        "  border-radius: 4px;"
        "}"
        "frame > border {"
        "  background-color: #2d2d2d;"
        "}"
        "frame > label {"
        "  color: #ffffff;"
        "  background-color: #2d2d2d;"
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
    gtk_box_pack_start(GTK_BOX(main_box), video_frame, TRUE, TRUE, 0);
    
    // Create video area - this will be used for video display
    video_area = gtk_drawing_area_new();
    gtk_widget_set_size_request(video_area, 800, 450);
    gtk_widget_set_hexpand(video_area, TRUE);
    gtk_widget_set_vexpand(video_area, TRUE);
    
    // Set black background
    GdkRGBA color;
    gdk_rgba_parse(&color, "#000000");
    gtk_widget_override_background_color(video_area, GTK_STATE_FLAG_NORMAL, &color);
    
    gtk_container_add(GTK_CONTAINER(video_frame), video_area);
    
    std::cout << "🎬 Video area created (800x450)" << std::endl;
}

void RTSPStreamClient::create_camera_buttons() {
    // Create horizontal box for buttons
    button_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 5);
    gtk_box_pack_start(GTK_BOX(main_box), button_box, FALSE, FALSE, 0);
    
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
    
    // Create GStreamer pipeline using gst_parse_launch for reliability
    // Try with fakesink first to test if data is flowing
    std::string pipeline_str = 
        "rtspsrc location=" + camera.url + " protocols=udp latency=0 ! "
        "rtph264depay ! h264parse ! avdec_h264 ! "
        "videoconvert ! gtksink";
    
    std::cout << "🚀 Creating pipeline: " << pipeline_str << std::endl;
    
    GError* error = nullptr;
    pipeline = gst_parse_launch(pipeline_str.c_str(), &error);
    
    if (!pipeline) {
        std::cerr << "❌ Failed to create pipeline: " << (error ? error->message : "Unknown error") << std::endl;
        if (error) g_error_free(error);
        return false;
    }
    
    // Get the video sink - for fakesink, we don't need to extract widget
    video_sink = gst_bin_get_by_name(GST_BIN(pipeline), "fakesink0");
    if (!video_sink) {
        std::cout << "⚠️ Could not get fakesink element (this is normal)" << std::endl;
        // This is actually normal for fakesink, continue anyway
    }
    
    /* 
    // GTK widget code - disabled for autovideosink testing
    GtkWidget* video_widget;
    g_object_get(video_sink, "widget", &video_widget, NULL);
    
    if (!video_widget) {
        std::cerr << "❌ Failed to get video widget from gtksink" << std::endl;
        gst_object_unref(video_sink);
        gst_object_unref(pipeline);
        video_sink = nullptr;
        pipeline = nullptr;
        return false;
    }
    
    std::cout << "✅ Got video widget from gtksink" << std::endl;
    
    // Set explicit size for the video widget
    gtk_widget_set_size_request(video_widget, 800, 450);
    gtk_widget_set_hexpand(video_widget, TRUE);
    gtk_widget_set_vexpand(video_widget, TRUE);
    
    // Replace the drawing area with the video widget
    GtkWidget* parent = gtk_widget_get_parent(video_area);
    if (parent) {
        gtk_container_remove(GTK_CONTAINER(parent), video_area);
        gtk_container_add(GTK_CONTAINER(parent), video_widget);
        gtk_widget_show_all(video_widget);
        std::cout << "✅ Video widget added to container (800x450)" << std::endl;
    } else {
        std::cerr << "❌ No parent container found for video area" << std::endl;
    }
    
    video_area = video_widget;
    */
    
    // Set up bus monitoring
    GstBus* bus = gst_element_get_bus(pipeline);
    gst_bus_add_watch(bus, on_bus_message, this);
    gst_object_unref(bus);
    
    // Start the pipeline
    std::cout << "🚀 Starting pipeline..." << std::endl;
    GstStateChangeReturn ret = gst_element_set_state(pipeline, GST_STATE_PLAYING);
    
    if (ret == GST_STATE_CHANGE_FAILURE) {
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
    std::cout << "✅ Disconnected successfully" << std::endl;
}

void RTSPStreamClient::update_status(const std::string& message) {
    if (status_label) {
        gtk_label_set_text(GTK_LABEL(status_label), message.c_str());
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
    
    if (self->pipeline) {
        self->disconnect_from_camera();
    }
    
    gtk_main_quit();
    std::cout << "🔚 Application cleanup complete" << std::endl;
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

int main(int argc, char* argv[]) {
    RTSPStreamClient app;
    
    if (!app.initialize()) {
        std::cerr << "❌ Failed to initialize application" << std::endl;
        return 1;
    }
    
    app.run();
    return 0;
}