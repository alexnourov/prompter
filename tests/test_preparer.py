"""Tests for preparer subsystem.

Tests cover all requirements: INP-01..INP-06, PRE-01..PRE-04, INC-01..INC-05, ERR-10.
"""

import logging
from pathlib import Path

import pytest

from prompter.preparer import prepare_prompts, register_format


class TestBasicFormats:
    """Tests for basic format parsing (INP-01, INP-01a, INP-02)."""

    def test_prepare_txt(self, tmp_path: Path) -> None:
        """Test .txt format with metadata and two prompts (PRE-02)."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Metadata (skipped)\n---\nFirst prompt\n---\nSecond prompt")

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 2
        assert prompts[0].strip() == "First prompt"
        assert prompts[1].strip() == "Second prompt"

    def test_prepare_md(self, tmp_path: Path) -> None:
        """Test .md format with non-ASCII characters."""
        file_path = tmp_path / "test.md"
        file_path.write_text("Метаданные\n---\nПервый промпт\n---\nВторой промпт", encoding="utf-8")

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 2
        assert prompts[0].strip() == "Первый промпт"
        assert prompts[1].strip() == "Второй промпт"

    def test_prepare_adoc(self, tmp_path: Path) -> None:
        """Test .adoc format with ''' separator (INP-01a, PRE-02)."""
        file_path = tmp_path / "test.adoc"
        content = "= Заголовок (метаданные)\n'''\nПервый промпт\n'''\nВторой промпт"
        file_path.write_text(content, encoding="utf-8")

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 2
        assert "Первый промпт" in prompts[0]
        assert "Второй промпт" in prompts[1]

    def test_prepare_json(self, tmp_path: Path) -> None:
        """Test .json format (INP-02)."""
        file_path = tmp_path / "test.json"
        file_path.write_text('["Промпт один", "Промпт два", "Промпт три"]', encoding="utf-8")

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 3
        assert prompts[0] == "Промпт один"
        assert prompts[1] == "Промпт два"
        assert prompts[2] == "Промпт три"

    def test_prepare_utf8(self, tmp_path: Path) -> None:
        """Test non-ASCII characters preservation (кириллица, ©, €)."""
        test_text = "Тест\nКириллица © €"

        # Test .txt
        txt_file = tmp_path / "test.txt"
        txt_file.write_text(test_text, encoding="utf-8")
        txt_prompts = prepare_prompts(txt_file)
        assert "Кириллица © €" in txt_prompts[0]

        # Test .md
        md_file = tmp_path / "test.md"
        md_file.write_text(test_text, encoding="utf-8")
        md_prompts = prepare_prompts(md_file)
        assert "Кириллица © €" in md_prompts[0]

        # Test .json
        json_file = tmp_path / "test.json"
        json_file.write_text('["Кириллица © €"]', encoding="utf-8")
        json_prompts = prepare_prompts(json_file)
        assert json_prompts[0] == "Кириллица © €"

    def test_prepare_unsupported_extension(self, tmp_path: Path) -> None:
        """Test error on unsupported file format."""
        file_path = tmp_path / "test.xml"
        file_path.write_text("<root/>")

        with pytest.raises(ValueError, match="Unsupported file format: .xml"):
            prepare_prompts(file_path)

    def test_prepare_empty_prompts_stripped(self, tmp_path: Path) -> None:
        """Test that empty prompts between separators are discarded."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("meta\n---\nPrompt 1\n---\n\n---\nPrompt 2")

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 2
        assert prompts[0].strip() == "Prompt 1"
        assert prompts[1].strip() == "Prompt 2"

    def test_prepare_empty_file(self, tmp_path: Path) -> None:
        """Test empty file returns empty list (INP-05)."""
        file_path = tmp_path / "empty.txt"
        file_path.write_text("")

        prompts = prepare_prompts(file_path)

        assert prompts == []

    def test_prepare_only_separators(self, tmp_path: Path) -> None:
        """Test file with only separators returns empty list (INP-05)."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("---\n---")

        prompts = prepare_prompts(file_path)

        assert prompts == []


class TestJSONValidation:
    """Tests for JSON format validation (INP-06)."""

    def test_prepare_invalid_json(self, tmp_path: Path) -> None:
        """Test invalid JSON syntax raises ValueError (INP-06)."""
        file_path = tmp_path / "test.json"
        file_path.write_text("{broken")

        with pytest.raises(ValueError, match="Invalid JSON"):
            prepare_prompts(file_path)

    def test_prepare_json_not_array(self, tmp_path: Path) -> None:
        """Test JSON object instead of array raises ValueError (INP-06)."""
        file_path = tmp_path / "test.json"
        file_path.write_text('{"a": 1}')

        with pytest.raises(ValueError, match="JSON root must be an array"):
            prepare_prompts(file_path)

    def test_prepare_json_non_string_elements(self, tmp_path: Path) -> None:
        """Test JSON array with non-string elements raises ValueError (INP-06)."""
        file_path = tmp_path / "test.json"
        file_path.write_text("[1, 2, 3]")

        with pytest.raises(ValueError, match="Invalid element type"):
            prepare_prompts(file_path)


class TestEscapeSequences:
    """Tests for escape sequences in text formats (INP-04, INC-03)."""

    def test_prepare_escaped_separator(self, tmp_path: Path) -> None:
        """Test \\--- becomes literal --- (INP-04)."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("meta\n---\nPrompt with \\--- inside\n---\nSecond prompt")

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 2
        assert "---" in prompts[0]
        assert "Prompt with --- inside" in prompts[0]

    def test_prepare_double_escaped_separator(self, tmp_path: Path) -> None:
        """Test \\\\--- becomes literal \\--- (INP-04)."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("meta\n---\nString with \\\\--- inside\n---\nSecond prompt")

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 2
        assert "\\---" in prompts[0]
        assert "String with \\--- inside" in prompts[0]


class TestEncodingDetection:
    """Tests for encoding detection and handling (INP-03, ERR-10)."""

    def test_prepare_windows1251_autodetect(self, tmp_path: Path) -> None:
        """Test Windows-1251 encoding auto-detection (INP-03)."""
        file_path = tmp_path / "test.txt"
        text = "Кириллический текст"
        with open(file_path, "w", encoding="windows-1251") as f:
            f.write(text)

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 1
        assert prompts[0] == text

    def test_prepare_koi8r_autodetect(self, tmp_path: Path) -> None:
        """Test KOI8-R encoding auto-detection (INP-03)."""
        file_path = tmp_path / "test.txt"
        # Use longer text for better detection accuracy
        text = "Это длинный текст на русском языке в кодировке KOI8-R для более точного определения кодировки автоматическим детектором."
        with open(file_path, "w", encoding="koi8-r") as f:
            f.write(text)

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 1
        assert prompts[0] == text

    def test_prepare_utf16_bom_autodetect(self, tmp_path: Path) -> None:
        """Test UTF-16 with BOM auto-detection (INP-03)."""
        file_path = tmp_path / "test.txt"
        text = "UTF-16 текст"
        with open(file_path, "w", encoding="utf-16") as f:
            f.write(text)

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 1
        assert prompts[0] == text

    def test_prepare_explicit_source_encoding(self, tmp_path: Path) -> None:
        """Test explicit source_encoding parameter (INP-03)."""
        file_path = tmp_path / "test.txt"
        text = "Кириллица"
        with open(file_path, "w", encoding="windows-1251") as f:
            f.write(text)

        prompts = prepare_prompts(file_path, source_encoding="windows-1251")

        assert len(prompts) == 1
        assert prompts[0] == text

    def test_prepare_wrong_explicit_encoding(self, tmp_path: Path) -> None:
        """Test wrong explicit encoding raises ValueError (INP-03, ERR-10)."""
        file_path = tmp_path / "test.txt"
        text = "Кириллица"
        with open(file_path, "w", encoding="windows-1251") as f:
            f.write(text)

        with pytest.raises(ValueError, match="Failed to decode.*ascii"):
            prepare_prompts(file_path, source_encoding="ascii")

    def test_prepare_binary_file(self, tmp_path: Path) -> None:
        """Test binary file raises ValueError (INP-03, ERR-10)."""
        file_path = tmp_path / "test.txt"
        file_path.write_bytes(bytes(range(256)))

        with pytest.raises(ValueError, match="Could not detect text encoding"):
            prepare_prompts(file_path)

    def test_prepare_utf8_default_regression(self, tmp_path: Path) -> None:
        """Test UTF-8 works without explicit encoding (INP-03)."""
        file_path = tmp_path / "test.txt"
        text = "Кириллический текст"
        file_path.write_text(text, encoding="utf-8")

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 1
        assert prompts[0] == text


class TestMetadataSkipping:
    """Tests for metadata skipping (PRE-02)."""

    def test_metadata_skip_txt(self, tmp_path: Path) -> None:
        """Test metadata before first --- is skipped (PRE-02)."""
        file_path = tmp_path / "test.txt"
        content = "Title: Test\nAuthor: Me\n---\nPrompt 1\n---\nPrompt 2"
        file_path.write_text(content)

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 2
        assert "Title" not in prompts[0]
        assert "Author" not in prompts[0]

    def test_metadata_skip_adoc(self, tmp_path: Path) -> None:
        """Test metadata before first ''' is skipped (PRE-02)."""
        file_path = tmp_path / "test.adoc"
        content = "= Document Title\n:author: Me\n'''\nPrompt 1\n'''\nPrompt 2"
        file_path.write_text(content)

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 2
        assert "Document Title" not in prompts[0]
        assert "author" not in prompts[0]

    def test_no_separator_single_prompt(self, tmp_path: Path) -> None:
        """Test file without separators is treated as single prompt (PRE-02)."""
        file_path = tmp_path / "test.txt"
        content = "This is a single prompt without separators"
        file_path.write_text(content)

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 1
        assert prompts[0] == content


class TestAsciiDocCleaning:
    """Tests for AsciiDoc markup cleaning (PRE-03)."""

    def test_adoc_clean_anchors_and_headings(self, tmp_path: Path) -> None:
        """Test anchors [[...]] and headings == are removed (PRE-03)."""
        file_path = tmp_path / "test.adoc"
        content = "[[anchor-id]]\n== Section Title\n'''\nContent text"
        file_path.write_text(content)

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 1
        assert "[[" not in prompts[0]
        assert "anchor-id" not in prompts[0]
        assert "==" not in prompts[0]
        assert "Section Title" not in prompts[0]
        assert "Content text" in prompts[0]

    def test_adoc_clean_code_blocks_preserve_content(self, tmp_path: Path) -> None:
        """Test [source,python] and ---- are removed, content preserved (PRE-03)."""
        file_path = tmp_path / "test.adoc"
        content = "[source,python]\n----\nprint('hello')\n----"
        file_path.write_text(content)

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 1
        assert "[source" not in prompts[0]
        assert "----" not in prompts[0]
        assert "print('hello')" in prompts[0]

    def test_adoc_clean_admonition(self, tmp_path: Path) -> None:
        """Test [NOTE] and ==== are removed, content preserved (PRE-03)."""
        file_path = tmp_path / "test.adoc"
        content = "[NOTE]\n====\nImportant information\n===="
        file_path.write_text(content)

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 1
        assert "[NOTE]" not in prompts[0]
        assert "====" not in prompts[0]
        assert "Important information" in prompts[0]

    def test_adoc_clean_comments(self, tmp_path: Path) -> None:
        """Test AsciiDoc comments // are removed (PRE-03)."""
        file_path = tmp_path / "test.adoc"
        content = "Visible text\n// This is a comment\nMore visible text"
        file_path.write_text(content)

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 1
        assert "This is a comment" not in prompts[0]
        assert "Visible text" in prompts[0]
        assert "More visible text" in prompts[0]

    def test_adoc_preserve_inline_markup(self, tmp_path: Path) -> None:
        """Test lists, bold, italic, inline code are preserved (PRE-03)."""
        file_path = tmp_path / "test.adoc"
        content = "* List item\n*bold* _italic_ `code`"
        file_path.write_text(content)

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 1
        assert "* List item" in prompts[0]
        assert "*bold*" in prompts[0]
        assert "_italic_" in prompts[0]
        assert "`code`" in prompts[0]

    def test_adoc_code_block_not_filtered(self, tmp_path: Path) -> None:
        """Test markup-like lines inside code blocks are preserved (PRE-03)."""
        file_path = tmp_path / "test.adoc"
        content = "[source,text]\n----\n== Not a heading\n[[not-an-anchor]]\n----"
        file_path.write_text(content)

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 1
        assert "== Not a heading" in prompts[0]
        assert "[[not-an-anchor]]" in prompts[0]

    def test_adoc_smoke_test_prompts_file(self) -> None:
        """Test specs/test_prompts.adoc returns 7 clean prompts (8 blocks - 1 metadata)."""
        prompts_file = Path("specs/test_prompts.adoc")
        if not prompts_file.exists():
            pytest.skip("specs/test_prompts.adoc not found")

        prompts = prepare_prompts(prompts_file)

        assert len(prompts) == 7  # 7 separators = 8 blocks, first is metadata
        # Check no metadata/anchors leaked
        for prompt in prompts:
            assert "[[" not in prompt
            assert "==" not in prompt


