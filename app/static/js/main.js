function showToast(message, type = 'success') {
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    const toast = document.createElement('div');
    
    // palette mapping: prussian blue #031d44, deep space #04395e, muted teal #70a288, tan #dab785, burnt peach #d5896f
    const bgColor = type === 'success' ? 'bg-[#70a288]' : type === 'error' ? 'bg-[#d5896f]' : 'bg-[#04395e]';
    
    toast.className = `${bgColor} text-[#031d44] px-8 py-4 rounded-2xl shadow-2xl flex items-center justify-between min-w-[320px] transform translate-y-10 opacity-0 transition-all duration-500 ease-[cubic-bezier(0.23,1,0.32,1)] border border-white/10 mb-4`;
    toast.innerHTML = `
        <span class="font-black text-xs uppercase tracking-widest">${message}</span>
        <button onclick="this.parentElement.remove()" class="ml-6 text-[#031d44]/50 hover:text-[#031d44]">✕</button>
    `;
    
    toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.remove('translate-y-10', 'opacity-0');
        toast.classList.add('translate-y-0', 'opacity-100');
    }, 10);
    
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-x-10');
        setTimeout(() => toast.remove(), 500);
    }, 4500);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'fixed bottom-10 right-10 z-[100] flex flex-col items-end';
    document.body.appendChild(container);
    return container;
}

async function logout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
        window.location.href = '/login';
    } catch (err) {
        window.location.href = '/login';
    }
}

async function checkConnectivity() {
    const statusBadge = document.getElementById('system-status');
    try {
        const response = await fetch('/api/vaultwarden/ssh-keys');
        if (response.ok) {
            statusBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-teal mr-3 animate-pulse"></span>Vaultwarden Connected`;
            statusBadge.className = "inline-flex items-center px-4 py-2 rounded-full text-xs font-bold bg-teal/10 text-teal border border-teal/30 shadow-sm";
        } else {
            throw new Error();
        }
    } catch (err) {
        statusBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-peach mr-3"></span>Vault Connection Failure`;
        statusBadge.className = "inline-flex items-center px-4 py-2 rounded-full text-xs font-bold bg-peach/10 text-peach border border-peach/30 shadow-sm";
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log("QuickCreds Terminal Online");
    checkConnectivity();
    fetchLiteLLMOptions();
});

let lastGeneratedSSH = null;
let lastGeneratedLiteLLM = null;
let existingSSHKeys = [];
let existingLiteLLMKeys = [];

async function fetchLiteLLMOptions() {
    const userSelect = document.getElementById('llm-user');
    const teamSelect = document.getElementById('llm-team');
    const modelSelect = document.getElementById('llm-models');
    const generateBtn = document.querySelector('button[onclick="generateLiteLLM()"]');

    if (generateBtn) {
        generateBtn.disabled = true;
        generateBtn.classList.add('opacity-50', 'cursor-not-allowed');
        generateBtn.innerText = "Loading Options...";
    }

    try {
        const response = await fetch('/api/litellm/options');
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Failed to fetch options');

        if (data.users && userSelect) {
            if (data.users.length === 0) {
                userSelect.innerHTML = '<option value="">None Found</option>';
                userSelect.disabled = true;
            } else {
                userSelect.disabled = false;
                userSelect.innerHTML = '<option value="">-- Select User (Optional) --</option>' + 
                    data.users.map(u => `<option value="${u.user_id}">${u.user_id} (${u.user_role})</option>`).join('');
            }
        }

        if (data.teams && teamSelect) {
            if (data.teams.length === 0) {
                teamSelect.innerHTML = '<option value="">None Available</option>';
                teamSelect.disabled = true;
            } else {
                teamSelect.disabled = false;
                teamSelect.innerHTML = '<option value="">-- Select Team (Optional) --</option>' + 
                    data.teams.map(t => `<option value="${t.team_id}">${t.team_alias || t.team_id}</option>`).join('');
            }
        }

        if (data.models && modelSelect) {
            modelSelect.innerHTML = data.models.map(m => `<option value="${m.id}">${m.id}</option>`).join('');
        }

        if (generateBtn) {
            generateBtn.disabled = false;
            generateBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            generateBtn.innerText = "1. Generate Key";
        }
    } catch (err) {
        console.error(err);
        showToast("Unable to reach LiteLLM API", "error");
        if (userSelect) userSelect.innerHTML = '<option value="">Error Loading</option>';
        if (teamSelect) teamSelect.innerHTML = '<option value="">Error Loading</option>';
        if (modelSelect) modelSelect.innerHTML = '<option value="">Error Loading</option>';
        if (generateBtn) generateBtn.innerText = "API Connection Error";
    }
}

