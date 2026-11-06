"""Shift management: list, create, update shifts and assign to employees."""
from datetime import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.shift import Shift
from app.models.user import User
from app.services import audit_service


async def list_shifts(db: AsyncSession, only_active: bool = True) -> list[Shift]:
    q = select(Shift).order_by(Shift.id)
    if only_active:
        q = q.where(Shift.is_active.is_(True))
    return list((await db.scalars(q)).all())


async def create_shift(db: AsyncSession, actor: User, name: str, code: str, start_time: time,
                       end_time: time, is_night_shift: bool = False) -> Shift:
    code = code.strip().upper()
    existing = await db.scalar(select(Shift).where(Shift.code == code))
    if existing:
        raise AppError(409, "duplicate_shift", f"Shift code '{code}' already exists.")

    shift = Shift(
        name=name.strip(),
        code=code,
        start_time=start_time,
        end_time=end_time,
        is_night_shift=is_night_shift,
        is_active=True,
    )
    db.add(shift)
    await db.flush()
    audit_service.record(
        db, actor=actor, action="shift.created", entity_type="shift", entity_id=shift.id,
        after={"name": shift.name, "code": shift.code, "start": str(shift.start_time), "end": str(shift.end_time)}
    )
    await db.commit()
    return shift


async def assign_user_shift(db: AsyncSession, actor: User, user_id: int, shift_id: int) -> User:
    target_user = await db.get(User, user_id)
    if not target_user:
        raise AppError(404, "user_not_found", "User not found.")

    shift = await db.get(Shift, shift_id)
    if not shift:
        raise AppError(404, "shift_not_found", "Shift not found.")

    old_shift_id = target_user.shift_id
    target_user.shift_id = shift.id
    audit_service.record(
        db, actor=actor, action="user.shift_assigned", entity_type="user", entity_id=target_user.id,
        before={"shift_id": old_shift_id},
        after={"shift_id": shift.id, "shift_name": shift.name}
    )
    await db.commit()
    return target_user

