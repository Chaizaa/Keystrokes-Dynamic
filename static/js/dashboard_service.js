/**
 * JANUS Dashboard Service
 * Handles user profile info, API key management, and account actions.
 */

class DashboardService {
    constructor() {
        this.initDOM();
        this.attachEventListeners();
        this.loadAll();
    }

    initDOM() {
        this.elements = {
            loading: document.getElementById('loadingSection'),
            main: document.getElementById('mainContent'),
            username: document.getElementById('username'),
            email: document.getElementById('email'),
            createdAt: document.getElementById('createdAt'),
            emailVerified: document.getElementById('emailVerified'),
            enrollmentCount: document.getElementById('enrollmentCount'),
            hasPassword: document.getElementById('hasPassword'),
            apiKeyCount: document.getElementById('apiKeyCount'),
            apiKeyList: document.getElementById('apiKeysList'),
            apiKeyLoading: document.getElementById('apiKeyListLoading'),
            apiKeyResult: document.getElementById('apiKeyResult'),
            newApiKeyValue: document.getElementById('newApiKeyValue'),
            generateBtn: document.getElementById('generateApiKeyBtn'),
            resetBtn: document.getElementById('resetBtn')
        };
    }

    attachEventListeners() {
        if (this.elements.generateBtn) {
            this.elements.generateBtn?.addEventListener('click', () => this.generateApiKey());
        }
        if (this.elements.resetBtn) {
            this.elements.resetBtn?.addEventListener('click', () => this.startResetFlow());
        }
    }

    async loadAll() {
        await Promise.all([
            this.loadUserInfo(),
            this.loadApiKeys()
        ]);
        this.elements.loading.classList.add('hidden');
        this.elements.main.classList.remove('hidden');
    }

    async loadUserInfo() {
        try {
            const resp = await fetch('/api/user/info');
            if (resp.status === 401) { window.location.href = '/login'; return; }
            if (!resp.ok) throw new Error('Failed to load profile');

            const data = await resp.json();

            // Tambahkan tanda ? agar kebal error kalau elemennya nggak ada di HTML
            if (this.elements.username) this.elements.username.textContent = data.username;
            if (this.elements.email) this.elements.email.textContent = data.email || '-';
            if (this.elements.createdAt) this.elements.createdAt.textContent = this.formatDate(data.created_at);
            if (this.elements.emailVerified) this.elements.emailVerified.textContent = data.email_verified ? 'VERIFIED' : 'PENDING';
            if (this.elements.enrollmentCount) this.elements.enrollmentCount.textContent = data.enrollment_count ?? 0;
            if (this.elements.hasPassword) this.elements.hasPassword.textContent = data.has_password ? 'ACTIVE' : 'INACTIVE';
            if (this.elements.apiKeyCount) this.elements.apiKeyCount.textContent = data.api_key_count ?? 0;
        } catch (e) {
            console.error('User Info Error:', e);
        }
    }

    async loadApiKeys() {
        // Pakai ?. biar nggak error classList kalau animasinya dihapus
        this.elements.apiKeyLoading?.classList.remove('hidden');

        if (this.elements.apiKeyList) {
            this.elements.apiKeyList.innerHTML = '';
        }

        try {
            const resp = await fetch('/api/user/api-keys?include_inactive=true');
            const body = await resp.json();
            if (!resp.ok) throw new Error(body.message || 'Load failed');

            const keys = body.keys || [];
            if (!keys.length) {
                if (this.elements.apiKeyList) {
                    this.elements.apiKeyList.innerHTML = '<div class="text-gray-600 text-[10px] uppercase py-8 text-center border border-dashed border-gray-800">No active integrations</div>';
                }
                return;
            }

            if (this.elements.apiKeyList) {
                this.elements.apiKeyList.innerHTML = keys.map(k => this.renderApiKey(k)).join('');
            }
        } catch (e) {
            if (this.elements.apiKeyList) {
                this.elements.apiKeyList.innerHTML = `<div class="text-red-500 text-xs">${e.message}</div>`;
            }
        } finally {
            // Pakai ?. lagi di sini
            this.elements.apiKeyLoading?.classList.add('hidden');
        }
    }