class TestLogging:
    """Tests for logging output (PRE-04)."""

    def test_logging_info_summary(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test INFO log contains prompt count and filename (PRE-04)."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("meta\n---\nPrompt 1\n---\nPrompt 2")

        with caplog.at_level(logging.INFO):
            prepare_prompts(file_path)

        assert any("2 prompt(s)" in record.message for record in caplog.records)
        assert any("test.txt" in record.message for record in caplog.records)

    def test_logging_debug_prompt_text(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test DEBUG log contains full prompt text (PRE-04)."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("meta\n---\nSpecial debug prompt")

        with caplog.at_level(logging.DEBUG):
            prepare_prompts(file_path)

        assert any("Special debug prompt" in record.message for record in caplog.records)


class TestCustomFormat:
    """Tests for format registration (PRE-01)."""

    def test_register_custom_format(self, tmp_path: Path) -> None:
        """Test custom format handler registration (PRE-01)."""

        @register_format(".custom")
        def parse_custom(content: str, file_path: Path) -> list[str]:
            return content.split("|")

        file_path = tmp_path / "test.custom"
        file_path.write_text("prompt1|prompt2|prompt3")

        prompts = prepare_prompts(file_path)

        assert len(prompts) == 3
        assert prompts[0] == "prompt1"
        assert prompts[1] == "prompt2"
        assert prompts[2] == "prompt3"


class TestIncludes:
    """Tests for include directives (INC-01..INC-05)."""

    def test_include_txt(self, tmp_path: Path) -> None:
        """Test @include: directive in .txt format (INC-01, INC-03)."""
        # Create extra.txt
        extra_file = tmp_path / "extra.txt"
        extra_file.write_text("extra meta\n---\nExtra 1\n---\nExtra 2")

        # Create main.txt
        main_file = tmp_path / "main.txt"
        main_file.write_text("meta\n---\nPrompt 1\n---\n@include: extra.txt\n---\nPrompt 2")

        prompts = prepare_prompts(main_file)

        assert len(prompts) == 4
        assert prompts[0].strip() == "Prompt 1"
        assert prompts[1].strip() == "Extra 1"
        assert prompts[2].strip() == "Extra 2"
        assert prompts[3].strip() == "Prompt 2"

    def test_include_adoc(self, tmp_path: Path) -> None:
        """Test include::file[] directive in .adoc format (INC-01, INC-04)."""
        # Create extra.adoc
        extra_file = tmp_path / "extra.adoc"
        extra_file.write_text("Extra prompt content")

        # Create main.adoc
        main_file = tmp_path / "main.adoc"
        main_file.write_text("meta\n'''\nPrompt 1\n'''\ninclude::extra.adoc[]\n'''\nPrompt 2")

        prompts = prepare_prompts(main_file)

        assert len(prompts) == 3
        assert "Prompt 1" in prompts[0]
        assert "Extra prompt content" in prompts[1]
        assert "Prompt 2" in prompts[2]

    def test_include_json(self, tmp_path: Path) -> None:
        """Test $ref in .json format (INC-01, INC-05)."""
        # Create extra.json
        extra_file = tmp_path / "extra.json"
        extra_file.write_text('["extra1", "extra2"]')

        # Create main.json
        main_file = tmp_path / "main.json"
        main_file.write_text('["prompt1", {"$ref": "extra.json"}, "prompt3"]')

        prompts = prepare_prompts(main_file)

        assert len(prompts) == 4
        assert prompts[0] == "prompt1"
        assert prompts[1] == "extra1"
        assert prompts[2] == "extra2"
        assert prompts[3] == "prompt3"

    def test_include_json_ref_not_string(self, tmp_path: Path) -> None:
        """Test $ref with non-string value raises ValueError (INC-05)."""
        file_path = tmp_path / "test.json"
        file_path.write_text('[{"$ref": 123}]')

        with pytest.raises(ValueError, match=r"\$ref value must be a string"):
            prepare_prompts(file_path)

    def test_include_cross_format(self, tmp_path: Path) -> None:
        """Test cross-format includes (INC-01)."""
        # Create extra.json
        extra_file = tmp_path / "extra.json"
        extra_file.write_text('["json1", "json2"]')

        # Create main.txt
        main_file = tmp_path / "main.txt"
        main_file.write_text("meta\n---\n@include: extra.json")

        prompts = prepare_prompts(main_file)

        assert len(prompts) == 2
        assert prompts[0] == "json1"
        assert prompts[1] == "json2"

    def test_include_multilevel(self, tmp_path: Path) -> None:
        """Test multilevel includes (INC-01)."""
        # Create c.txt
        c_file = tmp_path / "c.txt"
        c_file.write_text("Prompt C")

        # Create b.txt (metadata + include c)
        b_file = tmp_path / "b.txt"
        b_file.write_text("meta b\n---\nPrompt B\n---\n@include: c.txt")

        # Create a.txt (metadata + include b)
        a_file = tmp_path / "a.txt"
        a_file.write_text("meta a\n---\nPrompt A\n---\n@include: b.txt")

        prompts = prepare_prompts(a_file)

        assert len(prompts) == 3
        assert "Prompt A" in prompts[0]
        assert "Prompt B" in prompts[1]
        assert "Prompt C" in prompts[2]

    def test_include_diamond(self, tmp_path: Path) -> None:
        """Test diamond dependency (A→B→D, A→C→D) (INC-01)."""
        # Create d.txt
        d_file = tmp_path / "d.txt"
        d_file.write_text("Prompt D")

        # Create b.txt (metadata + include d)
        b_file = tmp_path / "b.txt"
        b_file.write_text("meta b\n---\nPrompt B\n---\n@include: d.txt")

        # Create c.txt (metadata + include d)
        c_file = tmp_path / "c.txt"
        c_file.write_text("meta c\n---\nPrompt C\n---\n@include: d.txt")

        # Create a.txt (metadata + include b and c)
        a_file = tmp_path / "a.txt"
        a_file.write_text("meta a\n---\nPrompt A\n---\n@include: b.txt\n---\n@include: c.txt")

        prompts = prepare_prompts(a_file)

        # D appears twice (once per branch)
        assert len(prompts) == 5
        assert "Prompt A" in prompts[0]
        assert "Prompt B" in prompts[1]
        assert "Prompt D" in prompts[2]
        assert "Prompt C" in prompts[3]
        assert "Prompt D" in prompts[4]

    def test_include_circular(self, tmp_path: Path) -> None:
        """Test circular include raises ValueError (INC-02)."""
        # Create a.txt
        a_file = tmp_path / "a.txt"
        a_file.write_text("@include: b.txt")

        # Create b.txt
        b_file = tmp_path / "b.txt"
        b_file.write_text("@include: a.txt")

        with pytest.raises(ValueError, match="Circular include detected"):
            prepare_prompts(a_file)

    def test_include_max_depth(self, tmp_path: Path) -> None:
        """Test excessive include depth raises ValueError (INC-02)."""
        # Create chain of 12 files
        for i in range(12):
            file_path = tmp_path / f"file{i}.txt"
            if i == 11:
                file_path.write_text("Final prompt")
            else:
                file_path.write_text(f"@include: file{i+1}.txt")

        with pytest.raises(ValueError, match="Include depth exceeds maximum"):
            prepare_prompts(tmp_path / "file0.txt")

    def test_include_file_not_found(self, tmp_path: Path) -> None:
        """Test missing include file raises FileNotFoundError (INC-01)."""
        main_file = tmp_path / "main.txt"
        main_file.write_text("@include: nonexistent.txt")

        with pytest.raises(FileNotFoundError):
            prepare_prompts(main_file)
