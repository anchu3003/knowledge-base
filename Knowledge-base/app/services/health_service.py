"""Health & readiness checks (KB-3.4).

Tách khỏi route để test không cần HTTP/Chroma:

- **liveness** (`GET /health`): process còn sống — không phụ thuộc Chroma/provider, luôn rẻ, không bao giờ 5xx.
- **readiness** (`GET /ready`): đủ điều kiện trả lời chưa? 3 check **rẻ** (`provider_config`, `prompt_file`,
  `collection`) + `deep=true` (tuỳ chọn, **mặc định tắt**) gọi provider 1 request `max_tokens=1` để kiểm key thật.

Quy ước trạng thái:

| status | HTTP | Khi nào |
|---|---|---|
| `ok` | 200 | provider config + prompt + collection đều ổn |
| `degraded` | 200 | thiếu tài liệu (collection rỗng/lỗi) — vẫn nhận request, trả lời "không có trong knowledge base" |
| `error` | 503 | thiếu cấu hình provider / thiếu prompt / `deep` mà provider không trả lời |

Probe **không** trả `str(exception)` hay giá trị secret: chỉ tên biến env còn thiếu + `code` lỗi (taxonomy KB-3.1).
"""

import logging
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

HealthPayload = Dict[str, Any]
ProbeCallable = Callable[[], Awaitable[Any]]


