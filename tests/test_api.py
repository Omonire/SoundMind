from unittest.mock import MagicMock, patch
import pytest
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

@patch("app.main.get_storage_client")
@patch("app.main.get_db")
@patch("app.main.process_podcast_task.delay")
def test_create_podcast(mock_delay, mock_get_db, mock_get_storage):
    # Mocking storage client
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_storage.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    # Mocking firestore client
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_collection = MagicMock()
    mock_doc = MagicMock()
    mock_db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_doc

    # Send a mock file upload request
    response = client.post(
        "/api/v1/podcast/create",
        files={"file": ("test.txt", b"some text content", "text/plain")}
    )

    assert response.status_code == 200
    assert "jobId" in response.json()
    assert response.json()["status"] == "PENDING"

    # Verify storage upload called
    mock_bucket.blob.assert_called_once()
    mock_blob.upload_from_filename.assert_called_once()

    # Verify firestore job created
    mock_collection.document.assert_called_once()
    mock_doc.set.assert_called_once()

    # Verify Celery task triggered
    mock_delay.assert_called_once()

@patch("app.main.get_db")
@patch("app.main.get_storage_client")
def test_get_podcast_status(mock_get_storage, mock_get_db):
    # Mocking firestore client
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db
    mock_collection = MagicMock()
    mock_doc = MagicMock()
    mock_db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_doc

    # Simulate a document existing in Firestore
    mock_doc_get = MagicMock()
    mock_doc_get.exists = True
    mock_doc_get.to_dict.return_value = {
        "status": "COMPLETED",
        "finalAudioPath": "outputs/test.mp3"
    }
    mock_doc.get.return_value = mock_doc_get

    # Mocking storage client for signed URL
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_storage.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_blob.generate_signed_url.return_value = "https://signed-url.com"

    response = client.get("/api/v1/podcast/status/test-job-id")

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["audioUrl"] == "https://signed-url.com"