    renderApiKey(key) {
        const statusClass = key.is_active ? 'text-safety' : 'text-gray-600';
        const stats = key.stats || {};
        const inputCls = 'w-full bg-surface border border-border-dim py-2 px-3 text-xs text-stark focus:border-safety focus:ring-0 outline-none transition-all';
        const lblCls = 'block text-[9px] text-gray-500 uppercase font-bold tracking-widest mb-1';

        // Read-only detail rows; only render optional fields when present.
        const detailRow = (label, value) => `
            <div>
                <p class="text-[9px] text-gray-600 uppercase font-bold">${label}</p>
                <p class="text-[10px] text-gray-400 font-mono break-all">${value}</p>
            </div>`;

        return `
            <div class="bg-dark-obsidian border border-gray-800 p-5 group hover:border-gray-700 transition-colors">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <h4 class="text-white font-bold text-xs uppercase tracking-widest mb-1">${this.escape(key.partner_name)}</h4>
                        <p class="text-[9px] text-gray-600 font-mono uppercase">${this.escape(key.key_prefix)}...</p>
                    </div>
                    <span class="text-[9px] font-bold uppercase tracking-tighter ${statusClass}">${key.is_active ? 'ACTIVE' : 'INACTIVE'}</span>
                </div>

                <div class="grid grid-cols-2 gap-y-3 gap-x-4 mb-4">
                    ${detailRow('Rate Limit', `${key.rate_limit}/HR`)}
                    ${detailRow('Expires', this.formatDate(key.expires_at))}
                    ${detailRow('Created', this.formatDate(key.created_at))}
                    ${detailRow('Last Used', this.formatDate(key.last_used_at))}
                    ${key.description ? detailRow('Description', this.escape(key.description)) : ''}
                    ${key.allowed_origins ? detailRow('Allowed Origins', this.escape(key.allowed_origins)) : ''}
                </div>

                <div class="grid grid-cols-2 gap-x-4 mb-6 pt-3 border-t border-gray-800">
                    ${detailRow('Enrollments', `${stats.total_enrollments ?? 0} (${stats.successful_enrollments ?? 0} ok)`)}
                    ${detailRow('Verifications', `${stats.total_verifications ?? 0} (${stats.successful_verifications ?? 0} ok)`)}
                </div>

                <div class="flex flex-wrap gap-3">
                    <button onclick="window.dashboard.toggleEdit(${key.id})" class="text-[9px] font-bold uppercase text-gray-500 hover:text-white transition-colors">Edit</button>
                    ${key.is_active ?
                `<button onclick="window.dashboard.deactivateKey(${key.id})" class="text-[9px] font-bold uppercase text-gray-500 hover:text-white transition-colors">Deactivate</button>` :
                `<button onclick="window.dashboard.activateKey(${key.id})" class="text-[9px] font-bold uppercase text-green-500 hover:text-green-400 transition-colors">Activate</button>`
            }
                    <button onclick="window.dashboard.deleteKey(${key.id})" class="text-[9px] font-bold uppercase text-gray-500 hover:text-red-500 transition-colors">Purge</button>
                </div>

                <!-- Inline edit form (hidden until Edit is clicked) -->
                <div id="edit-form-${key.id}" class="hidden mt-5 pt-5 border-t border-gray-800 space-y-3">
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label class="${lblCls}">Partner Name</label>
                            <input type="text" id="edit-partner-${key.id}" value="${this.escapeAttr(key.partner_name)}" class="${inputCls}">
                        </div>
                        <div>
                            <label class="${lblCls}">Rate Limit / Hour</label>
                            <input type="number" id="edit-rate-${key.id}" value="${this.escapeAttr(key.rate_limit)}" class="${inputCls}">
                        </div>
                    </div>
                    <div>
                        <label class="${lblCls}">Description</label>
                        <input type="text" id="edit-desc-${key.id}" value="${this.escapeAttr(key.description || '')}" class="${inputCls}" placeholder="Optional note">
                    </div>
                    <div>
                        <label class="${lblCls}">Allowed Origins (Comma Separated)</label>
                        <input type="text" id="edit-origins-${key.id}" value="${this.escapeAttr(key.allowed_origins || '')}" class="${inputCls}" placeholder="partner-a.com, app.partner-a.com">
                    </div>
                    <div>
                        <label class="${lblCls}">Expires In (Days)</label>
                        <input type="number" id="edit-expires-${key.id}" value="" class="${inputCls}" placeholder="Blank = keep, 0 = never">
                        <p class="text-[9px] text-gray-600 mt-1 font-mono">Currently: ${this.formatDate(key.expires_at)}. Leave blank to keep, enter 0 to never expire.</p>
                    </div>
                    <div class="flex gap-3 pt-1">
                        <button onclick="window.dashboard.submitEditKey(${key.id})" class="bg-safety text-void font-bold text-[9px] uppercase tracking-widest py-2 px-5 hover:bg-opacity-90 transition-colors">Save</button>
                        <button onclick="window.dashboard.toggleEdit(${key.id})" class="text-[9px] font-bold uppercase text-gray-500 hover:text-white transition-colors">Cancel</button>
                    </div>
                </div>
            </div>
        `;
    }

