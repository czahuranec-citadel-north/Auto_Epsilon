#!/usr/bin/env python3
"""
ROS2 Camera Stream
------------------
Subscribes to ROS2 camera topic (bridged from Gazebo) and serves images via Flask
"""

import io
import threading
import time
import base64
from PIL import Image
import numpy as np


class CameraStream:
    """Singleton camera stream handler"""

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.running = False
        self.ros2_available = False
        self.frame_count = 0

        # For ROS2 callback
        self.latest_msg = None
        self.msg_lock = threading.Lock()

        # Try to import ROS2
        try:
            import rclpy
            from sensor_msgs.msg import Image as RosImage

            self.rclpy = rclpy
            self.RosImage = RosImage
            self.ros2_available = True
            print("📷 ROS2 available")
        except ImportError as e:
            print(f"⚠️ ROS2 not available, using placeholder: {e}")
            self.ros2_available = False

        # Start camera capture thread
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _capture_loop(self):
        """Capture camera frames from ROS2"""
        self.running = True
        print("📷 Camera stream started")

        if self.ros2_available:
            self._ros2_camera_loop()
        else:
            self._placeholder_loop()

    def _image_callback(self, msg):
        """ROS2 callback for camera images"""
        try:
            # Process ROS2 Image message
            width = msg.width
            height = msg.height
            encoding = msg.encoding

            # Convert image data to numpy array
            img_data = np.frombuffer(msg.data, dtype=np.uint8)

            # Handle different encodings
            if encoding == 'rgb8':
                img_array = img_data.reshape((height, width, 3))
                img = Image.fromarray(img_array, 'RGB')
            elif encoding == 'rgba8':
                img_array = img_data.reshape((height, width, 4))
                img = Image.fromarray(img_array, 'RGBA').convert('RGB')
            elif encoding == 'bgr8':
                img_array = img_data.reshape((height, width, 3))
                # Convert BGR to RGB
                img_array = img_array[:, :, ::-1]
                img = Image.fromarray(img_array, 'RGB')
            elif encoding == 'mono8' or encoding == 'grayscale':
                img_array = img_data.reshape((height, width))
                img = Image.fromarray(img_array, 'L').convert('RGB')
            else:
                print(f"⚠️ Unsupported encoding: {encoding}")
                return

            # Convert to JPEG
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            buffer.seek(0)

            with self.frame_lock:
                self.latest_frame = buffer.getvalue()

            self.frame_count += 1

            # Log first frame received
            if self.frame_count == 1:
                print(f"✅ First camera frame received: {width}x{height}, encoding={encoding}")

        except Exception as e:
            print(f"Image callback error: {e}")
            import traceback
            traceback.print_exc()

    def _ros2_camera_loop(self):
        """Capture frames using ROS2 subscriber"""
        try:
            # Initialize ROS2 in this thread
            self.rclpy.init()

            # Create a minimal node
            node = self.rclpy.create_node('camera_stream_node')

            # Subscribe to /camera topic
            subscription = node.create_subscription(
                self.RosImage,
                '/camera',
                self._image_callback,
                10  # QoS depth
            )

            print("✅ Subscribed to ROS2 /camera topic, waiting for frames...")

            # Spin to process callbacks
            while self.running:
                self.rclpy.spin_once(node, timeout_sec=0.1)

            # Cleanup
            node.destroy_node()
            self.rclpy.shutdown()

        except Exception as e:
            print(f"ROS2 camera error: {e}, falling back to placeholder")
            import traceback
            traceback.print_exc()
            self._placeholder_loop()

    def _placeholder_loop(self):
        """Generate placeholder images when Gazebo is not available"""
        while self.running:
            try:
                # Create placeholder image
                img = Image.new('RGB', (640, 480), color=(42, 45, 42))

                # Add text overlay
                from PIL import ImageDraw, ImageFont
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
                except:
                    font = ImageFont.load_default()

                draw.text((180, 200), "Camera Feed", fill=(253, 185, 19), font=font)
                draw.text((140, 240), "Waiting for ROS2...", fill=(200, 200, 200), font=font)

                # Add instructions
                try:
                    small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
                except:
                    small_font = font
                draw.text((100, 300), "Start ros_gz_bridge and PX4 SITL", fill=(150, 150, 150), font=small_font)

                # Convert to JPEG
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                buffer.seek(0)

                with self.frame_lock:
                    self.latest_frame = buffer.getvalue()

                time.sleep(0.2)  # 5 FPS for placeholder

            except Exception as e:
                print(f"Placeholder generation error: {e}")
                time.sleep(1)

    def get_frame(self):
        """Get latest camera frame as JPEG bytes"""
        with self.frame_lock:
            if self.latest_frame:
                return self.latest_frame
            else:
                # Return empty image if no frame available
                img = Image.new('RGB', (640, 480), color=(0, 0, 0))
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG')
                buffer.seek(0)
                return buffer.getvalue()

    def get_frame_base64(self):
        """Get latest frame as base64-encoded string"""
        frame = self.get_frame()
        return base64.b64encode(frame).decode('utf-8')

    def stop(self):
        """Stop camera stream"""
        self.running = False
