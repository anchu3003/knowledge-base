"""Unit test cho PIIRedactor (KB-1.1). Dữ liệu test là GIẢ, không dùng PII thật."""
from types import SimpleNamespace

from app.services.pii_service import PIIRedactor


def make_redactor(enabled: bool = True) -> PIIRedactor:
    settings = SimpleNamespace(enable_pii_redaction=enabled, pii_placeholder="[REDACTED:{type}]")
    return PIIRedactor(settings)


def test_redacts_email():
    out = make_redactor().redact("Contact me at john.doe@gmail.com please")
    assert "john.doe@gmail.com" not in out
    assert "[REDACTED:EMAIL]" in out


def test_redacts_phone_vn():
    out = make_redactor().redact("Call 0912345678 or +84912345678")
    assert "0912345678" not in out
    assert "912345678" not in out
    assert "[REDACTED:PHONE]" in out


def test_redacts_secrets():
    out = make_redactor().redact(
        "keys: gsk_abcdefghijklmnopqrstuvwxyz123456 and sk-abcdefghijklmnopqrstuvwxyz1234567890"
    )
    assert "gsk_abcdefghijklmnopqrstuvwxyz123456" not in out
    assert "sk-abcdefghijklmnopqrstuvwxyz1234567890" not in out
    assert "[REDACTED:SECRET]" in out


def test_redacts_password_value_but_keeps_key():
    out = make_redactor().redact("password=SuperSecret123")
    assert "SuperSecret123" not in out
    assert "password=" in out
    assert "[REDACTED:PASSWORD]" in out


def test_redacts_cccd_12_digits():
    out = make_redactor().redact("CCCD 012345678901 nhe")
    assert "012345678901" not in out


def test_keeps_technical_numbers():
    text = "port 8080, version 1.2.3000, token_count 1500"
    assert make_redactor().redact(text) == text


def test_allowlisted_examples_pass_through():
    text = "email user@example.com stays"
    assert make_redactor().redact(text) == text


def test_disabled_is_passthrough():
    text = "john.doe@gmail.com 0912345678"
    assert make_redactor(enabled=False).redact(text) == text


def test_stats_counts_multiple_emails():
    _, stats = make_redactor().redact_with_stats("a@b.com and c@d.com")
    assert stats.get("EMAIL") == 2
