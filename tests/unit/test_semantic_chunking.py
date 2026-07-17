"""Unit tests for semantic chunking."""

from __future__ import annotations

from archium.config.settings import Settings
from archium.infrastructure.chunking.semantic import SemanticChunker
from archium.infrastructure.chunking.text_splitter import split_text
from archium.infrastructure.document_parsers.base import ParsedPage


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "_env_file": None,
        "database_url": "sqlite:///:memory:",
        "semantic_chunking_enabled": True,
        "chunk_max_chars": 120,
        "chunk_min_chars": 40,
        "chunk_overlap_chars": 20,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_split_text_breaks_on_chinese_sentence_boundary() -> None:
    text = "老院区交通组织混乱，人车混行严重。" * 12
    chunks = split_text(text, chunk_size=80, chunk_overlap=15)

    assert len(chunks) > 1
    assert all(len(chunk) <= 80 for chunk in chunks)


def test_split_text_carries_overlap() -> None:
    text = "第一段内容较长，需要被切开。" + "第二段继续补充背景信息。" * 6
    chunks = split_text(text, chunk_size=60, chunk_overlap=12)

    assert len(chunks) >= 2
    tail = chunks[0][-12:]
    assert any(tail[-6:] in chunk for chunk in chunks[1:])


def test_merge_small_paragraphs_in_same_section() -> None:
    chunker = SemanticChunker(_settings(chunk_max_chars=200, chunk_min_chars=80))
    parts = chunker.chunk_pages(
        [
            ParsedPage(text="项目背景说明。", section_title="现状分析", content_type="paragraph"),
            ParsedPage(text="用地条件与周边关系。", section_title="现状分析", content_type="paragraph"),
        ]
    )

    assert len(parts) == 1
    assert "项目背景说明" in parts[0].content
    assert "用地条件" in parts[0].content
    assert parts[0].section_title == "现状分析"


def test_long_page_splits_into_multiple_semantic_chunks() -> None:
    chunker = SemanticChunker(_settings(chunk_max_chars=120, chunk_overlap_chars=15))
    long_text = "。".join(f"第{index}段描述项目现状与改造需求" for index in range(1, 25)) + "。"
    parts = chunker.chunk_pages(
        [
            ParsedPage(
                page_number=3,
                text=long_text,
                section_title="现状分析",
                content_type="text",
            )
        ]
    )

    assert len(parts) > 1
    assert all(part.page_number == 3 for part in parts)
    assert all(part.metadata.get("chunk_strategy") == "semantic" for part in parts)


def test_section_change_prevents_merge() -> None:
    chunker = SemanticChunker(_settings(chunk_max_chars=300, chunk_min_chars=80))
    parts = chunker.chunk_pages(
        [
            ParsedPage(text="交通组织现状描述。", section_title="交通", content_type="paragraph"),
            ParsedPage(text="景观绿化策略说明。", section_title="景观", content_type="paragraph"),
        ]
    )

    assert len(parts) == 2
    assert parts[0].section_title == "交通"
    assert parts[1].section_title == "景观"