    async generateApiKey() {
        const partner_name = document.getElementById('partnerName').value.trim();
        if (!partner_name) { window.showToast && window.showToast('Partner name required', 'error'); return; }

        this.elements.generateBtn.disabled = true;
        this.elements.generateBtn.textContent = 'SECURING...';

        // Build payload; only include expires_days when the user actually typed
        // one so the backend keeps "no expiry" as the default (was the bug: the
        // #expiresIn field existed in the form but was never sent).
        const payload = {
            partner_name,
            rate_limit: Number(document.getElementById('apiRateLimit').value) || 100,
            description: document.getElementById('apiDescription').value,
            allowed_origins: document.getElementById('allowedOrigins').value
        };
        const expiresVal = (document.getElementById('expiresIn').value || '').trim();
        if (expiresVal !== '') payload.expires_days = Number(expiresVal);

        try {
            const resp = await fetch('/api/user/api-keys/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const body = await resp.json();
            if (!resp.ok) throw new Error(body.error || body.message || 'Generation failed');

            // --- INI BAGIAN UTAMA YANG DIGANTI ---
            // 1. Masukkan teks key ke dalam <code> (pakai textContent, bukan value)
            document.getElementById('newKeyValue').textContent = body.api_key || body.key;

            // 2. Munculkan box UI lu dengan menghapus class 'hidden'
            document.getElementById('newKeyAlert').classList.remove('hidden');

            // 3. Refresh list api key & angka total di atas
            await this.loadApiKeys();
            await this.loadUserInfo();

            // 4. Kosongkan form input biar rapi lagi
            document.getElementById('apiKeyForm').reset();
            // -------------------------------------

        } catch (e) {
            window.showToast && window.showToast(e.message || 'Generation failed', 'error');
        } finally {
            this.elements.generateBtn.disabled = false;
            this.elements.generateBtn.textContent = 'GENERATE API KEY';
        }
    }

    async deactivateKey(id) {
        if (!await window.showConfirmModal('Deactivate?', 'This will disable the key immediately.', { destructive: true })) return;
        try {
            await fetch(`/api/user/api-keys/${id}/deactivate`, { method: 'POST' });
            await this.loadApiKeys();
        } catch (e) { console.error(e); }
    }

    async activateKey(id) {
        try {
            const resp = await fetch(`/api/user/api-keys/${id}/activate`, { method: 'POST' });
            if (!resp.ok) {
                const b = await resp.json().catch(() => ({}));
                throw new Error(b.message || 'Activation failed');
            }
            window.showToast && window.showToast('API key activated', 'success');
            await this.loadApiKeys();
        } catch (e) {
            window.showToast && window.showToast(e.message || 'Activation failed', 'error');
        }
    }

    toggleEdit(id) {
        const form = document.getElementById(`edit-form-${id}`);
        if (form) form.classList.toggle('hidden');
    }

    async submitEditKey(id) {
        // Always send the editable text/number fields. expires_days is only sent
        // when the user typed something, so a blank box keeps the current expiry
        // (0 explicitly clears it -> never expires).
        const payload = {
            partner_name: (document.getElementById(`edit-partner-${id}`).value || '').trim(),
            description: document.getElementById(`edit-desc-${id}`).value,
            allowed_origins: document.getElementById(`edit-origins-${id}`).value,
            rate_limit: Number(document.getElementById(`edit-rate-${id}`).value) || 100,
        };
        if (!payload.partner_name) {
            window.showToast && window.showToast('Partner name required', 'error');
            return;
        }
        const expVal = (document.getElementById(`edit-expires-${id}`).value || '').trim();
        if (expVal !== '') payload.expires_days = Number(expVal);

        try {
            const resp = await fetch(`/api/user/api-keys/${id}/update`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const body = await resp.json();
            if (!resp.ok) throw new Error(body.message || 'Update failed');
            window.showToast && window.showToast('API key updated', 'success');
            await this.loadApiKeys();
        } catch (e) {
            window.showToast && window.showToast(e.message || 'Update failed', 'error');
        }
    }

    async deleteKey(id) {
        if (!await window.showConfirmModal('Purge Key?', 'Permanent deletion. Irreversible.', { destructive: true })) return;
        try {
            await fetch(`/api/user/api-keys/${id}/delete`, { method: 'POST' });
            await this.loadApiKeys();
        } catch (e) { console.error(e); }
    }

    async startResetFlow() {
        this.elements.resetBtn.disabled = true;
        this.elements.resetBtn.textContent = 'SENDING...';
        try {
            const resp = await fetch('/api/send_reset_verification', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: this.elements.username.textContent })
            });
            if (resp.ok) {
                window.location.href = `/reset/verify-code?username=${encodeURIComponent(this.elements.username.textContent)}`;
            } else {
                const b = await resp.json().catch(() => ({}));
                window.showToast && window.showToast(b.message || 'Failed to send reset code', 'error');
                this.elements.resetBtn.disabled = false;
                this.elements.resetBtn.textContent = 'RESET PASSWORD';
            }
        } catch (e) {
            window.showToast && window.showToast('Network error — try again', 'error');
            this.elements.resetBtn.disabled = false;
            this.elements.resetBtn.textContent = 'RESET PASSWORD';
        }
    }

    formatDate(ds) {
        if (!ds) return 'NEVER';
        return new Date(ds).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase();
    }

    escape(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    // Attribute-safe escaping for values placed inside value="..." of edit inputs.
    escapeAttr(s) {
        if (s === null || s === undefined) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }
}

window.DashboardService = DashboardService;
