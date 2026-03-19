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
- **Persistence:** Vercel uses a read-only, ephemeral filesystem. This app uses `/tmp` for the SQLite database (`soundmind.db`) and generated audio files. Data will be **lost** when the Serverless Function cold-starts (restarts).
- **Production Use:** For a production-ready app, replace SQLite with a persistent database (e.g., Vercel Postgres or Supabase) and store audio files in an S3-compatible bucket (e.g., Vercel Blob or AWS S3).
