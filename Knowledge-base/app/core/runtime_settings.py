"""Cấu hình chỉnh được **lúc chạy** (KB-9.4) — không cần restart container.

Bối cảnh: mọi thứ đang đọc từ env lúc khởi động (`app/core/config.py`). Muốn thử nhanh một tham số
(`RETRIEVAL_K`, `RERANK_TOP_N`, ngưỡng liên quan…) thì phải sửa `.env` + restart ⇒ không ai thử. Ở đây mở
một **whitelist nhỏ** các tham số an toàn để đổi qua API/UI, mặc định lấy từ server (env).

Nguyên tắc:

- **Chỉ tham số đổi được mà KHÔNG cần re-index**: `retrieval_k`, `rerank_top_n`, `relevance_min_score`,
  `hybrid_alpha`, `hybrid_candidate_k`, `multi_query_*`, `dedup_*`, `max_chunks_per_file`, `enable_rerank`,
  `default_temperature`, `default_max_tokens`. **Không** cho đổi `CHUNK_SIZE`/`EMBEDDING_*`/`CHROMA_*`
  (đổi là phải re-index — ADR-0004/0011).
- Áp dụng bằng **setattr lên settings singleton** ⇒ mọi service đọc `self.settings.*` thấy ngay.
- Đổi tham số ảnh hưởng retrieval/rerank ⇒ **tính lại `config_fingerprint` + xoá cache rerank** (nếu không,
  cache trả điểm của cấu hình cũ — đúng lớp bug ADR-0012 cảnh báo).
- Mỗi tham số có `min`/`max` để chặn giá trị phá hệ thống (vd `rerank_top_n=50` ⇒ ~25 s/câu).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Tunable:
    """Một tham số chỉnh được lúc chạy."""

    key: str
    kind: str  #: "int" | "float" | "bool"
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    description: str = ""
    #: Ảnh hưởng tập ứng viên/điểm ⇒ phải xoá cache rerank + tính lại fingerprint.
    affects_retrieval: bool = True

    def coerce(self, value: Any) -> Any:
        """Validate + chuẩn hoá. Raise `ValueError` với message **không** chứa giá trị thô."""
        if self.kind == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)) and value in (0, 1):
                return bool(value)
            if isinstance(value, str) and value.lower() in ("true", "false"):
                return value.lower() == "true"
            raise ValueError(f"{self.key}: phải là true/false")

        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"{self.key}: phải là số")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{self.key}: phải là số") from None

        if self.kind == "int":
            if number != int(number):
                raise ValueError(f"{self.key}: phải là số nguyên")
            number = int(number)

        if self.minimum is not None and number < self.minimum:
            raise ValueError(f"{self.key}: nhỏ hơn mức tối thiểu {self.minimum}")
        if self.maximum is not None and number > self.maximum:
            raise ValueError(f"{self.key}: lớn hơn mức tối đa {self.maximum}")
        return number


#: Whitelist — cố ý **không** có tham số cần re-index.
TUNABLES: Dict[str, Tunable] = {
    t.key: t
    for t in (
        Tunable("retrieval_k", "int", 1, 12,
                "Số chunk đưa vào prompt (nhiều hơn = nhiều ngữ cảnh, chậm hơn)"),
        Tunable("rerank_top_n", "int", 2, 20,
                "Số ứng viên cross-encoder chấm (giảm = nhanh, có thể mất nguồn tốt)"),
        Tunable("relevance_min_score", "float", 0.0, 0.5,
                "Ngưỡng điểm rerank: dưới ngưỡng thì bỏ nguồn (0 = tắt lọc)"),
        Tunable("hybrid_alpha", "float", 0.0, 1.0, "Trọng số dense (1.0) vs BM25 (0.0)"),
        Tunable("hybrid_candidate_k", "int", 5, 50, "Số ứng viên gộp trước khi dedup/rerank"),
        Tunable("multi_query_enabled", "bool", description="Tách câu nhiều ý thành nhiều truy vấn"),
        Tunable("multi_query_max_parts", "int", 1, 5, "Số phần tối đa khi tách câu"),
        Tunable("dedup_enabled", "bool", description="Gộp chunk gần trùng trước khi rerank"),
        Tunable("max_chunks_per_file", "int", 1, 5, "Tối đa số chunk mỗi file trong top-k"),
        Tunable("enable_rerank", "bool", description="Bật cross-encoder rerank"),
        Tunable("default_temperature", "float", 0.0, 1.5, "Temperature mặc định cho câu trả lời", False),
        Tunable("default_max_tokens", "int", 256, 8000, "max_tokens mặc định cho câu trả lời", False),
    )
}

#: Override hiện tại (`key → value`) để `GET /settings` biết cái nào khác default.
_overrides: Dict[str, Any] = {}
#: Default gốc theo env, ghi lại lần đầu thấy settings (để "khôi phục mặc định" đúng nghĩa).
_env_defaults: Dict[str, Any] = {}


def _env_default(settings: Settings, key: str) -> Any:
    if key not in _env_defaults:
        _env_defaults[key] = getattr(settings, key)
    return _env_defaults[key]


def _capture_defaults(settings: Settings) -> None:
    """Ghi lại default env **trước** khi có ai đổi (gọi ở đầu `apply_updates`/`reset`)."""
    for key in TUNABLES:
        _env_default(settings, key)


def current(settings: Settings) -> Dict[str, Any]:
    """Giá trị đang có hiệu lực."""
    return {key: getattr(settings, key) for key in TUNABLES}


def describe(settings: Settings) -> Dict[str, Any]:
    """Payload cho `GET /settings` (UI dựng control từ đây)."""
    _capture_defaults(settings)
    return {
        "values": current(settings),
        "defaults": {key: _env_default(settings, key) for key in TUNABLES},
        "overridden": sorted(_overrides),
        "tunables": [
            {
                "key": t.key,
                "kind": t.kind,
                "min": t.minimum,
                "max": t.maximum,
                "description": t.description,
            }
            for t in TUNABLES.values()
        ],
    }


def apply_updates(
        settings: Settings,
        values: Dict[str, Any],
        on_retrieval_change: Optional[Callable[[], None]] = None,
) -> Dict[str, Any]:
    """Áp `values` (partial). Trả giá trị hiện tại. Raise `ValueError` nếu key/giá trị không hợp lệ."""
    _capture_defaults(settings)
    unknown = [key for key in values if key not in TUNABLES]
    if unknown:
        raise ValueError(f"tham số không chỉnh được: {', '.join(sorted(unknown))}")

    coerced: Dict[str, Any] = {}
    for key, raw in values.items():
        coerced[key] = TUNABLES[key].coerce(raw)  # message lỗi đã an toàn

    retrieval_changed = False
    for key, value in coerced.items():
        if getattr(settings, key, None) == value:
            continue
        setattr(settings, key, value)
        _overrides[key] = value
        retrieval_changed = retrieval_changed or TUNABLES[key].affects_retrieval
        # log chỉ tên tham số + giá trị cấu hình (không có nội dung người dùng)
        logger.info("runtime setting changed: %s=%s", key, value)

    if retrieval_changed and on_retrieval_change is not None:
        on_retrieval_change()

    return current(settings)


def reset(settings: Settings, on_retrieval_change: Optional[Callable[[], None]] = None) -> Dict[str, Any]:
    """Trả mọi tham số về default của server."""
    _capture_defaults(settings)
    changed = False
    for key in TUNABLES:
        default = _env_default(settings, key)
        if getattr(settings, key, None) != default:
            setattr(settings, key, default)
            changed = True
    _overrides.clear()
    logger.info("runtime settings reset to server defaults")
    if changed and on_retrieval_change is not None:
        on_retrieval_change()
    return current(settings)


def reset_for_tests() -> None:
    _overrides.clear()
    _env_defaults.clear()
