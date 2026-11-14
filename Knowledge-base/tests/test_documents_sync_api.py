"""`POST /documents/sync` — index tăng dần (KB-5.1).

Khác `refresh`: **không** clear index. Nhưng guard vẫn phải giống refresh — nếu folder không tồn tại/rỗng thì
sync sẽ coi mọi file đang có index là "đã bị xoá" và **xoá sạch** (mất dữ liệu).
"""

from types import SimpleNamespace

import app.main as main_module


def _patch_settings(monkeypatch, folder: str):
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: SimpleNamespace(documents_folder=folder, supported_extensions=[".md", ".txt"]),
    )


def test_sync_blocked_when_folder_missing(api_client, fake_document_service, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, str(tmp_path / "khong-ton-tai"))

    response = api_client.post("/documents/sync")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "documents_folder_empty"
    # Không được chạy sync: nếu chạy, mọi file đang index bị coi là "removed" ⇒ xoá sạch
    assert fake_document_service.calls == []


def test_sync_blocked_when_folder_has_no_supported_files(api_client, fake_document_service, monkeypatch, tmp_path):
    (tmp_path / "notes.bin").write_text("không hỗ trợ")
    _patch_settings(monkeypatch, str(tmp_path))

    response = api_client.post("/documents/sync")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "documents_folder_empty"
    assert fake_document_service.calls == []


def test_sync_returns_counts_and_never_clears(api_client, fake_document_service, monkeypatch, tmp_path):
    (tmp_path / "doc.md").write_text("# tài liệu thật")
    _patch_settings(monkeypatch, str(tmp_path))

    response = api_client.post("/documents/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["added"] == ["moi.md"]
    assert body["updated"] == ["sua.md"]
    assert body["removed"] == ["da-xoa.md"]
    assert body["skipped"][0]["reason"].startswith("too_large")
    assert body["unchanged"] == 4
    assert body["total_chunks"] == 6
    assert body["elapsed_ms"] == 1234
    # QUAN TRỌNG: sync không bao giờ clear index
    assert "clear_database" not in fake_document_service.calls
    assert fake_document_service.calls == ["sync_documents"]


def test_sync_message_reports_no_changes(api_client, fake_document_service, monkeypatch, tmp_path):
    (tmp_path / "doc.md").write_text("# tài liệu thật")
    _patch_settings(monkeypatch, str(tmp_path))
    fake_document_service.sync_documents = _no_change_sync(fake_document_service)

    body = api_client.post("/documents/sync").json()

    assert "Không có thay đổi" in body["message"]


def _no_change_sync(service):
    async def _run():
        service.calls.append("sync_documents")
        return {
            "added": [],
            "updated": [],
            "removed": [],
            "skipped": [],
            "unchanged": 9,
            "total_chunks": 0,
            "removed_chunks": 0,
            "elapsed_ms": 12,
            "details": [],
        }

    return _run
