/**
 * FORMULA PRO: ULTIMATE RESCUE EDITION
 * Fully Stabilized, Peer-to-Peer, AAA-Style Physics
 */

// --- Global Engine ---
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87CEEB); 
scene.fog = new THREE.Fog(0x87CEEB, 200, 1200);

const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 3000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;
document.getElementById('game-container').appendChild(renderer.domElement);

const clock = new THREE.Clock();
scene.add(new THREE.AmbientLight(0xffffff, 0.5));
const sun = new THREE.DirectionalLight(0xffffff, 1.2);
sun.position.set(50, 200, 50);
sun.castShadow = true;
scene.add(sun);

// --- Game State ---
let GAME_STATE = 'START';
let gameMode = 'SOLO'; // 'SOLO', 'HOST', 'JOIN'
let isHost = false;
let peer, conn, myPeerId;

let velocity = 0;
let maxVelocity = 5;
let frameCount = 0;
let selectedModel = 'MCLAREN';
let cameraMode = 0; // 0: Chase, 1: Cockpit

// Audio Synthesizer
let audioCtx;
let engineOsc;
let engineGain;

// New Mechanics State
let isNight = false;
let headlights = [];
let isDrafting = false;
let drsActive = false;
let currentCurve = 0;
let sparkParticles, smokeParticles;

let playerDistance = 0;
let isStunned = false;
let stunTimer = 0;
const GOAL_DISTANCE = 100000;
let raceFinished = false;

const players = {}; // { id: { mesh, x, targetX, name, team, color } }
const obstacles = [];
const scenery = [];

// --- Factory: High Detail F1 Car ---
function createF1(team, color) {
    const group = new THREE.Group();
    const mat = new THREE.MeshPhongMaterial({ color: color, shininess: 100 });
    const black = new THREE.MeshPhongMaterial({ color: 0x15151e });

    // Chassis
    const body = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.4, 4), mat);
    body.position.y = 0.35;
    group.add(body);

    // Halo
    const halo = new THREE.Mesh(new THREE.TorusGeometry(0.35, 0.05, 8, 16, Math.PI), black);
    halo.position.set(0, 0.75, 0.5);
    halo.rotation.x = -Math.PI / 2;
    group.add(halo);

    // Wings
    const fw = new THREE.Mesh(new THREE.BoxGeometry(2.8, 0.05, 0.8), black);
    fw.position.set(0, 0.1, 3.5);
    group.add(fw);
    const rw = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.1, 0.8), mat);
    rw.position.set(0, 1.0, -1.8);
    group.add(rw);

    // Wheels
    const wGeo = new THREE.CylinderGeometry(0.55, 0.55, 0.5, 32);
    wGeo.rotateZ(Math.PI / 2);
    for (let i = 0; i < 4; i++) {
        const w = new THREE.Mesh(wGeo, black);
        w.position.set(i % 2 ? 1.3 : -1.3, 0.55, i < 2 ? 1.7 : -1.7);
        group.add(w);
    }
    return group;
}

// --- Environment Setup ---
const roadWidth = 32;
for (let i = 0; i < 60; i++) {
    const road = new THREE.Mesh(new THREE.PlaneGeometry(roadWidth, 20.2), new THREE.MeshPhongMaterial({ color: 0x333333 }));
    road.rotation.x = -Math.PI / 2;
    road.position.z = -i * 20;
    road.receiveShadow = true;
    scene.add(road);
    scenery.push(road);

    // Kerbs
    const kGeo = new THREE.PlaneGeometry(3, 20.2);
    const kMat = new THREE.MeshBasicMaterial({ color: i % 2 ? 0xffffff : 0xff0000 });
    const lk = new THREE.Mesh(kGeo, kMat);
    lk.rotation.x = -Math.PI / 2;
    lk.position.set(-roadWidth/2 - 1.5, 0.01, -i * 20);
    scene.add(lk);
    scenery.push(lk);
    const rk = lk.clone(); rk.position.x = roadWidth/2 + 1.5;
    scene.add(rk);
    scenery.push(rk);

    // Grass (Real Life Green)
    const gGeo = new THREE.PlaneGeometry(200, 20.2);
    const gMat = new THREE.MeshPhongMaterial({ color: 0x228B22 }); // Forest Green
    const lg = new THREE.Mesh(gGeo, gMat);
    lg.rotation.x = -Math.PI / 2;
    lg.position.set(-115, -0.05, -i * 20);
    scene.add(lg);
    scenery.push(lg);
    const rg = lg.clone(); rg.position.x = 115;
    scene.add(rg);
    scenery.push(rg);
}

