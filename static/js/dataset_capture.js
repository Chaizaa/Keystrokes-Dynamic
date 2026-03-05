/**
 * Dataset Collection – Keystroke Capture JS
 *
 * Extends the base KeystrokeCapture class (keystroke.js) to drive the
 * 3-stage dataset collection UI:
 *
 *   Stage 1: Formulir registrasi (nama/inisial & kata sandi)
 *   Stage 2: Loop pengambilan sampel (ketik kata sandi N kali)
 *   Stage 3: Layar selesai
 */

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────
let subjectCode        = null;
let sessionToken       = null;  // HMAC session token — wajib di-attach pada setiap /submit
let collectedSamples   = 0;
let totalSamples       = 0;
let registeredPassword = null;  // kata sandi yang dipilih subjek saat registrasi
let keystroke          = null;  // KeystrokeCapture instance
let isSubmitting       = false;
let backspaceCount     = 0;     // direset tiap sampel baru

// ─────────────────────────────────────────────────────────────────────────────
// DOM helpers
// ─────────────────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

function showStage(stageName) {
    document.querySelectorAll(".ds-stage").forEach(el => el.classList.add("hidden"));
    const el = document.getElementById(`stage-${stageName}`);
    if (el) el.classList.remove("hidden");
}

let _statusTimer = null;

function setStatus(msg, type = "info") {
    const el = $("ds-status");
    if (!el) return;

    // Clear any pending auto-dismiss
    if (_statusTimer) { clearTimeout(_statusTimer); _statusTimer = null; }

    el.textContent = msg;
    el.className = `ds-status ds-status--${type}`;
    el.classList.remove("hidden");

    // Auto-dismiss warning and error after 2 s
    if (type === "warning" || type === "error") {
        _statusTimer = setTimeout(() => {
            el.classList.add("hidden");
            _statusTimer = null;
        }, 2000);
    }
}

function clearStatus() {
    const el = $("ds-status");
    if (el) el.classList.add("hidden");
}

// ─────────────────────────────────────────────────────────────────────────────
// Password Strength Bar
// ─────────────────────────────────────────────────────────────────────────────
// Mirrors the server-side password_strength.py scoring logic.
function calcPasswordStrength(pw) {
    if (!pw) return { score: 0, label: "Belum diisi", color: "#475569" };
    let score = 0;
    const n = pw.length;
    if      (n >= 16) score += 0.35;
    else if (n >= 12) score += 0.30;
    else if (n >= 8)  score += 0.20;
    else if (n >= 4)  score += 0.10;
    if (/[A-Z]/.test(pw)) score += 0.15;
    if (/[a-z]/.test(pw)) score += 0.15;
    if (/[0-9]/.test(pw)) score += 0.15;
    if (/[^A-Za-z0-9]/.test(pw)) score += 0.20;
    score = Math.min(1.0, score);
    let label, color;
    if      (score >= 0.67) { label = "Kuat";        color = "#10b981"; }
    else if (score >= 0.51) { label = "Sedang";      color = "#f59e0b"; }
    else if (score >= 0.34) { label = "Lemah";       color = "#f97316"; }
    else                    { label = "Sangat lemah"; color = "#ef4444"; }
    return { score, label, color };
}

function updateStrengthBar(pw, fillId, labelId) {
    const fill  = $(fillId);
    const label = $(labelId);
    if (!fill || !label) return;
    const result = calcPasswordStrength(pw);
    fill.style.width      = `${Math.round(result.score * 100)}%`;
    fill.style.background = result.color;
    label.textContent     = pw ? `Kekuatan: ${result.label} (${Math.round(result.score * 100)}%)` : "Kekuatan kata sandi: —";
    label.style.color     = pw ? result.color : "#64748b";
}

