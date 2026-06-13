from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm

from config import config_manager
from auth.dependencies import get_current_user
from auth.schemas import (
    AccessTokenResponse,
    AuthResponse,
    ForgotPasswordRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
    ValidateResetTokenRequest,
)
from auth import service
from core.rate_limit import limiter
from core.schemas import OkResponse

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


@router.post("/register", status_code=201, response_model=AuthResponse)
@limiter.limit(config_manager.auth.register_rate_limit)
def auth_register(request: Request, body: RegisterRequest, response: Response) -> AuthResponse:
    access_token, raw_refresh, user = service.register(body.email, body.password, body.display_name)
    _set_refresh_cookie(response, raw_refresh)
    return AuthResponse(accessToken=access_token, user=UserResponse(**user))


@router.post("/login", response_model=AuthResponse)
@limiter.limit(config_manager.auth.login_rate_limit)
def auth_login(request: Request, response: Response, form: OAuth2PasswordRequestForm = Depends()) -> AuthResponse:
    access_token, raw_refresh, user = service.login(form.username, form.password)
    _set_refresh_cookie(response, raw_refresh)
    return AuthResponse(accessToken=access_token, user=UserResponse(**user))


@router.post("/refresh", response_model=AccessTokenResponse)
def auth_refresh(request: Request, response: Response) -> AccessTokenResponse:
    raw_token = request.cookies.get(config_manager.auth.refresh_cookie_name)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing refresh token.")
    access_token, new_raw = service.refresh(raw_token)
    _set_refresh_cookie(response, new_raw)
    return AccessTokenResponse(accessToken=access_token)


@router.post("/logout", response_model=OkResponse)
def auth_logout(request: Request, response: Response) -> OkResponse:
    raw_token = request.cookies.get(config_manager.auth.refresh_cookie_name)
    service.logout(raw_token)
    _clear_refresh_cookie(response)
    return OkResponse()


@router.get("/me", response_model=UserResponse)
def auth_me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        displayName=current_user.get("displayName", ""),
        createdAt=current_user.get("createdAt", ""),
    )


@router.post("/forgot-password", response_model=OkResponse)
@limiter.limit(config_manager.auth.forgot_password_rate_limit)
def auth_forgot_password(request: Request, body: ForgotPasswordRequest) -> OkResponse:
    service.forgot_password(body.email)
    return OkResponse()


@router.post("/validate-reset-token", response_model=OkResponse)
def auth_validate_reset_token(body: ValidateResetTokenRequest) -> OkResponse:
    service.validate_reset_token(body.token)
    return OkResponse()


@router.post("/reset-password", response_model=OkResponse)
def auth_reset_password(body: ResetPasswordRequest) -> OkResponse:
    service.reset_password(body.token, body.new_password)
    return OkResponse()
