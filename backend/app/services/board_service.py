"""Order boards: plan steps on working days, run them, alert when a step uses up its time.

Planning (pure functions, unit tested):
- The board has a start date and a deadline. Working days = Mon–Sat minus holidays.
- percent mode: each step gets its % of the board's working days (at least 1 day);
  rounding is fixed on the last step so the plan ends exactly on the deadline.
- days mode: each step gets a fixed number of working days, one after another. If they
  don't fit before the deadline the plan says so (`plan_late`), it doesn't refuse.

People (migration 0016):
- The owner is the person who created the board. The owner and `boards.manage` add and remove
  people, change a step's assignees and head, finish the board, and approve file deletes.
- Everyone on the board sees it and updates it (checklists, files). Only a step's assignees
  (its head included), the owner or `boards.manage` mark that step done.
- The plan (dates, step sizes, adding / renaming / removing / reordering steps) can change at any
  time: by anyone on the board while it is unlocked, only by the owner or boards.manage once the
  owner locks it. Only steps that haven't started can be removed or moved.
- Every step keeps at least one assignee. Nothing is deleted for good: removing someone only ends
  their access (their uploads and the history stay), and every change is in the audit log.

Running:
- Creating a board starts step 1. Marking a step done starts the next one.
- Starting a step gives each of its members the step's task templates as tasks.
- The `board_alerts` job tells the step members and board managers when a running step has
  used 50 / 85 / 100 % of its planned time (thresholds in config/alerts.ini), once each.
"""
import logging
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import case, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.errors import AppError
from app.core.permissions import effective_permissions
from app.jobs.runner import job
from app.models.audit import AuditLog
from app.models.file import StoredFile
from app.models.order_board import BoardMember, BoardPerson, BoardStep, OrderBoard
from app.models.task import Task
from app.models.user import User
from app.services import audit_service, file_service, notification_service, task_service
from app.services.attendance_service import local_day, to_utc
from app.services.calendar_service import CalendarService, holiday_set

log = logging.getLogger(__name__)
CODE_RE = re.compile(r"^[A-Z0-9]{2,12}-[0-9]{1,6}$")


# ---------- Planning maths ----------
def working_days(start: date, count_at_least: int, until: date, holidays: set[date]) -> list[date]:
    """Working days from `start`, through `until`, and longer if we need `count_at_least` of them."""
    out, d = [], start
    while d <= until or len(out) < count_at_least:
        if CalendarService.is_working_day(d, holidays):
            out.append(d)
        d += timedelta(days=1)
    return out


def plan_steps(start: date, deadline: date, mode: str, sizes: list[int], holidays: set[date]) -> tuple[list[tuple[date, date]], bool]:
    """sizes = percents (percent mode) or working days (days mode). Returns ([(start, end)], plan_late)."""
    if deadline < start:
        raise AppError(422, "bad_dates", "The deadline is before the start.")
    available = CalendarService.working_days_between(start, deadline, holidays)
    if available == 0:
        raise AppError(422, "bad_dates", "There are no working days between start and deadline.")
    if not sizes or any(s <= 0 for s in sizes):
        raise AppError(422, "bad_steps", "Every step needs a size above 0.")
    if mode == "percent":
        if sum(sizes) != 100:
            raise AppError(422, "bad_steps", f"Step percentages must add up to 100 (now {sum(sizes)}).")
        if len(sizes) > available:
            raise AppError(422, "bad_steps", f"{len(sizes)} steps don't fit in {available} working days.")
        counts = [max(1, int(available * s / 100 + 0.5)) for s in sizes]  # normal rounding (2.5 -> 3)
        while sum(counts) > available:  # rounding pushed us over: take from the biggest step
            counts[counts.index(max(counts))] -= 1
        counts[-1] += available - sum(counts)  # rounding left days: give them to the last step
    else:
        counts = list(sizes)
    days = working_days(start, sum(counts), deadline, holidays)
    plan, i = [], 0
    for c in counts:
        plan.append((days[i], days[i + c - 1]))
        i += c
    return plan, plan[-1][1] > deadline


def used_pct(step: BoardStep, today: date, holidays: set[date]) -> int:
    """How much of the step's planned working time has passed (can go over 100)."""
    if step.status == "done":
        return 100
    if today < step.planned_start:
        return 0
    planned = max(1, CalendarService.working_days_between(step.planned_start, step.planned_end, holidays))
    # Only days that are over count as used: today is still available (a 1-day step is 0% on its
    # day, not already "out of time").
    elapsed = CalendarService.working_days_between(step.planned_start, today - timedelta(days=1), holidays)
    if today > step.planned_end:  # past the end: count calendar overrun too, so it keeps growing
        elapsed = max(elapsed, planned + (today - step.planned_end).days - 1)
    return round(elapsed / planned * 100)


