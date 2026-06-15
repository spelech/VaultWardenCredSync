import subprocess
import json
import os
import tempfile

VAULTWARDEN_URL = os.getenv("VAULTWARDEN_URL", "")

def run_bw_command(cmd_list, env=None):
    """Run a Bitwarden CLI command and return JSON."""
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    
    # Configure the server url if not set
    if VAULTWARDEN_URL:
        subprocess.run(["bw", "config", "server", VAULTWARDEN_URL], env=process_env, capture_output=True)
        
    result = subprocess.run(["bw"] + cmd_list, env=process_env, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"bw command failed: {result.stderr}")
    return result.stdout

def create_secure_note(name: str, notes: str, folder_id: str = None):
    """Creates a secure note in Vaultwarden using bw cli."""
    # MVP approach: Use bw get template
    # Since bw requires session management, for this MVP we'll log it if session isn't available
    session = os.getenv("BW_SESSION")
    if not session:
        print(f"Warning: BW_SESSION not set. Simulating Vaultwarden sync for: {name}")
        return {"simulated": True, "name": name, "status": "success"}

    env = {"BW_SESSION": session}
    
    # Get template
    template_str = run_bw_command(["get", "template", "item"], env=env)
    item = json.loads(template_str)
    
    item["type"] = 2 # Secure note
    item["name"] = name
    item["notes"] = notes
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
