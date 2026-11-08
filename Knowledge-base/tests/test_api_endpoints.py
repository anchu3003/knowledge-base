"""Test tầng HTTP — happy path cho toàn bộ endpoint (KB-3.5, trả TD-4).

Dùng fixture ở `tests/conftest.py`: fake service qua `dependency_overrides`, không chạy lifespan,
không load model/Chroma/network.
"""
import pytest

from app.main import app, get_health_service


# ------------------------------
# Meta / probes
# ------------------------------
def test_root_endpoint_contract(api_client):
    response = api_client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "message": "RAG Chatbot API is running",
        "version": "1.0.0",
    }


def test_health_liveness_ok(api_client):
    response = api_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "1.0.0"
    assert body["uptime_seconds"] >= 0


def test_ready_ok_when_documents_and_config_present(api_client, fake_document_service, health_service_factory, monkeypatch):
    import app.main as main_module

    # `/ready` đọc biến toàn cục (không phải dependency) ⇒ monkeypatch tường minh.
    monkeypatch.setattr(main_module, "document_service", fake_document_service)
    app.dependency_overrides[get_health_service] = lambda: health_service_factory()

    response = api_client.get("/ready")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["checks"]["collection"]["detail"] == "7 chunks indexed"


def test_ready_degraded_when_services_not_initialized(api_client, health_service_factory):
    app.dependency_overrides[get_health_service] = lambda: health_service_factory()

    response = api_client.get("/ready")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "degraded"
    assert body["checks"]["collection"]["ok"] is False


def test_ready_error_when_provider_config_broken(api_client, health_service_factory):
    from app.core.config import Settings  # noqa: F401  (giữ import để rõ nguồn settings thật)

    broken = health_service_factory(openai_api_key=type("S", (), {"get_secret_value": lambda self: ""})())
    app.dependency_overrides[get_health_service] = lambda: broken

    response = api_client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "error"


# ------------------------------
# Chat (non-stream)
# ------------------------------
def test_chat_happy_path_returns_answer_and_sources(api_client, fake_chat_service):
    response = api_client.post("/chat", json={"message": "xin chao", "conversation_id": "conv-1"})

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "echo: xin chao"
    assert body["conversation_id"] == "conv-1"
    assert body["sources"][0]["citation_id"] == "S1"
    assert fake_chat_service.chat_calls == [{"message": "xin chao", "conversation_id": "conv-1"}]


# ------------------------------
# Documents
# ------------------------------
def test_documents_status_ok(api_client, fake_document_service):
    response = api_client.get("/documents/status")

    assert response.status_code == 200
    assert response.json()["document_count"] == 7
    assert fake_document_service.calls == ["get_status"]


def test_documents_refresh_uses_fake_service(api_client, fake_document_service):
    response = api_client.post("/documents/refresh")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["processed_files"] == 2
    assert body["total_chunks"] == 7
    assert body["message"] == "Successfully refreshed 2 documents"
    # Q&A KB-3.5: chỉ verify route + shape, dùng fake ⇒ không xoá/re-index index thật
    assert fake_document_service.calls == ["clear_database", "auto_load_documents"]


def test_documents_clear_ok(api_client, fake_document_service):
    response = api_client.delete("/documents/clear")

    assert response.status_code == 200
    assert response.json() == {"message": "Document database cleared successfully"}
    assert fake_document_service.calls == ["clear_database"]


def test_documents_folder_info_ok(api_client):
    response = api_client.get("/documents/folder-info")

    assert response.status_code == 200
    body = response.json()
    assert "folder_path" in body
    assert "exists" in body
