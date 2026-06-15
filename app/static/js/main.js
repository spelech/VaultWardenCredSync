document.addEventListener('DOMContentLoaded', () => {
    console.log("Credential Portal loaded");

    const contentArea = document.getElementById('content-area');
    const tabs = document.querySelectorAll('.grid > div');

    const forms = {
        ssh: `
            <h3 class="text-lg font-medium mb-4">Generate SSH Keypair</h3>
            <div class="space-y-4 max-w-md">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Key Name</label>
                    <input type="text" id="ssh-name" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm border p-2" placeholder="e.g. github-action-key">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Comment (Optional)</label>
                    <input type="text" id="ssh-comment" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm border p-2" placeholder="user@host">
                </div>
                <button onclick="generateSSH()" class="bg-blue-600 text-white px-4 py-2 rounded shadow hover:bg-blue-700">Generate & Sync</button>
            </div>
            <div id="ssh-result" class="mt-6 hidden"></div>
        `,
        litellm: `
            <h3 class="text-lg font-medium mb-4">Generate LiteLLM Virtual Key</h3>
            <div class="space-y-4 max-w-md">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Key Alias / Description</label>
                    <input type="text" id="llm-name" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm border p-2" placeholder="e.g. dev-agent-1">
                </div>
                <button onclick="generateLiteLLM()" class="bg-blue-600 text-white px-4 py-2 rounded shadow hover:bg-blue-700">Generate & Sync</button>
            </div>
            <div id="llm-result" class="mt-6 hidden"></div>
        `,
        external: `
            <h3 class="text-lg font-medium mb-4">Store External Credential</h3>
            <div class="space-y-4 max-w-lg">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Credential Name</label>
                    <input type="text" id="ext-name" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm border p-2" placeholder="e.g. GCP Service Account JSON">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">Credential Data (JSON, String, etc)</label>
                    <textarea id="ext-data" rows="5" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm border p-2 font-mono text-sm"></textarea>
                </div>
                <button onclick="storeExternal()" class="bg-blue-600 text-white px-4 py-2 rounded shadow hover:bg-blue-700">Sync to Vaultwarden</button>
            </div>
            <div id="ext-result" class="mt-6 hidden"></div>
        `
    };

    tabs[0].addEventListener('click', () => { contentArea.innerHTML = forms.ssh; setActiveTab(tabs[0]); });
    tabs[1].addEventListener('click', () => { contentArea.innerHTML = forms.litellm; setActiveTab(tabs[1]); });
    tabs[2].addEventListener('click', () => { contentArea.innerHTML = forms.external; setActiveTab(tabs[2]); });

    function setActiveTab(activeTab) {
        tabs.forEach(t => t.classList.remove('ring-2', 'ring-blue-500'));
        activeTab.classList.add('ring-2', 'ring-blue-500');
    }
});

async function makeRequest(url, data, resultElementId) {
    const resultDiv = document.getElementById(resultElementId);
    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = '<p class="text-gray-500">Processing...</p>';

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

        let resultHtml = `<div class="bg-green-50 border-l-4 border-green-500 p-4 mb-4">
            <p class="text-green-700 font-medium">${result.message}</p>
        </div>`;

        if (result.keys) {
            resultHtml += `
                <div class="mt-4">
                    <label class="block text-sm font-medium text-gray-700">Public Key</label>
                    <textarea readonly rows="3" class="mt-1 w-full bg-gray-50 p-2 text-xs font-mono border rounded">${result.keys.public_key}</textarea>
                </div>
                <div class="mt-4">
                    <label class="block text-sm font-medium text-gray-700">Private Key</label>
                    <textarea readonly rows="5" class="mt-1 w-full bg-gray-50 p-2 text-xs font-mono border rounded">${result.keys.private_key}</textarea>
                </div>
            `;
        }

        if (result.key_data) {
            resultHtml += `
                <div class="mt-4">
                    <label class="block text-sm font-medium text-gray-700">Virtual Key</label>
                    <input type="text" readonly class="mt-1 w-full bg-gray-50 p-2 text-sm font-mono border rounded" value="${result.key_data.key}">
                </div>
            `;
        }

        resultDiv.innerHTML = resultHtml;
    } catch (err) {
        resultDiv.innerHTML = `<div class="bg-red-50 border-l-4 border-red-500 p-4">
            <p class="text-red-700 font-medium">Error: ${err.message}</p>
        </div>`;
    }
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
