import asyncio
import os

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Must set env vars BEFORE any app imports
_TEST_PASSWORD = "testpass"
_TEST_HASH = bcrypt.hashpw(_TEST_PASSWORD.encode(), bcrypt.gensalt()).decode()
TEST_ADMIN_EMAIL = "admin@example.com"

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["JWT_SECRET"] = "test-secret-not-for-production-use-only"
os.environ["ADMIN_EMAIL"] = TEST_ADMIN_EMAIL
os.environ["ADMIN_PASSWORD_HASH"] = _TEST_HASH
os.environ["COOKIE_SECURE"] = "false"

from app.models.base import Base  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    try:
        import aiosqlite  # noqa: F401
    except ImportError:
        pytest.skip("aiosqlite not installed")

    engine = create_async_engine("sqlite+aiosqlite:///./test.db", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed the test admin user. Lifespan doesn't run under ASGITransport, so
    # we do here what bootstrap.ensure_admin_user would do in real startup.
    from app.services.users import UserService

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        await UserService.create(
            session,
            email=TEST_ADMIN_EMAIL,
            password_hash=_TEST_HASH,
            is_admin=True,
        )

    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    from app.database import get_db
    from app.main import app
    from app.rate_limit import limiter

    # Per-IP rate-limit state would otherwise leak across tests.
    limiter.reset()

    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
