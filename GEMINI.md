# Gemini Mandates: QuickCreds Terminal

Follow these architecture and security rules when modifying this codebase.

## 🏗️ Architecture Mandates
- **Search Optimization**: NEVER use `grep` or `ripgrep` without narrowing down to likely file types (e.g., using `include_pattern`). This is a hard mandate to minimize search time and data volume.
- **Logic Separation**: Keep API route definitions in `app/main.py` and core business logic (SSH, LiteLLM, Vaultwarden interactions) in `app/services/`.
- **Encryption First**: All sensitive configuration MUST be stored via `app/database.py` which handles AES encryption at rest. NEVER use plain environment variables for persistent secrets.
- **Subprocess Safety**: When calling `bw` or `ssh-keygen`, always use `subprocess.run` with `capture_output=True` and avoid `shell=True` to prevent injection.
- **UI Consistency**: Adhere to the QuickCreds Prussian Blue (`#031d44`) & Muted Teal (`#70a288`) palette.

## 🔒 Security Mandates
- **Vaultwarden Types**: Use native `type: 5` for SSH keys. Use `type: 1` (Login) with custom fields of `type: 1` (Hidden) for all other sensitive keys.
- **Zero Hardcoded Secrets**: Do not hardcode API keys or passwords in the source. Use the `/setup` flow to populate the encrypted SQLite database.
- **Git Safety**: Ensure the `data/` directory and `__pycache__` are always ignored by `.gitignore`.
- **Encryption Handling**: The portal uses a local key (`data/portal.key`) to encrypt the SQLite database. Ensure this key is protected.

## 🐍 Development Workflow
- **Dependency Management**: Add new dependencies to `requirements.txt`.
- **Branching Strategy**: All features and fixes MUST be developed on dedicated branches (e.g., `feat/my-feature` or `fix/my-bug`).
- **Merging Protocol**: Merge to `main` via PR or non-squash merge. **DO NOT SQUASH** on merge to preserve commit history.
- **Versioning**: The `VERSION` file MUST be bumped manually for every merge to `main`.
- **CI Efficiency**: PRs and branches run unit tests. Production image builds and deployments are triggered ONLY on merges to `main` to conserve build minutes.
- **Testing**: Add unit tests in `tests/` for any new service logic.
