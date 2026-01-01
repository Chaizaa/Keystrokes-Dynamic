// reset_complete.js - extracted from template

// Simple helpers
function togglePass(inputId, iconSpan) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === 'password') input.type = 'text'; else input.type = 'password';
}

// Basic enrollment variables
let sampleCount = 0;
const targetSamples = 20;
let rawEvents = [];
let activeKeys = {};
let typingStartTime = null;
let timerInterval = null;
let isFirstKeystroke = true;

const countDisplay = document.getElementById('countDisplay');
const progressBar = document.getElementById('progressBar');
const typingInput = document.getElementById('typingField');
const mainPassInput = document.getElementById('rcPassword');
const usernameEl = document.getElementById('rcUsername');
const statusEl = document.getElementById('status');

// Prefill username from query or server context
const params = new URLSearchParams(window.location.search);
const prefillUsername = params.get('username') || "";
if (prefillUsername && usernameEl) usernameEl.value = prefillUsername;

function startTimer() {
    if (!typingStartTime) {
        typingStartTime = performance.now();
        const timerEl = document.getElementById('typingTimer');
        const disp = document.getElementById('timerDisplay');
        if (timerEl) timerEl.style.display = 'block';
        if (disp) disp.textContent = '0.000';
        timerInterval = setInterval(() => {
            try {
                const elapsed = (performance.now() - typingStartTime) / 1000;
                if (disp) disp.textContent = elapsed.toFixed(3);
            } catch (e) { /* ignore */ }
        }, 50);
    }
}
function stopTimer() {
    if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
    typingStartTime = null;
    const timerEl = document.getElementById('typingTimer');
    const disp = document.getElementById('timerDisplay');
    if (timerEl) timerEl.style.display = 'none';
    if (disp) disp.textContent = '0.000';
}
function resetTimer() { stopTimer(); isFirstKeystroke = true; }

// Keystroke capture
if (typingInput) {
    typingInput.addEventListener('keydown', (event) => {
        const isModifier = ['Shift', 'Control', 'Alt', 'Meta', 'CapsLock'].includes(event.key);
        if (event.key === 'Enter') return;
        if (event.repeat && !isModifier) {
            event.preventDefault();
            rawEvents.push({ key: event.key, code: event.code, evt: 'd', t: performance.now(), isRepeat: true });
            return;
        }
        if (!isModifier) {
            activeKeys[event.code] = performance.now();
            if (isFirstKeystroke) { startTimer(); isFirstKeystroke = false; }
            rawEvents.push({ key: event.key, code: event.code, evt: 'd', t: performance.now(), isRepeat: false });
        }
    });

    typingInput.addEventListener('keyup', (event) => {
        const isModifier = ['Shift', 'Control', 'Alt', 'Meta', 'CapsLock'].includes(event.key);
        if (event.key === 'Enter') { handleEnterPress(); return; }
        if (!isModifier) rawEvents.push({ key: event.key, code: event.code, evt: 'u', t: performance.now() });
    });
}

async function handleEnterPress() {
    const newPass = mainPassInput ? (mainPassInput.value || '') : '';
    const typedPass = typingInput ? (typingInput.value || '') : '';
    if (!newPass) { if (statusEl) statusEl.textContent = 'Please enter the new master password.'; return; }
    if (typedPass !== newPass) {
        if (statusEl) statusEl.textContent = 'Typed password does not match the master password.';
        if (typingInput) typingInput.value = '';
        rawEvents = [];
        resetTimer();
        return;
    }

    // submit sample to reset endpoint
    if (typingInput) typingInput.disabled = true;
    if (statusEl) statusEl.textContent = 'Saving sample...';
    try {
        const resetToken = params.get('reset_token') || '';
        const response = await fetch('/api/reset_password', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: usernameEl ? usernameEl.value.trim() : '', reset_token: resetToken, events: rawEvents, sample_count: sampleCount+1 })
        });
        const result = await response.json().catch(() => ({}));
        const ok = result.status === 'success' || result.success === true;
        if (ok) {
            sampleCount++;
            if (countDisplay) countDisplay.textContent = sampleCount;
            updateProgress();
            if (typingInput) typingInput.value = '';
            rawEvents = [];
            resetTimer();
            if (statusEl) statusEl.textContent = 'Sample saved';
            // Re-enable typing field for the next sample and focus it
            if (typingInput) { typingInput.disabled = false; try { typingInput.focus(); } catch (e) {} }

            if (sampleCount >= targetSamples) {
                const finish = document.getElementById('finishSection');
                if (finish) finish.classList.remove('hidden');
                // redirect to login after a short delay
                setTimeout(() => { window.location.href = `/login?username=${encodeURIComponent(usernameEl ? usernameEl.value.trim() : '')}&from=reset`; }, 1500);
                return;
            }
        } else {
            if (statusEl) statusEl.textContent = result.message || 'Failed to save sample';
            if (typingInput) typingInput.disabled = false;
        }
    } catch (e) {
        console.error(e);
        if (statusEl) statusEl.textContent = 'Network error';
        if (typingInput) typingInput.disabled = false;
    }
}

function updateProgress() {
    const pct = (sampleCount / targetSamples) * 100;
    if (progressBar) progressBar.style.width = pct + '%';
    const msgEl = document.getElementById('motivationalMsg');
    if (msgEl) {
        if (sampleCount <= 10) msgEl.textContent = `Progress: ${sampleCount}/20 samples recorded`;
        else if (sampleCount < 20) msgEl.textContent = `${sampleCount}/20 samples - ${20-sampleCount} remaining`;
    }
}
