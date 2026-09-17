from pypdf import PdfReader

from utils.pdf_export import markdown_to_pdf


def _extract_text(pdf_path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_headers_of_all_levels_render(tmp_path):
    out = tmp_path / "out.pdf"
    markdown_to_pdf("# H1\n## H2\n### H3\nBody text.", "Title", str(out))
    text = _extract_text(out)
    assert "H1" in text and "H2" in text and "H3" in text and "Body text." in text


def test_unicode_punctuation_renders_correctly(tmp_path):
    """
    Regression test: the original PDF exporter used the core Helvetica
    font (Latin-1 only) and fell back to '?' for anything outside that
    range — curly quotes, em-dashes, stars, tildes all came out as '?'.
    Switching to a bundled Unicode TTF font fixed this.
    """
    out = tmp_path / "out.pdf"
    sample = "Curly \u2019quotes\u2019 and an em\u2014dash and a star \u2605 and a tilde ~18."
    markdown_to_pdf(sample, "Title", str(out))
    text = _extract_text(out)
    assert "\u2019" in text
    assert "\u2014" in text
    assert "\u2605" in text
    assert "?" not in text


def test_markdown_table_renders_as_real_table_not_raw_pipes(tmp_path):
    out = tmp_path / "out.pdf"
    table_md = "| Col A | Col B |\n|---|---|\n| foo | bar |\n"
    markdown_to_pdf(table_md, "Title", str(out))
    text = _extract_text(out)
    assert "foo" in text and "bar" in text
    # the raw pipe-table syntax should not leak into the rendered page
    assert "|---|" not in text


def test_bullet_list_renders(tmp_path):
    out = tmp_path / "out.pdf"
    markdown_to_pdf("- First item\n- Second item", "Title", str(out))
    text = _extract_text(out)
    assert "First item" in text
    assert "Second item" in text
