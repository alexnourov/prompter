"""Tests for the prompter.preparer subpackage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from prompter.models import Prompt
from prompter.preparer import (
    MAX_INCLUDE_DEPTH,
    _first_sentence,
    _handlers,
    prepare_prompts,
    register_format,
)


# ─── Basic format tests ───────────────────────────────────────────────────

class TestPrepareTxt:
    """Tests for .txt file handling."""

    def test_prepare_txt(self, tmp_path: Path) -> None:
        """PRE-02: Metadata before the first --- is skipped, 2 prompts returned."""
        f = tmp_path / "prompts.txt"
        f.write_text(
            "Метаданные (пропускаются)\n"
            "---\n"
            "Первый промпт\n"
            "---\n"
            "Второй промпт\n"
        )
        result = prepare_prompts(f)
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(p, Prompt) for p in result)
        assert result[0].body == "Первый промпт"
        assert result[1].body == "Второй промпт"
        assert result[0].title
        assert result[1].title


class TestPrepareMd:
    """Tests for .md file handling."""

    def test_prepare_md(self, tmp_path: Path) -> None:
        """PRE-02: .md with non-ASCII (Cyrillic) content."""
        f = tmp_path / "prompts.md"
        f.write_text(
            "Метаданные\n"
            "---\n"
            "# Заголовок промпта\n"
            "Тело промпта с кириллицей.\n"
            "---\n"
            "Простой текст без заголовка\n"
        )
        result = prepare_prompts(f)
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(p, Prompt) for p in result)
        assert "кириллицей" in result[0].body


class TestPrepareAdoc:
    """Tests for .adoc file handling."""

    def test_prepare_adoc(self, tmp_path: Path) -> None:
        """INP-01a: AsciiDoc with ''' separators; anchor before heading."""
        f = tmp_path / "prompts.adoc"
        f.write_text(
            "= Заголовок (метаданные)\n"
            ":author: Test\n"
            "\n"
            "'''\n"
            "\n"
            "[[prompt-1]]\n"
            "== Первый промпт\n"
            "\n"
            "Текст первого промпта.\n"
            "\n"
            "'''\n"
            "\n"
            "== Второй промпт\n"
            "\n"
            "Текст второго промпта.\n"
        )
        result = prepare_prompts(f)
        assert len(result) == 2
        assert result[0].title == "Первый промпт"
        assert result[1].title == "Второй промпт"

    def test_prepare_adoc_inline_separator_ignored(self, tmp_path: Path) -> None:
        """PRE-02: ''' inside text/code (not surrounded by blank lines) is not a separator."""
        f = tmp_path / "inline.adoc"
        f.write_text(
            "Метаданные\n"
            "\n"
            "'''\n"
            "\n"
            "== Prompt\n"
            "\n"
            "Промпт с кодом:\n"
            "'''\n"
            "Или так:\n"
            "[source]\n"
            "----\n"
            "value = '''\n"
            "----\n"
        )
        result = prepare_prompts(f)
        assert len(result) == 1
        assert result[0].title == "Prompt"


class TestPrepareJson:
    """Tests for .json file handling."""

    def test_prepare_json(self, tmp_path: Path) -> None:
        """Basic JSON array with 3 title+body objects."""
        f = tmp_path / "prompts.json"
        data = [
            {"title": "Заголовок 1", "body": "Промпт один"},
            {"title": "Заголовок 2", "body": "Промпт два"},
            {"title": "Заголовок 3", "body": "Промпт три"},
        ]
        f.write_text(json.dumps(data, ensure_ascii=False))
        result = prepare_prompts(f)
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0].title == "Заголовок 1"
        assert result[0].body == "Промпт один"
        assert result[1].title == "Заголовок 2"
        assert result[1].body == "Промпт два"
        assert result[2].title == "Заголовок 3"
        assert result[2].body == "Промпт три"


# ─── UTF-8 / special chars ────────────────────────────────────────────────

