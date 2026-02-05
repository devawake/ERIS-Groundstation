document.addEventListener('DOMContentLoaded', () => {
    // ==========================================
    // 1. SOCKET.IO CONNECTION
    // ==========================================
    const socket = io();
    const statusDot = document.querySelector('.status-dot');
    const connText = document.querySelector('.conn-text');
    const missionTimer = document.getElementById('mission-timer');

    let missionStartTime = null;
    let timerInterval = null;

    socket.on('connect', () => {
        statusDot.classList.add('connected');
        connText.textContent = "LIVE";
        console.log("Connected to Ground Station Server");
    });

    socket.on('disconnect', () => {
        statusDot.classList.remove('connected');
        connText.textContent = "OFFLINE";
    });

    socket.on('log', (data) => {
        console.log("Server Log:", data.msg);
    });

    socket.on('telemetry', (data) => {
        // Start mission timer on first packet
        if (!missionStartTime) {
            missionStartTime = Date.now();
            startMissionTimer();
        }
        updateDashboard(data);
    });

    function startMissionTimer() {
        timerInterval = setInterval(() => {
            const elapsed = Date.now() - missionStartTime;
            const hours = Math.floor(elapsed / 3600000);
            const minutes = Math.floor((elapsed % 3600000) / 60000);
            const seconds = Math.floor((elapsed % 60000) / 1000);
            missionTimer.textContent = `T+ ${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }, 1000);
    }

    // ==========================================
    // 2. DOM ELEMENTS
    // ==========================================
    const els = {
        alt: document.getElementById('alt-val'),
        maxAlt: document.getElementById('max-alt-val'),
        vel: document.getElementById('vel-val'),
        lat: document.getElementById('lat-val'),
        lon: document.getElementById('lon-val'),
        ax: document.getElementById('ax-val'),
        ay: document.getElementById('ay-val'),
        az: document.getElementById('az-val'),
        sats: document.getElementById('sats-val'),
        rssi: document.getElementById('rssi-val'),
    };

    let maxAltitude = 0.0;
    let lastAlt = 0.0;
    let lastTime = Date.now();

    function updateDashboard(data) {
        // Update simple values
        animateValue(els.alt, data.alt.toFixed(1));
        els.sats.innerText = data.sats;
        els.rssi.innerText = data.rssi;
        els.lat.innerText = data.lat.toFixed(5);
        els.lon.innerText = data.lon.toFixed(5);
        els.ax.innerText = data.ax.toFixed(2);
        els.ay.innerText = data.ay.toFixed(2);
        els.az.innerText = data.az.toFixed(2);

        // Max Altitude Logic
        if (data.alt > maxAltitude) {
            maxAltitude = data.alt;
            animateValue(els.maxAlt, maxAltitude.toFixed(1));
        }

        // Velocity Calculation
        const now = Date.now();
        const dt = (now - lastTime) / 1000;
        if (dt > 0) {
            const v = (data.alt - lastAlt) / dt;
            els.vel.innerText = v.toFixed(1) + " m/s";
        }
        lastAlt = data.alt;
        lastTime = now;

        // Update Modules
        updateMap(data.lat, data.lon);
        updateChart(data.time, data.alt);
        updateRocketOrientation(data.ax, data.ay, data.az);
    }

    function animateValue(element, newValue) {
        element.innerText = newValue;
        element.style.transform = 'scale(1.05)';
        setTimeout(() => {
            element.style.transform = 'scale(1)';
        }, 100);
    }

    // ==========================================
    // 3. LEAFLET MAP
    // ==========================================
    const map = L.map('map', {
        zoomControl: true,
        attributionControl: true,
        touchZoom: true,
        dragging: true
    }).setView([51.505, -0.09], 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap',
        maxZoom: 19
    }).addTo(map);

    const rocketIcon = L.divIcon({
        className: 'rocket-marker',
        html: `<div style="
            background: linear-gradient(135deg, #00e5ff, #4d9fff);
            width: 14px;
            height: 14px;
            border-radius: 50%;
            box-shadow: 0 0 15px #00e5ff, 0 0 30px rgba(0, 229, 255, 0.5);
            border: 2px solid rgba(255,255,255,0.8);
        "></div>`,
        iconSize: [14, 14]
    });

    let rocketMarker = L.marker([51.505, -0.09], { icon: rocketIcon }).addTo(map);
    let pathLine = L.polyline([], {
        color: '#00e5ff',
        weight: 3,
        opacity: 0.8
    }).addTo(map);

    function updateMap(lat, lon) {
        if (lat === 0 && lon === 0) return;

        const newLatLng = [lat, lon];
        rocketMarker.setLatLng(newLatLng);
        pathLine.addLatLng(newLatLng);
    }

    // ==========================================
    // 4. CHART.JS
    // ==========================================
    const ctx = document.getElementById('telemetryChart').getContext('2d');

    // Create gradient for chart fill
    const chartGradient = ctx.createLinearGradient(0, 0, 0, 200);
    chartGradient.addColorStop(0, 'rgba(0, 229, 255, 0.3)');
    chartGradient.addColorStop(1, 'rgba(0, 229, 255, 0.02)');

    const telemetryChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Altitude (m)',
                data: [],
                borderColor: '#00e5ff',
                backgroundColor: chartGradient,
                borderWidth: 2,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHoverBackgroundColor: '#00e5ff',
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 0
            },
            interaction: {
                mode: 'nearest',
                intersect: false
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(10, 15, 24, 0.9)',
                    titleColor: '#8ba4c4',
                    bodyColor: '#00e5ff',
                    borderColor: 'rgba(0, 229, 255, 0.3)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 10
                }
            },
            scales: {
                x: {
                    display: false,
                    grid: { display: false }
                },
                y: {
                    grid: {
                        color: 'rgba(100, 150, 200, 0.1)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#546a8e',
                        font: { family: "'JetBrains Mono', monospace", size: 10 },
                        padding: 8
                    },
                    border: { display: false }
                }
            }
        }
    });

    function updateChart(timeLabel, altitude) {
        const labels = telemetryChart.data.labels;
        const data = telemetryChart.data.datasets[0].data;

        labels.push(timeLabel);
        data.push(altitude);

        // Keep last 60 points for smoother graph
        if (labels.length > 60) {
            labels.shift();
            data.shift();
        }

        telemetryChart.update('none');
    }

    // ==========================================
    // 5. THREE.JS - ERIS ROCKET MODEL
    // ==========================================
    const container = document.getElementById('rocket-3d-model');
    const scene = new THREE.Scene();

    // Fixed camera position to view rocket orientation
    const camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.01, 100000);
    camera.position.set(0, 1.5, 5);
    camera.lookAt(0, 0, 0);

    // Renderer
    const renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
        powerPreference: "high-performance"
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Enhanced Lighting
    const ambientLight = new THREE.AmbientLight(0x404060, 2);
    scene.add(ambientLight);

    const mainLight = new THREE.DirectionalLight(0xffffff, 2);
    mainLight.position.set(5, 5, 5);
    scene.add(mainLight);

    const fillLight = new THREE.DirectionalLight(0x00e5ff, 1);
    fillLight.position.set(-5, -2, 3);
    scene.add(fillLight);

    // Reference grid to show orientation
    const gridHelper = new THREE.GridHelper(6, 10, 0x00e5ff, 0x1a2a3a);
    gridHelper.position.y = -2.5;
    scene.add(gridHelper);

    // Load ERIS OBJ Model
    let rocketModel = null;

    OBJLoader.load(
        'static/eris.obj',
        function (object) {
            // Apply materials
            object.traverse(function (child) {
                if (child instanceof THREE.Mesh) {
                    child.material = new THREE.MeshPhongMaterial({
                        color: 0xffffff,
                        specular: 0x666666,
                        shininess: 40
                    });
                }
            });

            // Calculate size and center
            const box = new THREE.Box3().setFromObject(object);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());

            // Create a wrapper for robust centering and scaling
            const wrapper = new THREE.Group();
            wrapper.add(object);

            // Center inner object
            object.position.set(-center.x, -center.y, -center.z);

            // Scale wrapper to fit view (target ~4.5 units)
            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 4.5 / maxDim;
            wrapper.scale.set(scale, scale, scale);

            rocketModel = wrapper;
            scene.add(rocketModel);

            console.log('Model loaded. Wrapper scale:', scale, 'Original MaxDim:', maxDim);
        },
        function (xhr) { },
        function (error) {
            console.error('Error loading ERIS model:', error);
            createFallbackRocket();
        }
    );

    // Fallback procedural rocket if OBJ fails to load
    function createFallbackRocket() {
        const rocket = new THREE.Group();

        const bodyGeo = new THREE.CylinderGeometry(0.4, 0.4, 3, 32);
        const matWhite = new THREE.MeshPhongMaterial({ color: 0xffffff });
        const body = new THREE.Mesh(bodyGeo, matWhite);
        rocket.add(body);

        const noseGeo = new THREE.ConeGeometry(0.4, 0.8, 32);
        const nose = new THREE.Mesh(noseGeo, matWhite);
        nose.position.y = 1.9;
        rocket.add(nose);

        const finGeo = new THREE.BoxGeometry(0.15, 0.8, 1);
        const matRed = new THREE.MeshPhongMaterial({ color: 0xff3b5c });

        for (let i = 0; i < 4; i++) {
            const fin = new THREE.Mesh(finGeo, matRed);
            fin.position.y = -1.2;
            fin.rotation.y = (Math.PI / 2) * i;
            fin.position.x = Math.sin((Math.PI / 2) * i) * 0.4;
            fin.position.z = Math.cos((Math.PI / 2) * i) * 0.4;
            rocket.add(fin);
        }

        rocketModel = rocket;
        scene.add(rocketModel);
        console.log('Using fallback rocket model');
    }

    // Handle Resize
    window.addEventListener('resize', () => {
        const width = container.clientWidth;
        const height = container.clientHeight;
        renderer.setSize(width, height);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
    });

    function animate() {
        requestAnimationFrame(animate);
        renderer.render(scene, camera);
    }
    animate();

    function updateRocketOrientation(ax, ay, az) {
        if (!rocketModel) return;

        // Apply smooth rotation based on accelerometer data
        // Assuming Z is up, rotating based on X and Y tilt
        const targetRotationZ = THREE.MathUtils.degToRad(ax * 10);
        const targetRotationX = THREE.MathUtils.degToRad(ay * 10);

        // Smooth interpolation for natural movement
        rocketModel.rotation.z += (targetRotationZ - rocketModel.rotation.z) * 0.15;
        rocketModel.rotation.x += (targetRotationX - rocketModel.rotation.x) * 0.15;
    }
});
