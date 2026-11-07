"""Unit test cho ingest redaction (KB-1.2). Dữ liệu test là GIẢ."""
from types import SimpleNamespace

from app.services.pii_service import PIIRedactor, redact_texts_for_ingest


def make_redactor(enabled: bool = True) -> PIIRedactor:
    settings = SimpleNamespace(enable_pii_redaction=enabled, pii_placeholder="[REDACTED:{type}]")
    return PIIRedactor(settings)


def test_ingest_masks_pii_and_flags_metadata():
    r = make_redactor()
    texts = ["contact john.doe@gmail.com for access", "plain technical text about caching"]
    metas = [{"source": "a.md"}, {"source": "b.md"}]

    out_texts, out_metas, count = redact_texts_for_ingest(r, texts, metas)

    assert "john.doe@gmail.com" not in out_texts[0]
    assert "[REDACTED:EMAIL]" in out_texts[0]
    assert out_metas[0].get("pii_redacted") is True
    # Chunk sạch giữ nguyên + không bị gắn cờ
    assert out_texts[1] == "plain technical text about caching"
    assert "pii_redacted" not in out_metas[1]
    assert count >= 1


def test_ingest_does_not_mutate_input_metadata():
    r = make_redactor()
    original_meta = {"source": "a.md"}
    texts = ["email john.doe@gmail.com"]
    metas = [original_meta]

    _, out_metas, _ = redact_texts_for_ingest(r, texts, metas)

    assert original_meta == {"source": "a.md"}          # dict gốc không bị đụng
    assert out_metas[0]["pii_redacted"] is True          # bản sao có cờ


def test_ingest_disabled_is_passthrough():
    r = make_redactor(enabled=False)
    texts = ["john.doe@gmail.com 0912345678"]
    metas = [{"source": "a.md"}]

    out_texts, out_metas, count = redact_texts_for_ingest(r, texts, metas)

    assert out_texts == texts
    assert out_metas == metas
    assert count == 0