class TestPrepareUtf8:
    """Tests for non-ASCII character preservation across all formats."""

    def test_prepare_utf8(self, tmp_path: Path) -> None:
        """Non-ASCII chars (Cyrillic, (C), €) preserved in all three formats."""
        text_content = "Кириллица (C) € спецсимволы"

        # .txt
        txt = tmp_path / "u.txt"
        txt.write_text(f"meta\n---\n{text_content}\n")
        r_txt = prepare_prompts(txt)
        assert text_content in r_txt[0].body

        # .md
        md = tmp_path / "u.md"
        md.write_text(f"meta\n---\n{text_content}\n")
        r_md = prepare_prompts(md)
        assert text_content in r_md[0].body

        # .json
        js = tmp_path / "u.json"
        js.write_text(
            json.dumps([{"title": "T", "body": text_content}], ensure_ascii=False)
        )
        r_json = prepare_prompts(js)
        assert text_content in r_json[0].body


# ─── Edge cases ────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge-case tests."""

    def test_prepare_unsupported_extension(self, tmp_path: Path) -> None:
        """ValueError for .xml file."""
        f = tmp_path / "file.xml"
        f.write_text("<root/>")
        with pytest.raises(ValueError, match="Unsupported file format"):
            prepare_prompts(f)

    def test_prepare_empty_prompts_stripped(self, tmp_path: Path) -> None:
        """Empty blocks between --- are discarded."""
        f = tmp_path / "empty_blocks.txt"
        f.write_text("meta\n---\n\n---\n  \n---\nActual prompt\n")
        result = prepare_prompts(f)
        assert len(result) == 1
        assert result[0].body == "Actual prompt"

    def test_prepare_empty_file(self, tmp_path: Path) -> None:
        """INP-05: Empty .txt file returns empty list."""
        f = tmp_path / "empty.txt"
        f.write_text("")
        result = prepare_prompts(f)
        assert result == []

    def test_prepare_only_separators(self, tmp_path: Path) -> None:
        """INP-05: File with only separators returns empty list."""
        f = tmp_path / "seps.txt"
        f.write_text("---\n---\n")
        result = prepare_prompts(f)
        assert result == []


# ─── JSON validation ──────────────────────────────────────────────────────

class TestJsonValidation:
    """Validation tests for .json format (INP-06)."""

    def test_prepare_invalid_json(self, tmp_path: Path) -> None:
        """INP-06: Broken JSON raises ValueError."""
        f = tmp_path / "broken.json"
        f.write_text("{broken")
        with pytest.raises(ValueError, match="Invalid JSON"):
            prepare_prompts(f)

    def test_prepare_json_not_array(self, tmp_path: Path) -> None:
        """INP-06: JSON object (not array) raises ValueError."""
        f = tmp_path / "obj.json"
        f.write_text('{"a": 1}')
        with pytest.raises(ValueError, match="Expected a JSON array"):
            prepare_prompts(f)

    def test_prepare_json_string_elements(self, tmp_path: Path) -> None:
        """INP-06: String elements in array raise ValueError."""
        f = tmp_path / "strings.json"
        f.write_text('["строка"]')
        with pytest.raises(ValueError, match="must be an object"):
            prepare_prompts(f)

    def test_prepare_json_no_title(self, tmp_path: Path) -> None:
        """INP-06: Object without title raises ValueError."""
        f = tmp_path / "nobody.json"
        f.write_text('[{"body": "текст"}]')
        with pytest.raises(ValueError, match='must have "title"\\+"body" or "\\$ref"'):
            prepare_prompts(f)

    def test_prepare_json_non_string_title(self, tmp_path: Path) -> None:
        """INP-06: Non-string title raises ValueError."""
        f = tmp_path / "badtitle.json"
        f.write_text('[{"title": 123, "body": "текст"}]')
        with pytest.raises(ValueError, match="'title' must be a string"):
            prepare_prompts(f)


# ─── Escape sequences (INP-04) ────────────────────────────────────────────

class TestEscapedSeparators:
    """Tests for escaped separators in .txt files (INP-04)."""

    def test_prepare_escaped_separator(self, tmp_path: Path) -> None:
        r"""INP-04: \--- in content becomes literal ---."""
        f = tmp_path / "esc.txt"
        f.write_text("meta\n---\nПромпт с \\--- внутри\n---\nВторой промпт\n")
        result = prepare_prompts(f)
        assert len(result) == 2
        assert "---" in result[0].body
        assert "\\---" not in result[0].body

    def test_prepare_double_escaped_separator(self, tmp_path: Path) -> None:
        r"""INP-04: \\--- becomes literal \---."""
        f = tmp_path / "dblesc.txt"
        f.write_text("meta\n---\nСтрока с \\\\--- внутри\n---\nВторой промпт\n")
        result = prepare_prompts(f)
        assert len(result) == 2
        assert "\\---" in result[0].body


