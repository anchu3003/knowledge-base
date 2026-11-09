"""Test `multi_query` (KB-5.4): tách câu hỏi nhiều ý + gộp kết quả. Thuần, không I/O."""

from app.services.multi_query import merge_hits, split_query


def test_single_intent_query_is_not_split():
    """Câu hỏi 1 ý ⇒ trả nguyên câu (nơi gọi giữ hành vi cũ, không tốn thêm retrieval)."""
    query = "Saga pattern giải quyết vấn đề gì trong microservices?"

    assert split_query(query) == [query]


def test_splits_on_conjunction():
    parts = split_query("Kafka là gì và RabbitMQ khác nó ở điểm nào?")

    assert len(parts) == 2
    assert parts[0].startswith("Kafka là gì")
    assert "RabbitMQ" in parts[1]


def test_splits_on_so_voi():
    parts = split_query("So sánh optimistic locking so với pessimistic locking trong JPA")

    assert len(parts) == 2


def test_keeps_order_and_strips_trailing_punctuation():
    parts = split_query("B-Tree dùng khi nào? và Hash index dùng khi nào?")

    assert parts == ["B-Tree dùng khi nào", "Hash index dùng khi nào"]


def test_does_not_split_inside_quotes_or_code():
    query = 'Khác nhau giữa "a và b" trong `SELECT a and b` là gì?'
    parts = split_query(query)

    # Không tách dữ liệu trong ngoặc kép/backtick
    assert any('"a và b"' in part for part in parts)
    assert any("`SELECT a and b`" in part for part in parts)


def test_empty_query():
    assert split_query("") == []
    assert split_query("   ") == []


def test_drops_too_short_parts():
    """Mảnh 1 từ ("và gì?") là rác ⇒ bỏ, không tạo sub-query vô nghĩa."""
    parts = split_query("Kafka là message broker và gì?")

    assert len(parts) == 1


def test_dedupes_identical_parts():
    parts = split_query("Kafka là gì và Kafka là gì")

    assert len(parts) == 1


def test_limits_parts_and_merges_tail():
    query = "A là gì và B là gì và C là gì và D là gì"
    parts = split_query(query, max_parts=3)

    assert len(parts) == 3
    # Phần bị cắt được gộp vào phần cuối ⇒ không mất nội dung
    assert "C là gì" in parts[2] and "D là gì" in parts[2]


def test_english_conjunctions():
    parts = split_query("What is Kafka and how does it differ from RabbitMQ?")

    assert len(parts) == 2


# ----------------------------- merge_hits

def hit(chunk_id: str, score: float, content: str = "nội dung") -> dict:
    return {"chunk_id": chunk_id, "content": content, "metadata": {}, "score": score}


def test_merge_keeps_best_score_per_chunk():
    merged = merge_hits([
        [hit("c1", 0.4), hit("c2", 0.9)],
        [hit("c1", 0.7)],  # cùng chunk, điểm cao hơn ⇒ lấy 0.7
    ])

    by_id = {item["chunk_id"]: item["score"] for item in merged}
    assert by_id == {"c1": 0.7, "c2": 0.9}


def test_merge_sorts_by_score_desc():
    merged = merge_hits([[hit("a", 0.2)], [hit("b", 0.8)], [hit("c", 0.5)]])

    assert [item["chunk_id"] for item in merged] == ["b", "c", "a"]


def test_merge_dedupes_by_chunk_id():
    merged = merge_hits([[hit("c1", 0.5), hit("c1", 0.3)]])

    assert len(merged) == 1


def test_merge_handles_empty_lists():
    assert merge_hits([]) == []
    assert merge_hits([[], []]) == []


def test_merge_does_not_mutate_input():
    original = [hit("c1", 0.4)]
    snapshot = [dict(item) for item in original]

    merge_hits([original])

    assert original == snapshot
