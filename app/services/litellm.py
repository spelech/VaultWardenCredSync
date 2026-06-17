import httpx
from app.database import get_secret

async def generate_virtual_key(
    key_alias: str, 
    user_id: str = None, 
    team_id: str = None, 
    max_budget: float = None,
    models: list = None,
    key_type: str = "api"
):
    """Generates a virtual key in LiteLLM following official API schema."""
    litellm_api_url = get_secret("LITELLM_API_URL")
    litellm_master_key = get_secret("LITELLM_MASTER_KEY")
    
    if not litellm_master_key or not litellm_api_url:
        raise Exception("LiteLLM is not configured properly in setup.")

    headers = {
        "Authorization": f"Bearer {litellm_master_key}",
        "Content-Type": "application/json"
    }
    
    payload = {"key_alias": key_alias}
    if user_id: payload["user_id"] = user_id
    if team_id: payload["team_id"] = team_id
    if max_budget is not None: payload["max_budget"] = max_budget
    if models: payload["models"] = models

    # Restore Key Type logic
    if key_type == "mgmt":
        payload["user_role"] = "proxy_admin"
        payload["allowed_routes"] = ["/key/*", "/user/*", "/team/*", "/model/*", "/health/*", "/config/*", "/ui/*"]
    elif key_type == "both":
        payload["user_role"] = "proxy_admin"
    else:
        payload["user_role"] = "internal_user"

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
            "user_id": user_id,
            "team_id": team_id,
            "key_type": key_type,
            "models": data.get("models", []),
            "key_name": data.get("key_name")
        }

async def import_litellm_key(
    key: str,
    key_alias: str,
    user_id: str = None,
    team_id: str = None,
    max_budget: float = None,
    models: list = None,
    key_type: str = "api"
):
    """Imports an existing key back into LiteLLM (used for resync)."""
    litellm_api_url = get_secret("LITELLM_API_URL")
    litellm_master_key = get_secret("LITELLM_MASTER_KEY")
    
    if not litellm_master_key or not litellm_api_url:
        raise Exception("LiteLLM is not configured properly.")

    headers = {
        "Authorization": f"Bearer {litellm_master_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "key": key,
        "key_alias": key_alias
    }
    if user_id: payload["user_id"] = user_id
    if team_id: payload["team_id"] = team_id
    if max_budget is not None: payload["max_budget"] = max_budget
    if models: payload["models"] = models

    if key_type == "mgmt":
        payload["user_role"] = "proxy_admin"
        payload["allowed_routes"] = ["/key/*", "/user/*", "/team/*", "/model/*", "/health/*", "/config/*", "/ui/*"]
    elif key_type == "both":
        payload["user_role"] = "proxy_admin"
    else:
        payload["user_role"] = "internal_user"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{litellm_api_url}/key/generate",
            headers=headers,
            json=payload,
            timeout=10.0
        )
        
        if response.status_code != 200:
            # If it already exists, that's fine for an import
            if "already exists" in response.text.lower():
                return {"status": "exists", "key_alias": key_alias}
            raise Exception(f"Failed to import LiteLLM key: {response.text}")
            
        return {"status": "imported", "key_alias": key_alias}

async def get_litellm_teams():
    """Fetch all teams from LiteLLM."""
    url = get_secret("LITELLM_API_URL")
    key = get_secret("LITELLM_MASTER_KEY")
    if not url or not key: return []
    
    headers = {"Authorization": f"Bearer {key}"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{url}/team/list", headers=headers, timeout=5.0)
            if response.status_code == 200:
                res_data = response.json()
                # Handle both dict and list responses
                teams = []
                if isinstance(res_data, list):
                    teams = res_data
                elif isinstance(res_data, dict):
                    teams = res_data.get("teams", [])
                
                # Normalize to dicts
                return [t if isinstance(t, dict) else {"team_id": t, "team_alias": t} for t in teams]
        except Exception as e:
            print(f"DEBUG: Failed to fetch LiteLLM teams: {e}")
        return []

async def get_litellm_users():
    """Fetch all users from LiteLLM."""
    url = get_secret("LITELLM_API_URL")
    key = get_secret("LITELLM_MASTER_KEY")
    if not url or not key: return []
    
    headers = {"Authorization": f"Bearer {key}"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{url}/user/list", headers=headers, timeout=5.0)
            if response.status_code == 200:
                res_data = response.json()
                users = []
                if isinstance(res_data, list):
                    users = res_data
                elif isinstance(res_data, dict):
                    users = res_data.get("users", [])
                
                # Normalize to dicts
                return [u if isinstance(u, dict) else {"user_id": u, "user_role": "unknown"} for u in users]
        except Exception as e:
            print(f"DEBUG: Failed to fetch LiteLLM users: {e}")
        return []

async def get_litellm_models():
    """Fetch all models from LiteLLM."""
    url = get_secret("LITELLM_API_URL")
    key = get_secret("LITELLM_MASTER_KEY")
    if not url or not key: return []
    
    headers = {"Authorization": f"Bearer {key}"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{url}/models", headers=headers, timeout=5.0)
            if response.status_code == 200:
                res_data = response.json()
                models = []
                if isinstance(res_data, list):
                    models = res_data
                elif isinstance(res_data, dict):
                    models = res_data.get("data", [])
                return models
        except Exception as e:
            print(f"DEBUG: Failed to fetch LiteLLM models: {e}")
        return []

async def get_litellm_keys():
    """Fetch all virtual key metadata from LiteLLM."""
    url = get_secret("LITELLM_API_URL")
    key = get_secret("LITELLM_MASTER_KEY")
    if not url or not key: return []
    
    headers = {"Authorization": f"Bearer {key}"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{url}/key/list", headers=headers, timeout=5.0)
            if response.status_code == 200:
                res_data = response.json()
                keys_list = []
                if isinstance(res_data, list):
                    keys_list = res_data
                elif isinstance(res_data, dict):
                    keys_list = res_data.get("keys", [])
                
                # Return list of dicts with token and alias
                results = []
                for k in keys_list:
                    if isinstance(k, dict):
                        results.append({
                            "token": k.get("token") or k.get("key"), 
                            "alias": k.get("key_alias")
                        })
                    elif isinstance(k, str):
                        # If LiteLLM only returns IDs, we must fetch info for each
                        try:
                            info_res = await client.get(f"{url}/key/info?key={k}", headers=headers, timeout=2.0)
                            if info_res.status_code == 200:
                                info_data = info_res.json()
                                results.append({
                                    "token": k,
                                    "alias": info_data.get("info", {}).get("key_alias")
                                })
                        except:
                            continue
                return results
        except Exception as e:
            print(f"DEBUG: Failed to fetch LiteLLM keys: {e}")
        return []
