import google.generativeai as genai
import json
import config

genai.configure(api_key=config.GEMINI_API_KEY)

def generate_podcast_script(text):
    model = genai.GenerativeModel("gemini-1.5-pro")

    prompt = f"""
    You are a podcast script generator. Convert the following text into a natural, conversational script between two distinct personas:
    1. "Host" (Speaker A): Enthusiastic, asks insightful questions, and guides the conversation.
    2. "Expert" (Speaker B): Knowledgeable, explains complex concepts simply, and provides depth.

    The output MUST be a valid JSON array of objects with "speaker" (either "A" or "B") and "text" fields.
    Example:
    [
        {{"speaker": "A", "text": "Welcome to our show! Today we're talking about..."}},
        {{"speaker": "B", "text": "Thanks for having me. It's an important topic because..."}}
    ]

    Here is the source text:
    {text}
    """

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
        ),
    )

    try:
        script = json.loads(response.text)
        return script
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        # Fallback or retry logic can go here
        raise e
