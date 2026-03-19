# Hosting Sound Mind on Vercel

This guide outlines how to deploy the "Sound Mind" AI platform as a Serverless Flask application on Vercel.

## 🚀 Prerequisites
- A [Vercel](https://vercel.com/) account.
- API keys for:
  - **Google Gemini:** [Google AI Studio](https://aistudio.google.com/)
  - **ElevenLabs:** [ElevenLabs Dashboard](https://elevenlabs.io/)
  - **Paystack (Optional):** [Paystack Settings](https://dashboard.paystack.com/)

## 🛠️ Deployment Steps

### 1. Project Configuration
Ensure the project contains the following files:
- `vercel.json`: Defines the Python builder and routing.
- `requirements.txt`: Lists all dependencies including `gunicorn` and `elevenlabs`.
- `app.py`: contains the Vercel-compatible logic (using `/tmp` for SQLite and audio).

### 2. Environment Variables
You must configure the following Environment Variables in your Vercel Project Settings:

| Key | Description |
| :--- | :--- |
| `GEMINI_API_KEY` | Your Google Gemini 1.5 API Key. |
| `ELEVENLABS_API_KEY` | Your ElevenLabs API Key. |
| `PAYSTACK_SECRET_KEY` | (Optional) Your Paystack Secret Key for webhooks. |
| `SECRET_KEY` | A random string for Flask session security. |

### 3. Deploying via Vercel CLI
If you have the [Vercel CLI](https://vercel.com/docs/cli) installed, run:
```bash
vercel
```
Follow the prompts to link your project and deploy.

### 4. Deploying via GitHub (Recommended)
1. Push your code to a GitHub repository.
2. In the Vercel Dashboard, click **"New Project"**.
3. Import your repository.
4. Add the Environment Variables listed above.
5. Click **"Deploy"**.

## ⚠️ Important Notes
- **Persistence:** Vercel uses a read-only, ephemeral filesystem. This app currently uses `/tmp` for the SQLite database (`soundmind.db`) and generated audio files. Data will be **lost** when the Serverless Function cold-starts (restarts).

## 🚀 Moving to Production (Persistence)

To build a professional, persistent version of Sound Mind, you should swap the ephemeral `/tmp` storage for managed cloud services.

### 1. Database Alternatives (SQL Persistence)

| Service | Best For | Why? |
| :--- | :--- | :--- |
| **Turso** | Keeping SQLite logic | Managed "Edge SQLite". Extremely fast and allows you to keep using SQLite-style code with SQLAlchemy. |
| **Vercel Postgres** | Native Integration | Built-in managed PostgreSQL (powered by Neon). Best for sticking entirely within the Vercel ecosystem. |
| **Supabase** | All-in-one Backend | Provides a PostgreSQL DB, Auth, and Storage in one platform. Excellent for scaling. |

### 2. Audio Storage Alternatives (File Persistence)

Instead of saving MP3s to a folder, upload them to a bucket and store the resulting URL in your database.

| Service | Best For | Why? |
| :--- | :--- | :--- |
| **Vercel Blob** | Easiest Setup | Native to Vercel. One-line `put()` command to upload files and get a permanent URL. |
| **Supabase Storage** | Unified Stack | Integrated with Supabase Auth and DB. Great if you use Supabase for your database. |
| **AWS S3 / GCS** | Industrial Scale | The industry standards for massive file storage and CDN delivery. |

## 🛠️ Implementation Example: Vercel Postgres + Vercel Blob

If you decide to upgrade, your `app.py` would change as follows:

```python
# 1. Update DB Connection
# Replace sqlite:// with your Vercel Postgres string
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('POSTGRES_URL')

# 2. Update Audio Generation to use Vercel Blob
import vercel_blob

def generate_audio(script: str) -> str:
    # ... (generate audio bytes via ElevenLabs) ...

    # Upload to Vercel Blob instead of /tmp
    resp = vercel_blob.put(
        f"audio_{timestamp}.mp3",
        audio_bytes,
        {"access": "public"}
    )

    # Return the permanent URL
    return resp['url']
```
