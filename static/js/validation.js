// Form Validation Utilities

// Progress Bar Controller
class ProgressBarController {
    constructor(progressBarId, countDisplayId, messageId) {
        this.progressBar = document.getElementById(progressBarId);
        this.countDisplay = document.getElementById(countDisplayId);
        this.messageElement = document.getElementById(messageId);
        this.current = 0;
        this.target = 20;
    }

    update(currentCount) {
        this.current = currentCount;
        const percentage = (currentCount / this.target) * 100;
        this.progressBar.style.width = percentage + '%';
        this.countDisplay.textContent = currentCount;
        
        // Update motivational message
        if (currentCount <= 5) {
            this.messageElement.textContent = "Excellent start, keep going";
        } else if (currentCount <= 10) {
            this.messageElement.textContent = "Halfway there, maintain your natural rhythm";
        } else if (currentCount <= 15) {
            this.messageElement.textContent = "Almost done, stay consistent";
        } else if (currentCount < 20) {
            this.messageElement.textContent = `Final ${20 - currentCount} samples remaining`;
        } else {
            this.messageElement.textContent = "All 20 samples collected";
        }
    }

    reset() {
        this.current = 0;
        this.progressBar.style.width = '0%';
        this.countDisplay.textContent = '0';
        this.messageElement.textContent = "Take your time, type naturally";
    }
}

// Form Status Display
function showFormStatus(elementId, message, type = 'info') {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    element.className = `status status-${type}`;
    element.textContent = message;
    element.style.display = 'block';
}

function hideFormStatus(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    element.style.display = 'none';
}

// Loading Spinner
function showLoadingSpinner(buttonId, text = 'Loading...') {
    const button = document.getElementById(buttonId);
    if (!button) return;
    
    button.disabled = true;
    button.innerHTML = `<span class="spinner"></span> ${text}`;
}

function hideLoadingSpinner(buttonId, text = 'Submit') {
    const button = document.getElementById(buttonId);
    if (!button) return;
    
    button.disabled = false;
    button.innerHTML = text;
}

// Password Strength Checker
function checkPasswordStrength(password) {
    let strength = 0;
    const feedback = [];
    
    // Length check: allow any non-empty password (minimum 1 character)
    if (password.length >= 1) {
        strength += 1;
    } else {
        // Do not add length feedback to keep UX passive; empty passwords will show other feedback when applicable
    }
    
    // Contains lowercase
    if (/[a-z]/.test(password)) {
        strength += 1;
    } else {
        feedback.push('Add lowercase letters');
    }
    
    // Contains uppercase
    if (/[A-Z]/.test(password)) {
        strength += 1;
    } else {
        feedback.push('Add uppercase letters');
    }
    
    // Contains numbers
    if (/[0-9]/.test(password)) {
        strength += 1;
    } else {
        feedback.push('Add numbers');
    }
    
    // Contains special characters
    if (/[^a-zA-Z0-9]/.test(password)) {
        strength += 1;
    } else {
        feedback.push('Add special characters');
    }
    
    return {
        strength: strength,
        level: strength <= 2 ? 'weak' : strength <= 3 ? 'medium' : 'strong',
        feedback: feedback
    };
}

// Display Password Strength
function displayPasswordStrength(inputId, displayId) {
    const input = document.getElementById(inputId);
    const display = document.getElementById(displayId);
    
    if (!input || !display) return;
    
    input.addEventListener('input', () => {
        const result = checkPasswordStrength(input.value);
        
        display.className = `password-strength ${result.level}`;
        display.innerHTML = `
            <div class="strength-bar">
                <div class="strength-fill" style="width: ${(result.strength / 5) * 100}%"></div>
            </div>
            <span class="strength-text">${result.level.toUpperCase()}</span>
        `;
        
        if (result.feedback.length > 0 && result.strength < 4) {
            display.innerHTML += `<ul class="strength-feedback">
                ${result.feedback.map(f => `<li>${f}</li>`).join('')}
            </ul>`;
        }
        
        display.style.display = input.value ? 'block' : 'none';
    });
}

// Debounce Helper
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        ProgressBarController,
        showFormStatus,
        hideFormStatus,
        showLoadingSpinner,
        hideLoadingSpinner,
        checkPasswordStrength,
        displayPasswordStrength,
        debounce
    };
}
