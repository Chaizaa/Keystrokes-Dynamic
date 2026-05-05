/**
 * JANUS Login Service
 * Handles unified login with keystroke biometric verification.
 */

class LoginService {
    constructor(config) {
        this.config = {
            devLenient: config.devLenient || false,
            successDelay: 250,
            resetDelay: 600,
            ...config
        };

        this.state = {
            rawEvents: [],
            activeKeys: {},
            isSubmitting: false,
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
            form: document.getElementById('loginForm'),
            username: document.getElementById('username'),
            password: document.getElementById('passwordField'),
            submitBtn: document.getElementById('submitBtn'),
            resultBox: document.getElementById('resultBox'),
            usernameStatus: document.getElementById('usernameStatus'),
            debugPanel: document.getElementById('debugPanel'),
            debugToggle: document.getElementById('debugToggle'),
            debugOutput: document.getElementById('debugOutput')
        };
    }

    attachEventListeners() {
        this.elements.form.addEventListener('submit', (e) => this.handleSubmit(e));
        this.elements.username.addEventListener('blur', () => this.checkUsername());
        
        this.elements.password.addEventListener('keydown', (e) => this.onKeyDown(e));
        this.elements.password.addEventListener('keyup', (e) => this.onKeyUp(e));
        
        if (this.config.devLenient && this.elements.debugPanel) {
            this.elements.debugPanel.classList.remove('hidden');
        }
    }

    handlePrefill() {
        const params = new URLSearchParams(window.location.search);
        const preUser = params.get('username');
        const from = params.get('from');
        const reset = params.get('reset') === '1';

        if (preUser) {
            this.elements.username.value = decodeURIComponent(preUser);
            if (reset) setTimeout(() => this.elements.password.focus(), 50);
        }

        if (from === 'register') this.showToast('Account created - Please login', 'info');
        if (reset) this.showToast('Re-enrollment complete - Please login', 'success');
    }

    async checkUsername() {
        let username = this.elements.username.value.trim();
        if (!username) {
            this.elements.usernameStatus.classList.add('hidden');
            return;
        }

        if (username.includes('@')) username = username.toLowerCase();

        this.showUsernameStatus('checking', 'Checking...');

        if (this.state.usernameCheckTimeout) clearTimeout(this.state.usernameCheckTimeout);
        this.state.usernameCheckTimeout = setTimeout(async () => {
            try {
                const resp = await fetch('/api/check_username', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, mode: 'login' })
                });
                const data = await resp.json();
                if (!data.exists) {
                    this.showUsernameStatus('error', 'User not found');
                } else if (!data.can_login) {
                    this.showUsernameStatus('error', 'Incomplete enrollment');
                } else {
                    this.elements.usernameStatus.classList.add('hidden');
                }
            } catch (e) {
                this.showUsernameStatus('error', 'Validation error');
            }
        }, 300);
    }

    onKeyDown(e) {
        if (e.key === 'Enter') return;
        if (e.key.length > 1 && e.key !== 'Backspace') return;

        const now = performance.now();
        if (this.state.isFirstKeystroke) {
            this.state.typingStartTime = now;
            this.state.isFirstKeystroke = false;
        }

        if (e.repeat) {
            e.preventDefault();
            this.state.rawEvents.push({ evt: 'd', key: e.key, code: e.code, t: now, isRepeat: true });
            return;
        }

        if (!this.state.activeKeys[e.code]) {
            this.state.rawEvents.push({ evt: 'd', key: e.key, code: e.code, t: now, isRepeat: false });
            this.state.activeKeys[e.code] = now;
        }
    }

    onKeyUp(e) {
        if (e.key === 'Enter') return;
        if (e.key.length > 1 && e.key !== 'Backspace') return;

        const now = performance.now();
        if (this.state.activeKeys[e.code]) {
            this.state.rawEvents.push({ evt: 'u', key: e.key, code: e.code, t: now });
            delete this.state.activeKeys[e.code];
        }
    }

    async handleSubmit(e) {
        e.preventDefault();
        if (this.state.isSubmitting) return;

        let username = this.elements.username.value.trim();
        if (username.includes('@')) username = username.toLowerCase();
        
        if (this.state.rawEvents.length < 4) {
            this.showResult('Insufficient telemetry data. Type naturally.', 'error');
            return;
        }

        this.state.isSubmitting = true;
        this.elements.submitBtn.disabled = true;
        this.elements.submitBtn.innerHTML = '<span class="animate-pulse">VERIFYING...</span>';

        try {
            const debug = this.elements.debugToggle?.checked || this.config.devLenient;
            const resp = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username,
                    events: this.state.rawEvents,
                    debug
                })
            });

            const body = await resp.json();
            if (resp.ok && body.success) {
                this.showResult('Access Granted', 'success');
                setTimeout(() => window.location.href = '/home', this.config.successDelay);
            } else {
                this.handleFailure(body);
            }
        } catch (err) {
            this.showResult('Connection error', 'error');
            this.resetForm();
        }
    }

    handleFailure(body) {
        let msg = body.message || 'Login failed';
        if (body.reason === 'impostor_detected') msg = 'Biometric mismatch. Try again.';
        if (body.reason === 'PASSWORD_MISMATCH') msg = 'Invalid credentials.';
        
        this.showResult(msg, 'error');
        if (body.debug && this.elements.debugOutput) {
            this.elements.debugOutput.classList.remove('hidden');
            this.elements.debugOutput.textContent = JSON.stringify(body.debug, null, 2);
        }
        setTimeout(() => this.resetForm(), this.config.resetDelay);
    }

    resetForm() {
        this.state.rawEvents = [];
        this.state.activeKeys = {};
        this.state.isSubmitting = false;
        this.state.isFirstKeystroke = true;
        this.elements.submitBtn.disabled = false;
        this.elements.submitBtn.innerHTML = 'Login';
        this.elements.password.value = '';
    }

    showUsernameStatus(type, msg) {
        this.elements.usernameStatus.className = `mt-2 text-[10px] font-bold uppercase status-${type}`;
        this.elements.usernameStatus.textContent = msg;
        this.elements.usernameStatus.classList.remove('hidden');
    }

    showResult(msg, type) {
        this.elements.resultBox.innerHTML = msg;
        this.elements.resultBox.className = `mt-4 p-3 text-xs font-bold uppercase rounded border border-opacity-20 ${type === 'success' ? 'bg-green-900/20 border-green-500 text-green-500' : 'bg-red-900/20 border-red-500 text-red-500'}`;
        this.elements.resultBox.style.display = 'block';
    }

    showToast(msg, tone) {
        if (window.showToast) window.showToast(msg, tone);
        else console.log(`[Toast] ${tone}: ${msg}`);
    }
}

window.LoginService = LoginService;
