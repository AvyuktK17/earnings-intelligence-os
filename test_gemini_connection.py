"""
Test the Gemini API connection with a simple prompt.
Does NOT send filing text, write to Supabase, or expose the API key.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.llm_client import test_gemini_connection


def main():
    print("Testing Gemini API connection...")
    response = test_gemini_connection()

    print(f"Gemini response: {response}")

    assert "Gemini connection successful" in response, (
        f"Expected response to contain 'Gemini connection successful' but got: {response!r}"
    )

    print("PASS: Gemini API connection is working correctly.")


if __name__ == "__main__":
    main()