def board_state(board: OrderBoard, steps: list[BoardStep], today: date, holidays: set[date]) -> str:
    if board.status == "finished":
        return "finished"
    if today > local_day(board.deadline_at):
        return "late_board"
    active = [used_pct(s, today, holidays) for s in steps if s.status == "active"]
    if any(p >= 100 for p in active):
        return "late_board"
    if any(p >= 85 for p in active):
        return "at_risk"
    return "on_track"


# ---------- Access ----------
def can_manage(user: User) -> bool:
    return "boards.manage" in effective_permissions(user.role, user.permissions)


def can_admin(user: User, board: OrderBoard) -> bool:
    """The board's owner, or boards.manage: people, assignees, finishing, file deletes."""
    return can_manage(user) or board.created_by == user.id


async def _board(db: AsyncSession, code: str, lock: bool = False) -> OrderBoard:
    q = select(OrderBoard).where(OrderBoard.code == code.upper())
    if lock:
        q = q.with_for_update().execution_options(populate_existing=True)
    b = await db.scalar(q)
    if b is None:
        raise AppError(404, "not_found", "Order board not found.")
    return b


async def _member_ids(db: AsyncSession, board_id: int, step_id: int | None = None) -> set[int]:
    q = select(BoardMember.user_id).where(BoardMember.board_id == board_id)
    if step_id:
        q = q.where(BoardMember.step_id == step_id)
    return set((await db.scalars(q)).all())


async def _people_ids(db: AsyncSession, board_id: int) -> set[int]:
    return set((await db.scalars(select(BoardPerson.user_id).where(BoardPerson.board_id == board_id))).all())


async def _heads(db: AsyncSession, step_id: int) -> set[int]:
    return set((await db.scalars(select(BoardMember.user_id).where(
        BoardMember.step_id == step_id, BoardMember.is_head.is_(True)))).all())


async def _visible_board(db: AsyncSession, user: User, code: str, lock: bool = False) -> OrderBoard:
    b = await _board(db, code, lock=lock)
    if not can_admin(user, b) and user.id not in await _people_ids(db, b.id):
        raise AppError(404, "not_found", "Order board not found.")
    return b


async def _admin_board(db: AsyncSession, user: User, code: str) -> OrderBoard:
    """A running board whose people this person may change. Locked until commit, so two
    changes to the same board's people can't overwrite each other."""
    b = await _visible_board(db, user, code, lock=True)
    if not can_admin(user, b):
        raise AppError(403, "forbidden", "Only the board's owner can change this.")
    if b.status != "active":
        raise AppError(409, "finished", "This board is finished.")
    return b


async def _active_staff(db: AsyncSession, ids: set[int]) -> set[int]:
    found = set((await db.scalars(select(User.id).where(User.id.in_(ids), User.status == "active"))).all())
    if ids - found:
        raise AppError(422, "bad_members", "Some people are not active staff.", {"ids": sorted(ids - found)})
    return found


async def _files_access(db: AsyncSession, user: User, owner_id: str, action: str) -> bool:
    try:
        await _visible_board(db, user, owner_id)
        return True
    except AppError:
        return False


async def _files_approvers(db: AsyncSession, owner_id: str) -> tuple[set[int], str]:
    """The board's owner may approve deletes of its files (files.approve holders always can)."""
    owner = await db.scalar(select(OrderBoard.created_by).where(OrderBoard.code == owner_id.upper()))
    return ({owner} if owner else set()), f"/employee/order-boards/{owner_id.upper()}"


file_service.register_owner("board", _files_access, approvers=_files_approvers)


# ---------- Create ----------
async def create(db: AsyncSession, user: User, data) -> dict:
    code = data.code.strip().upper()
    if not CODE_RE.match(code):
        raise AppError(422, "bad_code", "Board code looks like ABC117-3 (letters/numbers, dash, number).")
    if await db.scalar(select(OrderBoard.id).where(OrderBoard.code == code)):
        raise AppError(409, "duplicate", f"Board {code} already exists.")
    holidays = await holiday_set(db, data.start.year, data.deadline.year + 1)
    sizes = [(s.percent if data.split_mode == "percent" else s.days) or 0 for s in data.steps]
    plan, plan_late = plan_steps(data.start, data.deadline, data.split_mode, sizes, holidays)

    member_ids = {m for s in data.steps for m in s.member_ids}
    for s in data.steps:
        if not s.member_ids:
            raise AppError(422, "no_assignee", f"Step '{s.name}' needs at least one person.")
        if set(s.head_ids) - set(s.member_ids):
            raise AppError(422, "bad_head", f"The head of '{s.name}' must be one of its people.")
    await _active_staff(db, member_ids)

    c = cfg().app
    board = OrderBoard(code=code, name=data.name.strip(), client=data.client.strip(), priority=data.priority,
                       start_at=to_utc(data.start, c.shift_start), deadline_at=to_utc(data.deadline, c.shift_end),
                       split_mode=data.split_mode, status="active", notes=data.notes, created_by=user.id)
    db.add(board)
    await db.flush()
    for i, (s, (p_start, p_end)) in enumerate(zip(data.steps, plan), start=1):
        step = BoardStep(board_id=board.id, position=i, name=s.name.strip(), percent=s.percent if data.split_mode == "percent" else None,
                         days=s.days if data.split_mode == "days" else None, planned_start=p_start, planned_end=p_end,
                         status="pending", task_templates=[t.strip() for t in s.task_templates if t.strip()],
                         checklist=[{"text": t.strip(), "done": False} for t in s.checklist if t.strip()], alerted_pct=0)
        db.add(step)
        await db.flush()
        for uid in set(s.member_ids):
            db.add(BoardMember(board_id=board.id, step_id=step.id, user_id=uid, is_head=uid in s.head_ids))
    for uid in member_ids | {user.id}:  # everyone on a step, and the owner, is on the board
        db.add(BoardPerson(board_id=board.id, user_id=uid, added_by=user.id))
    await db.flush()
    first = await db.scalar(select(BoardStep).where(BoardStep.board_id == board.id, BoardStep.position == 1))
    await _start_step(db, board, first, user)
    audit_service.record(db, actor=user, action="board.created", entity_type="board", entity_id=code,
                         after={"steps": len(plan), "deadline": data.deadline.isoformat(), "plan_late": plan_late})
    notification_service.notify(db, member_ids - {user.id}, "board.added", f"You are on order board {code}",
                                f"{board.name} for {board.client}.", f"/employee/order-boards/{code}")
    await db.commit()
    return await detail(db, user, code)


