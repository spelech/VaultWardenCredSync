import subprocess
import json
import os
import tempfile
from datetime import datetime
from typing import List, Dict
from app.database import get_secret, set_secret

def get_vw_env():
    session = get_secret("BW_SESSION")
    env = os.environ.copy()
    if session:
        env["BW_SESSION"] = session
    return env

def initialize_vaultwarden_session(url: str, client_id: str, client_secret: str, password: str) -> str:
    """Logs into Vaultwarden and unlocks the vault to return a session key."""
    env = os.environ.copy()
    
    # 1. Ensure we are logged out first to avoid session conflicts
    subprocess.run(["bw", "logout"], env=env, capture_output=True)
    
    # 2. Config Server
    subprocess.run(["bw", "config", "server", url], env=env, capture_output=True)
    
    # 3. Login via API keys
    env["BW_CLIENTID"] = client_id
    env["BW_CLIENTSECRET"] = client_secret
    subprocess.run(["bw", "login", "--apikey"], env=env, capture_output=True, text=True)
    
    # 4. Unlock with password
    unlock_proc = subprocess.run(["bw", "unlock", password, "--raw"], env=env, capture_output=True, text=True)
    if unlock_proc.returncode != 0:
        error_msg = unlock_proc.stderr if unlock_proc.stderr else "Unknown unlock failure"
        raise Exception(f"Failed to unlock Vaultwarden: {error_msg}")
        
    session_token = unlock_proc.stdout.strip()
    return session_token

def ensure_session():
    """Checks if current session is valid, if not, attempts to re-authenticate."""
    env = get_vw_env()
    
    # Test session with a simple command
    if env.get("BW_SESSION"):
        test_proc = subprocess.run(["bw", "list", "folders"], env=env, capture_output=True, text=True)
        if test_proc.returncode == 0:
            return env

    # Session invalid or missing, attempt full re-auth
    print("DEBUG: Vaultwarden session invalid or missing. Attempting auto-recovery...")
    url = get_secret("VAULTWARDEN_URL")
    client_id = get_secret("VAULTWARDEN_CLIENT_ID")
    client_secret = get_secret("VAULTWARDEN_CLIENT_SECRET")
    password = get_secret("VAULTWARDEN_PASSWORD")
    
    if not all([url, client_id, client_secret, password]):
        raise Exception("Vaultwarden session expired and credentials missing for recovery. Please re-run setup.")
        
    try:
        new_session = initialize_vaultwarden_session(url, client_id, client_secret, password)
        set_secret("BW_SESSION", new_session)
        env = os.environ.copy()
        env["BW_SESSION"] = new_session
        return env
    except Exception as e:
        print(f"ERROR: Vaultwarden recovery failed: {e}")
        raise e

