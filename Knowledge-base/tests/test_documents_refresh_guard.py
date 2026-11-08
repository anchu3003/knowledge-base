"""Guard an toàn cho `POST /documents/refresh` (KB-4.10).

Refresh = clear index + auto-load từ folder. Nếu folder không tồn tại/rỗng thì phải **chặn trước khi clear**,
nếu không index cũ (đắt: embedding) sẽ mất mà không có nguồn thay thế.

Bug thật phát hiện 2026-11-08: `.dockerignore` của BE loại `Interview/` ⇒ trong container folder rỗng nhưng
index vẫn có 601 chunk ⇒ bấm Refresh là mất sạch.
"""

from types import SimpleNamespace

import app.main as main_module


def _patch_settings(monkeypatch, folder: str):
    """`main.refresh_documents` đọc settings qua `get_settings()` (không phải dependency) ⇒ patch tường minh."""
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: SimpleNamespace(documents_folder=folder, supported_extensions=[".md", ".txt"]),
    )


def test_refresh_blocked_when_folder_missing(api_client, fake_document_service, monkeypatch, tmp_path):
    _patch_settings(monkeypatch, str(tmp_path / "khong-ton-tai"))

    response = api_client.post("/documents/refresh")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "documents_folder_empty"
    # QUAN TRỌNG: không được clear index khi chưa chắc có gì để index lại
    assert fake_document_service.calls == []


def test_refresh_blocked_when_folder_has_no_supported_files(api_client, fake_document_service, monkeypatch, tmp_path):
    (tmp_path / "notes.bin").write_text("không phải định dạng hỗ trợ")
    _patch_settings(monkeypatch, str(tmp_path))

    response = api_client.post("/documents/refresh")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "documents_folder_empty"
    assert fake_document_service.calls == []


def test_refresh_allowed_when_folder_has_supported_files(api_client, fake_document_service, monkeypatch, tmp_path):
    (tmp_path / "doc.md").write_text("# tài liệu thật")
    _patch_settings(monkeypatch, str(tmp_path))

    response = api_client.post("/documents/refresh")

    assert response.status_code == 200
    assert fake_document_service.calls == ["clear_database", "auto_load_documents"]


def test_count_supported_files_counts_only_supported_extensions(tmp_path):
    (tmp_path / "a.md").write_text("x")
    (tmp_path / "b.txt").write_text("x")
    (tmp_path / "c.pdf").write_text("x")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "d.md").write_text("x")

    assert main_module.count_supported_files(tmp_path, [".md", ".txt"]) == 3
    assert main_module.count_supported_files(tmp_path / "missing", [".md"]) == 0
