from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User


def record(
    db: AsyncSession,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    before: dict | None = None,
    after: dict | None = None,
    ip_hash: str | None = None,
) -> None:
    """Add an audit row to the *current* transaction. It is saved by the same
    db.commit() that saves the change, so we never get a change without its log line
    (or a log line for a change that rolled back)."""
    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            actor_label=f"{actor.name} ({actor.email})" if actor else "visitor/system",
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            before=before,
            after=after,
            ip_hash=ip_hash,
        )
    )
