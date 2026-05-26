"""Dump the FastAPI app's OpenAPI schema to stdout.

Used by `make generate-client` to produce TypeScript types in the frontend
without needing the backend server to be running. Importing `app.main` is
side-effect-light (it creates the FastAPI instance and registers middleware
+ routes, but doesn't open a database connection or start the lifespan).

Run with DEBUG=true so the config's startup validation doesn't kill the
process when ADMIN_PASSWORD_HASH / JWT_SECRET aren't set locally.
"""

import json

from app.main import app

print(json.dumps(app.openapi()))
