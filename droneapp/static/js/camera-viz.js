/**
 * Citadel North - Camera Visualization via ROS Bridge
 * Subscribes to camera topic and displays images on canvas
 */

class CameraVisualization {
    constructor(containerId, rosbridgeUrl, cameraTopic) {
        this.container = document.getElementById(containerId);
        this.rosbridgeUrl = rosbridgeUrl;
        this.cameraTopic = cameraTopic || '/camera/color/image_raw';
        this.ros = null;
        this.cameraSubscriber = null;
        this.canvas = null;
        this.ctx = null;
        this.connectionStatus = 'disconnected';
        this.frameCount = 0;
        this.lastFrameTime = Date.now();
        this.fps = 0;

        this.init();
    }

    init() {
        // Create status indicator
        this.createStatusIndicator();

        // Create canvas
        this.canvas = document.createElement('canvas');
        this.canvas.style.cssText = `
            width: 100%;
            height: 100%;
            object-fit: contain;
            background-color: #1a1b19;
            border-radius: 4px;
        `;
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');

        // Connect to ROS
        this.connectToROS();
    }

    createStatusIndicator() {
        const statusBar = document.createElement('div');
        statusBar.id = 'camera-status';
        statusBar.style.cssText = `
            padding: 8px;
            background-color: #1a1b19;
            border-radius: 4px;
            margin-bottom: 5px;
            text-align: center;
            font-size: 14px;
            color: #FDB913;
            font-weight: 600;
        `;
        statusBar.textContent = 'Connecting to camera...';
        this.container.insertBefore(statusBar, this.container.firstChild);
        this.statusBar = statusBar;
    }

    updateStatus(status, message) {
        this.connectionStatus = status;
        const colors = {
            connected: '#00FF00',
            connecting: '#FDB913',
            disconnected: '#FF0000'
        };
        this.statusBar.style.color = colors[status] || '#FDB913';
        this.statusBar.textContent = message;
    }

    connectToROS() {
        this.updateStatus('connecting', 'Connecting to camera...');

        // Create ROS connection
        this.ros = new ROSLIB.Ros({
            url: this.rosbridgeUrl
        });

        this.ros.on('connection', () => {
            console.log('Camera viewer connected to rosbridge');
            this.updateStatus('connected', '✓ Camera Connected');
            this.subscribeToCamera();
        });

        this.ros.on('error', (error) => {
            console.error('Camera viewer error connecting to rosbridge:', error);
            this.updateStatus('disconnected', '✗ Connection Error');
        });

        this.ros.on('close', () => {
            console.log('Camera viewer connection to rosbridge closed');
            this.updateStatus('disconnected', '✗ Disconnected');
            // Attempt to reconnect after 3 seconds
            setTimeout(() => this.connectToROS(), 3000);
        });
    }

    subscribeToCamera() {
        // List available topics first for debugging
        this.listTopics();

        // Try compressed image first, fallback to raw
        this.subscribeCompressedImage();
    }

    listTopics() {
        // Get list of all topics to help with debugging
        this.ros.getTopics((topics) => {
            console.log('Available ROS topics:');

            // Filter for image-related topics
            const imageTopics = topics.topics.filter(topic =>
                topic.includes('image') || topic.includes('camera')
            );

            if (imageTopics.length > 0) {
                console.log('Image/Camera topics found:', imageTopics);
            } else {
                console.warn('No image or camera topics found. All topics:', topics.topics);
            }
        }, (error) => {
            console.error('Error getting topics:', error);
        });
    }

    subscribeCompressedImage() {
        console.log(`Attempting to subscribe to ${this.cameraTopic}/compressed`);

        this.cameraSubscriber = new ROSLIB.Topic({
            ros: this.ros,
            name: this.cameraTopic + '/compressed',
            messageType: 'sensor_msgs/CompressedImage'
        });

        let receivedMessage = false;
        const timeout = setTimeout(() => {
            if (!receivedMessage) {
                console.log('No compressed images received, trying raw image topic');
                this.updateStatus('connecting', 'Trying raw image topic...');
                this.cameraSubscriber.unsubscribe();
                this.subscribeRawImage();
            }
        }, 3000);

        this.cameraSubscriber.subscribe((message) => {
            receivedMessage = true;
            clearTimeout(timeout);
            console.log('Compressed image received:', {
                format: message.format,
                dataLength: message.data ? message.data.length : 0,
                hasData: !!message.data
            });
            this.handleCompressedImage(message);
        });
    }

    subscribeRawImage() {
        console.log(`Subscribing to ${this.cameraTopic} (raw)`);
        this.updateStatus('connecting', 'Waiting for raw images...');

        this.cameraSubscriber = new ROSLIB.Topic({
            ros: this.ros,
            name: this.cameraTopic,
            messageType: 'sensor_msgs/Image'
        });

        this.cameraSubscriber.subscribe((message) => {
            console.log('Raw image message received:', {
                width: message.width,
                height: message.height,
                encoding: message.encoding,
                dataLength: message.data ? message.data.length : 0,
                hasData: !!message.data
            });
            this.handleRawImage(message);
        });
    }

