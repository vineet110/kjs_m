"""Leave management: employee leave application, approval/rejection, and attendance integration."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.attendance import Attendance
from app.models.leave import LeaveRequest
from app.models.user import AvailabilityLog, User
from app.services import audit_service
from app.services.attendance_service import today_local
from app.services.calendar_service import CalendarService, holiday_set


def _leave_out(req: LeaveRequest, user_name: str, working_days: int) -> dict:
    return {
        "id": req.id,
        "user_id": req.user_id,
        "user_name": user_name,
        "leave_type": req.leave_type,
        "start_date": req.start_date.isoformat(),
        "end_date": req.end_date.isoformat(),
        "is_half_day": req.is_half_day,
        "half_day_session": req.half_day_session,
        "reason": req.reason,
        "status": req.status,
        "working_days": working_days,
        "decided_by": req.decided_by,
        "decided_at": req.decided_at.isoformat() if req.decided_at else None,
        "rejection_reason": req.rejection_reason,
        "created_at": req.created_at.isoformat() if req.created_at else None,
    }


async def request_leave(
    db: AsyncSession,
    user: User,
    leave_type: str,
    start_date: date,
    end_date: date,
    reason: str,
    is_half_day: bool = False,
    half_day_session: str | None = None,
) -> dict:
    if end_date < start_date:
        raise AppError(422, "bad_dates", "End date cannot be earlier than start date.")

    # Check for overlapping pending or approved leave requests
    overlap = await db.scalar(
        select(LeaveRequest.id).where(
            LeaveRequest.user_id == user.id,
            LeaveRequest.status.in_(["pending", "approved"]),
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
        )
    )
    if overlap:
        raise AppError(409, "overlapping_leave", "You already have a pending or approved leave in this date range.")

    holidays = await holiday_set(db, start_date.year, end_date.year)
    working_days = CalendarService.working_days_between(start_date, end_date, holidays)
    if working_days == 0 and not is_half_day:
        raise AppError(422, "no_working_days", "The selected dates only contain holidays or non-working days.")

    req = LeaveRequest(
        user_id=user.id,
        leave_type=leave_type.strip().lower(),
        start_date=start_date,
        end_date=end_date,
        is_half_day=is_half_day,
        half_day_session=half_day_session,
        reason=reason.strip(),
        status="pending",
    )
    db.add(req)
    await db.flush()

    audit_service.record(
        db, actor=user, action="leave.requested", entity_type="leave_request", entity_id=req.id,
        after={
            "leave_type": req.leave_type,
            "start_date": req.start_date.isoformat(),
            "end_date": req.end_date.isoformat(),
            "working_days": working_days,
            "is_half_day": is_half_day,
        }
    )
    await db.commit()
    return _leave_out(req, user.name, working_days)


async def list_leaves(
    db: AsyncSession,
    user_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    q = (
        select(LeaveRequest, User.name)
        .join(User, User.id == LeaveRequest.user_id)
        .order_by(LeaveRequest.id.desc())
    )
    if user_id is not None:
        q = q.where(LeaveRequest.user_id == user_id)
    if status:
        q = q.where(LeaveRequest.status == status)

    rows = (await db.execute(q.limit(300))).all()
    if not rows:
        return []

    min_year = min(r.start_date.year for r, _ in rows)
    max_year = max(r.end_date.year for r, _ in rows)
    holidays = await holiday_set(db, min_year, max_year)

    out = []
    for req, user_name in rows:
        wd = CalendarService.working_days_between(req.start_date, req.end_date, holidays)
        out.append(_leave_out(req, user_name, wd))
    return out


async def decide_leave(
    db: AsyncSession,
    approver: User,
    leave_id: int,
    approve: bool,
    rejection_reason: str | None = None,
) -> dict:
    req = await db.get(LeaveRequest, leave_id, with_for_update=True, populate_existing=True)
    if req is None:
        raise AppError(404, "not_found", "Leave request not found.")
    if req.status != "pending":
        raise AppError(409, "already_decided", f"This leave request was already {req.status}.")
    if req.user_id == approver.id and approver.role != "admin":
        raise AppError(403, "own_request", "Someone else must approve your own leave request.")

    req.status = "approved" if approve else "rejected"
    req.decided_by = approver.id
    req.decided_at = datetime.now(timezone.utc)
    if not approve and rejection_reason:
        req.rejection_reason = rejection_reason.strip()

    holidays = await holiday_set(db, req.start_date.year, req.end_date.year)
    working_days = CalendarService.working_days_between(req.start_date, req.end_date, holidays)

    if approve:
        # Populate attendance records with status="leave" for all working days in range
        cur = req.start_date
        while cur <= req.end_date:
            if CalendarService.is_working_day(cur, holidays):
                att = await db.scalar(
                    select(Attendance).where(Attendance.user_id == req.user_id, Attendance.day == cur)
                )
                if att is None:
                    att = Attendance(user_id=req.user_id, day=cur, status="leave", source="leave")
                    db.add(att)
                else:
                    att.status = "leave"
                    att.source = "leave"
            cur += timedelta(days=1)

        # If today is within approved leave period, toggle employee availability off
        today_ = today_local()
        if req.start_date <= today_ <= req.end_date:
            target_user = await db.get(User, req.user_id)
            if target_user and target_user.is_available:
                target_user.is_available = False
                db.add(AvailabilityLog(user_id=target_user.id, value=False, changed_at=datetime.now(timezone.utc)))

    audit_service.record(
        db, actor=approver, action=f"leave.{req.status}", entity_type="leave_request", entity_id=req.id,
        after={"status": req.status, "rejection_reason": req.rejection_reason}
    )
    await db.commit()

    user_name = await db.scalar(select(User.name).where(User.id == req.user_id))
    return _leave_out(req, user_name or "", working_days)

