"""Order boards: plan steps on working days, run them, alert when a step uses up its time.

Planning (pure functions, unit tested):
- The board has a start date and a deadline. Working days = Mon–Sat minus holidays.
- percent mode: each step gets its % of the board's working days (at least 1 day);
  rounding is fixed on the last step so the plan ends exactly on the deadline.
- days mode: each step gets a fixed number of working days, one after another. If they
  don't fit before the deadline the plan says so (`plan_late`), it doesn't refuse.

Running:
- Creating a board starts step 1. Marking a step done starts the next one.
- Starting a step gives each of its members the step's task templates as tasks.
- The `board_alerts` job tells the step members and board managers when a running step has
  used 50 / 85 / 100 % of its planned time (thresholds in config/alerts.ini), once each.
"""
import logging
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.errors import AppError
from app.core.permissions import effective_permissions
from app.jobs.runner import job
from app.models.order_board import BoardMember, BoardStep, OrderBoard
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
    elapsed = CalendarService.working_days_between(step.planned_start, today, holidays)
    if today > step.planned_end:  # past the end: count calendar overrun too, so it keeps growing
        elapsed = max(elapsed, planned + (today - step.planned_end).days)
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


async def _board(db: AsyncSession, code: str) -> OrderBoard:
    b = await db.scalar(select(OrderBoard).where(OrderBoard.code == code.upper()))
    if b is None:
        raise AppError(404, "not_found", "Order board not found.")
    return b


async def _member_ids(db: AsyncSession, board_id: int, step_id: int | None = None) -> set[int]:
    q = select(BoardMember.user_id).where(BoardMember.board_id == board_id)
    if step_id:
        q = q.where(BoardMember.step_id == step_id)
    return set((await db.scalars(q)).all())


async def _visible_board(db: AsyncSession, user: User, code: str) -> OrderBoard:
    b = await _board(db, code)
    if not can_manage(user) and user.id not in await _member_ids(db, b.id):
        raise AppError(404, "not_found", "Order board not found.")
    return b


async def _files_access(db: AsyncSession, user: User, owner_id: str, action: str) -> bool:
    try:
        await _visible_board(db, user, owner_id)
        return True
    except AppError:
        return False


file_service.register_owner("board", _files_access)


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
    active = set((await db.scalars(select(User.id).where(User.id.in_(member_ids), User.status == "active"))).all())
    if member_ids - active:
        raise AppError(422, "bad_members", "Some members are not active staff.", {"ids": sorted(member_ids - active)})

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
            db.add(BoardMember(board_id=board.id, step_id=step.id, user_id=uid))
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
    return {"id": s.id, "position": s.position, "name": s.name, "percent": s.percent, "days": s.days,
            "planned_start": s.planned_start, "planned_end": s.planned_end, "status": s.status,
            "started_at": s.started_at, "done_at": s.done_at, "used_pct": used_pct(s, today, holidays),
            "task_templates": s.task_templates, "checklist": s.checklist,
            "members": [{"id": m, "name": names.get(m, "")} for m in sorted(members)]}


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
    q = select(OrderBoard).order_by(OrderBoard.deadline_at)
    if not can_manage(user):
        q = q.where(OrderBoard.id.in_(select(BoardMember.board_id).where(BoardMember.user_id == user.id)))
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
    return await _board_out(db, b, steps, today, holidays) | {
        "steps": [await _step_out(db, s, today, holidays, names) for s in steps],
        "my_step_ids": my_steps, "can_manage": can_manage(user)}


# ---------- Run ----------
async def _step_for_action(db: AsyncSession, user: User, code: str, step_id: int) -> tuple[OrderBoard, BoardStep]:
    b = await _visible_board(db, user, code)
    # Locked until commit: a double "done" click would otherwise start the next step twice
    # (duplicate tasks), and two members ticking the checklist at once would lose one tick.
    step = await db.get(BoardStep, step_id, with_for_update=True, populate_existing=True)
    if step is None or step.board_id != b.id:
        raise AppError(404, "not_found", "Step not found.")
    if not can_manage(user) and user.id not in await _member_ids(db, b.id, step.id):
        raise AppError(403, "forbidden", "Only this step's members can update it.")
    if b.status != "active":
        raise AppError(409, "finished", "This board is finished.")
    return b, step


async def complete_step(db: AsyncSession, user: User, code: str, step_id: int) -> dict:
    b, step = await _step_for_action(db, user, code, step_id)
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
    _, step = await _step_for_action(db, user, code, step_id)
    if not 0 <= index < len(step.checklist):
        raise AppError(404, "not_found", "Checklist item not found.")
    items = [dict(i) for i in step.checklist]
    items[index]["done"] = done
    step.checklist = items  # new list so SQLAlchemy sees the change
    await db.commit()
    return await detail(db, user, code)


async def finish(db: AsyncSession, user: User, code: str, final_status: str) -> dict:
    b = await _board(db, code)
    before = {"status": b.status, "final_status": b.final_status}
    b.status, b.final_status = "finished", final_status
    audit_service.record(db, actor=user, action="board.finished", entity_type="board", entity_id=b.code,
                         before=before, after={"final_status": final_status})
    await db.commit()
    return await detail(db, user, code)


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
