from fastapi.testclient import TestClient

from customer_support_agent.app import app

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Customer Support Agent API",
        "version": "0.1.0",
        "status": "ok",
    }


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
