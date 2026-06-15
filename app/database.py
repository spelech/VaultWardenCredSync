import sqlite3
import os
from pathlib import Path
from cryptography.fernet import Fernet

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "portal.db"
KEY_PATH = DATA_DIR / "master.key"

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

def get_fernet():
    if not os.path.exists(KEY_PATH):
        key = Fernet.generate_key()
        with open(KEY_PATH, "wb") as f:
            f.write(key)
    else:
        with open(KEY_PATH, "rb") as f:
            key = f.read()
    return Fernet(key)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS secrets (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()

def set_secret(key: str, value: str):
    f = get_fernet()
    encrypted_value = f.encrypt(value.encode()).decode()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO secrets (key, value) VALUES (?, ?)", 
        (key, encrypted_value)
    )
    conn.commit()
    conn.close()

def get_secret(key: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM secrets WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        f = get_fernet()
        return f.decrypt(row[0].encode()).decode()
    return None

def is_setup_complete() -> bool:
    # We consider setup complete if Vaultwarden URL is configured
    return get_secret("VAULTWARDEN_URL") is not None

# Initialize database on load
init_db()
