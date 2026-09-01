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

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATES = sorted((_ROOT / "core" / "templates").glob("*.md"))

#: The issue template is a template this repo authors under the same convention,
#: and it sat outside this glob until a slip landed in it. Note the limit: this
#: guard decides one shape — a slot *inside* italic guidance — and the slip that
#: widened the glob was the other shape, guidance written *as* a slot, which no
#: heuristic can tell from a legitimate value slot. Covering the shape it can
#: decide still costs nothing.
_TEMPLATES += sorted((_ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.md"))


_ITALIC_DELIM_RE = re.compile(r"(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])")


def _guidance_slots(path: Path) -> list:
    """(lineno, text) for every `{{...}}` that sits *inside* an italic span.

    Scans positionally, carrying italic state across lines, so it covers all
    three shapes the templates actually use: a whole italic paragraph, a
    single-line `_guidance._`, and `**Label.** _guidance…_` that opens its
    italics mid-line.

    An earlier version tested "does the line start with `_`", which had a blind
    spot for that third shape — and the very slip this file guards against
    recurred *in the PR that added the guard* because of it. A guard with a
    blind spot is worse than none, because it is trusted (conventions.md §6).
    A `_` inside a word (`queue_cap`) is not a delimiter and never toggles.
    """
    hits, in_italic = [], False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        events = [(m.start(), "delim") for m in _ITALIC_DELIM_RE.finditer(line)]
        events += [(m.start(), "slot") for m in re.finditer(r"\{\{", line)]
        flagged = False
        for _, kind in sorted(events):
            if kind == "delim":
                in_italic = not in_italic
            elif in_italic and not flagged:
                hits.append((n, line.strip()))
                flagged = True
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


def test_guidance_opening_mid_line_is_covered(tmp_path: Path):
    """`**Label.** _guidance…_` opens its italics after a bold label. The first
    version of this check only opened a block on a LEADING underscore, so it
    missed exactly this shape — and the slip recurred in the same PR that added
    the guard."""
    bad = tmp_path / "midline.md"
    bad.write_text("**Human gate.** _OPTIONAL — the row usually reads\n"
                   "`Blocks: stage {{n}}`. A gate written only here does nothing._\n",
                   encoding="utf-8")
    assert [n for n, _ in _guidance_slots(bad)] == [2]


def test_a_word_internal_underscore_is_not_a_delimiter(tmp_path: Path):
    """`queue_cap` in prose must not be read as opening an italic block, or
    every slot after it would be falsely flagged."""
    ok = tmp_path / "snake.md"
    ok.write_text("Prose naming queue_cap and loop_clarify.\n\n| {{slot}} | x |\n",
                  encoding="utf-8")
    assert _guidance_slots(ok) == []


def test_multi_line_guidance_is_covered(tmp_path: Path):
    """Every recorded instance sat in a multi-line italic paragraph, so a
    single-line check would have missed all of them."""
    bad = tmp_path / "multi.md"
    bad.write_text("_Guidance opens here\nand mentions {{yyyy-mm-dd}} midway\n"
                   "before closing._\n", encoding="utf-8")
    assert [n for n, _ in _guidance_slots(bad)] == [2]
