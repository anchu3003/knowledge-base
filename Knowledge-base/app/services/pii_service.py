"""PII / secret redaction trước khi gửi dữ liệu lên LLM.

Xem `.clinerules/30-pii-safety.md` và skill `kb-pii-redaction`.
Regex-first: nhanh, offline, đủ cho các PII/secret cấu trúc. PII phi cấu trúc (tên riêng,
địa chỉ tự do) chưa xử lý — tech debt TD-1.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import partial
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Rule:
    type: str
    pattern: re.Pattern
    # 0 = thay cả match; >0 = chỉ thay group đó (giữ phần còn lại)
    group: int = 0


# Thứ tự quan trọng: secret/JWT/PEM trước, rồi password, rồi PII cấu trúc.
_RULES: List[_Rule] = [
    _Rule("SECRET", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    _Rule("SECRET", re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b")),
    _Rule("SECRET", re.compile(r"\b(?:ghp_|gho_|github_pat_)[A-Za-z0-9_]{20,}\b")),
    _Rule("SECRET", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    _Rule("SECRET", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    _Rule("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    _Rule("PRIVATE_KEY",
          re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    # password = ..., pwd: ...  -> giữ tên key, che giá trị (group 3)
    _Rule("PASSWORD",
          re.compile(r"(?i)\b(password|passwd|pwd|mat\s?khau|secret)\b(\s*[:=]\s*)(\S+)"),
          group=3),
    _Rule("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    # SĐT VN: 0xxxxxxxxx hoặc +84xxxxxxxxx (cho phép khoảng trắng/dấu)
    _Rule("PHONE", re.compile(r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)")),
    # CCCD (12 số) hoặc CMND (9 số) — heuristic
    _Rule("ID", re.compile(r"(?<!\d)(?:\d{12}|\d{9})(?!\d)")),
]

# Giá trị ví dụ/placeholder — không coi là vi phạm
_ALLOW = re.compile(
    r"(?i)(example\.(com|org)|REDACTED|placeholder|your_|localhost|@test\b|"
    r"\bxxx+\b|change[_-]?me|dummy)"
)


def _sub_group(match: re.Match, placeholder: str, group: int) -> str:
    """Thay chỉ phần group trong match, giữ phần còn lại."""
    whole = match.group(0)
    start = match.start(group) - match.start(0)
    end = match.end(group) - match.start(0)
    return whole[:start] + placeholder + whole[end:]


class PIIRedactor:
    """Che PII/secret trong text theo cấu hình `Settings`."""

    def __init__(self, settings: Any):
        self.settings = settings
        self.enabled: bool = bool(getattr(settings, "enable_pii_redaction", True))
        self._placeholder_tmpl: str = getattr(settings, "pii_placeholder", "[REDACTED:{type}]")
        self._placeholder_re = re.compile(r"\[REDACTED[:\[\]]*[A-Z_]*\]", re.IGNORECASE)

    def _placeholder(self, type_: str) -> str:
        try:
            return self._placeholder_tmpl.format(type=type_)
        except (KeyError, IndexError, ValueError):
            return f"[REDACTED:{type_}]"

    def redact_with_stats(self, text: str) -> Tuple[str, Dict[str, int]]:
        """Trả về (text đã che, thống kê {loại: số lượng})."""
        if not self.enabled or not text:
            return text, {}

        counts: Dict[str, int] = {}
        out = text
        for rule in _RULES:
            placeholder = self._placeholder(rule.type)
            if rule.group == 0:
                def _repl(match: re.Match, ph: str = placeholder) -> str:
                    return match.group(0) if _ALLOW.search(match.group(0)) else ph
                out, n = rule.pattern.subn(_repl, out)
            else:
                repl = partial(_sub_group, placeholder=placeholder, group=rule.group)
                out, n = rule.pattern.subn(repl, out)
            if n:
                counts[rule.type] = counts.get(rule.type, 0) + n
        return out, counts

    def redact(self, text: str) -> str:
        """Trả về text đã che PII/secret."""
        redacted, _ = self.redact_with_stats(text)
        return redacted

    def stats_only(self, orig: str, redacted: str) -> Dict[str, int]:
        """Thống kê loại PII đã bị che khi so sánh 2 bản text (tiện cho log)."""
        if orig == redacted:
            return {}
        found = self._placeholder_re.findall(redacted)
        return {"redacted": len(found)} if found else {}


def redact_texts_for_ingest(
    redactor: PIIRedactor,
    texts: List[str],
    metadatas: List[Dict[str, Any]],
) -> Tuple[List[str], List[Dict[str, Any]], int]:
    """Che PII/secret trong list chunk text TRƯỚC khi index vào vector store (KB-1.2).

    Trả về (texts, metadatas, số giá trị bị che). Chunk nào bị che sẽ được gắn
    metadata `pii_redacted=True` để tiện kiểm tra. File gốc trên đĩa KHÔNG bị đụng.

    Là hàm thuần (không phụ thuộc ChromaDB/embeddings) nên unit-test được.
    """
    if not redactor.enabled:
        return texts, metadatas, 0

    new_texts = list(texts)
    new_metas = list(metadatas)
    total = 0
    for i, text in enumerate(new_texts):
        redacted, stats = redactor.redact_with_stats(text)
        if stats:
            new_texts[i] = redacted
            if i < len(new_metas):
                new_metas[i] = {**new_metas[i], "pii_redacted": True}
            total += sum(stats.values())
    return new_texts, new_metas, total
