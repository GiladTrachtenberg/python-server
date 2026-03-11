from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Any, NoReturn

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from tortoise.exceptions import IntegrityError

from src.auth_schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from src.models import RefreshToken, User
from src.schemas import ErrorBody, ErrorResponse

if TYPE_CHECKING:
    from uuid import UUID

    from src.config import Settings

auth_router = APIRouter(prefix="/auth", tags=["auth"])

_ph = PasswordHasher()
_DUMMY_HASH: str = _ph.hash("dummy-constant-for-timing")

_INVALID_CREDS = ("invalid_credentials", "Invalid email or password")
_UNAUTHORIZED = ("unauthorized", "Invalid or expired token")
_HTTP_401 = status.HTTP_401_UNAUTHORIZED


def _get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated["Settings", Depends(_get_settings)]


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: str, settings: Settings) -> str:
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes,
    )
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    return jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
    )


def _error(
    code: str, message: str, status_code: int,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump())


def _raise_unauthorized() -> NoReturn:
    raise HTTPException(
        status_code=_HTTP_401,
        detail=ErrorResponse(
            error=ErrorBody(code=_UNAUTHORIZED[0], message=_UNAUTHORIZED[1]),
        ).model_dump(),
    )


async def _create_token_pair(
    user_id: UUID,
    settings: Settings,
    family_id: UUID | None = None,
) -> tuple[str, str]:
    access_token = create_access_token(str(user_id), settings)
    raw_refresh = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(
        days=settings.refresh_token_expire_days,
    )
    create_kwargs: dict[str, Any] = {
        "user_id": user_id,
        "token_hash": hash_token(raw_refresh),
        "expires_at": expires_at,
    }
    if family_id is not None:
        create_kwargs["family_id"] = family_id
    await RefreshToken.create(**create_kwargs)
    return access_token, raw_refresh


async def get_current_user(
    request: Request, settings: SettingsDep,
) -> User:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        _raise_unauthorized()

    token = auth_header.removeprefix("Bearer ")
    try:
        payload = decode_access_token(token, settings)
    except jwt.InvalidTokenError:
        _raise_unauthorized()

    if payload.get("type") != "access":
        _raise_unauthorized()

    user = await User.get_or_none(id=payload["sub"])
    if user is None:
        _raise_unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest) -> JSONResponse:
    hashed = hash_password(body.password)
    try:
        user = await User.create(email=body.email, password_hash=hashed)
    except IntegrityError:
        return _error(
            "conflict", "Email already registered", status.HTTP_409_CONFLICT,
        )

    data = UserResponse(
        id=user.id, email=user.email, created_at=user.created_at,
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"data": data.model_dump(mode="json")},
    )


@auth_router.post("/login")
async def login(body: LoginRequest, settings: SettingsDep) -> JSONResponse:
    user = await User.get_or_none(email=body.email)
    if user is None:
        verify_password(body.password, _DUMMY_HASH)
        return _error(*_INVALID_CREDS, _HTTP_401)

    if not verify_password(body.password, user.password_hash):
        return _error(*_INVALID_CREDS, _HTTP_401)

    access_token, raw_refresh = await _create_token_pair(
        user.id, settings,
    )
    data = TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )
    return JSONResponse(content={"data": data.model_dump()})


@auth_router.post("/refresh")
async def refresh(
    body: RefreshRequest, settings: SettingsDep,
) -> JSONResponse:
    token_hash = hash_token(body.refresh_token)
    stored = (
        await RefreshToken.get_or_none(token_hash=token_hash)
        .select_related("user")
    )

    if stored is None:
        return _error(*_UNAUTHORIZED, _HTTP_401)

    if stored.revoked:
        await RefreshToken.filter(
            family_id=stored.family_id,
        ).update(revoked=True)
        return _error(
            "unauthorized", "Token reuse detected", _HTTP_401,
        )

    now = datetime.now(UTC)
    expires_at = (
        stored.expires_at
        if stored.expires_at.tzinfo
        else stored.expires_at.replace(tzinfo=UTC)
    )
    if expires_at < now:
        return _error(
            "unauthorized", "Refresh token expired", _HTTP_401,
        )

    stored.revoked = True
    await stored.save(update_fields=["revoked"])

    access_token, raw_refresh = await _create_token_pair(
        stored.user.id, settings, family_id=stored.family_id,
    )

    data = TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )
    return JSONResponse(content={"data": data.model_dump()})


@auth_router.get("/me")
async def me(user: CurrentUser) -> JSONResponse:
    data = UserResponse(
        id=user.id, email=user.email, created_at=user.created_at,
    )
    return JSONResponse(content={"data": data.model_dump(mode="json")})
