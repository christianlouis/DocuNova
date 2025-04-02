# app/frontend.py
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.auth import require_login
from app.database import SessionLocal
from app.config import settings

router = APIRouter()

# Set up Jinja2 templates
templates_dir = Path(__file__).parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Set up logging
logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/files")
@require_login
def files_page(request: Request):
    """
    Return the 'files.html' template. 
    The actual file data is fetched via XHR from /api/files in the template.
    """
    return templates.TemplateResponse("files.html", {"request": request})

@router.get("/", include_in_schema=False)
async def serve_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/about", include_in_schema=False)
async def serve_about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@router.get("/upload", include_in_schema=False)
@require_login
async def serve_upload(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    # If you have a real favicon in `frontend/static/favicon.ico`:
    favicon_path = Path(__file__).parent.parent / "frontend" / "static" / "favicon.ico"
    return str(favicon_path)

@router.get("/status")
@require_login
async def status_dashboard(request: Request):
    """
    Status dashboard showing all configured integration targets
    """
    from app.utils.config_validator import get_provider_status
    
    # Get provider status
    providers = get_provider_status()
    
    return templates.TemplateResponse(
        "status_dashboard.html",
        {
            "request": request, 
            "providers": providers,
            "debug_enabled": getattr(settings, 'debug', False),
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    )

@router.get("/env")
@require_login
async def env_debug(request: Request):
    """
    Debug endpoint to view environment variables and settings
    Uses actual debug setting from config
    """
    # Use the actual debug setting from configuration
    debug_enabled = settings.debug
    
    # Get settings data
    from app.utils.config_validator import get_settings_for_display
    settings_data = get_settings_for_display(show_values=debug_enabled)
    
    return templates.TemplateResponse(
        "env_debug.html",
        {
            "request": request, 
            "settings": settings_data,
            "debug_enabled": debug_enabled,
            "app_version": settings.version
        }
    )

@router.get("/onedrive-setup")
@require_login
async def onedrive_setup_page(request: Request):
    """
    Setup page for the OneDrive integration.
    Shows configuration status and setup instructions.
    """
    # Check OneDrive configuration
    is_configured = bool(settings.onedrive_client_id and 
                         settings.onedrive_client_secret and 
                         settings.onedrive_refresh_token)
    
    # Get configuration values to display status (hide sensitive values)
    return templates.TemplateResponse(
        "onedrive.html",
        {
            "request": request,
            "is_configured": is_configured,
            "client_id": bool(settings.onedrive_client_id),
            "client_id_value": settings.onedrive_client_id or "",  # Pass the actual value for the form
            "client_secret": bool(settings.onedrive_client_secret),
            "client_secret_value": settings.onedrive_client_secret if settings.onedrive_client_secret else "",
            "tenant_id": settings.onedrive_tenant_id,
            "refresh_token": bool(settings.onedrive_refresh_token),
            "refresh_token_value": settings.onedrive_refresh_token if settings.onedrive_refresh_token else "",
            "folder_path": settings.onedrive_folder_path or "Documents/Uploads"  # Default folder path
        }
    )

@router.get("/onedrive-callback")
@require_login
async def onedrive_callback(request: Request, code: str = None, error: str = None):
    """
    Callback endpoint for OneDrive OAuth flow.
    Now automatically exchanges the code for a token and saves it to the configuration.
    """
    if error:
        return templates.TemplateResponse(
            "onedrive_callback_error.html",
            {"request": request, "error": error}
        )
    
    if not code:
        return templates.TemplateResponse(
            "onedrive_callback_error.html",
            {"request": request, "error": "No authorization code received from Microsoft"}
        )
    
    # Display the processing page with automatic token exchange
    return templates.TemplateResponse(
        "onedrive_callback.html",
        {
            "request": request, 
            "code": code,
            "client_id_value": settings.onedrive_client_id or "",
            "client_secret_value": settings.onedrive_client_secret or "",
            "tenant_id": settings.onedrive_tenant_id or "common"
        }
    )