async function fetchExistingKeys() {
    try {
        const [sshRes, llmRes] = await Promise.all([
            fetch('/api/vaultwarden/ssh-keys'),
            fetch('/api/litellm/keys')
        ]);
        const sshData = await sshRes.json();
        const llmData = await llmRes.json();
        existingSSHKeys = sshData.keys || [];
        existingLiteLLMKeys = llmData.keys || [];

        const select = document.getElementById('ssh-existing-select');
        if (select) {
            if (existingSSHKeys.length === 0) {
                select.innerHTML = '<option value="">-- No keys in vault --</option>';
            } else {
                select.innerHTML = '<option value="">-- Select a key --</option>' +
                    existingSSHKeys.map(k => `<option value="${k}">${k}</option>`).join('');
            }
        }
    } catch (err) {
        console.error("Failed to fetch existing vault items", err);
    }
}

async function loadExistingSSHKey() {
    const name = document.getElementById('ssh-existing-select').value;
    if (!name) return alert('Please select a key');

    const resultDiv = document.getElementById('ssh-result');
    if (resultDiv) {
        resultDiv.innerHTML = '';
        resultDiv.classList.add('hidden');
    }

    const detailDiv = document.getElementById('ssh-existing-detail');
    detailDiv.classList.remove('hidden');
    detailDiv.innerHTML = '<p class="text-teal animate-pulse font-black text-xs uppercase tracking-widest">⚙️ Retrieving key details...</p>';

    try {
        const response = await fetch(`/api/vaultwarden/ssh-keys/${encodeURIComponent(name)}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Failed to retrieve key');

        const key = data.key;
        lastGeneratedSSH = {
            name: key.name,
            private_key: key.private_key,
            public_key: key.public_key,
            fingerprint: key.fingerprint,
            overwrite: true
        };

        detailDiv.innerHTML = `
            <div class="bg-[#031d44]/50 border border-[#70a288]/20 rounded-3xl p-8 mt-6">
                <h3 class="text-white font-black text-xs uppercase tracking-widest mb-4 flex items-center"><span class="mr-3">👁️</span> Key Details: ${key.name}</h3>
                
                <div class="space-y-4 mb-6">
                    <div>
                        <label class="block text-[10px] font-black text-gray-600 uppercase tracking-widest mb-1.5">Registered Hosts</label>
                        <div class="text-xs text-tan font-mono bg-[#031d44] p-3 border border-white/5 rounded-xl">
                            ${key.registered_hosts || '<span class="italic text-gray-500">Not registered on any hosts yet</span>'}
                        </div>
                    </div>
                    <div>
                        <label class="block text-[10px] font-black text-gray-600 uppercase tracking-widest mb-1.5">Public Key</label>
                        <div class="relative">
                            <textarea id="preview-ssh-pub" readonly rows="2" class="w-full bg-[#031d44] text-teal p-4 text-xs font-mono border border-white/5 rounded-xl focus:outline-none shadow-inner">${key.public_key}</textarea>
                            <button onclick="copyToClipboard(this)" class="absolute top-4 right-4 text-gray-500 hover:text-tan text-[9px] font-black uppercase tracking-tighter">Copy</button>
                        </div>
                    </div>
                </div>

                <div class="border-t border-white/5 mt-6 pt-6">
                    <h4 class="text-white font-black text-xs uppercase tracking-widest mb-4 flex items-center"><span class="mr-3">🚀</span> Push Key to Remote Host</h4>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        <div class="col-span-2">
                            <label class="block text-[9px] font-black text-gray-500 uppercase tracking-widest mb-1">Hostname / IP</label>
                            <input type="text" id="push-host" class="block w-full rounded-xl border-transparent text-white p-2 outline-none text-xs" style="background-color: var(--neutral-black)" placeholder="e.g. 192.168.1.50">
                        </div>
                        <div>
                            <label class="block text-[9px] font-black text-gray-500 uppercase tracking-widest mb-1">Port</label>
                            <input type="number" id="push-port" value="22" class="block w-full rounded-xl border-transparent text-white p-2 outline-none text-xs" style="background-color: var(--neutral-black)">
                        </div>
                        <div>
                            <label class="block text-[9px] font-black text-gray-500 uppercase tracking-widest mb-1">Username</label>
                            <input type="text" id="push-user" value="root" class="block w-full rounded-xl border-transparent text-white p-2 outline-none text-xs" style="background-color: var(--neutral-black)">
                        </div>
                        <div class="col-span-2">
                            <label class="block text-[9px] font-black text-gray-500 uppercase tracking-widest mb-1">Password</label>
                            <input type="password" id="push-password" class="block w-full rounded-xl border-transparent text-white p-2 outline-none text-xs" style="background-color: var(--neutral-black)" placeholder="SSH Password">
                        </div>
                        <div class="col-span-2 flex items-end">
                            <button onclick="pushSSHKey()" class="w-full bg-[#70a288] text-[#031d44] font-black py-2.5 rounded-xl hover:brightness-110 transition uppercase tracking-widest text-[10px]">Register Key on Host</button>
                        </div>
                    </div>
                    <div id="push-status" class="hidden text-[10px] font-mono mt-2"></div>
                </div>
            </div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
        detailDiv.innerHTML = `<div class="bg-burnt-peach/10 border border-burnt-peach/30 rounded-2xl p-6 mt-6 text-burnt-peach font-black text-xs uppercase tracking-widest">Error Loading Details: ${err.message}</div>`;
    }
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-section').forEach(s => s.classList.add('hidden'));
    document.getElementById(`section-${tabId}`).classList.remove('hidden');
    document.querySelectorAll('.sidebar-btn').forEach(b => {
        b.classList.remove('active');
        b.classList.add('text-gray-400');
    });
    const activeBtn = document.getElementById(`tab-${tabId}`);
    activeBtn.classList.remove('text-gray-400');
    activeBtn.classList.add('active');

    fetchExistingKeys();
    if (tabId === 'litellm') {
        fetchLiteLLMOptions();
    }
}

async function generateSSH() {
    const name = document.getElementById('ssh-name').value;
    const comment = document.getElementById('ssh-comment').value;
    const key_type = document.getElementById('ssh-type').value;
    if (!name) return alert('Key name required');

    let overwrite = false;
    if (existingSSHKeys.includes(name)) {
        if (confirm(`An SSH key named "${name}" already exists. Overwrite existing vault item?`)) {
            overwrite = true;
        } else {
            return;
        }
    }

    const detailDiv = document.getElementById('ssh-existing-detail');
    if (detailDiv) {
        detailDiv.innerHTML = '';
        detailDiv.classList.add('hidden');
    }

    const resultDiv = document.getElementById('ssh-result');
    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = '<p class="text-teal animate-pulse font-black text-xs uppercase tracking-widest">⚙️ Running ssh-keygen...</p>';

    try {
        const response = await fetch('/api/generate-ssh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, comment, key_type })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Generation failed');

        lastGeneratedSSH = { name, overwrite, ...result.keys };
        showToast(result.message);

        const filename = `${name}_id_${key_type}`;
        resultDiv.innerHTML = `
            <div class="bg-[#031d44]/50 border border-[#70a288]/20 rounded-3xl p-8 mt-10">
                <h3 class="text-white font-black text-xs uppercase tracking-widest mb-6 flex items-center"><span class="mr-3">👁️</span> Secure Review Stage</h3>
                <div class="space-y-6">
                    <div>
                        <label class="block text-[10px] font-black text-gray-600 uppercase tracking-widest mb-2">Public Key</label>
                        <div class="relative">
                            <textarea id="preview-ssh-pub" readonly rows="2" class="w-full bg-[#031d44] text-teal p-4 text-xs font-mono border border-white/5 rounded-xl focus:outline-none shadow-inner">${result.keys.public_key}</textarea>
                            <button onclick="copyToClipboard(this)" class="absolute top-4 right-4 text-gray-500 hover:text-tan text-[9px] font-black uppercase tracking-tighter">Copy</button>
                        </div>
                    </div>
                    <div>
                        <label class="block text-[10px] font-black text-gray-600 uppercase tracking-widest mb-2">Private Key (Masked in Vault)</label>
                        <div class="relative">
                            <textarea id="preview-ssh-priv" readonly rows="4" class="w-full bg-[#031d44] text-teal p-4 text-xs font-mono border border-white/5 rounded-xl focus:outline-none shadow-inner">${result.keys.private_key}</textarea>
                            <button onclick="copyToClipboard(this)" class="absolute top-4 right-4 text-gray-500 hover:text-tan text-[9px] font-black uppercase tracking-tighter">Copy</button>
                        </div>
                    </div>
                </div>
                <div class="flex space-x-4 mt-8">
                    <button onclick="downloadFile('${filename}.pub', lastGeneratedSSH.public_key)" class="flex-1 bg-white/5 text-white font-black py-4 rounded-2xl hover:bg-white/10 transition uppercase tracking-widest text-[10px]">Download Pub</button>
                    <button onclick="downloadFile('${filename}', lastGeneratedSSH.private_key)" class="flex-1 bg-white/5 text-white font-black py-4 rounded-2xl hover:bg-white/10 transition uppercase tracking-widest text-[10px]">Download Key</button>
                </div>
                <button onclick="syncSSH()" class="btn-primary mt-6 w-full font-black py-5 rounded-2xl shadow-xl uppercase tracking-widest text-sm">2. Transmit to Vaultwarden</button>

                <div class="border-t border-white/5 mt-8 pt-8">
                    <h4 class="text-white font-black text-xs uppercase tracking-widest mb-4 flex items-center"><span class="mr-3">🚀</span> Push Key to Remote Host (Optional)</h4>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        <div class="col-span-2">
                            <label class="block text-[9px] font-black text-gray-500 uppercase tracking-widest mb-1">Hostname / IP</label>
                            <input type="text" id="push-host" class="block w-full rounded-xl border-transparent text-white p-2 outline-none text-xs" style="background-color: var(--neutral-black)" placeholder="e.g. 192.168.1.50">
                        </div>
                        <div>
                            <label class="block text-[9px] font-black text-gray-500 uppercase tracking-widest mb-1">Port</label>
                            <input type="number" id="push-port" value="22" class="block w-full rounded-xl border-transparent text-white p-2 outline-none text-xs" style="background-color: var(--neutral-black)">
                        </div>
                        <div>
                            <label class="block text-[9px] font-black text-gray-500 uppercase tracking-widest mb-1">Username</label>
                            <input type="text" id="push-user" value="root" class="block w-full rounded-xl border-transparent text-white p-2 outline-none text-xs" style="background-color: var(--neutral-black)">
                        </div>
                        <div class="col-span-2">
                            <label class="block text-[9px] font-black text-gray-500 uppercase tracking-widest mb-1">Password</label>
                            <input type="password" id="push-password" class="block w-full rounded-xl border-transparent text-white p-2 outline-none text-xs" style="background-color: var(--neutral-black)" placeholder="SSH Password">
                        </div>
                        <div class="col-span-2 flex items-end">
                            <button onclick="pushSSHKey()" class="w-full bg-[#70a288] text-[#031d44] font-black py-2.5 rounded-xl hover:brightness-110 transition uppercase tracking-widest text-[10px]">Register Key on Host</button>
                        </div>
                    </div>
                    <div id="push-status" class="hidden text-[10px] font-mono mt-2"></div>
                </div>
            </div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
        resultDiv.innerHTML = `<div class="bg-burnt-peach/10 border border-burnt-peach/30 rounded-2xl p-6 mt-6 text-burnt-peach font-black text-xs uppercase tracking-widest">Transaction Failure: ${err.message}</div>`;
    }
}

async function pushSSHKey() {
    if (!lastGeneratedSSH) return;
    const host = document.getElementById('push-host').value;
    const port = parseInt(document.getElementById('push-port').value) || 22;
    const username = document.getElementById('push-user').value;
    const password = document.getElementById('push-password').value;
    
    if (!host || !username) {
        return alert("Hostname and username are required");
    }
    
    const statusDiv = document.getElementById('push-status');
    statusDiv.classList.remove('hidden');
    statusDiv.className = "text-teal animate-pulse font-bold mt-2";
    statusDiv.innerText = "Connecting and registering public key...";
    
    showToast("Connecting to host...", "info");
    
    try {
        const response = await fetch('/api/push-ssh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                host: host,
                username: username,
                public_key: lastGeneratedSSH.public_key,
                password: password || null,
                port: port,
                name: lastGeneratedSSH.name
            })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Failed to push key');
        
        statusDiv.className = "text-teal font-bold mt-2";
        statusDiv.innerText = `Success: ${result.message}`;
        showToast("SSH Key successfully registered on host");
    } catch (err) {
        statusDiv.className = "text-peach font-bold mt-2";
        statusDiv.innerText = `Error: ${err.message}`;
        showToast(err.message, "error");
    }
}

async function syncSSH() {
    if (!lastGeneratedSSH) return;
    showToast("Transmitting data...", "info");
    try {
        const response = await fetch('/api/sync-ssh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: lastGeneratedSSH.name,
                private_key: lastGeneratedSSH.private_key,
                public_key: lastGeneratedSSH.public_key,
                fingerprint: lastGeneratedSSH.fingerprint,
                overwrite: lastGeneratedSSH.overwrite
            })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Transmission failed');
        showToast("Encrypted and stored in Vaultwarden");
        document.getElementById('ssh-result').innerHTML = `
            <div class="bg-teal/10 border border-teal/30 rounded-3xl p-10 mt-10">
                <p class="text-teal font-black text-xs uppercase tracking-[0.2em] flex items-center"><span class="mr-3 text-lg">✅</span> Vault Transmission Complete</p>
                <p class="text-[11px] text-gray-500 mt-4 italic leading-relaxed">The item has been securely provisioned to your designated SSH folder.</p>
            </div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function generateLiteLLM() {
    const key_alias = document.getElementById('llm-alias').value;
    const key_type = document.getElementById('llm-key-type').value;
    const user_id = document.getElementById('llm-user').value || null;
    const team_id = document.getElementById('llm-team').value || null;
    const max_budget = parseFloat(document.getElementById('llm-budget').value) || null;
    const budget_duration = document.getElementById('llm-duration').value || null;
    
    // Multi-select for models
    const modelSelect = document.getElementById('llm-models');
    const models = Array.from(modelSelect.selectedOptions).map(o => o.value).filter(v => v !== "");

    if (!key_alias) return alert('Alias required');

    if (existingLiteLLMKeys.includes(key_alias)) {
        showToast(`Terminal Error: Alias "${key_alias}" already in use.`, "error");
        return;
    }

    const resultDiv = document.getElementById('llm-result');
    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = '<p class="text-teal animate-pulse font-black text-xs uppercase tracking-widest">⚙️ Polling Proxy API...</p>';

    try {
        const response = await fetch('/api/generate-litellm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key_alias, user_id, team_id, max_budget, budget_duration, models, key_type })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'API Call failed');

        lastGeneratedLiteLLM = { 
            name: key_alias, 
            key: result.key_data.key, 
            alias: key_alias, 
            user_id, 
            team_id, 
            key_type,
            max_budget,
            budget_duration
        };
        showToast(result.message);

        resultDiv.innerHTML = `
            <div class="bg-[#031d44]/50 border border-[#70a288]/20 rounded-3xl p-8 mt-10">
                <h3 class="text-white font-black text-xs uppercase tracking-widest mb-6 flex items-center"><span class="mr-3">👁️</span> Secure Review Stage</h3>
                <div class="space-y-6">
                    <div>
                        <label class="block text-[10px] font-black text-gray-600 uppercase tracking-widest mb-2">Virtual Key</label>
                        <div class="relative">
                            <input type="text" id="preview-llm-key" readonly class="w-full bg-[#031d44] text-teal p-4 text-xs font-mono border border-white/5 rounded-xl focus:outline-none shadow-inner" value="${result.key_data.key}">
                            <button onclick="copyToClipboard(this)" class="absolute top-4 right-4 text-gray-500 hover:text-tan text-[9px] font-black uppercase tracking-tighter">Copy</button>
                        </div>
                    </div>
                    <div class="grid grid-cols-3 gap-6">
                        <div class="bg-[#031d44] p-3 rounded-xl border border-white/5">
                            <span class="block text-[8px] font-black text-gray-600 uppercase mb-1">Type</span>
                            <span class="text-[10px] font-mono text-tan uppercase">${key_type}</span>
                        </div>
                        <div class="bg-[#031d44] p-3 rounded-xl border border-white/5">
                            <span class="block text-[8px] font-black text-gray-600 uppercase mb-1">User</span>
                            <span class="text-[10px] font-mono text-tan truncate">${user_id || 'None'}</span>
                        </div>
                        <div class="bg-[#031d44] p-3 rounded-xl border border-white/5">
                            <span class="block text-[8px] font-black text-gray-600 uppercase mb-1">Duration</span>
                            <span class="text-[10px] font-mono text-tan truncate">${budget_duration || 'Lifetime'}</span>
                        </div>
                    </div>
                </div>
                <div class="flex space-x-4 mt-8">
                    <button onclick="downloadFile('${key_alias}.txt', lastGeneratedLiteLLM.key)" class="flex-1 bg-white/5 text-white font-black py-4 rounded-2xl hover:bg-white/10 transition uppercase tracking-widest text-[10px]">Download Key</button>
                </div>
                <button onclick="syncLiteLLM()" class="btn-primary mt-6 w-full font-black py-5 rounded-2xl shadow-xl uppercase tracking-widest text-sm">2. Transmit to Vaultwarden</button>
            </div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
        resultDiv.innerHTML = `<div class="bg-burnt-peach/10 border border-burnt-peach/30 rounded-2xl p-6 mt-6 text-burnt-peach font-black text-xs uppercase tracking-widest">Transaction Failure: ${err.message}</div>`;
    }
}

async function syncLiteLLM() {
    if (!lastGeneratedLiteLLM) return;
    showToast("Transmitting data...", "info");
    try {
        const response = await fetch('/api/sync-litellm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: lastGeneratedLiteLLM.name,
                key: lastGeneratedLiteLLM.key,
                alias: lastGeneratedLiteLLM.alias,
                user_id: lastGeneratedLiteLLM.user_id,
                team_id: lastGeneratedLiteLLM.team_id,
                key_type: lastGeneratedLiteLLM.key_type,
                max_budget: lastGeneratedLiteLLM.max_budget,
                budget_duration: lastGeneratedLiteLLM.budget_duration
            })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Transmission failed');
        showToast("Stored in Vaultwarden");
        document.getElementById('llm-result').innerHTML = `
            <div class="bg-teal/10 border border-teal/30 rounded-3xl p-10 mt-10">
                <p class="text-teal font-black text-xs uppercase tracking-[0.2em] flex items-center"><span class="mr-3 text-lg">✅</span> Vault Transmission Complete</p>
            </div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function storeExternal() {
    const name = document.getElementById('ext-name').value;
    const credential_data = document.getElementById('ext-data').value;
    if (!name || !credential_data) return alert('Metadata missing');

    const resultDiv = document.getElementById('ext-result');
    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = '<p class="text-teal animate-pulse font-black text-xs uppercase tracking-widest">⚙️ Securing External Payload...</p>';

    try {
        const response = await fetch('/api/store-external', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, credential_data })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Transmission failed');
        
        showToast("Encrypted and stored");
        resultDiv.innerHTML = `
            <div class="bg-teal/10 border border-teal/30 rounded-3xl p-10 mt-10">
                <p class="text-teal font-black text-xs uppercase tracking-[0.2em] flex items-center"><span class="mr-3 text-lg">✅</span> Vault Transmission Complete</p>
            </div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
        resultDiv.innerHTML = `<div class="bg-burnt-peach/10 border border-burnt-peach/30 rounded-2xl p-6 mt-6 text-burnt-peach font-black text-xs uppercase tracking-widest">Transaction Failure: ${err.message}</div>`;
    }
}

function copyToClipboard(btn) {
    const el = btn.parentElement.querySelector('textarea, input');
    el.select();
    document.execCommand('copy');
    const oldText = btn.innerText;
    btn.innerText = 'Copied';
    btn.classList.add('text-tan');
    setTimeout(() => {
        btn.innerText = oldText;
        btn.classList.remove('text-tan');
    }, 2000);
}

function downloadFile(filename, text) {
    const element = document.createElement('a');
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(text));
    element.setAttribute('download', filename);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
    showToast(`Stored ${filename}`);
}