// --- VFX Systems ---
function createParticles() {
    const sGeo = new THREE.BufferGeometry();
    const sPos = new Float32Array(200 * 3);
    sGeo.setAttribute('position', new THREE.BufferAttribute(sPos, 3));
    const sMat = new THREE.PointsMaterial({ color: 0xffaa00, size: 0.2, transparent: true, opacity: 0 });
    sparkParticles = new THREE.Points(sGeo, sMat);
    scene.add(sparkParticles);

    const smGeo = new THREE.BufferGeometry();
    const smPos = new Float32Array(200 * 3);
    smGeo.setAttribute('position', new THREE.BufferAttribute(smPos, 3));
    const smMat = new THREE.PointsMaterial({ color: 0xdddddd, size: 0.5, transparent: true, opacity: 0 });
    smokeParticles = new THREE.Points(smGeo, smMat);
    scene.add(smokeParticles);
}
createParticles();

// --- Networking (PeerJS) ---
function setupPeer() {
    peer = new Peer();
    peer.on('open', (id) => {
        myPeerId = id;
        document.getElementById('room-id-display').innerText = id;
        document.getElementById('connection-status').innerText = 'READY';
    });
    peer.on('connection', (c) => {
        if (!isHost) return;
        c.on('data', (data) => {
            if (data.type === 'JOIN') {
                const car = createF1(data.team, data.color);
                scene.add(car);
                players[c.peer] = { mesh: car, x: 0, targetX: 0, name: data.name, team: data.team, color: data.color, distance: 0 };
                connections[c.peer] = c;
            }
            if (data.type === 'MOVE') {
                if (players[c.peer]) {
                    players[c.peer].targetX = data.x;
                    players[c.peer].distance = data.distance;
                }
            }
        });
    });
}
const connections = {};

function joinLobby(id) {
    conn = peer.connect(id);
    conn.on('open', () => {
        conn.send({
            type: 'JOIN',
            name: document.getElementById('player-name-input').value || 'PILOT',
            team: selectedModel,
            color: document.getElementById('car-color-input').value
        });
        startGame('JOIN');
    });
    conn.on('data', (data) => {
        if (data.type === 'STATE') syncFromServer(data);
        if (data.type === 'LEADERBOARD') showLeaderboard(data.standings);
        if (data.type === 'REMATCH') resetRace();
    });
}

function syncFromServer(data) {
    data.players.forEach(pData => {
        if (pData.id === myPeerId) return;
        if (!players[pData.id]) {
            const car = createF1(pData.team, pData.color);
            scene.add(car);
            players[pData.id] = { mesh: car, x: 0, targetX: 0, name: pData.name, distance: 0 };
        }
        players[pData.id].targetX = pData.x;
        players[pData.id].distance = pData.distance;
    });
}

// --- Input Handling ---
const keys = { w: false, s: false, a: false, d: false, ArrowUp: false, ArrowDown: false, ArrowLeft: false, ArrowRight: false };
window.addEventListener('keydown', e => { 
    if (keys.hasOwnProperty(e.key)) keys[e.key] = true; 
    if (e.key === 'c' || e.key === 'C') cameraMode = (cameraMode + 1) % 2;
    if (e.key === 'n' || e.key === 'N') toggleNightMode();
    if (e.code === 'Space') {
        if (isDrafting && !drsActive) drsActive = true;
    }
});
window.addEventListener('keyup', e => { if (keys.hasOwnProperty(e.key)) keys[e.key] = false; });

