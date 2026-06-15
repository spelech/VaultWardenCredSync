function showToast(message, type = 'success') {
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    const toast = document.createElement('div');
    
    const bgColor = type === 'success' ? 'bg-festool' : type === 'error' ? 'bg-red-600' : 'bg-blue-600';
    
    toast.className = `${bgColor} text-white px-6 py-3 rounded-xl shadow-2xl flex items-center justify-between min-w-[300px] transform translate-y-10 opacity-0 transition-all duration-300 ease-out border border-white/10 mb-3`;
    toast.innerHTML = `
        <span class="font-bold text-sm">${message}</span>
        <button onclick="this.parentElement.remove()" class="ml-4 text-white/50 hover:text-white">✕</button>
    `;
    
    toastContainer.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
        toast.classList.remove('translate-y-10', 'opacity-0');
        toast.classList.add('translate-y-0', 'opacity-100');
    }, 10);
    
    // Auto remove
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-x-10');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
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
}

async function makeRequest(url, data, resultElementId) {
    const resultDiv = document.getElementById(resultElementId);
    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = '<p class="text-gray-500 animate-pulse font-bold text-xs uppercase tracking-widest">⚙️ Initializing Secure Transaction...</p>';

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.detail || 'Request failed');
        }

        showToast(result.message);

        let resultHtml = `
            <div class="bg-green-900/20 border border-festool/30 rounded-xl p-6 mt-6">
                <div class="flex items-center mb-4">
                    <span class="text-festool text-xl mr-2">✅</span>
                    <p class="text-white font-bold">${result.message}</p>
                </div>
        `;

        if (result.keys) {
            resultHtml += `
                <div class="space-y-4">
                    <div>
                        <label class="block text-[10px] font-bold text-gray-500 uppercase mb-1">Public Key</label>
                        <div class="relative">
                            <textarea readonly rows="2" class="w-full bg-[#111827] text-festool p-3 text-xs font-mono border border-gray-700 rounded-lg focus:outline-none">${result.keys.public_key}</textarea>
                            <button onclick="copyToClipboard(this)" class="absolute top-2 right-2 text-gray-500 hover:text-festool text-[10px] font-bold uppercase">Copy</button>
                        </div>
                    </div>
                    <div>
                        <label class="block text-[10px] font-bold text-gray-500 uppercase mb-1">Private Key (Hidden in Bitwarden)</label>
                        <div class="relative">
                            <textarea readonly rows="4" class="w-full bg-[#111827] text-festool p-3 text-xs font-mono border border-gray-700 rounded-lg focus:outline-none">${result.keys.private_key}</textarea>
                            <button onclick="copyToClipboard(this)" class="absolute top-2 right-2 text-gray-500 hover:text-festool text-[10px] font-bold uppercase">Copy</button>
                        </div>
                    </div>
                </div>
            `;
        }

        if (result.key_data) {
            resultHtml += `
                <div class="mt-4">
                    <label class="block text-[10px] font-bold text-gray-500 uppercase mb-1">Virtual Key</label>
                    <div class="relative">
                        <input type="text" readonly class="w-full bg-[#111827] text-festool p-3 text-sm font-mono border border-gray-700 rounded-lg focus:outline-none" value="${result.key_data.key}">
                        <button onclick="copyToClipboard(this)" class="absolute top-3 right-3 text-gray-500 hover:text-festool text-[10px] font-bold uppercase">Copy</button>
                    </div>
                </div>
            `;
        }

        resultHtml += `</div>`;
        resultDiv.innerHTML = resultHtml;
    } catch (err) {
        showToast(err.message, 'error');
        resultDiv.innerHTML = `
            <div class="bg-red-900/20 border border-red-500/30 rounded-xl p-6 mt-6">
                <div class="flex items-center">
                    <span class="text-red-500 text-xl mr-2">❌</span>
                    <p class="text-red-400 font-bold">Error: ${err.message}</p>
                </div>
            </div>
        `;
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

window.generateSSH = () => {
    const name = document.getElementById('ssh-name').value;
    const comment = document.getElementById('ssh-comment').value;
    if (!name) return alert('Name is required');
    makeRequest('/api/generate-ssh', { name, comment }, 'ssh-result');
};

window.generateLiteLLM = () => {
    const name = document.getElementById('llm-name').value;
    if (!name) return alert('Alias is required');
    makeRequest('/api/generate-litellm', { name }, 'llm-result');
};

window.storeExternal = () => {
    const name = document.getElementById('ext-name').value;
    const credential_data = document.getElementById('ext-data').value;
    if (!name || !credential_data) return alert('Name and data are required');
    makeRequest('/api/store-external', { name, credential_data }, 'ext-result');
};