class HealthService:
    """Tính payload cho `/health` (liveness) và `/ready` (readiness)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.started_at = time.monotonic()

    def liveness(self) -> HealthPayload:
        """Process còn sống ⇒ luôn `ok` (không chạm Chroma/provider)."""
        return {
            "status": "ok",
            "version": str(getattr(self.settings, "app_version", "unknown")),
            "uptime_seconds": round(time.monotonic() - self.started_at, 3),
        }

    async def readiness(
            self,
            *,
            document_service: Any = None,
            provider_probe: Optional[ProbeCallable] = None,
            deep: bool = False,
            startup_sync: Any = None,
            rate_limit: Optional[Dict[str, Any]] = None,
    ) -> Tuple[HealthPayload, int]:
        """Trả `(payload, http_status)`. `deep=True` mới gọi provider (tốn 1 request)."""
        checks: Dict[str, Dict[str, Any]] = {
            "provider_config": self._check_provider_config(),
            "prompt_file": self._check_prompt_file(),
            "collection": self._check_collection(document_service),
        }
        if startup_sync is not None:
            # TD-25: sync chạy nền ⇒ đây là **thông tin**, không phải điều kiện sẵn sàng
            # (chat vẫn trả lời được bằng index cũ).
            checks["startup_sync"] = {"ok": True, "detail": _startup_sync_detail(startup_sync)}
        if rate_limit is not None:
            checks["rate_limit"] = _check_rate_limit(rate_limit)
        if deep:
            checks["provider"] = await self._check_provider(provider_probe)


        status = "ok"
        if not checks["provider_config"]["ok"] or not checks["prompt_file"]["ok"]:
            status = "error"
        elif deep and not checks["provider"]["ok"]:
            status = "error"
        elif not checks["collection"]["ok"]:
            status = "degraded"

        http_status = 503 if status == "error" else 200
        if status == "error":
            failed = [name for name, check in checks.items() if not check["ok"]]
            logger.warning("readiness failed: status=error failed_checks=%s", ",".join(failed))

        return {"status": status, "checks": checks}, http_status

    # ------------------------------
    # Từng check (rẻ, không network)
    # ------------------------------
    def _check_provider_config(self) -> Dict[str, Any]:
        """Chỉ kiểm **có cấu hình**, không kiểm key đúng/sai (dùng `deep=true` cho việc đó)."""
        missing = []
        if not _secret_value(getattr(self.settings, "openai_api_key", None)).strip():
            missing.append("OPENAI_API_KEY")
        if not str(getattr(self.settings, "openai_model", "") or "").strip():
            missing.append("OPENAI_MODEL")
        if not str(getattr(self.settings, "openai_base_url", "") or "").strip():
            missing.append("OPENAI_BASE_URL")

        if missing:
            # Chỉ tên biến env, KHÔNG giá trị (PII/secret rule).
            return {"ok": False, "detail": "missing config: " + ", ".join(missing)}
        return {"ok": True, "detail": f"model={self.settings.openai_model}"}

    def _check_prompt_file(self) -> Dict[str, Any]:
        """Kiểm prompt template (KB-5.9 — trả TD-19).

        `ChatService._create_system_prompt()` có **prompt fallback** dựng sẵn trong code ⇒ thiếu file **không**
        làm chat hỏng. Trước KB-5.9, `/ready` trả `ok: false` khi thiếu file ⇒ health đỏ sai và container bị
        coi là "chưa sẵn sàng" dù vẫn trả lời được.
        """
        raw_path = getattr(self.settings, "system_prompt_path", None)
        if not raw_path:
            return {"ok": True, "detail": "SYSTEM_PROMPT_PATH is not set — dùng prompt fallback trong code"}
        path = Path(raw_path)
        if not path.is_file():
            return {"ok": True, "detail": f"prompt file not found: {path.name} — dùng prompt fallback trong code"}
        return {"ok": True, "detail": f"prompt file: {path.name}"}

    def _check_collection(self, document_service: Any) -> Dict[str, Any]:
        if document_service is None:
            return {"ok": False, "detail": "document service not initialized"}
        try:
            count = int(document_service.collection.count())
        except Exception as exc:  # Chroma lỗi ⇒ coi như chưa sẵn sàng, không lộ chi tiết
            logger.warning("readiness collection check failed: %s", type(exc).__name__)
            return {"ok": False, "detail": "collection unavailable"}
        if count <= 0:
            return {"ok": False, "detail": "collection is empty (0 chunks)"}
        return {"ok": True, "detail": f"{count} chunks indexed"}

    async def _check_provider(self, provider_probe: Optional[ProbeCallable]) -> Dict[str, Any]:
        if provider_probe is None:
            return {"ok": False, "detail": "provider not initialized"}
        try:
            await provider_probe()
        except AppError as exc:
            return {"ok": False, "detail": f"provider call failed: {exc.code}"}
        except Exception as exc:
            logger.warning("readiness provider probe failed: %s", type(exc).__name__)
            return {"ok": False, "detail": "provider call failed"}
        return {"ok": True, "detail": "provider answered a 1-token ping"}


def _secret_value(value: Any) -> str:
    """`SecretStr` → str (không log giá trị), `None` → chuỗi rỗng."""
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        return str(getter() or "")
    return str(value)


def _startup_sync_detail(state: Any) -> str:
    """`StartupSyncState.detail()` nếu có; chấp nhận cả dict (dựng tay trong test)."""
    if hasattr(state, "detail") and callable(state.detail):
        return str(state.detail())
    if isinstance(state, dict):
        return str(state.get("detail") or state.get("status") or "unknown")
    return "unknown"


def _check_rate_limit(stats: Dict[str, Any]) -> Dict[str, Any]:
    """Rate limit (TD-20) — **thông tin**: bật/tắt + hạn mức, không tính vào `status`.

    Bật rate limit mà làm `/ready` đỏ thì sai: 429 cho client là hành vi mong muốn, không phải lỗi
    readiness (cùng lý do KB-5.9 không cho prompt file làm 503).
    """
    if not stats.get("enabled"):
        return {"ok": True, "detail": "rate limit tắt (RATE_LIMIT_ENABLED=false)"}
    return {
        "ok": True,
        "detail": (
            f"{stats.get('max_requests')} req / {stats.get('window_seconds')}s mỗi IP trên "
            f"/chat + /chat/stream · đã chặn {stats.get('blocked', 0)}"
        ),
    }