# ─── Encoding (INP-03, ERR-10) ────────────────────────────────────────────

class TestEncoding:
    """Tests for encoding detection and explicit encoding."""

    def test_prepare_windows1251_autodetect(self, tmp_path: Path) -> None:
        """INP-03: Auto-detect Windows-1251 encoding."""
        f = tmp_path / "win1251.txt"
        # Longer text for reliable detection by charset_normalizer
        content = (
            "Метаданные документа для проекта\n"
            "---\n"
            "Это достаточно длинный текст на русском языке, "
            "написанный в кодировке Windows-1251, чтобы библиотека "
            "charset_normalizer могла корректно определить кодировку.\n"
        )
        f.write_bytes(content.encode("windows-1251"))
        result = prepare_prompts(f)
        assert len(result) == 1
        assert "русском" in result[0].body

    def test_prepare_koi8r_autodetect(self, tmp_path: Path) -> None:
        """INP-03: Auto-detect KOI8-R encoding."""
        f = tmp_path / "koi8r.txt"
        # Longer text for reliable detection by charset_normalizer
        content = (
            "Метаданные документа для проекта\n"
            "---\n"
            "Это достаточно длинный текст на русском языке, "
            "написанный в кодировке KOI8-R, чтобы библиотека "
            "charset_normalizer могла корректно определить кодировку.\n"
        )
        f.write_bytes(content.encode("koi8-r"))
        result = prepare_prompts(f)
        assert len(result) == 1
        assert "русском" in result[0].body

    def test_prepare_utf16_bom_autodetect(self, tmp_path: Path) -> None:
        """INP-03: Auto-detect UTF-16 with BOM."""
        f = tmp_path / "utf16.txt"
        content = "meta\n---\nТекст в UTF-16\n"
        f.write_bytes(content.encode("utf-16"))
        result = prepare_prompts(f)
        assert len(result) == 1
        assert "Текст" in result[0].body

    def test_prepare_explicit_source_encoding(self, tmp_path: Path) -> None:
        """INP-03: Explicit source_encoding='windows-1251' works correctly."""
        f = tmp_path / "explicit.txt"
        content = "meta\n---\nТекст\n"
        f.write_bytes(content.encode("windows-1251"))
        result = prepare_prompts(f, source_encoding="windows-1251")
        assert len(result) == 1
        assert "Текст" in result[0].body

    def test_prepare_wrong_explicit_encoding(self, tmp_path: Path) -> None:
        """INP-03, ERR-10: Wrong explicit encoding raises ValueError."""
        f = tmp_path / "wrong.txt"
        f.write_bytes("Кириллица\n".encode("windows-1251"))
        with pytest.raises(ValueError, match="Cannot decode"):
            prepare_prompts(f, source_encoding="ascii")

    def test_prepare_binary_file(self, tmp_path: Path) -> None:
        """INP-03, ERR-10: Binary file raises ValueError."""
        f = tmp_path / "binary.txt"
        f.write_bytes(bytes(range(256)))
        with pytest.raises(ValueError, match="Cannot detect encoding"):
            prepare_prompts(f)

    def test_prepare_utf8_default_regression(self, tmp_path: Path) -> None:
        """INP-03: UTF-8 auto-detect regression — works without source_encoding."""
        f = tmp_path / "utf8.txt"
        f.write_text("meta\n---\nКириллица\n", encoding="utf-8")
        result = prepare_prompts(f)
        assert len(result) == 1
        assert "Кириллица" in result[0].body


# ─── Metadata skip (PRE-02) ───────────────────────────────────────────────

