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
        this.goalPublisher = null;
        this.cancelPublisher = null;
        this.pathSubscriber = null;
        this.statusSubscriber = null;
        this.pathLine = null;
        this.navigationStatus = 'IDLE';
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

        // Navigation goal
        this.goalMarker = null;
        this.goalPosition = null;
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();

        this.init();
    }

    init() {
        // Create status indicator
        this.createStatusIndicator();

        // Create navigation controls
        this.createNavigationControls();

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

        // Create goal marker (initially hidden)
        this.createGoalMarker();

        // Create path line (initially hidden)
        this.createPathLine();

        // Add orbit controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableRotate = true;
        this.controls.enableZoom = true;
        this.controls.enablePan = true;

        // Add click handler for setting navigation goals
        this.renderer.domElement.addEventListener('click', (event) => this.onCanvasClick(event), false);

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

    createNavigationControls() {
        const controlsDiv = document.createElement('div');
        controlsDiv.id = 'nav-controls';
        controlsDiv.style.cssText = `
            display: none;
            padding: 10px;
            background-color: rgba(42, 45, 42, 0.9);
            border-radius: 4px;
            margin-bottom: 5px;
            text-align: center;
            gap: 10px;
        `;

        // Send Goal button
        const sendButton = document.createElement('button');
        sendButton.textContent = 'Send Goal';
        sendButton.style.cssText = `
            padding: 8px 16px;
            background-color: #00FF00;
            color: #000;
            border: none;
            border-radius: 4px;
            font-weight: 600;
            cursor: pointer;
            margin-right: 10px;
        `;
        sendButton.onclick = () => this.sendGoal();

        // Cancel Goal button
        const cancelButton = document.createElement('button');
        cancelButton.textContent = 'Cancel Goal';
        cancelButton.style.cssText = `
            padding: 8px 16px;
            background-color: #FFA500;
            color: #000;
            border: none;
            border-radius: 4px;
            font-weight: 600;
            cursor: pointer;
            margin-right: 10px;
        `;
        cancelButton.onclick = () => {
            this.clearGoal();
            this.hideNavigationControls();
        };

        // Stop Navigation button (emergency stop)
        const stopButton = document.createElement('button');
        stopButton.textContent = 'STOP Navigation';
        stopButton.style.cssText = `
            padding: 8px 16px;
            background-color: #FF0000;
            color: #FFF;
            border: none;
            border-radius: 4px;
            font-weight: 600;
            cursor: pointer;
        `;
        stopButton.onclick = () => this.cancelNavigation();

        controlsDiv.appendChild(sendButton);
        controlsDiv.appendChild(cancelButton);
        controlsDiv.appendChild(stopButton);

        this.container.insertBefore(controlsDiv, this.container.firstChild);
        this.navControls = controlsDiv;
    }

    showNavigationControls() {
        if (this.navControls) {
            this.navControls.style.display = 'block';
        }
    }

    hideNavigationControls() {
        if (this.navControls) {
            this.navControls.style.display = 'none';
        }
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
            this.setupGoalPublisher();
            this.subscribePath();
            this.subscribeNavigationStatus();
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

    setupGoalPublisher() {
        // Create publisher for navigation goals
        // Using move_base_simple/goal topic (geometry_msgs/PoseStamped)
        this.goalPublisher = new ROSLIB.Topic({
            ros: this.ros,
            name: '/move_base_simple/goal',
            messageType: 'geometry_msgs/PoseStamped'
        });

        console.log('Goal publisher created for /move_base_simple/goal');

        // Create publisher for canceling navigation goals
        this.cancelPublisher = new ROSLIB.Topic({
            ros: this.ros,
            name: '/move_base/cancel',
            messageType: 'actionlib_msgs/GoalID'
        });

        console.log('Cancel publisher created for /move_base/cancel');
    }

    cancelNavigation() {
        if (!this.cancelPublisher) {
            console.error('Cancel publisher not initialized');
            return;
        }

        // Publish empty GoalID to cancel all goals
        const cancelMessage = new ROSLIB.Message({
            stamp: {
                secs: 0,
                nsecs: 0
            },
            id: ''  // Empty ID cancels all goals
        });

        this.cancelPublisher.publish(cancelMessage);
        console.log('Navigation canceled');

        this.updateStatus('connected', '✓ Navigation Canceled');
        this.clearGoal();
    }

    subscribePath() {
        // Subscribe to the global planner path
        // Common topics: /move_base/NavfnROS/plan, /move_base/GlobalPlanner/plan, or /plan
        this.pathSubscriber = new ROSLIB.Topic({
            ros: this.ros,
            name: '/move_base/NavfnROS/plan',  // Adjust based on your ROS setup
            messageType: 'nav_msgs/Path'
        });

        this.pathSubscriber.subscribe((message) => {
            console.log(`Received path with ${message.poses.length} poses`);
            this.updatePath(message.poses);
        });

        console.log('Subscribed to /move_base/NavfnROS/plan');
    }

    subscribeNavigationStatus() {
        // Subscribe to move_base status to monitor navigation progress
        this.statusSubscriber = new ROSLIB.Topic({
            ros: this.ros,
            name: '/move_base/status',
            messageType: 'actionlib_msgs/GoalStatusArray'
        });

        this.statusSubscriber.subscribe((message) => {
            if (message.status_list && message.status_list.length > 0) {
                // Get the most recent goal status
                const latestStatus = message.status_list[message.status_list.length - 1];
                this.handleNavigationStatus(latestStatus);
            }
        });

        console.log('Subscribed to /move_base/status');
    }

    handleNavigationStatus(status) {
        // GoalStatus values:
        // 0: PENDING, 1: ACTIVE, 2: PREEMPTED, 3: SUCCEEDED,
        // 4: ABORTED, 5: REJECTED, 6: PREEMPTING, 7: RECALLING,
        // 8: RECALLED, 9: LOST

        const statusMap = {
            0: 'PENDING',
            1: 'ACTIVE',
            2: 'PREEMPTED',
            3: 'SUCCEEDED',
            4: 'ABORTED',
            5: 'REJECTED',
            6: 'PREEMPTING',
            7: 'RECALLING',
            8: 'RECALLED',
            9: 'LOST'
        };

        const statusName = statusMap[status.status] || 'UNKNOWN';
        this.navigationStatus = statusName;

        // Update UI based on status
        switch(status.status) {
            case 1: // ACTIVE
                this.updateStatus('connected', `🚁 Navigating... (${statusName})`);
                break;
            case 3: // SUCCEEDED
                this.updateStatus('connected', `✓ Goal Reached! (${statusName})`);
                this.clearGoal();
                break;
            case 4: // ABORTED
            case 5: // REJECTED
                this.updateStatus('disconnected', `✗ Navigation Failed (${statusName})`);
                break;
            default:
                if (this.goalPosition) {
                    this.updateStatus('connected', `⏱ ${statusName}`);
                }
                break;
        }

        console.log(`Navigation status: ${statusName} (${status.status})`);
    }

    createPathLine() {
        // Create a line to visualize the navigation path
        const lineGeometry = new THREE.BufferGeometry();
        const lineMaterial = new THREE.LineBasicMaterial({
            color: 0x00FFFF,  // Cyan color for the path
            linewidth: 3
        });
        this.pathLine = new THREE.Line(lineGeometry, lineMaterial);
        this.pathLine.visible = false;
        this.scene.add(this.pathLine);
    }

    updatePath(poses) {
        if (!poses || poses.length === 0) {
            this.pathLine.visible = false;
            return;
        }

        // Extract positions from poses
        const positions = [];
        for (let i = 0; i < poses.length; i++) {
            const pose = poses[i].pose;
            positions.push(pose.position.x, pose.position.y, 0.1);  // Slightly above ground
        }

        // Update the line geometry
        const positionsArray = new Float32Array(positions);
        this.pathLine.geometry.setAttribute(
            'position',
            new THREE.BufferAttribute(positionsArray, 3)
        );
        this.pathLine.geometry.attributes.position.needsUpdate = true;
        this.pathLine.visible = true;

        console.log(`Path visualization updated with ${poses.length} waypoints`);
    }

    publishNavigationGoal(x, y, yaw = 0) {
        if (!this.goalPublisher) {
            console.error('Goal publisher not initialized');
            return;
        }

        // Create PoseStamped message
        const goalMessage = new ROSLIB.Message({
            header: {
                frame_id: 'map', // or 'odom' depending on your setup
                stamp: {
                    secs: Math.floor(Date.now() / 1000),
                    nsecs: (Date.now() % 1000) * 1000000
                }
            },
            pose: {
                position: {
                    x: x,
                    y: y,
                    z: 0.0
                },
                orientation: {
                    x: 0.0,
                    y: 0.0,
                    z: Math.sin(yaw / 2),
                    w: Math.cos(yaw / 2)
                }
            }
        });

        // Publish the goal
        this.goalPublisher.publish(goalMessage);
        console.log(`Published navigation goal: x=${x.toFixed(2)}, y=${y.toFixed(2)}, yaw=${yaw.toFixed(2)}`);

        this.updateStatus('connected', `✓ Goal Published! Moving to (${x.toFixed(2)}, ${y.toFixed(2)})`);
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

    createGoalMarker() {
        // Create a group for the goal marker
        const goalGroup = new THREE.Group();

        // Create a cone pointing up (green)
        const coneGeometry = new THREE.ConeGeometry(0.3, 0.6, 8);
        const coneMaterial = new THREE.MeshBasicMaterial({ color: 0x00FF00 });
        const cone = new THREE.Mesh(coneGeometry, coneMaterial);
        cone.rotation.z = -Math.PI / 2; // Point in forward direction

        // Create a circle base
        const circleGeometry = new THREE.CircleGeometry(0.4, 32);
        const circleMaterial = new THREE.MeshBasicMaterial({
            color: 0x00FF00,
            transparent: true,
            opacity: 0.3
        });
        const circle = new THREE.Mesh(circleGeometry, circleMaterial);

        goalGroup.add(cone);
        goalGroup.add(circle);
        goalGroup.visible = false; // Hidden by default

        this.goalMarker = goalGroup;
        this.scene.add(this.goalMarker);
    }

    onCanvasClick(event) {
        // Calculate mouse position in normalized device coordinates (-1 to +1)
        const rect = this.renderer.domElement.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        // Update the raycaster with the camera and mouse position
        this.raycaster.setFromCamera(this.mouse, this.camera);

        // Create a plane at z=0 to intersect with
        const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
        const intersectPoint = new THREE.Vector3();

        // Find intersection point
        if (this.raycaster.ray.intersectPlane(plane, intersectPoint)) {
            this.setGoalPosition(intersectPoint.x, intersectPoint.y);
        }
    }

    setGoalPosition(x, y) {
        // Store the goal position
        this.goalPosition = { x: x, y: y };

        // Move the goal marker to the clicked position
        this.goalMarker.position.set(x, y, 0.1);
        this.goalMarker.visible = true;

        // Update status
        this.updateStatus('connected', `✓ Goal Set: (${x.toFixed(2)}, ${y.toFixed(2)}) - Click 'Send Goal' to navigate`);

        console.log(`Navigation goal set to: x=${x.toFixed(2)}, y=${y.toFixed(2)}`);

        // Show the navigation control buttons
        this.showNavigationControls();
    }

    sendGoal() {
        if (!this.goalPosition) {
            console.warn('No goal position set');
            return;
        }

        // Publish the navigation goal to ROS
        this.publishNavigationGoal(this.goalPosition.x, this.goalPosition.y);
    }

    clearGoal() {
        this.goalPosition = null;
        this.goalMarker.visible = false;
        this.hideNavigationControls();
        this.updateStatus('connected', '✓ Connected to ROS');
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
