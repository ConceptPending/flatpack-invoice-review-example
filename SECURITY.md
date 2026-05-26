# Security Policy

## Supported versions

This project is a starter template, not a deployed product. Only the `main`
branch receives security updates. Tagged releases (`v0.1.0`, etc.) are
historical snapshots and won't be patched in place — rebase onto current
`main` if you need fixes.

## Reporting a vulnerability

If you discover a vulnerability, please report it **privately** rather than
opening a public issue.

Preferred channels, in order:

1. **GitHub Security Advisories** — https://github.com/ConceptPending/baseplate/security/advisories/new
2. **Email** — nick@nickw.info

What to include:

- A description of the vulnerability and its impact
- Steps to reproduce (or a proof-of-concept)
- The affected file(s) and line numbers if you know them
- Whether you'd like to be credited in the fix announcement

## Response expectations

This is a personal project with no commercial backing — calibrate expectations
accordingly:

- I'll acknowledge receipt within **7 days**
- I'll aim to provide a fix or substantive response within **30 days**
- Critical issues may be patched faster; non-critical ones may take longer

I will publicly disclose the issue after a fix is merged, crediting the
reporter unless they prefer otherwise.

## Scope

**In scope** — Baseplate's code as shipped on `main`:

- Authentication and authorization logic (`backend/app/api/auth.py`, `backend/app/deps.py`)
- CSRF middleware (`backend/app/middleware/csrf.py`)
- Startup validation (`backend/app/config.py`)
- Default cookie / JWT configuration
- Default rate limits
- Dockerfile and CI/deploy workflow defaults

**Out of scope:**

- Vulnerabilities in upstream dependencies — report those to the upstream
  project. (Run `pip-audit` / `npm audit` locally to check.)
- Issues only present in heavily-modified forks
- Issues requiring privileged local access or non-default insecure
  configurations (e.g., setting `DEBUG=true` in production, choosing a
  short `JWT_SECRET` against the startup check's advice)
- Theoretical issues without a demonstrable impact

## Hardening already in place

Before reporting, note that Baseplate already addresses the common
issues:

- bcrypt password hashing
- JWT in `HttpOnly` + `SameSite=Lax` + `Secure` cookies
- 32-byte minimum `JWT_SECRET` enforced at startup in non-debug mode
- CSRF middleware (double-submit cookie) on all non-safe, non-exempt writes
- Per-endpoint rate limiting (5/min on login)
- Identical responses for "wrong password" vs "unknown user" (no enumeration)
- Containers run as non-root (uid 1000)
- Multi-stage backend image; no build tools in runtime

If you're reporting something in this list, please include the angle from
which the existing protection fails.
