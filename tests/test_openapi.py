from fastapi.testclient import TestClient

from app.main import app


def test_openapi_documents_auth_errors_and_tags() -> None:
    schema = TestClient(app).get("/openapi.json").json()

    assert schema["info"]["summary"]
    assert (
        schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"].lower()
        == "bearer"
    )
    tags = {tag["name"] for tag in schema["tags"]}
    assert {"Auth", "Conversations", "Messages", "Documents", "Orders"} <= tags
    assert "Autenticação" in schema["info"]["description"]


def test_openapi_operations_have_summaries() -> None:
    schema = TestClient(app).get("/openapi.json").json()

    missing = [
        f"{method.upper()} {path}"
        for path, operations in schema["paths"].items()
        for method, operation in operations.items()
        if method in {"get", "post", "patch", "delete", "put"}
        and not operation.get("summary")
    ]

    assert missing == []