async def _start_step(db: AsyncSession, board: OrderBoard, step: BoardStep, actor: User) -> None:
    step.status, step.started_at = "active", datetime.now(timezone.utc)
    due = to_utc(step.planned_end, cfg().app.shift_end)
    for uid in await _member_ids(db, board.id, step.id):
        for title in step.task_templates:
            task_service.add(db, assignee_id=uid, title=f"{board.code} · {step.name}: {title}", source="board",
                             source_ref=f"board:{board.code}:step:{step.position}", due_at=due, created_by=actor.id)
        notification_service.notify(db, [uid], "board.step_started", f"{board.code}: step '{step.name}' started",
                                    f"Planned until {step.planned_end:%d %b}.", f"/employee/order-boards/{board.code}")


# ---------- Read ----------
async def _step_out(db: AsyncSession, s: BoardStep, today: date, holidays: set[date], names: dict[int, str]) -> dict:
    members = await _member_ids(db, s.board_id, s.id)
    heads = await _heads(db, s.id)
    return {"id": s.id, "position": s.position, "name": s.name, "percent": s.percent, "days": s.days,
            "planned_start": s.planned_start, "planned_end": s.planned_end, "status": s.status,
            "started_at": s.started_at, "done_at": s.done_at, "used_pct": used_pct(s, today, holidays),
            "task_templates": s.task_templates, "checklist": s.checklist,
            "members": [{"id": m, "name": names.get(m, ""), "is_head": m in heads}
                        for m in sorted(members, key=lambda m: (m not in heads, names.get(m, "")))]}


async def _board_out(db: AsyncSession, b: OrderBoard, steps: list[BoardStep], today: date, holidays: set[date]) -> dict:
    done = sum(1 for s in steps if s.status == "done")
    current = next((s for s in steps if s.status == "active"), None)
    return {"code": b.code, "name": b.name, "client": b.client, "priority": b.priority,
            "start": local_day(b.start_at), "deadline": local_day(b.deadline_at), "split_mode": b.split_mode,
            "status": b.status, "final_status": b.final_status, "notes": b.notes,
            "state": board_state(b, steps, today, holidays), "steps_done": done, "steps_total": len(steps),
            "current_step": current.name if current else None,
            "current_used_pct": used_pct(current, today, holidays) if current else None}


async def list_boards(db: AsyncSession, user: User, include_finished: bool = False) -> list[dict]:
    # Running boards first (nearest deadline first), then finished ones (newest first), at most 300:
    # finished boards pile up over the years.
    q = (select(OrderBoard)
         .order_by(OrderBoard.status != "active",
                   case((OrderBoard.status == "active", OrderBoard.deadline_at)).asc(),
                   OrderBoard.deadline_at.desc())
         .limit(300))
    if not can_manage(user):
        q = q.where(OrderBoard.id.in_(select(BoardPerson.board_id).where(BoardPerson.user_id == user.id))
                    | (OrderBoard.created_by == user.id))
    if not include_finished:
        q = q.where(OrderBoard.status == "active")
    boards = (await db.scalars(q)).all()
    today = local_day(datetime.now(timezone.utc))
    holidays = await holiday_set(db, today.year - 1, today.year + 1)
    out = []
    for b in boards:
        steps = (await db.scalars(select(BoardStep).where(BoardStep.board_id == b.id).order_by(BoardStep.position))).all()
        out.append(await _board_out(db, b, list(steps), today, holidays))
    return out


