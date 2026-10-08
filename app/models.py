import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class JobStatus(str, enum.Enum):
    PENDING = "pending"                          # accepted, waiting to be processed
    PROCESSING = "processing"                    # being processed now
    COMPLETED = "completed"                      # every certificate generated
    PARTIALLY_COMPLETED = "partially_completed"  # some succeeded, some failed
    FAILED = "failed"                            # every certificate failed


class CertificateStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    total: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    certificates: Mapped[list["Certificate"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Certificate.index"
    )


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)  # position in the original request
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    course_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issue_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[CertificateStatus] = mapped_column(
        Enum(CertificateStatus), default=CertificateStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    job: Mapped[Job] = relationship(back_populates="certificates")
