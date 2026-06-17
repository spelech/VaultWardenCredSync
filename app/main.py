from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path
from typing import Optional, List
import httpx
import uuid
import asyncio
from fastapi import BackgroundTasks

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.services.ssh import generate_ssh_keypair
from app.services.litellm import generate_virtual_key, get_litellm_teams, get_litellm_users, get_litellm_models, get_litellm_keys, import_litellm_key
from app.services.vaultwarden import create_secure_login, create_secure_note_item, initialize_vaultwarden_session, get_folders, create_ssh_key_item, get_existing_ssh_keys, get_item_by_name, get_litellm_keys_from_vault
from app.database import is_setup_complete, set_secret, get_secret, hash_password, verify_password

app = FastAPI(title="QuickCreds Terminal", version="0.1.0")

# Background Sync Task
async def reconcile_litellm_keys():
    """Background task to ensure all keys in Vaultwarden exist in LiteLLM."""
    while True:
        try:
            if is_setup_complete():
                print("DEBUG: Starting background LiteLLM key reconciliation...")
                vault_keys = get_litellm_keys_from_vault()
                litellm_keys = await get_litellm_keys()
                litellm_aliases = [k["alias"] for k in litellm_keys]
                
                for vk in vault_keys:
                    if vk["alias"] not in litellm_aliases:
                        print(f"INFO: Key '{vk['alias']}' missing in LiteLLM. Restoring from Vault...")
                        await import_litellm_key(
                            key=vk["key"],
                            key_alias=vk["alias"],
                            user_id=vk["user_id"],
                            team_id=vk["team_id"],
                            max_budget=vk["max_budget"],
                            key_type=vk["key_type"]
                        )
                print("DEBUG: Background reconciliation complete.")
        except Exception as e:
            print(f"ERROR: Background reconciliation failed: {e}")
            
        # Run every 30 minutes
        await asyncio.sleep(1800)

@app.on_event("startup")
async def startup_event():
    # Start reconciliation in the background
    asyncio.create_task(reconcile_litellm_keys())

# Setup Rate Limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Setup templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Read version
try:
    with open(BASE_DIR.parent / "VERSION", "r") as f:
        VERSION = f.read().strip()
except:
    VERSION = "0.0.0"

# Pydantic models for requests
class SSHGenerateRequest(BaseModel):
    name: str
    comment: Optional[str] = ""
    key_type: Optional[str] = "ed25519"

class SSHSyncRequest(BaseModel):
    name: str
    private_key: str
    public_key: str
    fingerprint: str
    overwrite: Optional[bool] = False

class LiteLLMGenerateRequest(BaseModel):
    key_alias: str
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    max_budget: Optional[float] = None
    models: Optional[List[str]] = None
    key_type: Optional[str] = "api"

class LiteLLMSyncRequest(BaseModel):
    name: str
    key: str
    alias: str
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    key_type: Optional[str] = None
    max_budget: Optional[float] = None

class ExternalCredentialRequest(BaseModel):
    name: str
    credential_data: str

class LiteLLMTestRequest(BaseModel):
    url: str
    key: str

class LoginTestRequest(BaseModel):
    vw_url: str
    vw_client_id: str
    vw_client_secret: str
    vw_password: str

class SetupRequest(BaseModel):
    litellm_url: str
    litellm_key: str
    vw_url: str
    vw_client_id: str
    vw_client_secret: str
    vw_password: str
    ssh_folder_id: Optional[str] = None
    litellm_folder_id: Optional[str] = None
    external_folder_id: Optional[str] = None

class LoginRequest(BaseModel):
    password: str

# Middleware to check if setup is complete and user is authenticated
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    
    # 1. Always allow static files
    if path.startswith("/static"):
        return await call_next(request)
        
    # 2. Check Setup
    setup_allowed_paths = ["/setup", "/api/setup", "/api/vaultwarden/login-test", "/api/litellm/test", "/api/health"]
    if not is_setup_complete():
        if path in setup_allowed_paths:
            return await call_next(request)
        if path.startswith("/api/"):
            return JSONResponse(status_code=403, content={"detail": "Setup not complete"})
        return RedirectResponse(url="/setup")
    
    # 3. Check Auth (Session Cookie)
    allowed_auth_paths = ["/login", "/api/login", "/setup", "/api/setup", "/api/vaultwarden/login-test", "/api/litellm/test", "/api/health"]
    if path not in allowed_auth_paths:
        session = request.cookies.get("portal_session")
        if not session or session != get_secret("SESSION_ID"):
            if path.startswith("/api/"):
                return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
            return RedirectResponse(url="/login")
            
    return await call_next(request)

