"""Diff folder tài liệu với index để **chỉ index phần thay đổi** (KB-5.1).

Tách thành module thuần (không Chroma, không async) để test bằng pytest mà không cần model/embedding.

Vì sao cần: `refresh` = clear + index lại **toàn bộ** folder. Với kho 601 chunk thì mất ~22 phút (TD-14) và trong
lúc chạy index rỗng nên chat không có nguồn. Thực tế mỗi lần chỉ **1–2 file** thay đổi.

Quy ước:
- `digest` = `sha256(nội dung)[:16]` — đổi tên file **không** đổi digest, nhưng `source` (path) đổi ⇒ vẫn là removed + added.
- File đã index từ bản **trước KB-5.1** không có `file_hash` trong metadata ⇒ xử lý ở `diff_indexed`:
  cùng `file_size` ⇒ coi là *unchanged* + backfill hash (không embed lại); khác size ⇒ *updated*.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

_HASH_READ_SIZE = 1024 * 1024  # 1MB mỗi lần đọc


@dataclass(frozen=True)
class DiskFile:
    """Một file hợp lệ trên đĩa."""

    path: str
    size: int
    digest: str


@dataclass(frozen=True)
class IndexedFile:
    """Thông tin tối thiểu về một file đã có trong vector store."""

    source: str
    digest: Optional[str] = None
    size: Optional[int] = None


@dataclass
class SyncPlan:
    """Kết quả diff — service chỉ cần thi hành plan này."""

    added: List[DiskFile] = field(default_factory=list)
    updated: List[DiskFile] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    unchanged: List[DiskFile] = field(default_factory=list)
    skipped: List[Dict[str, str]] = field(default_factory=list)
    # File *unchanged* nhưng metadata cũ thiếu `file_hash` ⇒ chỉ cần update metadata (không embed lại)
    backfill: List[DiskFile] = field(default_factory=list)

    @property
    def to_index(self) -> List[DiskFile]:
        """File cần embed lại (thêm mới + đổi nội dung)."""
        return [*self.added, *self.updated]


def compute_file_digest(path: Path) -> str:
    """`sha256` 16 ký tự đầu của nội dung file (đọc theo block để không nạp cả file vào RAM)."""
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(_HASH_READ_SIZE)
            if not block:
                break
            sha.update(block)
    return sha.hexdigest()[:16]


def scan_folder(
    folder: Path,
    supported_exts: Sequence[str],
    max_file_size_mb: int,
) -> Tuple[List[DiskFile], List[Dict[str, str]]]:
    """Quét folder ⇒ (file hợp lệ có digest, danh sách file bị bỏ qua kèm lý do).

    Bỏ qua (không làm fail cả lần sync):
    - sai extension (không nằm trong `supported_exts`) — im lặng
    - **file rỗng 0 byte** — placeholder; nếu không loại thì lần sync nào cũng báo "file mới" mà 0 chunk
    - lớn hơn `max_file_size_mb` (mặc định 10MB — giữ nguyên theo quyết định user)
    - không đọc được (permission/IO) — ghi lý do để user biết
    """
    exts = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in supported_exts}
    max_bytes = max(1, int(max_file_size_mb)) * 1024 * 1024

    valid: List[DiskFile] = []
    skipped: List[Dict[str, str]] = []

    if not folder.exists():
        return valid, skipped

    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in exts:
            continue  # im lặng: file lạ không phải lỗi của user

        try:
            size = path.stat().st_size
        except OSError as exc:  # pragma: no cover - hiếm
            skipped.append({"path": str(path), "reason": f"stat_failed: {exc}"})
            continue

        if size == 0:
            skipped.append({"path": str(path), "reason": "empty_file: 0 bytes"})
            continue

        if size > max_bytes:
            skipped.append(
                {"path": str(path), "reason": f"too_large: {size / 1024 / 1024:.1f}MB > {max_file_size_mb}MB"}
            )
            continue

        try:
            digest = compute_file_digest(path)
        except OSError as exc:
            skipped.append({"path": str(path), "reason": f"read_failed: {exc}"})
            continue

        valid.append(DiskFile(path=str(path), size=size, digest=digest))

    return valid, skipped


def diff_indexed(disk_files: Iterable[DiskFile], indexed_files: Dict[str, IndexedFile]) -> SyncPlan:
    """So file trên đĩa với file đã index ⇒ plan added/updated/removed/unchanged/backfill."""
    plan = SyncPlan()
    seen: set[str] = set()

    for disk in disk_files:
        seen.add(disk.path)
        current = indexed_files.get(disk.path)

        if current is None:
            plan.added.append(disk)
            continue

        if current.digest:
            if current.digest == disk.digest:
                plan.unchanged.append(disk)
            else:
                plan.updated.append(disk)
            continue

        # Metadata cũ (trước KB-5.1) chưa có `file_hash`
        if current.size is not None and current.size == disk.size:
            plan.unchanged.append(disk)
            plan.backfill.append(disk)
        else:
            plan.updated.append(disk)

    for source in sorted(indexed_files.keys() - seen):
        plan.removed.append(source)

    return plan