class TestMetadataSkip:
    """Tests for metadata skipping (PRE-02)."""

    def test_metadata_skip_txt(self, tmp_path: Path) -> None:
        """PRE-02: .txt metadata before first --- is excluded."""
        f = tmp_path / "meta.txt"
        f.write_text("Title: Doc\nAuthor: Me\n---\nPrompt 1\n---\nPrompt 2\n")
        result = prepare_prompts(f)
        assert len(result) == 2
        assert all("Title" not in p.body and "Author" not in p.body for p in result)

    def test_metadata_skip_adoc(self, tmp_path: Path) -> None:
        """PRE-02: .adoc metadata before first ''' is excluded."""
        f = tmp_path / "meta.adoc"
        f.write_text(
            "= Doc Title\n"
            ":version: 1.0\n"
            "Preamble text.\n"
            "\n"
            "'''\n"
            "\n"
            "Prompt body.\n"
        )
        result = prepare_prompts(f)
        assert len(result) == 1
        assert "Preamble" not in result[0].body
        assert "Prompt body." in result[0].body

    def test_no_separator_single_prompt(self, tmp_path: Path) -> None:
        """PRE-02: No separators — entire file is one prompt (no metadata)."""
        f = tmp_path / "nosep.txt"
        f.write_text("Full content is one prompt.")
        result = prepare_prompts(f)
        assert len(result) == 1
        assert result[0].body == "Full content is one prompt."


# ─── AsciiDoc cleanup (PRE-03) ────────────────────────────────────────────

class TestAdocCleanup:
    """Tests for AsciiDoc markup cleanup (PRE-03)."""

    def test_adoc_clean_anchors_and_headings(self, tmp_path: Path) -> None:
        """PRE-03: Anchors [[...]] and headings == ... removed from body."""
        f = tmp_path / "ah.adoc"
        f.write_text(
            "meta\n\n'''\n\n"
            "== Main Title\n\n"
            "[[my-anchor]]\n"
            "== Sub heading\n"
            "Body text.\n"
        )
        result = prepare_prompts(f)
        body = result[0].body
        assert "[[my-anchor]]" not in body
        assert "== Sub heading" not in body
        assert "Body text." in body

    def test_adoc_clean_code_blocks_preserve_content(self, tmp_path: Path) -> None:
        """PRE-03: [source,...] and ---- removed; code content preserved."""
        f = tmp_path / "code.adoc"
        f.write_text(
            "meta\n\n'''\n\n"
            "== Prompt\n\n"
            "[source,python]\n"
            "----\n"
            "print('hello')\n"
            "----\n"
        )
        result = prepare_prompts(f)
        body = result[0].body
        assert "[source,python]" not in body
        assert "----" not in body
        assert "print('hello')" in body

    def test_adoc_clean_admonition(self, tmp_path: Path) -> None:
        """PRE-03: [NOTE] and ==== removed; admonition text preserved."""
        f = tmp_path / "adm.adoc"
        f.write_text(
            "meta\n\n'''\n\n"
            "== Prompt\n\n"
            "[NOTE]\n"
            "====\n"
            "Important info.\n"
            "====\n"
            "Normal text.\n"
        )
        result = prepare_prompts(f)
        body = result[0].body
        assert "[NOTE]" not in body
        assert "====" not in body
        assert "Important info." in body
        assert "Normal text." in body

    def test_adoc_clean_comments(self, tmp_path: Path) -> None:
        """PRE-03: AsciiDoc comments // ... removed."""
        f = tmp_path / "comment.adoc"
        f.write_text(
            "meta\n\n'''\n\n"
            "== Prompt\n\n"
            "// This is a comment\n"
            "Visible text.\n"
        )
        result = prepare_prompts(f)
        body = result[0].body
        assert "// This is a comment" not in body
        assert "Visible text." in body

    def test_adoc_preserve_inline_markup(self, tmp_path: Path) -> None:
        """PRE-03: Lists, bold, italic, inline code preserved."""
        f = tmp_path / "inline.adoc"
        f.write_text(
            "meta\n\n'''\n\n"
            "== Prompt\n\n"
            "* Item one\n"
            "* **bold** and _italic_\n"
            "* `inline code`\n"
        )
        result = prepare_prompts(f)
        body = result[0].body
        assert "* Item one" in body
        assert "**bold**" in body
        assert "_italic_" in body
        assert "`inline code`" in body

    def test_adoc_code_block_not_filtered(self, tmp_path: Path) -> None:
        """PRE-03: Markup-like lines inside code blocks are preserved."""
        f = tmp_path / "codefilt.adoc"
        f.write_text(
            "meta\n\n'''\n\n"
            "== Prompt\n\n"
            "[source]\n"
            "----\n"
            "// comment in code\n"
            "[[anchor-in-code]]\n"
            "== heading in code\n"
            "[NOTE]\n"
            "----\n"
            "Outside text.\n"
        )
        result = prepare_prompts(f)
        body = result[0].body
        assert "// comment in code" in body
        assert "[[anchor-in-code]]" in body
        assert "== heading in code" in body
        assert "[NOTE]" in body
        assert "Outside text." in body