@app.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"version": VERSION})

@app.post("/api/login")
@limiter.limit("5/10 minutes")
async def post_login(request: Request, req: LoginRequest):
    stored_hash = get_secret("PORTAL_PASSWORD_HASH")
    if verify_password(req.password, stored_hash):
        session_id = str(uuid.uuid4())
        set_secret("SESSION_ID", session_id)
        response = JSONResponse(content={"status": "success"})
        response.set_cookie(key="portal_session", value=session_id, httponly=True)
        return response
    raise HTTPException(status_code=401, detail="Invalid password")

@app.post("/api/logout")
async def post_logout():
    response = JSONResponse(content={"status": "success"})
    response.delete_cookie("portal_session")
    return response

@app.get("/setup", response_class=HTMLResponse)
async def get_setup(request: Request):
    if is_setup_complete():
        return RedirectResponse(url="/")
    return templates.TemplateResponse(request=request, name="setup.html", context={"version": VERSION})

@app.post("/api/litellm/test")
async def api_test_litellm(req: LiteLLMTestRequest):
    try:
        headers = {"Authorization": f"Bearer {req.key}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{req.url}/health/readiness", headers=headers, timeout=5.0)
            if response.status_code != 200:
                response = await client.get(f"{req.url}/models", headers=headers, timeout=5.0)
            if response.status_code == 200:
                return {"status": "success", "message": "LiteLLM connection verified."}
            else:
                raise Exception(f"LiteLLM returned status {response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/vaultwarden/login-test")
async def post_login_test(req: LoginTestRequest):
    try:
        session_token = initialize_vaultwarden_session(
            req.vw_url, req.vw_client_id, req.vw_client_secret, req.vw_password
        )
        set_secret("BW_SESSION", session_token)
        set_secret("VAULTWARDEN_URL", req.vw_url)
        folders = get_folders()
        return {"status": "success", "session": session_token, "folders": folders}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/setup")