    handleCompressedImage(message) {
        // Update FPS counter
        this.updateFPS();

        // CompressedImage has data field with base64 encoded JPEG/PNG
        if (!message.data) {
            console.error('Compressed image has no data field');
            return;
        }

        const imageData = 'data:image/jpeg;base64,' + message.data;

        const img = new Image();
        img.onload = () => {
            // Set canvas size to match image on first frame
            if (this.canvas.width !== img.width || this.canvas.height !== img.height) {
                console.log(`Setting canvas size to ${img.width}x${img.height}`);
                this.canvas.width = img.width;
                this.canvas.height = img.height;
            }

            // Draw image to canvas
            this.ctx.drawImage(img, 0, 0);
        };
        img.onerror = (error) => {
            console.error('Error loading compressed image:', error);
            console.log('Image data preview:', imageData.substring(0, 100) + '...');
        };
        img.src = imageData;
    }

    handleRawImage(message) {
        // Update FPS counter
        this.updateFPS();

        // Raw image has width, height, encoding, and data fields
        const width = message.width;
        const height = message.height;
        const encoding = message.encoding;
        const data = message.data;

        if (!data || data.length === 0) {
            console.error('Raw image has no data');
            return;
        }

        console.log(`Processing raw image: ${width}x${height}, encoding: ${encoding}, data type: ${typeof data}`);

        // Set canvas size if needed
        if (this.canvas.width !== width || this.canvas.height !== height) {
            console.log(`Setting canvas size to ${width}x${height}`);
            this.canvas.width = width;
            this.canvas.height = height;
        }

        // Decode base64 data to byte array
        // ROS bridge sends image data as base64 encoded string
        let byteArray;
        if (typeof data === 'string') {
            // Decode base64 string to binary
            const binaryString = atob(data);
            byteArray = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                byteArray[i] = binaryString.charCodeAt(i);
            }
            console.log(`Decoded base64 to ${byteArray.length} bytes`);
        } else {
            // Already a byte array
            byteArray = new Uint8Array(data);
        }

        // Create ImageData object
        const imageData = this.ctx.createImageData(width, height);

        // Convert based on encoding
        if (encoding === 'rgb8') {
            // RGB8: 3 bytes per pixel
            for (let i = 0; i < byteArray.length; i += 3) {
                const idx = (i / 3) * 4;
                imageData.data[idx] = byteArray[i];         // R
                imageData.data[idx + 1] = byteArray[i + 1]; // G
                imageData.data[idx + 2] = byteArray[i + 2]; // B
                imageData.data[idx + 3] = 255;              // A
            }
        } else if (encoding === 'bgr8') {
            // BGR8: 3 bytes per pixel (reversed)
            for (let i = 0; i < byteArray.length; i += 3) {
                const idx = (i / 3) * 4;
                imageData.data[idx] = byteArray[i + 2];     // R
                imageData.data[idx + 1] = byteArray[i + 1]; // G
                imageData.data[idx + 2] = byteArray[i];     // B
                imageData.data[idx + 3] = 255;              // A
            }
        } else if (encoding === 'rgba8') {
            // RGBA8: 4 bytes per pixel
            for (let i = 0; i < byteArray.length; i++) {
                imageData.data[i] = byteArray[i];
            }
        } else if (encoding === 'bgra8') {
            // BGRA8: 4 bytes per pixel (reversed)
            for (let i = 0; i < byteArray.length; i += 4) {
                imageData.data[i] = byteArray[i + 2];       // R
                imageData.data[i + 1] = byteArray[i + 1];   // G
                imageData.data[i + 2] = byteArray[i];       // B
                imageData.data[i + 3] = byteArray[i + 3];   // A
            }
        } else if (encoding === 'mono8' || encoding === 'grayscale') {
            // Grayscale: 1 byte per pixel
            for (let i = 0; i < byteArray.length; i++) {
                const idx = i * 4;
                const gray = byteArray[i];
                imageData.data[idx] = gray;
                imageData.data[idx + 1] = gray;
                imageData.data[idx + 2] = gray;
                imageData.data[idx + 3] = 255;
            }
        } else {
            console.warn(`Unsupported image encoding: ${encoding}`);
            return;
        }

        // Put the image data on the canvas
        this.ctx.putImageData(imageData, 0, 0);
        console.log('Image rendered to canvas');
    }

    updateFPS() {
        this.frameCount++;
        const now = Date.now();
        const elapsed = now - this.lastFrameTime;

        // Update FPS every second
        if (elapsed >= 1000) {
            this.fps = Math.round((this.frameCount * 1000) / elapsed);
            this.updateStatus('connected', `✓ Camera Connected (${this.fps} FPS)`);
            this.frameCount = 0;
            this.lastFrameTime = now;
        }
    }

    disconnect() {
        if (this.cameraSubscriber) {
            this.cameraSubscriber.unsubscribe();
        }
        if (this.ros) {
            this.ros.close();
        }
    }
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('camera-container')) {
        const rosbridgeUrl = window.ROSBRIDGE_URL || 'ws://localhost:9090';
        const cameraTopic = '/camera/color/image_raw';
        window.cameraViz = new CameraVisualization('camera-container', rosbridgeUrl, cameraTopic);
    }
});
