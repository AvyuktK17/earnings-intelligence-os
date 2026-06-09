"""Test CORS support for local frontend development.

Sends a browser-style preflight (OPTIONS) request from the default local
frontend origin and verifies the CORS headers, and confirms a disallowed
origin is not echoed back. Read-only: no Supabase mutations, no AI calls.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app

FRONTEND_ORIGIN = "http://localhost:3000"


def main() -> None:
    client = TestClient(app)

    # --- Preflight from the allowed local frontend origin ---
    response = client.options(
        "/filings",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200, (
        f"Preflight: expected 200, got {response.status_code}."
    )
    headers = response.headers
    assert headers.get("access-control-allow-origin") == FRONTEND_ORIGIN, (
        f"Expected allow-origin={FRONTEND_ORIGIN!r}, "
        f"got {headers.get('access-control-allow-origin')!r}."
    )
    assert headers.get("access-control-allow-credentials") == "true", (
        "Expected allow-credentials=true."
    )
    allowed_methods = headers.get("access-control-allow-methods", "")
    assert "GET" in allowed_methods or "*" in allowed_methods, (
        f"GET must be allowed, got {allowed_methods!r}."
    )
    print(f"OPTIONS /filings (Origin: {FRONTEND_ORIGIN}) -> 200")
    print(f"  access-control-allow-origin      : "
          f"{headers.get('access-control-allow-origin')}")
    print(f"  access-control-allow-credentials : "
          f"{headers.get('access-control-allow-credentials')}")
    print(f"  access-control-allow-methods     : {allowed_methods}")

    # --- Preflight POST for the analyst write endpoints ---
    response = client.options(
        "/review-queue/1/approve",
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200, (
        f"POST preflight: expected 200, got {response.status_code}."
    )
    assert response.headers.get("access-control-allow-origin") == FRONTEND_ORIGIN
    print(f"OPTIONS /review-queue/1/approve (POST preflight) -> 200")

    # --- Disallowed origin gets no allow-origin echo ---
    response = client.options(
        "/filings",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") != (
        "https://evil.example.com"
    ), "Disallowed origin must not be echoed back."
    print("OPTIONS /filings (Origin: https://evil.example.com) -> "
          "no allow-origin echo")

    print()
    print(
        "PASS: preflight requests from the local frontend origin receive the "
        "expected CORS headers and unknown origins are not allowed."
    )


if __name__ == "__main__":
    main()
