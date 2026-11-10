"""KB-9.4: lọc nguồn theo ngưỡng rerank score + metadata `dropped_sources`.

Ngưỡng mặc định 0,02 chốt từ đo trên bộ vàng 28 câu: câu ngoài phạm vi có score <= 0,0003; chunk đúng
thấp nhất 0,0031 (p10 0,0278). Test ở đây kiểm **hành vi**, không phụ thuộc con số cụ thể.
"""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core import runtime_settings
from app.models.schemas import ChatRequest
from app.services.document_service import DocumentService


def _service(threshold: float) -> DocumentService:
    """DocumentService không qua `__init__` (khỏi load Chroma/model) — chỉ cần settings."""
    service = object.__new__(DocumentService)
    service.settings = SimpleNamespace(relevance_min_score=threshold)
    return service


def _docs(*scores: float) -> list[dict]:
    return [{"chunk_id": f"c{i}", "content": "x", "score": s, "metadata": {}} for i, s in enumerate(scores)]


def test_filter_keeps_scores_at_or_above_threshold():
    kept, dropped = _service(0.02).filter_by_relevance(_docs(0.91, 0.05, 0.02, 0.019, 0.0))
    assert [d["score"] for d in kept] == [0.91, 0.05, 0.02]  # biên được giữ
    assert dropped == 2


def test_filter_disabled_when_threshold_is_zero():
    kept, dropped = _service(0.0).filter_by_relevance(_docs(0.9, 0.0))
    assert len(kept) == 2 and dropped == 0


def test_filter_can_drop_everything():
    """Câu ngoài phạm vi: mọi score ~0 ⇒ bỏ hết ⇒ context rỗng ⇒ prompt chuyển nhánh \"không có trong KB\"."""
    kept, dropped = _service(0.02).filter_by_relevance(_docs(0.0003, 0.0001, 0.0))
    assert kept == [] and dropped == 3


def test_filter_handles_missing_score_key():
    docs = [{"chunk_id": "a", "content": "x"}, {"chunk_id": "b", "content": "y", "score": 0.5}]
    kept, dropped = _service(0.02).filter_by_relevance(docs)
    assert [d["chunk_id"] for d in kept] == ["b"] and dropped == 1


def test_settings_default_is_measured_value():
    """Ngưỡng mặc định phải là số đã đo (0,02), không phải 0 (tắt lọc) hay 0,5 (bỏ quá tay)."""
    from app.core.config import Settings

    field = Settings.model_fields["relevance_min_score"]
    assert field.default == pytest.approx(0.02)


def test_chat_request_rejects_temperature_out_of_range():
    """Chặn ở schema (KB-9.1) — giữ nguyên khi thêm ngưỡng."""
    with pytest.raises(ValidationError):
        ChatRequest(message="x", temperature=3.0)


# ------------------------------
# Runtime settings (whitelist)
# ------------------------------
class _FakeSettings:
    """Settings giả đủ field cho whitelist."""

    def __init__(self) -> None:
        for key, tunable in runtime_settings.TUNABLES.items():
            setattr(self, key, tunable.minimum if tunable.kind == "int" else
                    (tunable.minimum if tunable.kind == "float" else False))
        self.retrieval_k = 6
        self.rerank_top_n = 6
        self.relevance_min_score = 0.02
        self.default_temperature = 0.2
        self.default_max_tokens = 2500


@pytest.fixture(autouse=True)
def _clean_runtime_settings():
    runtime_settings.reset_for_tests()
    yield
    runtime_settings.reset_for_tests()


def test_apply_updates_sets_values_and_reports_overrides():
    settings = _FakeSettings()
    calls: list[str] = []

    runtime_settings.apply_updates(
        settings, {"retrieval_k": 8, "relevance_min_score": 0.05},
        on_retrieval_change=lambda: calls.append("changed"),
    )

    assert settings.retrieval_k == 8
    assert settings.relevance_min_score == pytest.approx(0.05)
    assert calls == ["changed"]  # đổi tham số retrieval ⇒ invalidate cache
    assert runtime_settings.describe(settings)["overridden"] == ["relevance_min_score", "retrieval_k"]


def test_apply_updates_without_retrieval_change_does_not_invalidate():
    settings = _FakeSettings()
    calls: list[str] = []
    runtime_settings.apply_updates(
        settings, {"default_max_tokens": 3000}, on_retrieval_change=lambda: calls.append("changed"),
    )
    assert settings.default_max_tokens == 3000
    assert calls == []  # chỉ ảnh hưởng câu trả lời, không tới retrieval/cache


def test_apply_updates_rejects_unknown_and_out_of_range():
    settings = _FakeSettings()
    with pytest.raises(ValueError):
        runtime_settings.apply_updates(settings, {"chunk_size": 500})  # cần re-index ⇒ không cho
    with pytest.raises(ValueError):
        runtime_settings.apply_updates(settings, {"rerank_top_n": 99})  # > max 20
    with pytest.raises(ValueError):
        runtime_settings.apply_updates(settings, {"enable_rerank": "maybe"})


def test_coerce_types():
    assert runtime_settings.TUNABLES["retrieval_k"].coerce("8") == 8
    assert runtime_settings.TUNABLES["enable_rerank"].coerce("true") is True
    assert runtime_settings.TUNABLES["relevance_min_score"].coerce(0) == 0
    with pytest.raises(ValueError):
        runtime_settings.TUNABLES["retrieval_k"].coerce(7.5)  # int nhưng không nguyên


def test_reset_restores_env_defaults():
    settings = _FakeSettings()
    original = settings.retrieval_k
    runtime_settings.apply_updates(settings, {"retrieval_k": 10})
    runtime_settings.reset(settings)
    assert settings.retrieval_k == original
    assert runtime_settings.describe(settings)["overridden"] == []
