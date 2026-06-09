"""Test the /health endpoint of the read-only research API.

Uses FastAPI TestClient. No Supabase queries, no AI calls, no mutations.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200, (
        f"Expected 200 from /health, got {response.status_code}."
    )
    body = response.json()
    print(f"GET /health -> {response.status_code} {body}")

    assert body["status"] == "ok", f"Expected status='ok', got {body['status']!r}."
    assert body["service"] == "earnings-intelligence-os", (
        f"Expected service='earnings-intelligence-os', got {body['service']!r}."
    )

    print()
    print("PASS: /health returns 200 with the expected status and service fields.")


if __name__ == "__main__":
    main()
