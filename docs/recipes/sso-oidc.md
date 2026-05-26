# Recipe: SSO via OpenID Connect (Google Workspace)

Lets users log in to the admin area via their Google Workspace identity,
keyed by a domain allowlist. For company-internal tools where everyone
has a `@yourcompany.com` Google account, this turns "log in" into one
click and removes password management entirely for the common case.

This recipe leads with **Google Workspace** because it covers the most
common case. The same pattern works for **Microsoft Entra ID (Azure AD)**
and any **generic OIDC** provider — adapter notes are at the bottom.

## What you'll add

- `authlib` to backend deps for the OAuth/OIDC flow
- New env vars: `OIDC_GOOGLE_CLIENT_ID`, `OIDC_GOOGLE_CLIENT_SECRET`, `OIDC_ALLOWED_DOMAINS`
- `backend/app/models/oidc_identity.py` — links external OIDC subjects to local `User` rows
- New alembic migration
- `backend/app/services/oidc.py` — `find_or_create_user_from_claims()`
- `backend/app/api/oidc.py` — `GET /api/auth/oidc/google/login` + `/callback`
- CSRF exemption for the callback path (OIDC's own `state` parameter handles CSRF on the redirect flow)
- Frontend: "Sign in with Google" button on `/admin/login`
- Three tests: domain-allowlist enforcement, auto-create on first login, refusal to auto-link by email

## Architecture decisions

**Local password auth stays the default.** OIDC is additive. A user can have a `password_hash` AND zero or more linked OIDC identities; either path logs in. The env-var bootstrap admin remains your emergency fallback if Google is down or your tenant is locked out.

**No auto-link by email.** First-time SSO login from an allowed domain creates a new `User` row. If a `User` with that email already exists (e.g., the bootstrap admin), the recipe **refuses to auto-link** and returns an error. Auto-linking by email is an account-takeover vector when SSO providers allow unverified email addresses; require admin to merge identities manually if needed. This is the [Google Sign-In confused-deputy](https://medium.com/@xtraordinaryhuman/google-sign-in-and-account-takeover-via-confused-deputy-d3a4cc4ad9d4) class of issue — worth the friction.

**OIDC `state` parameter handles CSRF on the redirect flow** — it's not part of Baseplate's CSRF middleware. The callback path is added to `EXEMPT_PATHS`. The `state` value is a `secrets.token_urlsafe(32)` stored in a short-lived signed cookie and validated on callback return; mismatch → 400.

**PKCE is on.** S256 code challenge, generated per request. Free defence-in-depth against intercepted authorization codes.

**Refresh tokens are skipped in v1.** Baseplate's sessions are 24h JWTs already; that's well within Google's access-token lifetime. Add refresh handling if you need long-lived sessions and don't want users re-auth'ing daily.

## 1. Install authlib

```bash
# In backend/pyproject.toml dependencies:
"authlib>=1.3.0",
"itsdangerous>=2.2.0",  # for signing the short-lived state cookie
```

Then `make install`.

## 2. Provider setup (Google Workspace)

In [Google Cloud Console](https://console.cloud.google.com/apis/credentials):

1. Create or select a project under your Workspace org.
2. **APIs & Services → OAuth consent screen**: User Type "Internal" (only users in your Workspace). Add the `email` and `openid` and `profile` scopes.
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**: type Web application. Authorized redirect URI: `https://your-app.example.com/api/auth/oidc/google/callback` (and `http://localhost:3001/api/auth/oidc/google/callback` for dev).
4. Copy the client ID + secret into `backend/.env`.

```env
OIDC_GOOGLE_CLIENT_ID=...
OIDC_GOOGLE_CLIENT_SECRET=...
OIDC_ALLOWED_DOMAINS=yourcompany.com,trusted-contractor.com
OIDC_REDIRECT_BASE_URL=http://localhost:3001  # frontend origin; Next.js proxies /api/* to backend
```

The `OIDC_ALLOWED_DOMAINS` list is comma-separated. Login from any other domain returns 403.

## 3. Model

`backend/app/models/oidc_identity.py`:

```python
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class OidcIdentity(Base, TimestampMixin):
    __tablename__ = "oidc_identities"
    __table_args__ = (
        # One identity per (provider, subject) globally; one provider link per user.
        UniqueConstraint("provider", "subject", name="uq_oidc_provider_subject"),
        UniqueConstraint("provider", "user_id", name="uq_oidc_provider_user"),
    )

    id = uuid_pk()
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32))  # "google" | "microsoft" | ...
    subject: Mapped[str] = mapped_column(String(255))  # provider's stable user ID
    email: Mapped[str] = mapped_column(String(255))    # last-seen email (informational)
```

Register in `app/models/__init__.py`. Generate + apply migration.

## 4. Service

`backend/app/services/oidc.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.oidc_identity import OidcIdentity
from app.models.user import User


class OidcError(Exception):
    """Raised for any reason a claim shouldn't result in a login."""


class OidcService:
    @staticmethod
    def _allowed_domains() -> set[str]:
        raw = (settings.oidc_allowed_domains or "").strip()
        return {d.strip().lower() for d in raw.split(",") if d.strip()}

    @staticmethod
    async def find_or_create_user_from_claims(
        db: AsyncSession,
        *,
        provider: str,
        subject: str,
        email: str,
        email_verified: bool,
    ) -> User:
        if not email_verified:
            raise OidcError("Email not verified by the provider.")

        email = email.strip().lower()
        domain = email.rsplit("@", 1)[-1]
        allowed = OidcService._allowed_domains()
        if allowed and domain not in allowed:
            raise OidcError(f"Domain '{domain}' not in OIDC_ALLOWED_DOMAINS.")

        # Already linked? Just return the user.
        linked = await db.execute(
            select(OidcIdentity).where(
                OidcIdentity.provider == provider,
                OidcIdentity.subject == subject,
            )
        )
        identity = linked.scalar_one_or_none()
        if identity:
            # Refresh the cached email if the provider changed it.
            if identity.email != email:
                identity.email = email
                await db.commit()
            user_q = await db.execute(select(User).where(User.id == identity.user_id))
            return user_q.scalar_one()

        # No link yet. If a local user with this email exists, REFUSE to
        # auto-link — that's an account-takeover vector. Admin must merge.
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise OidcError(
                "A local account with this email exists. Ask an admin to "
                "link your SSO identity manually."
            )

        # Create a new user + identity. Domain has already passed the allowlist.
        user = User(email=email, password_hash="", is_admin=True)
        db.add(user)
        await db.flush()
        identity = OidcIdentity(
            user_id=user.id, provider=provider, subject=subject, email=email
        )
        db.add(identity)
        await db.commit()
        await db.refresh(user)
        return user
```

A user created via SSO has an empty `password_hash` — they can't log in via password until an admin sets one. That's intentional.

## 5. Routes

`backend/app/api/oidc.py`:

```python
from datetime import datetime, timedelta, timezone

import jwt
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.csrf import COOKIE_NAME as CSRF_COOKIE_NAME, new_csrf_token
from app.services.oidc import OidcError, OidcService

router = APIRouter(prefix="/api/auth/oidc", tags=["oidc"])

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=settings.oidc_google_client_id,
    client_secret=settings.oidc_google_client_secret,
    client_kwargs={"scope": "openid email profile"},
)

_signer = URLSafeTimedSerializer(settings.jwt_secret, salt="oidc-state")
_STATE_TTL_SECONDS = 600  # 10 minutes


@router.get("/google/login")
async def google_login(request: Request, response: Response):
    redirect_uri = f"{settings.oidc_redirect_base_url}/api/auth/oidc/google/callback"
    # authlib generates state + PKCE; we wrap state in a signed cookie so we
    # can verify it on return without server-side session state.
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:  # authlib raises various subclasses
        raise HTTPException(status_code=400, detail=f"OIDC error: {exc}") from exc

    claims = token.get("userinfo") or {}
    try:
        user = await OidcService.find_or_create_user_from_claims(
            db,
            provider="google",
            subject=claims["sub"],
            email=claims.get("email", ""),
            email_verified=bool(claims.get("email_verified", False)),
        )
    except OidcError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    # Same JWT cookie + csrf cookie as /api/auth/login.
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    access = jwt.encode(
        {"sub": str(user.id), "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response.set_cookie(
        key="access_token", value=access, httponly=True,
        secure=settings.cookie_secure, samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME, value=new_csrf_token(), httponly=False,
        secure=settings.cookie_secure, samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )
    # 303 so the browser flips to GET on the destination.
    response.status_code = 303
    response.headers["Location"] = "/admin"
    return response
```

Register in `main.py`:

```python
from app.api import oidc
app.include_router(oidc.router)
```

Add `SessionMiddleware` (required by authlib for the redirect state):

```python
from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key=settings.jwt_secret)
```

## 6. CSRF exemption

The callback is a `GET` so it's already exempt (safe methods bypass CSRF). The login redirect is also a `GET`. No middleware change needed — OIDC's own `state` parameter (managed by authlib + the session middleware) covers the CSRF concern on the redirect flow.

## 7. Frontend

Add a "Sign in with Google" button to `admin/login/page.tsx`:

```tsx
<a
  href="/api/auth/oidc/google/login"
  className="block w-full text-center rounded-lg border border-border px-4 py-2 text-sm hover:bg-surface-elevated"
>
  Sign in with Google
</a>
```

Plain `<a>`, not a fetch — the OAuth flow is a full-page redirect, not an XHR.

## 8. Tests

`backend/tests/test_oidc.py`:

```python
import pytest

from app.services.oidc import OidcError, OidcService


@pytest.mark.asyncio
async def test_domain_allowlist_blocks_outsiders(db_session, monkeypatch):
    monkeypatch.setenv("OIDC_ALLOWED_DOMAINS", "company.com")
    # Reload settings if your config caches them; or pass through directly:
    from app.config import settings
    settings.oidc_allowed_domains = "company.com"
    with pytest.raises(OidcError, match="not in OIDC_ALLOWED_DOMAINS"):
        await OidcService.find_or_create_user_from_claims(
            db_session,
            provider="google",
            subject="abc",
            email="someone@gmail.com",
            email_verified=True,
        )


@pytest.mark.asyncio
async def test_first_login_creates_user(db_session):
    from app.config import settings
    settings.oidc_allowed_domains = "company.com"
    user = await OidcService.find_or_create_user_from_claims(
        db_session,
        provider="google",
        subject="abc-123",
        email="new@company.com",
        email_verified=True,
    )
    assert user.email == "new@company.com"
    assert user.is_admin is True
    assert user.password_hash == ""  # no password set on SSO-created accounts


@pytest.mark.asyncio
async def test_refuses_to_auto_link_to_existing_email(db_session):
    from app.config import settings
    from app.services.users import UserService
    settings.oidc_allowed_domains = "company.com"
    # Existing local user
    await UserService.create(
        db_session, email="incumbent@company.com",
        password_hash="$2b$12$x" * 4, is_admin=True,
    )
    with pytest.raises(OidcError, match="Ask an admin"):
        await OidcService.find_or_create_user_from_claims(
            db_session,
            provider="google",
            subject="malicious",
            email="incumbent@company.com",
            email_verified=True,
        )
```

The redirect-handling endpoints aren't tested directly — that requires mocking authlib's OAuth flow, which adds more friction than value for a recipe. The service-layer tests cover the security-critical decisions.

## Adapting to Microsoft Entra ID (Azure AD)

Same recipe, different provider registration:

```python
oauth.register(
    name="microsoft",
    server_metadata_url=(
        f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration"
    ),
    client_id=settings.oidc_microsoft_client_id,
    client_secret=settings.oidc_microsoft_client_secret,
    client_kwargs={"scope": "openid email profile"},
)
```

Where `tenant_id` is your Entra tenant ID, or `common` for any work/school account, or `consumers` for personal accounts. Add an `/api/auth/oidc/microsoft/login` + `/callback` pair following the same structure.

The `find_or_create_user_from_claims` service stays unchanged — claims are normalised across providers (Entra returns `email` + `email_verified` in id-token claims when the `email` scope is requested).

## Adapting to a generic OIDC provider

Any provider with a public `.well-known/openid-configuration` endpoint works:

```python
oauth.register(
    name="custom",
    server_metadata_url="https://idp.example.com/.well-known/openid-configuration",
    client_id=settings.oidc_custom_client_id,
    client_secret=settings.oidc_custom_client_secret,
    client_kwargs={"scope": "openid email profile"},
)
```

Pick the right `scope`; some providers also require `offline_access` for refresh tokens. Audit the ID token's `iss` and `aud` claims if the provider issues for multiple tenants.

## What to skip until you need it

- **SAML.** Heavier protocol, harder to debug, mostly demanded by enterprises. Add a `docs/growth-paths/sso-saml.md` recipe when an enterprise customer asks. OIDC handles ≥95% of "log in with company identity" cases.
- **Group/role claim mapping** ("only people in the `engineering` group should be admins"). Add when you have more than one role. Until then `is_admin=True` for every allowlisted login is fine.
- **Refresh tokens** + token rotation. Adds complexity for a starter where sessions are short anyway. Add when you want long-lived sessions and don't want users re-auth'ing daily.
- **Multi-tenant Entra** (any-tenant `common` issuer). Useful for consumer apps, dangerous for internal tools because anyone with a Microsoft account becomes a login candidate. Use a specific tenant ID.
- **Account-merging UI** for the "local user with this email exists" case. Until you actually hit it, the explicit-refusal error is fine — admin runs a manual SQL `UPDATE oidc_identities SET user_id = ...` to link.
- **Auto-disabling local password auth** when SSO is configured. Two-paths is more resilient (if your IDP is down, the bootstrap admin still logs in).
- **`auth_log` audit trail** for SSO logins. Compose with the [`audit-log.md`](audit-log.md) recipe — call `AuditLogService.record(user_id=user.id, action="sso_login", resource_type="session", extra={"provider": "google"})` at the end of the callback.
