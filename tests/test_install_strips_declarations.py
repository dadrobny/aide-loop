"""The test declarations stop at the installer (issue #205).

`pins`, `reach` and `triggers` are comments this repository's suite reads:
`adapters/claude/tests/test_rule_pins.py` asserts every pinned sentence on both
sides, `tests/test_structural_budget.py` compares a declared reach to the
carrier that delivers it. A consumer installs neither module. So in a
consumer's tree the blocks are bytes nobody can act on, sitting inside files a
runtime may hand a reader whole — 26% of the installed skills, rules and
always-on page at 1.49.2, and 42% of the worst single file, `aide-item-specs`. ADAPTER-SPEC's
*Copies of engine text* section decides it under *What an install ships*: a
declaration that exists for the framework's tests does not ship.

**What this module holds is the strip's edges**, which is where a text
transform goes wrong:

- it removes the three declaration kinds and **nothing else** — a comment
  written for the *reader* of a delivered file is content, and survives;
- it takes the blank line a block stood on, so a block between two paragraphs
  leaves the one blank line that separated them, not two and not none;
- it leaves a file with no declaration byte-identical, which is what lets the
  installer copy most of the adapter rather than rewrite it;
- and stripping is not **drift**: `--check` after an `--update` says up to
  date, because the installed file is what the installer writes, not what it
  compares.

The two claims about *which* files it applies to live with their own subjects:
that an installed control file is its source minus the declarations is
`tests/test_structural_budget.py`, and that a generated file's adapter half is
stripped before the core is appended is
`adapters/claude/tests/test_generated_delivery.py`.

Stdlib + pytest only, and `Path` throughout: the windows leg runs this too.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above; there is no conftest.py)

#: A comment a *reader* is meant to see, in the shape an author would write
#: one. It must survive, or "strip the declarations" has quietly become "strip
#: every comment" and the next editorial note vanishes on install.
READER_COMMENT = "<!-- A note for whoever opens this file. -->"

#: A declaration as the delivered files write one: opener, a prose note, `- `
#: lines, and a `-->` several lines down. The multi-line case is the one with
#: a blank line to get wrong.
MULTILINE_BLOCK = (
    "<!-- pins: .aide/conventions/6-test-hygiene.md\n"
    "     A prose note may sit above the quotations.\n"
    "     - A test must be deterministic.\n"
    "     - And pass on Windows. -->"
)


# --------------------------------------------------------------------------- #
# the function — every shape the strip has to get right, without an install
# --------------------------------------------------------------------------- #
def test_a_file_with_no_declaration_is_returned_unchanged():
    """Identity, not "equal after normalising". `delivered_bytes` says "copy
    it" on exactly this answer, so a strip that reformatted an untouched file
    would rewrite most of the adapter on every install."""
    text = f"# A skill\n\n{READER_COMMENT}\n\nA paragraph.\n"
    assert install.strip_declarations(text) == text


@pytest.mark.parametrize("kind", install.DECLARATION_KINDS)
def test_each_declaration_kind_is_removed(kind: str):
    """Parametrised over the constant, so a fourth kind added to
    `DECLARATION_KINDS` is covered here the moment it is named."""
    text = f"Before.\n\n<!-- {kind}: whatever it says -->\n\nAfter.\n"
    assert install.strip_declarations(text) == "Before.\n\nAfter.\n"


def test_a_block_between_two_paragraphs_leaves_one_blank_line():
    """The separation the block stood in is the separation that remains.

    Two blank lines would be a visible artefact in every delivered file, and
    none would run two paragraphs together — the failure that would reach a
    reader as one sentence continuing into another.
    """
    text = f"Before.\n\n{MULTILINE_BLOCK}\n\nAfter.\n"
    assert install.strip_declarations(text) == "Before.\n\nAfter.\n"


def test_a_block_at_the_top_of_a_file_leaves_no_leading_blank_line():
    """The shape `rules/aide-command-hygiene.md` is in: the `reach` block is
    the first thing in the file, and what follows it has to stay first."""
    text = f"{MULTILINE_BLOCK}\n\n# The rest.\n"
    assert install.strip_declarations(text) == "# The rest.\n"


def test_a_block_at_the_end_of_a_file_leaves_one_trailing_newline():
    """A block with no blank line under it takes its own newline, and the file
    still ends the way every other file the installer writes does."""
    text = f"A paragraph.\n\n{MULTILINE_BLOCK}\n"
    assert install.strip_declarations(text) == "A paragraph.\n"


def test_a_reader_comment_survives_beside_a_declaration():
    """The rule is about *test* declarations, not about HTML comments. A strip
    that could not tell the two apart would be a licence to delete anything a
    future author writes to the reader of a delivered file."""
    text = (f"Before.\n\n<!-- reach: validator -->\n\n{READER_COMMENT}\n\nAfter.\n")
    assert install.strip_declarations(text) == (
        f"Before.\n\n{READER_COMMENT}\n\nAfter.\n")


def test_an_inline_mention_of_a_declaration_is_not_a_block():
    """Prose naming the grammar is prose.

    A delivered file may one day say what a `<!-- pins:` block is, and a
    span-hungry pattern would run from that code span to the next `-->` in the
    file and delete the paragraphs in between. Only a declaration that *opens
    a line* is one, which is the only shape a delivered file writes; anything
    else fails `test_no_declaration_reaches_the_consumer` below rather than
    being guessed at.
    """
    text = "A block is written `<!-- pins:` then the sentences. <!-- ok -->\n"
    assert install.strip_declarations(text) == text


def test_an_indented_block_is_still_a_block():
    """Leading whitespace before the opener does not make it content — a file
    reformatted by an editor still gets stripped rather than shipping."""
    text = "Before.\n\n   <!-- triggers: none -->\n\nAfter.\n"
    assert install.strip_declarations(text) == "Before.\n\nAfter.\n"


def test_consecutive_blocks_go_together():
    """The delivered skills carry `reach`, `triggers` and one `pins` block per
    section, back to back. Non-greedy matching is what keeps the first block's
    `-->` from swallowing the ones below it."""
    text = ("---\nname: x\n---\n\n"
            "<!-- reach: validator -->\n\n"
            "<!-- triggers: none -->\n\n"
            f"{MULTILINE_BLOCK}\n\n"
            "# The body.\n")
    assert install.strip_declarations(text) == "---\nname: x\n---\n\n# The body.\n"


# --------------------------------------------------------------------------- #
# a real install — the same claims about the tree a consumer ends up with
#
# The framework is copied so a scratch control file can be added to it: the
# survival of a reader's comment is only worth asserting on a file the
# installer had no special knowledge of, and this repo ships none.
# --------------------------------------------------------------------------- #
SCRATCH_RULE = Path("rules") / "aide-scratch-declarations.md"

SCRATCH_TEXT = (
    "<!-- reach: all\n"
    "     A multi-line declaration, so the blank line below it has somewhere\n"
    "     to go wrong. -->\n"
    "\n"
    f"{READER_COMMENT}\n"
    "\n"
    "**A scratch rule.** Written by tests/test_install_strips_declarations.py.\n"
    "\n"
    f"{MULTILINE_BLOCK}\n"
    "\n"
    "The last paragraph.\n"
)

SCRATCH_INSTALLED = (
    f"{READER_COMMENT}\n"
    "\n"
    "**A scratch rule.** Written by tests/test_install_strips_declarations.py.\n"
    "\n"
    "The last paragraph.\n"
)


@pytest.fixture
def framework(tmp_path: Path, monkeypatch) -> Path:
    """A copy of `core/` and `adapters/`, with one scratch rule added."""
    root = tmp_path / "framework"
    root.mkdir()
    for name in ("core", "adapters"):
        shutil.copytree(FRAMEWORK_ROOT / name, root / name,
                        ignore=shutil.ignore_patterns("__pycache__", "tests"))
    scratch = root / "adapters" / install.DEFAULT_ADAPTER / SCRATCH_RULE
    scratch.write_text(SCRATCH_TEXT, encoding="utf-8")
    monkeypatch.setattr(install, "FRAMEWORK_ROOT", root)
    return root


@pytest.fixture
def target(tmp_path: Path) -> Path:
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    return consumer


def _install(target: Path, *args: str) -> int:
    return install.main(["--into", str(target), "--yes", "--git-mode", "local",
                         "--name", "Strip", *args])


def _installed_markdown(target: Path) -> list:
    """Every markdown control file an install wrote under `.claude/`."""
    claude = target / install.ADAPTER_INSTALL_DIR
    return sorted(path for name in install.ADAPTER_CONTROL
                  for path in (claude / name).rglob("*.md"))


def _text(path: Path) -> str:
    return path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")


def test_no_declaration_reaches_the_consumer(framework: Path, target: Path):
    """The rule itself, over the whole installed tree.

    The opener rather than the block: a declaration that survived because it
    was written in some other shape is still a declaration in a consumer's
    tree, and this is where that is said. `.aide/` is checked too — the engine
    writes no declarations today and this is what would notice if one appeared
    where no strip runs.
    """
    assert _install(target) == 0
    files = _installed_markdown(target) + sorted(
        (target / ".aide").rglob("*.md"))
    assert files, "nothing was installed — the layout moved"
    offenders = {path.name for path in files
                 if install.DECLARATION_OPENER.search(_text(path))}
    assert not offenders, (
        f"a `pins` / `reach` / `triggers` declaration reached the consumer in "
        f"{sorted(offenders)}. Those address this repository's test suite, "
        f"which a consumer does not install; see ADAPTER-SPEC's *Copies of "
        f"engine text* section, under *What an install ships*.")


def test_a_comment_written_for_the_reader_survives(framework: Path, target: Path):
    """The other direction, on a file the installer knows nothing about.

    Asserted as the whole installed text, so the blank lines are pinned with
    it: a multi-line block between two paragraphs leaves exactly the
    separation it stood in.
    """
    assert _install(target) == 0
    installed = target / install.ADAPTER_INSTALL_DIR / SCRATCH_RULE
    assert installed.is_file(), "the scratch rule never reached .claude/"
    assert _text(installed) == SCRATCH_INSTALLED


def test_no_installed_file_gained_a_double_blank_line(framework: Path,
                                                      target: Path):
    """The artefact a careless strip leaves, looked for across the tree.

    A run of three newlines is not illegal markdown, so this asserts a
    *difference*: no installed file has one its source did not. That way a
    file that legitimately holds one keeps it, and a gap opened by the strip
    fails wherever it appears.
    """
    assert _install(target) == 0
    run = re.compile(r"\n\n\n")
    gained = []
    for installed in _installed_markdown(target):
        tail = installed.relative_to(target / install.ADAPTER_INSTALL_DIR)
        source = framework / "adapters" / install.DEFAULT_ADAPTER / tail
        if not source.is_file():
            continue
        if len(run.findall(_text(installed))) > len(run.findall(_text(source))):
            gained.append(str(tail))
    assert not gained, (
        f"the strip left a blank line behind in {sorted(gained)} — a block "
        f"takes the blank line it stood on with it")


def test_an_update_over_a_stripped_install_reports_up_to_date(framework: Path,
                                                              target: Path):
    """Stripping must not read as drift.

    `--check` compares `.aide/VERSION`, the instruction-file import line and
    the manifest — never installed adapter bytes against source bytes — so a
    file that is deliberately not its source is invisible to it. That is a
    property of the checker worth pinning from this side: the day it grows a
    content comparison, every consumer starts being told it is behind on an
    install that is exactly current.
    """
    assert _install(target) == 0
    assert _install(target, "--check") == 0
    assert _install(target, "--update") == 0
    assert _install(target, "--check") == 0


def test_an_update_rewrites_nothing_when_the_source_is_unchanged(
        framework: Path, target: Path):
    """Idempotence, which is what makes a consumer's `git diff` after an
    `--update` the intended change and nothing else. A strip applied twice, or
    applied to its own output differently, would show up here as a file whose
    bytes moved with no edit behind them."""
    assert _install(target) == 0
    before = {path: path.read_bytes() for path in _installed_markdown(target)}
    assert _install(target, "--update") == 0
    after = {path: path.read_bytes() for path in _installed_markdown(target)}
    assert after == before
