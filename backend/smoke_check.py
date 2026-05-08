from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    client = TestClient(app)
    for path in ["/health", "/imports/spec", "/model/status", "/system/status"]:
        response = client.get(path)
        response.raise_for_status()
        print(f"{path} {response.status_code}")


if __name__ == "__main__":
    main()
