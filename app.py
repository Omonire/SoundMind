import os
import hmac
import hashlib
import json
import math
import re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, session
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import google.generativeai as genai
import requests
from typing import List, Dict, Any, Optional

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///soundmind.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-for-session'

db = SQLAlchemy(app)

# --- Models ---

class User(db.Model):
    """User model for storing authentication and credit balance."""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    credits_balance = db.Column(db.Integer, default=0)
    # For POC purposes, we are not hashing passwords as per request.
    # In a real app, always hash passwords!
    password = db.Column(db.String(120), nullable=False)
    # Track monthly usage for free users
    docs_this_month = db.Column(db.Integer, default=0)
    last_processed_date = db.Column(db.DateTime, default=datetime.utcnow)

class Job(db.Model):
    """Job model for tracking document processing tasks."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='PENDING') # PENDING, PROCESSING, COMPLETED, FAILED
    file_path = db.Column(db.String(255))
    audio_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- Database Initialization ---

with app.app_context():
    db.create_all()

# --- Auth Routes ---

@app.route('/signup', methods=['POST'])
def signup():
    """Simple signup route."""
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "User already exists"}), 400

    new_user = User(email=email, password=password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User created successfully"}), 201

@app.route('/login', methods=['POST'])
def login():
    """Simple login route."""
    data = request.json
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email, password=password).first()
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    session['user_id'] = user.id
    return jsonify({"message": "Logged in successfully", "credits": user.credits_balance}), 200

# --- Main Routes ---

@app.route('/')
def index():
    """Basic index route."""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    """Endpoint to process a document."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    user = User.query.get(user_id)
    data = request.json
    text = data.get('text')
    mode = data.get('mode', 'monologue') # podcast or monologue

    if not text:
        return jsonify({"error": "No text provided"}), 400

    # Check limits for free users
    # Reset monthly limit if month has passed
    now = datetime.utcnow()
    if user.last_processed_date.month != now.month or user.last_processed_date.year != now.year:
        user.docs_this_month = 0
        user.last_processed_date = now

    # 1 Credit = 1,000 characters (ceiling-based)
    credits_needed = max(1, math.ceil(len(text) / 1000))

    if user.credits_balance < credits_needed:
        # Check free limit
        if user.docs_this_month >= 2:
            return jsonify({"error": "Insufficient credits and free limit reached (2/month)"}), 403
        user.docs_this_month += 1
    else:
        user.credits_balance -= credits_needed

    # Create job
    job = Job(user_id=user.id, status='PROCESSING')
    db.session.add(job)
    db.session.commit()

    try:
        # Step 1: Process document to script
        script_raw = process_document(text, mode)

        # Step 2: Clean script for audio generation
        # If podcast mode, strip JSON structure to avoid reading it out
        if mode == 'podcast':
            try:
                # Find JSON block if Gemini included text around it
                json_match = re.search(r'\[.*\]', script_raw, re.DOTALL)
                if json_match:
                    script_data = json.loads(json_match.group())
                    script_clean = " ".join([f"{item['speaker']}: {item['text']}" for item in script_data])
                else:
                    script_clean = script_raw
            except Exception:
                script_clean = script_raw
        else:
            script_clean = script_raw

        # Step 3: Generate audio
        audio_url = generate_audio(script_clean)

        # Step 3: Update job
        job.status = 'COMPLETED'
        job.audio_url = audio_url
        db.session.commit()

        return jsonify({
            "job_id": job.id,
            "status": job.status,
            "audio_url": job.audio_url,
            "credits_remaining": user.credits_balance
        }), 200

    except Exception as e:
        job.status = 'FAILED'
        db.session.commit()
        return jsonify({"error": str(e), "job_id": job.id}), 500

@app.route('/job/<int:job_id>', methods=['GET'])
def get_job(job_id):
    """Retrieve job status."""
    job = Job.query.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "id": job.id,
        "status": job.status,
        "audio_url": job.audio_url
    }), 200

# --- Helper Functions ---

def process_document(text: str, mode: str) -> str:
    """Uses Gemini API to convert raw text into a script.

    If mode == 'podcast', returns a two-person dialogue JSON.
    If mode == 'monologue', returns a single-narrator script.
    """
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro')

    if mode == 'podcast':
        prompt = (
            f"Convert the following text into a two-person podcast dialogue script. "
            f"Speaker A is the 'Host' and Speaker B is the 'Expert'. "
            f"Format the output as a JSON list of objects, each with 'speaker' and 'text' fields. "
            f"Text: {text}"
        )
    else: # monologue
        prompt = (
            f"Convert the following text into a single-narrator script for a monologue. "
            f"Return the script as a plain text string. "
            f"Text: {text}"
        )

    response = model.generate_content(prompt)
    return response.text

def generate_audio(script: str) -> str:
    """Uses ElevenLabs API to convert script to MP3 and returns the URL.

    For POC, we'll save the file locally and return the path as the URL.
    """
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY is not set")

    url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM" # Adam voice
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }

    data = {
        "text": script,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5
        }
    }

    response = requests.post(url, json=data, headers=headers)
    if response.status_code != 200:
        raise Exception(f"ElevenLabs API error: {response.text}")

    # Generate unique filename
    filename = f"audio_{int(datetime.utcnow().timestamp())}.mp3"
    filepath = os.path.join('static', filename)

    if not os.path.exists('static'):
        os.makedirs('static')

    with open(filepath, 'wb') as f:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)

    return f"/static/{filename}"

# --- Webhook ---

@app.route('/webhook/paystack', methods=['POST'])
def paystack_webhook():
    """Paystack webhook for handling successful charges.

    Verifies x-paystack-signature header and increments user's credits_balance
    by 50 for every 2,500 NGN paid.
    """
    payload = request.get_data()
    signature = request.headers.get('x-paystack-signature')

    if not signature:
        return jsonify({"error": "No signature"}), 401

    secret = os.getenv('PAYSTACK_SECRET_KEY')
    if not secret:
        return jsonify({"error": "Secret not configured"}), 500

    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        return jsonify({"error": "Invalid signature"}), 401

    event_data = request.json
    if event_data.get('event') == 'charge.success':
        data = event_data.get('data')
        amount = data.get('amount') # In kobo (100 kobo = 1 Naira)
        email = data.get('customer', {}).get('email')

        user = User.query.filter_by(email=email).first()
        if user:
            # 50 credits for every 2,500 NGN
            # amount is in kobo, so 2,500 NGN is 250,000 kobo
            naira_amount = amount / 100
            credits_to_add = int((naira_amount / 2500) * 50)

            user.credits_balance += credits_to_add
            db.session.commit()

            return jsonify({"status": "success", "added": credits_to_add}), 200

    return jsonify({"status": "ignored"}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
