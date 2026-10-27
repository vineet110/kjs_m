"""Numbers for the Analytics page. Real database data only (backlog D6): an empty
database shows zeros, never sample numbers."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import Attendance
from app.models.content import KokoChat
from app.models.lead import Lead
from app.models.notification import Notification
from app.models.order_board import BoardStep, OrderBoard
from app.models.task import Task
from app.models.user import User
from app.services import board_service, lead_service
from app.services.attendance_service import local_day
from app.services.calendar_service import holiday_set


async def summary(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    today = local_day(now)
    since = now - timedelta(weeks=8)
    holidays = await holiday_set(db, today.year - 1, today.year + 1)

    # Leads per week (last 8 weeks) and by source / status / outcome
    leads = (await db.scalars(select(Lead).where(Lead.created_at >= since))).all()
    weeks = [(today - timedelta(days=today.weekday() + 7 * i)) for i in range(7, -1, -1)]
    per_week = {w.isoformat(): 0 for w in weeks}
    for lead in leads:
        d = local_day(lead.created_at)
        monday = (d - timedelta(days=d.weekday())).isoformat()
        if monday in per_week:
            per_week[monday] += 1
    by_source = dict((await db.execute(select(Lead.source, func.count()).group_by(Lead.source))).all())
    by_status = dict((await db.execute(select(Lead.status, func.count()).group_by(Lead.status))).all())
    by_outcome = dict((await db.execute(select(Lead.outcome, func.count()).where(Lead.outcome != "")
                                        .group_by(Lead.outcome))).all())

    # SLA: of leads answered in the last 8 weeks, how many on time
    answered = [x for x in leads if x.responded_at]
    on_time = sum(1 for x in answered if x.responded_at <= lead_service.sla(x, now, holidays)["respond_due_at"])
    # Leads that went over a time limit (counting notifications instead would multiply each breach by
    # the number of people told about it).
    breaches = sum(1 for x in leads if x.escalation_level > 0)

    # Attendance: last 14 days, present vs late
    start = today - timedelta(days=13)
    att = dict()
    for day, status, n in (await db.execute(select(Attendance.day, Attendance.status, func.count())
                                            .where(Attendance.day >= start).group_by(Attendance.day, Attendance.status))).all():
        att.setdefault(day.isoformat(), {"present": 0, "late": 0})[status if status in ("present", "late") else "present"] += n
    attendance = [{"day": (start + timedelta(days=i)).isoformat(), **att.get((start + timedelta(days=i)).isoformat(), {"present": 0, "late": 0})}
                  for i in range(14)]

    # Tasks done per person (last 30 days)
    tasks_done = [{"name": n, "done": c} for n, c in (await db.execute(
        select(User.name, func.count()).join(Task, Task.assignee_id == User.id)
        .where(Task.status == "done", Task.completed_at >= now - timedelta(days=30))
        .group_by(User.name).order_by(func.count().desc()).limit(15))).all()]

    # Order boards by state
    boards = (await db.scalars(select(OrderBoard).where(OrderBoard.status == "active"))).all()
    states: dict[str, int] = {}
    for b in boards:
        steps = list((await db.scalars(select(BoardStep).where(BoardStep.board_id == b.id))).all())
        s = board_service.board_state(b, steps, today, holidays)
        states[s] = states.get(s, 0) + 1
    finished = dict((await db.execute(select(OrderBoard.final_status, func.count())
                                      .where(OrderBoard.status == "finished").group_by(OrderBoard.final_status))).all())

    chats = await db.scalar(select(func.count()).select_from(KokoChat).where(KokoChat.created_at >= since))
    chat_buyers = await db.scalar(select(func.count()).select_from(KokoChat).where(
        KokoChat.created_at >= since, KokoChat.suggested_enquiry.is_(True)))

    return {
        "leads_per_week": [{"week": k, "count": v} for k, v in per_week.items()],
        "leads_by_source": by_source, "leads_by_status": by_status, "leads_by_outcome": by_outcome,
        "sla": {"answered": len(answered), "on_time": on_time, "breaches": breaches or 0},
        "attendance": attendance, "tasks_done": tasks_done,
        "boards": {"active": states, "finished": {k or "Unknown": v for k, v in finished.items()}},
        "koko": {"chats": chats or 0, "buyer_chats": chat_buyers or 0, "leads": by_source.get("koko", 0)},
    }


async def alert_log(db: AsyncSession, limit: int = 100) -> list[dict]:
    """Alerts sent (one row per alert, with how many people got it)."""
    # 'minute' written into the SQL (not a parameter) so GROUP BY and ORDER BY see the same expression
    at = func.date_trunc(literal_column("'minute'"), Notification.created_at).label("at")
    rows = (await db.execute(
        select(Notification.kind, Notification.title, Notification.body, Notification.link, at, func.count())
        .where(Notification.kind.in_(["board.alert", "lead.sla_breach"]))
        .group_by(Notification.kind, Notification.title, Notification.body, Notification.link, at)
        .order_by(at.desc()).limit(limit))).all()
    return [{"kind": k, "title": t, "body": b, "link": link, "at": at, "people": n} for k, t, b, link, at, n in rows]