async def detail(db: AsyncSession, user: User, code: str) -> dict:
    b = await _visible_board(db, user, code)
    steps = list((await db.scalars(select(BoardStep).where(BoardStep.board_id == b.id).order_by(BoardStep.position))).all())
    today = local_day(datetime.now(timezone.utc))
    holidays = await holiday_set(db, today.year - 1, today.year + 1)
    names = dict((await db.execute(select(User.id, User.name))).all())
    my_steps = [s.id for s in steps if user.id in await _member_ids(db, b.id, s.id)]
    step_rows = [await _step_out(db, s, today, holidays, names) for s in steps]
    on_steps: dict[int, list[int]] = {}
    for st in step_rows:
        for m in st["members"]:
            on_steps.setdefault(m["id"], []).append(st["position"])
    people = sorted(await _people_ids(db, b.id) | ({b.created_by} if b.created_by else set()),
                    key=lambda p: (p != b.created_by, names.get(p, "")))
    return await _board_out(db, b, steps, today, holidays) | {
        "steps": step_rows, "my_step_ids": my_steps, "can_manage": can_manage(user),
        "owner": {"id": b.created_by, "name": names.get(b.created_by or 0, "")},
        "people": [{"id": p, "name": names.get(p, ""), "is_owner": p == b.created_by, "steps": on_steps.get(p, [])}
                   for p in people],
        # can_edit: people, assignees, finishing. can_decide_deletes: approve / reject file delete requests.
        "can_edit": can_admin(user, b), "can_decide_deletes": await file_service.can_decide(db, user, "board", b.code),
        "plan_locked": b.plan_locked, "can_edit_plan": b.status == "active" and (can_admin(user, b) or not b.plan_locked)}


# ---------- Run ----------
async def _step_for_action(db: AsyncSession, user: User, code: str, step_id: int,
                           assignees_only: bool = False) -> tuple[OrderBoard, BoardStep]:
    """Anyone on the board may update a step; with assignees_only, only its assignees (head
    included), the owner or boards.manage may (marking it done)."""
    b = await _visible_board(db, user, code)
    # Locked until commit: a double "done" click would otherwise start the next step twice
    # (duplicate tasks), and two members ticking the checklist at once would lose one tick.
    step = await db.get(BoardStep, step_id, with_for_update=True, populate_existing=True)
    if step is None or step.board_id != b.id:
        raise AppError(404, "not_found", "Step not found.")
    if assignees_only and not can_admin(user, b) and user.id not in await _member_ids(db, b.id, step.id):
        raise AppError(403, "forbidden", "Only this step's people or the board's owner can mark it done.")
    if b.status != "active":
        raise AppError(409, "finished", "This board is finished.")
    return b, step


async def complete_step(db: AsyncSession, user: User, code: str, step_id: int) -> dict:
    b, step = await _step_for_action(db, user, code, step_id, assignees_only=True)
    if step.status != "active":
        raise AppError(409, "not_active", "Only the running step can be marked done.")
    step.status, step.done_at = "done", datetime.now(timezone.utc)
    nxt = await db.scalar(select(BoardStep).where(BoardStep.board_id == b.id, BoardStep.position == step.position + 1))
    if nxt:
        await _start_step(db, b, nxt, user)
    managers = await notification_service.users_with(db, "boards.manage")
    notification_service.notify(db, set(managers) - {user.id}, "board.step_done", f"{b.code}: '{step.name}' done",
                                f"By {user.name}." + (f" Next: {nxt.name}." if nxt else " All steps done."),
                                f"/admin/order-boards/{b.code}")
    audit_service.record(db, actor=user, action="board.step_done", entity_type="board", entity_id=b.code,
                         after={"step": step.position, "name": step.name})
    await db.commit()
    return await detail(db, user, code)


async def toggle_check(db: AsyncSession, user: User, code: str, step_id: int, index: int, done: bool) -> dict:
    b, step = await _step_for_action(db, user, code, step_id)
    if not 0 <= index < len(step.checklist):
        raise AppError(404, "not_found", "Checklist item not found.")
    items = [dict(i) for i in step.checklist]
    items[index]["done"] = done
    step.checklist = items  # new list so SQLAlchemy sees the change
    audit_service.record(db, actor=user, action="board.check_ticked" if done else "board.check_unticked",
                         entity_type="board", entity_id=b.code,
                         after={"step": step.position, "item": items[index].get("text", ""), "done": done})
    await db.commit()
    return await detail(db, user, code)


async def finish(db: AsyncSession, user: User, code: str, final_status: str) -> dict:
    b = await _visible_board(db, user, code, lock=True)
    if not can_admin(user, b):
        raise AppError(403, "forbidden", "Only the board's owner can finish it.")
    if b.status != "active":
        # Finished once, with one outcome: "Delivered" must not later become "Cancelled".
        raise AppError(409, "finished", "This board is already finished.")
    before = {"status": b.status, "final_status": b.final_status}
    b.status, b.final_status = "finished", final_status
    # Its open tasks would otherwise show as overdue on people's lists forever.
    closed = await _close_tasks(db, b.code, f"board finished as {final_status}")
    audit_service.record(db, actor=user, action="board.finished", entity_type="board", entity_id=b.code,
                         before=before, after={"final_status": final_status, "tasks_closed": closed})
    await db.commit()
    return await detail(db, user, code)


