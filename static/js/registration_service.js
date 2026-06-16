/**
 * Identitype Registration & Enrollment Service
 * Handles username validation, email verification, and biometric enrollment flow.
 */

class RegistrationService {
    constructor(config) {
        this.config = {
            targetSamples: config.targetSamples || 20,
            devLenient: config.devLenient || false,
            usernameDebounce: config.devLenient ? 200 : 500,
            ...config
        };

        this.state = {
            sampleCount: 0,
            rawEvents: [],
            activeKeys: {},
            usernameAvailable: false,
            emailVerifiedLocked: false,
            passwordMismatchCount: 0,
            registrationComplete: false,
            isFirstKeystroke: true,
            typingStartTime: null,
            usernameCheckTimeout: null
        };

        this.initDOM();
        this.attachEventListeners();
        this.handlePrefill();
    }

    initDOM() {
        this.elements = {
            root: document.getElementById('registerRoot'),
            username: document.getElementById('regUsername'),
            email: document.getElementById('regEmail'),
            mainPassword: document.getElementById('mainPassword'),
            typingField: document.getElementById('typingField'),
            status: document.getElementById('status'),
            countDisplay: document.getElementById('countDisplay'),
            progressBar: document.getElementById('progressBar'),
            usernameStatus: document.getElementById('usernameStatus'),
            enrollmentSection: document.getElementById('enrollmentSection'),
            sendVerifyBtn: document.getElementById('sendVerifyBtn'),
            finishSection: document.getElementById('finishSection'),
            motivationalMsg: document.getElementById('motivationalMsg'),
            strengthBar: document.getElementById('strengthBarFill'),
            strengthLabel: document.getElementById('pwStrengthLabel'),
            strengthContainer: document.getElementById('pwStrength')
        };
    }

