"""One config/<feature>.ini per feature: values apply live, bad values are refused, the portal gets its limits."""
import pytest

from app.core.config import ini
from tests.conftest import HDR, login, make_user
from tests.test_chat import _channel, _send, _team
from tests.test_complaints import GOOD

NEW_FILES = ("chat", "leads", "attendance", "notifications", "harvest", "boards", "analytics")


def _set(monkeypatch, name: str, value) -> ini.Config:
    monkeypatch.setenv(f"KJS__{name.upper()}", str(value))
    return ini.reload_now()


def test_every_feature_file_is_in_the_repo_and_valid():
    for name in NEW_FILES:
        assert (ini.CONFIG_DIR / f"{name}.ini").exists(), name
    assert ini.FILES["chat"] == "chat.ini"
    ini.reload_now()  # the repo files themselves pass validation (else this keeps the defaults, below)
    assert ini._store.loaded_from_files


def test_missing_files_use_the_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(ini, "CONFIG_DIR", tmp_path)  # an empty folder, e.g. a server without the new files
    c = ini.reload_now()
    assert (c.chat.body_max, c.leads.import_max_rows, c.boards.max_days, c.app.job_timeout_seconds) == (4000, 500, 730, 300)


def test_list_keys_come_from_the_field_types():
    assert {("alerts", "thresholds"), ("alerts", "channels"), ("storage", "allowed_types")} <= ini.LIST_FIELDS
    assert ini._is_list(list[str] | None) and not ini._is_list(str)


def test_a_list_key_is_split_only_in_its_own_file(monkeypatch):
    """`channels` is a list in alerts.ini; the same name in another file must stay as written."""
    monkeypatch.setattr(ini, "LIST_FIELDS", {("alerts", "channels")})
    monkeypatch.setenv("KJS__ALERTS__CHANNELS", "in_app, email")
    monkeypatch.setenv("KJS__APP__CHANNELS", "a, b")
    raw = ini._read_raw()
    assert raw["alerts"]["channels"] == ["in_app", "email"] and raw["app"]["channels"] == "a, b"


@pytest.mark.parametrize("key, bad", [("chat__body_max", 0), ("leads__import_max_rows", -1),
                                      ("boards__max_days", 999999), ("complaints__min_title_words", 0),
                                      # uploads: nginx stops anything over 26 MB, so more can never work
                                      ("assign__import_max_mb", 26), ("leads__file_max_mb", 26),
                                      ("storage__max_upload_mb", 26)])
def test_a_value_that_would_break_a_feature_is_refused(monkeypatch, key, bad):
    before = ini.reload_now().model_dump()
    _set(monkeypatch, key, bad)
    assert ini.cfg().model_dump() == before  # the last good config stays


def test_koko_http_timeout_cannot_exceed_the_whole_call(monkeypatch):
    _set(monkeypatch, "koko__http_timeout_seconds", 30)
    assert ini.cfg().koko.http_timeout_seconds == 20  # 30 > timeout_seconds 25: refused


async def test_me_sends_the_portal_limits(client, monkeypatch):
    await make_user("e@kjsindia.com")
    me = (await login(client, "e@kjsindia.com")).json()
    assert me["limits"] == {"chat_body_max": 4000, "chat_page_max": 100, "complaint_min_title_words": 3,
                            "complaint_min_description_words": 15}
    _set(monkeypatch, "chat__body_max", 500)
    assert (await client.get("/api/v1/auth/me")).json()["limits"]["chat_body_max"] == 500


async def test_chat_body_max_applies_live(client, monkeypatch):
    ids = await _team("asha", "ravi")
    await login(client, "asha@kjsindia.com")
    cid = (await _channel(client, member_ids=[ids["ravi"]]))["id"]
    assert (await _send(client, cid, "x" * 150)).status_code == 201
    _set(monkeypatch, "chat__body_max", 100)
    r = await _send(client, cid, "x" * 150)
    assert r.status_code == 422 and "100 characters" in r.text


async def test_complaint_word_minimum_applies_live(client, monkeypatch):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    _set(monkeypatch, "complaints__min_title_words", 6)
    r = await client.post("/api/v1/complaints", json=GOOD, headers=HDR)  # its title has 4 words
    assert r.status_code == 422 and "at least 6 words" in r.text


async def test_chat_catch_up_is_capped_but_a_normal_page_too_big_is_refused(client, monkeypatch):
    ids = await _team("asha", "ravi")
    await login(client, "asha@kjsindia.com")
    cid = (await _channel(client, member_ids=[ids["ravi"]]))["id"]
    first = (await _send(client, cid, "msg 0")).json()["id"]
    for i in range(1, 13):
        await _send(client, cid, f"msg {i}")
    _set(monkeypatch, "chat__page_max", 10)
    url = f"/api/v1/chat/channels/{cid}/messages"
    assert (await client.get(f"{url}?limit=100")).status_code == 422  # a normal load: refused
    r = await client.get(f"{url}?after={first}&limit=100")  # an open tab catching up with the old number
    assert r.status_code == 200 and len(r.json()["messages"]) == 10 and r.json()["has_more"]


def test_board_message_names_the_configured_days(monkeypatch):
    from datetime import date

    from app.api.v1.endpoints.boards import _check_dates
    _set(monkeypatch, "boards__max_days", 30)
    with pytest.raises(ValueError, match="at most 30 days"):
        _check_dates(date(2026, 1, 1), date(2026, 3, 1))


async def test_analytics_sends_its_window_sizes(client, monkeypatch):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    _set(monkeypatch, "analytics__attendance_days", 7)
    a = (await client.get("/api/v1/admin/analytics")).json()
    assert a["attendance_days"] == 7 and len(a["attendance"]) == 7 and a["tasks_days"] == 30


async def test_a_huge_lead_import_is_refused_before_its_rows_are_read(client, monkeypatch):
    await make_user("e@kjsindia.com", permissions=["leads.view"])
    await login(client, "e@kjsindia.com")
    _set(monkeypatch, "leads__import_max_rows", 1)
    r = await client.post("/api/v1/employee/leads/import", json={"leads": [{}, {}]}, headers=HDR)
    # broken rows, but the count is checked first: one clear message, not one error per row
    assert r.status_code == 422 and "At most 1 leads" in r.text