# ─── Smoke test: specs/test_prompts.adoc ──────────────────────────────────

class TestAdocSmoke:
    """Smoke test with real spec file."""

    def test_adoc_smoke_test_prompts_file(self) -> None:
        """specs/test_prompts.adoc returns 7 clean prompts without metadata."""
        spec_file = Path(__file__).parent.parent / "specs" / "test_prompts.adoc"
        if not spec_file.exists():
            pytest.skip("specs/test_prompts.adoc not found")
        result = prepare_prompts(spec_file)
        assert len(result) == 7
        # No metadata content leaked
        for p in result:
            assert "Версия:" not in p.body
            assert ":doctype:" not in p.body


# ─── Title extraction (PRE-05) ────────────────────────────────────────────

class TestTitleExtraction:
    """Tests for title extraction across formats (PRE-05)."""

    def test_title_extraction_md_heading(self, tmp_path: Path) -> None:
        """PRE-05: .md # heading becomes title, excluded from body."""
        f = tmp_path / "t.md"
        f.write_text("meta\n---\n# My Title\nBody text\n")
        result = prepare_prompts(f)
        assert result[0].title == "My Title"
        assert "# My Title" not in result[0].body

    def test_title_extraction_md_no_heading(self, tmp_path: Path) -> None:
        """PRE-05: .md without # — title = first sentence, ≤80 chars."""
        f = tmp_path / "t2.md"
        f.write_text("meta\n---\nFirst sentence here. More text.\n")
        result = prepare_prompts(f)
        assert result[0].title == "First sentence here."
        assert len(result[0].title) <= 80

    def test_title_extraction_txt(self, tmp_path: Path) -> None:
        """PRE-05: .txt title = first sentence; body = full text unchanged."""
        f = tmp_path / "t.txt"
        f.write_text("meta\n---\nFirst sentence. Rest of text.\n")
        result = prepare_prompts(f)
        assert result[0].title == "First sentence."
        assert "First sentence." in result[0].body

    def test_title_extraction_adoc_heading_with_anchors(self, tmp_path: Path) -> None:
        """PRE-05: .adoc [[anchor]] + == Title → title='Title', no anchor/heading in body."""
        f = tmp_path / "t.adoc"
        f.write_text(
            "meta\n\n'''\n\n"
            "[[anchor]]\n"
            "== Title\n\n"
            "Body text\n"
        )
        result = prepare_prompts(f)
        assert result[0].title == "Title"
        assert "== Title" not in result[0].body
        assert "[[anchor]]" not in result[0].body

    def test_title_extraction_adoc_no_heading(self, tmp_path: Path) -> None:
        """PRE-05: .adoc without == — title = first sentence after cleanup."""
        f = tmp_path / "t2.adoc"
        f.write_text(
            "meta\n\n'''\n\n"
            "No heading here. More text.\n"
        )
        result = prepare_prompts(f)
        assert result[0].title == "No heading here."

    def test_title_truncation(self, tmp_path: Path) -> None:
        """PRE-05: Title >80 chars truncated to 79 + '…'."""
        long_sentence = "A" * 100 + "."
        f = tmp_path / "long.txt"
        f.write_text(f"meta\n---\n{long_sentence}\n")
        result = prepare_prompts(f)
        assert len(result[0].title) == 80
        assert result[0].title.endswith("…")


# ─── _first_sentence utility (PRE-05) ─────────────────────────────────────

