from slowapi import Limiter
from slowapi.util import get_remote_address

# Default limit applies to every route; tighten per-endpoint with
# `@limiter.limit("N/period")` on a specific handler. See `api/auth.login`
# for an example.
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
