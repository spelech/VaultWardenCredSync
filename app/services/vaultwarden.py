import subprocess
import json
import os
import tempfile
from datetime import datetime
from typing import List, Dict
import httpx
import time
from app.database import get_secret, set_secret

class BitwardenDaemon:
    _process = None
    _port = 8087
    _host = "127.0.0.1"

    @classmethod
    def get_url(cls, path: str = "") -> str:
        return f"http://{cls._host}:{cls._port}{path}"

    @classmethod
    def is_running(cls) -> bool:
        return cls._process is not None and cls._process.poll() is None

    @classmethod
    def ensure_authenticated(cls):
        env = os.environ.copy()
        env["PATH"] = "/home/steve/.nvm/versions/node/v22.17.0/bin:" + env.get("PATH", "")
        status_proc = subprocess.run(["bw", "status"], env=env, capture_output=True, text=True)
        if status_proc.returncode == 0:
            try:
                status_data = json.loads(status_proc.stdout)
                status = status_data.get("status")
                if status == "unauthenticated":
                    url = get_secret("VAULTWARDEN_URL")
                    client_id = get_secret("VAULTWARDEN_CLIENT_ID")
                    client_secret = get_secret("VAULTWARDEN_CLIENT_SECRET")
                    if url and client_id and client_secret:
                        print("INFO: Bitwarden CLI is unauthenticated. Logging in...")
                        subprocess.run(["bw", "config", "server", url], env=env, capture_output=True)
                        login_env = env.copy()
                        login_env["BW_CLIENTID"] = client_id
                        login_env["BW_CLIENTSECRET"] = client_secret
                        subprocess.run(["bw", "login", "--apikey"], env=login_env, capture_output=True)
            except Exception as e:
                print(f"WARNING: Failed to check/perform Bitwarden authentication: {e}")

    @classmethod
    def start(cls):
        if cls.is_running():
            return
        
        cls.ensure_authenticated()
        
        print(f"INFO: Starting Bitwarden daemon on {cls._host}:{cls._port}...")
        env = os.environ.copy()
        # Add local NVM path to env just in case it is installed under a custom node setup
        env["PATH"] = "/home/steve/.nvm/versions/node/v22.17.0/bin:" + env.get("PATH", "")
        
        cls._process = subprocess.Popen(
            ["bw", "serve", "--port", str(cls._port), "--hostname", cls._host],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # Give it a small moment to start up
        time.sleep(1.5)
        
    @classmethod
    def stop(cls):
        if cls.is_running():
            print("INFO: Stopping Bitwarden daemon...")
            cls._process.terminate()
            cls._process.wait()
            cls._process = None

    @classmethod
    def get_status(cls) -> str:
        """Returns 'locked', 'unlocked', or 'stopped'."""
        if not cls.is_running():
            return "stopped"
        try:
            r = httpx.get(cls.get_url("/status"), timeout=2.0)
            if r.status_code == 200:
                data = r.json()
                return data.get("data", {}).get("template", {}).get("status", "locked")
        except Exception as e:
            print(f"WARNING: Failed to get Bitwarden daemon status: {e}")
        return "locked"

    @classmethod
    def unlock(cls, password: str) -> bool:
        if not cls.is_running():
            cls.start()
        try:
            print("INFO: Unlocking Bitwarden vault via daemon API...")
            r = httpx.post(cls.get_url("/unlock"), json={"password": password}, timeout=10.0)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    session_key = data.get("data", {}).get("raw")
                    if session_key:
                        set_secret("BW_SESSION", session_key)
                    return True
        except Exception as e:
            print(f"ERROR: Failed to unlock vault via daemon API: {e}")
        return False

    @classmethod
    def ensure_ready(cls):
        """Ensures the daemon is running and unlocked."""
        if not cls.is_running():
            cls.start()
        
        status = cls.get_status()
        if status == "locked":
            password = get_secret("VAULTWARDEN_PASSWORD")
            if password:
                cls.unlock(password)
            else:
                raise Exception("Bitwarden vault is locked and password is not configured.")

def get_vw_env():
    session = get_secret("BW_SESSION")
    env = os.environ.copy()
    if session:
        env["BW_SESSION"] = session
    return env

def initialize_vaultwarden_session(url: str, client_id: str, client_secret: str, password: str) -> str:
    """Logs into Vaultwarden and unlocks the vault to return a session key."""
    env = os.environ.copy()
    env["PATH"] = "/home/steve/.nvm/versions/node/v22.17.0/bin:" + env.get("PATH", "")
    
    # 1. Ensure we stop the daemon first to avoid lock/session conflicts on the DB
    BitwardenDaemon.stop()
    
    # 2. Ensure we are logged out first to avoid session conflicts
    subprocess.run(["bw", "logout"], env=env, capture_output=True)
    
    # 3. Config Server
    subprocess.run(["bw", "config", "server", url], env=env, capture_output=True)
    
    # 4. Login via API keys
    env["BW_CLIENTID"] = client_id
    env["BW_CLIENTSECRET"] = client_secret
    subprocess.run(["bw", "login", "--apikey"], env=env, capture_output=True, text=True)
    
    # 5. Unlock with password
    unlock_proc = subprocess.run(["bw", "unlock", password, "--raw"], env=env, capture_output=True, text=True)
    if unlock_proc.returncode != 0:
        error_msg = unlock_proc.stderr if unlock_proc.stderr else "Unknown unlock failure"
        raise Exception(f"Failed to unlock Vaultwarden: {error_msg}")
        
    session_token = unlock_proc.stdout.strip()
    
    # Start the daemon back up and unlock it with the password
    BitwardenDaemon.start()
    BitwardenDaemon.unlock(password)
    
    return session_token

def ensure_session():
    """Checks if current session is valid, if not, attempts to re-authenticate."""
    BitwardenDaemon.ensure_ready()
    return {}

def run_bw_command(cmd_list, env=None):
    """Fallback to run a Bitwarden CLI command directly."""
    if not env:
        BitwardenDaemon.ensure_ready()
        session = get_secret("BW_SESSION")
        env = os.environ.copy()
        env["PATH"] = "/home/steve/.nvm/versions/node/v22.17.0/bin:" + env.get("PATH", "")
        if session:
            env["BW_SESSION"] = session
    result = subprocess.run(["bw"] + cmd_list, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        error_msg = f"bw command {cmd_list} failed with exit code {result.returncode}. Stderr: {result.stderr}"
        print(f"ERROR: {error_msg}")
        raise Exception(error_msg)
    return result.stdout

def get_folders():
    """Fetch all folders from Vaultwarden."""
    BitwardenDaemon.ensure_ready()
    
    # Run sync to ensure latest folders
    try:
        httpx.post(BitwardenDaemon.get_url("/sync"), timeout=15.0)
    except Exception as e:
        print(f"WARNING: Sync failed: {e}")
        
    r = httpx.get(BitwardenDaemon.get_url("/list/object/folders"), timeout=10.0)
    if r.status_code != 200:
        raise Exception(f"Failed to fetch folders: {r.text}")
    return r.json().get("data", {}).get("data", [])

def get_existing_ssh_keys():
    """Fetch all native SSH Key items from Vaultwarden."""
    BitwardenDaemon.ensure_ready()
    
    r = httpx.get(BitwardenDaemon.get_url("/list/object/items"), timeout=10.0)
    if r.status_code != 200:
        raise Exception(f"Failed to fetch items: {r.text}")
    items = r.json().get("data", {}).get("data", [])
    return [i.get("name") for i in items if i.get("type") == 5]

def get_litellm_keys_from_vault():
    """Fetch all LiteLLM keys stored in the vault."""
    BitwardenDaemon.ensure_ready()
    folder_id = get_secret("LITELLM_FOLDER_ID")
    
    url = BitwardenDaemon.get_url("/list/object/items")
    r = httpx.get(url, timeout=10.0)
    if r.status_code != 200:
        raise Exception(f"Failed to fetch items: {r.text}")
    items = r.json().get("data", {}).get("data", [])
    
    keys = []
    for item in items:
        if folder_id and item.get("folderId") != folder_id:
            continue
        # Support both Login (1) and Secure Note (2) types for LiteLLM keys
        if item.get("type") in [1, 2] and item.get("name", "").startswith("LiteLLM:"):
            fields = item.get("fields", [])
            key_data = {
                "name": item.get("name").replace("LiteLLM: ", ""),
                "key": None,
                "alias": None,
                "user_id": None,
                "team_id": None,
                "max_budget": None,
                "budget_duration": None,
                "key_type": "api"
            }
            for f in fields:
                name = f.get("name")
                val = f.get("value")
                if name == "Virtual Key": key_data["key"] = val
                elif name == "Alias": key_data["alias"] = val
                elif name == "Owned By": key_data["user_id"] = val
                elif name == "Team ID": key_data["team_id"] = val
                elif name == "Max Budget": key_data["max_budget"] = float(val) if val else None
                elif name == "Budget Duration": key_data["budget_duration"] = val
                elif name == "Key Type": key_data["key_type"] = val
            
            if key_data["key"] and key_data["alias"]:
                keys.append(key_data)
    return keys

def get_item_by_name(name: str, item_type: int = None):
    """Finds an item by exact name and optional type, returning its ID."""
    BitwardenDaemon.ensure_ready()
    
    url = BitwardenDaemon.get_url("/list/object/items")
    r = httpx.get(url, params={"search": name}, timeout=10.0)
    if r.status_code != 200:
        raise Exception(f"Failed to search items: {r.text}")
    items = r.json().get("data", {}).get("data", [])
    
    for item in items:
        if item.get("name") == name:
            if item_type is None or item.get("type") == item_type:
                return item.get("id")
    return None

def add_audit_tags(fields: List[Dict]):
    """Appends audit tags to the custom fields list."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields.append({"name": "Provisioned By", "value": "QuickCreds", "type": 0})
    fields.append({"name": "Provision Date", "value": timestamp, "type": 0})
    return fields

def create_ssh_key_item(name: str, private_key: str, public_key: str, fingerprint: str, folder_id: str = None, item_id: str = None):
    """Creates or overwrites a native SSH Key item (type 5) in Vaultwarden."""
    BitwardenDaemon.ensure_ready()
    fields = add_audit_tags([])

    item = None
    if item_id:
        try:
            r = httpx.get(BitwardenDaemon.get_url(f"/object/item/{item_id}"), timeout=5.0)
            if r.status_code == 200:
                item = r.json().get("data")
                item["name"] = name
                item["sshKey"] = {
                    "privateKey": private_key, 
                    "publicKey": public_key,
                    "keyFingerprint": fingerprint
                }
                if folder_id:
                    item["folderId"] = folder_id
                
                # Merge or replace audit fields
                existing_fields = item.get("fields", [])
                existing_fields = [f for f in existing_fields if f.get("name") not in ["Provisioned By", "Provision Date"]]
                item["fields"] = existing_fields + fields
        except Exception as e:
            print(f"WARNING: Failed to fetch existing item {item_id} for update: {e}")
            item_id = None

    if not item:
        r_temp = httpx.get(BitwardenDaemon.get_url("/object/template/item"), timeout=5.0)
        if r_temp.status_code != 200:
            raise Exception("Failed to retrieve item template from daemon")
        item = r_temp.json().get("data", {}).get("template")
        
        item["type"] = 5
        item["name"] = name
        if folder_id:
            item["folderId"] = folder_id
        item["fields"] = fields
        item["sshKey"] = {
            "privateKey": private_key,
            "publicKey": public_key,
            "keyFingerprint": fingerprint
        }

    if item_id:
        url = BitwardenDaemon.get_url(f"/object/item/{item_id}")
        r = httpx.put(url, json=item, timeout=10.0)
    else:
        url = BitwardenDaemon.get_url("/object/item")
        r = httpx.post(url, json=item, timeout=10.0)

    if r.status_code != 200:
        raise Exception(f"Failed to save SSH Key item via daemon: {r.text}")
    return r.json().get("data")

def create_secure_note_item(name: str, fields: List[Dict] = None, folder_id: str = None, item_id: str = None):
    """Creates or overwrites a Secure Note item (type 2) in Vaultwarden."""
    BitwardenDaemon.ensure_ready()
    audit_fields = add_audit_tags([])
    if fields is None:
        fields = []

    item = None
    if item_id:
        try:
            r = httpx.get(BitwardenDaemon.get_url(f"/object/item/{item_id}"), timeout=5.0)
            if r.status_code == 200:
                item = r.json().get("data")
                item["name"] = name
                existing_fields = item.get("fields", [])
                existing_fields = [f for f in existing_fields if f.get("name") not in ["Provisioned By", "Provision Date"]]
                item["fields"] = fields + existing_fields + audit_fields
                if folder_id:
                    item["folderId"] = folder_id
        except Exception as e:
            print(f"WARNING: Failed to fetch existing secure note {item_id} for update: {e}")
            item_id = None

    if not item:
        r_temp = httpx.get(BitwardenDaemon.get_url("/object/template/item"), timeout=5.0)
        item = r_temp.json().get("data", {}).get("template")
        item["type"] = 2
        item["name"] = name
        
        r_sn = httpx.get(BitwardenDaemon.get_url("/object/template/item.secureNote"), timeout=5.0)
        item["secureNote"] = r_sn.json().get("data", {}).get("template")
        item["fields"] = fields + audit_fields
        if folder_id:
            item["folderId"] = folder_id

    if item_id:
        url = BitwardenDaemon.get_url(f"/object/item/{item_id}")
        r = httpx.put(url, json=item, timeout=10.0)
    else:
        url = BitwardenDaemon.get_url("/object/item")
        r = httpx.post(url, json=item, timeout=10.0)

    if r.status_code != 200:
        raise Exception(f"Failed to save Secure Note item via daemon: {r.text}")
    return r.json().get("data")

def create_secure_login(name: str, username: str = None, fields: List[Dict] = None, folder_id: str = None, item_id: str = None):
    """Creates or overwrites a login item in Vaultwarden."""
    BitwardenDaemon.ensure_ready()
    audit_fields = add_audit_tags([])
    if fields is None:
        fields = []

    item = None
    if item_id:
        try:
            r = httpx.get(BitwardenDaemon.get_url(f"/object/item/{item_id}"), timeout=5.0)
            if r.status_code == 200:
                item = r.json().get("data")
                item["name"] = name
                existing_fields = item.get("fields", [])
                existing_fields = [f for f in existing_fields if f.get("name") not in ["Provisioned By", "Provision Date"]]
                item["fields"] = fields + existing_fields + audit_fields
                if folder_id:
                    item["folderId"] = folder_id
                if username:
                    if "login" not in item or not item["login"]:
                        r_login = httpx.get(BitwardenDaemon.get_url("/object/template/item.login"), timeout=5.0)
                        item["login"] = r_login.json().get("data", {}).get("template")
                    item["login"]["username"] = username
        except Exception as e:
            print(f"WARNING: Failed to fetch existing login {item_id} for update: {e}")
            item_id = None

    if not item:
        r_temp = httpx.get(BitwardenDaemon.get_url("/object/template/item"), timeout=5.0)
        item = r_temp.json().get("data", {}).get("template")
        item["type"] = 1
        item["name"] = name
        
        r_login = httpx.get(BitwardenDaemon.get_url("/object/template/item.login"), timeout=5.0)
        item["login"] = r_login.json().get("data", {}).get("template")
        if username:
            item["login"]["username"] = username
        item["fields"] = fields + audit_fields
        if folder_id:
            item["folderId"] = folder_id

    if item_id:
        url = BitwardenDaemon.get_url(f"/object/item/{item_id}")
        r = httpx.put(url, json=item, timeout=10.0)
    else:
        url = BitwardenDaemon.get_url("/object/item")
        r = httpx.post(url, json=item, timeout=10.0)

    if r.status_code != 200:
        raise Exception(f"Failed to save Login item via daemon: {r.text}")
    return r.json().get("data")

def add_registered_host_to_ssh_key(name: str, host: str):
    """Appends a host to the 'Registered Hosts' custom field of the SSH key item."""
    BitwardenDaemon.ensure_ready()
    item_id = get_item_by_name(name, item_type=5)
    if not item_id:
        return
        
    try:
        r = httpx.get(BitwardenDaemon.get_url(f"/object/item/{item_id}"), timeout=5.0)
        if r.status_code != 200:
            return
        item = r.json().get("data")
        
        fields = item.get("fields", [])
        registered_field = None
        for f in fields:
            if f.get("name") == "Registered Hosts":
                registered_field = f
                break
                
        if registered_field:
            hosts = [h.strip() for h in registered_field.get("value", "").split(",") if h.strip()]
            if host not in hosts:
                hosts.append(host)
                registered_field["value"] = ", ".join(hosts)
        else:
            fields.append({"name": "Registered Hosts", "value": host, "type": 0})
            
        item["fields"] = fields
        
        url = BitwardenDaemon.get_url(f"/object/item/{item_id}")
        httpx.put(url, json=item, timeout=10.0)
    except Exception as e:
        print(f"WARNING: Could not update Registered Hosts in Vaultwarden: {e}")

def get_ssh_key_item(name: str):
    """Fetches details of an existing SSH Key item by name."""
    BitwardenDaemon.ensure_ready()
    item_id = get_item_by_name(name, item_type=5)
    if not item_id:
        raise Exception(f"SSH Key item '{name}' not found in vault.")
        
    r = httpx.get(BitwardenDaemon.get_url(f"/object/item/{item_id}"), timeout=5.0)
    if r.status_code != 200:
        raise Exception(f"Failed to fetch SSH Key item: {r.text}")
    item = r.json().get("data")
    
    ssh_key_data = item.get("sshKey", {})
    return {
        "name": name,
        "private_key": ssh_key_data.get("privateKey", ""),
        "public_key": ssh_key_data.get("publicKey", ""),
        "fingerprint": ssh_key_data.get("keyFingerprint", ""),
        "registered_hosts": next((f.get("value") for f in item.get("fields", []) if f.get("name") == "Registered Hosts"), "")
    }



