"""Tests for FastAPI endpoints — validates route behaviour."""

import os

import pytest
from fastapi.testclient import TestClient

# Override paths before importing app to avoid /app filesystem errors
os.environ["OUTPUT_DIR"] = "./output"
os.environ["TEMP_DIR"] = "/tmp/sofie"
os.environ["BRIEF_TEMPLATE_PATH"] = "./briefs/brief-template.docx"
os.environ["BRANDS_DIR"] = "./brands"

from backend.main import app


@pytest.fixture
def client():
    """TestClient with lifespan context for DB table creation."""
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    """Health endpoint should return 200 with status ok."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


def test_brief_template_exists(client):
    """Brief template endpoint should return 200 when file exists."""
    r = client.get("/brief-template")
    assert r.status_code == 200
    assert "wordprocessingml" in r.headers.get("content-type", "")


def test_operator_jobs_empty(client):
    """Operator jobs should return empty list when no jobs exist."""
    r = client.get("/operator/jobs")
    assert r.status_code == 200
    assert r.json() == []


def test_job_status_not_found(client):
    """Job status for nonexistent job should return 404."""
    r = client.get("/job/JOB-doesnotexist/status")
    assert r.status_code == 404


def test_approve_nonexistent_job(client):
    """Approving a nonexistent job should return 404."""
    r = client.post("/operator/jobs/JOB-doesnotexist/approve")
    assert r.status_code == 404


def test_reject_nonexistent_job(client):
    """Rejecting a nonexistent job should return 404."""
    r = client.post("/operator/jobs/JOB-doesnotexist/reject")
    assert r.status_code == 404


def test_download_nonexistent_file(client):
    """Download for nonexistent file should return 404."""
    r = client.get("/job/JOB-test/download/nonexistent.jpg")
    assert r.status_code == 404


def test_upload_non_docx_rejected(client):
    """Upload endpoint should reject non-.docx files."""
    from io import BytesIO

    r = client.post(
        "/upload-brief",
        files={"file": ("test.pdf", BytesIO(b"not a docx"), "application/pdf")},
    )
    assert r.status_code == 400
    assert "docx" in r.json()["error"].lower()


def test_upload_valid_docx(client):
    """Upload endpoint should accept .docx files and return file path."""
    # Read the actual test brief
    with open("tests/test_brief.docx", "rb") as f:
        r = client.post(
            "/upload-brief",
            files={
                "file": (
                    "test_brief.docx",
                    f,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert "file_path" in data
    assert data["filename"] == "test_brief.docx"
