import os
import sys

from dotenv import load_dotenv
from supabase import Client, create_client


def get_supabase_client() -> Client:
    """Load environment variables and return a Supabase client."""
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SECRET_KEY")

    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL or SUPABASE_SECRET_KEY is missing from .env")
        sys.exit(1)

    return create_client(supabase_url, supabase_key)
