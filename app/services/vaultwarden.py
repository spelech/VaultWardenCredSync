import subprocess
import json
import os
import tempfile
from typing import List, Dict
from app.database import get_secret

def get_vw_env():
    session = get_secret("BW_SESSION")
    env = os.environ.copy()
    if session:
        env["BW_SESSION"] = session
    return env

def initialize_vaultwarden_session(url: str, client_id: str, client_secret: str, password: str) -> str:
    """Logs into Vaultwarden and unlocks the vault to return a session key."""
    env = os.environ.copy()
    
    # 1. Config Server
    subprocess.run(["bw", "config", "server", url], env=env, capture_output=True, check=True)
    
    # 2. Login via API keys
    env["BW_CLIENTID"] = client_id
    env["BW_CLIENTSECRET"] = client_secret
    login_proc = subprocess.run(["bw", "login", "--apikey"], env=env, capture_output=True, text=True)
    # Note: If already logged in, it returns a non-zero code. We can ignore failures here and just try to unlock.
    
    # 3. Unlock with password
    unlock_proc = subprocess.run(["bw", "unlock", password, "--raw"], env=env, capture_output=True, text=True)
    if unlock_proc.returncode != 0:
        raise Exception(f"Failed to unlock Vaultwarden: {unlock_proc.stderr}")
        
    return unlock_proc.stdout.strip()

def run_bw_command(cmd_list, env=None):
    """Run a Bitwarden CLI command and return JSON."""
    vw_url = get_secret("VAULTWARDEN_URL")
    if vw_url:
        subprocess.run(["bw", "config", "server", vw_url], env=env, capture_output=True)
        
    result = subprocess.run(["bw"] + cmd_list, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"bw command failed: {result.stderr}")
    return result.stdout

def create_secure_login(name: str, username: str = None, fields: List[Dict] = None, folder_id: str = None):
    """Creates a login item in Vaultwarden with custom fields using bw cli."""
    env = get_vw_env()
    if not env.get("BW_SESSION"):
        print(f"Warning: BW_SESSION not set. Simulating Vaultwarden sync for: {name}")
        return {"simulated": True, "name": name, "status": "success", "fields": fields}
    
    # Get template
    template_str = run_bw_command(["get", "template", "item"], env=env)
    item = json.loads(template_str)
    
    item["type"] = 1 # 1 = Login
    item["name"] = name
    
    # Setup login struct
    login_template_str = run_bw_command(["get", "template", "item.login"], env=env)
    login_item = json.loads(login_template_str)
    if username:
        login_item["username"] = username
    item["login"] = login_item
    
    # Add custom fields
    if fields:
        item["fields"] = fields
        
    if folder_id:
        item["folderId"] = folder_id
        
    # Encode item
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        json.dump(item, f)
        temp_name = f.name
        
    try:
        with open(temp_name, 'r') as f:
            encoded_str = subprocess.run(["bw", "encode"], stdin=f, env=env, capture_output=True, text=True, check=True).stdout
            
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f_enc:
            f_enc.write(encoded_str)
            temp_enc_name = f_enc.name
            
        try:
            with open(temp_enc_name, 'r') as f_enc_read:
                create_result = subprocess.run(["bw", "create", "item"], stdin=f_enc_read, env=env, capture_output=True, text=True, check=True).stdout
                return json.loads(create_result)
        finally:
            os.remove(temp_enc_name)
    finally:
        os.remove(temp_name)
