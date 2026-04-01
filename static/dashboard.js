let recorder;
let streamRef;
let liveChunkCount = 0;
let hasGunshotAlerted = false;
let hasScreamAlerted = false;
let isLiveRunning = false;
let chunkTimer = null;
let audioContextRef = null;
let analyserRef = null;
let waveformDataRef = null;
let waveformAnimationRef = null;
let waveformCanvasRef = null;
let waveformCtxRef = null;
let sourceNodeRef = null;
const MAX_DETECTION_LOGS = 50;
let logRefreshTimer = null;
let liveAlertTimer = null;
let liveTimerInterval = null;
let liveElapsedSeconds = 0;

function formatElapsed(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function renderLiveTimer() {
    const timer = document.getElementById("live-runtime");
    if (!timer) {
        return;
    }
    timer.textContent = formatElapsed(liveElapsedSeconds);
}

function startLiveTimer() {
    if (liveTimerInterval) {
        clearInterval(liveTimerInterval);
    }

    liveElapsedSeconds = 0;
    renderLiveTimer();

    liveTimerInterval = setInterval(() => {
        liveElapsedSeconds += 1;
        renderLiveTimer();
    }, 1000);
}

function stopLiveTimer() {
    if (liveTimerInterval) {
        clearInterval(liveTimerInterval);
        liveTimerInterval = null;
    }
    liveElapsedSeconds = 0;
    renderLiveTimer();
}

function getDetectionTimestamp() {
    return new Date().toLocaleString([], {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });
}

function addDetectionLog(eventType, source) {
    const logList = document.getElementById("detection-log-list");
    if (!logList) {
        return;
    }

    const empty = logList.querySelector(".empty-log");
    if (empty) {
        empty.remove();
    }

    const item = document.createElement("li");
    const eventClass = eventType.toLowerCase();
    item.innerHTML = `<span class="log-event"><span class="log-badge ${eventClass}">${eventType}</span> detected (${source})</span><span class="log-time">${getDetectionTimestamp()}</span>`;
    logList.prepend(item);

    while (logList.children.length > MAX_DETECTION_LOGS) {
        logList.removeChild(logList.lastElementChild);
    }
}

function clearDetectionLog() {
    const logList = document.getElementById("detection-log-list");
    if (!logList) {
        return;
    }

    logList.innerHTML = '<li class="empty-log">No detections yet</li>';
}

function renderDetectionLogs(logs) {
    const logList = document.getElementById("detection-log-list");
    if (!logList) {
        return;
    }

    if (!Array.isArray(logs) || logs.length === 0) {
        logList.innerHTML = '<li class="empty-log">No detections yet</li>';
        return;
    }

    const trimmed = logs.slice(0, MAX_DETECTION_LOGS);
    const fragment = document.createDocumentFragment();

    for (const item of trimmed) {
        const li = document.createElement("li");

        const eventWrap = document.createElement("span");
        eventWrap.className = "log-event";

        const badge = document.createElement("span");
        const eventType = String(item.event || "Event");
        badge.className = `log-badge ${eventType.toLowerCase()}`;
        badge.textContent = eventType;

        const source = String(item.source || "Unknown");
        eventWrap.appendChild(badge);
        eventWrap.append(` detected (${source})`);

        const time = document.createElement("span");
        time.className = "log-time";
        time.textContent = String(item.timestamp || "-");

        li.appendChild(eventWrap);
        li.appendChild(time);
        fragment.appendChild(li);
    }

    logList.innerHTML = "";
    logList.appendChild(fragment);
}

async function refreshDetectionLogs() {
    try {
        const response = await fetch("/api/detection-logs", { cache: "no-store" });
        if (!response.ok) {
            return;
        }

        const data = await response.json();
        renderDetectionLogs(data.logs || []);
    } catch (err) {
        console.error("Failed to refresh detection logs:", err);
    }
}

function showLiveAlert(message, type = "info") {
    const alertEl = document.getElementById("live-alert");
    if (!alertEl) {
        return;
    }

    alertEl.classList.remove("gunshot", "scream", "info", "show");
    alertEl.textContent = message;
    alertEl.classList.add(type, "show");

    if (liveAlertTimer) {
        clearTimeout(liveAlertTimer);
    }

    liveAlertTimer = setTimeout(() => {
        alertEl.classList.remove("show");
    }, 3500);
}

function updateDetectionPanel(label, isLoading) {
    const chip = document.getElementById("detection-chip");
    if (!chip) {
        return;
    }

    chip.classList.remove("clear", "alert", "neutral", "loading", "background", "gunshot", "scream");

    if (isLoading) {
        chip.textContent = "Loading...";
        chip.classList.add("loading");
        return;
    }

    const normalized = String(label || "Background").trim().toLowerCase();

    if (normalized.includes("gunshot")) {
        chip.textContent = "Gunshot";
        chip.classList.add("gunshot");
    } else if (normalized.includes("scream")) {
        chip.textContent = "Scream";
        chip.classList.add("scream");
    } else {
        chip.textContent = "Background";
        chip.classList.add("background");
    }
}

function resetWaveformCanvas() {
    if (!waveformCanvasRef || !waveformCtxRef) {
        return;
    }

    const width = waveformCanvasRef.width;
    const height = waveformCanvasRef.height;

    waveformCtxRef.clearRect(0, 0, width, height);
    waveformCtxRef.fillStyle = "#11262c";
    waveformCtxRef.fillRect(0, 0, width, height);
    waveformCtxRef.strokeStyle = "rgba(77, 217, 190, 0.45)";
    waveformCtxRef.lineWidth = 2;
    waveformCtxRef.beginPath();
    waveformCtxRef.moveTo(0, height / 2);
    waveformCtxRef.lineTo(width, height / 2);
    waveformCtxRef.stroke();
}

function drawWaveform() {
    if (!analyserRef || !waveformDataRef || !waveformCanvasRef || !waveformCtxRef) {
        return;
    }

    const pixelRatio = window.devicePixelRatio || 1;
    const targetWidth = Math.floor(waveformCanvasRef.clientWidth * pixelRatio);
    const targetHeight = Math.floor(waveformCanvasRef.clientHeight * pixelRatio);

    if (waveformCanvasRef.width !== targetWidth || waveformCanvasRef.height !== targetHeight) {
        waveformCanvasRef.width = targetWidth;
        waveformCanvasRef.height = targetHeight;
    }

    analyserRef.getByteTimeDomainData(waveformDataRef);

    const width = waveformCanvasRef.width;
    const height = waveformCanvasRef.height;

    waveformCtxRef.fillStyle = "#11262c";
    waveformCtxRef.fillRect(0, 0, width, height);

    waveformCtxRef.strokeStyle = "#56f5d5";
    waveformCtxRef.lineWidth = 2;
    waveformCtxRef.beginPath();

    const sliceWidth = width / waveformDataRef.length;
    let x = 0;

    for (let i = 0; i < waveformDataRef.length; i += 1) {
        const v = waveformDataRef[i] / 128.0;
        const y = (v * height) / 2;

        if (i === 0) {
            waveformCtxRef.moveTo(x, y);
        } else {
            waveformCtxRef.lineTo(x, y);
        }

        x += sliceWidth;
    }

    waveformCtxRef.lineTo(width, height / 2);
    waveformCtxRef.stroke();

    waveformAnimationRef = requestAnimationFrame(drawWaveform);
}

async function startWaveform(stream) {
    waveformCanvasRef = document.getElementById("mic-waveform");
    if (!waveformCanvasRef) {
        return;
    }

    waveformCtxRef = waveformCanvasRef.getContext("2d");
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    audioContextRef = new AudioCtx();

    if (audioContextRef.state === "suspended") {
        await audioContextRef.resume();
    }

    analyserRef = audioContextRef.createAnalyser();
    analyserRef.fftSize = 2048;
    analyserRef.smoothingTimeConstant = 0.85;

    waveformDataRef = new Uint8Array(analyserRef.frequencyBinCount);
    sourceNodeRef = audioContextRef.createMediaStreamSource(stream);
    sourceNodeRef.connect(analyserRef);

    drawWaveform();
}

async function stopWaveform() {
    if (waveformAnimationRef) {
        cancelAnimationFrame(waveformAnimationRef);
        waveformAnimationRef = null;
    }

    if (sourceNodeRef) {
        sourceNodeRef.disconnect();
        sourceNodeRef = null;
    }

    if (audioContextRef) {
        await audioContextRef.close();
        audioContextRef = null;
    }

    analyserRef = null;
    waveformDataRef = null;
    resetWaveformCanvas();
}

// Audio conversion utilities
function interleaveTo16BitPCM(channelData) {
    const pcm = new Int16Array(channelData.length);
    for (let i = 0; i < channelData.length; i += 1) {
        const s = Math.max(-1, Math.min(1, channelData[i]));
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return pcm;
}

function encodeWavFromFloat32(channelData, sampleRate) {
    const pcm = interleaveTo16BitPCM(channelData);
    const bytesPerSample = 2;
    const numChannels = 1;
    const blockAlign = numChannels * bytesPerSample;
    const byteRate = sampleRate * blockAlign;
    const dataSize = pcm.length * bytesPerSample;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);

    let offset = 0;
    const writeString = (str) => {
        for (let i = 0; i < str.length; i += 1) {
            view.setUint8(offset + i, str.charCodeAt(i));
        }
        offset += str.length;
    };

    writeString("RIFF");
    view.setUint32(offset, 36 + dataSize, true); offset += 4;
    writeString("WAVE");
    writeString("fmt ");
    view.setUint32(offset, 16, true); offset += 4;
    view.setUint16(offset, 1, true); offset += 2;
    view.setUint16(offset, numChannels, true); offset += 2;
    view.setUint32(offset, sampleRate, true); offset += 4;
    view.setUint32(offset, byteRate, true); offset += 4;
    view.setUint16(offset, blockAlign, true); offset += 2;
    view.setUint16(offset, 16, true); offset += 2;
    writeString("data");
    view.setUint32(offset, dataSize, true); offset += 4;

    for (let i = 0; i < pcm.length; i += 1) {
        view.setInt16(offset, pcm[i], true);
        offset += 2;
    }

    return new Blob([buffer], { type: "audio/wav" });
}

async function convertBlobToWav(blob) {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const audioCtx = new AudioCtx();
    try {
        const arrayBuffer = await blob.arrayBuffer();
        const decoded = await audioCtx.decodeAudioData(arrayBuffer.slice(0));

        let mono = decoded.getChannelData(0);
        if (decoded.numberOfChannels > 1) {
            const right = decoded.getChannelData(1);
            const mixed = new Float32Array(decoded.length);
            for (let i = 0; i < decoded.length; i += 1) {
                mixed[i] = 0.5 * (mono[i] + right[i]);
            }
            mono = mixed;
        }

        return encodeWavFromFloat32(mono, decoded.sampleRate);
    } finally {
        await audioCtx.close();
    }
}

function chooseSupportedMimeType() {
    const candidates = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/ogg;codecs=opus"
    ];

    for (const type of candidates) {
        if (MediaRecorder.isTypeSupported(type)) {
            return type;
        }
    }

    return "";
}

