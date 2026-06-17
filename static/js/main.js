// Main Configuration Page JS
let uploadedResumeId = null;
// File Upload Drag & Drop Styling
const dropzone = document.getElementById('dropzone');
if (dropzone) {
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add('border-primary', 'bg-purple-opacity');
        }, false);
    });
    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.remove('border-primary', 'bg-purple-opacity');
        }, false);
    });
    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0 && files[0].name.endsWith('.txt')) {
            document.getElementById('resumeFile').files = files;
            uploadFile(files[0]);
        } else {
            alert('Please upload a valid plain text (.txt) file.');
        }
    });
}
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        if (file.name.endsWith('.txt')) {
            uploadFile(file);
        } else {
            alert('Please upload a valid plain text (.txt) file.');
            event.target.value = '';
        }
    }
}
function uploadFile(file) {
    const formData = new FormData();
    formData.append('resume', file);
    const startBtn = document.getElementById('startBtn');
    if (startBtn) startBtn.disabled = true;
    // Show upload state
    const uploadStatus = document.getElementById('uploadStatus');
    const uploadedFileName = document.getElementById('uploadedFileName');
    const uploadStatusText = document.getElementById('uploadStatusText');
    const extractedSkills = document.getElementById('extractedSkills');
    const skillsContainer = document.getElementById('skillsContainer');
    uploadStatus.classList.remove('d-none');
    uploadedFileName.textContent = file.name;
    uploadStatusText.innerHTML = '<span class="spinner-border spinner-border-sm text-purple-accent me-2"></span>Parsing resume content...';
    extractedSkills.classList.add('d-none');
    fetch('/api/upload-resume', {
        method: 'POST',
        body: formData
    })
    .then(res => {
        if (!res.ok) throw new Error('Failed to parse resume');
        return res.json();
    })
    .then(data => {
        uploadedResumeId = data.resume_id;
        uploadStatusText.innerHTML = '<i class="bi bi-check-circle-fill text-success me-1"></i>Parsed successfully!';
        
        // Show skills
        if (data.skills && data.skills.length > 0) {
            skillsContainer.innerHTML = '';
            data.skills.forEach(skill => {
                const badge = document.createElement('span');
                badge.className = 'badge bg-dark-glow border border-secondary text-purple-accent px-2 py-1';
                badge.textContent = skill;
                skillsContainer.appendChild(badge);
            });
            extractedSkills.classList.remove('d-none');
        }
    })
    .catch(err => {
        console.error(err);
        uploadStatusText.innerHTML = '<span class="text-danger"><i class="bi bi-exclamation-triangle-fill me-1"></i>Failed to parse. Is it valid text?</span>';
    })
    .finally(() => {
        if (startBtn) startBtn.disabled = false;
    });
}
function removeUploadedFile(event) {
    event.stopPropagation();
    uploadedResumeId = null;
    document.getElementById('resumeFile').value = '';
    document.getElementById('uploadStatus').classList.add('d-none');
    document.getElementById('extractedSkills').classList.add('d-none');
}
function startInterview(event) {
    event.preventDefault();
    const selectedDomain = document.querySelector('input[name="domain"]:checked').value;
    const stressMode = document.getElementById('stressModeToggle').checked ? 1 : 0;
    const coachMode = document.getElementById('coachModeToggle').checked ? 1 : 0;
    const startBtn = document.getElementById('startBtn');
    const btnText = document.getElementById('btnText');
    const btnSpinner = document.getElementById('btnSpinner');
    startBtn.disabled = true;
    btnText.textContent = 'Initializing Simulation...';
    btnSpinner.classList.remove('d-none');
    // Create session API request
    fetch('/api/start-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            domain: selectedDomain,
            stress_mode: stressMode,
            coach_mode: coachMode,
            resume_id: uploadedResumeId
        })
    })
    .then(res => {
        if (!res.ok) throw new Error('Start session failed');
        return res.json();
    })
    .then(data => {
        // Save initial details in sessionStorage
        sessionStorage.setItem('session_id', data.session_id);
        sessionStorage.setItem('stress_mode', stressMode);
        sessionStorage.setItem('coach_mode', coachMode);
        sessionStorage.setItem('domain', selectedDomain);
        sessionStorage.setItem('first_question_text', data.question_text);
        sessionStorage.setItem('first_question_id', data.question_id);
        sessionStorage.setItem('first_question_difficulty', data.difficulty);
        // Redirect to interview room
        window.location.href = '/interview';
    })
    .catch(err => {
        console.error(err);
        alert('Error starting interview session. Please verify backend is running.');
        startBtn.disabled = false;
        btnText.textContent = 'Start Mock Interview';
        btnSpinner.classList.add('d-none');
    });
}
function handleLogout() {
    fetch('/api/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(() => {
        window.location.href = '/login';
    })
    .catch(err => {
        console.error('Logout error:', err);
    });
}