function toggleNightMode() {
    isNight = !isNight;
    if (isNight) {
        scene.background = new THREE.Color(0x050510);
        scene.fog = new THREE.Fog(0x050510, 50, 400);
        sun.intensity = 0.1;
        headlights.forEach(h => h.intensity = 2);
    } else {
        scene.background = new THREE.Color(0x87CEEB);
        scene.fog = new THREE.Fog(0x87CEEB, 200, 1200);
        sun.intensity = 1.2;
        headlights.forEach(h => h.intensity = 0);
    }
}

// --- UI Binding ---
document.querySelectorAll('.model-btn').forEach(btn => {
    btn.onclick = () => {
        document.querySelectorAll('.model-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedModel = btn.dataset.model;
    };
});

document.getElementById('p1-btn').onclick = () => startGame('SOLO');
document.getElementById('host-btn').onclick = () => { isHost = true; setupPeer(); document.getElementById('start-screen').classList.remove('active'); document.getElementById('lobby-screen').classList.add('active'); document.getElementById('host-info').classList.remove('hidden'); };
document.getElementById('join-btn').onclick = () => { isHost = false; setupPeer(); document.getElementById('start-screen').classList.remove('active'); document.getElementById('lobby-screen').classList.add('active'); document.getElementById('join-info').classList.remove('hidden'); };
document.getElementById('connect-btn').onclick = () => joinLobby(document.getElementById('join-id-input').value);
document.getElementById('start-multi-btn').onclick = () => startGame('HOST');

document.getElementById('rematch-btn').onclick = () => {
    if (gameMode === 'HOST') {
        Object.values(connections).forEach(c => c.send({ type: 'REMATCH' }));
        resetRace();
    } else if (gameMode === 'SOLO') {
        resetRace();
    }
};
document.getElementById('quit-btn').onclick = () => location.reload();

// --- Core Loops ---

function startGame(mode) {
    gameMode = mode;
    
    // Setup Player
    const name = document.getElementById('player-name-input').value || 'PILOT';
    const color = document.getElementById('car-color-input').value;
    document.getElementById('player-name-hud').innerText = name.toUpperCase();
    document.getElementById('hud-team-badge').innerText = selectedModel;

    const car = createF1(selectedModel, color);
    scene.add(car);
    players['local'] = { mesh: car, x: 0, targetX: 0, name: name, crashed: false };

    // Init Headlights
    headlights = [];
    for(let i=0; i<2; i++) {
        const spot = new THREE.SpotLight(0xffffff, isNight ? 2 : 0);
        spot.position.set(i===0 ? -0.6 : 0.6, 0.5, 0.5);
        spot.target.position.set(i===0 ? -0.6 : 0.6, 0, -20);
        spot.angle = Math.PI / 6;
        spot.penumbra = 0.5;
        spot.distance = 200;
        car.add(spot);
        car.add(spot.target);
        headlights.push(spot);
    }

    // Init Engine Audio
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        engineOsc = audioCtx.createOscillator();
        engineGain = audioCtx.createGain();
        
        engineOsc.type = 'sawtooth';
        engineOsc.frequency.setValueAtTime(50, audioCtx.currentTime);
        
        engineGain.gain.setValueAtTime(0, audioCtx.currentTime);
        
        const filter = audioCtx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(800, audioCtx.currentTime);
        
        engineOsc.connect(filter);
        filter.connect(engineGain);
        engineGain.connect(audioCtx.destination);
        engineOsc.start();
    }
    if (audioCtx.state === 'suspended') audioCtx.resume();

    resetRace();
    animate();
}