class TestFirstSentence:
    """Tests for _first_sentence utility (PRE-05)."""

    def test_first_sentence(self) -> None:
        """Comprehensive _first_sentence test: dot+space, dot+EOL, no dot, truncation."""
        # dot + space
        assert _first_sentence("Hello world. More text.") == "Hello world."
        # dot at end of line
        assert _first_sentence("Hello world.") == "Hello world."
        # no dot — returns first line
        assert _first_sentence("No dot here\nSecond line.") == "No dot here"
        # truncation
        result = _first_sentence("A" * 100, max_len=80)
        assert len(result) == 80
        assert result == "A" * 79 + "…"

    def test_exact_max_len(self) -> None:
        """Text exactly at max_len is returned as-is."""
        assert _first_sentence("A" * 80, max_len=80) == "A" * 80

    def test_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert _first_sentence("") == ""

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace stripped."""
        assert _first_sentence("  Hello.  \n  World.  ") == "Hello."

    def test_sentence_within_max_len(self) -> None:
        """Short sentence within max_len returned even if line is longer."""
        assert _first_sentence("Short. " + "A" * 200) == "Short."


# ─── Logging (PRE-04) ─────────────────────────────────────────────────────

class TestLogging:
    """Tests for logging in the preparer (PRE-04)."""

    def test_logging_info_summary(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """INFO log contains prompt count and filename."""
        f = tmp_path / "log_test.txt"
        f.write_text("meta\n---\nPrompt one\n---\nPrompt two\n")
        with caplog.at_level("INFO", logger="prompter.preparer"):
            prepare_prompts(f)
        assert any(
            "2 prompt(s)" in rec.message and "log_test.txt" in rec.message
            for rec in caplog.records
        )

    def test_logging_debug_prompt_title(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """DEBUG log contains each prompt's title."""
        f = tmp_path / "debug_test.txt"
        f.write_text("meta\n---\nFirst prompt.\n---\nSecond prompt.\n")
        with caplog.at_level("DEBUG", logger="prompter.preparer"):
            prepare_prompts(f)
        debug_msgs = [r.message for r in caplog.records if r.levelname == "DEBUG"]
        assert any("First prompt." in msg for msg in debug_msgs)
        assert any("Second prompt." in msg for msg in debug_msgs)


# ─── Register custom format (PRE-01) ──────────────────────────────────────

class TestRegisterFormat:
    """Tests for format registration (PRE-01)."""

    def test_register_custom_format(self, tmp_path: Path) -> None:
        """PRE-01: Custom handler registered via @register_format works."""
        @register_format(".custom")
        def handle_custom(content, file_path, resolve_include):
            return [Prompt(title="Custom", body=content.strip())]

        try:
            f = tmp_path / "test.custom"
            f.write_text("Custom body content")
            result = prepare_prompts(f)
            assert len(result) == 1
            assert result[0].title == "Custom"
            assert result[0].body == "Custom body content"
        finally:
            _handlers.pop(".custom", None)


# ─── Include mechanics (INC-01..INC-05) ───────────────────────────────────

