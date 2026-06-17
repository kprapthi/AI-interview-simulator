// Interview Room Simulation Logic

const sessionId = sessionStorage.getItem('session_id');
const stressMode = parseInt(sessionStorage.getItem('stress_mode') || '0');
const coachMode = parseInt(sessionStorage.getItem('coach_mode') || '0');
const domain = sessionStorage.getItem('domain') || 'software_development';

let currentQuestionId = sessionStorage.getItem('first_question_id');
let currentQuestionText = sessionStorage.getItem('first_question_text');
let currentDifficulty = sessionStorage.getItem('first_question_difficulty') || 'easy';
let questionNumber = 1;

let speechRecognition = null;
let recognitionActive = false;
let spokenResponseText = "";
let questionStartTime = 0;
let speakingStartTime = 0;
let hesitationTime = 0;
let speechDurationSec = 0;

// Filler word trackers
const FILLER_WORDS = ['um', 'uh', 'like', 'actually', 'basically', 'so', 'essentially', 'you know'];
let detectedFillersCount = 0;

// Speech Synthesis (TTS) setup
const ttsSynth = window.speechSynthesis;
let ttsUtterance = null;

window.addEventListener('DOMContentLoaded', () => {
    // Check session
    if (!sessionId) {
        alert('Invalid session. Redirecting to landing page.');
        window.location.href = '/';
        return;
    }

    // Setup UI Text
    document.getElementById('domainHeader').textContent = formatDomainName(domain);
    document.getElementById('sessionModeLabel').textContent = 
        (stressMode ? "Adaptive Stress Mode" : "Standard Mode") + 
        (coachMode ? " + Live Coach" : "");
    
    updateQuestionUI(currentQuestionText, currentDifficulty, questionNumber);

    // If Coach Mode disabled, hide Coach Panel
    if (!coachMode) {
        document.getElementById('coachPanel').style.display = 'none';
        document.getElementById('coachStatusBadge').style.display = 'none';
    } else {
        // Start webcam analysis if enabled
        startWebcamAnalysis();
    }

    // Setup speech recognition
    setupSpeechRecognition();

    // Trigger AI speech for the first question
    setTimeout(() => {
        speakQuestion(currentQuestionText);
    }, 1000);
});

