import io
import zipfile
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config, services
from .database import Base, engine, get_db
from .models import Certificate, CertificateStatus, Job, JobStatus
from .schemas import CertificateOut, JobCreate, JobDetail, JobSummary

app = FastAPI(
    title="Bulk Certificate Generator API",
    description="Submit many recipients in one request; certificates are generated in the background.",
    version="1.0.0",
)

Base.metadata.create_all(bind=engine)


def _summary(db: Session, job: Job) -> dict:
    counts = services.get_counts(db, job.id)
    progress = round(100 * counts["processed"] / job.total, 1) if job.total else 100.0
    return dict(
        job_id=job.id,
        status=job.status.value,
        total=job.total,
        processed=counts["processed"],
        succeeded=counts["succeeded"],
        failed=counts["failed"],
        progress_percent=progress,
        created_at=job.created_at,
        completed_at=job.completed_at,
        status_url=f"/jobs/{job.id}",
    )


def _get_job_or_404(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/jobs", response_model=JobSummary, status_code=202)
def create_job(payload: JobCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Accept a bulk request and return immediately (202) with a job id."""
    if len(payload.recipients) > config.MAX_RECIPIENTS_PER_JOB:
        raise HTTPException(
            status_code=413,
            detail=f"Too many recipients: max {config.MAX_RECIPIENTS_PER_JOB} per job",
        )
    job = services.create_job(db, payload.recipients)
    background_tasks.add_task(services.process_job, job.id)
    return _summary(db, job)


@app.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Status, progress and per-certificate result (success / failure reason)."""
    job = _get_job_or_404(db, job_id)
    certs = db.scalars(
        select(Certificate).where(Certificate.job_id == job_id).order_by(Certificate.index)
    ).all()
    out = [
        CertificateOut(
            id=c.id,
            index=c.index,
            recipient_name=c.recipient_name,
            recipient_email=c.recipient_email,
            status=c.status.value,
            error=c.error,
            download_url=(
                f"/jobs/{job_id}/certificates/{c.id}/download"
                if c.status == CertificateStatus.SUCCESS else None
            ),
        )
        for c in certs
    ]
    return JobDetail(**_summary(db, job), certificates=out)


@app.get("/jobs/{job_id}/certificates/{certificate_id}/download")
def download_certificate(job_id: str, certificate_id: str, db: Session = Depends(get_db)):
    """Download one certificate PDF."""
    _get_job_or_404(db, job_id)
    cert = db.get(Certificate, certificate_id)
    if cert is None or cert.job_id != job_id:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if cert.status != CertificateStatus.SUCCESS or not cert.file_path:
        raise HTTPException(status_code=409, detail=f"Certificate not available (status: {cert.status.value})")
    path = Path(cert.file_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Certificate file is no longer available")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@app.get("/jobs/{job_id}/download")
def download_all(job_id: str, db: Session = Depends(get_db)):
    """Download every successfully generated certificate of the job as one ZIP."""
    job = _get_job_or_404(db, job_id)
    if job.status in (JobStatus.PENDING, JobStatus.PROCESSING):
        raise HTTPException(status_code=409, detail=f"Job is still {job.status.value}")
    certs = db.scalars(
        select(Certificate).where(
            Certificate.job_id == job_id, Certificate.status == CertificateStatus.SUCCESS
        ).order_by(Certificate.index)
    ).all()
    if not certs:
        raise HTTPException(status_code=404, detail="No certificates were generated for this job")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for c in certs:
            p = Path(c.file_path)
            if p.exists():
                zf.write(p, arcname=p.name)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="certificates_{job_id}.zip"'},
    )
