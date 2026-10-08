import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config, services
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Fresh in-memory DB and temp certificate folder for every test."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(config, "CERTIFICATE_DIR", tmp_path / "certs")

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Background task must use the test DB as well.
    original = services.process_job
    monkeypatch.setattr(
        "app.main.services.process_job",
        lambda job_id: original(job_id, session_factory=TestSession),
    )

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_recipient(name="Asha Rao", **overrides):
    data = {
        "name": name,
        "email": "asha@example.com",
        "course_name": "Python Backend Development",
        "issue_date": "2026-10-08",
    }
    data.update(overrides)
    return data
