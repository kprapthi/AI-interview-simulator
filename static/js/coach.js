// Real-time AI Coach Webcam & Voice Analyzer
let webcamStream = null;
let cameraActive = false;
let faceMesh = null;
let mpCamera = null;
let audioContext = null;
let audioAnalyser = null;
let audioStreamSource = null;
let volumeCheckInterval = null;

// Coach Scores updated in real-time
let eyeContactLog = [];
let currentEyeContactState = true;
let lastAlertText = "";
let lostEyeContactTime = null;
let eyeContactAlertTriggered = false;
let volumeWarningTriggered = false;

// Web Audio API Volume Monitor
async function startAudioMonitor() {
    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
        
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        audioAnalyser = audioContext.createAnalyser();
        audioStreamSource = audioContext.createMediaStreamSource(stream);
        audioStreamSource.connect(audioAnalyser);
        audioAnalyser.fftSize = 256;
        
        const bufferLength = audioAnalyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        
        let lowVolumeCounter = 0;
        
        volumeCheckInterval = setInterval(() => {
            // Only monitor if the candidate is supposed to be speaking
            const currentStatus = document.getElementById('interviewerState')?.textContent || "";
            if (!currentStatus.toLowerCase().includes("listening")) {
                return;
            }
            
            audioAnalyser.getByteFrequencyData(dataArray);
            let sum = 0;
            for (let i = 0; i < bufferLength; i++) {
                sum += dataArray[i];
            }
            let averageVolume = sum / bufferLength;
            
            if (averageVolume < 5 && averageVolume > 0) {
                lowVolumeCounter++;
                if (lowVolumeCounter > 16) { // ~8 seconds of silence or whispers
                    if (!volumeWarningTriggered) {
                        pushCoachAlert("warning", "Speak slightly louder or adjust microphone.", "volume");
                        volumeWarningTriggered = true;
                    }
                    lowVolumeCounter = 0;
                }
            } else {
                lowVolumeCounter = 0;
            }
        }, 500);
        
    } catch (err) {
        console.warn("Audio Context monitoring failed to start:", err);
    }
}

function stopAudioMonitor() {
    if (volumeCheckInterval) clearInterval(volumeCheckInterval);
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
}

// MediaPipe Face Tracking Setup
async function startWebcamAnalysis() {
    const video = document.getElementById('webcam');
    const placeholder = document.getElementById('webcamPlaceholder');
    const canvas = document.getElementById('faceCanvas');
    const ctx = canvas.getContext('2d');
    
    if (!video || !canvas) return;
    
    try {
        webcamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: "user" }
        });
        video.srcObject = webcamStream;
        placeholder.classList.add('d-none');
        cameraActive = true;
        
        // Dynamically match canvas resolution to video
        video.onloadedmetadata = () => {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            startFaceMesh(video, canvas, ctx);
        };
        
        // Start volume monitoring
        startAudioMonitor();
        
    } catch (err) {
        console.error("Webcam initialization failed:", err);
        pushCoachAlert("danger", "Camera access denied. Visual coach disabled.", "camera");
        placeholder.innerHTML = '<i class="bi bi-camera-video-off display-4 mb-3"></i><span>Camera access required for body language analysis</span>';
    }
}

