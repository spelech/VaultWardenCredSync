function showToast(message, type = 'success') {
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    const toast = document.createElement('div');
    const bgColor = type === 'success' ? 'bg-festool' : type === 'error' ? 'bg-red-600' : 'bg-blue-600';
    toast.className = `${bgColor} text-white px-6 py-3 rounded-xl shadow-2xl flex items-center justify-between min-w-[300px] transform translate-y-10 opacity-0 transition-all duration-300 ease-out border border-white/10 mb-3`;
    toast.innerHTML = `<span class="font-bold text-sm">${message}</span><button onclick="this.parentElement.remove()" class="ml-4 text-white/50 hover:text-white">✕</button>`;
    toastContainer.appendChild(toast);
    setTimeout(() => { toast.classList.remove('translate-y-10', 'opacity-0'); toast.classList.add('translate-y-0', 'opacity-100'); }, 10);
    setTimeout(() => { toast.classList.add('opacity-0', 'translate-x-10'); setTimeout(() => toast.remove(), 300); }, 4000);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'fixed bottom-8 right-8 z-[100] flex flex-col items-end';
    document.body.appendChild(container);
    return container;
}

document.addEventListener('DOMContentLoaded', () => {
    console.log("Credential Portal loaded");
});

let lastGeneratedSSH = null;
let lastGeneratedLiteLLM = null;
let existingSSHKeys = [];
let existingLiteLLMKeys = [];

async function fetchLiteLLMOptions() {
    try {
        const response = await fetch('/api/litellm/options');
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Failed to fetch options');

        const userList = document.getElementById('users-list');
        const teamList = document.getElementById('teams-list');

        if (data.users) {
            userList.innerHTML = data.users.map(u => `<option value="${u.user_id}">${u.user_id} (${u.user_role})</option>`).join('');
        }
        if (data.teams) {
            teamList.innerHTML = data.teams.map(t => `<option value="${t.team_id}">${t.team_alias || t.team_id}</option>`).join('');
        }
    } catch (err) {
        console.error(err);
        showToast("Error loading LiteLLM options", "error");
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
    } catch (err) {
        console.error("Failed to fetch existing keys", err);
    }
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-section').forEach(s => s.classList.add('hidden'));
    document.getElementById(`section-${tabId}`).classList.remove('hidden');
    document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('bg-[#1f2937]', 'text-festool', 'border-l-4', 'border-festool');
        b.classList.add('text-gray-400');
    });
    const activeBtn = document.getElementById(`tab-${tabId}`);
    activeBtn.classList.remove('text-gray-400');
    activeBtn.classList.add('bg-[#1f2937]', 'text-festool', 'border-l-4', 'border-festool');

    fetchExistingKeys();
    if (tabId === 'litellm') {
        fetchLiteLLMOptions();
    }
}

