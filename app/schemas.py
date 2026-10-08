from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    # Kept as raw dicts on purpose: each recipient is validated individually
    # later so a single invalid recipient doesn't reject the entire request.
    recipients: list[Any] = Field(..., min_length=1)


class CertificateOut(BaseModel):
    id: str
    index: int
    recipient_name: str | None
    recipient_email: str | None
    status: str
    error: str | None
    download_url: str | None


class JobSummary(BaseModel):
    job_id: str
    status: str
    total: int
    processed: int
    succeeded: int
    failed: int
    progress_percent: float
    created_at: datetime
    completed_at: datetime | None
    status_url: str


class JobDetail(JobSummary):
    certificates: list[CertificateOut]
