// Keystroke Capture Module
class KeystrokeCapture {
    constructor() {
        this.rawEvents = [];
        this.activeKeys = {};
        this.startTime = null;
    }

    handleKeyDown(event) {
        // Exclude Enter key - for form submission only
        if (event.key === 'Enter') return;

        // Exclude modifier keys entirely — not part of biometric vector
        if (['Shift', 'Control', 'Alt', 'Meta', 'CapsLock'].includes(event.key)) return;

        // Exclude other special keys (arrows, F-keys, etc.) except Backspace
        if (event.key.length > 1 && event.key !== 'Backspace') return;

        // Track by physical key CODE (not character) so that keyup always matches
        // even when Shift state changes between keydown and keyup (e.g. K → k).
        const code = event.code;
        const now  = performance.now();

        // Skip OS key-repeat bursts (holding a key down). preventDefault stops the
        // browser from inserting extra characters into the input, so the value stays
        // in sync with telemetry (one physical press = one char). Backspace is left
        // repeatable so users can erase fluidly.
        if (event.repeat) {
            if (event.key !== 'Backspace') event.preventDefault();
            return;
        }

        // Start timer on first keystroke
        if (this.startTime === null) {
            this.startTime = now;
        }

        // Always overwrite activeKeys so the hold-time anchor stays accurate
        // even when two presses of the same key overlap during fast typing.
        this.activeKeys[code] = now;
        this.rawEvents.push({
            evt: 'd',
            key: event.key,   // character at keydown time
            code: event.code,
            t: now
        });
    }

    handleKeyUp(event) {
        // Exclude Enter key
        if (event.key === 'Enter') return;

        // Exclude modifier keys entirely
        if (['Shift', 'Control', 'Alt', 'Meta', 'CapsLock'].includes(event.key)) return;

        // Exclude other special keys except Backspace
        if (event.key.length > 1 && event.key !== 'Backspace') return;

        // Match by physical code — correct even if Shift was released before keyup
        const code = event.code;
        const now  = performance.now();

        if (this.activeKeys[code]) {
            delete this.activeKeys[code];
            this.rawEvents.push({
                evt: 'u',
                key: event.key,
                code: event.code,
                t: now
            });
        }
    }

    getEvents() {
        return this.rawEvents;
    }

    /**
     * Close all dangling keydowns (keys still in activeKeys) by injecting
     * synthetic keyup events timestamped to now.
     *
     * Call this immediately before getEvents() when a submit fires before
     * the browser has had a chance to dispatch keyup for the last key(s) —
     * which happens when the user presses Enter very quickly after their
     * last character, so the last character would otherwise be dropped from
     * the timing reconstruction.
     */
    flush() {
        const now = performance.now();
        Object.keys(this.activeKeys).forEach(code => {
            // Find the most recent keydown event for this code to retrieve its key char
            const lastDown = [...this.rawEvents].reverse().find(e => e.evt === 'd' && e.code === code);
            this.rawEvents.push({
                evt:  'u',
                key:  lastDown ? lastDown.key : code,
                code: code,
                t:    now,
            });
            delete this.activeKeys[code];
        });
    }

    reset() {
        this.rawEvents = [];
        this.activeKeys = {};
        this.startTime = null;
    }

    getElapsedTime() {
        if (this.startTime === null) return 0;
        return (performance.now() - this.startTime) / 1000;
    }
}

// Timer Display Module
class TypingTimer {
    constructor(displayElement) {
        this.displayElement = displayElement;
        this.timerInterval = null;
        this.startTime = null;
    }

    start() {
        if (this.startTime === null) {
            this.startTime = performance.now();
            this.displayElement.style.display = 'block';
            this.timerInterval = setInterval(() => {
                if (this.startTime) {
                    const elapsed = (performance.now() - this.startTime) / 1000;
                    const display = this.displayElement.querySelector('#timerDisplay') || 
                                  this.displayElement.querySelector('.time span');
                    if (display) {
                        display.textContent = elapsed.toFixed(3);
                    }
                }
            }, 50); // Update every 50ms
        }
    }

    stop() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
        this.startTime = null;
        this.displayElement.style.display = 'none';
        const display = this.displayElement.querySelector('#timerDisplay') || 
                      this.displayElement.querySelector('.time span');
        if (display) {
            display.textContent = '0.000';
        }
    }

    reset() {
        this.stop();
    }
}

// Password Visibility Toggle
function togglePasswordVisibility(inputId, iconElement) {
    const input = document.getElementById(inputId);
    const svgVisible = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
    const svgHidden = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>';
    
    if (input.type === 'password') {
        input.type = 'text';
        iconElement.innerHTML = svgHidden;
    } else {
        input.type = 'password';
        iconElement.innerHTML = svgVisible;
    }
}

// Username Validation with Debounce
class UsernameValidator {
    constructor(endpoint = '/api/check_username', debounceMs = 500) {
        this.endpoint = endpoint;
        this.debounceMs = debounceMs;
        this.timeoutId = null;
    }

    async validate(username, statusElement) {
        // Clear previous timeout
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
        }

        // Basic validation
        if (!username) {
            this.showStatus(statusElement, 'error', 'Username required');
            return false;
        }

        if (username.length < 3) {
            this.showStatus(statusElement, 'error', 'Minimum 3 characters');
            return false;
        }

        if (!/^[a-zA-Z0-9_]+$/.test(username)) {
            this.showStatus(statusElement, 'error', 'Alphanumeric only');
            return false;
        }

        // Show checking status
        this.showStatus(statusElement, 'checking', 'Checking availability...');

        // Debounced API call
        return new Promise((resolve) => {
            this.timeoutId = setTimeout(async () => {
                try {
                    const response = await fetch(this.endpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ username: username })
                    });

                    const result = await response.json();

                    if (result.status === 'taken') {
                        this.showStatus(statusElement, 'error', result.message);
                        resolve(false);
                    } else if (result.status === 'available') {
                        const message = result.is_retry ? 
                            result.message : 
                            result.message;
                        this.showStatus(statusElement, 
                            result.is_retry ? 'info' : 'success', 
                            message
                        );
                        resolve(true);
                    }
                } catch (error) {
                    console.error('Username validation error:', error);
                    this.showStatus(statusElement, 'error', 'Connection error');
                    resolve(false);
                }
            }, this.debounceMs);
        });
    }

    showStatus(element, type, message) {
        element.className = `status ${type}`;
        element.classList.remove('hidden');
        element.textContent = message;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        KeystrokeCapture,
        TypingTimer,
        togglePasswordVisibility,
        UsernameValidator
    };
}
