#!/usr/bin/env python3

"""
RTSP Video Stream Client - GTK3 version
Fixed video embedding using GTK3 + GStreamer integration
"""

import os
import sys
import json

# Set GStreamer debug level for RTSP debugging
os.environ['GST_DEBUG'] = 'rtspsrc:4,rtsp:3'
import threading
import time
import sqlite3
from datetime import datetime
import random

# Try to import paho-mqtt, but make it optional
MQTT_AVAILABLE = False
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
    print("🔌 paho-mqtt imported successfully")
except ImportError:
    print("❌ paho-mqtt not available. Install with: pip install paho-mqtt")

try:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gst', '1.0')
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gio', '2.0')
    from gi.repository import Gtk, Gst, Gdk, GLib, Gio
except ImportError as e:
    print(f"❌ Error: Required GTK/GStreamer libraries not found: {e}")
    print("Install with: sudo apt install python3-gi gir1.2-gtk-3.0 gstreamer1.0-tools gstreamer1.0-plugins-* gstreamer1.0-gtk3")
    sys.exit(1)

# Initialize GStreamer
Gst.init(None)

class RTSPClient(Gtk.Window):
    """Main RTSP client application window"""
    
    def __init__(self):
        super().__init__()
        self.set_title("RTSP Video Stream Client - GTK3")
        self.set_default_size(1000, 700)
        self.connect("destroy", Gtk.main_quit)
        
        # Load camera configuration
        self.load_config()
        
        # Current connection state
        self.current_pipeline = None
        self.current_camera = None
        self.pads_connected = False  # Track if any pads were connected
        
        # Setup UI
        self.setup_ui()
        
        # Apply CSS styling
        self.apply_styling()
        
    def load_config(self):
        """Load camera configuration from config.json"""
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
                # Try "cameras" first, then "streams" for compatibility
                self.camera_configs = config.get("cameras", config.get("streams", {}))
                print(f"📸 Loaded {len(self.camera_configs)} camera configurations from config.json")
        except FileNotFoundError:
            print("❌ config.json not found. Using default configuration.")
            self.camera_configs = {
                "test": {
                    "name": "Test Stream (Public)",
                    "url": "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4"
                },
                "test2": {
                    "name": "Local Test Stream", 
                    "url": "rtsp://10.0.4.67:8554/stream1"
                },
                "shed": {
                    "name": "Shed Camera",
                    "url": "rtsp://10.0.4.67:8554/stream1"
                },
                "backdoor": {
                    "name": "Back Door",
                    "url": "rtsp://10.0.6.165:8554/stream1"
                },
                "frontdoor": {
                    "name": "Front Door",
                    "url": "rtsp://10.0.4.60:8554/stream1"
                }
            }
            print(f"📸 Using {len(self.camera_configs)} default camera configurations")
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            self.camera_configs = {
                "test": {
                    "name": "Test Camera",
                    "url": "rtsp://10.0.4.67:8554/stream1"
                }
            }
            print(f"📸 Using {len(self.camera_configs)} fallback camera configurations")
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_border_width(20)
        self.add(main_box)
        
        # Title
        title_label = Gtk.Label()
        title_label.set_markup("<big><b>RTSP Video Stream Client</b></big>")
        main_box.pack_start(title_label, False, False, 0)
        
        # Camera selection with buttons instead of dropdown
        camera_label = Gtk.Label(label="Select Camera:")
        main_box.pack_start(camera_label, False, False, 0)
        
        # Camera buttons container
        camera_buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.pack_start(camera_buttons_box, False, False, 0)
        
        # Create camera selection buttons
        self.camera_buttons = {}
        self.selected_camera = None
        
        for camera_id, config in self.camera_configs.items():
            button = Gtk.Button(label=config["name"])
            button.connect("clicked", self.on_camera_button_clicked, camera_id)
            camera_buttons_box.pack_start(button, True, True, 0)
            self.camera_buttons[camera_id] = button
        
        # Select first camera by default
        if self.camera_configs:
            first_camera = list(self.camera_configs.keys())[0]
            self.selected_camera = first_camera
            self.camera_buttons[first_camera].get_style_context().add_class("selected-camera")
        
        # Connect/Disconnect buttons
        control_buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.pack_start(control_buttons_box, False, False, 0)
        
        self.connect_button = Gtk.Button(label="Connect")
        self.connect_button.connect("clicked", self.on_connect_clicked)
        control_buttons_box.pack_start(self.connect_button, False, False, 0)
        
        self.disconnect_button = Gtk.Button(label="Disconnect")
        self.disconnect_button.connect("clicked", self.on_disconnect_clicked)
        self.disconnect_button.set_sensitive(False)
        control_buttons_box.pack_start(self.disconnect_button, False, False, 0)
        
        # Test button for debugging
        self.test_button = Gtk.Button(label="Test Pattern")
        self.test_button.connect("clicked", self.on_test_clicked)
        control_buttons_box.pack_start(self.test_button, False, False, 0)
        
        # Status label
        self.status_label = Gtk.Label(label="Ready to connect")
        main_box.pack_start(self.status_label, False, False, 0)
        
        # Video container frame
        video_frame = Gtk.Frame()
        video_frame.set_label("Video Stream")
        video_frame.set_size_request(820, 480)  # Set minimum size for frame
        main_box.pack_start(video_frame, True, True, 0)
        
        # Video container - use Gtk.Fixed for absolute positioning
        self.video_container = Gtk.Fixed()
        self.video_container.set_size_request(800, 450)
        video_frame.add(self.video_container)
        
        # Initial placeholder
        self.create_placeholder()
        
        print(f"📺 UI setup complete with {len(self.camera_configs)} cameras")
        
    def create_placeholder(self):
        """Create placeholder widget for video area"""
        placeholder = Gtk.Label()
        placeholder.set_markup("<big>No video stream</big>\n\nSelect a camera and click Connect")
        placeholder.set_justify(Gtk.Justification.CENTER)
        placeholder.set_size_request(800, 450)
        
        # Clear container and add placeholder
        for child in self.video_container.get_children():
            self.video_container.remove(child)
        
        self.video_container.put(placeholder, 0, 0)
        placeholder.show()
    
    def check_widget_size(self, widget):
        """Check and log widget size after layout"""
        if hasattr(widget, 'get_allocation'):
            allocation = widget.get_allocation()
            print(f"🔍 Widget size after layout: {allocation.width}x{allocation.height}")
            
            # If still 1x1, try to force a proper size
            if allocation.width <= 1 or allocation.height <= 1:
                print("⚠️ Widget still too small, forcing resize...")
                widget.set_size_request(800, 450)
                widget.queue_resize()
                
        return False  # Don't repeat the timeout
    
    def debug_video_sink(self):
        """Debug video sink state and properties"""
        if not self.current_pipeline:
            return False
            
        # Get the gtksink element
        gtksink = self.current_pipeline.get_by_name("videosink")
        if gtksink:
            print("🔍 GTK Sink debugging:")
            widget = gtksink.get_property("widget")
            if widget:
                print(f"  📺 Sink widget: {type(widget)}")
                print(f"  📏 Widget size: {widget.get_allocated_width()}x{widget.get_allocated_height()}")
                print(f"  👁️ Widget visible: {widget.get_visible()}")
                print(f"  🎯 Widget realized: {widget.get_realized()}")
                print(f"  📐 Widget mapped: {widget.get_mapped()}")
                
                # Check if widget has a parent
                parent = widget.get_parent()
                print(f"  👨‍👧‍👦 Parent widget: {type(parent) if parent else 'None'}")
                
                # Force redraw
                widget.queue_draw()
                
            # Check sink state
            state = gtksink.get_state(Gst.CLOCK_TIME_NONE)
            print(f"  🎬 Sink state: {state[1].value_name if len(state) > 1 else 'Unknown'}")
            
            # Check if sink is receiving data
            sink_pad = gtksink.get_static_pad("sink")
            if sink_pad:
                print(f"  📡 Sink pad linked: {sink_pad.is_linked()}")
                caps = sink_pad.get_current_caps()
                if caps:
                    print(f"  🎞️ Current caps: {caps.to_string()}")
                else:
                    print("  ❌ No caps on sink pad")
        else:
            print("❌ Could not find gtksink element")
            
        return False  # Don't repeat timeout
    
    def test_simple_pipeline(self):
        """Test with a simple test pattern pipeline"""
        print("🧪 Testing with simple pipeline...")
        
        # Create a simple test pipeline
        test_pipeline = Gst.Pipeline.new("test-pipeline")
        
        # Use videotestsrc for testing
        videotestsrc = Gst.ElementFactory.make("videotestsrc", "testsrc")
        videotestsrc.set_property("pattern", 0)  # SMPTE test pattern
        
        videoconvert = Gst.ElementFactory.make("videoconvert", "convert")
        gtksink = Gst.ElementFactory.make("gtksink", "videosink")
        
        if not all([videotestsrc, videoconvert, gtksink]):
            print("❌ Failed to create test pipeline elements")
            return
        
        # Add elements to pipeline
        test_pipeline.add(videotestsrc)
        test_pipeline.add(videoconvert)
        test_pipeline.add(gtksink)
        
        # Link elements
        if not videotestsrc.link(videoconvert):
            print("❌ Failed to link videotestsrc to videoconvert")
            return
        if not videoconvert.link(gtksink):
            print("❌ Failed to link videoconvert to gtksink")
            return
            
        # Get the widget
        video_widget = gtksink.get_property("widget")
        if video_widget:
            print("✅ Test widget created")
            
            # Remove existing video widget and clear container
            for child in self.video_container.get_children():
                self.video_container.remove(child)
            
            # Add test widget
            self.video_widget = video_widget
            self.video_container.put(self.video_widget, 0, 0)
            self.video_widget.set_size_request(800, 450)
            self.video_widget.show()
            
            # Set up bus
            bus = test_pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.on_pipeline_message)
            
            # Start test pipeline
            print("🚀 Starting test pipeline...")
            ret = test_pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                print("❌ Failed to start test pipeline")
            else:
                print("✅ Test pipeline started")
                self.current_pipeline = test_pipeline
                self.current_camera = None  # Mark as test, not real camera
                self.status_label.set_text("🧪 Test pattern playing")
        else:
            print("❌ No widget from test gtksink")
    
    def on_camera_button_clicked(self, button, camera_id):
        """Handle camera selection button click"""
        print(f"� Selected camera: {camera_id}")
        
        # Update visual selection
        for btn_id, btn in self.camera_buttons.items():
            btn.get_style_context().remove_class("selected-camera")
        
        button.get_style_context().add_class("selected-camera")
        self.selected_camera = camera_id
        
        # Update status
        camera_name = self.camera_configs[camera_id]["name"]
        self.status_label.set_text(f"Selected: {camera_name}")
    
    def on_connect_clicked(self, button):
        """Handle connect button click"""
        print("🔘 Connect button clicked!")
        
        if not self.selected_camera:
            print("❌ No camera selected")
            self.status_label.set_text("Please select a camera")
            return
            
        camera_config = self.camera_configs[self.selected_camera]
        print(f"🎯 Connecting to: {camera_config}")
        self.connect_to_camera(camera_config)
    
    def on_disconnect_clicked(self, button):
        """Handle disconnect button click"""
        print("🔘 Disconnect button clicked!")
        self.disconnect_from_camera()
        self.connect_button.set_sensitive(True)
        self.disconnect_button.set_sensitive(False)
    
    def on_test_clicked(self, button):
        """Handle test button click"""
        print("🔘 Test button clicked!")
        # Stop any existing pipeline first
        if self.current_pipeline:
            self.disconnect_from_camera()
            import time
            time.sleep(0.1)  # Give it time to clean up
        
        self.test_simple_pipeline()
        self.connect_button.set_sensitive(True)
        self.disconnect_button.set_sensitive(True)
    
    def connect_to_camera(self, camera_config):
        """Connect to a camera and embed video in the UI"""
        rtsp_url = camera_config["url"]
        camera_name = camera_config["name"]
        
        self.status_label.set_text(f"Connecting to {camera_name}...")
        self.connect_button.set_sensitive(False)
        
        # Stop any existing pipeline first
        if self.current_pipeline:
            print("🛑 Stopping existing pipeline before creating new one")
            self.disconnect_from_camera()
            # Give it a moment to clean up
            import time
            time.sleep(0.1)
        
        try:
            print(f"🎥 Connecting to {camera_name} at {rtsp_url}")
            
            # Reset connection state
            self.pads_connected = False
            
            # Create GStreamer pipeline
            self.current_pipeline = Gst.Pipeline.new("video-pipeline")
            
            # Create elements with more robust settings
            rtspsrc = Gst.ElementFactory.make("rtspsrc", "source")
            if not rtspsrc:
                print("❌ Failed to create rtspsrc element")
                return False
                
            rtspsrc.set_property("location", rtsp_url)
            rtspsrc.set_property("latency", 50)  # Reduced latency
            rtspsrc.set_property("drop-on-latency", True)
            rtspsrc.set_property("timeout", 10)
            rtspsrc.set_property("tcp-timeout", 10000000)
            rtspsrc.set_property("retry", 5)
            rtspsrc.set_property("protocols", 1)  # GST_RTSP_LOWER_TRANS_UDP = 1
            
            # Simplified decoding chain
            rtph264depay = Gst.ElementFactory.make("rtph264depay", "depay")
            h264parse = Gst.ElementFactory.make("h264parse", "parse")
            avdec_h264 = Gst.ElementFactory.make("avdec_h264", "decode")
            
            if not all([rtph264depay, h264parse, avdec_h264]):
                print("❌ Failed to create decoder elements")
                return False
            
            # Set decoder properties for better performance
            if avdec_h264:
                avdec_h264.set_property("max-threads", 2)
            
            videoconvert = Gst.ElementFactory.make("videoconvert", "convert")
            if not videoconvert:
                print("❌ Failed to create videoconvert element")
                return False
            
            # Remove videoscale and capsfilter to reduce processing
            # videoscale = Gst.ElementFactory.make("videoscale", "scale")
            # capsfilter = Gst.ElementFactory.make("capsfilter", "caps")
            # caps = Gst.Caps.from_string("video/x-raw,width=800,height=450,framerate=15/1")
            # capsfilter.set_property("caps", caps)
            
            # Try gtksink first, fallback to other methods if it doesn't work
            gtksink = Gst.ElementFactory.make("gtksink", "videosink")
            video_widget = None
            
            if gtksink:
                try:
                    # Set sink properties for better performance
                    gtksink.set_property("sync", False)
                    gtksink.set_property("async", False)
                    
                    # Get the GTK widget from gtksink
                    video_widget = gtksink.get_property("widget")
                    if video_widget:
                        print("✅ Using gtksink with embedded widget")
                        sink_element = gtksink
                    else:
                        print("❌ gtksink widget creation failed")
                        gtksink = None
                except Exception as e:
                    print(f"❌ gtksink failed: {e}")
                    gtksink = None
            
            # Fallback to autovideosink if gtksink doesn't work
            if not gtksink:
                print("🔄 Falling back to autovideosink")
                sink_element = Gst.ElementFactory.make("autovideosink", "sink")
                if not sink_element:
                    raise Exception("Could not create any video sink")
                
                # Create a placeholder for external window notification
                placeholder = Gtk.Label()
                placeholder.set_markup("<big><b>Video playing in external window</b></big>\n\nGTK embedding not available.\nVideo stream opened in separate window.")
                placeholder.set_justify(Gtk.Justification.CENTER)
                video_widget = placeholder
            
            # Add all elements to pipeline  
            elements = [rtspsrc, rtph264depay, h264parse, avdec_h264, videoconvert, sink_element]
            for element in elements:
                self.current_pipeline.add(element)
            
            # Link static elements (skip rtspsrc - it will be linked dynamically)
            h264parse.link(avdec_h264)
            avdec_h264.link(videoconvert)
            videoconvert.link(sink_element)
            
            # Connect rtspsrc pad-added signal for dynamic linking
            rtspsrc.connect("pad-added", self.on_pad_added, rtph264depay)
            
            # Add debugging callbacks for all RTSP signals
            def on_select_stream(src, stream_id, caps):
                print(f"🎯 Stream selected: {stream_id}, caps: {caps.to_string()}")
                return True
                
            def on_new_manager(src, manager):
                print(f"📡 RTSP: New RTP manager created: {manager}")
                # Connect to manager signals to debug pad creation
                manager.connect("new-jitterbuffer", lambda mgr, jb, sess, ssrc: print(f"🔄 New jitter buffer: session {sess}, ssrc {ssrc}"))
                manager.connect("pad-added", lambda mgr, pad: print(f"🔄 RTP manager pad added: {pad.get_name()}"))
                return True
                
            def on_sdp_received(src, sdp):
                print(f"📋 RTSP: SDP received - checking for video tracks...")
                # Try to access SDP content for debugging
                try:
                    print(f"📋 SDP props not accessible")
                except:
                    print(f"📋 Stream info not accessible via properties")
                return True
            
            rtspsrc.connect("select-stream", on_select_stream)
            rtspsrc.connect("new-manager", on_new_manager) 
            rtspsrc.connect("handle-request", lambda src, req: print(f"📡 RTSP request: {req}"))
            
            # Add simple debugging callbacks
            rtspsrc.connect("no-more-pads", lambda src: print("🔚 no-more-pads signal received"))
            
            # Debug: Check if source has any pads right after creation (should be none initially)
            pad_iterator = rtspsrc.iterate_pads()
            pad_count = 0
            while True:
                ret, pad = pad_iterator.next()
                if ret == Gst.IteratorResult.DONE:
                    break
                elif ret == Gst.IteratorResult.OK:
                    pad_count += 1
                else:
                    break
            def check_delayed_pads():
                """Check for pads after a delay"""
                print("🕐 Checking for pads after 3 seconds...")
                pad_iterator = rtspsrc.iterate_pads()
                pad_count = 0
                pads = []
                while True:
                    ret, pad = pad_iterator.next()
                    if ret == Gst.IteratorResult.DONE:
                        break
                    elif ret == Gst.IteratorResult.OK:
                        pad_count += 1
                        pads.append(pad.get_name())
                    else:
                        break
                print(f"🔍 RTSP source pads after delay: {pad_count} pads: {pads}")
                return False  # Don't repeat
            
            # Schedule delayed pad check
            GLib.timeout_add_seconds(3, check_delayed_pads)
            
            # Add RTSP connection monitoring
            rtspsrc.connect("new-manager", self.on_new_manager)
            try:
                rtspsrc.connect("on-sdp", self.on_sdp_received)
            except:
                pass  # Not all GStreamer versions have this signal
            
            # Handle the video widget display
            if video_widget:
                print("✅ GTK video widget created successfully!")
                print(f"🔍 Widget type: {type(video_widget)}")
                
                # Clear video container and add the video widget
                for child in self.video_container.get_children():
                    self.video_container.remove(child)
                
                # Set explicit size and place at origin
                video_widget.set_size_request(800, 450)
                self.video_container.put(video_widget, 0, 0)
                
                # Force widget to be shown and realized
                video_widget.show_all()
                
                if hasattr(video_widget, 'realize'):
                    video_widget.realize()
                    print(f"🔍 Widget realized: {video_widget.get_realized()}")
                
                # Force a resize after adding to container
                GLib.timeout_add(100, self.check_widget_size, video_widget)
                
                # Additional debugging for gtksink widget
                if hasattr(video_widget, 'get_allocation'):
                    allocation = video_widget.get_allocation()
                    print(f"🔍 Widget allocation: {allocation.width}x{allocation.height}")
            else:
                raise Exception("Could not create video display widget")
            
            # Connect to pipeline messages
            bus = self.current_pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.on_pipeline_message)
            
            # Store camera info
            self.current_camera_config = camera_config
            
            # Start the pipeline
            print("🚀 Starting pipeline...")
            ret = self.current_pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                raise Exception("Failed to start pipeline")
            
            print(f"🎬 Pipeline started for {camera_name}")
            
            # Add a timeout to check for pad creation
            GLib.timeout_add(5000, self.check_rtsp_connection, camera_name)
            
            self.status_label.set_text(f"Connecting to {camera_name}...")
            self.disconnect_button.set_sensitive(True)
            self.current_camera = camera_config
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.status_label.set_text(f"Connection failed: {e}")
            self.connect_button.set_sensitive(True)
            if self.current_pipeline:
                self.current_pipeline.set_state(Gst.State.NULL)
                self.current_pipeline = None
            self.create_placeholder()
    
    def check_rtsp_connection(self, camera_name):
        """Check if RTSP connection produced any video pads"""
        if not self.current_pipeline:
            return False
            
        print(f"🕐 Checking RTSP connection for {camera_name} after 5 seconds...")
        
        # Check if we have any video pads
        rtspsrc = self.current_pipeline.get_by_name("source")
        if rtspsrc:
            # List all pads on rtspsrc
            iterator = rtspsrc.iterate_src_pads()
            pad_count = 0
            done = False
            while not done:
                result, pad = iterator.next()
                if result == Gst.IteratorResult.OK:
                    pad_count += 1
                    caps = pad.get_current_caps()
                    if caps:
                        print(f"  📡 Found pad: {pad.get_name()} with caps: {caps.to_string()}")
                    else:
                        print(f"  📡 Found pad: {pad.get_name()} (no caps)")
                elif result == Gst.IteratorResult.DONE:
                    done = True
                else:
                    break
            
            if pad_count == 0:
                print("❌ No source pads found - RTSP stream may not contain video")
                self.status_label.set_text("No video streams found")
            else:
                print(f"✅ Found {pad_count} source pads")
        
        return False  # Don't repeat
    
    def on_pad_added(self, src, new_pad, sink_element):
        """Handle dynamic pad addition from rtspsrc"""
        print(f"🔗 Pad added from {src.get_name()}: {new_pad.get_name()}")
        
        new_pad_caps = new_pad.get_current_caps()
        if not new_pad_caps:
            print("❌ No caps on new pad")
            return
        
        new_pad_struct = new_pad_caps.get_structure(0)
        new_pad_type = new_pad_struct.get_name()
        print(f"🎬 New pad type: {new_pad_type}")
        print(f"📺 New pad caps: {new_pad_caps.to_string()}")
        
        # Look for RTP video streams - check the structure for video media
        if new_pad_type.startswith("application/x-rtp"):
            # Check if this is a video stream
            media_type = new_pad_struct.get_string("media")
            encoding = new_pad_struct.get_string("encoding-name")
            print(f"🎯 Media type: {media_type}, Encoding: {encoding}")
            
            if media_type == "video":
                print(f"✅ Found video RTP stream - linking to {sink_element.get_name()}")
                sink_pad = sink_element.get_static_pad("sink")
                if sink_pad and not sink_pad.is_linked():
                    ret = new_pad.link(sink_pad)
                    if ret == Gst.PadLinkReturn.OK:
                        print(f"✅ Successfully linked {new_pad_type} video pad")
                        self.pads_connected = True
                    else:
                        print(f"❌ Failed to link pad: {ret}")
                else:
                    print(f"⚠️ Sink pad already linked or not available")
            else:
                print(f"🚫 Ignoring non-video stream: {media_type}")
        else:
            print(f"🚫 Ignoring non-RTP pad: {new_pad_type}")
    
    def on_new_manager(self, rtspsrc, manager):
        """Handle new RTP manager creation"""
        print(f"📡 RTSP: New RTP manager created: {manager}")
        return True
    
    def on_sdp_received(self, element, message):
        """Callback when SDP is received from RTSP server"""
        print("📋 RTSP: SDP received - checking for video tracks...")
        
        # Try to extract SDP info from the element
        if hasattr(element, 'props'):
            sdp_info = getattr(element.props, 'sdp', None)
            if sdp_info:
                print(f"📋 SDP details: {sdp_info}")
            else:
                print("📋 SDP props not accessible")
        
        # Check if any streams were negotiated
        if hasattr(element, 'get_property'):
            try:
                streams = element.get_property('streams')
                if streams:
                    print(f"📊 RTSP streams detected: {len(streams)} streams")
                    for i, stream in enumerate(streams):
                        print(f"  Stream {i}: {stream}")
                else:
                    print("⚠️ No RTSP streams detected")
            except:
                print("📋 Stream info not accessible via properties")
    
    def check_rtsp_connection(self, camera_name):
        """Check if RTSP connection created any video pads"""
        if not self.current_pipeline:
            return False
            
        # Get the rtspsrc element
        rtspsrc = self.current_pipeline.get_by_name("source")
        if rtspsrc:
            # Count source pads
            pad_count = 0
            iterator = rtspsrc.iterate_src_pads()
            done = False
            while not done:
                result, pad = iterator.next()
                if result == Gst.IteratorResult.OK:
                    if pad:
                        pad_count += 1
                        caps = pad.get_current_caps()
                        if caps:
                            struct = caps.get_structure(0)
                            print(f"🔍 Found pad: {pad.get_name()} with caps: {struct.get_name()}")
                elif result == Gst.IteratorResult.DONE:
                    done = True
                else:
                    break
            
            print(f"📊 RTSP Connection Status for {camera_name}:")
            print(f"  📡 Total source pads created: {pad_count}")
            print(f"  🔗 Video pads connected: {self.pads_connected}")
            
            if pad_count == 0:
                print("❌ No source pads created - stream may not contain video or is incompatible")
                self.status_label.set_text(f"No video stream found in {camera_name}")
            elif not self.pads_connected:
                print(f"⚠️ Found {pad_count} source pads but none matched video format")
                self.status_label.set_text(f"Incompatible video format in {camera_name}")
            else:
                print(f"✅ Successfully connected to video stream")
        
        return False  # Don't repeat
    
    def on_pipeline_message(self, bus, message):
        """Handle pipeline messages"""
        if message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"❌ Pipeline error: {err}")
            print(f"🔍 Debug info: {debug}")
            self.status_label.set_text(f"Stream error: {err.message}")
            
        elif message.type == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            print(f"⚠️ Pipeline warning: {warn}")
            print(f"🔍 Debug info: {debug}")
            
        elif message.type == Gst.MessageType.INFO:
            info, debug = message.parse_info()
            print(f"ℹ️ Pipeline info: {info}")
            
        elif message.type == Gst.MessageType.EOS:
            print("📺 End of stream")
            self.status_label.set_text("Stream ended")
            
        elif message.type == Gst.MessageType.STATE_CHANGED:
            if message.src == self.current_pipeline:
                old_state, new_state, pending_state = message.parse_state_changed()
                print(f"🔄 State changed: {old_state.value_name} -> {new_state.value_name}")
                if new_state == Gst.State.PLAYING:
                    print("▶️ Pipeline is now playing")
                    if self.current_camera:
                        self.status_label.set_text(f"🎬 Playing: {self.current_camera['name']}")
                    else:
                        self.status_label.set_text("🎬 Playing test pattern")
                    # Debug video sink when playing
                    GLib.timeout_add(1000, self.debug_video_sink)
                elif new_state == Gst.State.PAUSED:
                    print("⏸️ Pipeline paused")
                    if self.current_camera:
                        self.status_label.set_text(f"⏸️ Paused: {self.current_camera['name']}")
                    else:
                        self.status_label.set_text("⏸️ Test pattern paused")
                    
        elif message.type == Gst.MessageType.STREAM_START:
            print("🌊 Stream started")
            
        elif message.type == Gst.MessageType.BUFFERING:
            percent = message.parse_buffering()
            print(f"📊 Buffering: {percent}%")
            if percent < 100:
                self.status_label.set_text(f"Buffering: {percent}%")
        
        # Add more detailed debugging for RTSP
        elif message.type == Gst.MessageType.ELEMENT:
            struct = message.get_structure()
            if struct:
                print(f"🔧 Element message: {struct.get_name()}")
                
        elif message.type == Gst.MessageType.ASYNC_DONE:
            print("🔄 Async done - pipeline ready")
            
        elif message.type == Gst.MessageType.NEW_CLOCK:
            clock = message.parse_new_clock()
            print(f"🕐 New clock: {clock}")
        
        return True
    
    def disconnect_from_camera(self):
        """Disconnect from current camera"""
        if self.current_pipeline:
            print("🛑 Stopping pipeline")
            # Stop the pipeline properly
            self.current_pipeline.set_state(Gst.State.NULL)
            # Wait for state change to complete
            ret = self.current_pipeline.get_state(Gst.CLOCK_TIME_NONE)
            print(f"🔄 Pipeline stopped with state: {ret[1].value_name if len(ret) > 1 else 'Unknown'}")
            
            # Remove bus watch
            bus = self.current_pipeline.get_bus()
            if bus:
                bus.remove_signal_watch()
            
            # Force cleanup - remove all elements
            try:
                iterator = self.current_pipeline.iterate_elements()
                done = False
                while not done:
                    result, element = iterator.next()
                    if result == Gst.IteratorResult.OK:
                        if element:
                            element.set_state(Gst.State.NULL)
                    elif result == Gst.IteratorResult.DONE:
                        done = True
                    else:
                        break
            except:
                pass  # Ignore cleanup errors
            
            # Clear pipeline reference
            self.current_pipeline = None
        
        self.current_camera = None
        self.status_label.set_text("Disconnected")
        self.connect_button.set_sensitive(True)
        self.disconnect_button.set_sensitive(False)
        
        # Restore placeholder
        self.create_placeholder()
    
    def apply_styling(self):
        """Apply CSS styling"""
        css = """
        window {
            background-color: #2c3e50;
            color: #ecf0f1;
        }
        
        label {
            color: #ecf0f1;
        }
        
        frame {
            border: 2px solid #34495e;
            border-radius: 8px;
        }
        
        frame > label {
            background-color: #34495e;
            padding: 5px 10px;
            color: #ecf0f1;
            font-weight: bold;
        }
        
        button {
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
            margin: 2px;
        }
        
        button:hover {
            background-color: #2980b9;
        }
        
        button:disabled {
            background-color: #7f8c8d;
            color: #bdc3c7;
        }
        
        /* Camera selection buttons */
        button.selected-camera {
            background-color: #e74c3c;
            color: white;
        }
        
        button.selected-camera:hover {
            background-color: #c0392b;
        }
        """
        
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode())
        screen = Gdk.Screen.get_default()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

def main():
    """Main application entry point"""
    print("🚀 Starting RTSP Client application...")
    
    try:
        app = RTSPClient()
        print("✅ Application created successfully")
        
        app.show_all()
        print("👁️ UI shown, entering main loop...")
        
        Gtk.main()
        print("🏁 Main loop ended")
        
    except Exception as e:
        print(f"❌ Application error: {e}")
        import traceback
        traceback.print_exc()
    except KeyboardInterrupt:
        print("\n👋 Application interrupted by user")
    finally:
        print("🔚 Application cleanup")
        try:
            Gtk.main_quit()
        except:
            pass

if __name__ == "__main__":
    main()