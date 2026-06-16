import subprocess
import tempfile
import os

def generate_ssh_keypair(key_name: str = "id_ssh", comment: str = "", key_type: str = "ed25519"):
    """Generates an SSH keypair (ed25519 or rsa)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = os.path.join(tmpdir, key_name)
        
        cmd = [
            "ssh-keygen",
            "-t", key_type,
            "-N", "",           # No passphrase
            "-C", comment,
            "-f", key_path,
            "-q"
        ]
        
        if key_type == "rsa":
            cmd.extend(["-b", "4096"]) # Use 4096 bit for RSA
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to generate SSH key: {result.stderr}")
            
        with open(key_path, "r") as f:
            private_key = f.read()
            
        with open(f"{key_path}.pub", "r") as f:
            public_key = f.read()
            
    return {"private_key": private_key, "public_key": public_key}
