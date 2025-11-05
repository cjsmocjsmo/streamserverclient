#!/usr/bin/env python3

"""
RTSP Video Stream Client - GTK3 version with working video display
Uses gst-parse-launch for automatic pipeline creation and pad handling
"""

import os
import sys
import json

# Set GStreamer debug level for RTSP debugging
os.environ['GST_DEBUG'] = 'rtspsrc:3'

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')

from gi.repository import Gtk, Gst, Gdk, GLib, Gio

# Import paho.mqtt
try:
    import paho.mqtt.client as mqtt
    print("🔌 paho-mqtt imported successfully")
except ImportError:
    print("⚠️ paho-mqtt not available, MQTT features disabled")
    mqtt = None

class RTSPStreamClient:
    def __init__(self):
        print("🚀 Starting RTSP Client application...")
        
        # Initialize GStreamer
        Gst.init(None)
        
        # Initialize variables
        self.current_camera = None
        self.pipeline = None
        self.video_widget = None
        self.cameras = []
        
        # Load configuration
        self.load_config()
        
        # Setup UI
        self.setup_ui()
        
        print("✅ Application created successfully")
    
    def load_config(self):
        """Load camera configurations from config.json"""
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                
                # Handle both 'cameras' array and 'streams' object formats
                if 'cameras' in config:
                    self.cameras = config['cameras']
                elif 'streams' in config:
                    # Convert streams object to cameras array
                    streams = config['streams']
                    self.cameras = []
                    for stream_id, stream_data in streams.items():
                        self.cameras.append(stream_data)
                else:
                    self.cameras = []
                
                print(f"📸 Loaded {len(self.cameras)} camera configurations from config.json")
        except FileNotFoundError:
            print("❌ config.json not found")
            self.cameras = []
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing config.json: {e}")
            self.cameras = []
    
    def setup_ui(self):
        """Setup the GTK3 user interface"""
        self.window = Gtk.Window()
        self.window.set_title("RTSP Stream Client")
        self.window.set_default_size(1000, 600)
        self.window.connect("destroy", self.quit_application)
        
        # Create main container
        main_box = Gtk.VBox(spacing=10)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)
        main_box.set_margin_left(10)
        main_box.set_margin_right(10)
        
        # Create control panel
        control_box = Gtk.HBox(spacing=10)
        
        # Test pattern button
        test_button = Gtk.Button(label="Test Pattern")
        test_button.connect("clicked", self.on_test_clicked)
        control_box.pack_start(test_button, False, False, 0)
        
        # Camera buttons
        for camera in self.cameras:
            button = Gtk.Button(label=camera['name'])
            button.connect("clicked", self.on_camera_clicked, camera)
            control_box.pack_start(button, False, False, 0)
        
        # Disconnect button
        disconnect_button = Gtk.Button(label="Disconnect")
        disconnect_button.connect("clicked", self.on_disconnect_clicked)
        control_box.pack_start(disconnect_button, False, False, 0)
        
        main_box.pack_start(control_box, False, False, 0)
        
        # Create video area using Fixed container for absolute positioning
        self.fixed_container = Gtk.Fixed()
        self.fixed_container.set_size_request(820, 470)
        
        # Add a placeholder label
        self.placeholder_label = Gtk.Label()
        self.placeholder_label.set_markup("<i>No video stream connected</i>")
        self.fixed_container.put(self.placeholder_label, 350, 200)
        
        main_box.pack_start(self.fixed_container, True, True, 0)
        
        self.window.add(main_box)
        self.window.show_all()
        
        print("📺 UI setup complete with 3 cameras")
    
    def on_test_clicked(self, button):
        """Test with a simple video pattern"""
        print("🔘 Test button clicked!")
        
        # Create test pipeline
        test_camera = {
            'name': 'Test Pattern',
            'url': 'videotestsrc pattern=smpte ! video/x-raw,width=320,height=240,framerate=30/1'
        }
        self.connect_to_test_pattern()
    
    def on_camera_clicked(self, button, camera_config):
        """Handle camera button click"""
        print(f"🔘 Connect button clicked!")
        print(f"🎯 Connecting to: {camera_config}")
        self.connect_to_camera(camera_config)
    
    def on_disconnect_clicked(self, button):
        """Handle disconnect button click"""
        print("🔘 Disconnect button clicked!")
        self.disconnect_from_camera()
    
    def connect_to_test_pattern(self):
        """Connect to test pattern for verification"""
        print("🧪 Testing with simple pipeline...")
        
        try:
            # Stop any existing pipeline
            if self.pipeline:
                self.stop_pipeline()
            
            # Create test pattern pipeline
            pipeline_str = "videotestsrc pattern=smpte ! video/x-raw,width=320,height=240,framerate=30/1 ! videoconvert ! gtksink name=videosink"
            
            self.pipeline = Gst.parse_launch(pipeline_str)
            
            # Get the gtksink
            gtksink = self.pipeline.get_by_name("videosink")
            video_widget = gtksink.get_property("widget")
            
            print("✅ Test widget created")
            
            # Setup video widget
            if self.video_widget:
                self.video_widget.get_parent().remove(self.video_widget)
            
            self.video_widget = video_widget
            self.video_widget.set_size_request(800, 450)
            self.fixed_container.put(self.video_widget, 10, 10)
            self.video_widget.show()
            
            # Setup bus monitoring
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.on_bus_message)
            
            # Start pipeline
            print("🚀 Starting test pipeline...")
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                print("❌ Failed to start test pipeline")
                return False
            
            print("✅ Test pipeline started")
            return True
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            return False
    
    def connect_to_camera(self, camera_config):
        """Connect to camera using gst-parse-launch approach"""
        print(f"🎥 Connecting to {camera_config['name']} at {camera_config['url']}")
        
        try:
            # Stop any existing pipeline
            if self.pipeline:
                print("🛑 Stopping existing pipeline before creating new one")
                self.stop_pipeline()
            
            # Test with fakesink first to see if data is flowing
            rtsp_url = camera_config['url']
            # Test pipeline with fakesink to check if video data flows
            pipeline_str = f"rtspsrc location={rtsp_url} protocols=udp ! rtph264depay ! h264parse ! fakesink sync=false"
            
            print(f"🚀 Creating simplified pipeline: {pipeline_str}")
            self.pipeline = Gst.parse_launch(pipeline_str)
            
            if not self.pipeline:
                print("❌ Failed to create pipeline")
                return False
            
            print("✅ Pipeline created successfully using gst-parse-launch")
            
            # Set up pipeline bus for monitoring
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.on_bus_message)
            
            print("🎬 Testing RTSP stream with autovideosink (separate window)")
            
            # Start the pipeline with async approach
            print("🚀 Starting pipeline...")
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                print("❌ Failed to start pipeline")
                return False
            
            print(f"🔄 Pipeline start result: {ret}")
            print(f"🎬 Pipeline started for {camera_config['name']} - look for separate video window")
            self.current_camera = camera_config
            
            # Don't wait synchronously - let the bus messages handle state changes
            # Add a periodic check to monitor state
            GLib.timeout_add_seconds(2, self.check_pipeline_status)
            
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def check_pipeline_status(self):
        """Periodically check pipeline status"""
        if self.pipeline:
            change_return, current_state, pending_state = self.pipeline.get_state(0)
            print(f"🔍 Pipeline status - Current: {current_state}, Pending: {pending_state}")
            
            if current_state == Gst.State.PLAYING:
                print("🎉 SUCCESS: Pipeline is playing!")
                return False  # Stop checking
            elif current_state == Gst.State.PAUSED:
                print("🔄 Pipeline stuck in paused, checking for errors...")
                # Continue checking for a few more times
                return True
        return False
    
    def disconnect_from_camera(self):
        """Disconnect from current camera"""
        if self.pipeline:
            print("🛑 Disconnecting from camera...")
            self.stop_pipeline()
            self.current_camera = None
            
            # Remove video widget
            if self.video_widget:
                self.video_widget.get_parent().remove(self.video_widget)
                self.video_widget = None
            
            print("✅ Disconnected successfully")
        else:
            print("⚠️ No active connection to disconnect")
    
    def stop_pipeline(self):
        """Stop the current pipeline"""
        if self.pipeline:
            print("🛑 Stopping pipeline")
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
    
    def on_bus_message(self, bus, message):
        """Handle GStreamer bus messages"""
        t = message.type
        
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"❌ GStreamer Error: {err.message}")
            if debug:
                print(f"❌ Debug info: {debug}")
        
        elif t == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            print(f"⚠️ GStreamer Warning: {warn.message}")
        
        elif t == Gst.MessageType.EOS:
            print("🔚 End of stream")
            self.stop_pipeline()
        
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending = message.parse_state_changed()
                print(f"🔄 State changed: {old_state.value_nick} -> {new_state.value_nick}")
                
                if new_state == Gst.State.PLAYING:
                    print("▶️ Pipeline is now playing")
                elif new_state == Gst.State.PAUSED:
                    print("⏸️ Pipeline paused")
        
        elif t == Gst.MessageType.ASYNC_DONE:
            print("🔄 Async done - pipeline ready")
        
        elif t == Gst.MessageType.NEW_CLOCK:
            clock = message.parse_new_clock()
            print(f"🕐 New clock: {clock}")
        
        elif t == Gst.MessageType.STREAM_START:
            print("🌊 Stream started")
        
        elif t == Gst.MessageType.PROGRESS:
            progress_type, code, text = message.parse_progress()
            print(f"📈 Progress ({progress_type.value_nick}): {text}")
            
        elif t == Gst.MessageType.BUFFERING:
            percent = message.parse_buffering()
            print(f"🔄 Buffering: {percent}%")
            # Handle buffering for network streams
            if percent < 100:
                print(f"⏸️ Pausing for buffering...")
                if self.pipeline:
                    self.pipeline.set_state(Gst.State.PAUSED)
            else:
                print(f"▶️ Buffering complete, resuming...")
                if self.pipeline:
                    self.pipeline.set_state(Gst.State.PLAYING)
        
        elif t == Gst.MessageType.ELEMENT:
            struct = message.get_structure()
            if struct:
                print(f"🔧 Element message: {struct.get_name()}")
        
        return True
    
    def quit_application(self, widget=None):
        """Clean shutdown of the application"""
        print("👋 Application shutting down...")
        
        # Stop pipeline
        if self.pipeline:
            self.stop_pipeline()
        
        # Quit GTK
        Gtk.main_quit()
        print("🔚 Application cleanup complete")
    
    def run(self):
        """Start the application"""
        print("👁️ UI shown, entering main loop...")
        
        # Auto-test: Connect to first camera automatically for testing
        if self.cameras:
            print("🧪 Auto-testing first camera...")
            def auto_test():
                self.connect_to_camera(self.cameras[0])
                return False  # Don't repeat
            GLib.timeout_add_seconds(2, auto_test)
        
        Gtk.main()
        print("🏁 Main loop ended")

def main():
    try:
        app = RTSPStreamClient()
        app.run()
    except KeyboardInterrupt:
        print("👋 Application interrupted by user")
    except Exception as e:
        print(f"❌ Application error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🔚 Application cleanup")

if __name__ == "__main__":
    main()