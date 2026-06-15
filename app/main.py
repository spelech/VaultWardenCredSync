from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path
from typing import Optional, List

from app.services.ssh import generate_ssh_keypair
from app.services.litellm import generate_virtual_key
from app.services.vaultwarden import create_secure_note

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

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/generate-ssh")
async def api_generate_ssh(req: SSHRequest):
    try:
        keys = generate_ssh_keypair(key_name=req.name, comment=req.comment)
        note_content = f"Private Key:\n{keys['private_key']}\n\nPublic Key:\n{keys['public_key']}"
        sync_result = create_secure_note(name=req.name, notes=note_content)
        
        return {
            "status": "success",
            "message": "SSH Key generated and synced.",
            "keys": keys,
            "vaultwarden": sync_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-litellm")
async def api_generate_litellm(req: LiteLLMRequest):
    try:
        key_data = await generate_virtual_key(key_alias=req.name, models=req.models)
        
        note_content = f"LiteLLM Virtual Key: {key_data['key']}\nAlias: {key_data['key_alias']}"
        sync_result = create_secure_note(name=f"LiteLLM: {req.name}", notes=note_content)
        
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
        sync_result = create_secure_note(name=req.name, notes=req.credential_data)
        
        return {
            "status": "success",
            "message": "External credential synced to Vaultwarden.",
            "vaultwarden": sync_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