function updateProgress() {
    const pct = totalSamples > 0 ? Math.round((collectedSamples / totalSamples) * 100) : 0;

    const bar   = $("ds-progress-bar");
    const label = $("ds-progress-label");
    const repEl = $("ds-rep-label");

    if (bar)   { bar.style.width = `${pct}%`; bar.setAttribute("aria-valuenow", pct); }
    if (label) label.textContent = `${collectedSamples} / ${totalSamples} sampel`;
    if (repEl) repEl.textContent = `Sampel ke-${collectedSamples + 1} dari ${totalSamples}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Registration
// ─────────────────────────────────────────────────────────────────────────────
async function registerSubject() {
    const nameInput = $("ds-name");
    const pwInput   = $("ds-password");
    const btn       = $("ds-register-btn");
    const nameVal   = nameInput ? nameInput.value.trim() : "";
    const pwVal     = pwInput   ? pwInput.value : "";

    if (!pwVal) {
        setStatus("Kata sandinya belum diisi nih.", "warning");
        if (pwInput) pwInput.focus();
        return;
    }
    if (pwVal.length < 6) {
        setStatus("Kata sandinya minimal 6 karakter ya.", "warning");
        if (pwInput) pwInput.focus();
        return;
    }

    if (btn) { btn.disabled = true; btn.textContent = "Mendaftar…"; }

    try {
        const res  = await fetch("/api/dataset/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name_initial: nameVal || null, password: pwVal }),
        });
        const data = await res.json();

        if (!res.ok || !data.success) {
            throw new Error(data.error || "Gagal daftar, coba lagi ya");
        }

        subjectCode        = data.subject_code;
        sessionToken       = data.session_token || null;
        collectedSamples   = data.collected;
        totalSamples       = data.total_samples;
        registeredPassword = pwVal;

        startCaptureStage();

    } catch (err) {
        setStatus(`Error: ${err.message}`, "warning");
        if (btn) { btn.disabled = false; btn.textContent = "Mulai"; }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Resume (subject returning for later session)
// ─────────────────────────────────────────────────────────────────────────────
async function resumeSession() {
    const codeInput = $("ds-resume-code");
    const btn       = $("ds-resume-btn");
    const code      = codeInput ? codeInput.value.trim().toLowerCase() : "";

    if (!code) { setStatus("Masukkin kode subjeknya dulu dong!", "error"); return; }
    if (btn) { btn.disabled = true; btn.textContent = "Memuat…"; }

    try {
        const res  = await fetch(`/api/dataset/status/${encodeURIComponent(code)}`);
        const data = await res.json();

        if (!res.ok || !data.success) {
            throw new Error(data.error || "Kode subjeknya nggak ketemu nih");
        }

        if (data.is_complete) {
            showStage("done");
            $("ds-done-code").textContent = code;
            return;
        }

        subjectCode      = data.subject_code;
        sessionToken     = data.session_token || null;
        collectedSamples = data.collected;
        totalSamples     = data.total_samples;
        // registeredPassword stays null on resume — backend hash check handles consistency

        startCaptureStage();

    } catch (err) {
        setStatus(`Error: ${err.message}`, "warning");
        if (btn) { btn.disabled = false; btn.textContent = "Lanjutkan"; }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Capture stage
// ─────────────────────────────────────────────────────────────────────────────
function startCaptureStage() {
    // Show subject code to user clearly
    const codeDisplayEls = document.querySelectorAll(".ds-subject-code");
    codeDisplayEls.forEach(el => { el.textContent = subjectCode; });

    updateProgress();
    showStage("capture");
    clearStatus();
    prepareInput();
}

const MODIFIER_KEYS = ["Shift", "Control", "Alt", "Meta", "CapsLock"];
const MAX_BACKSPACE  = 4;

/** Helper: re-fetch status from server and update local state. */
async function syncStateFromServer() {
    if (!subjectCode) return;
    try {
        const res  = await fetch(`/api/dataset/status/${encodeURIComponent(subjectCode)}`);
        const data = await res.json();
        if (res.ok && data.success) {
            collectedSamples = data.collected;
            totalSamples     = data.total_samples;
            updateProgress();
        }
    } catch (_) { /* ignore */ }
}

function prepareInput() {
    const input = $("ds-input");
    if (!input) return;
    input.value    = "";
    input.disabled = false;
    input.focus();
    backspaceCount = 0;   // reset for this sample
    // Reset capture-stage strength bar for fresh typing
    updateStrengthBar("", "ds-pw-fill-capture", "ds-pw-label-capture");

    // Initialise or reset keystroke capture
    if (!keystroke) {
        keystroke = new KeystrokeCapture();
    } else {
        keystroke.reset();
    }

    input.onkeydown = function(e) {
        // Enter → submit
        if (e.key === "Enter") {
            e.preventDefault();
            submitSample();
            return;
        }

        // Block OS key-repeat for all keys except Backspace.
        // - Non-backspace repeat: preventDefault() stops extra chars from entering
        //   the field (e.g. holding "a" must not produce "aaaa").
        // - Hold time (H_vector) is still correct: keystroke.js records only the
        //   first keydown (repeat=false) and the single keyup → H = keyup.t - keydown.t
        //   = full physical hold duration, regardless of how many repeat events fire.
        // - Backspace is intentionally excluded so users can hold it to erase quickly.
        if (e.repeat && e.key !== "Backspace") { e.preventDefault(); return; }

        // Exclude modifier keys (Shift, Ctrl, Alt, Meta, CapsLock)
        // These are NOT part of the biometric vector.
        if (MODIFIER_KEYS.includes(e.key)) return;

        // Backspace limit: max 4x per sample.
        // If exceeded, clear field and force retype.
        if (e.key === "Backspace") {
            backspaceCount++;
            if (backspaceCount > MAX_BACKSPACE) {
                e.preventDefault();
                input.value = "";
                keystroke.reset();
                backspaceCount = 0;
                updateStrengthBar("", "ds-pw-fill-capture", "ds-pw-label-capture");
                setStatus(
                    `Kebanyakan hapus nih (maks ${MAX_BACKSPACE}x). Ketik ulang dari awal ya!`,
                    "warning"
                );
                return;
            }
        }

        keystroke.handleKeyDown(e);
    };

    input.onkeyup = function(e) {
        // Skip modifiers on keyup too
        if (MODIFIER_KEYS.includes(e.key)) return;
        keystroke.handleKeyUp(e);
        // Update strength bar as user types
        updateStrengthBar(input.value, "ds-pw-fill-capture", "ds-pw-label-capture");
    };
}

async function submitSample() {
    if (isSubmitting) return;

    const input    = $("ds-input");
    const typed    = input ? input.value : "";
    // Flush any dangling keydowns (keys still held at the moment Enter was pressed).
    // Without this, the last character is silently dropped when the user presses
    // Enter before the browser fires keyup for their final key, causing a hash
    // mismatch even though the password was typed correctly.
    if (keystroke) keystroke.flush();
    const events   = keystroke ? keystroke.getEvents() : [];

    // Basic validation
    if (!typed || typed.length === 0) {
        setStatus("Kata sandinya belum diketik nih!", "warning");
        return;
    }
    if (events.length < 4) {
        setStatus("Ketukan keyboard nggak ke-detect. Coba lagi ya?", "warning");
        return;
    }

    // Client-side consistency check (only when password is known from this session)
    if (registeredPassword && typed !== registeredPassword) {
        setStatus("Kata sandinya nggak cocok sama yang tadi didaftarin. Coba ketik lagi ya.", "warning");
        prepareInput();
        return;
    }

    isSubmitting = true;
    clearStatus();
    if (input) input.disabled = true;

    const submitBtn  = $("ds-submit-btn");
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Menyimpan…"; }

    try {
        const res  = await fetch("/api/dataset/submit", {
            method: "POST",
            headers: {
                "Content-Type":    "application/json",
                ...(sessionToken ? { "X-Session-Token": sessionToken } : {}),
            },
            // session_no and repetition are computed server-side — not sent
            body: JSON.stringify({
                subject_code: subjectCode,
                raw_events:   events,
            }),
        });
        const data = await res.json();

        if (res.status === 409) {
            // Duplicate submission (double-click / network retry) — re-sync and continue
            console.warn("[dataset] Duplicate sample detected, re-syncing state…");
            await syncStateFromServer();
            prepareInput();
            return;
        }

        if (!res.ok || !data.success) {
            throw new Error(data.error || "Gagal nyimpen sampel, coba lagi");
        }

        // Update state from server response
        collectedSamples = data.collected;
        totalSamples     = data.total_samples;
        updateProgress();

        if (data.all_done) {
            showStage("done");
            const codeEl = $("ds-done-code");
            if (codeEl) codeEl.textContent = subjectCode;
            return;
        }

        // Next sample
        setStatus(`✓ Sampel ke-${collectedSamples} tersimpan!`, "success");
        prepareInput();

    } catch (err) {
        setStatus(err.message, "warning");
        // Reset field and keystroke buffer so old events don't carry over
        prepareInput();
    } finally {
        isSubmitting = false;
        if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Kirim (Enter)"; }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Init on DOMContentLoaded
// ─────────────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    const regBtn    = $("ds-register-btn");
    const resumeBtn = $("ds-resume-btn");
    const submitBtn = $("ds-submit-btn");
    const pwInput   = $("ds-password");

    if (regBtn)    regBtn.addEventListener("click",    registerSubject);
    if (resumeBtn) resumeBtn.addEventListener("click", resumeSession);
    if (submitBtn) submitBtn.addEventListener("click", submitSample);

    // Enter on the intro password field → register (no button click needed)
    if (pwInput) {
        pwInput.addEventListener("keydown", e => {
            if (e.key === "Enter") { e.preventDefault(); registerSubject(); }
        });
        pwInput.addEventListener("input", () => {
            updateStrengthBar(pwInput.value, "ds-pw-fill-intro", "ds-pw-label-intro");
        });
    }

    // Enter on the resume-code field → resume without clicking button
    const resumeCodeInput = $("ds-resume-code");
    if (resumeCodeInput) {
        resumeCodeInput.addEventListener("keydown", e => {
            if (e.key === "Enter") { e.preventDefault(); resumeSession(); }
        });
    }
});
