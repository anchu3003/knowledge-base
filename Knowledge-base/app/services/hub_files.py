"""KB-9.7: nhận diện file 'hub' (index/Q&A/interview) — chúng chiếm top-k nhưng ít nội dung thật.

Vì sao cần: corpus có nhiều file dạng **mục lục / tổng hợp Q&A** (`*Index*.md`, `Microservices Q&A.md`,
`Junior/Middle Java Interview.md`, `Questions for interviewers.md`…). Chúng chứa rất nhiều từ khoá nên
điểm hybrid/rerank cao, nhưng khi vào prompt lại là **danh sách câu hỏi/link** ⇒ câu trả lời loãng và đẩy
file nội dung thật ra khỏi top-k (`precision@k` chỉ 0,333 trên bộ vàng v4).

Cách xử lý: **hạ điểm** (không xoá) chunk thuộc file hub ngay sau rerank. Hạ điểm thay vì loại hẳn để nếu
câu hỏi *đúng là* hỏi về mục lục thì chunk vẫn còn; và hệ số chỉnh được lúc chạy (`HUB_FILE_PENALTY`).

Bộ dò dùng **2 tín hiệu**, đều rẻ và không cần re-index:

1. **Tên file** — mẫu mục lục/Q&A/bộ câu hỏi.
2. **Nội dung** — tỉ lệ wiki-link `[[...]]` và độ dài dòng trung bình (mục lục = nhiều dòng ngắn/link).
"""

from __future__ import annotations

import re
from typing import Iterable

#: Mẫu tên file hub (so khớp trên basename, lowercase).
HUB_NAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bindex\b"),
    re.compile(r"\bq\s*&\s*a\b"),
    re.compile(r"\bexam guide\b"),
    re.compile(r"\bcheat[- ]?sheets?\b"),
    re.compile(r"\bhub\b"),
    re.compile(r"\bdairy\b"),
)

#: Ngưỡng nội dung: ≥ 4 link `[[…]]` trên 1.000 ký tự ⇒ coi là mục lục.
_LINK_DENSITY_PER_1K = 4.0
#: Chỉ hạ điểm hub khi đã có chunk **không phải hub** đạt ít nhất tỉ lệ này so với điểm hub.
#: Đo trên bộ vàng v4: hạ vô điều kiện làm `hit@k` 0,964 → 0,821 (nhiều đáp án chính là file index).
HUB_PENALTY_MIN_RATIO = 0.5

#: Dòng trung bình < ngưỡng này (ký tự) + nhiều dòng ⇒ dạng danh sách.
_SHORT_LINE_CHARS = 45.0
_MIN_LINES = 6


def is_hub_name(source: str) -> bool:
    """Tên file có phải dạng mục lục/Q&A không."""
    name = (source or "").replace("\\", "/").rsplit("/", 1)[-1].lower()
    return any(pattern.search(name) for pattern in HUB_NAME_PATTERNS)


def is_hub_content(text: str) -> bool:
    """Nội dung có phải dạng mục lục (nhiều link / nhiều dòng ngắn) không."""
    body = (text or "").strip()
    # Chunk thật ~1.000 ký tự; ngưỡng thấp để bắt được cả mục lục ngắn trong test.
    if len(body) < 100:
        return False
    links = body.count("[[")
    if links >= max(3, int(len(body) / 1000 * _LINK_DENSITY_PER_1K)):
        return True
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if len(lines) < _MIN_LINES:
        return False
    average = sum(len(line) for line in lines) / len(lines)
    # Danh sách gạch đầu dòng ngắn (mục lục) — không phải đoạn văn
    bullets = sum(1 for line in lines if line.startswith(("-", "*", "|", "#")))
    return average < _SHORT_LINE_CHARS and bullets >= len(lines) * 0.6


def is_hub(source: str, text: str = "") -> bool:
    """`True` nếu chunk thuộc file hub (theo tên **hoặc** nội dung)."""
    return is_hub_name(source) or is_hub_content(text)


def hub_sources(hits: Iterable[dict]) -> list[str]:
    """Danh sách file hub trong một tập hits (dùng cho log/eval)."""
    found: list[str] = []
    for hit in hits:
        source = ((hit.get("metadata") or {}).get("source") or "")
        if source not in found and is_hub_name(source):
            found.append(source)
    return found