function resetRace() {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById('hud').classList.remove('hidden');
    
    playerDistance = 0;
    velocity = 0;
    frameCount = 0;
    isStunned = false;
    raceFinished = false;
    GAME_STATE = 'PLAYING';
    
    obstacles.forEach(o => scene.remove(o));
    obstacles.length = 0;
    
    Object.values(players).forEach(p => { 
        p.distance = 0; 
        p.crashed = false; 
        p.x = 0; 
        p.targetX = 0; 
        if (p.mesh) {
            p.mesh.position.set(0, 0, 0);
            p.mesh.rotation.set(0, 0, 0);
        }
    });
}

function showLeaderboard(standings) {
    GAME_STATE = 'FINISHED';
    
    if (audioCtx && engineGain) {
        engineGain.gain.setTargetAtTime(0, audioCtx.currentTime, 0.5);
    }

    document.getElementById('hud').classList.add('hidden');
    document.getElementById('leaderboard-screen').classList.add('active');
    
    const list = document.getElementById('leaderboard-list');
    list.innerHTML = '';
    
    standings.forEach((p, idx) => {
        let cls = 'lb-item';
        if (idx === 0) cls += ' lb-first';
        else if (idx === 1) cls += ' lb-second';
        else if (idx === 2) cls += ' lb-third';
        
        const div = document.createElement('div');
        div.className = cls;
        const pos = idx === 0 ? '1ST' : (idx === 1 ? '2ND' : (idx === 2 ? '3RD' : `${idx+1}TH`));
        div.innerHTML = `<span>${pos} - ${p.name.toUpperCase()}</span> <span>${p.team}</span>`;
        list.appendChild(div);
    });
}