function formatDomainName(d) {
    return d.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

function updateQuestionUI(text, difficulty, number) {
    document.getElementById('questionText').textContent = text;
    document.getElementById('questionCounter').textContent = `Q ${number} / 5`;
    
    const diffBadge = document.getElementById('difficultyBadge');
    diffBadge.textContent = difficulty.charAt(0).toUpperCase() + difficulty.slice(1);
    
    // Class coloring for difficulty
    diffBadge.className = 'badge';
    if (difficulty === 'easy') diffBadge.classList.add('bg-success');
    else if (difficulty === 'medium') diffBadge.classList.add('bg-warning', 'text-dark');
    else if (difficulty === 'hard') diffBadge.classList.add('bg-danger');
}

// Speak Question (Text-to-Speech)
function speakQuestion(text) {
    // Stop recognition if active
    stopRecognition();

    // Stop existing TTS
    ttsSynth.cancel();

    // Set UI State
    setInterviewerState("speaking");

    ttsUtterance = new SpeechSynthesisUtterance(text);
    
    // Set natural speaking rates
    // Stress mode: make AI voice slightly faster or slower to induce tension, or keep default
    if (stressMode && questionNumber > 2) {
        ttsUtterance.rate = 1.05; // Slightly faster/pressuring
    } else {
        ttsUtterance.rate = 0.95; // Clear and calm
    }

    // Select suitable English voice if available
    const voices = ttsSynth.getVoices();
    const englishVoice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Google') || v.name.includes('Natural')));
    if (englishVoice) {
        ttsUtterance.voice = englishVoice;
    }

    ttsUtterance.onend = () => {
        setInterviewerState("listening");
        questionStartTime = Date.now();
        
        // Auto trigger microphone recognition for candidate convenience
        startRecognition();
    };

    ttsUtterance.onerror = (e) => {
        console.error("TTS failed:", e);
        // Fallback state if speech synthesis fails (e.g. browser permission issues)
        setInterviewerState("listening");
        questionStartTime = Date.now();
    };

    ttsSynth.speak(ttsUtterance);
}

// Set visual state of interviewer card
function setInterviewerState(state) {
    const avatarOuter = document.getElementById('avatarOuter');
    const waveVisualizer = document.getElementById('waveVisualizer');
    const interviewerLabel = document.getElementById('interviewerState');

    if (state === "speaking") {
        avatarOuter.classList.add('speaking');
        waveVisualizer.classList.add('speaking');
        interviewerLabel.className = "badge bg-purple-glow pulse-element px-3 py-2";
        interviewerLabel.innerHTML = '<i class="bi bi-volume-up-fill me-2"></i>AI Interviewer Speaking';
        document.getElementById('micBtn').disabled = true;
        document.getElementById('submitBtn').disabled = true;
    } else if (state === "listening") {
        avatarOuter.classList.remove('speaking');
        waveVisualizer.classList.remove('speaking');
        interviewerLabel.className = "badge bg-success px-3 py-2";
        interviewerLabel.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Listening for Answer';
        document.getElementById('micBtn').disabled = false;
        
        // Clear transcript box
        document.getElementById('transcriptPreview').innerHTML = '<span class="text-white-50">Speaking active... Start talking.</span>';
        spokenResponseText = "";
    } else if (state === "evaluating") {
        avatarOuter.classList.remove('speaking');
        waveVisualizer.classList.remove('speaking');
        interviewerLabel.className = "badge bg-warning text-dark px-3 py-2";
        interviewerLabel.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Evaluating Response';
        document.getElementById('micBtn').disabled = true;
        document.getElementById('submitBtn').disabled = true;
    }
}

// Speech to Text (Speech Recognition) Configuration
function setupSpeechRecognition() {
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) {
        console.warn("Speech Recognition API not supported in this browser.");
        document.getElementById('transcriptPreview').innerHTML = 
            '<span class="text-danger"><i class="bi bi-exclamation-octagon-fill me-2"></i>Speech recognition not supported in this browser. Please type your responses directly by clicking here.</span>';
        makeTranscriptEditable();
        return;
    }

    speechRecognition = new SpeechRecognitionAPI();
    speechRecognition.continuous = true;
    speechRecognition.interimResults = true;
    speechRecognition.lang = 'en-US';

    speechRecognition.onstart = () => {
        recognitionActive = true;
        detectedFillersCount = 0;
        speakingStartTime = Date.now();
        
        // Calculate hesitation (delay between question end and speaking start)
        hesitationTime = Math.max(0, (speakingStartTime - questionStartTime) / 1000);
        
        const micIcon = document.getElementById('micIcon');
        const micBtnText = document.getElementById('micBtnText');
        const micBtn = document.getElementById('micBtn');

        micBtn.classList.add('recording');
        micIcon.className = "bi bi-record-fill";
        micBtnText.textContent = "Mic Active (Stop)";
    };

    speechRecognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }

        if (finalTranscript) {
            spokenResponseText += " " + finalTranscript;
        }

        // Live transcription display
        const displayVal = (spokenResponseText + " " + interimTranscript).trim();
        const preview = document.getElementById('transcriptPreview');
        preview.textContent = displayVal;
        preview.style.color = "#ffffff";
        preview.classList.add('text-white');

        // Check for filler words live if Coach Mode is on
        if (coachMode && finalTranscript) {
            checkFillerWords(finalTranscript);
        }

        // Enable submission once response text is present
        if (displayVal.split(' ').length > 2) {
            document.getElementById('submitBtn').disabled = false;
        }
    };

    speechRecognition.onerror = (event) => {
        console.error("Speech Recognition Error:", event.error);
        if (event.error === 'not-allowed') {
            alert("Microphone permission denied. Please enable mic access.");
            stopRecognition();
        }
    };

    speechRecognition.onend = () => {
        recognitionActive = false;
        const micIcon = document.getElementById('micIcon');
        const micBtnText = document.getElementById('micBtnText');
        const micBtn = document.getElementById('micBtn');

        micBtn.classList.remove('recording');
        micIcon.className = "bi bi-mic-fill";
        micBtnText.textContent = "Click to Answer";

        // Convert the preview box to a contenteditable field so user can manually edit errors
        makeTranscriptEditable();
    };
}

function makeTranscriptEditable() {
    const preview = document.getElementById('transcriptPreview');
    preview.contentEditable = "true";
    preview.style.cursor = "text";
    
    // Add instruction
    if (preview.textContent.includes("Your response transcript will appear")) {
        preview.textContent = "";
    }
    
    // On keyup, enable submit button if word count is > 2
    preview.onkeyup = () => {
        const text = preview.textContent.trim();
        document.getElementById('submitBtn').disabled = (text.split(' ').length <= 2);
    };
}

function checkFillerWords(phrase) {
    const words = phrase.toLowerCase().split(/\s+/);
    words.forEach(w => {
        if (FILLER_WORDS.includes(w)) {
            detectedFillersCount++;
            if (detectedFillersCount % 2 === 0) {
                pushCoachAlert("warning", `Detected filler word use: "${w}". Try to pause instead.`, "filler");
            }
        }
    });
}

