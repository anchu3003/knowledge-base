"""Trạng thái index sync lúc khởi động (TD-25).

Vấn đề trước đây: `lifespan` **await** `sync_documents()` ⇒ app chưa phục vụ cho tới khi hash xong 56
file (~1,5 s) hoặc tệ hơn khi phải embed file mới (1,2 s/file — KB-5.1). Container mới ở trạng thái
`starting` lâu, healthcheck fail, và **không có cách nào biết sync đang chạy hay đã xong** ngoài đọc log.

Ở đây: sync chạy như **background task**, trạng thái ghi vào object dùng chung đọc được từ `/ready`
(`checks.startup_sync`) và `/documents/status`. Chat vẫn trả lời được ngay với index cũ trong lúc sync —
đúng semantics của KB-5.1 (sync không clear index).

Không dùng `asyncio.Queue`/job queue: 1 job duy nhất lúc khởi động, chưa cần hạ tầng (AGENTS.md §3.4).
"""

from __future__ import annotations

import copy
import threading
import time
from typing import Any, Dict, Optional

#: Trạng thái có thể có của job sync lúc khởi động.
STATUS_IDLE = "idle"          #: chưa chạy (auto-load tắt)
STATUS_RUNNING = "running"    #: đang quét folder / embed
STATUS_DONE = "done"          #: xong, đọc `summary`
STATUS_FAILED = "failed"      #: lỗi — app **vẫn** phục vụ với index cũ
STATUS_SKIPPED = "skipped"    #: folder rỗng/không tồn tại ⇒ cố tình không sync (guard KB-4.10)


class StartupSyncState:
    """Ghi trạng thái job sync khởi động; thread-safe (task asyncio + request đọc `/ready`)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status = STATUS_IDLE
        self._started_at: Optional[float] = None
        self._finished_at: Optional[float] = None
        self._summary: Dict[str, Any] = {}
        self._error: Optional[str] = None
        self._reason: Optional[str] = None

    # ------------------------------------------------------------------ ghi
    def start(self) -> None:
        with self._lock:
            self._status = STATUS_RUNNING
            self._started_at = time.monotonic()
            self._finished_at = None
            self._summary = {}
            self._error = None
            self._reason = None

    def finish(self, summary: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            self._status = STATUS_DONE
            self._finished_at = time.monotonic()
            self._summary = copy.deepcopy(summary or {})

    def fail(self, error: str) -> None:
        with self._lock:
            self._status = STATUS_FAILED
            self._finished_at = time.monotonic()
            self._error = error

    def skip(self, reason: str) -> None:
        with self._lock:
            self._status = STATUS_SKIPPED
            self._finished_at = time.monotonic()
            self._reason = reason

    # ------------------------------------------------------------------ đọc
    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @property
    def running(self) -> bool:
        return self.status == STATUS_RUNNING

    def as_dict(self) -> Dict[str, Any]:
        """Payload gọn để nhét vào `/ready`/`/documents/status` (không lộ path tuyệt đối)."""
        with self._lock:
            elapsed: Optional[float] = None
            if self._started_at is not None:
                end = self._finished_at if self._finished_at is not None else time.monotonic()
                elapsed = round(end - self._started_at, 3)
            payload: Dict[str, Any] = {
                "status": self._status,
                "elapsed_seconds": elapsed,
            }
            if self._summary:
                payload["chunks"] = int(self._summary.get("total_chunks") or 0)
                payload["added"] = len(self._summary.get("added") or [])
                payload["updated"] = len(self._summary.get("updated") or [])
                payload["removed"] = len(self._summary.get("removed") or [])
                payload["unchanged"] = int(self._summary.get("unchanged") or 0)
            if self._error:
                # Chỉ tên loại lỗi — message có thể chứa path/PII (rule 30-pii-safety).
                payload["error"] = self._error
            if self._reason:
                payload["reason"] = self._reason
            return payload

    def detail(self) -> str:
        """1 dòng mô tả cho `checks.startup_sync.detail` của `/ready`."""
        data = self.as_dict()
        status = data["status"]
        if status == STATUS_RUNNING:
            return "index sync đang chạy nền — chat dùng index hiện có"
        if status == STATUS_DONE:
            return (
                f"index sync xong trong {data.get('elapsed_seconds')}s "
                f"(+{data.get('added', 0)} mới, ~{data.get('updated', 0)} cập nhật, "
                f"-{data.get('removed', 0)} xoá, {data.get('chunks', 0)} chunk)"
            )
        if status == STATUS_FAILED:
            return f"index sync lỗi ({data.get('error')}) — vẫn phục vụ với index cũ"
        if status == STATUS_SKIPPED:
            return f"index sync bỏ qua ({data.get('reason')})"
        return "index sync chưa chạy"