async def _close_tasks(db: AsyncSession, code: str, why: str, user_id: int | None = None,
                       step_position: int | None = None) -> int:
    """Close open board tasks (all of a board, one person's, or one step's) so they don't show as
    overdue forever. Marked done with a note saying why; never deleted."""
    q = update(Task).where(Task.source == "board", Task.status != "done")
    if step_position is not None:
        q = q.where(Task.source_ref == f"board:{code}:step:{step_position}")
    else:
        q = q.where(Task.source_ref.startswith(f"board:{code}:"))
    if user_id is not None:
        q = q.where(Task.assignee_id == user_id)
    return (await db.execute(q.values(status="done", notes=Task.notes + f"\n[Closed: {why}]"))).rowcount


# ---------- People ----------
async def add_person(db: AsyncSession, user: User, code: str, person_id: int) -> dict:
    b = await _admin_board(db, user, code)
    await _active_staff(db, {person_id})
    if person_id in await _people_ids(db, b.id) or person_id == b.created_by:
        raise AppError(409, "already_on_board", "This person is already on the board.")
    db.add(BoardPerson(board_id=b.id, user_id=person_id, added_by=user.id))
    name = await db.scalar(select(User.name).where(User.id == person_id))
    audit_service.record(db, actor=user, action="board.person_added", entity_type="board", entity_id=b.code,
                         after={"user_id": person_id, "name": name})
    notification_service.notify(db, {person_id} - {user.id}, "board.added", f"You are on order board {b.code}",
                                f"{b.name} for {b.client}.", f"/employee/order-boards/{b.code}")
    await db.commit()
    return await detail(db, user, code)


async def remove_person(db: AsyncSession, user: User, code: str, person_id: int) -> dict:
    """Ends their access to the board. Their uploads and the history stay; their open tasks on
    this board are closed. Refused while they are the only person on a step that isn't done."""
    b = await _admin_board(db, user, code)
    if person_id == b.created_by:
        raise AppError(409, "owner", "The board's owner can't be removed.")
    if person_id not in await _people_ids(db, b.id):
        raise AppError(404, "not_found", "This person is not on the board.")
    open_steps = (await db.scalars(select(BoardStep).where(BoardStep.board_id == b.id, BoardStep.status != "done")
                                   .order_by(BoardStep.position))).all()
    theirs = [s for s in open_steps if person_id in await _member_ids(db, b.id, s.id)]
    alone = [s.name for s in theirs if await _member_ids(db, b.id, s.id) == {person_id}]
    if alone:
        raise AppError(409, "last_assignee", f"Give these steps to someone else first: {', '.join(alone)}.",
                       {"steps": alone})
    for s in theirs:  # done steps keep them: that's who did the work
        await db.execute(delete(BoardMember).where(BoardMember.step_id == s.id, BoardMember.user_id == person_id))
    await db.execute(delete(BoardPerson).where(BoardPerson.board_id == b.id, BoardPerson.user_id == person_id))
    closed = await _close_tasks(db, b.code, "removed from the board", user_id=person_id)
    name = await db.scalar(select(User.name).where(User.id == person_id))
    audit_service.record(db, actor=user, action="board.person_removed", entity_type="board", entity_id=b.code,
                         before={"user_id": person_id, "name": name, "steps": [s.position for s in theirs]},
                         after={"tasks_closed": closed})
    notification_service.notify(db, {person_id} - {user.id}, "board.removed", f"You were removed from {b.code}",
                                f"By {user.name}.", "")
    await db.commit()
    return await detail(db, user, code)


