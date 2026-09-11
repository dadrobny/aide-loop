"""The generated delivered files: the copy a role loads **is** the section.

The gap this closes (issue #109). ADAPTER-SPEC §7 makes three things
conformant about a delivered file: it loads without the role choosing to, it
names the section it delivers, and it **adds no rule the engine does not
have**. `test_rules.py` holds the first two structurally. The third was held by
`test_rule_pins.py` — a curated list of sentences, asserted on both sides —
which is a real check with a known gap: a statement nobody pinned drifts
freely, and the curation is the step a tired author skips.

For a file that declares

    <!-- generated-from: .aide/conventions/6-test-hygiene.md -->

there is nothing to curate. `install.py` writes the section's **core** —
everything above its closing `Rationale` heading (issue #122) — into the file
verbatim at install time, so the third obligation holds by construction and the
pins mechanism retires for it (`test_rule_pins.py` excludes it and fails if it
declares a pin anyway).

**What is left to check is that the generator actually runs, and that what it
emits is the section.** That is this module, on the source tree: each generated
file names a section that exists, and its rendered form is its own text
followed by that section's core, byte for byte. The same claim inside a real
install is `tests/test_fixture_consumer.py`; the grammar itself, as functions,
is `tests/test_install_generated.py`.

**And the adapter's half stays the adapter's.** The text a generated file
authors — its frontmatter, whatever it has to say about *delivering* the
section — sits above the render and is checked here too, because that half can
drift: it is the one place a generated file could still state a rule the
engine does not have. Its `<!-- reach -->` / `<!-- triggers -->` declarations
sit there in the source and nowhere else: they address this repository's
suite, so an install strips them (issue #205) and the equality below composes
the stripped half.

Stdlib + pytest only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_ADAPTER = Path(__file__).resolve().parents[1]
_CORE = _ADAPTER.parents[1] / "core"

sys.path.insert(0, str(_ADAPTER.parents[1]))
sys.path.insert(0, str(_ADAPTER.parents[1] / "tests"))
import install  # noqa: E402  (path shim above)
from _delivered import (STRIPS_BOM, generated_from, is_generated,  # noqa: E402
                        label as _label, rendered, rendered_body,
                        strip_comments, strip_declarations)

#: The source tree, so the reader that reports on a file behind a BOM rather
#: than the one that refuses it — `tests/_delivered.py` has the difference.
_read = STRIPS_BOM.text
_body = STRIPS_BOM.body

_DELIVERING = (sorted((_ADAPTER / "rules").glob("*.md"))
               + [p for p in sorted((_ADAPTER / "skills").glob("*/SKILL.md"))
                  if STRIPS_BOM.is_section_skill(p)])

#: Every delivered file an install renders. Structural, like every other set
#: in this suite: a file converted tomorrow is checked the moment it lands.
_GENERATED = [p for p in _DELIVERING if is_generated(p)]


# --------------------------------------------------------------------------- #
# fail closed — the set is recognisable before anything is asserted about it
# --------------------------------------------------------------------------- #
def test_the_adapter_ships_generated_delivered_files():
    """conventions.md §6: an empty derived set makes every parametrised test
    below vanish with a green suite — here that would read as "the generator
    is fine" when what happened is that nothing declares itself generated."""
    assert _DELIVERING, "no delivered files found — the layout moved"
    assert _GENERATED, (
        "no delivered file declares `<!-- generated-from: … -->`. Either the "
        "declaration stopped parsing, or every generated file was converted "
        "back to a hand-written copy — in which case the pins mechanism owns "
        "them again and this module should go, not sit here passing over "
        "nothing.")


# --------------------------------------------------------------------------- #
# the render — the delivered body IS the section
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path", _GENERATED, ids=_label)
def test_a_generated_file_names_a_section_that_exists(path: Path):
    """The section is the source of truth, so its path is the one thing this
    file cannot get wrong quietly: a rename would otherwise deliver a
    frontmatter block and a pointer, with no rules under it."""
    declared = generated_from(path)
    assert declared, f"{_label(path)}: declares no section"
    for section in declared:
        source = _CORE.joinpath(*section[len(".aide/"):].split("/"))
        assert source.is_file(), (
            f"{_label(path)}: names {section}, which is not a file under "
            f"core/ — the section moved or was renamed")


