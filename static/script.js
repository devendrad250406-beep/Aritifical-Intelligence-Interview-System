// 1. PROGRESS BAR INITIALIZATION
const progressBar = document.querySelector(".progress-bar");
if (progressBar && progressBar.dataset.progress) {
    progressBar.style.width = progressBar.dataset.progress + "%";
}

// 2. CAMERA INITIALIZATION
const video = document.getElementById("video");
const cameraStatus = document.getElementById("camera-status");

if (video) {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices
            .getUserMedia({
                video: true,
                audio: false
            })
            .then(function(stream) {
                video.srcObject = stream;
                if (cameraStatus) {
                    cameraStatus.innerText = "Camera is ON ✅";
                }
            })
            .catch(function(error) {
                if (cameraStatus) {
                    cameraStatus.innerText = "Camera permission denied ❌";
                }
                console.log("Camera error:", error);
            });
    }
}

// 3. SPEECH RECOGNITION
function startVoice() {
    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        alert("Speech recognition is not supported by this browser.");
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;

    const button = document.getElementById("voice-button");

    recognition.onstart = function() {
        if (button) {
            button.innerText = "🎤 Listening...";
        }
    };

    recognition.onresult = function(event) {
        const text = event.results[0][0].transcript;
        const answer = document.getElementById("answer");

        if (answer) {
            if (answer.value.trim() !== "") {
                answer.value += " " + text;
            } else {
                answer.value = text;
            }
        }
    };

    recognition.onerror = function(event) {
        console.log("Speech error:", event.error);
    };

    recognition.onend = function() {
        if (button) {
            button.innerText = "🎤 Start Speaking";
        }
    };

    recognition.start();
}

// 4. COUNTDOWN TIMER & AUTO-SUBMIT
let timeLeft = 60;
const timer = document.getElementById("timer");

if (timer) {
    timer.innerText = timeLeft;

    const countdown = setInterval(function() {
        timeLeft--;
        timer.innerText = timeLeft;

        if (timeLeft <= 0) {
            clearInterval(countdown);

            const form = document.getElementById("answer-form");

            if (form) {
                const answer = document.getElementById("answer");

                // Prevent empty answer from blocking submission
                if (answer && answer.value.trim() === "") {
                    answer.value = "No answer provided.";
                }

                form.submit();
            }
        }
    }, 1000);
}