function scheduleChunkStop() {
    if (!isLiveRunning || !recorder || recorder.state !== "recording") {
        return;
    }

    chunkTimer = setTimeout(() => {
        if (isLiveRunning && recorder && recorder.state === "recording") {
            recorder.stop();
        }
    }, 3000);
}

// Live detection functions
async function startRec() {
    if (isLiveRunning) {
        return;
    }

    try {
        streamRef = await navigator.mediaDevices.getUserMedia({
            audio: {
                channelCount: 1,
                noiseSuppression: false,
                autoGainControl: false,
                echoCancellation: false
            }
        });

        const mimeType = chooseSupportedMimeType();
        recorder = mimeType ? new MediaRecorder(streamRef, { mimeType }) : new MediaRecorder(streamRef);

        isLiveRunning = true;
        liveChunkCount = 0;
        hasGunshotAlerted = false;
        hasScreamAlerted = false;
        updateDetectionPanel("Background", false);

        await startWaveform(streamRef);

        updateLiveIndicator(true);
        updateStatusMsg("Monitoring live microphone");

        recorder.ondataavailable = async (e) => {
            if (!e.data || e.data.size === 0) {
                if (isLiveRunning && recorder && recorder.state === "inactive") {
                    recorder.start();
                    scheduleChunkStop();
                }
                return;
            }

            liveChunkCount += 1;

            try {
                updateDetectionPanel("", true);

                const wavBlob = await convertBlobToWav(e.data);
                const formData = new FormData();
                formData.append("file", wavBlob, `live_${liveChunkCount}.wav`);

                const res = await fetch("/predict-live-chunk", {
                    method: "POST",
                    body: formData
                });

                const data = await res.json();

                if (data.gunshot_alert && !hasGunshotAlerted) {
                    hasGunshotAlerted = true;
                    showLiveAlert("Gunshot detected in live audio", "gunshot");
                }

                if (data.scream_alert && !hasScreamAlerted) {
                    hasScreamAlerted = true;
                    showLiveAlert("Scream detected in live audio", "scream");
                }

                updateDetectionPanel(data.label, false);
                await refreshDetectionLogs();
            } catch (err) {
                updateStatusMsg("Live detection error");
                updateDetectionPanel("Background", false);
                console.error(err);
            } finally {
                if (isLiveRunning && recorder && recorder.state === "inactive") {
                    recorder.start();
                    scheduleChunkStop();
                }
            }
        };

        recorder.start();
        scheduleChunkStop();
        startLiveTimer();
    } catch (err) {
        updateStatusMsg("Failed to access microphone");
        updateDetectionPanel("Background", false);
        console.error(err);
    }
}

