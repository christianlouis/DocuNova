import os
import inspect
from functools import wraps

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request, status
from starlette.responses import RedirectResponse

from app.config import settings

oauth = OAuth()

AUTH_ENABLED = settings.auth_enabled

if AUTH_ENABLED:
    oauth.register(
        name="authentik",
        client_id=settings.authentik_client_id,
        client_secret=settings.authentik_client_secret,
        server_metadata_url=settings.authentik_config_url,
        client_kwargs={"scope": "openid profile email"},
    )

router = APIRouter()


def get_current_user(request: Request):
    return request.session.get("user")


def require_login(func):
    if not AUTH_ENABLED:
        return func  # no-op

    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if not request.session.get("user"):
            request.session["redirect_after_login"] = str(request.url)
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        # Check if the wrapped function is a coroutine function
        if inspect.iscoroutinefunction(func):
            return await func(request, *args, **kwargs)
        else:
            return func(request, *args, **kwargs)

    return wrapper


if AUTH_ENABLED:
    @router.get("/login")
    async def login(request: Request):
        redirect_uri = request.url_for("auth")
        return await oauth.authentik.authorize_redirect(request, redirect_uri)

    @router.get("/auth")
    async def auth(request: Request):
        token = await oauth.authentik.authorize_access_token(request)
        userinfo = token.get("userinfo")
        request.session["user"] = dict(userinfo)
        redirect_url = request.session.pop("redirect_after_login", "/upload")
        return RedirectResponse(url=redirect_url)

    @router.get("/logout")
    async def logout(request: Request):
        request.session.pop("user", None)
        return RedirectResponse(url="/")


@router.get("/private")
@require_login
async def private_page(request: Request):
    """A protected endpoint that requires login."""
    user = request.session.get("user")  # e.g. {"email": "...", ...}
    return {"message": "This is a protected page.", "user": user}
