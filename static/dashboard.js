let recorder;
let streamRef;
let liveChunkCount = 0;
let hasGunshotAlerted = false;
let hasScreamAlerted = false;
let isLiveRunning = false;
let chunkTimer = null;

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

        updateLiveIndicator(true);
        updateStatusMsg("Live recording started (3s chunks)...");

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
                const wavBlob = await convertBlobToWav(e.data);
                const formData = new FormData();
                formData.append("file", wavBlob, `live_${liveChunkCount}.wav`);

                const res = await fetch("/predict-live-chunk", {
                    method: "POST",
                    body: formData
                });

                const data = await res.json();
                updateLiveResult(liveChunkCount, data);

                if (data.gunshot_alert && !hasGunshotAlerted) {
                    hasGunshotAlerted = true;
                    alert("Gunshot detected in live audio!");
                }

                if (data.scream_alert && !hasScreamAlerted) {
                    hasScreamAlerted = true;
                    alert("Scream detected in live audio!");
                }
            } catch (err) {
                updateStatusMsg("Live detection error");
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
    } catch (err) {
        updateStatusMsg("Failed to access microphone");
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
    }

    updateLiveIndicator(false);
    updateStatusMsg("Live recording stopped");
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
    document.getElementById("status-msg").textContent = `Status: ${message}`;
}

function updateLiveResult(chunkIndex, data) {
    updateStatusMsg(`Chunk ${chunkIndex}: ${data.label}`);
    if (data.confidence) {
        const bar = document.getElementById("level-bar");
        bar.style.width = (data.confidence * 100) + "%";
    }
}

// Live indicator button handler
document.addEventListener("DOMContentLoaded", function () {
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

                    if (data.gunshot_alert) {
                        alert("Gunshot detected!");
                    }
                    if (data.scream_alert) {
                        alert("Scream detected!");
                    }
                } else {
                    resultDiv.textContent = `Error: ${data.error || data.label || "Unknown error"}`;
                    resultDiv.classList.add("error");
                    updateStatusMsg("Analysis failed");
                }
            } catch (error) {
                resultDiv.textContent = "Error during upload: " + error.message;
                resultDiv.classList.add("error");
                updateStatusMsg("Upload error");
                console.error("Upload error:", error);
            }
        });
    }
});
