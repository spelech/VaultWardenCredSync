import hmac
import os
from fastmcp import FastMCP
from fastmcp.server.auth import OAuthProxy
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.providers.jwt import JWTVerifier

from app.services.ssh import generate_ssh_keypair, push_ssh_key_to_host
from app.services.litellm import generate_virtual_key
from app.services.vaultwarden import create_ssh_key_item, create_secure_note_item
from app.database import get_secret

EXTERNAL_OIDC_URL = "https://sso.wileyriley.com"
INTERNAL_OIDC_URL = "http://pocketid:1411"

token_verifier = JWTVerifier(
    jwks_uri=f"{INTERNAL_OIDC_URL}/.well-known/jwks.json",
    issuer=EXTERNAL_OIDC_URL,
    audience="quickcreds-mcp"
)


class GatewayOAuthProxy(OAuthProxy):
    """OAuthProxy that also accepts a configured service Bearer key (MCP_API_KEY) for MCG."""

    async def verify_token(self, token: str) -> AccessToken | None:
        api_key = os.getenv("MCP_API_KEY", "").strip()
        if api_key and hmac.compare_digest(token, api_key):
            return AccessToken(
                token=token,
                client_id="mcg-gateway",
                scopes=["mcp"],
            )
        return await super().verify_token(token)


auth = GatewayOAuthProxy(
    upstream_authorization_endpoint=f"{EXTERNAL_OIDC_URL}/api/oidc/authorize",
    upstream_token_endpoint=f"{INTERNAL_OIDC_URL}/api/oidc/token",
    upstream_client_id=os.getenv("MCP_CLIENT_ID", "quickcreds-mcp"),
    upstream_client_secret=os.getenv("MCP_CLIENT_SECRET", "dummy-secret"), # Ensure safe fallback or require
    token_verifier=token_verifier,
    base_url="https://quickcreds.wileyriley.com",
    redirect_path="/mcp/auth/callback",
)

mcp = FastMCP("QuickCreds", auth=auth)

@mcp.tool
async def create_and_sync_ssh_key(name: str, comment: str = "", host_to_push: str = None, push_username: str = None, push_password: str = None) -> str:
    """Generates a new SSH keypair and syncs it to Vaultwarden. Optionally pushes the public key to a remote host."""
    # Generate Key
    keys = generate_ssh_keypair(key_name=name, comment=comment)
    folder_id = get_secret("SSH_FOLDER_ID")
    
    # Sync
    create_ssh_key_item(name=name, private_key=keys["private_key"], public_key=keys["public_key"], fingerprint=keys["fingerprint"], folder_id=folder_id)
    
    # Push if requested
    if host_to_push and push_username:
        push_ssh_key_to_host(host=host_to_push, username=push_username, public_key=keys["public_key"], password=push_password)
    
    return f"Successfully generated and synced SSH Key '{name}'."

@mcp.tool
async def create_and_sync_litellm_key(alias: str, max_budget: float = None, team_id: str = None) -> str:
    """Generates a new LiteLLM virtual key and syncs it to Vaultwarden."""
    # Generate Key
    key_data = await generate_virtual_key(key_alias=alias, max_budget=max_budget, team_id=team_id)
    folder_id = get_secret("LITELLM_FOLDER_ID")
    
    # Sync
    fields = [
        {"name": "Virtual Key", "value": key_data["key"], "type": 1},
        {"name": "Alias", "value": alias, "type": 0},
        {"name": "Key Type", "value": "api", "type": 0}
    ]
    if team_id: fields.append({"name": "Team ID", "value": team_id, "type": 0})
    if max_budget: fields.append({"name": "Max Budget", "value": str(max_budget), "type": 0})
    
    create_secure_note_item(name=f"LiteLLM: {alias}", fields=fields, folder_id=folder_id)
    
    return f"Successfully generated and synced LiteLLM Key '{alias}'."
