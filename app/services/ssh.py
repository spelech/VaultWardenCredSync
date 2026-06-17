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
        
        # Explicitly pass /dev/null as stdin to avoid any "no terminal" or "tty" prompts
        with open(os.devnull, 'rb') as devnull:
            result = subprocess.run(cmd, stdin=devnull, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to generate SSH key: {result.stderr}")
            
        # Get fingerprint
        fingerprint_cmd = ["ssh-keygen", "-l", "-f", key_path]
        fp_result = subprocess.run(fingerprint_cmd, capture_output=True, text=True)
        fingerprint = ""
        if fp_result.returncode == 0:
            # Output is usually: 256 SHA256:.... comment (ED25519)
            fingerprint = fp_result.stdout.split()[1]

        with open(key_path, "r") as f:
            private_key = f.read()
            
        with open(f"{key_path}.pub", "r") as f:
            public_key = f.read()
            
    return {"private_key": private_key, "public_key": public_key, "fingerprint": fingerprint}
