"""Order boards, History tab (PR 3): every change on a board, newest first, readable sentences, read
only. Everyone on the board may read it; nobody can edit it (the audit log's trigger)."""
import pytest
from sqlalchemy import text

from app.core.database import engine
from tests.conftest import HDR, login
from tests.test_board_people import B, _create_as_plain_owner, _team


async def _texts(client, url=f"{B}/history") -> list[str]:
    r = await client.get(url)
    assert r.status_code == 200, r.text
    return [f"{i['who']}: {i['text']}" for i in r.json()["items"]]


async def test_history_tells_the_story_newest_first_including_deleted_files(client):
    ids = await _team()
    b = await _create_as_plain_owner(client, ids)
    step1 = b["steps"][0]["id"]

    await login(client, "blend@kjsindia.com")
    await client.post(f"{B}/steps/{step1}/checklist", json={"index": 0, "done": True}, headers=HDR)
    fid = (await client.post("/api/v1/files", data={"owner_type": "board", "owner_id": "ABC117-3"},
                             files={"file": ("old-label.pdf", b"%PDF", "application/pdf")}, headers=HDR)).json()["id"]
    await client.post(f"/api/v1/files/{fid}/delete-request", json={"reason": "wrong version"}, headers=HDR)

    await login(client, "owner@kjsindia.com")
    await client.post(f"/api/v1/files/{fid}/delete-decision", json={"approve": True}, headers=HDR)
    await client.post(f"{B}/people", json={"user_id": ids["extra"]}, headers=HDR)
    await client.put(f"{B}/steps/{step1}/people", json={"member_ids": [ids["blend"], ids["extra"]],
                                                       "head_ids": [ids["extra"]]}, headers=HDR)
    await client.put(f"{B}/steps/{step1}/people", json={"member_ids": [ids["extra"]], "head_ids": [ids["extra"]]},
                     headers=HDR)
    await client.delete(f"{B}/people/{ids['blend']}", headers=HDR)

    await login(client, "pack@kjsindia.com")  # anyone on the board reads it
    assert await _texts(client) == [
        "owner: removed blend from the board",
        "owner: changed the people on step 1: took off blend",
        "owner: changed the people on step 1: added extra; head now extra",
        "owner: added extra to the board",
        "owner: approved deleting old-label.pdf",  # the file is gone, its history isn't
        'blend: asked to delete old-label.pdf: "wrong version"',
        "blend: uploaded old-label.pdf",
        'blend: ticked "Batch record signed" on step 1',
        "owner: created the board (2 steps, deadline 07 Nov 2026)",
    ]


async def test_history_pages_back_and_shows_only_this_board(client):
    ids = await _team()
    b = await _create_as_plain_owner(client, ids)
    await login(client, "blend@kjsindia.com")
    for done in (True, False, True):
        await client.post(f"{B}/steps/{b['steps'][0]['id']}/checklist", json={"index": 0, "done": done}, headers=HDR)

    # A second board's changes stay on that board
    await login(client, "owner@kjsindia.com")
    async with engine.begin() as conn:  # the owner lost boards.manage; give it back to create another board
        await conn.execute(text("UPDATE users SET permissions = '[\"leads.view\", \"boards.manage\"]' WHERE id = :i"),
                           {"i": ids["owner"]})
    body = {"code": "XYZ1-1", "name": "Other", "client": "Other client", "start": "2026-10-26", "deadline": "2026-11-07",
            "steps": [{"name": "Only", "percent": 100, "member_ids": [ids["pack"]], "checklist": ["x"]}]}
    assert (await client.post("/api/v1/boards", json=body, headers=HDR)).status_code == 201
    await client.post("/api/v1/boards/XYZ1-1/finish", json={"final_status": "Cancelled"}, headers=HDR)

    first = (await client.get(f"{B}/history?limit=2")).json()
    assert [i["action"] for i in first["items"]] == ["board.check_ticked", "board.check_unticked"]
    assert first["more"] is True
    rest = (await client.get(f"{B}/history?limit=2&before_id={first['items'][-1]['id']}")).json()
    assert [i["action"] for i in rest["items"]] == ["board.check_ticked", "board.created"]
    assert rest["more"] is False
    every = (await client.get(f"{B}/history?limit=100")).json()["items"]
    assert "board.finished" not in [i["action"] for i in every]  # XYZ1-1 was closed; ABC117-3 wasn't


async def test_an_odd_old_row_never_breaks_the_tab_and_no_emails_show(client):
    ids = await _team()
    await _create_as_plain_owner(client, ids)
    async with engine.begin() as conn:  # rows can be added (never changed): one with a missing deadline
        await conn.execute(text(
            "INSERT INTO audit_log (actor_id, actor_label, action, entity_type, entity_id, after) "
            "VALUES (NULL, 'Ghost (ghost@kjsindia.com)', 'board.created', 'board', 'ABC117-3', '{\"deadline\": null}')"))
    await login(client, "blend@kjsindia.com")
    top = (await client.get(f"{B}/history")).json()["items"][0]
    assert top["who"] == "Ghost" and top["text"] == "made a change (board.created)"


async def test_history_only_for_people_on_the_board(client):
    ids = await _team()
    await _create_as_plain_owner(client, ids)
    await login(client, "stranger@kjsindia.com")
    assert (await client.get(f"{B}/history")).status_code == 404
    client.cookies.clear()
    assert (await client.get(f"{B}/history")).status_code == 401
    await login(client, "extra@kjsindia.com")  # not added yet
    assert (await client.get(f"{B}/history")).status_code == 404


async def test_history_lines_cannot_be_edited():
    """The audit log is append-only (trigger from the first migration): history can't be rewritten."""
    async with engine.begin() as conn:
        await conn.execute(text("INSERT INTO audit_log (actor_label, action, entity_type, entity_id) "
                                "VALUES ('x', 'board.created', 'board', 'ABC117-3')"))
    with pytest.raises(Exception, match="append-only"):
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE audit_log SET actor_label = 'someone else'"))
