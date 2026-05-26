from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_admin
from app.middleware.csrf import COOKIE_NAME as CSRF_COOKIE_NAME, new_csrf_token
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import UserResponse
from app.services.users import UserService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        # Must be readable from JS so the frontend can echo it in a header.
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await UserService.authenticate(db, body.email, body.password)
    if not user or not user.is_admin:
        # Same response for missing user, wrong password, and non-admin user
        # — never leak which case it is.
        raise HTTPException(status_code=401, detail="Invalid credentials")

    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    token = jwt.encode(
        {"sub": str(user.id), "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )
    _set_csrf_cookie(response, new_csrf_token())
    return LoginResponse()


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie(CSRF_COOKIE_NAME)
    return {"message": "Logged out"}


@router.get("/csrf")
async def csrf(response: Response):
    """Issue (or refresh) a CSRF token. Sets the cookie AND returns the token
    in the body so JS can grab it without parsing document.cookie."""
    token = new_csrf_token()
    _set_csrf_cookie(response, token)
    return {"token": token}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_admin)):
    """Check auth status — requires valid cookie."""
    return user
