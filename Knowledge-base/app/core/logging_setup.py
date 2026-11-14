"""Cấu hình logging cho toàn app (KB-5.9 — trả TD-18).

Vấn đề trước đây: không có `basicConfig`/`dictConfig` ở đâu cả ⇒ logger `app.*` không có handler ⇒ mọi
`logger.info(...)` (vd `multi-query: 2 phần`, `rerank cache hit`, `Conversation store ready`) **vô hình** khi
chạy uvicorn (chỉ WARNING+ lọt qua `lastResort` handler của root). Muốn debug phải đọc `print()`.

Vì sao tách module: test được (gọi 2 lần không nhân đôi handler) và `lifespan` chỉ cần 1 dòng.

**Không** log PII/secret: hàm này chỉ cấu hình format/level — nội dung log vẫn phải qua quy ước
`.clinerules/30-pii-safety.md`.
"""

from __future__ import annotations

import logging
from typing import Optional

#: Định dạng 1 dòng log: `INFO app.services.chat_service: multi-query: 2 phần, 3 hit`.
LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"

#: Thư viện ồn ào (INFO của chúng không giúp debug app) ⇒ hạ xuống WARNING.
NOISY_LOGGERS = (
    "chromadb",
    "chromadb.telemetry",
    "httpx",
    "httpcore",
    "urllib3",
    "sentence_transformers",
    "transformers",
    "huggingface_hub",
)

#: Marker để nhận ra handler do module này gắn (idempotent, không nhân đôi khi reload/test).
_HANDLER_NAME = "kb-console"


def resolve_level(raw: Optional[str]) -> int:
    """Đổi tên level (`info`/`DEBUG`/`20`) sang hằng số logging; giá trị lạ ⇒ `INFO`."""
    if raw is None:
        return logging.INFO
    text = str(raw).strip().upper()
    if not text:
        return logging.INFO
    if text.isdigit():
        return int(text)
    return getattr(logging, text, logging.INFO)


def configure_logging(level: Optional[str] = None) -> int:
    """Gắn 1 console handler cho root logger (idempotent). Trả về level đã áp dụng.

    Gọi 2 lần (vd test + lifespan) **không** tạo handler thứ 2 ⇒ không log trùng dòng.
    """
    resolved = resolve_level(level)

    root = logging.getLogger()
    existing = next((h for h in root.handlers if getattr(h, "name", None) == _HANDLER_NAME), None)
    if existing is None:
        handler = logging.StreamHandler()
        handler.name = _HANDLER_NAME
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(handler)
    else:
        handler = existing

    handler.setLevel(resolved)
    root.setLevel(resolved)

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(max(resolved, logging.WARNING))

    return resolved
