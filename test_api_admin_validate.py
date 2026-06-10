"""Test the GET /admin/validate token-check endpoint.

No Supabase mutations, no AI calls. Uses a temporary token through the
environment (never printed).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import secrets
from unittest import mock

from fastapi.testclient import TestClient

from app.main import app

TEMP_TOKEN = secrets.token_urlsafe(32)


def main() -> None:
    client = TestClient(app)

    with mock.patch.dict(os.environ, {"ADMIN_API_TOKEN": TEMP_TOKEN}):
        response = client.get("/admin/validate")
        assert response.status_code == 401, f"Got {response.status_code}."
        assert response.json()["detail"] == "Admin token missing or invalid."
        print("Missing token -> 401.")

        response = client.get(
            "/admin/validate", headers={"X-Admin-Token": "wrong-token"}
        )
        assert response.status_code == 401
        print("Wrong token -> 401.")

        response = client.get(
            "/admin/validate", headers={"X-Admin-Token": TEMP_TOKEN}
        )
        assert response.status_code == 200, f"Got {response.status_code}."
        assert response.json() == {"status": "ok"}
        print("Correct token -> 200 {'status': 'ok'}.")

    # Server with no token configured fails closed and never names the var.
    env_without_token = {
        k: v for k, v in os.environ.items() if k != "ADMIN_API_TOKEN"
    }
    with mock.patch.dict(os.environ, env_without_token, clear=True):
        response = client.get(
            "/admin/validate", headers={"X-Admin-Token": TEMP_TOKEN}
        )
        assert response.status_code == 500, f"Got {response.status_code}."
        assert response.json()["detail"] == "Server configuration error."
        assert "ADMIN_API_TOKEN" not in response.text
        print("Unconfigured server token -> safe 500.")

    print()
    print(
        "PASS: /admin/validate confirms valid tokens, rejects missing or "
        "wrong tokens with 401, and fails closed when unconfigured."
    )


if __name__ == "__main__":
    main()
