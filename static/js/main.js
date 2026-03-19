/**
 * Sound Mind - AI Audio Platform JS Logic
 *
 * Handles signup, login, document processing, and job polling.
 */

async function apiRequest(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    if (data) options.body = JSON.stringify(data);

    const response = await fetch(endpoint, options);
    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.error || 'Something went wrong');
    }
    return result;
}

// --- PDF Extraction ---

pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

async function handlePdfUpload(file) {
    if (!file) return;

    const statusElement = document.getElementById('job-status');
    statusElement.textContent = 'Extracting PDF text...';

    try {
        const text = await extractText(file);
        document.getElementById('doc-text').value = text;
        statusElement.textContent = 'PDF text extracted successfully.';
    } catch (err) {
        console.error('PDF extraction failed:', err);
        statusElement.textContent = 'Failed to extract PDF text.';
        alert('Could not extract text from this PDF. Please try copying it manually.');
    }
}

async function extractText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = async function() {
            try {
                const typedarray = new Uint8Array(this.result);
                const pdf = await pdfjsLib.getDocument(typedarray).promise;
                let fullText = "";

                for (let i = 1; i <= pdf.numPages; i++) {
                    const page = await pdf.getPage(i);
                    const content = await page.getTextContent();
                    fullText += content.items.map(s => s.str).join(" ") + "\n";
                }
                resolve(fullText);
            } catch (err) {
                reject(err);
            }
        };
        reader.onerror = reject;
        reader.readAsArrayBuffer(file);
    });
}

// --- Auth Handlers ---

async function signup(email, password) {
    try {
        const result = await apiRequest('/signup', 'POST', { email, password });
        alert(result.message);
    } catch (err) {
        alert(err.message);
    }
}

async function login(email, password) {
    try {
        const result = await apiRequest('/login', 'POST', { email, password });
        localStorage.setItem('user_email', email);
        localStorage.setItem('user_credits', result.credits);
        window.location.reload();
    } catch (err) {
        alert(err.message);
    }
}

// --- Document Processing ---

async function processDocument(text, mode) {
    const statusElement = document.getElementById('job-status');
    const btn = document.getElementById('generate-btn');
    const btnText = document.getElementById('btn-text');
    const btnIcon = document.getElementById('btn-icon');

    try {
        const result = await apiRequest('/process', 'POST', { text, mode });
        console.log('Job finished:', result.job_id);

        if (result.status === 'COMPLETED') {
            const audioContainer = document.getElementById('audio-result');

            if (result.audio_url) {
                statusElement.textContent = 'Premium audio ready!';
                audioContainer.innerHTML = `
                    <div class="flex flex-col items-center gap-4 w-full">
                        <audio controls class="w-full">
                            <source src="${result.audio_url}" type="audio/mpeg">
                            Your browser does not support the audio element.
                        </audio>
                        <details class="w-full">
                            <summary class="text-xs text-blue-600 cursor-pointer hover:underline">View Generated Script</summary>
                            <p class="mt-2 text-gray-700 text-sm whitespace-pre-wrap italic bg-white p-4 rounded-lg border border-blue-50">${result.script}</p>
                        </details>
                    </div>
                `;
            } else {
                statusElement.textContent = 'Script ready! Speaking (Free Fallback)...';
                speakText(result.script);
                audioContainer.innerHTML = `
                    <div class="text-left w-full">
                        <div class="flex justify-between items-center mb-4">
                            <span class="text-xs font-bold uppercase text-blue-600">Generated Script (Fallback)</span>
                            <button onclick="stopSpeaking()" class="text-xs bg-red-100 text-red-600 px-2 py-1 rounded hover:bg-red-200">Stop Voice</button>
                        </div>
                        <p class="text-gray-700 text-sm whitespace-pre-wrap italic bg-white p-4 rounded-lg border border-blue-50">${result.script}</p>
                    </div>
                `;
            }

            // UI Reset
            btn.disabled = false;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
            btnText.textContent = 'Generate Audio';
            btnIcon.textContent = '⚡';
        }
        return result.job_id;
    } catch (err) {
        alert(err.message);
        statusElement.textContent = 'Error: ' + err.message;
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
        btnText.textContent = 'Generate Audio';
        btnIcon.textContent = '⚡';
    }
}

// --- Browser TTS Logic ---

let currentUtterance = null;

function speakText(text) {
    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);

    // Choose a professional-sounding voice if available
    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find(v => v.name.includes('Google US English') || v.name.includes('Samantha')) || voices[0];

    if (preferredVoice) {
        utterance.voice = preferredVoice;
    }

    utterance.pitch = 1.0;
    utterance.rate = 1.0;

    currentUtterance = utterance;
    window.speechSynthesis.speak(utterance);

    utterance.onend = () => {
        document.getElementById('job-status').textContent = 'Playback finished.';
    };
}

function stopSpeaking() {
    window.speechSynthesis.cancel();
    document.getElementById('job-status').textContent = 'Playback stopped.';
}

// --- UI Logic (Bound in HTML) ---

document.addEventListener('DOMContentLoaded', () => {
    const email = localStorage.getItem('user_email');
    const credits = localStorage.getItem('user_credits');

    if (email) {
        // Toggle view
        const authSection = document.getElementById('auth-section');
        const loggedInView = document.getElementById('logged-in-view');
        const userInfo = document.getElementById('user-info');
        const authLinks = document.getElementById('auth-links');

        if (authSection) authSection.classList.add('hidden');
        if (loggedInView) loggedInView.classList.remove('hidden');
        if (userInfo) userInfo.classList.remove('hidden');
        if (authLinks) authLinks.classList.add('hidden');

        // Update values
        const userEmailSpan = document.getElementById('user-email');
        const userCreditsSpan = document.getElementById('user-credits');
        const dashCreditsDiv = document.getElementById('dash-credits');

        if (userEmailSpan) userEmailSpan.textContent = email;
        if (userCreditsSpan) userCreditsSpan.textContent = credits;
        if (dashCreditsDiv) dashCreditsDiv.textContent = credits;
    }
});