async function generateSSH() {
    const name = document.getElementById('ssh-name').value;
    const comment = document.getElementById('ssh-comment').value;
    const key_type = document.getElementById('ssh-type').value;
    if (!name) return alert('Name is required');

    let overwrite = false;
    if (existingSSHKeys.includes(name)) {
        if (confirm(`An SSH key named "${name}" already exists. Overwrite existing item?`)) {
            overwrite = true;
        } else {
            return;
        }
    }

    const resultDiv = document.getElementById('ssh-result');
    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = '<p class="text-gray-500 animate-pulse font-bold text-xs uppercase tracking-widest">⚙️ Generating Secure Keys...</p>';

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

        resultDiv.innerHTML = `
            <div class="bg-blue-900/20 border border-blue-500/30 rounded-xl p-6 mt-6">
                <h3 class="text-white font-bold mb-4 flex items-center"><span class="mr-2">👁️</span> Review & Sync</h3>
                <div class="space-y-4">
                    <div>
                        <label class="block text-[10px] font-bold text-gray-500 uppercase mb-1">Public Key</label>
                        <div class="relative">
                            <textarea id="preview-ssh-pub" readonly rows="2" class="w-full bg-[#111827] text-festool p-3 text-xs font-mono border border-gray-700 rounded-lg focus:outline-none">${result.keys.public_key}</textarea>
                            <button onclick="copyToClipboard(this)" class="absolute top-2 right-2 text-gray-500 hover:text-festool text-[10px] font-bold uppercase">Copy</button>
                        </div>
                    </div>
                    <div>
                        <label class="block text-[10px] font-bold text-gray-500 uppercase mb-1">Private Key (Hidden in Bitwarden)</label>
                        <div class="relative">
                            <textarea id="preview-ssh-priv" readonly rows="4" class="w-full bg-[#111827] text-festool p-3 text-xs font-mono border border-gray-700 rounded-lg focus:outline-none">${result.keys.private_key}</textarea>
                            <button onclick="copyToClipboard(this)" class="absolute top-2 right-2 text-gray-500 hover:text-festool text-[10px] font-bold uppercase">Copy</button>
                        </div>
                    </div>
                </div>
                <div class="flex space-x-4 mt-6">
                    <button onclick="downloadFile('${name}.pub', lastGeneratedSSH.public_key)" class="flex-1 bg-gray-700 text-white font-bold py-3 rounded-xl hover:bg-gray-600 transition">Download .pub</button>
                    <button onclick="downloadFile('${name}.pem', lastGeneratedSSH.private_key)" class="flex-1 bg-gray-700 text-white font-bold py-3 rounded-xl hover:bg-gray-600 transition">Download .pem</button>
                </div>
                <button onclick="syncSSH()" class="mt-4 w-full bg-festool text-white font-bold py-4 rounded-xl shadow-lg hover:brightness-110 transition active:scale-95">2. Sync to Vaultwarden</button>
            </div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
        resultDiv.innerHTML = `<div class="bg-red-900/20 border border-red-500/30 rounded-xl p-6 mt-6 text-red-400 font-bold">Error: ${err.message}</div>`;
    }
}

async function syncSSH() {
    if (!lastGeneratedSSH) return;
    showToast("Syncing to Vaultwarden...", "info");
    try {
        const response = await fetch('/api/sync-ssh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: lastGeneratedSSH.name,
                private_key: lastGeneratedSSH.private_key,
                public_key: lastGeneratedSSH.public_key,
                overwrite: lastGeneratedSSH.overwrite
            })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Sync failed');
        showToast("SSH Key securely stored in Vaultwarden!");
        document.getElementById('ssh-result').innerHTML = `
            <div class="bg-green-900/20 border border-festool/30 rounded-xl p-6 mt-6">
                <p class="text-festool font-bold flex items-center"><span class="mr-2">✅</span> Successfully Synced to Vaultwarden</p>
                <p class="text-xs text-gray-400 mt-2 italic">The key is now safely stored in your designated folder.</p>
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
    const models_str = document.getElementById('llm-models').value;
    const models = models_str ? models_str.split(',').map(m => m.trim()) : null;

    if (!key_alias) return alert('Key Alias is required');

    if (existingLiteLLMKeys.includes(key_alias)) {
        showToast(`Error: A key with alias "${key_alias}" already exists. Use a unique name.`, "error");
        return;
    }

    const resultDiv = document.getElementById('llm-result');
    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = '<p class="text-gray-500 animate-pulse font-bold text-xs uppercase tracking-widest">⚙️ Requesting Key...</p>';

    try {
        const response = await fetch('/api/generate-litellm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key_alias, user_id, team_id, max_budget, models, key_type })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Generation failed');

        lastGeneratedLiteLLM = { 
            name: key_alias, 
            key: result.key_data.key, 
            alias: key_alias,
            user_id: user_id,
            team_id: team_id,
            key_type: key_type
        };
        showToast(result.message);

        resultDiv.innerHTML = `
            <div class="bg-blue-900/20 border border-blue-500/30 rounded-xl p-6 mt-6">
                <h3 class="text-white font-bold mb-4 flex items-center"><span class="mr-2">👁️</span> Review & Sync</h3>
                <div class="space-y-4">
                    <div>
                        <label class="block text-[10px] font-bold text-gray-500 uppercase mb-1">Generated Virtual Key</label>
                        <div class="relative">
                            <input type="text" readonly class="w-full bg-[#111827] text-festool p-3 text-sm font-mono border border-gray-700 rounded-lg focus:outline-none" value="${result.key_data.key}">
                            <button onclick="copyToClipboard(this)" class="absolute top-3 right-3 text-gray-500 hover:text-festool text-[10px] font-bold uppercase">Copy</button>
                        </div>
                    </div>
                    <div class="grid grid-cols-3 gap-4">
                        <div class="text-[10px] text-gray-400">
                            <span class="font-bold uppercase block text-gray-600 mb-1">Type:</span>
                            <span class="font-mono text-festool uppercase">${key_type}</span>
                        </div>
                        <div class="text-[10px] text-gray-400">
                            <span class="font-bold uppercase block text-gray-600 mb-1">User:</span>
                            <span class="font-mono text-festool">${user_id || 'None'}</span>
                        </div>
                        <div class="text-[10px] text-gray-400">
                            <span class="font-bold uppercase block text-gray-600 mb-1">Team:</span>
                            <span class="font-mono text-festool">${team_id || 'None'}</span>
                        </div>
                    </div>
                </div>
                <div class="flex space-x-4 mt-6">
                    <button onclick="downloadFile('${key_alias}.txt', lastGeneratedLiteLLM.key)" class="flex-1 bg-gray-700 text-white font-bold py-3 rounded-xl hover:bg-gray-600 transition">Download .txt</button>
                </div>
                <button onclick="syncLiteLLM()" class="mt-4 w-full bg-festool text-white font-bold py-4 rounded-xl shadow-lg hover:brightness-110 transition active:scale-95">2. Sync to Vaultwarden</button>
            </div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
        resultDiv.innerHTML = `<div class="bg-red-900/20 border border-red-500/30 rounded-xl p-6 mt-6 text-red-400 font-bold">Error: ${err.message}</div>`;
    }
}

async function syncLiteLLM() {
    if (!lastGeneratedLiteLLM) return;
    showToast("Syncing to Vaultwarden...", "info");
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
                key_type: lastGeneratedLiteLLM.key_type
            })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Sync failed');
        showToast("LiteLLM Key securely stored in Vaultwarden!");
        document.getElementById('llm-result').innerHTML = `
            <div class="bg-green-900/20 border border-festool/30 rounded-xl p-6 mt-6">
                <p class="text-festool font-bold flex items-center"><span class="mr-2">✅</span> Successfully Synced to Vaultwarden</p>
            </div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function storeExternal() {
    const name = document.getElementById('ext-name').value;
    const credential_data = document.getElementById('ext-data').value;
    if (!name || !credential_data) return alert('Name and data are required');

    const resultDiv = document.getElementById('ext-result');
    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = '<p class="text-gray-500 animate-pulse font-bold text-xs uppercase tracking-widest">⚙️ Syncing External Data...</p>';

    try {
        const response = await fetch('/api/store-external', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, credential_data })
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Sync failed');
        
        showToast(result.message);
        resultDiv.innerHTML = `
            <div class="bg-green-900/20 border border-festool/30 rounded-xl p-6 mt-6">
                <p class="text-festool font-bold flex items-center"><span class="mr-2">✅</span> Successfully Synced to Vaultwarden</p>
            </div>
        `;
    } catch (err) {
        showToast(err.message, 'error');
        resultDiv.innerHTML = `<div class="bg-red-900/20 border border-red-500/30 rounded-xl p-6 mt-6 text-red-400 font-bold">Error: ${err.message}</div>`;
    }
}

function copyToClipboard(btn) {
    const el = btn.parentElement.querySelector('textarea, input');
    el.select();
    document.execCommand('copy');
    const oldText = btn.innerText;
    btn.innerText = 'Copied!';
    btn.classList.add('text-festool');
    setTimeout(() => {
        btn.innerText = oldText;
        btn.classList.remove('text-festool');
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
    showToast(`Downloaded ${filename}`);
}
