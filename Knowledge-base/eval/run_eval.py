"""RAG eval harness — KB-2.1.

Đo chất lượng retrieval + grounding của pipeline hiện tại để làm **baseline** cho Phase 2.
Không sửa code app; chỉ đọc settings hiện tại rồi đo.

Cách chạy (từ thư mục `Knowledge-base/`):

    .venv/bin/python eval/run_eval.py --build-index          # (re)index Interview/ (tuỳ chọn)
    .venv/bin/python eval/run_eval.py --mode retrieval        # KHÔNG tốn quota LLM
    .venv/bin/python eval/run_eval.py --mode full --tag baseline   # gọi Groq (/chat)

Kết quả: bảng markdown in ra stdout + snapshot JSON ở `eval/runs/`.

Metrics:
    hit@k                    tỉ lệ câu có >= 1 file kỳ vọng nằm trong top-k
    MRR                      mean reciprocal rank của file kỳ vọng đầu tiên
    dup_ratio                tỉ lệ cặp chunk trong top-k gần trùng (Jaccard shingle 3-gram >= 0.8)
    distinct_file_ratio      tỉ lệ file khác nhau trong top-k (1.0 = không lặp; 0.2 = 5 hit cùng 1 file)
    latency_p50              trung vị thời gian 1 query (giây)
    citation_presence (full) tỉ lệ câu trả lời có nhãn [S1], [S2], ...
    answer_keyword_hit (full) tỉ lệ câu trả lời chứa keyword kỳ vọng
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent
QA_SET_PATH = EVAL_DIR / "qa_set.json"
RUNS_DIR = EVAL_DIR / "runs"

DUP_JACCARD_THRESHOLD = 0.8
CITATION_RE = re.compile(r"\[S\d+\]")


# -----------------------------
# Pure helpers (dễ test, không cần model)
# -----------------------------
def normalize_path(value: str) -> str:
    """Chuẩn hoá path để so sánh: bỏ backslash, gộp slash thừa."""
    return value.replace("\\", "/").replace("//", "/").strip()


def match_expected_files(source: str, expected_files: List[str]) -> bool:
    """True nếu `source` (metadata của chunk) khớp 1 trong các file kỳ vọng."""
    src = normalize_path(source)
    return any(normalize_path(exp) in src for exp in expected_files)


def shingles(text: str, size: int = 3) -> set:
    """Tập shingle word-level (đã normalize lowercase + gộp whitespace)."""
    tokens = text.lower().split()
    if len(tokens) < size:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i:i + size]) for i in range(len(tokens) - size + 1)}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def duplicate_ratio(hits: List[Dict[str, Any]], threshold: float = DUP_JACCARD_THRESHOLD) -> float:
    """Tỉ lệ cặp chunk trong top-k bị coi là gần trùng (đo triệu chứng '5 tài liệu giống nhau')."""
    if len(hits) < 2:
        return 0.0
    shingle_sets = [shingles(hit.get("content", "")) for hit in hits]
    dup_pairs = 0
    total_pairs = 0
    for i in range(len(shingle_sets)):
        for j in range(i + 1, len(shingle_sets)):
            total_pairs += 1
            if jaccard(shingle_sets[i], shingle_sets[j]) >= threshold:
                dup_pairs += 1
    return dup_pairs / total_pairs if total_pairs else 0.0


def hit_and_rank(hits: List[Dict[str, Any]], expected_files: List[str]) -> Tuple[bool, Optional[int]]:
    """Trả (có hit không, rank 1-based của hit đầu tiên)."""
    for idx, hit in enumerate(hits, start=1):
        source = (hit.get("metadata") or {}).get("source", "")
        if match_expected_files(source, expected_files):
            return True, idx
    return False, None


def distinct_file_ratio(hits: List[Dict[str, Any]]) -> float:
    """Tỉ lệ file khác nhau trong top-k: 1.0 = không lặp file nào, 0.2 = 5 hit cùng 1 file.

    Đây là metric bắt đúng triệu chứng "trả về 5 tài liệu giống nhau": manifest rõ nhất là
    nhiều chunk của **cùng một file** chiếm hết slot, kể cả khi text không trùng >80% (chunk overlap 20%).
    """
    if not hits:
        return 0.0
    files = [(hit.get("metadata") or {}).get("source", "") for hit in hits]
    return len(set(files)) / len(files)


def precision_at_k(hits: List[Dict[str, Any]], expected_files: List[str]) -> float:
    """Tỉ lệ hit trong top-k trỏ đúng file kỳ vọng (0..1). Đo trực tiếp "precision" của ngữ cảnh.

    Precision cao ⇒ ít nguồn nhiễu được đưa vào prompt (quan trọng khi ưu tiên precision).
    """
    if not hits:
        return 0.0
    relevant = sum(
        1 for hit in hits
        if match_expected_files((hit.get("metadata") or {}).get("source", ""), expected_files)
    )
    return relevant / len(hits)


def keyword_hit(answer: str, keywords: List[str]) -> bool:
    """True nếu câu trả lời chứa >= 1 keyword kỳ vọng (case-insensitive)."""
    if not keywords:
        return False
    lowered = answer.lower()
    return any(kw.lower() in lowered for kw in keywords)


def has_inline_citation(answer: str) -> bool:
    """True nếu nhãn `[S#]` nằm trong **thân** câu trả lời (không chỉ ở dòng `Nguồn:` cuối).

    Yêu cầu của KB-2.3 Q1 là **inline** — nhãn ngay sau ý được trích. Model hay "đối phó" bằng
    cách dồn hết nhãn xuống dòng cuối, nên phải đo riêng để không tự lừa mình.
    """
    body_lines = [
        line for line in (answer or "").splitlines()
        if not line.strip().lower().startswith("nguồn")
    ]
    return bool(CITATION_RE.search("\n".join(body_lines)))


# -----------------------------
# Service wiring
# -----------------------------
def prepare_env(args: argparse.Namespace) -> None:
    """Set env override TRƯỚC khi `Settings` được tạo, và chdir về Knowledge-base/."""
    os.chdir(REPO_ROOT)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if args.rerank == "on":
        os.environ["ENABLE_RERANK"] = "true"
    elif args.rerank == "off":
        os.environ["ENABLE_RERANK"] = "false"
    if args.k:
        os.environ["RETRIEVAL_K"] = str(args.k)


def load_qa_set(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    data = json.loads(QA_SET_PATH.read_text(encoding="utf-8"))
    items = data["items"]
    return items[:limit] if limit else items


def build_services():
    """Import app muộn để env override ở `prepare_env` có hiệu lực."""
    from app.core.config import get_settings
    from app.services.document_service import DocumentService

    settings = get_settings()
    return settings, DocumentService(settings)


# -----------------------------
# Runners
# -----------------------------
async def run_retrieval(settings, service, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in items:
        t0 = time.perf_counter()
        hits = await service.search_similar_documents(query=item["question"], k=settings.retrieval_k)
        latency = time.perf_counter() - t0
        hit, rank = hit_and_rank(hits, item["expected_files"])
        row = {
            "id": item["id"],
            "question": item["question"],
            "hit": hit,
            "rank": rank,
            "dup_ratio": round(duplicate_ratio(hits), 3),
            "precision_at_k": round(precision_at_k(hits, item["expected_files"]), 3),
            "distinct_file_ratio": round(distinct_file_ratio(hits), 3),
            "latency": round(latency, 3),
            "top_files": [normalize_path((h.get("metadata") or {}).get("source", "")) for h in hits],
            "scores": [round(float(h.get("score", 0.0)), 4) for h in hits],
        }
        rows.append(row)
        print(f"[{item['id']}] hit={hit} rank={rank} dup={row['dup_ratio']:<5} {latency:.2f}s")
    return rows


async def run_full(settings, service, items: List[Dict[str, Any]], pause_seconds: float = 0.0) -> List[Dict[str, Any]]:
    from app.services.chat_service import ChatService

    chat = ChatService(settings, service)
    rows: List[Dict[str, Any]] = []
    for position, item in enumerate(items):
        if pause_seconds and position:
            # Groq free tier giới hạn TPM (8000) ⇒ nghỉ giữa các câu để không bị 429 hàng loạt
            await asyncio.sleep(pause_seconds)
        t0 = time.perf_counter()
        try:
            result = await chat.chat(message=item["question"])
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            meta = result.get("metadata", {})
        except Exception as exc:  # noqa: BLE001 — eval phải chạy tiếp các câu sau
            rows.append({"id": item["id"], "error": f"{type(exc).__name__}: {exc}"})
            print(f"[{item['id']}] ERROR {type(exc).__name__}: {exc}")
            continue

        latency = time.perf_counter() - t0
        cited = bool(CITATION_RE.search(answer))
        inline_cited = has_inline_citation(answer)
        kw_hit = keyword_hit(answer, item.get("expected_keywords", []))
        rows.append({
            "id": item["id"],
            "citation_present": cited,
            "inline_citation_present": inline_cited,
            "answer_keyword_hit": kw_hit,
            "sources": len(sources),
            "answer_chars": len(answer),
            "latency": round(latency, 3),
            "used_query": meta.get("used_query"),
            "query_rewrite_attempts": meta.get("query_rewrite_attempts"),
            "pii_redacted_count": meta.get("pii_redacted_count"),
            "error": None,
        })
        print(f"[{item['id']}] cite={cited} kw={kw_hit} sources={len(sources)} {latency:.2f}s")
    return rows


# -----------------------------
# Reporting
# -----------------------------
def summarize_retrieval(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok = [r for r in rows if "error" not in r]
    ranks = [1 / r["rank"] for r in ok if r["rank"]]
    return {
        "questions": len(rows),
        "hit_at_k": round(sum(1 for r in ok if r["hit"]) / len(ok), 3) if ok else 0.0,
        "mrr": round(statistics.mean(ranks), 3) if ranks else 0.0,
        "dup_ratio": round(statistics.mean([r["dup_ratio"] for r in ok]), 3) if ok else 0.0,
        "precision_at_k": round(statistics.mean([r["precision_at_k"] for r in ok]), 3) if ok else 0.0,
        "distinct_file_ratio": round(statistics.mean([r["distinct_file_ratio"] for r in ok]), 3) if ok else 0.0,
        "latency_p50": round(statistics.median([r["latency"] for r in ok]), 3) if ok else 0.0,
    }


def summarize_full(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok = [r for r in rows if not r.get("error")]
    return {
        "questions": len(rows),
        "errors": len(rows) - len(ok),
        "citation_presence": round(sum(1 for r in ok if r["citation_present"]) / len(ok), 3) if ok else 0.0,
        "inline_citation_presence": round(sum(1 for r in ok if r["inline_citation_present"]) / len(ok), 3) if ok else 0.0,
        "answer_keyword_hit": round(sum(1 for r in ok if r["answer_keyword_hit"]) / len(ok), 3) if ok else 0.0,
        "latency_p50": round(statistics.median([r["latency"] for r in ok]), 3) if ok else 0.0,
    }


def print_summary(summary: Dict[str, Any], meta: Dict[str, Any]) -> None:
    print("\n## Kết quả eval\n")
    print("| Metric | Giá trị |")
    print("|---|---|")
    for key, value in summary.items():
        print(f"| `{key}` | {value} |")
    print("\n| Cấu hình | Giá trị |")
    print("|---|---|")
    for key, value in meta.items():
        print(f"| `{key}` | {value} |")


def dump_run(mode: str, tag: str, summary: Dict[str, Any], meta: Dict[str, Any],
             rows: List[Dict[str, Any]]) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    path = RUNS_DIR / f"{stamp}-{tag}-{mode}.json"
    payload = {"mode": mode, "tag": tag, "timestamp": stamp, "summary": summary, "config": meta, "rows": rows}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ snapshot: {path.relative_to(REPO_ROOT)}")
    return path

# -----------------------------
# CLI
# -----------------------------
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG eval harness (KB-2.1)")
    parser.add_argument("--mode", choices=["retrieval", "full"], default="retrieval",
                        help="retrieval = chỉ đo retrieval (không gọi LLM); full = gọi /chat qua Groq")
    parser.add_argument("--tag", default="run", help="nhãn cho snapshot JSON (vd baseline)")
    parser.add_argument("--limit", type=int, default=None, help="chỉ chạy N câu đầu (để thử)")
    parser.add_argument("--k", type=int, default=None, help="override RETRIEVAL_K")
    parser.add_argument("--rerank", choices=["env", "on", "off"], default="env",
                        help="override ENABLE_RERANK (env = giữ nguyên theo .env)")
    parser.add_argument("--build-index", action="store_true",
                        help="clear collection + index lại DOCUMENTS_FOLDER trước khi đo")
    parser.add_argument("--sleep", type=float, default=0.0,
                        help="nghỉ N giây giữa các câu ở --mode full (tránh 429 TPM của free tier)")
    return parser.parse_args(argv)


async def main_async(args: argparse.Namespace) -> int:
    prepare_env(args)
    settings, service = build_services()

    if args.build_index:
        print(f"→ Re-index '{settings.documents_folder}' (xoá collection '{settings.collection_name}')...")
        t0 = time.perf_counter()
        await service.clear_database()
        result = await service.auto_load_documents()
        elapsed = time.perf_counter() - t0
        print(f"→ Indexed {result['processed_files']} files, {result['total_chunks']} chunks "
              f"trong {elapsed:.1f}s; collection.count()={service.collection.count()}")
        if result.get("details"):
            print(f"→ Lỗi khi load: {result['details']}")

    items = load_qa_set(args.limit)
    meta = {
        "embedding_model": settings.embedding_model,
        "collection": settings.collection_name,
        "collection_count": service.collection.count(),
        "retrieval_k": settings.retrieval_k,
        "enable_hybrid": settings.enable_hybrid,
        "hybrid_alpha": settings.hybrid_alpha,
        "enable_rerank": settings.enable_rerank,
        "rerank_model": settings.rerank_model if settings.enable_rerank else "(off)",
        "similarity_threshold": settings.similarity_threshold,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "questions": len(items),
    }

    print(f"→ Mode={args.mode} · {len(items)} câu · k={settings.retrieval_k} · "
          f"rerank={settings.enable_rerank} · index={meta['collection_count']} chunks\n")

    if args.mode == "retrieval":
        rows = await run_retrieval(settings, service, items)
        summary = summarize_retrieval(rows)
    else:
        rows = await run_full(settings, service, items, pause_seconds=args.sleep)
        summary = summarize_full(rows)

    print_summary(summary, meta)
    dump_run(args.mode, args.tag, summary, meta, rows)
    await service.cleanup()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args(argv)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
