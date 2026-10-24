"""Tasks: own tasks, giving tasks needs tasks.assign, status/outcome, filters, privacy."""
from tests.conftest import HDR, login, make_user


async def test_own_task_lifecycle(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    r = await client.post("/api/v1/tasks", json={"title": "Call Al Noor", "due_at": "2020-01-01T10:00:00Z"}, headers=HDR)
    assert r.status_code == 201 and r.json()["source"] == "own" and r.json()["overdue"] is True
    tid = r.json()["id"]
    assert [t["id"] for t in (await client.get("/api/v1/tasks?due=overdue")).json()] == [tid]
    r = await client.patch(f"/api/v1/tasks/{tid}", json={"status": "done", "outcome": "Sent quote"}, headers=HDR)
    assert r.json()["status"] == "done" and r.json()["completed_at"] and not r.json()["overdue"]
    assert (await client.get("/api/v1/tasks/stats")).json() == {"total": 1, "done": 1, "pending": 0, "overdue": 0}


async def test_giving_tasks_needs_permission(client):
    await make_user("a@kjsindia.com")
    await make_user("b@kjsindia.com")
    await login(client, "a@kjsindia.com")
    r = await client.post("/api/v1/tasks", json={"title": "Do my work", "assignee_id": 2}, headers=HDR)
    assert r.status_code == 403 and r.json()["details"]["needs"] == "tasks.assign"
    assert (await client.get("/api/v1/tasks?assignee_id=2")).status_code == 403


async def test_manager_gives_task_and_assignee_is_notified(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "tasks.assign"])
    await make_user("b@kjsindia.com")
    await login(client, "boss@kjsindia.com")
    staff = {c["name"]: c["id"] for c in (await client.get("/api/v1/employee/colleagues")).json()}
    r = await client.post("/api/v1/tasks", json={"title": "Prepare samples", "assignee_id": staff["b"]}, headers=HDR)
    assert r.status_code == 201 and r.json()["source"] == "manager"
    tid = r.json()["id"]
    assert len((await client.get("/api/v1/tasks?assignee_id=0")).json()) == 1

    await login(client, "b@kjsindia.com")
    mine = (await client.get("/api/v1/tasks")).json()
    assert [t["title"] for t in mine] == ["Prepare samples"] and mine[0]["created_by_name"] == "boss"
    assert (await client.get("/api/v1/employee/notifications")).json()["unread"] == 1
    assert (await client.patch(f"/api/v1/tasks/{tid}", json={"status": "doing"}, headers=HDR)).json()["status"] == "doing"


async def test_other_peoples_tasks_are_private(client):
    await make_user("a@kjsindia.com")
    await make_user("b@kjsindia.com")
    await login(client, "a@kjsindia.com")
    tid = (await client.post("/api/v1/tasks", json={"title": "Secret"}, headers=HDR)).json()["id"]
    await login(client, "b@kjsindia.com")
    assert (await client.get("/api/v1/tasks")).json() == []
    assert (await client.patch(f"/api/v1/tasks/{tid}", json={"status": "done"}, headers=HDR)).status_code == 404


async def test_tasks_need_login(client):
    assert (await client.get("/api/v1/tasks")).status_code == 401
