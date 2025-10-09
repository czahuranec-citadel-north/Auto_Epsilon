/**
 * Citadel North - Laser Scan Visualization
 * Connects to ROS via rosbridge and displays laser scan data
 */

class LaserScanVisualization {
    constructor(containerId, rosbridgeUrl) {
        this.container = document.getElementById(containerId);
        this.rosbridgeUrl = rosbridgeUrl;
        this.ros = null;
        this.laserScanTopic = null;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.laserPoints = null;
        this.connectionStatus = 'disconnected';

        // Laser scan data
        this.scanData = {
            ranges: [],
            angle_min: 0,
            angle_max: 0,
            angle_increment: 0,
            range_min: 0,
            range_max: 0
        };

        this.init();
    }

    init() {
        // Create status indicator
        this.createStatusIndicator();

        // Create scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x2B2D2A);

        // Create camera
        const width = this.container.clientWidth;
        const height = this.container.clientHeight - 40; // Account for status bar
        this.camera = new THREE.OrthographicCamera(
            width / -100, width / 100,
            height / 100, height / -100,
            0.1, 1000
        );
        this.camera.position.set(0, 0, 10);
        this.camera.lookAt(0, 0, 0);

        // Create renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height - 40);
        this.container.appendChild(this.renderer.domElement);

        // Add lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
        this.scene.add(ambientLight);

        // Create robot center indicator
        const robotGeometry = new THREE.CircleGeometry(0.3, 32);
        const robotMaterial = new THREE.MeshBasicMaterial({ color: 0xFFFFFF });
        const robot = new THREE.Mesh(robotGeometry, robotMaterial);
        this.scene.add(robot);

        // Add forward direction indicator
        const arrowGeometry = new THREE.ConeGeometry(0.2, 0.5, 8);
        const arrowMaterial = new THREE.MeshBasicMaterial({ color: 0xFDB913 });
        const arrow = new THREE.Mesh(arrowGeometry, arrowMaterial);
        arrow.position.y = 0.5;
        arrow.rotation.z = -Math.PI / 2;
        this.scene.add(arrow);

        // Create grid
        const gridHelper = new THREE.GridHelper(20, 20, 0xFDB913, 0x444444);
        gridHelper.rotation.x = Math.PI / 2;
        this.scene.add(gridHelper);

        // Create laser scan points
        const pointsGeometry = new THREE.BufferGeometry();
        const pointsMaterial = new THREE.PointsMaterial({
            color: 0xFF0000,
            size: 0.15,
            sizeAttenuation: false
        });
        this.laserPoints = new THREE.Points(pointsGeometry, pointsMaterial);
        this.scene.add(this.laserPoints);

        // Add orbit controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableRotate = true;
        this.controls.enableZoom = true;
        this.controls.enablePan = true;

        // Connect to ROS
        this.connectToROS();

        // Start animation loop
        this.animate();

        // Handle window resize
        window.addEventListener('resize', () => this.onWindowResize(), false);
    }

    createStatusIndicator() {
        const statusBar = document.createElement('div');
        statusBar.id = 'ros-status';
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
        statusBar.textContent = 'Connecting to ROS...';
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
        this.updateStatus('connecting', 'Connecting to ROS...');

        // Create ROS connection
        this.ros = new ROSLIB.Ros({
            url: this.rosbridgeUrl
        });

        this.ros.on('connection', () => {
            console.log('Connected to rosbridge');
            this.updateStatus('connected', '✓ Connected to ROS');
            this.subscribeLaserScan();
        });

        this.ros.on('error', (error) => {
            console.error('Error connecting to rosbridge:', error);
            this.updateStatus('disconnected', '✗ Connection Error - Check rosbridge');
        });

        this.ros.on('close', () => {
            console.log('Connection to rosbridge closed');
            this.updateStatus('disconnected', '✗ Disconnected from ROS');
            // Attempt to reconnect after 3 seconds
            setTimeout(() => this.connectToROS(), 3000);
        });
    }

    subscribeLaserScan() {
        this.laserScanTopic = new ROSLIB.Topic({
            ros: this.ros,
            name: '/world',
            messageType: 'sensor_msgs/LaserScan'
        });

        this.laserScanTopic.subscribe((message) => {
            this.scanData = {
                ranges: message.ranges,
                angle_min: message.angle_min,
                angle_max: message.angle_max,
                angle_increment: message.angle_increment,
                range_min: message.range_min,
                range_max: message.range_max
            };
            this.updateLaserScan();
        });

        console.log('Subscribed to /world topic');
    }

    updateLaserScan() {
        const positions = [];
        const colors = [];

        for (let i = 0; i < this.scanData.ranges.length; i++) {
            const range = this.scanData.ranges[i];

            // Skip invalid readings
            if (isNaN(range) || range < this.scanData.range_min || range > this.scanData.range_max) {
                continue;
            }

            // Calculate angle for this reading
            const angle = this.scanData.angle_min + (i * this.scanData.angle_increment);

            // Convert polar to Cartesian coordinates
            const x = range * Math.cos(angle);
            const y = range * Math.sin(angle);

            positions.push(x, y, 0);

            // Color based on distance (red = close, yellow = far)
            const normalizedRange = (range - this.scanData.range_min) /
                                   (this.scanData.range_max - this.scanData.range_min);
            const red = 1.0;
            const green = normalizedRange;
            const blue = 0.0;
            colors.push(red, green, blue);
        }

        // Update geometry
        const positionsArray = new Float32Array(positions);
        const colorsArray = new Float32Array(colors);

        this.laserPoints.geometry.setAttribute(
            'position',
            new THREE.BufferAttribute(positionsArray, 3)
        );
        this.laserPoints.geometry.setAttribute(
            'color',
            new THREE.BufferAttribute(colorsArray, 3)
        );
        this.laserPoints.material.vertexColors = true;
        this.laserPoints.geometry.attributes.position.needsUpdate = true;
        this.laserPoints.geometry.attributes.color.needsUpdate = true;
    }

    animate() {
        requestAnimationFrame(() => this.animate());

        if (this.controls) {
            this.controls.update();
        }

        this.renderer.render(this.scene, this.camera);
    }

    onWindowResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight - 40;

        this.camera.left = width / -100;
        this.camera.right = width / 100;
        this.camera.top = height / 100;
        this.camera.bottom = height / -100;
        this.camera.updateProjectionMatrix();

        this.renderer.setSize(width, height);
    }

    disconnect() {
        if (this.laserScanTopic) {
            this.laserScanTopic.unsubscribe();
        }
        if (this.ros) {
            this.ros.close();
        }
    }
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('laser-scan-container')) {
        // Default rosbridge URL - user can modify in config
        const rosbridgeUrl = window.ROSBRIDGE_URL || 'ws://localhost:9090';
        window.laserScanViz = new LaserScanVisualization('laser-scan-container', rosbridgeUrl);
    }
});