function toggleVoiceInput() {
    if (recognitionActive) {
        stopRecognition();
    } else {
        startRecognition();
    }
}

function startRecognition() {
    if (speechRecognition && !recognitionActive) {
        // Clear past logs
        const preview = document.getElementById('transcriptPreview');
        preview.contentEditable = "false";
        preview.textContent = "Adjusting microphone...";
        
        try {
            speechRecognition.start();
        } catch (e) {
            console.error(e);
        }
    }
}

function stopRecognition() {
    if (speechRecognition && recognitionActive) {
        speechRecognition.stop();
        speechDurationSec += Math.max(1, (Date.now() - speakingStartTime) / 1000);
    }
}

// Skip question
function skipQuestion() {
    const preview = document.getElementById('transcriptPreview');
    preview.textContent = "Skipped question.";
    document.getElementById('submitBtn').disabled = false;
    submitAnswer();
}

// Evaluate Response & Progress State
function submitAnswer() {
    stopRecognition();
    ttsSynth.cancel();

    const transcriptBox = document.getElementById('transcriptPreview');
    const finalAnswer = transcriptBox.textContent.trim();

    setInterviewerState("evaluating");

    const submitBtn = document.getElementById('submitBtn');
    const submitSpinner = document.getElementById('submitSpinner');
    submitBtn.disabled = true;
    submitSpinner.classList.remove('d-none');

    // Calculate Speaking Pacing (WPM)
    const wordCount = finalAnswer.split(/\s+/).filter(w => w.length > 0).length;
    const duration = speechDurationSec || Math.max(1, (Date.now() - questionStartTime) / 1000);
    const wpm = Math.round((wordCount / duration) * 60);

    // Real-Time Coach alerts for speed
    if (coachMode && finalAnswer !== "Skipped question.") {
        if (wpm > 170) {
            pushCoachAlert("warning", `Speaking speed fast (${wpm} WPM). Slow down and enunciate.`, "pace");
        } else if (wpm < 80) {
            pushCoachAlert("warning", `Speaking speed slow (${wpm} WPM). Try to speak more fluently.`, "pace");
        } else {
            pushCoachAlert("success", `Excellent pace (${wpm} WPM).`, "pace");
        }
    }

    // Get webcam eye contact score
    const eyeContactVal = typeof getAverageEyeContactScore === 'function' ? getAverageEyeContactScore() : 95.0;

    // Stress Handling parameters
    // Hesitation delay (> 4s is high) + high filler word count + poor eye contact
    let stressVal = 0.0;
    if (stressMode) {
        const hesitationScore = Math.min(40, hesitationTime * 8); // Max 40 points
        const fillerScore = Math.min(30, detectedFillersCount * 6); // Max 30 points
        const eyeScorePenalty = Math.max(0, (100 - eyeContactVal) * 0.4); // Max 30 points
        stressVal = Math.round(hesitationScore + fillerScore + eyeScorePenalty);
    }

    // Call evaluate API
    fetch('/api/evaluate-answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionId,
            question_id: currentQuestionId,
            candidate_answer: finalAnswer,
            eye_contact_score: eyeContactVal,
            speaking_speed: wpm,
            filler_words_count: detectedFillersCount,
            stress_score: stressVal,
            question_number: questionNumber
        })
    })
    .then(res => {
        if (!res.ok) throw new Error('Evaluation failed');
        return res.json();
    })
    .then(data => {
        // Reset timers and logs
        speechDurationSec = 0;
        clearCoachLogs();

        if (data.finished) {
            // Redirect to dashboard with session ID
            window.location.href = `/dashboard?session_id=${sessionId}`;
        } else {
            // Move to next question
            questionNumber = data.question_number;
            currentQuestionId = data.next_question_id;
            currentQuestionText = data.next_question_text;
            currentDifficulty = data.next_difficulty;

            // Update UI elements
            updateQuestionUI(currentQuestionText, currentDifficulty, questionNumber);
            
            // Speak next question
            speakQuestion(currentQuestionText);
        }
    })
    .catch(err => {
        console.error(err);
        alert('Failed to submit response. Please verify server is alive.');
        setInterviewerState("listening");
    })
    .finally(() => {
        submitSpinner.classList.add('d-none');
    });
}

// Exit Navigation
let exitModalObj = null;
function confirmExit() {
    ttsSynth.cancel();
    stopRecognition();
    
    const modalEl = document.getElementById('exitModal');
    if (modalEl) {
        exitModalObj = new bootstrap.Modal(modalEl);
        exitModalObj.show();
    } else {
        exitSession();
    }
}

function exitSession() {
    if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
    }
    window.location.href = '/';
}