async def set_assignees(db: AsyncSession, user: User, code: str, step_id: int, member_ids: list[int],
                        head_ids: list[int]) -> dict:
    """Who works on a step, and who heads it. New people are added to the board too; on a running
    step they get its tasks, and people taken off it have their open tasks for it closed."""
    b = await _admin_board(db, user, code)
    step = await db.get(BoardStep, step_id, with_for_update=True, populate_existing=True)
    if step is None or step.board_id != b.id:
        raise AppError(404, "not_found", "Step not found.")
    if step.status == "done":
        raise AppError(409, "step_done", "This step is done; its people stay as they were.")
    new, heads = set(member_ids), set(head_ids)
    if not new:
        raise AppError(422, "no_assignee", "A step needs at least one person.")
    if heads - new:
        raise AppError(422, "bad_head", "The head must be one of the step's people.")
    await _active_staff(db, new)
    old, old_heads = await _member_ids(db, b.id, step.id), await _heads(db, step.id)
    if (new, heads) == (old, old_heads):
        return await detail(db, user, code)
    await db.execute(delete(BoardMember).where(BoardMember.step_id == step.id, BoardMember.user_id.in_(old - new)))
    await db.execute(update(BoardMember).where(BoardMember.step_id == step.id)
                     .values(is_head=BoardMember.user_id.in_(heads)))
    for uid in new - old:
        db.add(BoardMember(board_id=b.id, step_id=step.id, user_id=uid, is_head=uid in heads))
    for uid in new - await _people_ids(db, b.id):
        db.add(BoardPerson(board_id=b.id, user_id=uid, added_by=user.id))
    closed = 0
    if step.status == "active":
        due = to_utc(step.planned_end, cfg().app.shift_end)
        for uid in new - old:
            for title in step.task_templates:
                task_service.add(db, assignee_id=uid, title=f"{b.code} · {step.name}: {title}", source="board",
                                 source_ref=f"board:{b.code}:step:{step.position}", due_at=due, created_by=user.id)
        for uid in old - new:
            closed += await _close_tasks(db, b.code, f"taken off step '{step.name}'", user_id=uid,
                                         step_position=step.position)
    notification_service.notify(db, (new - old) - {user.id}, "board.step_assigned",
                                f"{b.code}: you are on step '{step.name}'",
                                f"Planned {step.planned_start:%d %b}–{step.planned_end:%d %b}.",
                                f"/employee/order-boards/{b.code}")
    audit_service.record(db, actor=user, action="board.step_people_changed", entity_type="board", entity_id=b.code,
                         before={"step": step.position, "people": sorted(old), "heads": sorted(old_heads)},
                         after={"step": step.position, "people": sorted(new), "heads": sorted(heads),
                                "tasks_closed": closed})
    await db.commit()
    return await detail(db, user, code)


# ---------- Plan: edit and lock ----------
async def set_plan_lock(db: AsyncSession, user: User, code: str, locked: bool) -> dict:
    b = await _admin_board(db, user, code)  # owner or boards.manage, running board
    if b.plan_locked != locked:
        b.plan_locked = locked
        audit_service.record(db, actor=user, action="board.plan_locked" if locked else "board.plan_unlocked",
                             entity_type="board", entity_id=b.code)
        await db.commit()
    return await detail(db, user, code)


def _size(s: BoardStep, mode: str) -> int | None:
    return s.percent if mode == "percent" else s.days


