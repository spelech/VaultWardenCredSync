# 🛡️ VaultWarden Credential Portal

A standalone, secure broker for generating and auto-organizing credentials into Vaultwarden.

## 🚀 Overview
This portal provides a unified interface to:
1. **Generate SSH Keys**: Creates Ed25519 pairs and syncs them as **Native SSH Key** items (`type: 5`) in Vaultwarden.
2. **Generate LiteLLM Keys**: Mints virtual keys via the LiteLLM Proxy API and syncs them as Login items with **Hidden Custom Fields**.
3. **Store External Credentials**: Securely stores JSON (GCP), API keys (OpenRouter), or other strings into designated Vaultwarden folders.

## 🏗️ Architecture
- **Backend**: FastAPI (Python 3.11).
- **Security**: Configurations are stored in an **Encrypted SQLite Database** (`data/portal.db`) using AES-256 (Fernet). The encryption key is generated locally on the first run (`data/master.key`).
- **Organization**: Automatically routes credentials to specific Vaultwarden folders (mapped during setup).
- **UI**: Modern, responsive dashboard built with Tailwind CSS.

## 🛠️ Setup

### 1. Prerequisite
Ensure Docker and Docker Compose are installed.

### 2. Deployment
```bash
docker compose build
docker compose up -d
```

### 3. Onboarding
1. Navigate to `http://localhost:8111`.
2. You will be automatically redirected to `/setup`.
3. Provide your LiteLLM and Vaultwarden API credentials.
4. Select your preferred folders for auto-organization.

## 🧪 Testing
Run tests using `pytest`:
```bash
docker compose exec credential-portal pytest
```

## 🔒 Security Notes
- `data/` directory is ignored by Git and contains the local database and master encryption key.
- Never commit `.env` or `data/master.key`.
- Credentials synced to Bitwarden use **Hidden Custom Fields** to prevent accidental plaintext exposure in the UI.
