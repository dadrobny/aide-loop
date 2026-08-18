"""The templates must obey the template convention they define.

`CLAUDE.md` and `conventions.md` §1 state it: `{{slot}}` marks a literal value
to substitute, an _italic line_ marks authoring guidance to read then replace,
and **guidance must never be written as a slot** — because `aide check` errors
on any `{{...}}` surviving into a consumer's `docs/aide/**`, so a slot sitting
inside guidance prose turns "you left the guidance in" into a confusing
"unfilled template slot" pointing at text that was never a field.

Nothing checked this, and it recurred: the same slip landed in two separate
PRs, once in prose describing a date format and once as a whole guidance
sentence written as a slot. A convention nothing enforces is a convention that
decays — the same reasoning that put the command-hygiene rules behind a hook.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_TEMPLATES = sorted((Path(__file__).resolve().parents[1] / "core" / "templates").glob("*.md"))


def _guidance_slots(path: Path) -> list:
    """(lineno, text) for every `{{...}}` inside an italic guidance block.

    A guidance block starts at a line beginning with `_` and runs until a line
    ending with `_`, so a multi-line italic paragraph is covered — which is
    where every recorded instance actually sat.
    """
    hits, in_block = [], False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not in_block:
            if not stripped.startswith("_"):
                continue
            # A one-line block opens and closes on the same line.
            in_block = not (stripped.endswith("_") and len(stripped) > 1)
            if "{{" in stripped:
                hits.append((n, stripped))
            continue
        if "{{" in stripped:
            hits.append((n, stripped))
        if stripped.endswith("_"):
            in_block = False
    return hits


def test_there_are_templates():
    assert _TEMPLATES, "no core/templates/*.md found — the glob or the layout moved"


@pytest.mark.parametrize("path", _TEMPLATES, ids=lambda p: p.name)
def test_no_slot_inside_guidance(path: Path):
    hits = _guidance_slots(path)
    assert not hits, (
        f"{path.name}: {{{{...}}}} inside italic guidance at line(s) "
        + ", ".join(str(n) for n, _ in hits)
        + ". Guidance is replaced, not filled: write the shape in plain text "
          "(YYYY-MM-DD, 'item numbers') and keep {{slots}} on the content line "
          "an author actually substitutes."
    )


def test_the_check_would_catch_a_regression(tmp_path: Path):
    """The guard on the guard — a check that cannot fail is worse than none
    (conventions.md §6)."""
    bad = tmp_path / "bad.md"
    bad.write_text("_Guidance saying `✅ Met ({{yyyy-mm-dd}})` here._\n", encoding="utf-8")
    assert _guidance_slots(bad)


def test_a_slot_on_a_content_line_is_allowed(tmp_path: Path):
    """Table rows and headings are exactly where slots belong."""
    ok = tmp_path / "ok.md"
    ok.write_text("| {{target}} | ⏳ Awaiting |\n\n_Plain guidance, no slots._\n",
                  encoding="utf-8")
    assert _guidance_slots(ok) == []


def test_multi_line_guidance_is_covered(tmp_path: Path):
    """Every recorded instance sat in a multi-line italic paragraph, so a
    single-line check would have missed all of them."""
    bad = tmp_path / "multi.md"
    bad.write_text("_Guidance opens here\nand mentions {{yyyy-mm-dd}} midway\n"
                   "before closing._\n", encoding="utf-8")
    assert [n for n, _ in _guidance_slots(bad)] == [2]
