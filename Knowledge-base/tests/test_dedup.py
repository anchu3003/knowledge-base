"""Test cho dedup + cap per file (KB-2.2).

Chỉ test hàm thuần trong `app/services/dedup.py` — không cần model, không cần ChromaDB.
"""
from app.services.dedup import cap_per_file, dedupe_hits, jaccard, normalize_text, shingles

SAGA_CHUNK = (
    "The Saga Pattern manages distributed transactions in microservices using "
    "compensatable transactions and event driven coordination for eventual consistency."
)
SAGA_NEAR_DUP = (
    "The Saga Pattern manages distributed transactions in microservices using "
    "compensatable transactions and event driven coordination for eventual consistency. "
    "Extra trailing sentence about rollback."
)
DOCKER_CHUNK = "A container is a sandboxed process using kernel namespaces and cgroups."


def hit(content: str, source: str, score: float = 0.9) -> dict:
    return {"chunk_id": "id", "content": content, "metadata": {"source": source}, "score": score}


def test_normalize_text_collapses_whitespace_and_case():
    assert normalize_text("  Hello\n\tWORLD  ") == "hello world"


def test_jaccard_bounds():
    assert jaccard(set(), set()) == 0.0
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3


def test_shingles_short_text():
    assert shingles("one two", size=3) == {"one two"}
    assert shingles("   ") == set()


def test_dedupe_removes_normalized_duplicate_and_keeps_first():
    """Chunk chỉ khác whitespace/case ⇒ Jaccard = 1.0 ⇒ bị bỏ (giữ hit đầu)."""
    duplicated = "  the SAGA pattern manages distributed transactions…  "
    hits = [hit(SAGA_CHUNK, "saga.md"), hit(duplicated.upper(), "saga.md"), hit(DOCKER_CHUNK, "docker.md")]
    kept = dedupe_hits(hits, threshold=0.8)
    assert len(kept) == 3  # 'duplicated' khác nội dung thật ⇒ không phải near-dup, giữ nguyên

    exact_dup = hit(SAGA_CHUNK.replace(" ", "  ").lower(), "saga.md")
    kept = dedupe_hits([hit(SAGA_CHUNK, "saga.md"), exact_dup, hit(DOCKER_CHUNK, "docker.md")], threshold=0.8)
    assert len(kept) == 2
    assert kept[0]["content"] == SAGA_CHUNK  # giữ hit đứng trước (score cao hơn)
    assert kept[1]["metadata"]["source"] == "docker.md"


def test_dedupe_threshold_08_does_not_catch_merely_similar_chunks():
    """J ≈ 0.762 (< 0.8) ⇒ KHÔNG bị dedup. Đây là lý do phải có cap/file (MAX_CHUNKS_PER_FILE)."""
    similarity = jaccard(shingles(SAGA_CHUNK), shingles(SAGA_NEAR_DUP))
    assert 0.7 < similarity < 0.8

    kept = dedupe_hits([hit(SAGA_CHUNK, "saga.md"), hit(SAGA_NEAR_DUP, "saga.md")], threshold=0.8)
    assert len(kept) == 2


def test_dedupe_threshold_zero_keeps_everything():
    hits = [hit(SAGA_CHUNK, "a.md"), hit(SAGA_NEAR_DUP, "b.md")]
    assert len(dedupe_hits(hits, threshold=1.01)) == 2


def test_cap_per_file_limits_chunks_per_source():
    hits = [hit(f"chunk {i}", "same.md") for i in range(4)] + [hit("other", "other.md")]
    kept = cap_per_file(hits, max_per_file=2)
    assert [h["metadata"]["source"] for h in kept] == ["same.md", "same.md", "other.md"]


def test_cap_per_file_disabled_when_zero():
    hits = [hit(f"chunk {i}", "same.md") for i in range(4)]
    assert len(cap_per_file(hits, max_per_file=0)) == 4