async def edit_plan(db: AsyncSession, user: User, code: str, data) -> dict:
    """Save the whole plan at once: start, deadline, split, and the steps in their new order.
    `data.steps` lists every step to keep (by id) and new ones (no id). Steps that are running or
    done stay first, in their order; only steps that haven't started can be moved or left out
    (= removed: the step and its checklist are deleted, the history keeps a copy). All planned dates
    are worked out again."""
    b = await _visible_board(db, user, code, lock=True)
    if b.status != "active":
        raise AppError(409, "finished", "This board is finished.")
    if b.plan_locked and not can_admin(user, b):
        raise AppError(403, "plan_locked", "The owner has locked the plan.")
    old = list((await db.scalars(select(BoardStep).where(BoardStep.board_id == b.id)
                                 .order_by(BoardStep.position).with_for_update())).all())
    by_id = {s.id: s for s in old}
    wanted = [x.id for x in data.steps if x.id is not None]
    if len(wanted) != len(set(wanted)) or set(wanted) - set(by_id):
        raise AppError(422, "bad_steps", "The step list doesn't match this board. Reload and try again.")
    started = [s.id for s in old if s.status != "pending"]
    if wanted[:len(started)] != started or [x.id for x in data.steps[:len(started)]] != started:
        raise AppError(422, "started_steps", "Steps that are running or done stay where they are, first in the list.")
    removed = [s for s in old if s.id not in wanted]
    if any(s.status != "pending" for s in removed):
        raise AppError(422, "started_steps", "Only steps that haven't started can be removed.")
    new_people: set[int] = set()
    for x in data.steps:
        if x.id is None:
            if not x.member_ids:
                raise AppError(422, "no_assignee", f"New step '{x.name}' needs at least one person.")
            if set(x.head_ids) - set(x.member_ids):
                raise AppError(422, "bad_head", f"The head of '{x.name}' must be one of its people.")
            new_people |= set(x.member_ids)
    if new_people:
        await _active_staff(db, new_people)

    holidays = await holiday_set(db, data.start.year, data.deadline.year + 1)
    plan, plan_late = plan_steps(data.start, data.deadline, data.split_mode, [x.size for x in data.steps], holidays)
    names = dict((await db.execute(select(User.id, User.name))).all())

    # What changed, in words, for the history
    summary: list[str] = []
    old_start, old_deadline = local_day(b.start_at), local_day(b.deadline_at)
    if data.start != old_start:
        summary.append(f"start {old_start:%d %b} → {data.start:%d %b}")
    if data.deadline != old_deadline:
        summary.append(f"deadline {old_deadline:%d %b} → {data.deadline:%d %b}")
    if data.split_mode != b.split_mode:
        summary.append("split by " + ("% of the time" if data.split_mode == "percent" else "fixed working days"))
    unit = "%" if data.split_mode == "percent" else " days"
    for x in data.steps:
        if x.id is None:
            summary.append(f"added step '{x.name.strip()}' ({_names_of(sorted(set(x.member_ids)), names)})")
            continue
        s = by_id[x.id]
        if x.name.strip() != s.name:
            summary.append(f"renamed '{s.name}' to '{x.name.strip()}'")
        if data.split_mode == b.split_mode and x.size != _size(s, b.split_mode):
            summary.append(f"'{x.name.strip()}' {_size(s, b.split_mode)}{unit} → {x.size}{unit}")
    for s in removed:
        summary.append(f"removed step '{s.name}'")
    if wanted != [s.id for s in old if s.id in wanted]:  # kept steps moved (new steps are listed above)
        summary.append("new order: " + ", ".join(x.name.strip() for x in data.steps))

    # Removed steps: their tasks (none before a step starts) are closed, never deleted
    for s in removed:
        members = sorted(await _member_ids(db, b.id, s.id))
        await _close_tasks(db, b.code, f"step '{s.name}' removed", step_position=s.position)
        audit_service.record(db, actor=user, action="board.step_removed", entity_type="board", entity_id=b.code,
                             before={"step": s.position, "name": s.name, "checklist": s.checklist,
                                     "task_templates": s.task_templates, "people": members})
        await db.delete(s)
    await db.flush()

    # New positions. (board_id, position) must stay unique at every moment, so park the kept steps
    # on negative numbers first. Running and done steps keep their numbers (they come first), so
    # their tasks ("board:CODE:step:N") still point to the right step.
    for i in wanted:
        by_id[i].position = -by_id[i].id
    await db.flush()
    active = next((s for s in old if s.status == "active"), None)
    old_active_end = active.planned_end if active else None
    today = local_day(datetime.now(timezone.utc))
    for pos, (x, (p_start, p_end)) in enumerate(zip(data.steps, plan), start=1):
        if x.id is None:
            st = BoardStep(board_id=b.id, position=pos, name=x.name.strip(), status="pending", alerted_pct=0,
                           task_templates=[t.strip() for t in x.task_templates if t.strip()],
                           checklist=[{"text": t.strip(), "done": False} for t in x.checklist if t.strip()])
            db.add(st)
        else:
            st = by_id[x.id]
            st.position, st.name = pos, x.name.strip()
        st.percent = x.size if data.split_mode == "percent" else None
        st.days = x.size if data.split_mode == "days" else None
        st.planned_start, st.planned_end = p_start, p_end
        if x.id is None:
            await db.flush()
            for uid in set(x.member_ids):
                db.add(BoardMember(board_id=b.id, step_id=st.id, user_id=uid, is_head=uid in x.head_ids))
    for uid in new_people - await _people_ids(db, b.id):
        db.add(BoardPerson(board_id=b.id, user_id=uid, added_by=user.id))

    c = cfg().app
    b.start_at, b.deadline_at, b.split_mode = to_utc(data.start, c.shift_start), to_utc(data.deadline, c.shift_end), data.split_mode
    await db.flush()

    if active is not None:
        if active.planned_end != old_active_end:  # its open tasks follow the new planned end
            await db.execute(update(Task).where(Task.source == "board", Task.status != "done",
                                                Task.source_ref == f"board:{b.code}:step:{active.position}")
                             .values(due_at=to_utc(active.planned_end, c.shift_end)))
        # More time: alerts can fire again later. Less time: a newly crossed level is still sent.
        crossed = max((t for t in cfg().alerts.thresholds if used_pct(active, today, holidays) >= t), default=0)
        active.alerted_pct = min(active.alerted_pct, crossed)
    else:
        # Everything before was done (e.g. a step added after the last one): start the first new one
        first = await db.scalar(select(BoardStep).where(BoardStep.board_id == b.id, BoardStep.status == "pending")
                                .order_by(BoardStep.position))
        if first is not None:
            await _start_step(db, b, first, user)

    audit_service.record(db, actor=user, action="board.plan_changed", entity_type="board", entity_id=b.code,
                         after={"summary": summary, "plan_late": plan_late})
    who = (await _people_ids(db, b.id) | ({b.created_by} if b.created_by else set())) - {user.id}
    if summary:
        notification_service.notify(db, who, "board.plan_changed", f"{b.code}: plan changed by {user.name}",
                                    "; ".join(summary)[:500], f"/employee/order-boards/{b.code}")
    await db.commit()
    return await detail(db, user, code)


# ---------- History (read only) ----------
def _names_of(ids: list | None, names: dict[int, str]) -> str:
    return ", ".join(names.get(i, f"#{i}") for i in ids or []) or "nobody"