function update(dt) {
    frameCount++;
    const p = players['local'];
    if (!p) return;
    
    // Curve Math
    currentCurve = Math.sin(frameCount * 0.005) * 0.05;

    if (isStunned) {
        stunTimer -= dt;
        velocity *= 0.9;
        if (velocity < 0.1) velocity = 0;
        p.mesh.rotation.y += 15 * dt; // Spin out
        if (stunTimer <= 0) {
            isStunned = false;
            p.mesh.rotation.y = 0;
        }
    } else {
        // DRS & Slipstream Logic
        maxVelocity = drsActive ? 6.5 : 5.0;
        
        // Acceleration Logic
        const acc = keys.w || keys.ArrowUp;
        const brake = keys.s || keys.ArrowDown;
        if (acc) velocity += (drsActive ? 1.2 : 0.8) * dt;
        else if (brake) velocity -= 4 * dt;
        else velocity -= 0.2 * dt;
        velocity = THREE.MathUtils.clamp(velocity, 0, maxVelocity);

        // Steering Logic
        const steerSpeed = 15 * dt;
        if (keys.a || keys.ArrowLeft) p.targetX -= steerSpeed;
        if (keys.d || keys.ArrowRight) p.targetX += steerSpeed;
        p.targetX = THREE.MathUtils.clamp(p.targetX, -13, 13);
        p.x = THREE.MathUtils.lerp(p.x, p.targetX, 0.1);

        // ANCHOR: Car at Z=0
        p.mesh.position.set(p.x, 0, 0);
        p.mesh.rotation.z = -(p.x - p.targetX) * 0.15;
        p.mesh.rotation.y = -(p.x - p.targetX) * 0.05;
    }

    document.getElementById('current-score').innerText = Math.floor(velocity * 80);

    // Race Progress
    playerDistance += velocity * 100 * dt;
    if (playerDistance >= GOAL_DISTANCE && !raceFinished) {
        raceFinished = true;
        velocity = 0;
        if (gameMode === 'SOLO') {
            showLeaderboard([{ name: p.name, team: selectedModel, distance: playerDistance }]);
        }
    }

    // Particle VFX Update
    const sPos = sparkParticles.geometry.attributes.position.array;
    const smPos = smokeParticles.geometry.attributes.position.array;
    for(let i=0; i<200; i++) {
        // Sparks
        if (velocity > 4.8 && Math.random() > 0.5) {
            sPos[i*3] = p.x + (Math.random() - 0.5);
            sPos[i*3+1] = 0.1;
            sPos[i*3+2] = 2;
            sparkParticles.material.opacity = 1;
        } else {
            sPos[i*3+2] += velocity * 100 * dt;
        }
        // Smoke
        if (brake && velocity > 1 && Math.random() > 0.5) {
            smPos[i*3] = p.x + (Math.random() - 0.5) * 2;
            smPos[i*3+1] = 0.5 + Math.random();
            smPos[i*3+2] = 1;
            smokeParticles.material.opacity = 0.6;
        } else {
            smPos[i*3+2] += velocity * 100 * dt;
            smPos[i*3+1] += dt * 5; // rise
        }
    }
    sparkParticles.material.opacity = Math.max(0, sparkParticles.material.opacity - dt);
    smokeParticles.material.opacity = Math.max(0, smokeParticles.material.opacity - dt);
    sparkParticles.geometry.attributes.position.needsUpdate = true;
    smokeParticles.geometry.attributes.position.needsUpdate = true;

    // Send Move
    if (gameMode === 'JOIN' && frameCount % 2 === 0 && conn) {
        conn.send({ type: 'MOVE', x: p.x, distance: playerDistance });
    }

    // World Scrolling & Track Curvature
    const scroll = velocity * 100 * dt;
    scenery.forEach(obj => {
        obj.position.z += scroll;
        if (obj.position.z > 20) obj.position.z -= 1200;
        
        // Apply Visual Curve based on Z depth
        const zDepth = Math.max(0, -obj.position.z);
        const curveOffset = currentCurve * Math.pow(zDepth / 50, 2);
        
        // We only curve the visual X, the base X is stored in userData or implied
        if (obj.userData.baseX === undefined) obj.userData.baseX = obj.position.x;
        obj.position.x = obj.userData.baseX + curveOffset;
    });

    // Audio Engine Update
    if (audioCtx && engineOsc && GAME_STATE === 'PLAYING') {
        const targetPitch = 50 + (velocity * 40);
        const targetVol = 0.02 + (velocity * 0.015);
        engineOsc.frequency.setTargetAtTime(targetPitch, audioCtx.currentTime, 0.1);
        engineGain.gain.setTargetAtTime(targetVol, audioCtx.currentTime, 0.1);
    }

    // Obstacles Logic
    if (velocity > 0.5 && frameCount % 80 === 0) {
        spawnObstacle();
    }

    const pBox = new THREE.Box3().setFromObject(p.mesh);
    // Reduce player hitbox slightly to be more forgiving
    pBox.expandByScalar(-0.2); 

    let draftedBot = false;

    for (let i = obstacles.length - 1; i >= 0; i--) {
        const o = obstacles[i];
        
        if (o.userData && o.userData.isBot) {
            o.position.z += scroll - (o.userData.speed * 100 * dt);
            
            // Drafting Check (behind a bot in the same lane)
            const distZ = -o.position.z;
            const distX = Math.abs(o.userData.lane - p.x);
            if (distZ > 5 && distZ < 60 && distX < 2.5) {
                draftedBot = true;
            }
            
            // Visual Curve for Bots
            const zDepth = Math.max(0, -o.position.z);
            const curveOffset = currentCurve * Math.pow(zDepth / 50, 2);
            o.position.x = o.userData.lane + curveOffset;
        } else {
            o.position.z += scroll;
        }
        
        // Collision
        const oBox = new THREE.Box3().setFromObject(o);
        oBox.expandByScalar(-0.2);
        if (pBox.intersectsBox(oBox)) {
            if (!isStunned) {
                isStunned = true;
                stunTimer = 1.5; // 1.5 seconds spin out
                
                if (audioCtx && engineGain) {
                    engineGain.gain.setTargetAtTime(0.02, audioCtx.currentTime, 0.1);
                }
            }
        }

        if (o.position.z > 30) {
            scene.remove(o);
            obstacles.splice(i, 1);
        }
    }

    // DRS UI Update & Logic
    isDrafting = draftedBot;
    const drsUI = document.getElementById('drs-ui');
    
    if (isDrafting && !drsActive) {
        drsUI.innerText = 'DRS: READY [SPACE]';
        drsUI.className = 'powerup-slot-glass drs-ready';
    } else if (!isDrafting && !drsActive) {
        drsUI.innerText = 'DRS: UNAVAILABLE';
        drsUI.className = 'powerup-slot-glass';
    }

    if (drsActive) {
        drsUI.innerText = 'DRS: ACTIVE';
        drsUI.className = 'powerup-slot-glass drs-active';
        if (velocity < 4.5 || brake) drsActive = false; // Disable DRS if slowed
    }

    // Response Bar Update
    const speedPct = Math.min(100, (velocity / maxVelocity) * 100);
    document.getElementById('speed-bar').style.width = speedPct + '%';
    const progPct = Math.min(100, (playerDistance / GOAL_DISTANCE) * 100);
    document.getElementById('progress-bar').style.width = progPct + '%';
    document.getElementById('progress-pct').innerText = Math.floor(progPct) + '%';

    // Remote Players
    Object.keys(players).forEach(id => {
        if (id === 'local') return;
        const rp = players[id];
        rp.x = THREE.MathUtils.lerp(rp.x, rp.targetX, 0.1);
        
        const relZ = playerDistance - (rp.distance || 0);
        const zDepth = Math.max(0, -relZ);
        const curveOffset = currentCurve * Math.pow(zDepth / 50, 2);
        
        rp.mesh.position.set(rp.x + curveOffset, 0, relZ);
        rp.mesh.rotation.z = -(rp.x - rp.targetX) * 0.15;
        rp.mesh.rotation.y = -(rp.x - rp.targetX) * 0.05;
    });

    // Host Broadcast
    if (gameMode === 'HOST' && frameCount % 3 === 0) {
        players['local'].distance = playerDistance;
        
        const standings = Object.keys(players).map(id => ({ 
            id: id === 'local' ? myPeerId : id,
            x: players[id].x, team: players[id].team, color: players[id].color, name: players[id].name, distance: players[id].distance || 0 
        }));
        
        const state = {
            type: 'STATE',
            speed: velocity,
            players: standings
        };
        Object.values(connections).forEach(c => c.send(state));
        
        if (standings.some(pl => pl.distance >= GOAL_DISTANCE)) {
            standings.sort((a,b) => b.distance - a.distance);
            Object.values(connections).forEach(c => c.send({ type: 'LEADERBOARD', standings }));
            if (!raceFinished) {
                showLeaderboard(standings);
                raceFinished = true;
            }
        }
    }

    // Camera
    camera.fov = 60 + velocity * 10;
    if (cameraMode === 0) {
        camera.position.set(p.x * 0.5, 4.5, 12);
        camera.lookAt(p.x, 1, -25);
    } else {
        camera.position.set(p.x, 1.3, -0.5); // Halo Cockpit View
        camera.lookAt(p.x, 1.0, -30);
    }
    camera.updateProjectionMatrix();
}

function spawnObstacle() {
    const lane = (Math.floor(Math.random() * 4) - 1.5) * 8;
    const teams = ['MCLAREN', 'FERRARI', 'MERCEDES'];
    const colors = ['#ff8800', '#e10600', '#00ffcc'];
    const rIdx = Math.floor(Math.random() * teams.length);
    
    const botCar = createF1(teams[rIdx], colors[rIdx]);
    botCar.position.set(lane, 0, -800);
    
    botCar.userData = {
        isBot: true,
        speed: Math.random() * 2.5 + 1.5, // Bot driving speed
        lane: lane
    };
    
    scene.add(botCar);
    obstacles.push(botCar);
}

function animate() {
    requestAnimationFrame(animate);
    const dt = clock.getDelta();
    if (GAME_STATE === 'PLAYING') {
        update(dt);
    }
    renderer.render(scene, camera);
}

window.onresize = () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
};
