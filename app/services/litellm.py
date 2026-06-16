import httpx
from app.database import get_secret

async def generate_virtual_key(
    key_alias: str, 
    models: list = None, 
    user_role: str = None, 
    team_id: str = None, 
    max_budget: float = None
):
    """Generates a virtual key in LiteLLM with advanced options."""
    litellm_api_url = get_secret("LITELLM_API_URL")
    litellm_master_key = get_secret("LITELLM_MASTER_KEY")
    
    if not litellm_master_key or not litellm_api_url:
        raise Exception("LiteLLM is not configured properly in setup.")

    headers = {
        "Authorization": f"Bearer {litellm_master_key}",
        "Content-Type": "application/json"
    }
    
    payload = {"key_alias": key_alias}
    if models:
        payload["models"] = models
    if user_role:
        payload["user_role"] = user_role
    if team_id:
        payload["team_id"] = team_id
    if max_budget is not None:
        payload["max_budget"] = max_budget

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{litellm_api_url}/key/generate",
            headers=headers,
            json=payload,
            timeout=10.0
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to generate LiteLLM key: {response.text}")
            
        data = response.json()
        
        return {
            "key": data.get("key"),
            "key_alias": key_alias,
            "models": data.get("models", []),
            "key_name": data.get("key_name")
        }
