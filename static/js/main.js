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
    try {
        const result = await apiRequest('/process', 'POST', { text, mode });
        console.log('Job started:', result.job_id);
        pollJob(result.job_id);
        return result.job_id;
    } catch (err) {
        alert(err.message);
    }
}

async function pollJob(jobId) {
    const statusElement = document.getElementById('job-status');
    const audioContainer = document.getElementById('audio-result');

    statusElement.textContent = 'Processing...';

    const interval = setInterval(async () => {
        try {
            const job = await apiRequest(`/job/${jobId}`);
            if (job.status === 'COMPLETED') {
                clearInterval(interval);
                statusElement.textContent = 'Completed!';
                audioContainer.innerHTML = `
                    <audio controls>
                        <source src="${job.audio_url}" type="audio/mpeg">
                        Your browser does not support the audio element.
                    </audio>
                `;
            } else if (job.status === 'FAILED') {
                clearInterval(interval);
                statusElement.textContent = 'Failed to process document.';
            }
        } catch (err) {
            clearInterval(interval);
            console.error('Polling failed:', err);
        }
    }, 3000);
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
