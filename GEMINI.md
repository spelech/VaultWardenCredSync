# Gemini Mandates: Credential Portal

Follow these architecture and security rules when modifying this codebase.

## 🏗️ Architecture Mandates
- **Logic Separation**: Keep API route definitions in `app/main.py` and core business logic (SSH, LiteLLM, Vaultwarden interactions) in `app/services/`.
- **Encryption First**: All sensitive configuration MUST be stored via `app/database.py` which handles AES encryption at rest. NEVER use plain environment variables for persistent secrets.
- **Subprocess Safety**: When calling `bw` or `ssh-keygen`, always use `subprocess.run` with `capture_output=True` and avoid `shell=True` to prevent injection.

## 🔒 Security Mandates
- **Vaultwarden Types**: Use native `type: 5` for SSH keys. Use `type: 1` (Login) with custom fields of `type: 1` (Hidden) for all other sensitive keys.
- **Zero Hardcoded Secrets**: Do not hardcode API keys or passwords in the source. Use the `/setup` flow to populate the encrypted SQLite database.
- **Git Safety**: Ensure the `data/` directory and `__pycache__` are always ignored by `.gitignore`.

## 🐍 Development Workflow
- **Dependency Management**: Add new dependencies to `requirements.txt`.
- **Branching**: All new features must be developed on branches (e.g., `feat/my-feature`).
- **Versioning**: Bump the `VERSION` file for every merge to `main`.
- **Testing**: Add unit tests in `tests/` for any new service logic.
