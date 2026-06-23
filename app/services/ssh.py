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

def push_ssh_key_to_host(host: str, username: str, public_key: str, password: str = None, port: int = 22):
    """Pushes a public key to the remote host's ~/.ssh/authorized_keys file."""
    import paramiko
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(hostname=host, port=port, username=username, password=password, timeout=10)
        # Escaping single quotes in public_key to avoid shell injection
        escaped_key = public_key.replace("'", "'\\''")
        cmd = f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '{escaped_key.strip()}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            error_msg = stderr.read().decode().strip()
            raise Exception(f"SSH command failed with exit status {exit_status}: {error_msg}")
    except Exception as e:
        raise Exception(f"Failed to connect or push key: {str(e)}")
    finally:
        ssh.close()

