"""Test `app/services/index_sync.py` — diff folder ↔ index (KB-5.1)."""

from pathlib import Path

import pytest

from app.services.index_sync import (
    DiskFile,
    IndexedFile,
    compute_file_digest,
    diff_indexed,
    scan_folder,
)


def write(tmp_path: Path, name: str, content: str = "hello") -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def disk(path: Path) -> DiskFile:
    return DiskFile(path=str(path), size=path.stat().st_size, digest=compute_file_digest(path))


class TestComputeDigest:
    def test_same_content_same_digest(self, tmp_path):
        a = write(tmp_path, "a.md", "nội dung")
        b = write(tmp_path, "b.md", "nội dung")
        assert compute_file_digest(a) == compute_file_digest(b)

    def test_different_content_different_digest(self, tmp_path):
        a = write(tmp_path, "a.md", "một")
        digest_a = compute_file_digest(a)
        b = write(tmp_path, "b.md", "hai")
        assert digest_a != compute_file_digest(b)

    def test_digest_is_16_chars(self, tmp_path):
        assert len(compute_file_digest(write(tmp_path, "a.md"))) == 16


class TestScanFolder:
    def test_only_supported_extensions_counted(self, tmp_path):
        write(tmp_path, "note.md")
        write(tmp_path, "deep/nested.txt")
        write(tmp_path, "image.png")  # ext không hỗ trợ ⇒ bỏ qua im lặng

        valid, skipped = scan_folder(tmp_path, [".md", ".txt"], max_file_size_mb=10)

        assert {Path(f.path).name for f in valid} == {"note.md", "nested.txt"}
        assert skipped == []

    def test_file_larger_than_limit_is_skipped_with_reason(self, tmp_path):
        big = tmp_path / "big.md"
        big.write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB

        valid, skipped = scan_folder(tmp_path, [".md"], max_file_size_mb=1)

        assert valid == []
        assert len(skipped) == 1
        assert "too_large" in skipped[0]["reason"]

    def test_missing_folder_returns_empty(self, tmp_path):
        valid, skipped = scan_folder(tmp_path / "nope", [".md"], max_file_size_mb=10)
        assert valid == [] and skipped == []


class TestDiffIndexed:
    def test_new_file_is_added(self, tmp_path):
        f = write(tmp_path, "new.md")
        plan = diff_indexed([disk(f)], {})

        assert [Path(x.path).name for x in plan.added] == ["new.md"]
        assert plan.updated == [] and plan.removed == []

    def test_same_digest_is_unchanged(self, tmp_path):
        f = write(tmp_path, "same.md", "nội dung")
        d = disk(f)
        plan = diff_indexed([d], {d.path: IndexedFile(source=d.path, digest=d.digest, size=d.size)})

        assert plan.unchanged and plan.added == [] and plan.updated == []

    def test_changed_content_is_updated(self, tmp_path):
        f = write(tmp_path, "changed.md", "nội dung mới")
        old = IndexedFile(source=str(f), digest="deadbeefdeadbeef", size=999)
        plan = diff_indexed([disk(f)], {str(f): old})

        assert [Path(x.path).name for x in plan.updated] == ["changed.md"]

    def test_missing_on_disk_is_removed(self, tmp_path):
        gone = str(tmp_path / "gone.md")
        plan = diff_indexed([], {gone: IndexedFile(source=gone, digest="abc", size=10)})

        assert plan.removed == [gone]

    def test_legacy_metadata_without_hash_same_size_is_backfill_not_reindex(self, tmp_path):
        """File index từ bản trước KB-5.1 (không có file_hash) nhưng size khớp ⇒ chỉ backfill hash."""
        f = write(tmp_path, "legacy.md", "nội dung cũ")
        d = disk(f)
        plan = diff_indexed([d], {d.path: IndexedFile(source=d.path, digest=None, size=d.size)})

        assert plan.updated == [] and plan.to_index == []
        assert [Path(x.path).name for x in plan.backfill] == ["legacy.md"]

    def test_legacy_metadata_without_hash_different_size_is_updated(self, tmp_path):
        f = write(tmp_path, "legacy2.md", "nội dung mới dài hơn")
        d = disk(f)
        plan = diff_indexed([d], {d.path: IndexedFile(source=d.path, digest=None, size=1)})

        assert [Path(x.path).name for x in plan.updated] == ["legacy2.md"]

    def test_to_index_unions_added_and_updated(self, tmp_path):
        added = write(tmp_path, "a.md", "a")
        updated = write(tmp_path, "b.md", "b mới")
        plan = diff_indexed(
            [disk(added), disk(updated)],
            {str(updated): IndexedFile(source=str(updated), digest="oldoldoldoldold", size=1)},
        )

        assert {Path(x.path).name for x in plan.to_index} == {"a.md", "b.md"}


class TestEmptyFiles:
    def test_empty_file_is_skipped_not_added(self, tmp_path):
        """File 0 byte (placeholder) không được coi là "file mới" — nếu không sync lần nào cũng báo +N mà 0 chunk."""
        (tmp_path / "empty.md").write_text("")
        write(tmp_path, "real.md", "nội dung")

        valid, skipped = scan_folder(tmp_path, [".md"], max_file_size_mb=10)

        assert [Path(f.path).name for f in valid] == ["real.md"]
        assert len(skipped) == 1 and "empty_file" in skipped[0]["reason"]
        # Và vì bị skip nên không xuất hiện trong plan ⇒ không embed lại mỗi lần sync
        plan = diff_indexed(valid, {})
        assert [Path(x.path).name for x in plan.added] == ["real.md"]
