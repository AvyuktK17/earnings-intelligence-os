import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

_MODEL = "gemini-2.5-flash"


def get_gemini_client() -> genai.Client:
    """Create and return a Gemini API client.

    Returns:
        An authenticated genai.Client instance.

    Raises:
        EnvironmentError: If GEMINI_API_KEY is not set.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Add it to your .env file."
        )
    return genai.Client(api_key=api_key)


def test_gemini_connection() -> str:
    """Send a simple prompt to Gemini and return the text response.

    Returns:
        The text content of the Gemini response.
    """
    client = get_gemini_client()
    response = client.models.generate_content(
        model=_MODEL,
        contents="Reply with exactly: Gemini connection successful",
    )
    return response.text
