from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record(
    db: Session,
    *,
    actor_id: int | None,
    action: str,
    target_type: str,
    target_id: int | None = None,
    meta: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        meta=meta,
    )
    db.add(entry)
    return entry
