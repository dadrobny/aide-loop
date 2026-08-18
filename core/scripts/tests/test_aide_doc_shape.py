"""Tests for the checks that hold documents and tests to conventions.md.

Each rule here was stated in the conventions and enforced by nothing. A stated
rule with no check decays — demonstrated twice in this framework's own history:
the slot-in-guidance rule was violated in two consecutive PRs, and the first
guard written for it had a blind spot that let it be violated again.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "aide.py"
_spec = importlib.util.spec_from_file_location("aide_cli_shape", _MODULE_PATH)
aide = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = aide
_spec.loader.exec_module(aide)  # type: ignore[union-attr]

TOML = '[project]\nname = "D"\ndocs_dir = "docs/aide"\ntests_dir = "tests"\n'


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs" / "aide" / "items").mkdir(parents=True)
    (repo / "docs" / "aide" / "queue").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "aide.toml").write_text(TOML, encoding="utf-8")
    return repo


def _cfg(repo: Path):
    return aide.load_config(repo)


# --------------------------------------------------------------------------- #
# nested deliverable bullets
# --------------------------------------------------------------------------- #
def _stage(deliverables: str) -> list:
    return f"## Stage 1 — Rules — 🚧\n\n**Deliverables.**\n{deliverables}\n".splitlines()


def test_nested_status_bullet_is_reported():
    """The rollup reads flat bullets only, so a nested one is invisible to the
    tooling while reading as status to a human."""
    w = aide.nested_deliverable_warnings(_stage("- ✅ A. *(Item 027)*\n  - 🚧 sub. *(Item 028)*"))
    assert len(w) == 1 and "nested status bullet" in w[0]


def test_flat_bullets_are_silent():
    assert aide.nested_deliverable_warnings(
        _stage("- ✅ A. *(Item 027)*\n- 📋 B. *(Item 028)*")) == []


def test_nested_bullet_without_an_icon_is_fine():
    """Only a nested bullet CARRYING status is ambiguous; plain prose is not."""
    assert aide.nested_deliverable_warnings(
        _stage("- ✅ A. *(Item 027)*\n  - a note with no icon")) == []


# --------------------------------------------------------------------------- #
# header blockquote
# --------------------------------------------------------------------------- #
def test_missing_blockquote_is_reported(tmp_path: Path):
    repo = _repo(tmp_path)
    d = repo / "docs" / "aide"
    (d / "progress.md").write_text("# P\n\nStraight into prose.\n", encoding="utf-8")
    w = aide.header_blockquote_warnings(d)
    assert len(w) == 1 and "no header blockquote" in w[0]


def test_blockquote_present_is_silent(tmp_path: Path):
    repo = _repo(tmp_path)
    d = repo / "docs" / "aide"
    (d / "progress.md").write_text("# P\n\n> **Status:** Draft\n", encoding="utf-8")
    assert aide.header_blockquote_warnings(d) == []


def test_an_html_comment_before_the_blockquote_is_allowed(tmp_path: Path):
    """Templates open with a comment the author deletes; it must not read as
    the missing blockquote."""
    repo = _repo(tmp_path)
    d = repo / "docs" / "aide"
    (d / "roadmap.md").write_text("<!-- note -->\n# R\n\n> **Status:** Draft\n",
                                  encoding="utf-8")
    assert aide.header_blockquote_warnings(d) == []


def test_generated_docs_are_not_checked(tmp_path: Path):
    """Only the templated living documents carry a blockquote. A generated
    artifact or a project note under docs_dir is not one — checking those was
    3 false positives out of 8 files when measured against a real consumer."""
    repo = _repo(tmp_path)
    d = repo / "docs" / "aide"
    (d / "feature_catalogue.generated.md").write_text("# Generated\n\ntable\n",
                                                      encoding="utf-8")
    (d / "insights.md").write_text("# Insight Inbox\n\n_Entries below._\n", encoding="utf-8")
    assert aide.header_blockquote_warnings(d) == []


# --------------------------------------------------------------------------- #
# item spec shape
# --------------------------------------------------------------------------- #
def _spec_file(repo: Path, name: str, text: str) -> None:
    (repo / "docs" / "aide" / "items" / name).write_text(text, encoding="utf-8")


GOOD_SPEC = "# Item 027 — Bounds\n\n> **Created:** 2026-08-18\n\n---\n\n## Assumptions\n\nNone.\n"


def test_a_good_spec_is_silent(tmp_path: Path):
    repo = _repo(tmp_path)
    _spec_file(repo, "027-bounds.md", GOOD_SPEC)
    assert aide.item_spec_warnings(repo / "docs" / "aide") == []


def test_heading_disagreeing_with_the_filename_is_reported(tmp_path: Path):
    repo = _repo(tmp_path)
    _spec_file(repo, "027-bounds.md", GOOD_SPEC.replace("Item 027", "Item 028"))
    w = aide.item_spec_warnings(repo / "docs" / "aide")
    assert any("matching the filename" in x for x in w)


def test_a_status_field_in_the_header_is_reported(tmp_path: Path):
    """Status lives only in progress.md; a duplicate has no owner and drifts."""
    repo = _repo(tmp_path)
    _spec_file(repo, "027-bounds.md",
               GOOD_SPEC.replace("> **Created:**", "> **Status:** done\n> **Created:**"))
    w = aide.item_spec_warnings(repo / "docs" / "aide")
    assert any("'Status' field" in x for x in w)


def test_both_bold_field_spellings_are_caught(tmp_path: Path):
    """The template writes `**Created:**` with the colon INSIDE the bold, so a
    pattern expecting `**Status**:` matches nothing and the check silently
    never fires — caught only because a test asserted the real template shape."""
    repo = _repo(tmp_path)
    _spec_file(repo, "027-a.md", GOOD_SPEC.replace("> **Created:**", "> **Status:** x\n> **Created:**"))
    _spec_file(repo, "028-b.md", GOOD_SPEC.replace("Item 027", "Item 028").replace(
        "> **Created:**", "> **Completed**: y\n> **Created:**"))
    w = aide.item_spec_warnings(repo / "docs" / "aide")
    assert sum("field" in x for x in w) == 2


def test_a_status_word_after_the_header_is_not_flagged(tmp_path: Path):
    """Only the header carries the ban — body prose may discuss status freely."""
    repo = _repo(tmp_path)
    _spec_file(repo, "027-bounds.md", GOOD_SPEC + "\n**Status**: discussed in prose.\n")
    assert aide.item_spec_warnings(repo / "docs" / "aide") == []


def test_missing_assumptions_is_aggregated_into_one_warning(tmp_path: Path):
    """32 of 112 specs predated the rule in the consumer measured against.
    Thirty-two separate warnings would bury the substantive ones — the failure
    mode issue #13 was filed for."""
    repo = _repo(tmp_path)
    for n in range(1, 13):
        _spec_file(repo, f"{n:03d}-x.md", f"# Item {n:03d} — X\n\n> **Created:** 2026-08-18\n")
    w = aide.item_spec_warnings(repo / "docs" / "aide")
    assumption_warnings = [x for x in w if "Assumptions" in x]
    assert len(assumption_warnings) == 1
    assert "12 item spec(s)" in assumption_warnings[0] and "+4 more" in assumption_warnings[0]


