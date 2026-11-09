"""Test `RerankCache` (KB-5.3 — trả TD-15).

Thuần logic: không load model, không Chroma. Dùng `clock` giả để test TTL mà không `sleep`.
"""

import pytest

from app.services.rerank_cache import RerankCache, make_cache_key, normalize_query


class FakeClock:
    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_get_returns_none_when_empty():
    cache = RerankCache()

    assert cache.get("k") is None
    assert cache.stats()["misses"] == 1


def test_set_then_get_round_trip():
    cache = RerankCache()
    cache.set("k", [0.9, 0.1])

    assert cache.get("k") == [0.9, 0.1]
    assert cache.stats()["hits"] == 1


def test_get_returns_copy_not_reference():
    """Trả list copy: nơi gọi sort/reverse không được làm hỏng entry trong cache."""
    cache = RerankCache()
    cache.set("k", [0.9, 0.1])

    got = cache.get("k")
    got.reverse()

    assert cache.get("k") == [0.9, 0.1]


def test_entry_expires_after_ttl():
    clock = FakeClock()
    cache = RerankCache(ttl_seconds=60, clock=clock)
    cache.set("k", [1.0])

    clock.advance(59)
    assert cache.get("k") == [1.0]

    clock.advance(2)  # 61s > TTL
    assert cache.get("k") is None
    assert cache.stats()["size"] == 0  # entry hết hạn bị xoá luôn


def test_ttl_zero_means_no_expiry():
    clock = FakeClock()
    cache = RerankCache(ttl_seconds=0, clock=clock)
    cache.set("k", [1.0])

    clock.advance(10_000)
    assert cache.get("k") == [1.0]


def test_lru_eviction_keeps_most_recent():
    cache = RerankCache(max_entries=2)
    cache.set("a", [1.0])
    cache.set("b", [2.0])
    cache.set("c", [3.0])  # vượt 2 entry ⇒ đuổi entry cũ nhất ("a")

    assert cache.get("a") is None
    assert cache.get("b") == [2.0]
    assert cache.get("c") == [3.0]
    assert cache.stats()["evictions"] == 1


def test_get_promotes_entry_so_it_is_not_evicted():
    cache = RerankCache(max_entries=2)
    cache.set("a", [1.0])
    cache.set("b", [2.0])
    cache.get("a")  # "a" thành mới dùng nhất

    cache.set("c", [3.0])

    assert cache.get("a") == [1.0]
    assert cache.get("b") is None


def test_clear_removes_all_entries():
    cache = RerankCache()
    cache.set("a", [1.0])
    cache.set("b", [2.0])

    cache.clear()

    assert cache.stats()["size"] == 0
    assert cache.get("a") is None


def test_stats_hit_rate():
    cache = RerankCache()
    cache.set("a", [1.0])
    cache.get("a")  # hit
    cache.get("b")  # miss

    stats = cache.stats()
    assert (stats["hits"], stats["misses"], stats["hit_rate"]) == (1, 1, 0.5)


def test_normalize_query_collapses_whitespace_and_case():
    assert normalize_query("  Kafka   LÀ gì?  ") == "kafka là gì?"


def test_cache_key_ignores_whitespace_and_case():
    a = make_cache_key(query="Kafka  là gì?", index_version=1, k=3, top_n=8)
    b = make_cache_key(query="kafka là gì?", index_version=1, k=3, top_n=8)

    assert a == b


@pytest.mark.parametrize(
    "override",
    [
        {"index_version": 2},
        {"k": 5},
        {"top_n": 12},
        {"config_fingerprint": "khac"},
    ],
)
def test_cache_key_changes_with_every_input(override):
    base = dict(query="kafka", index_version=1, k=3, top_n=8, config_fingerprint="fp")
    expected = make_cache_key(**base)
    changed = make_cache_key(**{**base, **override})

    assert changed != expected


def test_index_change_invalidates_cache_via_key():
    """Sync tài liệu ⇒ `index_version` tăng ⇒ khoá đổi ⇒ không dùng lại điểm cũ."""
    version_before = 3
    cache = RerankCache()
    old_key = make_cache_key(query="kafka", index_version=version_before, k=3, top_n=8)
    cache.set(old_key, [0.5])

    new_key = make_cache_key(query="kafka", index_version=version_before + 1, k=3, top_n=8)

    assert cache.get(new_key) is None
    assert cache.get(old_key) == [0.5]  # entry cũ còn nhưng không bao giờ được tra tới