function stopRec() {
    if (!isLiveRunning) {
        return;
    }

    isLiveRunning = false;

    if (chunkTimer) {
        clearTimeout(chunkTimer);
        chunkTimer = null;
    }

    if (recorder && recorder.state === "recording") {
        recorder.stop();
    }

    if (streamRef) {
        streamRef.getTracks().forEach(track => track.stop());
        streamRef = null;
    }

    stopWaveform().catch(err => console.error("Waveform stop failed:", err));
    stopLiveTimer();

    updateLiveIndicator(false);
    updateStatusMsg("Live recording stopped");
    updateDetectionPanel("Background", false);
}

// UI Update functions
function updateLiveIndicator(isActive) {
    const indicator = document.getElementById("live-indicator");
    if (isActive) {
        indicator.textContent = "Online";
        indicator.classList.remove("offline");
        indicator.classList.add("live");
    } else {
        indicator.textContent = "Offline";
        indicator.classList.remove("live");
        indicator.classList.add("offline");
    }
}

function updateStatusMsg(message) {
    if (typeof message === "string" && message.toLowerCase().includes("chunk")) {
        return;
    }
    const statusEl = document.getElementById("status-msg");
    if (statusEl) {
        statusEl.textContent = `Status: ${message}`;
    }
}

function updateLiveResult(chunkIndex, data) {
    // Intentionally no chunk/status UI updates in live mode.
}

