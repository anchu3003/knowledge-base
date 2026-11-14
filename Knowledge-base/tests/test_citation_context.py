"""Test citation contract (KB-2.3): `build_context`, `_format_sources`, prompt rules.

Không cần LLM/Chroma — chỉ kiểm shape + nội dung prompt.
"""
from pathlib import Path
from types import SimpleNamespace

from app.services.chat_service import ChatService

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "system_prompt.txt"


def make_service(system_prompt_path=None, context_max_chars: int = 6000) -> ChatService:
    service = object.__new__(ChatService)  # bỏ qua __init__ (không tạo LLM)
    service.settings = SimpleNamespace(
        system_prompt_path=system_prompt_path,
        context_max_chars=context_max_chars,
    )
    return service


def make_doc(content: str, name: str = "note.md", heading: str = "",
             chunk_id: str = "chunk1", score: float = 0.9) -> dict:
    return {
        "chunk_id": chunk_id,
        "content": content,
        "metadata": {
            "source": f"Interview/{name}",
            "file_name": name,
            "file_type": ".md",
            "heading_path": heading,
        },
        "score": score,
    }


# -----------------------------
# build_context
# -----------------------------
def test_build_context_labels_and_keeps_full_chunk():
    service = make_service()
    content = "x" * 1000  # chunk_size=1000; bản cũ cắt còn 500 ký tự

    context = service.build_context([make_doc(content)])

    assert context.startswith("[S1] note.md")
    assert content in context  # KHÔNG bị cắt 500 ký tự


def test_build_context_numbers_follow_rank_order_and_include_heading():
    service = make_service()

    context = service.build_context([
        make_doc("alpha", "a.md"),
        make_doc("beta", "b.md", heading="Java > Core"),
    ])

    assert "[S1] a.md" in context
    assert "[S2] b.md — Java > Core" in context


def test_build_context_respects_budget_and_drops_low_rank_sources():
    service = make_service(context_max_chars=40)

    context = service.build_context([
        make_doc("a" * 40, "a.md"),
        make_doc("b" * 40, "b.md"),
    ])

    assert "[S1] a.md" in context
    assert "b.md" not in context  # hết budget ⇒ bỏ nguồn xếp sau


def test_build_context_truncates_last_source_to_fit_budget():
    service = make_service(context_max_chars=60)

    context = service.build_context([
        make_doc("a" * 40, "a.md"),
        make_doc("b" * 40, "b.md"),
    ])

    assert "[S2] b.md" in context
    assert "b" * 20 in context and "b" * 21 not in context  # chỉ còn 20 ký tự budget


def test_build_context_empty():
    assert make_service().build_context([]) == "No relevant documents found."


# -----------------------------
# _format_sources
# -----------------------------
def test_format_sources_maps_citation_id_and_keeps_legacy_fields():
    sources = ChatService._format_sources([
        make_doc("nội dung dài " * 50, "a.md", chunk_id="c1"),
        make_doc("beta", "b.md", chunk_id="c2"),
    ])

    assert [s["citation_id"] for s in sources] == ["S1", "S2"]
    assert [s["chunk_id"] for s in sources] == ["c1", "c2"]
    assert sources[0]["snippet"].startswith("nội dung dài")
    for legacy_field in ("file_path", "file_name", "file_type", "relevance_score", "content_preview"):
        assert legacy_field in sources[0]


# -----------------------------
# Prompt: file + fallback phải cùng rule
# -----------------------------
def test_prompt_file_has_citation_and_grounding_rules():
    text = PROMPT_PATH.read_text(encoding="utf-8")

    assert "[S1]" in text
    assert "không có trong knowledge base" in text.lower()


def test_prompt_file_is_used_and_context_is_injected():
    service = make_service(system_prompt_path=str(PROMPT_PATH))

    prompt = service._create_system_prompt("[S1] a.md:\nhello")

    assert "[S1] a.md:\nhello" in prompt


def test_fallback_prompt_also_requires_citations():
    service = make_service(system_prompt_path="/nonexistent/prompt.txt")

    prompt = service._create_system_prompt("CTX")

    assert "[S1]" in prompt
    assert "không có trong knowledge base" in prompt.lower()
    assert "onboarding" not in prompt.lower()  # nội dung cũ đã bỏ
