"""Every protected route: one allowed case and one forbidden case (project rule)."""
import pytest

from tests.conftest import HDR, login, make_user

# (method, path, permission it needs, json body)
ROUTES = [
    ("get", "/api/v1/admin/stats", "staff.approve", None),
    ("get", "/api/v1/admin/users", "staff.approve", None),
    ("get", "/api/v1/admin/permissions", "staff.approve", None),
    ("get", "/api/v1/admin/audit", "audit.view", None),
    ("post", "/api/v1/admin/products", "catalog.edit", {"category_slug": "coffee", "name": "Test Coffee"}),
    ("get", "/api/v1/employee/leads", "leads.view", None),
]


@pytest.mark.parametrize("method,path,perm,body", ROUTES)
async def test_not_logged_in_gets_401(client, method, path, perm, body):
    r = await client.request(method, path, json=body, headers=HDR)
    assert r.status_code == 401


@pytest.mark.parametrize("method,path,perm,body", ROUTES)
async def test_employee_without_permission_gets_403(client, method, path, perm, body):
    await make_user("e@kjsindia.com", permissions=[])  # no extras
    await login(client, "e@kjsindia.com")
    r = await client.request(method, path, json=body, headers=HDR)
    if perm == "leads.view":  # every employee has this by default
        assert r.status_code in (200, 201)
    else:
        assert r.status_code == 403 and r.json()["details"]["needs"] == perm


@pytest.mark.parametrize("method,path,perm,body", ROUTES)
async def test_employee_with_permission_allowed(client, method, path, perm, body):
    await make_user("e@kjsindia.com", permissions=[perm])
    await login(client, "e@kjsindia.com")
    r = await client.request(method, path, json=body, headers=HDR)
    assert r.status_code in (200, 201), r.text


@pytest.mark.parametrize("method,path,perm,body", ROUTES)
async def test_admin_allowed(client, method, path, perm, body):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    r = await client.request(method, path, json=body, headers=HDR)
    assert r.status_code in (200, 201), r.text


async def test_post_without_csrf_header_rejected(client):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    r = await client.post("/api/v1/admin/products", json={"category_slug": "coffee", "name": "X Coffee"})
    assert r.status_code == 403 and r.json()["code"] == "csrf"