    attachEventListeners() {
        this.elements.username.addEventListener('input', () => this.onUsernameInput());
        this.elements.username.addEventListener('blur', () => this.checkUsername());
        this.elements.username.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.checkUsername().then(() => {
                    if (this.state.usernameAvailable) this.elements.mainPassword.focus();
                });
            }
        });

        this.elements.mainPassword.addEventListener('input', () => {
            this.updatePasswordStrengthUI();
            this.syncEnrollmentAccess();
        });

        this.elements.typingField.addEventListener('keydown', (e) => this.onKeyDown(e));
        this.elements.typingField.addEventListener('keyup', (e) => this.onKeyUp(e));
        this.elements.typingField.addEventListener('blur', () => this.resetTimer());

        if (this.elements.sendVerifyBtn) {
            this.elements.sendVerifyBtn.addEventListener('click', () => this.sendVerification());
        }
    }

    handlePrefill() {
        const params = new URLSearchParams(window.location.search);
        const preUsername = params.get('username');
        const preEmail = params.get('email');
        const verified = params.get('verified') === '1';

        if (preEmail) this.elements.email.value = preEmail;
        if (preUsername) {
            this.elements.username.value = preUsername;
            this.checkUsername().then(() => {
                if (verified) {
                    this.state.emailVerifiedLocked = true;
                    this.state.usernameAvailable = true;
                    this.elements.username.readOnly = true;
                    this.elements.email.readOnly = true;
                    this.elements.username.classList.add('readonly');
                    this.elements.email.classList.add('readonly');
                    if (this.elements.sendVerifyBtn) this.elements.sendVerifyBtn.disabled = true;
                    this.showUsernameStatus('success', 'Email verified');
                    this.enableEnrollment();
                }
            });
        }
    }

    // --- Logic Methods ---

    onUsernameInput() {
        if (this.state.usernameCheckTimeout) clearTimeout(this.state.usernameCheckTimeout);
        this.state.usernameAvailable = false;
        const val = this.elements.username.value.trim();
        if (!val || val.length < 3) {
            this.disableEnrollment();
            return;
        }
        this.state.usernameCheckTimeout = setTimeout(() => this.checkUsername(), this.config.usernameDebounce);
    }

    async checkUsername() {
        if (this.state.registrationComplete || this.state.emailVerifiedLocked) return;
        const username = this.elements.username.value.trim();
        if (!username || username.length < 3) return;

        this.showUsernameStatus('info', 'Checking...');

        try {
            const resp = await fetch('/api/check_username', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username })
            });

            if (!resp.ok) throw new Error('Check failed');

            const data = await resp.json();
            const count = data.enrollment_count ?? data.count ?? 0;
            const isTaken = data.status === 'taken' || data.exists === true;

            if (isTaken && data.status !== 'resumable' && count > 0) {
                this.showUsernameStatus('error', 'Username registered');
                this.disableEnrollment();
                return;
            }

            this.state.usernameAvailable = true;
            this.state.sampleCount = count;
            this.updateProgress();

            if (count > 0) {
                this.showUsernameStatus('info', `Resume enrollment: ${count}/${this.config.targetSamples}`);
            } else {
                this.showUsernameStatus('success', 'Username available');
            }
            this.enableEnrollment();

        } catch (e) {
            console.error(e);
            this.showUsernameStatus('info', 'Offline mode - Validation skipped');
            this.state.usernameAvailable = true;
            this.enableEnrollment();
        }
    }

    async sendVerification() {
        const username = this.elements.username.value.trim();
        const email = this.elements.email.value.trim();
        if (!username || !email) {
            this.showToast('Username and email required', 'warn');
            return;
        }

        this.elements.sendVerifyBtn.disabled = true;
        try {
            const resp = await fetch('/api/send_verification', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email })
            });
            if (resp.ok) {
                this.showToast('Verification code sent', 'info');
                setTimeout(() => {
                    window.location.href = `/verify?username=${encodeURIComponent(username)}&email=${encodeURIComponent(email)}`;
                }, 800);
            } else {
                const d = await resp.json();
                this.showToast(d.message || 'Send failed', 'error');
                this.elements.sendVerifyBtn.disabled = false;
            }
        } catch (e) {
            this.showToast('Network error', 'error');
            this.elements.sendVerifyBtn.disabled = false;
        }
    }

    onKeyDown(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            this.handleSubmitSample();
            return;
        }
        if (['Shift', 'Control', 'Alt', 'Meta', 'CapsLock'].includes(e.key)) return;

        if (!this.state.typingStartTime) this.state.typingStartTime = performance.now();
        this.state.activeKeys[e.code] = performance.now();
        
        this.state.rawEvents.push({
            evt: 'd', key: e.key, code: e.code, t: performance.now(),
            isRepeat: e.repeat
        });
    }

    onKeyUp(e) {
        if (e.key === 'Enter') return;
        if (['Shift', 'Control', 'Alt', 'Meta', 'CapsLock'].includes(e.key)) return;
        
        delete this.state.activeKeys[e.code];
        this.state.rawEvents.push({
            evt: 'u', key: e.key, code: e.code, t: performance.now()
        });
    }

    async handleSubmitSample() {
        const username = this.elements.username.value.trim();
        const mainPass = this.elements.mainPassword.value;
        const typedPass = this.elements.typingField.value;

        if (!this.state.rawEvents.length) {
            this.showStatus('Type your password first', '#f59e0b');
            return;
        }

        if (typedPass !== mainPass) {
            this.state.passwordMismatchCount++;
            this.showStatus(`Password mismatch (${this.state.passwordMismatchCount})`, '#ef4444');
            this.elements.typingField.value = '';
            this.state.rawEvents = [];
            this.resetTimer();
            return;
        }

        this.elements.typingField.disabled = true;
        this.showStatus('Processing...', '#3b82f6');

        try {
            const resp = await fetch('/api/enroll', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username,
                    password: mainPass,
                    events: this.state.rawEvents
                })
            });

            const data = await resp.json();
            if (resp.ok) {
                this.state.sampleCount = data.enrollment_count || (this.state.sampleCount + 1);
                this.updateProgress();
                this.showStatus('Sample saved!', '#10b981');
                
                if (this.state.sampleCount >= this.config.targetSamples) {
                    this.completeRegistration();
                } else {
                    this.elements.typingField.value = '';
                    this.state.rawEvents = [];
                    this.elements.typingField.disabled = false;
                    this.elements.typingField.focus();
                }
            } else {
                this.showStatus(data.message || 'Error saving sample', '#ef4444');
                this.elements.typingField.disabled = false;
            }
        } catch (e) {
            this.showStatus('Network error', '#ef4444');
            this.elements.typingField.disabled = false;
        }
        this.resetTimer();
    }

    // --- UI Helpers ---

    enableEnrollment() {
        this.elements.enrollmentSection.classList.remove('disabled', 'opacity-50', 'pointer-events-none');
        this.elements.mainPassword.disabled = false;
        this.syncEnrollmentAccess();
    }

    disableEnrollment() {
        this.elements.enrollmentSection.classList.add('disabled', 'opacity-50', 'pointer-events-none');
        this.elements.mainPassword.disabled = true;
        this.elements.typingField.disabled = true;
    }

    syncEnrollmentAccess() {
        const canType = this.state.usernameAvailable && this.elements.mainPassword.value.length > 0;
        this.elements.typingField.disabled = !canType;
    }

    updateProgress() {
        const pct = Math.min(100, (this.state.sampleCount / this.config.targetSamples) * 100);
        this.elements.progressBar.style.width = pct + '%';
        this.elements.countDisplay.textContent = this.state.sampleCount;
    }

    showUsernameStatus(type, msg) {
        this.elements.usernameStatus.className = `mt-2 text-sm status-indicator ${type}`;
        this.elements.usernameStatus.textContent = msg;
        this.elements.usernameStatus.classList.remove('hidden');
    }

    showStatus(msg, color) {
        this.elements.status.textContent = msg;
        this.elements.status.style.color = color;
    }

    showToast(msg, tone) {
        if (window.showToast) window.showToast(msg, tone);
        else console.log(`[Toast] ${tone}: ${msg}`);
    }

    updatePasswordStrengthUI() {
        const pw = this.elements.mainPassword.value;
        if (!pw) {
            this.elements.strengthContainer.classList.add('hidden');
            return;
        }
        this.elements.strengthContainer.classList.remove('hidden');
        const score = Math.min(1, pw.length / 12);
        const pct = score * 100;
        this.elements.strengthBar.style.width = pct + '%';
        this.elements.strengthBar.style.backgroundColor = score < 0.5 ? '#ef4444' : (score < 0.8 ? '#f59e0b' : '#10b981');
        this.elements.strengthLabel.textContent = `Strength: ${score < 0.5 ? 'Weak' : (score < 0.8 ? 'Medium' : 'Strong')}`;
    }

    resetTimer() {
        this.state.typingStartTime = null;
        this.state.isFirstKeystroke = true;
    }

    completeRegistration() {
        this.state.registrationComplete = true;
        this.elements.enrollmentSection.classList.add('hidden');
        this.elements.finishSection.classList.remove('hidden');
        this.elements.username.readOnly = true;
        this.elements.mainPassword.disabled = true;
    }
}

// Global Export
window.RegistrationService = RegistrationService;