@pytest.mark.parametrize("path", _GENERATED, ids=_label)
def test_the_rendered_file_is_the_adapters_text_then_the_section_core(path: Path):
    """The whole property, as an equality rather than a substring test.

    Composition, not containment: `render` may append the core and nothing
    else, so a transform introduced between the two — a reflow, a demoted
    heading, a bullet dropped because it "reads oddly out of context" — fails
    here. That is the constraint the mechanism trades for retiring the pins:
    if a section cannot be delivered whole, the section is what changes.

    The adapter's text is its source *minus the test declarations* since
    1.49.3 (issue #205): `reach` and `triggers` are assertions addressed to
    `tests/test_structural_budget.py`, which a consumer does not install, so
    they stay in `adapters/claude/` and the render drops them. Nothing else
    about either half moves, which is what makes the strip expressible as one
    call on this side of the equality rather than a second render.
    """
    cores = []
    for section in generated_from(path):
        source = _CORE.joinpath(*section[len(".aide/"):].split("/"))
        core = install.section_core(install.source_text(source))
        assert core is not None, (
            f"{section}: no closing `Rationale` heading, so the cut #122 "
            f"defined does not exist in it and there is no core to deliver")
        cores.append(core.rstrip("\n"))
    own = strip_declarations(_read(path))
    expected = "\n\n".join([own.rstrip("\n")] + cores) + "\n"
    assert rendered(path) == expected


@pytest.mark.parametrize("path", _GENERATED, ids=_label)
def test_editing_the_section_edits_the_delivered_copy(path: Path, tmp_path: Path):
    """The direction that makes the section the source of truth.

    Not a restatement of the equality above: it asserts that a change to
    `core/conventions/<file>` reaches the delivered body with no second edit
    anywhere, which is the whole claim the pins mechanism could only
    approximate. Rendered against a copy of the engine with one sentence added
    to each section's core, so nothing on disk is touched and the installer's
    own code path is the one exercised.
    """
    added = "**A rule added by this test, above the Rationale heading.**"
    core = tmp_path / "core"
    for section in generated_from(path):
        relative = Path(*section[len(".aide/"):].split("/"))
        text = install.source_text(_CORE / relative)
        cut = install.RATIONALE_HEADING.search(text)
        assert cut, f"{section}: no `Rationale` heading to insert above"
        edited = f"{text[:cut.start()]}{added}\n\n{text[cut.start():]}"
        (core / relative).parent.mkdir(parents=True, exist_ok=True)
        (core / relative).write_text(edited, encoding="utf-8")

    assert added in install.render_delivered(_read(path), core), (
        f"{_label(path)}: a statement added to its section did not reach the "
        f"delivered body — the render is not reading the section")


# --------------------------------------------------------------------------- #
# the adapter's own half — the part that can still drift
# --------------------------------------------------------------------------- #
#: A heading in the adapter's half. The section's own `## N.` heading arrives
#: with the core and is not this; anything above the render is the adapter
#: talking, and a heading there is a second document starting.
_HEADING = re.compile(r"^#{1,6}[ \t]+\S", re.M)


@pytest.mark.parametrize("path", _GENERATED, ids=_label)
def test_the_adapters_half_says_it_is_delivery_and_names_the_section(path: Path):
    """What a role reads before the section starts, held to the two things it
    is for: saying which engine file this is a copy of, and saying that the
    engine file wins. It is the one place a generated file can still say
    something the engine does not."""
    own = strip_comments(_body(path))
    assert "conventions.md" in own, f"{_label(path)}: names no source section"
    assert re.search(r"§\d", own), f"{_label(path)}: names no section number"
    assert "not a second source of truth" in own, (
        f"{_label(path)}: does not say the engine section wins. A reader with "
        f"this file in context has to be told which copy is authoritative, or "
        f"the one in front of them is the one they will trust.")


@pytest.mark.parametrize("path", _GENERATED, ids=_label)
def test_the_adapters_half_opens_no_heading_of_its_own(path: Path):
    """The section arrives with its own `## N. …` heading, which titles the
    delivered file. A heading above it would make the file read as two
    documents, with the adapter's note as the title of the engine's rules."""
    own = strip_comments(_body(path))
    assert not _HEADING.search(own), (
        f"{_label(path)}: opens a heading above the rendered section. The "
        f"section's own heading is the title of this file.")


@pytest.mark.parametrize("path", _GENERATED, ids=_label)
def test_the_adapters_half_is_a_note_not_a_second_statement_of_the_rules(path: Path):
    """A budget, and the reason it is one. Every byte above the render is paid
    on every spawn that loads the file and says nothing the section says — so
    it stays a note. The number is generous and fails in one direction only:
    it is here to catch a restatement growing back, not to be tuned.
    """
    own = len(strip_comments(_body(path)).encode("utf-8"))
    delivered = len(strip_comments(rendered_body(path)).encode("utf-8"))
    assert own < delivered / 2, (
        f"{_label(path)}: the adapter's own half is {own} B against {delivered} "
        f"B delivered. That is no longer a delivery note; whatever it now says "
        f"belongs in the section, or in a comment the preload strips.")
