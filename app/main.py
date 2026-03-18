from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import uuid
import os
import shutil
import asyncio
from google.cloud import storage, firestore
from workers.tasks import process_podcast_task
import config

app = FastAPI(title="PodDocs API")

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

@app.post("/api/v1/podcast/create")
async def create_podcast(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())

    # Validate file type
    allowed_extensions = {".pdf", ".docx", ".txt"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Invalid file type. Supported: PDF, DOCX, TXT")

    # Store file in GCS
    storage_client = get_storage_client()
    bucket = storage_client.bucket(config.GCS_BUCKET_NAME)
    blob_path = f"uploads/{job_id}{ext}"
    blob = bucket.blob(blob_path)

    # Copy file content to a local temp file then upload
    temp_file_path = f"/tmp/{job_id}{ext}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        blob.upload_from_filename(temp_file_path)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    # Update job status in Firestore
    db = get_db()
    db.collection(config.FIRESTORE_COLLECTION).document(job_id).set({
        "status": "PENDING",
        "filename": file.filename,
        "jobId": job_id,
        "gcsPath": blob_path,
        "createdAt": firestore.SERVER_TIMESTAMP
    })

    # Trigger Celery task
    process_podcast_task.delay(job_id, blob_path, file.filename)

    return {"jobId": job_id, "status": "PENDING"}

@app.get("/api/v1/podcast/status/{job_id}")
async def get_podcast_status(job_id: str):
    db = get_db()
    doc_ref = db.collection(config.FIRESTORE_COLLECTION).document(job_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = doc.to_dict()

    # If completed, generate signed URL for final MP3
    if job_data.get("status") == "COMPLETED":
        storage_client = get_storage_client()
        bucket = storage_client.bucket(config.GCS_BUCKET_NAME)
        blob = bucket.blob(job_data["finalAudioPath"])
        signed_url = blob.generate_signed_url(expiration=3600)
        job_data["audioUrl"] = signed_url

    return job_data

@app.websocket("/ws/podcast/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    db = get_db()
    doc_ref = db.collection(config.FIRESTORE_COLLECTION).document(job_id)

    # Use a queue to communicate between the firestore listener thread and the websocket
    queue = asyncio.Queue()

    def on_snapshot(doc_snapshot, changes, read_time):
        # doc_snapshot is a list of snapshots if watching a query,
        # but for a DocumentReference, it is a single snapshot.
        # Wait, Firestore's `on_snapshot` on a DocumentReference returns a snapshot.
        # Let's check the API again...
        if not isinstance(doc_snapshot, list):
            doc_snapshot = [doc_snapshot]

        for doc in doc_snapshot:
            if doc.exists:
                asyncio.run_coroutine_threadsafe(queue.put(doc.to_dict()), loop)

    loop = asyncio.get_event_loop()
    watch = doc_ref.on_snapshot(on_snapshot)

    try:
        while True:
            data = await queue.get()

            # If completed, add signed URL
            if data.get("status") == "COMPLETED":
                storage_client = get_storage_client()
                bucket = storage_client.bucket(config.GCS_BUCKET_NAME)
                blob = bucket.blob(data["finalAudioPath"])
                data["audioUrl"] = blob.generate_signed_url(expiration=3600)

            await websocket.send_json(data)

            if data.get("status") in ["COMPLETED", "FAILED"]:
                break
    except WebSocketDisconnect:
        pass
    finally:
        watch.unsubscribe()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
