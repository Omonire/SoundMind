from celery import Celery
import config
import os
from google.cloud import storage, firestore
from utils.text_extractor import extract_text
from utils.script_generator import generate_podcast_script
from utils.audio_synthesis import concatenate_audio, add_ambience
import io

celery_app = Celery(
    "tasks",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND
)

# Use property to lazily initialize clients or mock them in tests
_storage_client = None
_db = None

def get_storage_client():
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client

def get_db():
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db

@celery_app.task(bind=True, max_retries=3)
def process_podcast_task(self, job_id: str, gcs_path: str, filename: str):
    storage_client = get_storage_client()
    db = get_db()

    try:
        # Update status: PROCESSING
        db.collection(config.FIRESTORE_COLLECTION).document(job_id).update({
            "status": "PROCESSING",
            "progress": 0
        })

        # 1. Download file from GCS
        bucket = storage_client.bucket(config.GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_path)

        ext = os.path.splitext(filename)[1].lower()
        local_path = f"/tmp/{job_id}{ext}"
        blob.download_to_filename(local_path)

        # 2. Extract Text
        text = extract_text(local_path)
        db.collection(config.FIRESTORE_COLLECTION).document(job_id).update({"progress": 20})

        # 3. Generate Script with Gemini
        script = generate_podcast_script(text)
        db.collection(config.FIRESTORE_COLLECTION).document(job_id).update({
            "progress": 50,
            "script": script
        })

        # 4. Generate Audio with ElevenLabs
        full_audio = concatenate_audio(script)

        # 5. Add Ambience (if available)
        ambience_path = "assets/studio_ambience.mp3"
        if os.path.exists(ambience_path):
             full_audio = add_ambience(full_audio, ambience_path)

        db.collection(config.FIRESTORE_COLLECTION).document(job_id).update({"progress": 80})

        # 6. Export and Upload Final MP3
        final_audio_path = f"outputs/{job_id}.mp3"
        output_buffer = io.BytesIO()
        full_audio.export(output_buffer, format="mp3")
        output_buffer.seek(0)

        final_blob = bucket.blob(final_audio_path)
        final_blob.upload_from_file(output_buffer, content_type="audio/mpeg")

        # 7. Update status: COMPLETED
        db.collection(config.FIRESTORE_COLLECTION).document(job_id).update({
            "status": "COMPLETED",
            "progress": 100,
            "finalAudioPath": final_audio_path,
            "completedAt": firestore.SERVER_TIMESTAMP
        })

    except Exception as exc:
        # Log error and update status: FAILED
        print(f"Error processing job {job_id}: {exc}")
        db.collection(config.FIRESTORE_COLLECTION).document(job_id).update({
            "status": "FAILED",
            "error": str(exc)
        })
        # Retry logic if appropriate (e.g. for API rate limits)
        raise self.retry(exc=exc, countdown=60)
    finally:
        # Cleanup
        if 'local_path' in locals() and os.path.exists(local_path):
            os.remove(local_path)