def describe(action: str, before: dict | None, after: dict | None, names: dict[int, str]) -> str:
    """One plain sentence for a history line ("who" is shown next to it)."""
    b, a = before or {}, after or {}
    step = f"step {a.get('step') or b.get('step')}"
    if action == "board.created":
        try:  # saved as 2026-11-28; shown as 28 Nov 2026
            deadline = f"{date.fromisoformat(a.get('deadline', '')):%d %b %Y}"
        except ValueError:
            deadline = a.get("deadline") or "?"
        return f"created the board ({a.get('steps')} steps, deadline {deadline})"
    if action == "board.step_done":
        return f"marked step {a.get('step')} \"{a.get('name')}\" done"
    if action in ("board.check_ticked", "board.check_unticked"):
        verb = "ticked" if action == "board.check_ticked" else "unticked"
        return f"{verb} \"{a.get('item')}\" on {step}"
    if action == "board.finished":
        return f"closed the board as {a.get('final_status')}" + (
            f" ({a['tasks_closed']} open tasks closed)" if a.get("tasks_closed") else "")
    if action == "board.step_removed":
        return f"removed step {b.get('step')} \"{b.get('name')}\" (it hadn't started)"
    if action == "board.person_added":
        return f"added {a.get('name')} to the board"
    if action == "board.person_removed":
        on = f" (was on step {', '.join(map(str, b['steps']))})" if b.get("steps") else ""
        return f"removed {b.get('name')} from the board{on}"
    if action == "board.step_people_changed":
        old, new = set(b.get("people") or []), set(a.get("people") or [])
        parts = []
        if new - old:
            parts.append(f"added {_names_of(sorted(new - old), names)}")
        if old - new:
            parts.append(f"took off {_names_of(sorted(old - new), names)}")
        if set(b.get("heads") or []) != set(a.get("heads") or []):
            parts.append(f"head now {_names_of(a.get('heads'), names)}")
        return f"changed the people on {step}: " + ("; ".join(parts) or "no change")
    if action == "board.plan_changed":
        return "changed the plan: " + ("; ".join(a.get("summary") or []) or "no change")
    if action == "board.plan_locked":
        return "locked the plan (only the owner can change it now)"
    if action == "board.plan_unlocked":
        return "unlocked the plan (everyone on the board can change it)"
    if action == "file.uploaded":
        return f"uploaded {a.get('name')}"
    if action == "file.delete_requested":
        return f"asked to delete {a.get('name')}: \"{a.get('reason')}\""
    if action == "file.delete_approved":
        return f"approved deleting {b.get('name')}"
    if action == "file.delete_rejected":
        return f"kept {b.get('name')} (delete request turned down)"
    return action  # a new kind of change still shows, by its name


async def history(db: AsyncSession, user: User, code: str, before_id: int | None = None, limit: int = 50) -> dict:
    """The board's changes, newest first, read from the audit log (which nobody can edit or delete:
    a database trigger blocks it). Everyone on the board may read it. Includes its files' uploads and
    delete decisions, also of files deleted since. `before_id` pages back to older lines."""
    b = await _visible_board(db, user, code)
    file_ids = [str(i) for i in (await db.scalars(select(StoredFile.id).where(
        StoredFile.owner_type == "board", StoredFile.owner_id == b.code))).all()]
    q = select(AuditLog).where(
        ((AuditLog.entity_type == "board") & (AuditLog.entity_id == b.code))
        | ((AuditLog.entity_type == "file") & AuditLog.entity_id.in_(file_ids)))
    if before_id:
        q = q.where(AuditLog.id < before_id)
    rows = (await db.scalars(q.order_by(AuditLog.id.desc()).limit(limit + 1))).all()
    names = dict((await db.execute(select(User.id, User.name))).all())
    return {
        "items": [{"id": r.id, "at": r.at, "who": names.get(r.actor_id or 0) or r.actor_label, "action": r.action,
                   "text": describe(r.action, r.before, r.after, names)} for r in rows[:limit]],
        "more": len(rows) > limit,  # older lines exist: ask again with before_id = the last id
    }


# ---------- Alerts job ----------
@job("board_alerts")
async def board_alerts(db: AsyncSession, today: date | None = None) -> dict:
    today = today or local_day(datetime.now(timezone.utc))
    holidays = await holiday_set(db, today.year - 1, today.year + 1)
    thresholds = sorted(cfg().alerts.thresholds)
    managers = await notification_service.users_with(db, "boards.manage")
    rows = (await db.execute(select(BoardStep, OrderBoard).join(OrderBoard, OrderBoard.id == BoardStep.board_id)
                             .where(BoardStep.status == "active", OrderBoard.status == "active"))).all()
    sent = 0
    for step, board in rows:
        pct = used_pct(step, today, holidays)
        crossed = max((t for t in thresholds if pct >= t), default=0)
        if crossed <= step.alerted_pct:
            continue
        step.alerted_pct = crossed
        who = await _member_ids(db, board.id, step.id) | set(managers)
        word = "is out of time" if crossed >= 100 else f"has used {crossed}% of its time"
        notification_service.notify(db, who, "board.alert", f"{board.code}: '{step.name}' {word}",
                                    f"Planned {step.planned_start:%d %b}–{step.planned_end:%d %b}. Deadline {local_day(board.deadline_at):%d %b}.",
                                    f"/employee/order-boards/{board.code}")
        log.warning("board.alert", extra={"board": board.code, "step": step.position, "pct": crossed})
        sent += 1
    return {"active_steps": len(rows), "alerts": sent}
