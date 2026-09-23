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

#: An exact model ID — `claude-<family>` and then numeric segments only, so a
#: moving tag (`claude-opus-5-latest`) is no more an ID than one of the aliases
#: below, which the runtime is free to re-point between two installs of
#: the same framework version (issue #250). The family is what §2's tier binding
#: is read from: T3 -> opus, T2 -> sonnet.
_MODEL_ID = re.compile(r"^claude-(opus|sonnet|haiku)(?:-[0-9]+)+$")
_ALIASES = {"opus", "sonnet", "haiku", "fable", "inherit", "default", "best"}
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
    model = fm.get("model", "")
    assert model not in _ALIASES, (
        f"{path.name}: model={model!r} is an alias. An alias resolves to "
        f"whatever the runtime maps it to today, so one installed version would "
        f"stop meaning one model set — write the exact ID, here and in "
        f"ADAPTER-SPEC.md §2's cell.")
    assert _MODEL_ID.match(model), f"{path.name}: model={model!r}"
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

#: A Claude cell: one folded token per the spec's own example,
#: `claude-opus-5-5, xhigh` — the frontmatter's two values, as written there.
_CLAUDE_CELL = re.compile(r"^`([A-Za-z][A-Za-z0-9.\-]*),\s*([A-Za-z]+)`$")

#: The tier the row claims, read from the first `T<n>` token in its cell, so
#: builder's "**T2** (escalates to **T3** as `builder-escalation`)" reads as T2.
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
    exact = _MODEL_ID.match(model)
    assert exact, (
        f"{role}: §2's Claude cell says {model!r} — an exact model ID, never "
        f"an alias (issue #250)")
    assert exact.group(1) == _TIER_MODEL[tier], (
        f"{role}: §2 binds {tier}→{_TIER_MODEL[tier]}, but its Claude cell "
        f"says {model!r}")


def test_the_cell_parser_rejects_a_cell_that_is_not_a_binding():
    """The guard on the guard. If `_CLAUDE_CELL` ever loosened enough to match
    a tier or a rationale cell, `_table_rows` would read the wrong column and
    the comparisons above would fail for the wrong reason — or, worse, pass."""
    assert _CLAUDE_CELL.match("`claude-opus-5-5, xhigh`")
    assert _CLAUDE_CELL.match("`claude-haiku-4-5-20251001, low`")
    for not_a_binding in ("**T3 (strongest)**", "one plan cascades into ~10 items",
                          "`claude-opus-5-5`", "claude-opus-5-5, xhigh",
                          "`claude-opus-5-5, xhigh` (late retry)"):
        assert not _CLAUDE_CELL.match(not_a_binding), not_a_binding


def test_an_alias_is_not_a_model_id():
    """The guard on #250's guard: every alias the runtime resolves is refused
    by the ID pattern too, so a new alias missing from `_ALIASES` still fails —
    with the less helpful message, but it fails.

    The accepted examples carry the most specific ID a spec ships
    (`claude-opus-5-5`, issue #261), not its generation prefix: a shorter
    `claude-opus-5` may be underspecified and resolve dynamically on the
    provider's side, and a more specific ID can behave differently from it,
    so the fixtures show the shape a move should land on. `claude-sonnet-5`
    stays accepted because a shipped spec still names it."""
    for alias in sorted(_ALIASES) + ["claude-opus", "opus-5", "claude-opus-latest",
                                     "claude-opus-5-latest", "claude-sonnet-5[1m]",
                                     "Claude-Opus-5"]:
        assert not _MODEL_ID.match(alias), alias
    for exact in ("claude-opus-5-5", "claude-sonnet-5", "claude-opus-4-8",
                  "claude-haiku-4-5-20251001"):
        assert _MODEL_ID.match(exact), exact


# --------------------------------------------------------------------------- #
# the escalated builder is the builder, byte for byte (#264)
# --------------------------------------------------------------------------- #
#: The one agent spec that is a copy of another. `builder-escalation` is the
#: builder role on T3: a model pinned per role can only come from frontmatter
#: (the per-dispatch `model` override takes aliases only), so the step-up is a
#: second definition — and nothing about it but the frontmatter may differ.
#: Registered by a byte comparison, which ADAPTER-SPEC's *Copies of engine
#: text* names beside the quote-pins: stricter than rung 3's normalised quotes,
#: since the whole body is held with no tolerance at all. It is held here because the copy's reader, the spawn, receives
#: the body whole, and a declaration in it would be one more thing to keep
#: identical. Install-time generation (rung 2) was not taken: the installer
#: generates *section cores*, and a second grammar for one adapter file buys
#: nothing a byte comparison in the suite does not.
_ESCALATION = {"builder-escalation": "builder"}

#: The frontmatter keys an escalated copy exists to change. Any other key —
#: `effort`, a `tools:` or `skills:` list added later — must match its
#: original, so a preload or a tool grant reaches both tiers of the role.
_ESCALATION_MAY_DIFFER = {"name", "description", "model"}


@pytest.mark.parametrize("copy, original", sorted(_ESCALATION.items()))
def test_an_escalated_spec_is_its_originals_body_byte_for_byte(copy, original):
    copy_path, original_path = _AGENTS_DIR / f"{copy}.md", _AGENTS_DIR / f"{original}.md"
    assert copy_path.is_file() and original_path.is_file(), (copy_path, original_path)
    assert _split(copy_path)[1] == _split(original_path)[1], (
        f"agents/{copy}.md's body differs from agents/{original}.md's. The "
        f"escalation is the same role on a stronger model — edit both bodies, "
        f"in one commit, so they stay identical.")


@pytest.mark.parametrize("copy, original", sorted(_ESCALATION.items()))
def test_an_escalated_spec_changes_only_its_name_description_and_model(copy, original):
    copied = _frontmatter(_AGENTS_DIR / f"{copy}.md")
    source = _frontmatter(_AGENTS_DIR / f"{original}.md")
    for key in (set(copied) | set(source)) - _ESCALATION_MAY_DIFFER:
        assert copied.get(key) == source.get(key), (
            f"agents/{copy}.md: {key}={copied.get(key)!r} but agents/{original}.md "
            f"says {source.get(key)!r} — only {sorted(_ESCALATION_MAY_DIFFER)} "
            f"may differ between the two tiers of one role")
    assert copied.get("model") != source.get("model"), (
        f"agents/{copy}.md runs on the same model as agents/{original}.md, so "
        f"escalating to it steps up nothing")


def test_the_escalation_register_names_every_copy_the_tree_holds():
    """The guard on the guard: a spec whose body equals another's is a copy
    the byte check must know about, or a later edit to one of them drifts."""
    bodies: dict = {}
    for path in _AGENT_FILES:
        bodies.setdefault(_split(path)[1], []).append(path.stem)
    shared = sorted(tuple(sorted(stems)) for stems in bodies.values() if len(stems) > 1)
    expected = sorted(tuple(sorted(pair)) for pair in _ESCALATION.items())
    assert shared == expected, shared


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