class TestInclude:
    """Tests for include directive resolution."""

    def test_include_txt(self, tmp_path: Path) -> None:
        """INC-01, INC-03: @include in .txt resolves in order."""
        extra = tmp_path / "extra.txt"
        extra.write_text("emeta\n---\nExtra1\n---\nExtra2\n")

        main = tmp_path / "main.txt"
        main.write_text(
            "meta\n---\nPrompt1\n---\n@include: extra.txt\n---\nPrompt2\n"
        )
        result = prepare_prompts(main)
        assert len(result) == 4
        assert result[0].body == "Prompt1"
        assert result[1].body == "Extra1"
        assert result[2].body == "Extra2"
        assert result[3].body == "Prompt2"

    def test_include_adoc(self, tmp_path: Path) -> None:
        """INC-01, INC-04: include:: in .adoc replaces the block."""
        extra = tmp_path / "extra.adoc"
        extra.write_text("== Included\n\nIncluded body.\n")

        main = tmp_path / "main.adoc"
        main.write_text(
            "meta\n\n'''\n\n"
            "include::extra.adoc[]\n"
        )
        result = prepare_prompts(main)
        assert len(result) == 1
        assert result[0].title == "Included"

    def test_include_json(self, tmp_path: Path) -> None:
        """INC-01, INC-05: $ref in .json resolves in order."""
        extra = tmp_path / "extra.json"
        extra.write_text(json.dumps([
            {"title": "E1", "body": "extra1"},
            {"title": "E2", "body": "extra2"},
        ]))

        main = tmp_path / "main.json"
        main.write_text(json.dumps([
            {"title": "T1", "body": "prompt1"},
            {"$ref": "extra.json"},
            {"title": "T3", "body": "prompt3"},
        ]))
        result = prepare_prompts(main)
        assert len(result) == 4
        assert [p.title for p in result] == ["T1", "E1", "E2", "T3"]

    def test_include_json_ref_not_string(self, tmp_path: Path) -> None:
        """INC-05: Non-string $ref raises ValueError."""
        f = tmp_path / "badref.json"
        f.write_text('[{"$ref": 123}]')
        with pytest.raises(ValueError, match="must be a string"):
            prepare_prompts(f)

    def test_include_cross_format(self, tmp_path: Path) -> None:
        """INC-01: .txt including .json — cross-format include works."""
        extra = tmp_path / "extra.json"
        extra.write_text(json.dumps([
            {"title": "J1", "body": "json1"},
            {"title": "J2", "body": "json2"},
        ]))

        main = tmp_path / "main.txt"
        main.write_text("meta\n---\n@include: extra.json\n")

        result = prepare_prompts(main)
        assert len(result) == 2
        assert all(isinstance(p, Prompt) for p in result)
        assert result[0].title == "J1"
        assert result[1].title == "J2"

    def test_include_multilevel(self, tmp_path: Path) -> None:
        """INC-01: Multi-level chain a→b→c collects all prompts in order."""
        c = tmp_path / "c.txt"
        c.write_text("C prompt")

        b = tmp_path / "b.txt"
        b.write_text("bmeta\n---\nB prompt\n---\n@include: c.txt\n")

        a = tmp_path / "a.txt"
        a.write_text("ameta\n---\nA prompt\n---\n@include: b.txt\n")

        result = prepare_prompts(a)
        assert len(result) == 3
        assert result[0].body == "A prompt"
        assert result[1].body == "B prompt"
        assert result[2].body == "C prompt"

    def test_include_diamond(self, tmp_path: Path) -> None:
        """INC-01: Diamond A→B→D, A→C→D — D included twice, no error."""
        d = tmp_path / "d.txt"
        d.write_text("D prompt")

        b = tmp_path / "b.txt"
        b.write_text("bmeta\n---\n@include: d.txt\n")

        c = tmp_path / "c.txt"
        c.write_text("cmeta\n---\n@include: d.txt\n")

        a = tmp_path / "a.json"
        a.write_text(json.dumps([{"$ref": "b.txt"}, {"$ref": "c.txt"}]))

        result = prepare_prompts(a)
        assert len(result) == 2
        assert result[0].body == "D prompt"
        assert result[1].body == "D prompt"

    def test_include_circular(self, tmp_path: Path) -> None:
        """INC-02: Circular a→b→a raises ValueError."""
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("meta\n---\n@include: b.txt\n")
        b.write_text("meta\n---\n@include: a.txt\n")
        with pytest.raises(ValueError, match="Circular include"):
            prepare_prompts(a)

    def test_include_max_depth(self, tmp_path: Path) -> None:
        """INC-02: Chain >MAX_INCLUDE_DEPTH raises ValueError."""
        for i in range(MAX_INCLUDE_DEPTH + 2):
            f = tmp_path / f"level{i}.txt"
            if i < MAX_INCLUDE_DEPTH + 1:
                f.write_text(f"meta\n---\n@include: level{i + 1}.txt\n")
            else:
                f.write_text("Final")
        with pytest.raises(ValueError, match="Maximum include depth"):
            prepare_prompts(tmp_path / "level0.txt")

    def test_include_file_not_found(self, tmp_path: Path) -> None:
        """INC-01: Missing include file raises FileNotFoundError."""
        main = tmp_path / "main.txt"
        main.write_text("meta\n---\n@include: nonexistent.txt\n")
        with pytest.raises(FileNotFoundError):
            prepare_prompts(main)
