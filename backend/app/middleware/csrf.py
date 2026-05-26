"""Double-submit cookie CSRF protection.

The server sets a non-HttpOnly `csrf_token` cookie on login (and via
GET /api/auth/csrf). The frontend reads the cookie and echoes it in an
`X-CSRF-Token` header on every write request. The middleware checks
that the header matches the cookie via constant-time comparison.

Why this works: a malicious cross-origin site can trigger a request that
carries the auth cookie (SameSite=Lax allows top-level POSTs) but it
CANNOT read the csrf cookie due to same-origin policy, so it can't
forge the header.
"""

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Paths that bypass CSRF entirely. Login can't have a prior token; the csrf
# endpoint itself ISSUES the token. Add new exemptions sparingly.
EXEMPT_PATHS = frozenset({"/api/auth/login", "/api/auth/csrf"})

COOKIE_NAME = "csrf_token"
HEADER_NAME = "X-CSRF-Token"


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in SAFE_METHODS:
            return await call_next(request)
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        cookie = request.cookies.get(COOKIE_NAME)
        header = request.headers.get(HEADER_NAME)

        if not cookie or not header or not secrets.compare_digest(cookie, header):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or invalid"},
            )
        return await call_next(request)


def new_csrf_token() -> str:
    """Generate a fresh CSRF token. Use when issuing the cookie."""
    return secrets.token_urlsafe(32)
