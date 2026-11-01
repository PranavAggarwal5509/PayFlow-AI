import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IdMixin, TimestampMixin, utcnow
from app.models.enums import CheckStatus, Impact, ReviewStatus, RunStatus
from app.models.invoice import Invoice


class ProcessingRun(IdMixin, Base):
    __tablename__ = "processing_runs"
    __table_args__ = (UniqueConstraint("invoice_id", "run_number", name="uq_run_invoice_number"),)

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    run_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=RunStatus.QUEUED.value, index=True)
    current_stage: Mapped[str | None] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)  # user-friendly
    error_category: Mapped[str | None] = mapped_column(String(32))
    triggered_by: Mapped[str] = mapped_column(String(100), default="system")
    # AI telemetry
    llm_model: Mapped[str | None] = mapped_column(String(64))
    prompt_tokens: Mapped[int | None] = mapped_column()
    completion_tokens: Mapped[int | None] = mapped_column()
    total_tokens: Mapped[int | None] = mapped_column()
    extraction_duration_ms: Mapped[int | None] = mapped_column()

    invoice: Mapped[Invoice] = relationship(back_populates="runs")
    stage_events: Mapped[list["StageEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="StageEvent.started_at"
    )


class StageEvent(IdMixin, Base):
    """One row per stage per run — drives the live progress tracker."""

    __tablename__ = "processing_stage_events"
    __table_args__ = (UniqueConstraint("run_id", "stage", name="uq_stage_event_run_stage"),)

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_runs.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped[ProcessingRun] = relationship(back_populates="stage_events")


class ValidationResult(IdMixin, Base):
    __tablename__ = "validation_results"
    __table_args__ = (
        UniqueConstraint("processing_run_id", "validation_type", name="uq_validation_run_type"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    processing_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_runs.id", ondelete="CASCADE"), index=True
    )
    validation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(10), default=CheckStatus.PASSED.value)
    impact: Mapped[str] = mapped_column(String(10), default=Impact.NONE.value)
    expected_value: Mapped[str | None] = mapped_column(String(255))
    actual_value: Mapped[str | None] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Decision(IdMixin, Base):
    """Final deterministic decision with the ordered list of reasons behind it."""

    __tablename__ = "decisions"
    __table_args__ = (UniqueConstraint("processing_run_id", name="uq_decision_run"),)

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    processing_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_runs.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(IdMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_invoice_created", "invoice_id", "created_at"),)

    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id"), index=True)
    processing_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("processing_runs.id"))
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)  # USER|SYSTEM|WORKFLOW
    actor_id: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Review(IdMixin, TimestampMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("invoice_id", name="uq_review_invoice"),)

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    assigned_to: Mapped[str | None] = mapped_column(String(100))
    review_status: Mapped[str] = mapped_column(
        String(30), default=ReviewStatus.PENDING.value, index=True
    )
    reviewer_comment: Mapped[str | None] = mapped_column(Text)
    final_action: Mapped[str | None] = mapped_column(String(30))
    issue_type: Mapped[str | None] = mapped_column(String(40), index=True)

    invoice: Mapped[Invoice] = relationship()


class NotificationDraft(IdMixin, Base):
    """Draft messages (never auto-sent in v1): clarification requests, failure alerts."""

    __tablename__ = "notification_drafts"

    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    recipient: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

