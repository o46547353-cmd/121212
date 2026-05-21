import os
import httpx
import logging
from gtts import gTTS
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

async def fetch_itunes_preview(artist: str, title: str) -> Optional[str]:
    """
    Searches iTunes API for a given track and returns the 30-second preview URL.
    """
    url = "https://itunes.apple.com/search"
    term = f"{artist} {title}"
    params = {
        "term": term,
        "media": "music",
        "entity": "song",
        "limit": 1
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data["resultCount"] > 0:
                return data["results"][0].get("previewUrl")
    except Exception as e:
        logger.error(f"Error fetching preview from iTunes for '{term}': {e}")

    return None

def generate_listening_audio(text: str) -> str:
    """
    Generates an mp3 file from text using Google Text-to-Speech (gTTS).
    Returns the file path.
    """
    tts = gTTS(text=text, lang='en', slow=False)

    # Save to a temporary file
    # We use a UUID to prevent collisions in a multi-user environment
    filename = f"/tmp/{uuid.uuid4().hex}.mp3"

    # Ensure /tmp exists (it usually does on Linux, but just in case)
    os.makedirs("/tmp", exist_ok=True)

    tts.save(filename)
    return filename

# Some sample listening comprehension texts
LISTENING_TEXTS = [
    "Welcome to Flight 105. Please fasten your seatbelts and turn off all electronic devices. We will be taking off shortly.",
    "The recipe for this cake is simple. First, mix two cups of flour with one cup of sugar. Then add three eggs and bake for thirty minutes.",
    "Excuse me, could you tell me how to get to the train station? Walk straight for two blocks, then turn left at the traffic light.",
    "Breaking news: Scientists have just discovered a new planet outside our solar system that might have water on its surface.",
    "Hi, I'd like to book a table for two tonight at 8 PM. Yes, we prefer sitting near the window, thank you."
]

def get_random_listening_text() -> str:
    import random
    return random.choice(LISTENING_TEXTS)