async def post_setup(req: SetupRequest):
    try:
        print(f"DEBUG: Setup triggered for {req.vw_url}")
        session_token = initialize_vaultwarden_session(
            req.vw_url, req.vw_client_id, req.vw_client_secret, req.vw_password
        )
        set_secret("LITELLM_API_URL", req.litellm_url)
        set_secret("LITELLM_MASTER_KEY", req.litellm_key)
        set_secret("VAULTWARDEN_URL", req.vw_url)
        set_secret("VAULTWARDEN_CLIENT_ID", req.vw_client_id)
        set_secret("VAULTWARDEN_CLIENT_SECRET", req.vw_client_secret)
        set_secret("VAULTWARDEN_PASSWORD", req.vw_password)
        set_secret("BW_SESSION", session_token)
        
        password_hash = hash_password(req.vw_password)
        set_secret("PORTAL_PASSWORD_HASH", password_hash)

        if req.ssh_folder_id: set_secret("SSH_FOLDER_ID", req.ssh_folder_id)
        if req.litellm_folder_id: set_secret("LITELLM_FOLDER_ID", req.litellm_folder_id)
        if req.external_folder_id: set_secret("EXTERNAL_FOLDER_ID", req.external_folder_id)
        
        return {"status": "success", "message": "Setup completed. Login with Master Password."}
    except Exception as e:
        print(f"ERROR in setup: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"version": VERSION})

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/vaultwarden/ssh-keys")
async def api_get_ssh_keys():
    try:
        names = get_existing_ssh_keys()
        return {"keys": names}
    except Exception as e:
        print(f"ERROR in api_get_ssh_keys: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/litellm/keys")
async def api_get_litellm_keys():
    try:
        aliases = await get_litellm_keys()
        return {"keys": aliases}
    except Exception as e:
        print(f"ERROR in api_get_litellm_keys: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/litellm/options")
async def api_get_litellm_options():
    try:
        teams = await get_litellm_teams()
        users = await get_litellm_users()
        models = await get_litellm_models()
        return {"teams": teams, "users": users, "models": models}
    except Exception as e:
        print(f"ERROR in api_get_litellm_options: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-ssh")
async def api_generate_ssh(req: SSHGenerateRequest):
    try:
        keys = generate_ssh_keypair(key_name=req.name, comment=req.comment, key_type=req.key_type)
        return {"status": "success", "message": "SSH Key generated.", "keys": keys}
    except Exception as e:
        print(f"ERROR in api_generate_ssh: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync-ssh")
async def api_sync_ssh(req: SSHSyncRequest):
    try:
        folder_id = get_secret("SSH_FOLDER_ID")
        item_id = None
        if req.overwrite:
            item_id = get_item_by_name(req.name, item_type=5)
            
        sync_result = create_ssh_key_item(name=req.name, private_key=req.private_key, public_key=req.public_key, fingerprint=req.fingerprint, folder_id=folder_id, item_id=item_id)
        return {"status": "success", "message": "SSH Key synced (overwritten)." if item_id else "SSH Key synced.", "vaultwarden": sync_result}
    except Exception as e:
        print(f"ERROR in api_sync_ssh: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-litellm")
async def api_generate_litellm(req: LiteLLMGenerateRequest):
    try:
        key_data = await generate_virtual_key(key_alias=req.key_alias, user_id=req.user_id, team_id=req.team_id, max_budget=req.max_budget, models=req.models, key_type=req.key_type)
        return {"status": "success", "message": "LiteLLM Key generated.", "key_data": key_data}
    except Exception as e:
        print(f"ERROR in api_generate_litellm: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync-litellm")
async def api_sync_litellm(req: LiteLLMSyncRequest):
    try:
        folder_id = get_secret("LITELLM_FOLDER_ID")
        # Metadata fields are text (type 0), only the key is hidden (type 1)
        fields = [
            {"name": "Virtual Key", "value": req.key, "type": 1},
            {"name": "Alias", "value": req.alias, "type": 0},
            {"name": "Key Type", "value": req.key_type if req.key_type else "api", "type": 0}
        ]
        if req.user_id: fields.append({"name": "Owned By", "value": req.user_id, "type": 0})
        if req.team_id: fields.append({"name": "Team ID", "value": req.team_id, "type": 0})
        if req.max_budget is not None: fields.append({"name": "Max Budget", "value": str(req.max_budget), "type": 0})
        
        sync_result = create_secure_note_item(name=f"LiteLLM: {req.name}", fields=fields, folder_id=folder_id)
        return {"status": "success", "message": "LiteLLM Key synced.", "vaultwarden": sync_result}
    except Exception as e:
        print(f"ERROR in api_sync_litellm: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/store-external")
async def api_store_external(req: ExternalCredentialRequest):
    try:
        folder_id = get_secret("EXTERNAL_FOLDER_ID")
        # For external data, we keep the main payload hidden but audit tags as text
        fields = [{"name": "Credential Data", "value": req.credential_data, "type": 1}]
        sync_result = create_secure_note_item(name=req.name, fields=fields, folder_id=folder_id)
        return {"status": "success", "message": "Credential synced.", "vaultwarden": sync_result}
    except Exception as e:
        print(f"ERROR in api_store_external: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/litellm/resync")
async def api_resync_litellm(background_tasks: BackgroundTasks):
    """Trigger a manual resync of LiteLLM keys from Vaultwarden."""
    try:
        # Define a wrapper to run the reconciliation once
        async def run_once():
            print("INFO: Manual reconciliation triggered.")
            vault_keys = get_litellm_keys_from_vault()
            litellm_keys = await get_litellm_keys()
            
            for vk in vault_keys:
                if vk["alias"] not in litellm_keys:
                    print(f"INFO: Key '{vk['alias']}' missing in LiteLLM. Restoring from Vault...")
                    await import_litellm_key(
                        key=vk["key"],
                        key_alias=vk["alias"],
                        user_id=vk["user_id"],
                        team_id=vk["team_id"],
                        max_budget=vk["max_budget"],
                        key_type=vk["key_type"]
                    )
            print("INFO: Manual reconciliation complete.")

        background_tasks.add_task(run_once)
        return {"status": "success", "message": "Resync task started in background."}
    except Exception as e:
        print(f"ERROR in api_resync_litellm: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
