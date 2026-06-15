import os
import httpx

LITELLM_API_URL = os.getenv("LITELLM_API_URL", "http://litellm:4000")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")

async def generate_virtual_key(key_alias: str, models: list = None):
    """Generates a virtual key in LiteLLM."""
    if not LITELLM_MASTER_KEY:
        raise Exception("LITELLM_MASTER_KEY environment variable is not set")

    headers = {
        "Authorization": f"Bearer {LITELLM_MASTER_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {"key_alias": key_alias}
    if models:
        payload["models"] = models

    async with httpx.AsyncClient() as client:
        # LiteLLM endpoint to generate keys
        response = await client.post(
            f"{LITELLM_API_URL}/key/generate",
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
