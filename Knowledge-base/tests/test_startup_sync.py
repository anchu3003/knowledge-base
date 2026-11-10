"""Test trạng thái index sync lúc khởi động (TD-25).

Trước TD-25: `lifespan` **await** sync ⇒ app chưa phục vụ cho tới khi xong, và không có chỗ nào xem
tiến trình (chỉ log). Sau TD-25: sync chạy nền + trạng thái hiện ở `/ready` và `/documents/status`.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app, _run_startup_sync, get_document_service, startup_sync_state
from app.services.startup_sync import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_IDLE,
    STATUS_RUNNING,
    STATUS_SKIPPED,
    StartupSyncState,
)


# ------------------------------
# StartupSyncState (thuần)
# ------------------------------
def test_state_starts_idle():
    state = StartupSyncState()
    assert state.status == STATUS_IDLE
    assert state.as_dict()["status"] == STATUS_IDLE
    assert state.detail() == "index sync chưa chạy"


def test_state_running_then_done_with_summary():
    state = StartupSyncState()
    state.start()
    assert state.status == STATUS_RUNNING
    assert state.running is True
    assert "đang chạy nền" in state.detail()

    state.finish(
        {
            "added": ["a.md"],
            "updated": ["b.md", "c.md"],
            "removed": [],
            "unchanged": 53,
            "total_chunks": 601,
            "elapsed_ms": 1200,
        }
    )
    payload = state.as_dict()
    assert payload["status"] == STATUS_DONE
    assert payload["added"] == 1
    assert payload["updated"] == 2
    assert payload["removed"] == 0
    assert payload["unchanged"] == 53
    assert payload["chunks"] == 601
    assert payload["elapsed_seconds"] is not None
    assert "601 chunk" in state.detail()


def test_state_failed_only_keeps_error_type():
    """Message gốc có thể chứa path/PII ⇒ chỉ giữ **tên loại lỗi** (rule 30-pii-safety)."""
    state = StartupSyncState()
    state.start()
    state.fail("DocumentStoreError")
    payload = state.as_dict()
    assert payload["status"] == STATUS_FAILED
    assert payload["error"] == "DocumentStoreError"
    assert "index cũ" in state.detail()


def test_state_skipped_records_reason():
    state = StartupSyncState()
    state.skip("folder không tồn tại")
    assert state.status == STATUS_SKIPPED
    assert "bỏ qua" in state.detail()


def test_state_detail_running_has_no_finish_time():
    state = StartupSyncState()
    state.start()
    payload = state.as_dict()
    assert payload["status"] == STATUS_RUNNING
    assert payload["elapsed_seconds"] is not None
    assert payload["elapsed_seconds"] >= 0


# ------------------------------
# _run_startup_sync (coroutine nền)
# ------------------------------
class FakeSyncService:
    def __init__(self, result=None, error=None):
        self.result = result or {"added": [], "updated": [], "removed": [], "unchanged": 0, "total_chunks": 0}
        self.error = error
        self.calls = 0

    async def sync_documents(self):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def test_background_job_marks_done_with_summary():
    service = FakeSyncService({"added": ["x.md"], "updated": [], "removed": [], "unchanged": 1, "total_chunks": 9})
    state = StartupSyncState()
    asyncio.run(_run_startup_sync(service, state, supported=2))
    assert service.calls == 1
    assert state.status == STATUS_DONE
    assert state.as_dict()["chunks"] == 9


def test_background_job_failure_does_not_raise():
    """Lỗi sync **không** được làm chết app — chỉ ghi trạng thái `failed`."""
    service = FakeSyncService(error=RuntimeError("disk full"))
    state = StartupSyncState()
    asyncio.run(_run_startup_sync(service, state, supported=1))
    assert state.status == STATUS_FAILED
    assert state.as_dict()["error"] == "RuntimeError"


# ------------------------------
# Endpoint: trạng thái hiện ở /ready + /documents/status
# ------------------------------
@pytest.fixture
def client_with_state(api_client, monkeypatch):
    """Gắn `StartupSyncState` vào module (TestClient không chạy lifespan)."""
    state = StartupSyncState()
    monkeypatch.setattr("app.main.startup_sync_state", state)
    return api_client, state


def test_ready_reports_startup_sync_running(client_with_state):
    client, state = client_with_state
    state.start()
    body = client.get("/ready").json()
    assert body["checks"]["startup_sync"]["ok"] is True
    assert "đang chạy nền" in body["checks"]["startup_sync"]["detail"]
    # thông tin, KHÔNG làm hỏng readiness
    assert body["status"] in ("ok", "degraded")


def test_ready_reports_startup_sync_done(client_with_state):
    client, state = client_with_state
    state.start()
    state.finish({"added": ["a.md"], "updated": [], "removed": [], "unchanged": 0, "total_chunks": 12})
    detail = client.get("/ready").json()["checks"]["startup_sync"]["detail"]
    assert "12 chunk" in detail and "+1 mới" in detail


def test_ready_reports_rate_limit_flag(client_with_state):
    client, _state = client_with_state
    checks = client.get("/ready").json()["checks"]
    assert "rate_limit" in checks
    assert checks["rate_limit"]["ok"] is True
    assert "rate limit" in checks["rate_limit"]["detail"]


def test_documents_status_includes_startup_sync(client_with_state):
    client, state = client_with_state
    state.start()
    state.skip("folder rỗng")
    body = client.get("/documents/status").json()
    assert body["startup_sync"]["status"] == STATUS_SKIPPED
