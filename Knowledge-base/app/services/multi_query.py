"""Multi-query retrieval cho câu hỏi nhiều ý (KB-5.4).

Vấn đề: câu hỏi kiểu *"B-Tree khác Hash index ở điểm nào và khi nào dùng cái nào?"* có **2 ý**; embed
cả câu thành 1 vector rồi lấy top-k thường chỉ phủ được nửa ý (nửa còn lại thua điểm).

Cách làm (Q&A KB-5.4: **không** dùng LangGraph, tự viết pipeline; **heuristic split**, 0 token LLM):
1. `split_query()` tách câu hỏi thành 2–3 phần theo dấu hiệu **nhiều ý** (liên từ "và", "so với",
   "khác … ở điểm nào", dấu `;`…), **không** đụng vào phần trong ngoặc kép/backtick (tên hàm, code).
2. Retrieve **từng phần** với cùng `k`.
3. `merge_hits()` gộp theo `chunk_id`, giữ **score cao nhất**, rồi sort giảm dần ⇒ tài liệu phủ nhiều ý
   cùng lọt vào top-k thay vì bị 1 ý chiếm hết.

Vì sao heuristic (không gọi LLM): mỗi LLM call thêm ~200–300 token ⇒ trần **TPM 8000** của Groq free tier
(TD-17) chạm sớm hơn; và split bằng quy tắc là **tất định** ⇒ eval so sánh trước/sau mới có nghĩa.
Split bằng LLM là fallback (`MULTI_QUERY_LLM_SPLIT_ENABLED`, mặc định tắt).

Toàn bộ hàm ở đây **thuần** (không I/O, không LLM) ⇒ test nhanh, không cần model.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Sequence

#: Tối đa số phần tách ra (nhiều hơn không có lợi: chỉ tổn thêm latency + loãng top-k).
DEFAULT_MAX_PARTS = 3
#: Phần quá ngắn ("và gì?") là rác ⇒ bỏ. Đếm theo từ.
MIN_PART_WORDS = 2

# Dấu hiệu "nhiều ý" trong câu hỏi tiếng Việt/Anh. Thứ tự quan trọng: cụm dài trước, từ đơn sau.
# Lưu ý: "khác … ở điểm nào" **không** phải dấu tách — đó là dạng câu hỏi; phải tách ở "so với"/"và".
# (Nếu tách ở "khác" thì phần sau chỉ còn "?" ⇒ bị loại ⇒ mất multi-query: đúng bug gặp khi test.)
_SPLIT_PATTERNS: Sequence[re.Pattern[str]] = (
    re.compile(r"\s+so\s+với\s+", re.IGNORECASE),
    re.compile(r"\s+(?:and|vs\.?|versus)\s+", re.IGNORECASE),
    re.compile(r"\s*;\s*"),
    re.compile(r"\s+đồng\s+thời\s+"),
    re.compile(r"\s+và\s+"),
    re.compile(r"\s*,\s*(?=(?:khi\s+nào|tại\s+sao|như\s+thế\s+nào|làm\s+sao|có\s+nên)\b)", re.IGNORECASE),
)

#: Phần nằm trong ngoặc kép/backtick là **dữ liệu** (tên hàm, câu code) — không tách.
_PROTECTED = re.compile(r"(`[^`]*`|\"[^\"]*\"|'[^']*')")
_PROTECTED_TOKEN = "\x00{}\x00"

#: Đuôi câu hỏi thừa khi đã tách ("… và tại sao?" ⇒ phần 2 chỉ còn "tại sao?").
_TRAILING_PUNCT = " \t\n?？.!,;:"


def _protect(text: str) -> tuple[str, List[str]]:
    saved: List[str] = []

    def _stash(match: re.Match[str]) -> str:
        saved.append(match.group(0))
        return _PROTECTED_TOKEN.format(len(saved) - 1)

    return _PROTECTED.sub(_stash, text), saved


def _restore(text: str, saved: List[str]) -> str:
    for index, original in enumerate(saved):
        text = text.replace(_PROTECTED_TOKEN.format(index), original)
    return text


def _split_outside_protected(text: str) -> List[str]:
    """Tách theo pattern nhưng **không** tách bên trong đoạn được bảo vệ."""
    parts = [text]
    for pattern in _SPLIT_PATTERNS:
        next_parts: List[str] = []
        for part in parts:
            next_parts.extend(pattern.split(part))
        parts = next_parts
    return parts


def _clean_part(part: str) -> str:
    cleaned = " ".join(part.split()).strip(_TRAILING_PUNCT)
    # Bỏ mảnh mở đầu kiểu "và", "so với", "nhưng"
    cleaned = re.sub(r"^(?:và|hoặc|nhưng|so với|and|or)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(_TRAILING_PUNCT)


def split_query(query: str, max_parts: int = DEFAULT_MAX_PARTS) -> List[str]:
    """Tách câu hỏi nhiều ý thành các sub-query.

    Trả `[query]` (1 phần) khi câu hỏi chỉ có **một** ý ⇒ nơi gọi giữ nguyên hành vi cũ.
    """
    if not query or not query.strip():
        return []

    protected, saved = _protect(query)
    raw_parts = _split_outside_protected(protected)

    cleaned: List[str] = []
    for raw in raw_parts:
        part = _clean_part(_restore(raw, saved))
        if len(part.split()) < MIN_PART_WORDS:
            continue
        if part.lower() in {existing.lower() for existing in cleaned}:
            continue
        cleaned.append(part)

    if len(cleaned) <= 1:
        return [query.strip()]

    # Giữ tối đa `max_parts` phần dài nhất? Không — giữ **thứ tự xuất hiện** (ý đầu thường là ý chính),
    # nhưng phần bị cắt bớt được gộp lại vào phần cuối để không mất nội dung.
    if len(cleaned) > max_parts:
        head = cleaned[: max_parts - 1]
        tail = cleaned[max_parts - 1:]
        return [*head, " ".join(tail)]
    return cleaned


def merge_hits(hit_lists: Iterable[Sequence[Dict[str, Any]]], dedup: bool = True) -> List[Dict[str, Any]]:
    """Gộp kết quả của nhiều sub-query: mỗi `chunk_id` giữ **score cao nhất**, sort giảm dần.

    `dedup=True`: giữ hit đầu tiên cho mỗi `chunk_id` (score đã là max) ⇒ không có chunk trùng.
    """
    best: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []

    for hits in hit_lists:
        for hit in hits:
            key = str(hit.get("chunk_id") or hit.get("content", "")[:64])
            current = best.get(key)
            if current is None:
                best[key] = dict(hit)
                order.append(key)
            elif float(hit.get("score", 0.0)) > float(current.get("score", 0.0)):
                best[key] = dict(hit)

    merged = [best[key] for key in order]
    merged.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
    if not dedup:
        return merged
    seen = set()
    unique: List[Dict[str, Any]] = []
    for hit in merged:
        key = str(hit.get("chunk_id") or hit.get("content", "")[:64])
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    return unique
