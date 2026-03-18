from unittest.mock import MagicMock, patch
import pytest
from workers.tasks import process_podcast_task

@patch("workers.tasks.get_storage_client")
@patch("workers.tasks.get_db")
@patch("workers.tasks.extract_text")
@patch("workers.tasks.generate_podcast_script")
@patch("workers.tasks.concatenate_audio")
@patch("workers.tasks.os.path.exists")
@patch("workers.tasks.os.remove")
def test_process_podcast_task(mock_remove, mock_exists, mock_concat, mock_gen_script, mock_extract, mock_get_db, mock_get_storage):
    # Mock storage and firestore
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    mock_bucket = MagicMock()
    mock_storage.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    mock_doc = MagicMock()
    mock_db.collection.return_value.document.return_value = mock_doc

    # Mock utility functions
    mock_extract.return_value = "extracted text"
    mock_gen_script.return_value = [{"speaker": "A", "text": "hello"}]

    mock_audio = MagicMock()
    mock_concat.return_value = mock_audio

    # Mock file system: Let's mock it so that the file actually 'exists' to be removed
    def exists_side_effect(path):
        if path.startswith("/tmp/"): return True
        return False
    mock_exists.side_effect = exists_side_effect

    # Execute task
    process_podcast_task("job-123", "uploads/job-123.txt", "test.txt")

    # Verify sequence of updates
    assert mock_doc.update.call_count >= 3 # PROCESSING, script, COMPLETED

    # Verify audio export called
    mock_audio.export.assert_called_once()

    # Verify final upload
    assert mock_bucket.blob.call_count == 2 # 1 for download, 1 for upload
    mock_blob.upload_from_file.assert_called_once()

    # Verify cleanup
    mock_remove.assert_called_once()
