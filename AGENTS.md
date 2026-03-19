# Sound Mind - AI Agent Instructions

## Technical Stack
- **Backend:** Flask (Python 3.12+)
- **Database:** SQLite (Local file)
- **APIs:** Gemini (Logic), ElevenLabs (Voice), Paystack (Payments)

## Coding Preferences
- **Structure:** Keep the project in a single-file `app.py` as much as possible.
- **UI:** I handle the CSS/Design. Only provide the functional HTML/JS needed for API calls.
- **Python Style:** Use type hints and clear docstrings for every function.
- **Payments:** Always verify the `x-paystack-signature` header in the webhook.

## Monetization Rules
- Free users: 2 documents/month limit.
- 1 Credit = 1,000 characters of audio generation.
