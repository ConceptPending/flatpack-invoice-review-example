import pytest

from tests.conftest import TEST_ADMIN_EMAIL


async def _login(client) -> str:
    """Log in and return the CSRF token. Cookies (access_token + csrf_token)
    are stored on the client automatically; callers must echo the returned
    token in an X-CSRF-Token header on writes."""
    resp = await client.post(
        "/api/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": "testpass"},
    )
    assert resp.status_code == 200
    return resp.cookies["csrf_token"]


@pytest.mark.asyncio
async def test_create_item(client):
    csrf = await _login(client)
    response = await client.post(
        "/api/admin/items",
        json={"name": "Test Item", "description": "A test item"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Item"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_items(client):
    csrf = await _login(client)

    await client.post(
        "/api/admin/items",
        json={"name": "Listed Item"},
        headers={"X-CSRF-Token": csrf},
    )

    response = await client.get("/api/admin/items")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_update_item(client):
    csrf = await _login(client)

    create_resp = await client.post(
        "/api/admin/items",
        json={"name": "Original Name"},
        headers={"X-CSRF-Token": csrf},
    )
    assert create_resp.status_code == 201
    item_id = create_resp.json()["id"]

    response = await client.patch(
        f"/api/admin/items/{item_id}",
        json={"name": "Updated Name", "is_active": False},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"
    assert response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_item(client):
    csrf = await _login(client)

    create_resp = await client.post(
        "/api/admin/items",
        json={"name": "To Delete"},
        headers={"X-CSRF-Token": csrf},
    )
    assert create_resp.status_code == 201
    item_id = create_resp.json()["id"]

    response = await client.delete(
        f"/api/admin/items/{item_id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_public_items(client):
    response = await client.get("/api/public/items")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
