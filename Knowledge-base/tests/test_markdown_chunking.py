"""Test markdown heading-aware chunking (KB-2.4).

Chỉ test splitter + `_process_single_file` với file tạm ⇒ không cần model/Chroma.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.document_service import DocumentService


def make_service(chunk_size: int = 200, chunk_overlap: int = 20) -> DocumentService:
    service = object.__new__(DocumentService)  # bỏ qua __init__ nặng
    service.settings = SimpleNamespace(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    service.text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )
    service.executor = ThreadPoolExecutor(max_workers=1)
    return service


def md_doc(content: str) -> Document:
    return Document(page_content=content, metadata={"source": "Interview/x.md"})


def test_headings_produce_heading_path():
    service = make_service()
    content = "# Java\nintro\n## Core\ncore text\n### Collections\ncollections text\n"

    chunks = service._split_markdown([md_doc(content)])
    paths = [chunk.metadata["heading_path"] for chunk in chunks]

    assert "Java" in paths
    assert "Java > Core" in paths
    assert "Java > Core > Collections" in paths
    assert all(chunk.metadata["source"] == "Interview/x.md" for chunk in chunks)


def test_file_without_heading_gets_empty_heading_path():
    chunks = make_service()._split_markdown([md_doc("plain text without headings")])

    assert len(chunks) == 1
    assert chunks[0].metadata["heading_path"] == ""


def test_long_section_is_split_and_keeps_heading_path():
    service = make_service(chunk_size=120, chunk_overlap=10)
    body = "sentence about caching. " * 40  # dài hơn chunk_size nhiều lần

    chunks = service._split_markdown([md_doc(f"## Caching\n{body}")])

    assert len(chunks) > 1  # section dài phải bị cắt tiếp
    assert {chunk.metadata["heading_path"] for chunk in chunks} == {"Caching"}
    assert all(len(chunk.page_content) <= 120 for chunk in chunks)


def test_process_single_file_assigns_chunk_index_and_heading_path(tmp_path):
    service = make_service()
    path = tmp_path / "note.md"
    path.write_text("# A\n\nalpha\n\n# B\n\nbeta\n", encoding="utf-8")

    chunks = asyncio.run(service._process_single_file(path))

    assert [chunk.metadata["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
    assert {chunk.metadata["heading_path"] for chunk in chunks} == {"A", "B"}
    assert all(chunk.metadata["file_name"] == "note.md" for chunk in chunks)


def test_txt_file_uses_plain_splitter_and_has_no_heading_path(tmp_path):
    service = make_service()
    path = tmp_path / "note.txt"
    path.write_text("plain text\n\nsecond paragraph\n", encoding="utf-8")

    chunks = asyncio.run(service._process_single_file(path))

    assert chunks
    assert all("heading_path" not in chunk.metadata for chunk in chunks)
