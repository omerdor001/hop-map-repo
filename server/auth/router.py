from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm

from config import config_manager
from auth.dependencies import get_current_user
from auth.schemas import RegisterRequest
from auth import service
from core.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    cfg = config_manager.auth
    response.set_cookie(
        key=cfg.refresh_cookie_name,
        value=raw_token,
        httponly=True,
        secure=cfg.refresh_cookie_secure,
        samesite="lax",
        max_age=cfg.refresh_token_expire_days * 86400,
        path="/auth/refresh",
    )


def _clear_refresh_cookie(response: Response) -> None:
    cfg = config_manager.auth
    response.delete_cookie(key=cfg.refresh_cookie_name, path="/auth/refresh")


@router.post("/register", status_code=201)
@limiter.limit(config_manager.auth.register_rate_limit)
async def auth_register(request: Request, body: RegisterRequest, response: Response) -> dict:
    access_token, raw_refresh, user = service.register(body.email, body.password, body.display_name)
    _set_refresh_cookie(response, raw_refresh)
    return {"accessToken": access_token, "tokenType": "bearer", "user": user}


@router.post("/login")
@limiter.limit(config_manager.auth.login_rate_limit)
async def auth_login(request: Request, response: Response, form: OAuth2PasswordRequestForm = Depends()) -> dict:
    access_token, raw_refresh, user = service.login(form.username, form.password)
    _set_refresh_cookie(response, raw_refresh)
    return {"accessToken": access_token, "tokenType": "bearer", "user": user}


@router.post("/refresh")
async def auth_refresh(request: Request, response: Response) -> dict:
    raw_token = request.cookies.get(config_manager.auth.refresh_cookie_name)
    if not raw_token:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Missing refresh token.")
    access_token, new_raw = service.refresh(raw_token)
    _set_refresh_cookie(response, new_raw)
    return {"accessToken": access_token}


@router.post("/logout")
async def auth_logout(request: Request, response: Response) -> dict:
    raw_token = request.cookies.get(config_manager.auth.refresh_cookie_name)
    service.logout(raw_token)
    _clear_refresh_cookie(response)
    return {"ok": True}


@router.get("/me")
async def auth_me(current_user: dict = Depends(get_current_user)) -> dict:
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "displayName": current_user.get("displayName", ""),
        "createdAt": current_user.get("createdAt", ""),
    }
