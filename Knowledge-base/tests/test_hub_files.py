"""KB-9.7: nhận diện file 'hub' (mục lục / Q&A lớn) + hạ điểm sau rerank."""
from types import SimpleNamespace

import pytest

from app.services.hub_files import is_hub, is_hub_content, is_hub_name


# ------------------------------
# Nhận diện theo tên file
# ------------------------------
@pytest.mark.parametrize("source", [
    "Interview/Backend&Devops/Database Index.md",
    "Interview/AI/AI Index.md",
    "Interview/Backend&Devops/Microservices Q&A.md",
    "Interview/Cloud/AWS/Exam guide.md",
])
def test_hub_names_are_detected(source):
    assert is_hub_name(source) is True


@pytest.mark.parametrize("source", [
    "Interview/Backend&Devops/Design Patterns/Saga Pattern.md",
    "Interview/AI/Embeddings & Semantic Search.md",
    "Interview/Data Structure/Hash Tables.md",
    "Interview/Cloud/AWS/Best practices.md",
])
def test_real_content_files_are_not_hub(source):
    """Không được 'bắt oan' file nội dung thật (nếu bắt oan ⇒ hạ điểm cả nguồn đúng)."""
    assert is_hub_name(source) is False


# ------------------------------
# Nhận diện theo nội dung (khi tên file vô hại)
# ------------------------------
def test_link_dense_content_is_hub():
    """Chunk dạng mục lục: nhiều link `[[...]]` ngắn gọn ⇒ phải nhận ra."""
    text = "> Hub for patterns\n\n" + "\n".join(
        f"- [[{name}]] — mô tả ngắn" for name in ("Saga", "CQRS", "Outbox", "Saga Pattern", "Retry", "Idempotency")
    ) + "\n"
    assert is_hub_content(text) is True


def test_short_bullet_list_is_hub():
    text = "Index\n\n" + "\n".join(f"- {i}. topic ngắn gọn trong mục lục" for i in range(8)) + "\n"
    assert is_hub_content(text) is True



def test_prose_is_not_hub():
    text = ("Saga chia giao dịch phân tán thành các giao dịch cục bộ và bù trừ khi lỗi. "
           "Nhờ vậy hệ thống đạt eventual consistency mà không cần khoá toàn cục như 2PC. ") * 4
    assert is_hub_content(text) is False


def test_short_chunk_is_never_hub_by_content():
    assert is_hub_content("Saga dùng compensating transaction.") is False


def test_freeform_qa_files_are_not_hub():
    """`Junior Java Interview.md` / `Questions for interviewers.md` là **file nội dung** (Q&A có đáp án),
    không phải mục lục ⇒ **không** đánh dấu hub. Đây là bài học từ đo eval: đánh dấu chúng làm rơi hit@k."""
    assert is_hub_name("Interview/Interview Q&A/Junior Java Interview.md") is False
    assert is_hub_name("Interview/Interview Q&A/Questions for interviewers.md") is False


def test_only_basename_is_used_not_folder():
    """Cố ý **không** match theo đường dẫn: mọi tài liệu nằm trong `Interview/` ⇒ match path thì TẤT CẢ
    thành hub. File trong folder `cheat-sheets/` vẫn bắt được nếu tên file có 'cheat'."""
    assert is_hub_name("Interview/Backend&Devops/Tools/cheat-sheets/Java.md") is False
    assert is_hub_name("Interview/Backend&Devops/Tools/Java cheat sheet.md") is True


def test_is_hub_uses_name_or_content():
    assert is_hub("Interview/AI/AI Index.md", "x") is True
    assert is_hub("Interview/AI/Embeddings & Semantic Search.md", "- [[a]]\n- [[b]]\n- [[c]]\n" * 10) is True
    assert is_hub("Interview/AI/Embeddings & Semantic Search.md", "đoạn văn dài bình thường") is False
