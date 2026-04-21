"""Tests for knowledge_loader.py."""
import pytest
from pathlib import Path

from knowledge_loader import build_prefix, load_knowledge


def test_load_knowledge_imc(tmp_path, monkeypatch):
    folder = tmp_path / "imc_prosperity"
    folder.mkdir()
    (folder / "market_making.md").write_text("# MM\n\nSome content.")
    (folder / "basket_arb.md").write_text("# Baskets\n\nArb content.")

    import knowledge_loader
    monkeypatch.setattr(knowledge_loader, "KNOWLEDGE_DIR", tmp_path)

    result = load_knowledge("imc_prosperity")
    assert "# MM" in result
    assert "# Baskets" in result
    assert "---" in result          # separator between files


def test_load_knowledge_missing_template(tmp_path, monkeypatch):
    import knowledge_loader
    monkeypatch.setattr(knowledge_loader, "KNOWLEDGE_DIR", tmp_path)
    result = load_knowledge("nonexistent_template")
    assert result == ""


def test_build_prefix_combines_addendum_and_knowledge(tmp_path, monkeypatch):
    folder = tmp_path / "my_comp"
    folder.mkdir()
    (folder / "notes.md").write_text("Key note here.")

    import knowledge_loader
    monkeypatch.setattr(knowledge_loader, "KNOWLEDGE_DIR", tmp_path)

    result = build_prefix("my_comp", prompt_addendum="Use this format.")
    assert "Competition Instructions" in result
    assert "Use this format." in result
    assert "Competition Knowledge Base" in result
    assert "Key note here." in result


def test_build_prefix_no_knowledge(tmp_path, monkeypatch):
    import knowledge_loader
    monkeypatch.setattr(knowledge_loader, "KNOWLEDGE_DIR", tmp_path)

    result = build_prefix("no_folder", prompt_addendum="Just addendum.")
    assert "Just addendum." in result
    assert "Knowledge Base" not in result


def test_build_prefix_no_addendum(tmp_path, monkeypatch):
    folder = tmp_path / "comp"
    folder.mkdir()
    (folder / "guide.md").write_text("Guide text.")

    import knowledge_loader
    monkeypatch.setattr(knowledge_loader, "KNOWLEDGE_DIR", tmp_path)

    result = build_prefix("comp", prompt_addendum="")
    assert "Guide text." in result
    assert "Competition Instructions" not in result


def test_real_imc_knowledge_files_exist():
    """Smoke test: real knowledge files are present and non-empty."""
    knowledge_dir = Path(__file__).parent.parent / "knowledge" / "imc_prosperity"
    assert knowledge_dir.is_dir()
    md_files = list(knowledge_dir.glob("*.md"))
    assert len(md_files) >= 3, f"Expected ≥3 files, got {len(md_files)}"
    for f in md_files:
        assert f.stat().st_size > 100, f"{f.name} is suspiciously small"
