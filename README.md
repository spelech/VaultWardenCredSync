# 🛡️ QuickCreds Terminal

A standalone, secure broker for generating and auto-organizing credentials into Vaultwarden. Formally integrated into the Webservices stack.

## 🚀 Overview
QuickCreds provides a unified interface to:
1. **Generate SSH Keys**: Creates Ed25519 or RSA pairs and syncs them as **Native SSH Key** items (`type: 5`) in Vaultwarden.
2. **Generate LiteLLM Keys**: Mints virtual keys via the LiteLLM Proxy API and syncs them as Login items with **Hidden Custom Fields**. Supports advanced options (Roles, Teams, Budgets).
3. **Store External Credentials**: Securely stores JSON (GCP), API keys (OpenRouter), or other strings into designated Vaultwarden folders.

## 🏗️ Architecture
- **Backend**: FastAPI (Python 3.11).
- **Security**: Configurations are stored in an **Encrypted SQLite Database** (`data/portal.db`) using AES-256 (Fernet). The encryption key is generated locally on the first run (`data/portal.key`).
- **Organization**: Automatically routes credentials to specific Vaultwarden folders.
- **UI**: High-contrast **QuickCreds Prussian Blue & Festool Green** theme with real-time validation and toast notifications.

## 🛠️ Deployment
Integrated into the home infrastructure webservices stack.
```bash
cd /containers/webservices
docker compose up -d quickcreds
```

## 🌐 Access
- **Local (SSL)**: `https://quickcreds.wileyriley.com`
- **Local (Internal)**: `http://quickcreds.lan` (managed via AdGuard rewrites)
- **Port**: `8006` (Internal)

## 🧪 Testing
```bash
docker compose exec quickcreds python3 -m pytest
```

## 🔒 Security Notes
- `data/` directory is ignored by Git and contains the local database and portal encryption key.
- Never commit `data/portal.key`.
- Credentials synced to Bitwarden use **Hidden Custom Fields** to prevent accidental plaintext exposure in the UI.
- **Authentication**: The Bitwarden CLI requires your **Master Password** to locally encrypt/decrypt items. This portal stores that password in the encrypted SQLite database mentioned above.
