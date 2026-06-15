from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path
from typing import Optional, List

from app.services.ssh import generate_ssh_keypair
from app.services.litellm import generate_virtual_key
from app.services.vaultwarden import create_secure_login, initialize_vaultwarden_session
from app.database import is_setup_complete, set_secret

app = FastAPI(title="Credential Portal", version="0.1.0")

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Setup templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Pydantic models for requests
class SSHRequest(BaseModel):
    name: str
    comment: Optional[str] = ""

class LiteLLMRequest(BaseModel):
    name: str
    models: Optional[List[str]] = None

class ExternalCredentialRequest(BaseModel):
    name: str
    credential_data: str

class SetupRequest(BaseModel):
    litellm_url: str
    litellm_key: str
    vw_url: str
    vw_client_id: str
    vw_client_secret: str
    vw_password: str

# Middleware to check if setup is complete
@app.middleware("http")
async def check_setup(request: Request, call_next):
    # Let static files and setup routes pass through
    if request.url.path.startswith("/static") or request.url.path.startswith("/setup") or request.url.path == "/api/setup":
        return await call_next(request)
        
    if not is_setup_complete():
        # Redirect API calls vs HTML page loads differently if needed, but a simple redirect to /setup works.
        if request.url.path.startswith("/api/"):
            return HTMLResponse(content="Setup not complete", status_code=403)
        return RedirectResponse(url="/setup")
        
    return await call_next(request)

@app.get("/setup", response_class=HTMLResponse)
async def get_setup(request: Request):
    if is_setup_complete():
        return RedirectResponse(url="/")
    return templates.TemplateResponse(request=request, name="setup.html")

@app.post("/api/setup")
async def post_setup(req: SetupRequest):
    try:
        # Before saving, let's verify we can log into Vaultwarden
        session_token = initialize_vaultwarden_session(
            req.vw_url, req.vw_client_id, req.vw_client_secret, req.vw_password
        )
        
        # If successful, save to encrypted DB
        set_secret("LITELLM_API_URL", req.litellm_url)
        set_secret("LITELLM_MASTER_KEY", req.litellm_key)
        set_secret("VAULTWARDEN_URL", req.vw_url)
        set_secret("VAULTWARDEN_CLIENT_ID", req.vw_client_id)
        set_secret("VAULTWARDEN_CLIENT_SECRET", req.vw_client_secret)
        set_secret("VAULTWARDEN_PASSWORD", req.vw_password)
        set_secret("BW_SESSION", session_token)
        
        return {"status": "success", "message": "Setup completed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/generate-ssh")
async def api_generate_ssh(req: SSHRequest):
    try:
        keys = generate_ssh_keypair(key_name=req.name, comment=req.comment)
        
        # Syncing to Vaultwarden as hidden fields on a Login Item
        fields = [
            {"name": "Private Key", "value": keys['private_key'], "type": 1}, # 1 = Hidden
            {"name": "Public Key", "value": keys['public_key'], "type": 1}
        ]
        sync_result = create_secure_login(name=req.name, username=req.comment, fields=fields)
        
        return {
            "status": "success",
            "message": "SSH Key generated and synced to Vaultwarden as hidden fields.",
            "keys": keys,
            "vaultwarden": sync_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-litellm")
async def api_generate_litellm(req: LiteLLMRequest):
    try:
        key_data = await generate_virtual_key(key_alias=req.name, models=req.models)
        
        fields = [
            {"name": "Virtual Key", "value": key_data['key'], "type": 1},
            {"name": "Alias", "value": key_data['key_alias'], "type": 0} # 0 = Text
        ]
        sync_result = create_secure_login(name=f"LiteLLM: {req.name}", fields=fields)
        
        return {
            "status": "success",
            "message": "LiteLLM Key generated and synced.",
            "key_data": key_data,
            "vaultwarden": sync_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/store-external")
async def api_store_external(req: ExternalCredentialRequest):
    try:
        fields = [
            {"name": "Credential Data", "value": req.credential_data, "type": 1}
        ]
        sync_result = create_secure_login(name=req.name, fields=fields)
        
        return {
            "status": "success",
            "message": "External credential synced to Vaultwarden.",
            "vaultwarden": sync_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
