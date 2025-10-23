/**
 * Citadel North - Drone 3D Visualization
 * RViz-like visualization using Three.js
 */

class DroneVisualization {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.drone = null;
        this.grid = null;
        this.axes = null;
        this.trajectoryLine = null;
        this.trajectoryPoints = [];
        this.maxTrajectoryPoints = 100;

        // Telemetry data
        this.telemetry = {
            altitude: 0,
            pitch: 0,
            roll: 0,
            yaw: 0,
            position: { x: 0, y: 0, z: 0 },
            battery: 100
        };

        this.init();
        this.animate();
        this.startTelemetryUpdates();
    }

    init() {
        // Create scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x2B2D2A);
        this.scene.fog = new THREE.Fog(0x2B2D2A, 10, 50);

        // Create camera
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        this.camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
        this.camera.position.set(5, 5, 5);
        this.camera.lookAt(0, 0, 0);

        // Create renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.renderer.shadowMap.enabled = true;
        this.container.appendChild(this.renderer.domElement);

        // Add lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(10, 20, 10);
        directionalLight.castShadow = true;
        this.scene.add(directionalLight);

        const goldLight = new THREE.PointLight(0xFDB913, 0.5, 100);
        goldLight.position.set(0, 10, 0);
        this.scene.add(goldLight);

        // Create ground grid
        const gridHelper = new THREE.GridHelper(20, 20, 0xFDB913, 0x444444);
        this.scene.add(gridHelper);

        // Create axes helper
        const axesHelper = new THREE.AxesHelper(5);
        this.scene.add(axesHelper);

        // Create drone model
        this.createDrone();

        // Create trajectory line
        const trajectoryGeometry = new THREE.BufferGeometry();
        const trajectoryMaterial = new THREE.LineBasicMaterial({
            color: 0xFDB913,
            linewidth: 2
        });
        this.trajectoryLine = new THREE.Line(trajectoryGeometry, trajectoryMaterial);
        this.scene.add(this.trajectoryLine);

        // Add orbit controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;

        // Handle window resize
        window.addEventListener('resize', () => this.onWindowResize(), false);
    }

    createDrone() {
        // Create a simple drone model
        const droneGroup = new THREE.Group();

        // Main body (rectangular box)
        const bodyGeometry = new THREE.BoxGeometry(0.6, 0.2, 0.6);
        const bodyMaterial = new THREE.MeshPhongMaterial({
            color: 0xFDB913,
            emissive: 0xFDB913,
            emissiveIntensity: 0.2
        });
        const body = new THREE.Mesh(bodyGeometry, bodyMaterial);
        body.castShadow = true;
        droneGroup.add(body);

        // Create 4 arms
        const armGeometry = new THREE.CylinderGeometry(0.05, 0.05, 0.8, 8);
        const armMaterial = new THREE.MeshPhongMaterial({ color: 0x333333 });

        const positions = [
            { x: 0.5, z: 0.5, rot: Math.PI / 4 },
            { x: -0.5, z: 0.5, rot: -Math.PI / 4 },
            { x: 0.5, z: -0.5, rot: -Math.PI / 4 },
            { x: -0.5, z: -0.5, rot: Math.PI / 4 }
        ];

        positions.forEach(pos => {
            const arm = new THREE.Mesh(armGeometry, armMaterial);
            arm.position.set(pos.x, 0, pos.z);
            arm.rotation.z = pos.rot;
            arm.castShadow = true;
            droneGroup.add(arm);

            // Add propeller
            const propGeometry = new THREE.CylinderGeometry(0.3, 0.3, 0.02, 32);
            const propMaterial = new THREE.MeshPhongMaterial({
                color: 0xFFFFFF,
                transparent: true,
                opacity: 0.3
            });
            const propeller = new THREE.Mesh(propGeometry, propMaterial);
            propeller.position.set(pos.x, 0.3, pos.z);
            propeller.rotation.x = Math.PI / 2;
            droneGroup.add(propeller);
        });

        // Add forward indicator (white cone pointing forward)
        const coneGeometry = new THREE.ConeGeometry(0.1, 0.3, 8);
        const coneMaterial = new THREE.MeshPhongMaterial({ color: 0xFFFFFF });
        const cone = new THREE.Mesh(coneGeometry, coneMaterial);
        cone.position.set(0, 0.2, -0.4);
        cone.rotation.x = Math.PI / 2;
        droneGroup.add(cone);

        this.drone = droneGroup;
        this.scene.add(this.drone);
    }

    updateDrone(telemetry) {
        if (!this.drone) return;

        // Update position
        this.drone.position.y = telemetry.altitude || 0;

        // Update orientation (convert degrees to radians)
        const pitch = THREE.MathUtils.degToRad(telemetry.pitch || 0);
        const roll = THREE.MathUtils.degToRad(telemetry.roll || 0);
        const yaw = THREE.MathUtils.degToRad(telemetry.yaw || 0);

        this.drone.rotation.set(pitch, yaw, roll, 'YXZ');

        // Update trajectory
        this.updateTrajectory();

        // Update camera to follow drone
        const targetY = Math.max(2, telemetry.altitude + 2);
        this.camera.position.y += (targetY - this.camera.position.y) * 0.05;
    }

    updateTrajectory() {
        const currentPos = new THREE.Vector3(
            this.drone.position.x,
            this.drone.position.y,
            this.drone.position.z
        );

        // Add point if drone has moved significantly
        if (this.trajectoryPoints.length === 0 ||
            currentPos.distanceTo(this.trajectoryPoints[this.trajectoryPoints.length - 1]) > 0.1) {
            this.trajectoryPoints.push(currentPos.clone());

            // Limit trajectory points
            if (this.trajectoryPoints.length > this.maxTrajectoryPoints) {
                this.trajectoryPoints.shift();
            }

            // Update line geometry
            const positions = new Float32Array(this.trajectoryPoints.length * 3);
            this.trajectoryPoints.forEach((point, i) => {
                positions[i * 3] = point.x;
                positions[i * 3 + 1] = point.y;
                positions[i * 3 + 2] = point.z;
            });

            this.trajectoryLine.geometry.setAttribute(
                'position',
                new THREE.BufferAttribute(positions, 3)
            );
            this.trajectoryLine.geometry.attributes.position.needsUpdate = true;
        }
    }

    startTelemetryUpdates() {
        // Poll telemetry data every 100ms
        setInterval(() => {
            this.fetchTelemetry();
        }, 100);
    }

    async fetchTelemetry() {
        try {
            const response = await fetch('/api/telemetry/');
            const data = await response.json();
            this.telemetry = data;
            this.updateDrone(data);
        } catch (error) {
            console.error('Failed to fetch telemetry:', error);
        }
    }

    animate() {
        requestAnimationFrame(() => this.animate());

        // Update controls
        if (this.controls) {
            this.controls.update();
        }

        // Rotate propellers for visual effect
        if (this.drone && this.telemetry.altitude > 0.1) {
            this.drone.children.forEach(child => {
                if (child.geometry && child.geometry.type === 'CylinderGeometry' &&
                    child.material.transparent) {
                    child.rotation.z += 0.5; // Fast rotation
                }
            });
        }

        this.renderer.render(this.scene, this.camera);
    }

    onWindowResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;

        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();

        this.renderer.setSize(width, height);
    }
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('drone-viz-container')) {
        window.droneViz = new DroneVisualization('drone-viz-container');
    }
});
