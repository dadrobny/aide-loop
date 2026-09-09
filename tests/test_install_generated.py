"""The generator: a delivered file rendered from the section it names.

The gap this closes (issue #109). ADAPTER-SPEC §7 makes an adapter deliver a
contract section to its roles, and makes the delivered copy "add no rule the
engine does not have". Until 1.47.0 the only way to hold a copy to that was to
quote it against itself — the `<!-- pins: … -->` blocks
`adapters/claude/tests/test_rule_pins.py` checks in both directions — which is
a real check and a hand-curated one: a statement nobody pinned drifts freely,
and the curation is the thing a tired reviewer skips.

A file the installer *renders* cannot drift at all. `install.py` reads the
adapter's file, and where it declares

    <!-- generated-from: .aide/conventions/6-test-hygiene.md -->

writes the file's own text followed by that section's **core** — everything
above its closing `Rationale` heading (issue #122) — verbatim. The adapter
half stays authored and inspectable in `adapters/<name>/`: frontmatter, the
`<!-- reach -->` / `<!-- triggers -->` declarations, and whatever the adapter
itself has to say about delivering the section. The engine half is the section.

**This module is the mechanism, tested as functions.** The corpus — which of
the shipped delivered files are generated, and that their rendered form is
their section — is `adapters/claude/tests/test_generated_delivery.py`; what a
consumer ends up holding is `tests/test_fixture_consumer.py`. Here the inputs
are written inline, so each failure names one rule of the grammar rather than
one file that happened to trip it.

Stdlib + pytest only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)

#: A section as `core/conventions/` writes one since #122: core, then a
#: `Rationale` heading one level below the file's own, then the provenance.
SECTION = (
    "## 6. Test hygiene\n"
    "\n"
    "**A rule.** With a shape.\n"
    "\n"
    "### Rationale\n"
    "\n"
    "- **Why.** The defect that earned it.\n"
)
CORE = "## 6. Test hygiene\n\n**A rule.** With a shape.\n"

#: A delivered file as an adapter authors one: frontmatter, the declarations,
#: the adapter's own note — and no body, because the body is the section.
STUB = (
    "---\n"
    "name: aide-test-hygiene\n"
    "user-invocable: false\n"
    "---\n"
    "\n"
    "<!-- reach: test-writer -->\n"
    "\n"
    "<!-- generated-from: .aide/conventions/6-test-hygiene.md -->\n"
    "\n"
    "The section below is `.aide/conventions/6-test-hygiene.md` (§6).\n"
)


@pytest.fixture
def core_dir(tmp_path: Path) -> Path:
    """A `core/` with one section in it — the engine half of a render."""
    conventions = tmp_path / "core" / "conventions"
    conventions.mkdir(parents=True)
    (conventions / "6-test-hygiene.md").write_text(SECTION, encoding="utf-8")
    return tmp_path / "core"


# --------------------------------------------------------------------------- #
# the declaration
# --------------------------------------------------------------------------- #
def test_a_file_with_no_declaration_declares_no_sections():
    """The ordinary answer, and the one that must never be a false positive:
    every other adapter file is copied, and a grammar that matched loosely
    would render an agent spec into an engine section."""
    assert install.generated_sections("# A skill\n\nProse about `generated-from`.\n") == []


def test_the_declaration_is_read_off_its_own_line():
    assert install.generated_sections(STUB) == [".aide/conventions/6-test-hygiene.md"]


def test_a_declaration_may_name_several_sections_in_order():
    """A file delivering more than one section renders them in the order it
    wrote them, which is the only order anyone can predict from reading it."""
    text = "<!-- generated-from: .aide/conventions/a.md, .aide/conventions/b.md -->\n"
    assert install.generated_sections(text) == [".aide/conventions/a.md",
                                                ".aide/conventions/b.md"]


def test_the_closing_arrow_is_not_part_of_the_path():
    """The one-line spelling is the spelling — `<!-- reach: … -->` next door is
    written that way and these comments are read by the same eyes — so the
    `-->` has to come off, or the path names a file with an arrow in it."""
    assert install.generated_sections(
        "<!-- generated-from: .aide/conventions/6-test-hygiene.md-->\n") == [
            ".aide/conventions/6-test-hygiene.md"]


# --------------------------------------------------------------------------- #
# the cut — everything above `Rationale`
# --------------------------------------------------------------------------- #
def test_the_core_is_everything_above_the_rationale_heading():
    assert install.section_core(SECTION) == CORE + "\n"


def test_a_section_with_no_rationale_heading_has_no_core():
    """`None`, not "the whole file". A section that never got #122's split has
    its provenance where its rules are, and delivering the tail as if it were
    rule text is exactly the thing this mechanism promises it does not do."""
    assert install.section_core("## 6. Test hygiene\n\nA rule.\n") is None


def test_a_prose_mention_of_rationale_is_not_the_heading():
    """Anchored to a whole heading line, so a section arguing about rationale
    in a sentence is not cut in half by the word."""
    text = "## 6.\n\nThe rationale for this is below.\n\n### Rationale\n\n- Why.\n"
    assert install.section_core(text) == "## 6.\n\nThe rationale for this is below.\n\n"


# --------------------------------------------------------------------------- #
# the render
# --------------------------------------------------------------------------- #
def test_the_render_is_the_file_then_the_core_verbatim(core_dir: Path):
    """The whole claim: what a role receives *is* the section, byte for byte.

    Written as an equality against the composition rather than a substring
    check, so a transform introduced anywhere in the middle — a reflow, a
    demoted heading, a trimmed bullet — fails here rather than passing a
    weaker assertion.
    """
    assert install.render_delivered(STUB, core_dir) == STUB.rstrip("\n") + "\n\n" + CORE


def test_the_rendered_core_is_the_section_file_itself(core_dir: Path):
    """The same claim from the engine's side: the tail of the delivered file
    is a substring of the section on disk. This is what makes the section the
    source of truth — editing it edits every copy of it."""
    rendered = install.render_delivered(STUB, core_dir)
    section = (core_dir / "conventions" / "6-test-hygiene.md").read_text(encoding="utf-8")
    assert rendered.endswith(install.section_core(section).rstrip("\n") + "\n")


def test_several_sections_render_in_declaration_order(core_dir: Path):
    (core_dir / "conventions" / "7-off.md").write_text(
        "## 7. Off\n\n**Another rule.**\n\n### Rationale\n\n- Why.\n", encoding="utf-8")
    text = ("<!-- generated-from: .aide/conventions/7-off.md, "
            ".aide/conventions/6-test-hygiene.md -->\n")
    rendered = install.render_delivered(text, core_dir)
    assert rendered.index("## 7. Off") < rendered.index("## 6. Test hygiene")


def test_a_declaration_naming_no_section_is_a_generation_error(core_dir: Path):
    """A section renamed under a file that still delivers it. Loud, and at
    install time: the alternative is a consumer holding a delivered file that
    is a frontmatter block and a pointer, with no rules in it at all."""
    text = "<!-- generated-from: .aide/conventions/99-gone.md -->\n"
    with pytest.raises(install.GenerationError, match="99-gone"):
        install.render_delivered(text, core_dir)


def test_a_section_named_by_its_source_path_is_refused(core_dir: Path):
    """`core/conventions/…` is this repo's layout; `.aide/conventions/…` is
    what the file will mean in a consumer, and every other path inside
    `adapters/` is written that way (CLAUDE.md). Refused rather than
    accommodated, so the two spellings never both work."""
    with pytest.raises(install.GenerationError, match="consumer path"):
        install.render_delivered("<!-- generated-from: core/conventions/6-test-hygiene.md -->",
                                 core_dir)


def test_a_climbing_section_path_is_refused(core_dir: Path):
    """The path is joined onto a directory, so it is arms-length input in the
    same sense the adapter manifest is."""
    with pytest.raises(install.GenerationError, match="escapes"):
        install.render_delivered("<!-- generated-from: .aide/../../etc/passwd -->",
                                 core_dir)


def test_a_section_with_no_rationale_heading_is_a_generation_error(core_dir: Path):
    (core_dir / "conventions" / "6-test-hygiene.md").write_text(
        "## 6. Test hygiene\n\nA rule with its provenance inline.\n", encoding="utf-8")
    with pytest.raises(install.GenerationError, match="Rationale"):
        install.render_delivered(STUB, core_dir)


def test_rendering_a_file_that_declares_nothing_is_a_generation_error(core_dir: Path):
    with pytest.raises(install.GenerationError, match="generated-from"):
        install.render_delivered("# A hand-written skill\n", core_dir)


# --------------------------------------------------------------------------- #
# the bytes — the same file whichever OS installed it
# --------------------------------------------------------------------------- #
def test_delivered_bytes_says_copy_it_for_an_ordinary_file(tmp_path: Path,
                                                           core_dir: Path):
    """`None` is "copy this", and it has to be the answer for everything the
    adapter ships that is not a generated delivered file."""
    plain = tmp_path / "SKILL.md"
    plain.write_text("---\nname: aide-create-item\n---\n\n# Create an item\n",
                     encoding="utf-8")
    assert install.delivered_bytes(plain, core_dir) is None
    binary = tmp_path / "hook.py"
    binary.write_bytes(b"# generated-from: nothing\n")
    assert install.delivered_bytes(binary, core_dir) is None


def test_a_crlf_checkout_renders_the_same_bytes_as_an_lf_one(tmp_path: Path,
                                                             core_dir: Path):
    """This repo pins no `text eol=lf`, so the windows CI leg holds CRLF
    (conventions §6) — and a consumer's `git diff` after an `--update` must
    not depend on which platform ran it."""
    lf = tmp_path / "lf.md"
    lf.write_bytes(STUB.encode("utf-8"))
    crlf = tmp_path / "crlf.md"
    crlf.write_bytes(STUB.replace("\n", "\r\n").encode("utf-8"))
    (core_dir / "conventions" / "6-test-hygiene.md").write_bytes(
        SECTION.replace("\n", "\r\n").encode("utf-8"))

    rendered = install.delivered_bytes(crlf, core_dir)
    assert rendered == install.delivered_bytes(lf, core_dir)
    assert b"\r" not in rendered


def test_a_bom_in_the_source_does_not_reach_the_rendered_file(tmp_path: Path,
                                                              core_dir: Path):
    """A BOM in front of `---` is what makes a section skill unpreloadable
    (`tests/test_structural_budget.py`). Rendering decodes with the reader
    that strips one, so an authoring accident in this repo cannot become a
    silently dead delivery in every consumer."""
    bommed = tmp_path / "bom.md"
    bommed.write_bytes(b"\xef\xbb\xbf" + STUB.encode("utf-8"))
    rendered = install.delivered_bytes(bommed, core_dir)
    assert rendered.startswith(b"---\n")
    assert rendered == install.render_delivered(STUB, core_dir).encode("utf-8")


# --------------------------------------------------------------------------- #
# the copy step — one write, recorded like any other
# --------------------------------------------------------------------------- #
def test_copy_tree_writes_the_rendered_bytes_and_records_the_path(tmp_path: Path,
                                                                 core_dir: Path):
    """The hook `run` passes in. A generated file has to land in `written`,
    or the adapter manifest would not list it and the next `--update` would
    read it as a file the consumer added itself."""
    src = tmp_path / "src"
    (src / "skills" / "aide-test-hygiene").mkdir(parents=True)
    (src / "skills" / "aide-test-hygiene" / "SKILL.md").write_text(STUB, encoding="utf-8")
    (src / "skills" / "plain.md").write_text("# copied\n", encoding="utf-8")
    dst = tmp_path / "dst"
    log, written = [], []

    install.copy_tree(src, dst, log, written=written,
                      render=lambda path: install.delivered_bytes(path, core_dir))

    generated = dst / "skills" / "aide-test-hygiene" / "SKILL.md"
    assert generated.read_text(encoding="utf-8").endswith(CORE)
    assert (dst / "skills" / "plain.md").read_text(encoding="utf-8") == "# copied\n"
    assert generated in written


def test_copy_tree_without_a_render_hook_copies_a_declaring_file(tmp_path: Path):
    """`core/` is copied by the same function, and nothing under it is
    generated. The hook is per-call, so the engine copy cannot start
    rendering because the adapter one does."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "SKILL.md").write_text(STUB, encoding="utf-8")
    dst = tmp_path / "dst"

    install.copy_tree(src, dst, [])

    assert (dst / "SKILL.md").read_text(encoding="utf-8") == STUB
