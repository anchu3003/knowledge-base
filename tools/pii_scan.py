#!/usr/bin/env python3
"""pii_scan.py — quét PII/secret trong file (lưới an toàn cuối trước khi commit).

Không thay thế secret scanner thật — chỉ cảnh báo các mẫu đặc trưng, ít false-positive.
Xem `.clinerules/30-pii-safety.md`.

Dùng:
    python tools/pii_scan.py <file1> [file2 ...]
    python tools/pii_scan.py .            # quét đệ quy thư mục (bỏ .git/.venv/node_modules)
    python tools/pii_scan.py --all        # quét cả workspace (từ thư mục hiện tại)

Exit code 1 nếu phát hiện, 0 nếu sạch.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# --- Mẫu secret (khớp cả trong file) ---
SECRET_PATTERNS = {
    "OpenAI key": re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    "Groq key": re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"),
    "GitHub PAT": re.compile(r"\b(ghp_|gho_|github_pat_)[A-Za-z0-9_]{20,}\b"),
    "AWS key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    "PEM key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}

# --- Mẫu PII (chỉ khớp khi không phải placeholder) ---
PII_PATTERNS = {
    "Email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "Phone VN": re.compile(r"(?<!\d)((?:\+84|0)\d{9,10})(?!\d)"),
    "CCCD/CMND": re.compile(r"(?<!\d)\d{9}(?:1|2)\d?(?!\d)"),  # heuristic 9-12 số
    "Password assign": re.compile(r"(?i)\b(password|pwd|passwd|matkhau)\b\s*[:=]\s*\S+"),
}

# Cho phép các giá trị ví dụ/placeholder (không coi là vi phạm)
ALLOW = re.compile(
    r"(?i)(example\.com|example\.org|REDACTED|placeholder|your_|xxx+|<.*?>|test@|user@|"
    r"mail\.com|domain|localhost|\.\.\.|\$\{|\$\(|@x\.com|\bstring\b|\bnumber\b|\bboolean\b|…)"
)

SKIP_DIRS = {".git", ".venv", "node_modules", ".next", "__pycache__", "dist", "build",
             ".mypy_cache", ".pytest_cache", "chroma_db", ".idea", "tests"}
SKIP_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".docx", ".ico", ".woff", ".woff2",
             ".lock", ".pyc", ".so", ".dll", ".exe"}


def scan_text(text: str) -> list[tuple[str, str, int]]:
    """Trả về list (loại, dòng khớp, số dòng)."""
    hits: list[tuple[str, str, int]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        # Bỏ qua dòng định nghĩa regex/pattern (chính scanner hay chứa marker) — tránh false positive.
        if "re.compile" in line or "pattern" in line.lower():
            continue
        for label, pat in {**SECRET_PATTERNS, **PII_PATTERNS}.items():
            for m in pat.finditer(line):
                val = m.group(0)
                if ALLOW.search(val):
                    continue
                hits.append((label, val, lineno))
    return hits


def iter_files(targets: list[str]) -> list[Path]:
    files: list[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_file():
            # Áp cùng bộ lọc cho file truyền trực tiếp (vd `git ls-files | xargs pii_scan.py`):
            # không quét `tests/` (dữ liệu giả theo quy ước) hay file nhị phân.
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            if p.suffix.lower() in SKIP_EXTS:
                continue
            files.append(p)
        elif p.is_dir():
            for f in p.rglob("*"):
                if not f.is_file():
                    continue
                if any(part in SKIP_DIRS for part in f.parts):
                    continue
                if f.suffix.lower() in SKIP_EXTS:
                    continue
                files.append(f)
    return files


def main(argv: list[str]) -> int:
    # Windows console mặc định cp1252 -> không in được tiếng Việt; ép UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    targets = argv[1:] or ["."]
    files = iter_files(targets)
    total = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hits = scan_text(text)
        if hits:
            total += len(hits)
            print(f"[!] {f}")
            for label, val, lineno in hits:
                shown = val if label not in ("Password assign",) else "[value hidden]"
                print(f"    L{lineno}: {label}: {shown}")
    if total:
        print(f"\n[X] {total} chỗ nghi vấn PII/secret. Che/xoá trước khi commit "
              f"(.clinerules/30-pii-safety.md).")
        return 1
    print(f"[OK] Không phát hiện PII/secret trong {len(files)} file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
