import io
import zipfile

from pypdf import PdfReader

from app import certificate
from tests.conftest import make_recipient


def create(client, recipients):
    return client.post("/jobs", json={"recipients": recipients})


# ---------- 1. Creating a generation job ----------
def test_create_job_returns_202_and_job_id(client):
    r = create(client, [make_recipient("A"), make_recipient("B")])
    assert r.status_code == 202
    body = r.json()
    assert body["job_id"]
    assert body["total"] == 2
    assert body["status_url"] == f"/jobs/{body['job_id']}"


def test_bulk_request_with_many_recipients_single_call(client):
    r = create(client, [make_recipient(f"Person {i}") for i in range(50)])
    assert r.status_code == 202
    job = client.get(f"/jobs/{r.json()['job_id']}").json()
    assert job["total"] == 50
    assert job["succeeded"] == 50


# ---------- 2. Input validation ----------
def test_empty_recipient_list_rejected(client):
    assert create(client, []).status_code == 422


def test_missing_recipients_field_rejected(client):
    assert client.post("/jobs", json={}).status_code == 422


def test_too_many_recipients_rejected(client, monkeypatch):
    monkeypatch.setattr("app.config.MAX_RECIPIENTS_PER_JOB", 2)
    r = create(client, [make_recipient(f"P{i}") for i in range(3)])
    assert r.status_code == 413


def test_invalid_recipients_marked_failed_but_valid_still_generated(client):
    recipients = [
        make_recipient("Good One"),
        make_recipient(name="   "),                       # blank name
        make_recipient("Bad Email", email="not-an-email"),  # bad email
        make_recipient("Bad Date", issue_date="31-31-2026"),  # bad date
        {"name": "Missing Fields"},                       # missing fields
        "not-an-object",                                  # wrong type
        make_recipient("Good Two"),
    ]
    job_id = create(client, recipients).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()

    assert job["total"] == 7
    assert job["succeeded"] == 2
    assert job["failed"] == 5
    assert job["status"] == "partially_completed"
    failed = [c for c in job["certificates"] if c["status"] == "failed"]
    assert all(c["error"].startswith("Validation error") for c in failed)
    assert all(c["download_url"] is None for c in failed)


# ---------- 3. Certificate generation ----------
def test_generated_certificate_is_pdf_containing_recipient_details(client):
    job_id = create(client, [make_recipient("Priya Sharma", course_name="Data Science")]).json()["job_id"]
    cert = client.get(f"/jobs/{job_id}").json()["certificates"][0]
    r = client.get(cert["download_url"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")

    text = PdfReader(io.BytesIO(r.content)).pages[0].extract_text()
    assert "Priya Sharma" in text
    assert "Data Science" in text
    assert "08 October 2026" in text


# ---------- 4. Job status / progress ----------
def test_job_status_and_progress_on_success(client):
    job_id = create(client, [make_recipient("A"), make_recipient("B"), make_recipient("C")]).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert job["processed"] == 3
    assert job["progress_percent"] == 100.0
    assert job["completed_at"] is not None


def test_unknown_job_returns_404(client):
    assert client.get("/jobs/does-not-exist").status_code == 404


# ---------- 5. Individual certificate failure ----------
def test_one_generation_failure_does_not_stop_others(client, monkeypatch):
    real_render = certificate.render_certificate

    def flaky(data, path):
        if data.name == "Explode":
            raise RuntimeError("renderer crashed")
        return real_render(data, path)

    monkeypatch.setattr("app.services.render_certificate", flaky)

    job_id = create(client, [make_recipient("Before"), make_recipient("Explode"), make_recipient("After")]).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()

    assert job["status"] == "partially_completed"
    assert job["succeeded"] == 2
    assert job["failed"] == 1
    by_name = {c["recipient_name"]: c for c in job["certificates"]}
    assert by_name["Before"]["status"] == "success"
    assert by_name["After"]["status"] == "success"
    assert by_name["Explode"]["status"] == "failed"
    assert "renderer crashed" in by_name["Explode"]["error"]


def test_job_fails_when_all_certificates_fail(client):
    job_id = create(client, [make_recipient(name=""), make_recipient(email="bad")]).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "failed"
    assert job["succeeded"] == 0


# ---------- 6. Retrieving generated certificates ----------
def test_download_all_as_zip(client):
    job_id = create(client, [make_recipient("A One"), make_recipient("B Two"), make_recipient(name="")]).json()["job_id"]
    r = client.get(f"/jobs/{job_id}/download")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert len(zf.namelist()) == 2  # failed one is excluded
    assert all(n.endswith(".pdf") for n in zf.namelist())


def test_download_failed_certificate_returns_409(client):
    job_id = create(client, [make_recipient("Ok"), make_recipient(name="")]).json()["job_id"]
    certs = client.get(f"/jobs/{job_id}").json()["certificates"]
    failed_id = next(c["id"] for c in certs if c["status"] == "failed")
    r = client.get(f"/jobs/{job_id}/certificates/{failed_id}/download")
    assert r.status_code == 409


def test_download_certificate_from_wrong_job_returns_404(client):
    job1 = create(client, [make_recipient("One")]).json()["job_id"]
    job2 = create(client, [make_recipient("Two")]).json()["job_id"]
    cert_of_job1 = client.get(f"/jobs/{job1}").json()["certificates"][0]["id"]
    assert client.get(f"/jobs/{job2}/certificates/{cert_of_job1}/download").status_code == 404


def test_zip_for_job_with_no_successes_returns_404(client):
    job_id = create(client, [make_recipient(name="")]).json()["job_id"]
    assert client.get(f"/jobs/{job_id}/download").status_code == 404
