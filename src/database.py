import os

from dotenv import load_dotenv
from supabase import Client, create_client


def get_supabase_client() -> Client:
    """Load environment variables and return a Supabase client.

    Raises:
        RuntimeError: If SUPABASE_URL or SUPABASE_SECRET_KEY is not set.
            The message never includes credential values, so it is safe
            to surface in CLI output; the API converts it to a generic
            HTTP 500 response.
    """
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SECRET_KEY")

    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Supabase configuration missing: set SUPABASE_URL and "
            "SUPABASE_SECRET_KEY in the environment or .env file."
        )

    return create_client(supabase_url, supabase_key)
