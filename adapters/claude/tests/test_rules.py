"""`.claude/rules/` — the adapter's delivery mechanism for the shared contract.

ADAPTER-SPEC §7 makes three properties conformant rather than decorative: a
delivered section loads without the role choosing to, names the section it
delivers, and adds no rule the engine does not have. The first is structural
(an unscoped rule loads everywhere; a `paths:` one loads on a match), and these
tests pin the parts a commit can silently break: that the files ship at all,
that their frontmatter is well-formed, that each still names its section, and
that the restatements this mechanism replaced stay retired.

Nothing else in the suite reads these files. Stdlib + pytest only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_ADAPTER = Path(__file__).resolve().parents[1]
_RULES_DIR = _ADAPTER / "rules"
_AGENTS_DIR = _ADAPTER / "agents"
_CORE = _ADAPTER.parents[1] / "core"

_RULE_FILES = sorted(_RULES_DIR.glob("*.md"))

FRAMEWORK_ROOT = _ADAPTER.parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)


#: Rules that MUST carry `paths:`. Named, because the frontmatter check below
#: can only verify the keys of a block that parses — a file whose delimiter
#: stopped being recognised has no keys to be wrong, and the runtime reads it
#: as an unscoped rule loaded into every context. That is the failure this
#: whole file exists to catch, and it cannot be caught by inspection alone.
_MUST_BE_SCOPED = ("aide-test-hygiene.md", "aide-living-documents.md")


def _split(path: Path) -> tuple:
    """``(frontmatter_or_None, body)``. A rule may legitimately have neither.

    Reads with `utf-8-sig` and normalises CRLF before looking for the
    delimiter. A BOM from a Windows editor, or CRLF line endings, would
    otherwise make `startswith("---\n")` false — and this helper would report a
    scoped rule as an unscoped one with a clean bill of health.
    """
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    assert end != -1, f"{path.name}: unterminated frontmatter block"
    return text[4:end], text[end + 5:]


@pytest.mark.parametrize("name", _MUST_BE_SCOPED)
def test_a_rule_that_must_be_scoped_still_parses_as_scoped(name: str):
    """Fails closed. `test_frontmatter_...` returns early on a block it cannot
    read, so without this an unparseable delimiter is indistinguishable from a
    deliberate unscoped rule — and costs ~560 tokens on every spawn, silently.
    """
    path = _RULES_DIR / name
    assert path.is_file(), f"{name} is gone; the scoping guarantee went with it"
    raw = path.read_bytes()
    assert raw.startswith(b"---"), f"{name}: no frontmatter delimiter at byte 0"
    block, _ = _split(path)
    assert block is not None and "paths:" in block, f"{name}: lost its `paths:`"


def test_the_adapter_ships_rules():
    assert _RULE_FILES, "no rules/*.md found — the glob or the layout moved"


def test_the_installer_copies_the_rules_directory():
    """A rule that never reaches `.claude/` is a rule that binds nobody.

    `ADAPTER_CONTROL` is the whole list the installer walks, so omitting
    `rules` ships the files in this repo and nothing to a consumer.
    """
    assert "rules" in install.ADAPTER_CONTROL


@pytest.mark.parametrize("path", _RULE_FILES, ids=lambda p: p.name)
def test_body_is_not_empty(path: Path):
    _, body = _split(path)
    assert body.strip(), f"{path.name}: frontmatter but no rule"


@pytest.mark.parametrize("path", _RULE_FILES, ids=lambda p: p.name)
def test_frontmatter_declares_only_paths_and_declares_it_well(path: Path):
    """`paths:` is the one key that changes WHEN a rule loads.

    An unrecognised key is not an error to the runtime — it is ignored — so a
    typo'd `path:` silently turns a scoped rule into one that loads in every
    context, which is the opposite of the intent and costs on every spawn.
    """
    block, _ = _split(path)
    if block is None:
        return
    keys = [line.split(":", 1)[0] for line in block.splitlines()
            if line and not line[0].isspace() and ":" in line]
    assert keys == ["paths"], f"{path.name}: unexpected frontmatter keys {keys}"

    globs = [line.strip().lstrip("- ").strip('"\'')
             for line in block.splitlines() if line.strip().startswith("- ")]
    assert globs, f"{path.name}: `paths:` with no glob matches nothing"
    for glob in globs:
        assert not glob.startswith("/"), f"{path.name}: {glob!r} is not repo-relative"


@pytest.mark.parametrize("path", _RULE_FILES, ids=lambda p: p.name)
def test_each_rule_names_the_section_it_delivers(path: Path):
    """The engine section is the source of truth; the rule is a restatement.

    A reader who cannot tell which copy wins has to guess, and the copy in
    front of them is the one they will guess.
    """
    _, body = _split(path)
    assert "conventions.md" in body, f"{path.name}: names no source section"
    assert re.search(r"§\d", body), f"{path.name}: names no section number"


@pytest.mark.parametrize("section", ["3", "6"])
def test_the_two_contract_sections_are_delivered(section: str):
    """ADAPTER-SPEC §7 names §3 and §6 specifically, and both sections say so.

    Losing one is not a syntax error anywhere: the rule file simply stops
    existing and every role carries on with no hygiene contract in context.
    """
    delivering = [p for p in _RULE_FILES if f"§{section}" in p.read_text(encoding="utf-8")]
    assert delivering, f"no rule delivers conventions.md §{section}"


@pytest.mark.parametrize("section", ["3", "6"])
def test_the_engine_section_still_asks_to_be_delivered(section: str):
    """The other half of the contract, in the engine, where it is runtime-general.

    If the section stops requiring delivery, the rule above is an adapter
    inventing its own obligation — the coupling `core/` exists to prevent.
    """
    matches = list((_CORE / "conventions").glob(f"{section}-*.md"))
    assert len(matches) == 1, f"expected one §{section} file, got {matches}"
    assert "**delivers**" in matches[0].read_text(encoding="utf-8")


@pytest.mark.parametrize("path", sorted(_AGENTS_DIR.glob("*.md")), ids=lambda p: p.name)
def test_no_agent_re_inlines_the_command_hygiene_block(path: Path):
    """The restatement this mechanism replaced, in the six specs that carried it.

    It was verbatim in all six and drifted anyway — `spec-reviewer` had lost the
    commit-substitution rule. A re-inlined copy is how that starts again.
    """
    body = path.read_text(encoding="utf-8")
    assert "## Command hygiene" not in body, (
        f"{path.name}: command hygiene is delivered by "
        f"rules/aide-command-hygiene.md, not restated per agent")