function startFaceMesh(video, canvas, ctx) {
    if (typeof FaceMesh === 'undefined') {
        console.warn("MediaPipe FaceMesh not loaded from CDN. Falling back to basic simulation.");
        runBasicCalibrationSim();
        return;
    }
    
    faceMesh = new FaceMesh({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`
    });
    
    faceMesh.setOptions({
        maxNumFaces: 1,
        refineLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
    });
    
    faceMesh.onResults((results) => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
            const landmarks = results.multiFaceLandmarks[0];
            
            // Draw face wireframe guidelines (subtle purple dots)
            ctx.fillStyle = 'rgba(139, 92, 246, 0.4)';
            // Draw a subset of landmarks to keep execution fast
            for (let i = 0; i < landmarks.length; i += 8) {
                const pt = landmarks[i];
                ctx.beginPath();
                ctx.arc(pt.x * canvas.width, pt.y * canvas.height, 1.5, 0, 2 * Math.PI);
                ctx.fill();
            }
            
            // Draw eyes tracking indicator
            ctx.fillStyle = 'rgba(59, 130, 246, 0.6)';
            const leftEyeIris = landmarks[468]; // Left Iris Center
            const rightEyeIris = landmarks[473]; // Right Iris Center
            
            if (leftEyeIris && rightEyeIris) {
                ctx.beginPath();
                ctx.arc(leftEyeIris.x * canvas.width, leftEyeIris.y * canvas.height, 4, 0, 2 * Math.PI);
                ctx.arc(rightEyeIris.x * canvas.width, rightEyeIris.y * canvas.height, 4, 0, 2 * Math.PI);
                ctx.fill();
            }
            
            // Analyze Orientation
            analyzeHeadPoseAndEyeContact(landmarks);
        } else {
            // No face detected
            pushCoachAlert("warning", "No face detected. Align yourself within the frame.", "pose");
            eyeContactLog.push(0);
        }
    });
    
    // Start camera frames loop using MediaPipe Camera Helper
    if (typeof Camera !== 'undefined') {
        mpCamera = new Camera(video, {
            onFrame: async () => {
                if (cameraActive) {
                    await faceMesh.send({ image: video });
                }
            },
            width: 640,
            height: 480
        });
        mpCamera.start();
    } else {
        // Fallback frame processor if Camera helper is missing
        async function processFrame() {
            if (cameraActive) {
                await faceMesh.send({ image: video });
                requestAnimationFrame(processFrame);
            }
        }
        processFrame();
    }
}

function analyzeHeadPoseAndEyeContact(landmarks) {
    // Nose tip: 4
    // Left boundary cheek: 234, Right cheek: 454
    // Top forehead: 10, Bottom chin: 152
    
    const nose = landmarks[4];
    const leftCheek = landmarks[234];
    const rightCheek = landmarks[454];
    const forehead = landmarks[10];
    const chin = landmarks[152];
    
    if (!nose || !leftCheek || !rightCheek || !forehead || !chin) return;
    
    // Calculate horizontal head turn ratio
    const distToLeft = Math.abs(nose.x - leftCheek.x);
    const distToRight = Math.abs(nose.x - rightCheek.x);
    const horizontalRatio = distToLeft / (distToRight || 1);
    
    // Calculate vertical head tilt ratio
    const distToForehead = Math.abs(nose.y - forehead.y);
    const distToChin = Math.abs(nose.y - chin.y);
    const verticalRatio = distToForehead / (distToChin || 1);
    
    let isLookingCenter = true;
    
    // Thresholds: ratio should be near 1.0 (symmetrical cheeks/chin)
    // If user looks too far left (ratio < 0.65) or too far right (ratio > 1.5)
    if (horizontalRatio < 0.65 || horizontalRatio > 1.5) {
        isLookingCenter = false;
    }
    // If user looks too far up or down
    if (verticalRatio < 0.6 || verticalRatio > 1.6) {
        isLookingCenter = false;
    }
    
    if (isLookingCenter) {
        eyeContactLog.push(100);
        lostEyeContactTime = null;
        if (eyeContactAlertTriggered) {
            pushCoachAlert("success", "Good eye contact restored.", "eye");
            eyeContactAlertTriggered = false;
        }
        currentEyeContactState = true;
    } else {
        eyeContactLog.push(0);
        currentEyeContactState = false;
        
        // Wait 4 seconds of continuous looking away before pushing warning
        if (!lostEyeContactTime) {
            lostEyeContactTime = Date.now();
        } else {
            const timeDiff = Date.now() - lostEyeContactTime;
            if (timeDiff >= 4000) { // 4000ms = 4s
                if (!eyeContactAlertTriggered) {
                    pushCoachAlert("warning", "Maintain eye contact with the camera.", "eye");
                    eyeContactAlertTriggered = true;
                }
            }
        }
    }
}

function runBasicCalibrationSim() {
    // Simulates standard webcam coaching comments if MediaPipe is blocked
    pushCoachAlert("success", "Calibration complete. Simulated posture tracker active.", "calibrate");
    
    // Simulated eye contact check (extremely throttled, checks occasionally to avoid distraction)
    setInterval(() => {
        if (!cameraActive) return;
        
        // Randomly simulate occasional eye contact warning (low frequency)
        const rand = Math.random();
        if (rand > 0.96) {
            if (!eyeContactAlertTriggered) {
                pushCoachAlert("warning", "Maintain eye contact with the camera.", "eye");
                eyeContactAlertTriggered = true;
                
                // Automatically restore after 3 seconds
                setTimeout(() => {
                    pushCoachAlert("success", "Good eye contact restored.", "eye");
                    eyeContactAlertTriggered = false;
                }, 3000);
            }
        }
    }, 10000);
}

// Push alerts to panel list
function pushCoachAlert(type, message, category) {
    const alertsList = document.getElementById('coachAlertsList');
    if (!alertsList) return;
    
    // Check if duplicate of last alert to prevent spamming
    if (message === lastAlertText) return;
    lastAlertText = message;
    
    const alertItem = document.createElement('div');
    alertItem.className = `coach-alert-item ${type}-item`;
    
    let icon = "info-circle-fill";
    if (type === "success") icon = "check-circle-fill";
    else if (type === "warning") icon = "exclamation-triangle-fill";
    else if (type === "danger") icon = "x-circle-fill";
    
    alertItem.innerHTML = `
        <span class="alert-icon"><i class="bi bi-${icon}"></i></span>
        <span class="alert-msg">${message}</span>
    `;
    
    // Prepend to top
    alertsList.insertBefore(alertItem, alertsList.firstChild);
    
    // Keep only last 5 items
    if (alertsList.children.length > 5) {
        alertsList.removeChild(alertsList.lastChild);
    }
}

function getAverageEyeContactScore() {
    if (eyeContactLog.length === 0) return 100.0;
    const sum = eyeContactLog.reduce((a, b) => a + b, 0);
    return Math.round(sum / eyeContactLog.length);
}

function clearCoachLogs() {
    eyeContactLog = [];
    currentEyeContactState = true;
    lastAlertText = "";
    lostEyeContactTime = null;
    eyeContactAlertTriggered = false;
    volumeWarningTriggered = false;
}

function toggleCamera() {
    const video = document.getElementById('webcam');
    const placeholder = document.getElementById('webcamPlaceholder');
    const btn = document.getElementById('cameraToggleBtn');
    
    if (cameraActive) {
        // Turn off
        if (webcamStream) {
            webcamStream.getTracks().forEach(track => track.stop());
        }
        if (mpCamera) {
            mpCamera.stop();
            mpCamera = null;
        }
        video.srcObject = null;
        placeholder.classList.remove('d-none');
        btn.innerHTML = '<i class="bi bi-camera-video-off-fill me-1"></i>Camera Off';
        btn.className = 'btn btn-sm btn-outline-danger';
        cameraActive = false;
        stopAudioMonitor();
    } else {
        // Turn on
        btn.innerHTML = '<i class="bi bi-camera-video-fill me-1"></i>Camera On';
        btn.className = 'btn btn-sm btn-dark-glow';
        startWebcamAnalysis();
    }
}