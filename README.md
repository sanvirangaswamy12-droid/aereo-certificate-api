# Bulk Certificate Generator API

A backend API that accepts **one request containing many recipients**, validates each recipient,
generates a PDF certificate for every valid recipient from a single predefined template, tracks
progress, and lets the client download the results (individually or as a ZIP).

**Stack:** Python 3.10+, FastAPI, SQLAlchemy (SQLite), ReportLab (PDF), Pydantic, pytest.

---

## 1. Setup

```bash
git clone <your-repo-url>
cd bulk-certificate-generator

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Run the application

```bash
uvicorn app.main:app --reload
```

- API runs at http://127.0.0.1:8000
- Interactive docs (Swagger UI): http://127.0.0.1:8000/docs

The SQLite database (`certificates.db`) and the generated PDFs (`generated_certificates/`) are created
automatically. Optional environment variables: `DATABASE_URL`, `CERTIFICATE_DIR`, `MAX_RECIPIENTS_PER_JOB` (default 1000).

## 3. Run the tests

```bash
python -m pytest -v
```

Tests use an in-memory database and a temporary folder, so they never touch real data.

## 4. API usage

### Submit a generation request
`POST /jobs` returns **202 Accepted** immediately with a job id.

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d @sample_request.json
```

Request body:
```json
{
  "recipients": [
    {"name": "Asha Rao", "email": "asha@example.com", "course_name": "Python Backend Development", "issue_date": "2026-10-08"}
  ]
}
```

Each recipient needs: `name`, `email`, `course_name` (non-blank, max 100 chars for name/course; valid email)
and `issue_date` (`YYYY-MM-DD`).

### Check progress / result
`GET /jobs/{job_id}`

Returns the job `status` (`pending`, `processing`, `completed`, `partially_completed`, `failed`),
`total / processed / succeeded / failed / progress_percent`, and a list of every certificate with its own
`status`, `error` (reason if failed) and `download_url` (if successful).

### Retrieve certificates
- One certificate (PDF): `GET /jobs/{job_id}/certificates/{certificate_id}/download`
- All successful certificates (ZIP): `GET /jobs/{job_id}/download`

```bash
curl -O -J http://127.0.0.1:8000/jobs/<job_id>/download
```

### Status codes
| Code | Meaning |
|------|---------|
| 202 | Job accepted |
| 404 | Job / certificate not found (or no certificates generated for ZIP) |
| 409 | Not ready yet (job still running, or that certificate failed) |
| 410 | File was removed from disk |
| 413 | More than `MAX_RECIPIENTS_PER_JOB` recipients |
| 422 | Malformed request (e.g. missing/empty `recipients`) |

## 5. Design decisions

**Background processing (not synchronous).** Generating hundreds of PDFs inside a request would be slow
and could time out. `POST /jobs` stores the job, returns 202 immediately, and a FastAPI `BackgroundTask`
generates the certificates. The client polls `GET /jobs/{id}`. Each certificate is committed as soon as
it finishes, so progress is visible live.
*Trade-off:* background tasks live inside the web process, so a server restart mid-job leaves the job
unfinished. For production I would move to a real queue (Celery/RQ + Redis) and reuse the same service layer.

**Per-recipient validation and failure isolation.** Recipients are validated one by one, not as one big
schema. An invalid recipient is stored as `failed` with a readable reason and never blocks the others.
Generation of each certificate also runs in its own `try/except`, so one rendering error does not stop
the rest of the job. The job ends as `completed` (all OK), `partially_completed` (mixed) or
`failed` (none succeeded).

**Data model.** `Job` (status, total, timestamps) has many `Certificate` rows (recipient data, status,
error, file path). Counts are computed from certificate rows with a `GROUP BY`, so they always match
the real state.

**Single template.** `app/certificate.py` draws one landscape A4 PDF with ReportLab; no template engine needed.

**Safety.** Filenames are built from a sanitised slug plus index (no path traversal), certificates can
only be downloaded through their own job id, and request size is capped.

**Limitations / future work.** Real task queue, authentication, email delivery of certificates,
retention/cleanup of old files, PostgreSQL + Alembic migrations, Docker.

## 6. Project structure

```
app/
  main.py          # FastAPI routes
  services.py      # create_job, process_job (background), status counts
  certificate.py   # PDF template rendering
  validation.py    # per-recipient validation
  models.py        # Job, Certificate tables
  schemas.py       # request/response models
  database.py, config.py
tests/             # pytest suite (15 tests)
sample_request.json
```
