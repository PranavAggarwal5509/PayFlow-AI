from sqlalchemy.orm import Session

from app.models.processing import AuditLog


def record_audit(
    db: Session,
    *,
    action: str,
    actor_type: str,
    actor_id: str | None = None,
    invoice_id: object | None = None,
    run_id: object | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    description: str | None = None,
) -> AuditLog:
    """Append-only audit entry; part of the caller's transaction so it commits atomically."""
    entry = AuditLog(
        invoice_id=invoice_id,
        processing_run_id=run_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        description=description,
    )
    db.add(entry)
    return entry

