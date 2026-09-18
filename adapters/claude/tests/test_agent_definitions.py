"""Every `agents/*.md` is a well-formed Claude Code sub-agent definition.

Agent files are discovered by filename and dispatched by the `name:` in their
frontmatter, so a typo in either is not a syntax error anywhere — it is an agent
that silently never runs, or runs under a name no orchestrator invokes. Nothing
else in the suite reads these files, so this is the only guard on them.

It also holds the **Claude column of `ADAPTER-SPEC.md` §2's role table** to
those same frontmatter blocks, in both directions (issue #156). That table is a
copy of the specs' `model:`/`effort:` — rung 3 of ADAPTER-SPEC's *Copies of
engine text*, quote-pinned — and its reader opens the spec interactively, so by
the placement criterion the pins live here rather than in a comment on the
table, the same placement as `tests/test_floor_pins.py`. Only the Claude column
is held: the tier and the "why" are the cross-adapter abstraction, not a second
copy of anything, and a reason is `Rationale` material a pin does not reach.

The parser is deliberately loud. A renamed heading or a reshaped table would
otherwise yield zero rows and pass every comparison below vacuously, which is
the silently-green shape the framework exists to catch.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
_ADAPTER_SPEC = Path(__file__).resolve().parents[2] / "ADAPTER-SPEC.md"

# The tiers the adapter README binds: T3 -> opus, T2 -> sonnet.
_MODELS = {"opus", "sonnet", "haiku"}
_EFFORTS = {"low", "medium", "high", "xhigh", "max"}

_AGENT_FILES = sorted(_AGENTS_DIR.glob("*.md"))


def _split(path: Path) -> tuple:
    """``(frontmatter_block, body)``, both validated.

    Every caller goes through here so none can slice on an unchecked
    ``find()``: a missing terminator returns -1, and ``text[-1 + 5:]`` is
    ``text[4:]`` — the frontmatter itself. A body assertion against *that* is
    non-empty and passes, reporting success while looking at the wrong text.
    """
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name}: no frontmatter block"
    end = text.find("\n---\n", 4)
    assert end != -1, f"{path.name}: unterminated frontmatter block"
    return text[4:end], text[end + 5:]


def _frontmatter(path: Path) -> dict:
    """The YAML-ish frontmatter as a flat dict.

    Deliberately a tiny hand parser rather than a PyYAML dependency: the suite
    is stdlib + pytest only (CLAUDE.md), and these files use one nesting level
    plus folded `>-` blocks.
    """
    block, _ = _split(path)

    data: dict = {}
    key = None
    for line in block.splitlines():
        if line and not line[0].isspace() and ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            data[key] = value.strip()
        elif key is not None and line.strip():
            data[key] = (data[key] + " " + line.strip()).strip()
    return data


def test_there_are_agent_files():
    assert _AGENT_FILES, "no agents/*.md found — the glob or the layout moved"


@pytest.mark.parametrize("path", _AGENT_FILES, ids=lambda p: p.stem)
def test_name_matches_filename(path: Path):
    """Dispatch is by `name:`; discovery is by filename. If they disagree the
    agent is invocable under a name no orchestrator ever writes."""
    assert _frontmatter(path).get("name") == path.stem


@pytest.mark.parametrize("path", _AGENT_FILES, ids=lambda p: p.stem)
def test_description_is_present_and_substantial(path: Path):
    """The description is what the orchestrator routes on — an empty or stub
    one makes the agent effectively unselectable."""
    description = _frontmatter(path).get("description", "")
    assert description.replace(">-", "").strip(), f"{path.name}: empty description"
    assert len(description) > 40, f"{path.name}: description too thin to route on"


@pytest.mark.parametrize("path", _AGENT_FILES, ids=lambda p: p.stem)
def test_model_and_effort_are_recognised(path: Path):
    fm = _frontmatter(path)
    assert fm.get("model") in _MODELS, f"{path.name}: model={fm.get('model')!r}"
    assert fm.get("effort") in _EFFORTS, f"{path.name}: effort={fm.get('effort')!r}"


@pytest.mark.parametrize("path", _AGENT_FILES, ids=lambda p: p.stem)
def test_body_is_not_empty(path: Path):
    _, body = _split(path)
    assert body.strip(), f"{path.name}: frontmatter but no instructions"


def test_split_rejects_an_unterminated_frontmatter(tmp_path: Path):
    """The guard on the guard. Without it this module's body check passes on a
    malformed file — `find()` returns -1, the slice yields the frontmatter, and
    a non-empty assertion against that reports success while reading the wrong
    text. Same silently-green shape the framework exists to catch."""
    broken = tmp_path / "broken.md"
    broken.write_text("---\nname: broken\nmodel: opus\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="unterminated"):
        _split(broken)


def test_split_rejects_a_file_with_no_frontmatter(tmp_path: Path):
    plain = tmp_path / "plain.md"
    plain.write_text("# Just a document\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="no frontmatter"):
        _split(plain)


# --------------------------------------------------------------------------- #
# ADAPTER-SPEC §2's Claude column, pinned to the frontmatter both ways (#156)
# --------------------------------------------------------------------------- #
#: The §2 heading, and the next `## ` that ends the section.
_SECTION_2 = re.compile(r"^## 2\. .*$", re.M)
_NEXT_SECTION = re.compile(r"^## ", re.M)

#: A Claude cell: one folded token per the spec's own example, `Opus, xhigh`.
#: Case-insensitive on the model because the table writes it as prose
#: (`Opus`) and the frontmatter as a value (`opus`).
_CLAUDE_CELL = re.compile(r"^`([A-Za-z]+),\s*([A-Za-z]+)`$")

#: The tier the row claims, read from the first `T<n>` token in its cell, so
#: builder's "**T2** (may escalate to **T3** on a late retry)" reads as T2.
_TIER = re.compile(r"T([0-9])")

#: The binding §2 states in prose, and the only one this adapter expresses.
_TIER_MODEL = {"T3": "opus", "T2": "sonnet"}


def _spec_section_2() -> str:
    text = _ADAPTER_SPEC.read_text(encoding="utf-8")
    start = _SECTION_2.search(text)
    assert start is not None, (
        f"{_ADAPTER_SPEC.name}: no `## 2. ` heading — the role table's section "
        f"was renamed or renumbered, and this module would otherwise compare "
        f"nothing at all")
    end = _NEXT_SECTION.search(text, start.end())
    return text[start.end():end.start() if end else len(text)]


def _table_rows() -> dict:
    """`role -> (model, effort, tier)` for every §2 row with a Claude cell."""
    rows: dict = {}
    for line in _spec_section_2().splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        bound = [(i, m) for i, cell in enumerate(cells)
                 if (m := _CLAUDE_CELL.match(cell))]
        if not bound:
            continue
        index, match = bound[0]
        role = cells[0].strip("*` ")
        assert role not in rows, f"{role}: two rows in §2's tables"
        tier = _TIER.search(cells[1]) if index > 1 else None
        rows[role] = (match.group(1).lower(), match.group(2).lower(),
                      f"T{tier.group(1)}" if tier else None)
    return rows


_TABLE_ROWS = _table_rows()


def test_the_role_table_was_actually_parsed():
    """§6: a derived value is recognisable before anything is asserted about
    it. A reshaped table yields `{}`, and every comparison below then passes
    while checking nothing."""
    assert len(_TABLE_ROWS) >= len(_AGENT_FILES), (
        f"parsed {len(_TABLE_ROWS)} Claude cells out of {_ADAPTER_SPEC.name} "
        f"§2 for {len(_AGENT_FILES)} agent specs: {sorted(_TABLE_ROWS)}")


@pytest.mark.parametrize("path", _AGENT_FILES, ids=lambda p: p.stem)
def test_every_agent_spec_has_a_row_that_matches_its_frontmatter(path: Path):
    """A spec silently retiered — or given a different effort — used to fail
    nothing. Role names are contractual across adapters (§2 names them), so a
    spec absent from the table is a missing row, never an exemption."""
    fm = _frontmatter(path)
    assert path.stem in _TABLE_ROWS, (
        f"{path.name}: no row in {_ADAPTER_SPEC.name} §2. Add one — role names "
        f"are contractual, and the table is where the routing decision is "
        f"recorded for every adapter.")
    model, effort, _ = _TABLE_ROWS[path.stem]
    assert (model, effort) == (fm.get("model"), fm.get("effort")), (
        f"{path.name}: frontmatter says "
        f"{fm.get('model')!r}/{fm.get('effort')!r} but {_ADAPTER_SPEC.name} §2 "
        f"says {model!r}/{effort!r} — edit both, in one commit.")


@pytest.mark.parametrize("role", sorted(_TABLE_ROWS), ids=lambda r: r)
def test_every_row_in_the_table_has_an_agent_spec(role: str):
    """The other direction: a row for a role this adapter does not ship is a
    binding nothing honours."""
    assert (_AGENTS_DIR / f"{role}.md").is_file(), (
        f"{_ADAPTER_SPEC.name} §2 binds {role!r} to a Claude model, but "
        f"agents/{role}.md does not exist — drop the cell, or add the spec.")


@pytest.mark.parametrize("role", sorted(_TABLE_ROWS), ids=lambda r: r)
def test_the_tier_binding_is_the_one_the_section_states(role: str):
    """§2's prose binds **T3→Opus, T2→Sonnet**. A row whose tier and model
    disagree makes the prose and the table two different contracts."""
    model, _, tier = _TABLE_ROWS[role]
    assert tier in _TIER_MODEL, f"{role}: no T2/T3 tier cell beside its Claude cell"
    assert model == _TIER_MODEL[tier], (
        f"{role}: §2 binds {tier}→{_TIER_MODEL[tier]}, but its Claude cell "
        f"says {model!r}")


def test_the_cell_parser_rejects_a_cell_that_is_not_a_binding():
    """The guard on the guard. If `_CLAUDE_CELL` ever loosened enough to match
    a tier or a rationale cell, `_table_rows` would read the wrong column and
    the comparisons above would fail for the wrong reason — or, worse, pass."""
    assert _CLAUDE_CELL.match("`Opus, xhigh`")
    for not_a_binding in ("**T3 (strongest)**", "one plan cascades into ~10 items",
                          "`Opus`", "Opus, xhigh", "`Opus, xhigh` (late retry)"):
        assert not _CLAUDE_CELL.match(not_a_binding), not_a_binding


# --------------------------------------------------------------------------- #
# the shipped rationale stays retired (#156)
# --------------------------------------------------------------------------- #
_MODEL_EFFORT = re.compile(r"^(?:#{1,6}[ \t]*|\*\*)Model\s*(?:&|and)\s*effort",
                           re.M | re.I)


def test_the_retirement_guard_reads_both_spellings_of_the_opener():
    for opener in ("**Model & effort.** Sonnet", "## Model and effort",
                   "**model and effort.**"):
        assert _MODEL_EFFORT.search(opener), opener
    assert not _MODEL_EFFORT.search("the model and effort live in §2")


@pytest.mark.parametrize("path", _AGENT_FILES, ids=lambda p: p.stem)
def test_no_agent_spec_argues_for_its_own_model(path: Path):
    """The restatement retired in 1.59.1.

    Four specs carried a `**Model & effort.**` paragraph, and an agent spec
    body *is* the sub-agent's system prompt — so every spawn of those roles
    paid for an argument about a choice the agent cannot change. The reason now
    has one home, `ADAPTER-SPEC.md` §2's role table, where it is beside the
    other six roles' and cannot drift from the frontmatter. Guarded on the
    opener rather than the prose, the same shape as the command-hygiene block
    and the `## Hand-off` tail in `test_rules.py`: a reworded justification
    under the same lead-in would re-open the cost.
    """
    _, body = _split(path)
    assert not _MODEL_EFFORT.search(body), (
        f"{path.name}: opens a `Model & effort` block. The tier, the model, "
        f"the effort and the reason for each live in ADAPTER-SPEC.md §2's "
        f"table; a role cannot act on them.")
