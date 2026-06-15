from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path
from typing import Optional, List
import httpx

from app.services.ssh import generate_ssh_keypair
from app.services.litellm import generate_virtual_key
from app.services.vaultwarden import create_secure_login, initialize_vaultwarden_session, get_folders, create_ssh_key_item
from app.database import is_setup_complete, set_secret, get_secret

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

# Middleware to check if setup is complete
@app.middleware("http")
async def check_setup(request: Request, call_next):
    # Let static files and setup routes pass through
    allowed_paths = ["/static", "/setup", "/api/setup", "/api/litellm/test", "/api/vaultwarden/login-test"]
    
    is_allowed = any(request.url.path.startswith(p) for p in allowed_paths)
    
    if not is_allowed and not is_setup_complete():
        if request.url.path.startswith("/api/"):
            return HTMLResponse(content="Setup not complete", status_code=403)
        return RedirectResponse(url="/setup")
        
    return await call_next(request)

@app.get("/setup", response_class=HTMLResponse)
async def get_setup(request: Request):
    if is_setup_complete():
        return RedirectResponse(url="/")
    return templates.TemplateResponse(request=request, name="setup.html")

@app.post("/api/litellm/test")
async def api_test_litellm(req: LiteLLMTestRequest):
    try:
        headers = {"Authorization": f"Bearer {req.key}"}
        async with httpx.AsyncClient() as client:
            # Check version or health
            response = await client.get(f"{req.url}/health/readiness", headers=headers, timeout=5.0)
            if response.status_code != 200:
                # Fallback
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
        # Temporarily save session just to fetch folders
        set_secret("BW_SESSION", session_token)
        set_secret("VAULTWARDEN_URL", req.vw_url)
        folders = get_folders()
        return {"status": "success", "session": session_token, "folders": folders}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/setup")
async def post_setup(req: SetupRequest):
    try:
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
        
        if req.ssh_folder_id: set_secret("SSH_FOLDER_ID", req.ssh_folder_id)
        if req.litellm_folder_id: set_secret("LITELLM_FOLDER_ID", req.litellm_folder_id)
        if req.external_folder_id: set_secret("EXTERNAL_FOLDER_ID", req.external_folder_id)
        
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
        folder_id = get_secret("SSH_FOLDER_ID")
        
        sync_result = create_ssh_key_item(
            name=req.name,
            private_key=keys['private_key'],
            public_key=keys['public_key'],
            folder_id=folder_id
        )
        
        return {
            "status": "success",
            "message": "SSH Key generated and synced to Vaultwarden as a native SSH Key.",
            "keys": keys,
            "vaultwarden": sync_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-litellm")
async def api_generate_litellm(req: LiteLLMRequest):
    try:
        key_data = await generate_virtual_key(key_alias=req.name, models=req.models)
        folder_id = get_secret("LITELLM_FOLDER_ID")
        
        fields = [
            {"name": "Virtual Key", "value": key_data['key'], "type": 1},
            {"name": "Alias", "value": key_data['key_alias'], "type": 0}
        ]
        sync_result = create_secure_login(name=f"LiteLLM: {req.name}", fields=fields, folder_id=folder_id)
        
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
        folder_id = get_secret("EXTERNAL_FOLDER_ID")
        fields = [
            {"name": "Credential Data", "value": req.credential_data, "type": 1}
        ]
        sync_result = create_secure_login(name=req.name, fields=fields, folder_id=folder_id)
        
        return {
            "status": "success",
            "message": "External credential synced to Vaultwarden.",
            "vaultwarden": sync_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