def run_bw_command(cmd_list, env=None):
    """Run a Bitwarden CLI command and return JSON."""
    if not env:
        env = ensure_session()
        
    # OPTIMIZATION: Removed redundant 'bw config server' call here.
    # It adds ~1s latency and is already handled during setup/session initialization.
        
    result = subprocess.run(["bw"] + cmd_list, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        error_msg = f"bw command {cmd_list} failed with exit code {result.returncode}. Stderr: {result.stderr}"
        print(f"ERROR: {error_msg}")
        raise Exception(error_msg)
    return result.stdout

def get_folders():
    """Fetch all folders from Vaultwarden."""
    env = ensure_session()
    
    # Run sync to ensure latest folders
    subprocess.run(["bw", "sync"], env=env, capture_output=True)
    
    folders_str = run_bw_command(["list", "folders"], env=env)
    return json.loads(folders_str)

def get_existing_ssh_keys():
    """Fetch all native SSH Key items from Vaultwarden."""
    env = ensure_session()
    
    # List items with type 5
    items_str = run_bw_command(["list", "items", "--search", ""], env=env)
    items = json.loads(items_str)
    return [i.get("name") for i in items if i.get("type") == 5]

def get_item_by_name(name: str, item_type: int = None):
    """Finds an item by exact name and optional type, returning its ID."""
    env = ensure_session()
    
    items_str = run_bw_command(["list", "items", "--search", name], env=env)
    items = json.loads(items_str)
    
    for item in items:
        if item.get("name") == name:
            if item_type is None or item.get("type") == item_type:
                return item.get("id")
    return None

def add_audit_tags(fields: List[Dict]):
    """Appends hidden audit tags to the custom fields list."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields.append({"name": "Provisioned By", "value": "QuickCreds", "type": 1})
    fields.append({"name": "Provision Date", "value": timestamp, "type": 1})
    return fields

def create_ssh_key_item(name: str, private_key: str, public_key: str, fingerprint: str, folder_id: str = None, item_id: str = None):
    """Creates or overwrites a native SSH Key item (type 5) in Vaultwarden."""
    env = ensure_session()

    fields = add_audit_tags([])

    if item_id:
        try:
            current_item_str = run_bw_command(["get", "item", item_id], env=env)
            item = json.loads(current_item_str)
            item["name"] = name
            item["sshKey"] = {
                "privateKey": private_key, 
                "publicKey": public_key,
                "fingerprint": fingerprint
            }
            if folder_id: item["folderId"] = folder_id
            
            # Merge or replace audit fields
            existing_fields = item.get("fields", [])
            existing_fields = [f for f in existing_fields if f.get("name") not in ["Provisioned By", "Provision Date"]]
            item["fields"] = existing_fields + fields
        except:
            item_id = None

    if not item_id:
        item = {
            "type": 5,
            "name": name,
            "folderId": folder_id,
            "fields": fields,
            "sshKey": {
                "privateKey": private_key,
                "publicKey": public_key,
                "fingerprint": fingerprint
            }
        }
    
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        json.dump(item, f)
        temp_name = f.name
        
    try:
        with open(temp_name, 'r') as f:
            encode_proc = subprocess.run(["bw", "encode"], stdin=f, env=env, capture_output=True, text=True)
            if encode_proc.returncode != 0:
                raise Exception(f"bw encode failed: {encode_proc.stderr}")
            encoded_str = encode_proc.stdout
            
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f_enc:
            f_enc.write(encoded_str)
            temp_enc_name = f_enc.name
            
        try:
            with open(temp_enc_name, 'r') as f_enc_read:
                cmd = ["create", "item"] if not item_id else ["edit", "item", item_id]
                create_proc = subprocess.run(["bw"] + cmd, stdin=f_enc_read, env=env, capture_output=True, text=True)
                if create_proc.returncode != 0:
                    raise Exception(f"bw {cmd} failed: {create_proc.stderr}")
                return json.loads(create_proc.stdout)
        finally:
            if os.path.exists(temp_enc_name):
                os.remove(temp_enc_name)
    finally:
        if os.path.exists(temp_name):
            os.remove(temp_name)

def create_secure_note_item(name: str, fields: List[Dict] = None, folder_id: str = None, item_id: str = None):
    """Creates or overwrites a Secure Note item (type 2) in Vaultwarden."""
    env = ensure_session()
    
    audit_fields = add_audit_tags([])
    if fields is None: fields = []
    
    if item_id:
        try:
            current_item_str = run_bw_command(["get", "item", item_id], env=env)
            item = json.loads(current_item_str)
            item["name"] = name
            
            existing_fields = item.get("fields", [])
            existing_fields = [f for f in existing_fields if f.get("name") not in ["Provisioned By", "Provision Date"]]
            item["fields"] = fields + existing_fields + audit_fields
            
            if folder_id: item["folderId"] = folder_id
        except:
            item_id = None

    if not item_id:
        template_str = run_bw_command(["get", "template", "item"], env=env)
        item = json.loads(template_str)
        item["type"] = 2 # 2 = Secure Note
        item["name"] = name
        item["fields"] = fields + audit_fields
        if folder_id: item["folderId"] = folder_id
        
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        json.dump(item, f)
        temp_name = f.name
        
    try:
        with open(temp_name, 'r') as f:
            encode_proc = subprocess.run(["bw", "encode"], stdin=f, env=env, capture_output=True, text=True)
            if encode_proc.returncode != 0:
                raise Exception(f"bw encode failed: {encode_proc.stderr}")
            encoded_str = encode_proc.stdout
            
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f_enc:
            f_enc.write(encoded_str)
            temp_enc_name = f_enc.name
            
        try:
            with open(temp_enc_name, 'r') as f_enc_read:
                cmd = ["create", "item"] if not item_id else ["edit", "item", item_id]
                create_proc = subprocess.run(["bw"] + cmd, stdin=f_enc_read, env=env, capture_output=True, text=True)
                if create_proc.returncode != 0:
                    raise Exception(f"bw {cmd} failed: {create_proc.stderr}")
                return json.loads(create_proc.stdout)
        finally:
            if os.path.exists(temp_enc_name):
                os.remove(temp_enc_name)
    finally:
        if os.path.exists(temp_name):
            os.remove(temp_name)

def create_secure_login(name: str, username: str = None, fields: List[Dict] = None, folder_id: str = None, item_id: str = None):
    """Creates or overwrites a login item in Vaultwarden."""
    env = ensure_session()
    
    audit_fields = add_audit_tags([])
    if fields is None: fields = []
    
    if item_id:
        try:
            current_item_str = run_bw_command(["get", "item", item_id], env=env)
            item = json.loads(current_item_str)
            item["name"] = name
            
            # Merge fields
            existing_fields = item.get("fields", [])
            # Filter out existing audit fields to avoid duplicates on overwrite
            existing_fields = [f for f in existing_fields if f.get("name") not in ["Provisioned By", "Provision Date"]]
            item["fields"] = fields + existing_fields + audit_fields
            
            if folder_id: item["folderId"] = folder_id
            if username:
                if "login" not in item: item["login"] = {}
                item["login"]["username"] = username
        except:
            item_id = None

    if not item_id:
        template_str = run_bw_command(["get", "template", "item"], env=env)
        item = json.loads(template_str)
        item["type"] = 1 # 1 = Login
        item["name"] = name
        login_template_str = run_bw_command(["get", "template", "item.login"], env=env)
        login_item = json.loads(login_template_str)
        if username: login_item["username"] = username
        item["login"] = login_item
        item["fields"] = fields + audit_fields
        if folder_id: item["folderId"] = folder_id
        
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        json.dump(item, f)
        temp_name = f.name
        
    try:
        with open(temp_name, 'r') as f:
            encode_proc = subprocess.run(["bw", "encode"], stdin=f, env=env, capture_output=True, text=True)
            if encode_proc.returncode != 0:
                raise Exception(f"bw encode failed: {encode_proc.stderr}")
            encoded_str = encode_proc.stdout
            
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f_enc:
            f_enc.write(encoded_str)
            temp_enc_name = f_enc.name
            
        try:
            with open(temp_enc_name, 'r') as f_enc_read:
                cmd = ["create", "item"] if not item_id else ["edit", "item", item_id]
                create_proc = subprocess.run(["bw"] + cmd, stdin=f_enc_read, env=env, capture_output=True, text=True)
                if create_proc.returncode != 0:
                    raise Exception(f"bw {cmd} failed: {create_proc.stderr}")
                return json.loads(create_proc.stdout)
        finally:
            if os.path.exists(temp_enc_name):
                os.remove(temp_enc_name)
    finally:
        if os.path.exists(temp_name):
            os.remove(temp_name)
