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
            this.elements.generateBtn.addEventListener('click', () => this.generateApiKey());
        }
        if (this.elements.resetBtn) {
            this.elements.resetBtn.addEventListener('click', () => this.startResetFlow());
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
            this.elements.username.textContent = data.username;
            this.elements.email.textContent = data.email || '-';
            this.elements.createdAt.textContent = this.formatDate(data.created_at);
            this.elements.emailVerified.textContent = data.email_verified ? 'VERIFIED' : 'PENDING';
            this.elements.emailVerified.className = data.email_verified ? 'text-green-500' : 'text-neon-orange';
            this.elements.enrollmentCount.textContent = data.enrollment_count ?? 0;
            this.elements.hasPassword.textContent = data.has_password ? 'ACTIVE' : 'INACTIVE';
            this.elements.apiKeyCount.textContent = data.api_key_count ?? 0;
        } catch (e) {
            console.error(e);
        }
    }

    async loadApiKeys() {
        this.elements.apiKeyLoading.classList.remove('hidden');
        this.elements.apiKeyList.innerHTML = '';

        try {
            const resp = await fetch('/api/user/api-keys?include_inactive=true');
            const body = await resp.json();
            if (!resp.ok) throw new Error(body.message || 'Load failed');

            const keys = body.keys || [];
            if (!keys.length) {
                this.elements.apiKeyList.innerHTML = '<div class="text-gray-600 text-[10px] uppercase py-8 text-center border border-dashed border-gray-800">No active integrations</div>';
                return;
            }

            this.elements.apiKeyList.innerHTML = keys.map(k => this.renderApiKey(k)).join('');
        } catch (e) {
            this.elements.apiKeyList.innerHTML = `<div class="text-red-500 text-xs">${e.message}</div>`;
        } finally {
            this.elements.apiKeyLoading.classList.add('hidden');
        }
    }

    renderApiKey(key) {
        const statusClass = key.is_active ? 'text-neon-orange' : 'text-gray-600';
        return `
            <div class="bg-dark-obsidian border border-gray-800 p-5 group hover:border-gray-700 transition-colors">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <h4 class="text-white font-bold text-xs uppercase tracking-widest mb-1">${this.escape(key.partner_name)}</h4>
                        <p class="text-[9px] text-gray-600 font-mono uppercase">${key.key_prefix}...</p>
                    </div>
                    <span class="text-[9px] font-bold uppercase tracking-tighter ${statusClass}">${key.is_active ? 'ACTIVE' : 'INACTIVE'}</span>
                </div>
                <div class="grid grid-cols-2 gap-y-2 mb-6">
                    <div>
                        <p class="text-[9px] text-gray-600 uppercase font-bold">Rate Limit</p>
                        <p class="text-[10px] text-gray-400 font-mono">${key.rate_limit}/HR</p>
                    </div>
                    <div>
                        <p class="text-[9px] text-gray-600 uppercase font-bold">Expires</p>
                        <p class="text-[10px] text-gray-400 font-mono">${this.formatDate(key.expires_at)}</p>
                    </div>
                </div>
                <div class="flex gap-2">
                    ${key.is_active ? 
                        `<button onclick="window.dashboard.deactivateKey(${key.id})" class="text-[9px] font-bold uppercase text-gray-500 hover:text-white transition-colors">Deactivate</button>` : 
                        ''
                    }
                    <button onclick="window.dashboard.deleteKey(${key.id})" class="text-[9px] font-bold uppercase text-gray-500 hover:text-red-500 transition-colors">Purge</button>
                </div>
            </div>
        `;
    }

    async generateApiKey() {
        const partner_name = document.getElementById('partnerName').value.trim();
        if (!partner_name) return alert('Partner name required');

        this.elements.generateBtn.disabled = true;
        this.elements.generateBtn.textContent = 'SECURING...';

        try {
            const resp = await fetch('/api/user/api-keys/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    partner_name,
                    rate_limit: Number(document.getElementById('apiRateLimit').value) || 100,
                    description: document.getElementById('apiDescription').value,
                    allowed_origins: document.getElementById('allowedOrigins').value
                })
            });
            const body = await resp.json();
            if (!resp.ok) throw new Error(body.message || 'Generation failed');

            this.elements.newApiKeyValue.value = body.api_key;
            this.elements.apiKeyResult.classList.remove('hidden');
            await this.loadApiKeys();
        } catch (e) {
            alert(e.message);
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
                const b = await resp.json();
                alert(b.message || 'Failed');
                this.elements.resetBtn.disabled = false;
                this.elements.resetBtn.textContent = 'RESET PASSWORD';
            }
        } catch (e) {
            alert('Error');
            this.elements.resetBtn.disabled = false;
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
}

window.DashboardService = DashboardService;