// Live indicator button handler
document.addEventListener("DOMContentLoaded", function () {
    resetWaveformCanvas();
    updateDetectionPanel("Background", false);
    renderLiveTimer();
    refreshDetectionLogs();

    if (!logRefreshTimer) {
        logRefreshTimer = setInterval(refreshDetectionLogs, 2000);
    }

    const clearLogBtn = document.getElementById("clear-log-btn");
    if (clearLogBtn) {
        clearLogBtn.addEventListener("click", async function () {
            clearDetectionLog();
            try {
                await fetch("/api/clear-detection-logs", { method: "POST" });
                await refreshDetectionLogs();
            } catch (err) {
                console.error("Failed to clear server log file:", err);
            }
        });
    }

    const liveButton = document.getElementById("live-indicator");
    
    if (liveButton) {
        liveButton.addEventListener("click", async function () {
            if (isLiveRunning) {
                stopRec();
            } else {
                await startRec();
            }
        });
    }
});

// Hamburger Menu and Settings Modal Handler
document.addEventListener("DOMContentLoaded", function () {
    const hamburgerBtn = document.getElementById("hamburger-btn");
    const settingsModal = document.getElementById("settings-modal");
    const closeBtn = document.querySelector(".close-btn");
    const receiverEmailInput = document.getElementById("receiver-email");
    const saveEmailBtn = document.getElementById("save-email-btn");
    const emailMessage = document.getElementById("email-message");

    // Load saved email on page load
    loadReceiverEmail();

    // Hamburger button toggle
    hamburgerBtn.addEventListener("click", function () {
        hamburgerBtn.classList.toggle("active");
        settingsModal.classList.toggle("active");
    });

    // Close modal when close button is clicked
    closeBtn.addEventListener("click", function () {
        hamburgerBtn.classList.remove("active");
        settingsModal.classList.remove("active");
    });

    // Close modal when clicking outside
    window.addEventListener("click", function (event) {
        if (event.target === settingsModal) {
            hamburgerBtn.classList.remove("active");
            settingsModal.classList.remove("active");
        }
    });

    // Save email button
    saveEmailBtn.addEventListener("click", async function () {
        const email = receiverEmailInput.value.trim();
        
        if (!email) {
            showEmailMessage("Please enter an email address", "error");
            return;
        }

        // Basic email validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            showEmailMessage("Please enter a valid email address", "error");
            return;
        }

        try {
            const response = await fetch("/api/set-receiver-email", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ email: email })
            });

            const data = await response.json();

            if (response.ok) {
                showEmailMessage("Email saved successfully!", "success");
                setTimeout(() => {
                    hamburgerBtn.classList.remove("active");
                    settingsModal.classList.remove("active");
                }, 1500);
            } else {
                showEmailMessage(data.error || "Failed to save email", "error");
            }
        } catch (error) {
            showEmailMessage("Error saving email: " + error.message, "error");
            console.error("Error:", error);
        }
    });

    function showEmailMessage(message, type) {
        emailMessage.textContent = message;
        emailMessage.classList.remove("success", "error");
        emailMessage.classList.add(type);
    }

    async function loadReceiverEmail() {
        try {
            const response = await fetch("/api/get-receiver-email");
            const data = await response.json();
            if (data.email) {
                receiverEmailInput.value = data.email;
            }
        } catch (error) {
            console.error("Error loading email:", error);
        }
    }
});