# --------------------------------------------------------------------------- #
# test hygiene lints
# --------------------------------------------------------------------------- #
def test_str_of_a_relative_path_is_reported(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "tests" / "test_x.py").write_text(
        "names = sorted(str(p.relative_to(root)) for p in tree)\n", encoding="utf-8")
    w = aide.separator_dependent_test_warnings(repo, _cfg(repo))
    assert len(w) == 1 and "as_posix" in w[0]


def test_fstring_interpolated_path_is_reported(tmp_path: Path):
    """An f-string calls str() too — this was the third recorded instance."""
    repo = _repo(tmp_path)
    (repo / "tests" / "test_x.py").write_text(
        'loc = f"{path.relative_to(ddir)}:{lineno}"\n', encoding="utf-8")
    assert len(aide.separator_dependent_test_warnings(repo, _cfg(repo))) == 1


def test_as_posix_is_silent(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "tests" / "test_x.py").write_text(
        "names = sorted(p.relative_to(root).as_posix() for p in tree)\n", encoding="utf-8")
    assert aide.separator_dependent_test_warnings(repo, _cfg(repo)) == []


def test_shelling_out_to_the_cli_is_reported(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "tests" / "test_x.py").write_text(
        'import subprocess\nsubprocess.run(["python", ".aide/scripts/aide.py", "check"])\n',
        encoding="utf-8")
    w = aide.cli_subprocess_test_warnings(repo, _cfg(repo))
    assert len(w) == 1 and "call the function instead" in w[0]


def test_a_docstring_mentioning_the_cli_is_not_flagged(tmp_path: Path):
    """Measured against a real consumer, the ONLY textual match was a docstring
    explaining why the author had removed a subprocess. A line-based lint flags
    the file documenting the correct practice, so this one walks the AST."""
    repo = _repo(tmp_path)
    (repo / "tests" / "test_x.py").write_text(
        'def f():\n    """Calls run_checks rather than shelling out to aide.py\n'
        '    via subprocess.run, which failed on Windows."""\n    return 1\n',
        encoding="utf-8")
    assert aide.cli_subprocess_test_warnings(repo, _cfg(repo)) == []


def test_an_unparseable_test_file_does_not_crash_the_check(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "tests" / "test_x.py").write_text("def broken(:\n", encoding="utf-8")
    assert aide.cli_subprocess_test_warnings(repo, _cfg(repo)) == []


def test_one_warning_per_file(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "tests" / "test_x.py").write_text(
        "a = str(p.relative_to(r))\nb = str(q.relative_to(r))\n", encoding="utf-8")
    assert len(aide.separator_dependent_test_warnings(repo, _cfg(repo))) == 1
