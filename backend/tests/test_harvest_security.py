"""Lead Harvester security fix (after the PR #53 review): no secret leak, no SSRF, assign.manage only.
See app/services/harvest_net.py for the rules. No real internet: host look-ups and responses are faked."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import Request, Response

from app.core.errors import AppError
from app.models.harvest import HarvestSource
from app.services import harvest_net
from app.services.harvest_net import check_env_name, check_url, is_public_ip, safe_get
from app.services.harvest_service import fetch_api_source
from tests.conftest import HDR, login, make_user

PUBLIC = "93.184.216.34"


def fake_dns(monkeypatch, table: dict[str, list[str]]):
    async def resolve(host, port):
        return table.get(host, [PUBLIC])
    monkeypatch.setattr(harvest_net, "resolve", resolve)


def answers(*responses):
    """Fake httpx.AsyncClient.get answering in order; returns the mock (to look at what was sent)."""
    mock = AsyncMock()
    mock.side_effect = list(responses)
    return mock


def ok(body="{}"):
    return Response(200, request=Request("GET", "https://x"), text=body)


def redirect(to: str):
    return Response(302, request=Request("GET", "https://x"), headers={"location": to})


# ---------- setting names ----------

def test_only_harvest_setting_names_are_allowed():
    assert check_env_name("") == ""
    assert check_env_name(" HARVEST_INDIAMART_KEY ") == "HARVEST_INDIAMART_KEY"
    for bad in ("DATABASE_URL", "SECRET_KEY", "harvest_key", "HARVEST_", "HARVEST_KEY;rm"):
        with pytest.raises(ValueError) as e:
            check_env_name(bad)
        assert "HARVEST_" in str(e.value)
    with pytest.raises(ValueError, match="rename DATABASE_URL to HARVEST_DATABASE_URL"):
        check_env_name("DATABASE_URL")


async def test_a_bad_setting_name_already_in_the_database_is_never_read(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://secret")
    source = HarvestSource(name="x", source_type="api", url="https://api.example.com/x", auth_env_var="DATABASE_URL")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as get:
        with pytest.raises(AppError) as e:
            await fetch_api_source(source)
    assert e.value.code == "bad_env_var" and get.call_count == 0  # refused before anything was sent


# ---------- addresses (when saving) ----------

def test_addresses_must_be_public_https():
    assert check_url("https://api.indiamart.com/enquiries?page=1")
    for bad in ("http://api.example.com/x", "https://localhost/x", "https://LOCALHOST./x", "https://intranet/x",
                "https://db.internal/x", "https://10.0.0.5/x", "https://192.168.1.1/x", "https://127.0.0.1/x",
                "https://169.254.169.254/latest/meta-data", "https://[::1]/x", "https://[::ffff:10.0.0.1]/x",
                "https://user:pw@api.example.com/x", "ftp://example.com/x", "not a url"):
        with pytest.raises(ValueError):
            check_url(bad)


def test_plain_http_only_for_hosts_an_admin_allowed(monkeypatch):
    monkeypatch.setenv("HARVEST_ALLOW_HTTP_HOSTS", "feeds.example.gov.in, OTHER.example.com")
    assert check_url("http://feeds.example.gov.in/rss")
    assert check_url("http://other.example.com/rss")
    with pytest.raises(ValueError):
        check_url("http://api.example.com/x")


def test_public_ip_rule():
    assert is_public_ip("8.8.8.8") and is_public_ip(PUBLIC)
    for bad in ("10.1.2.3", "172.16.0.1", "192.168.0.1", "127.0.0.1", "169.254.169.254", "0.0.0.0",
                "::1", "fc00::1", "fe80::1", "::ffff:10.0.0.1", "224.0.0.1", "nonsense"):
        assert not is_public_ip(bad), bad


# ---------- fetching ----------

async def test_a_host_that_points_inside_is_refused(monkeypatch):
    fake_dns(monkeypatch, {"evil.example.com": ["10.0.0.5", "127.0.0.1"]})
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as get:
        with pytest.raises(AppError) as e:
            await safe_get("https://evil.example.com/x")
    assert e.value.code == "blocked_address" and get.call_count == 0


async def test_mixed_addresses_connect_only_to_a_checked_public_one(monkeypatch):
    fake_dns(monkeypatch, {"cdn.example.com": ["10.0.0.5", PUBLIC]})
    get = answers(ok())
    with patch("httpx.AsyncClient.get", get):
        await safe_get("https://cdn.example.com/feed?x=1")
    url = get.call_args.args[0]
    assert url == f"https://{PUBLIC}/feed?x=1"  # the address we checked, not the name
    assert get.call_args.kwargs["headers"]["Host"] == "cdn.example.com"
    assert get.call_args.kwargs["extensions"] == {"sni_hostname": "cdn.example.com"}  # https checked for the real name


async def test_redirects_are_checked_every_time(monkeypatch):
    fake_dns(monkeypatch, {})
    with patch("httpx.AsyncClient.get", answers(redirect("https://169.254.169.254/latest/meta-data"))):
        with pytest.raises(AppError, match="public website"):
            await safe_get("https://api.example.com/x")
    fake_dns(monkeypatch, {"inside.example.com": ["10.0.0.9"]})
    with patch("httpx.AsyncClient.get", answers(redirect("https://inside.example.com/admin"))):
        with pytest.raises(AppError, match="internal address"):
            await safe_get("https://api.example.com/x")


async def test_https_to_http_redirect_is_refused_even_for_an_allowed_host(monkeypatch):
    fake_dns(monkeypatch, {})
    monkeypatch.setenv("HARVEST_ALLOW_HTTP_HOSTS", "api.example.com")
    with patch("httpx.AsyncClient.get", answers(redirect("http://api.example.com/x"))):
        with pytest.raises(AppError, match="https to plain http"):
            await safe_get("https://api.example.com/x")


async def test_relative_redirects_work_and_too_many_are_refused(monkeypatch):
    fake_dns(monkeypatch, {})
    get = answers(redirect("/v2/feed"), ok("done"))
    with patch("httpx.AsyncClient.get", get):
        assert (await safe_get("https://api.example.com/v1/feed")).text == "done"
    assert get.call_args.args[0] == f"https://{PUBLIC}/v2/feed"
    loop = [redirect(f"https://api.example.com/{i}") for i in range(harvest_net.MAX_REDIRECTS + 1)]
    with patch("httpx.AsyncClient.get", answers(*loop)):
        with pytest.raises(AppError, match="Too many redirects"):
            await safe_get("https://api.example.com/0")


async def test_the_api_key_only_goes_to_the_sources_own_host_over_https(monkeypatch):
    fake_dns(monkeypatch, {})
    get = answers(redirect("https://elsewhere.example.com/x"), ok())
    with patch("httpx.AsyncClient.get", get):
        await safe_get("https://api.example.com/x", api_key="k123")
    first, second = (c.kwargs["headers"] for c in get.call_args_list)
    assert first["Authorization"] == "Bearer k123" and "Authorization" not in second

    monkeypatch.setenv("HARVEST_ALLOW_HTTP_HOSTS", "plain.example.com")
    get = answers(ok())
    with patch("httpx.AsyncClient.get", get):
        await safe_get("http://plain.example.com/x", api_key="k123")
    assert "Authorization" not in get.call_args.kwargs["headers"]  # never over plain http


# ---------- the API ----------

async def test_only_assign_manage_can_use_harvesters(client):
    for email, perms in (("viewer@kjsindia.com", ["leads.view", "leads.view_all"]),
                         ("approver@kjsindia.com", ["leads.view", "staff.approve"])):
        await make_user(email, permissions=perms)
        await login(client, email)
        assert (await client.get("/api/v1/admin/harvest/sources", headers=HDR)).status_code == 403
        r = await client.post("/api/v1/admin/harvest/sources", headers=HDR,
                              json={"name": "x1", "source_type": "rss", "url": "https://feeds.example.com/x"})
        assert r.status_code == 403


async def test_create_and_edit_refuse_secrets_and_internal_addresses(client):
    await make_user("manager@kjsindia.com", permissions=["leads.view", "assign.manage"])
    await login(client, "manager@kjsindia.com")
    base = {"name": "IndiaMART", "source_type": "api", "url": "https://api.indiamart.com/x"}
    r = await client.post("/api/v1/admin/harvest/sources", json=base | {"auth_env_var": "DATABASE_URL"}, headers=HDR)
    assert r.status_code == 422 and "HARVEST_" in r.text
    r = await client.post("/api/v1/admin/harvest/sources", json=base | {"url": "http://169.254.169.254/"}, headers=HDR)
    assert r.status_code == 422
    r = await client.post("/api/v1/admin/harvest/sources", json=base | {"auth_env_var": "HARVEST_INDIAMART_KEY"},
                          headers=HDR)
    assert r.status_code == 201
    sid = r.json()["id"]
    # Editing used to skip every check
    for bad in ({"auth_env_var": "SECRET_KEY"}, {"url": "https://localhost/admin"}, {"url": "https://10.0.0.1/"}):
        r = await client.put(f"/api/v1/admin/harvest/sources/{sid}", json=bad, headers=HDR)
        assert r.status_code == 422, bad
    r = await client.put(f"/api/v1/admin/harvest/sources/{sid}", json={"url": "https://api.indiamart.com/v2"}, headers=HDR)
    assert r.status_code == 200 and r.json()["url"] == "https://api.indiamart.com/v2"