// File upload handler
document.addEventListener("DOMContentLoaded", function () {
    const uploadForm = document.getElementById("upload-form");
    const resultDiv = document.getElementById("upload-result");

    if (uploadForm) {
        uploadForm.addEventListener("submit", async function (e) {
            e.preventDefault();

            const fileInput = document.getElementById("audio-file");
            if (!fileInput.files.length) {
                resultDiv.textContent = "Please select an audio file";
                resultDiv.classList.add("error");
                return;
            }

            const formData = new FormData();
            formData.append("file", fileInput.files[0]);

            try {
                updateStatusMsg("Uploading and analyzing...");
                updateDetectionPanel("", true);
                resultDiv.textContent = "Processing...";
                resultDiv.classList.remove("error");

                const response = await fetch("/predict", {
                    method: "POST",
                    body: formData
                });

                let data;
                try {
                    data = await response.json();
                } catch (parseError) {
                    console.error("Failed to parse JSON response:", parseError);
                    console.error("Response status:", response.status);
                    console.error("Response text:", await response.text());
                    throw new Error("Invalid response format from server");
                }

                if (response.ok && data.label) {
                    resultDiv.textContent = `Result: ${data.label} (Confidence: ${(data.confidence * 100).toFixed(2)}%)`;
                    resultDiv.classList.remove("error");
                    updateStatusMsg("Analysis complete");

                    updateDetectionPanel(data.label, false);

                    if (data.gunshot_alert) {
                        showLiveAlert("Gunshot detected from uploaded audio", "gunshot");
                    }
                    if (data.scream_alert) {
                        showLiveAlert("Scream detected from uploaded audio", "scream");
                    }

                    await refreshDetectionLogs();
                } else {
                    resultDiv.textContent = `Error: ${data.error || data.label || "Unknown error"}`;
                    resultDiv.classList.add("error");
                    updateStatusMsg("Analysis failed");
                    updateDetectionPanel("Background", false);
                }
            } catch (error) {
                resultDiv.textContent = "Error during upload: " + error.message;
                resultDiv.classList.add("error");
                updateStatusMsg("Upload error");
                updateDetectionPanel("Background", false);
                console.error("Upload error:", error);
            }
        });
    }
});
