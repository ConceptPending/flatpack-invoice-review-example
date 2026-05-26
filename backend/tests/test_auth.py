import pytest

from tests.conftest import TEST_ADMIN_EMAIL


@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    response = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password_same_as_unknown_user(client):
    """Wrong password and unknown user must return identical responses."""
    unknown = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
    )
    wrong_pw = await client.post(
        "/api/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": "wrong"},
    )
    assert unknown.status_code == wrong_pw.status_code == 401
    assert unknown.json() == wrong_pw.json()


@pytest.mark.asyncio
async def test_login_success(client):
    response = await client.post(
        "/api/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": "testpass"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Login successful"
    assert "access_token" in response.cookies
    assert "csrf_token" in response.cookies


@pytest.mark.asyncio
async def test_login_email_case_insensitive(client):
    """Emails are normalized; mixed-case still authenticates."""
    response = await client.post(
        "/api/auth/login",
        json={"email": TEST_ADMIN_EMAIL.upper(), "password": "testpass"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_me_returns_user(client):
    await client.post(
        "/api/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": "testpass"},
    )
    response = await client.get("/api/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == TEST_ADMIN_EMAIL
    assert body["is_admin"] is True
    assert "id" in body
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_logout(client):
    """Logout is a state-changing write — it requires CSRF after login."""
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": "testpass"},
    )
    csrf = login_resp.cookies["csrf_token"]
    response = await client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_protected_endpoint_without_auth(client):
    response = await client.get("/api/admin/items")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limited(client):
    """6th login attempt within a minute should be rate-limited (429)."""
    for _ in range(5):
        await client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "wrong"},
        )
    response = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
    )
    assert response.status_code == 429
