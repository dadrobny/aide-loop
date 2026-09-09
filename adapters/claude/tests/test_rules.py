"""The adapter's delivery mechanism for the shared contract: the **delivered
files** — `.claude/rules/*.md` and the **section skills** under
`.claude/skills/<name>/SKILL.md`.

ADAPTER-SPEC §7 makes three properties conformant rather than decorative: a
delivered section loads without the role choosing to, names the section it
delivers, and adds no rule the engine does not have. The first is structural,
and it has two carriers here. An unscoped **rule** loads into every context.
A **section skill** (`user-invocable: false`, carrying `<!-- pins: … -->`) is
preloaded into exactly the agent specs whose `skills:` frontmatter names it —
at spawn, before the role has opened anything. Its `paths:` do not inject
anything on a read (issue #85, measured): the one-line description is in an
interactive session's listing regardless, and the globs only narrow when the
runtime auto-invokes the skill on its own — which is why the description is
written as a trigger.

These tests pin the parts a commit can silently break: that the files ship at
all, that their frontmatter is well-formed — a skill that loses `name:` cannot
be preloaded and is not listed, and one that sets
`disable-model-invocation: true` is skipped at preload with a debug-log
warning only — that each still names its section, that every preload names a
skill that exists and every section skill is preloaded by someone, and that
the restatements this mechanism replaced stay retired.

A section skill is recognised **structurally** — `user-invocable: false`, the
key that hides it from the `/` menu while leaving it preloadable — never by a
name list, so the next one is covered the moment it lands. A `<!-- pins:` block
is not that signal: a workflow skill may quote the contract it acts on, and
`test_rule_pins.py` holds it to the quote either way. What keeps the key and
the preload channel from coming apart is asserted from the preload side
instead. Stdlib + pytest only.
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
_SKILL_FILES = sorted((_ADAPTER / "skills").glob("*/SKILL.md"))
_AGENT_FILES = sorted(_AGENTS_DIR.glob("*.md"))

FRAMEWORK_ROOT = _ADAPTER.parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
sys.path.insert(0, str(FRAMEWORK_ROOT / "tests"))
import install  # noqa: E402  (path shim above)
from _delivered import (STRIPS_BOM, glob_list, keys as _keys,  # noqa: E402
                        label as _label, scalar as _scalar)


#: This module reads the adapter's **source** tree, where a BOM in front of a
#: `---` is an authoring accident to report on rather than a runtime's view of
#: the file — so the reader that strips it. `tests/_delivered.py` holds the
#: whole parser set and the reasoning for the other choice;
#: `tests/test_structural_budget.py` is the caller that makes it.
_split = STRIPS_BOM.split
_is_section_skill = STRIPS_BOM.is_section_skill
_preloads = STRIPS_BOM.preloads

_SECTION_SKILLS = [p for p in _SKILL_FILES if _is_section_skill(p)]
_WORKFLOW_SKILLS = [p for p in _SKILL_FILES if p not in _SECTION_SKILLS]

#: Every file that delivers a contract section: the rules, and the section
#: skills. The tests that pin "delivered files" range over this list.
_DELIVERED = _RULE_FILES + _SECTION_SKILLS


# --------------------------------------------------------------------------- #
# fail closed — the derived sets are recognisable before anything is asserted
# --------------------------------------------------------------------------- #
def test_the_adapter_ships_rules():
    assert _RULE_FILES, "no rules/*.md found — the glob or the layout moved"


def test_the_adapter_ships_section_skills():
    """conventions.md §6: the derived set must be recognisable first. An empty
    one makes every parametrised test below vanish with a green suite."""
    assert _SKILL_FILES, "no skills/*/SKILL.md found — the glob or the layout moved"
    assert _SECTION_SKILLS, ("no section skill recognised — none carries "
                             "`user-invocable: false`")
    assert _WORKFLOW_SKILLS, "every skill reads as a section skill — the signal broke"


def test_the_installer_copies_the_delivering_directories():
    """A delivered file that never reaches `.claude/` binds nobody.

    `ADAPTER_CONTROL` is the whole list the installer walks, so omitting
    `rules` or `skills` ships the files in this repo and nothing to a consumer.
    """
    assert "rules" in install.ADAPTER_CONTROL
    assert "skills" in install.ADAPTER_CONTROL


# --------------------------------------------------------------------------- #
# the envelope — frontmatter and body of every delivered file
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path", _SECTION_SKILLS, ids=_label)
def test_a_section_skill_still_parses_as_a_scoped_skill(path: Path):
    """Fails closed. `test_a_section_skills_frontmatter_...` can only check
    the keys of a block that parses, so without this an unparseable delimiter
    is indistinguishable from a file that never had one. For a skill that is
    not "arms everywhere" — it is worse in the other direction: with no
    readable `name:` the runtime cannot preload it and does not list it, so
    the section reaches nobody at all.
    """
    raw = path.read_bytes()
    assert raw.startswith(b"---"), f"{_label(path)}: no frontmatter delimiter at byte 0"
    block, _ = _split(path)
    assert block is not None, f"{_label(path)}: frontmatter does not parse"
    assert "paths:" in block, (
        f"{_label(path)}: lost its `paths:` — without them the runtime may "
        f"auto-invoke this section for any work at all; the globs keep it to "
        f"matching files (the listing shows the description regardless)")


@pytest.mark.parametrize("path", _DELIVERED, ids=_label)
def test_body_is_not_empty(path: Path):
    _, body = _split(path)
    assert body.strip(), f"{_label(path)}: frontmatter but no rule"


def _assert_globs_are_well_formed(path: Path, block: str) -> None:
    globs = glob_list(block)
    assert globs, f"{_label(path)}: `paths:` with no glob matches nothing"
    for glob in globs:
        assert not glob.startswith("/"), f"{_label(path)}: {glob!r} is not repo-relative"


@pytest.mark.parametrize("path", _RULE_FILES, ids=_label)
def test_a_rules_frontmatter_declares_only_paths_and_declares_it_well(path: Path):
    """`paths:` is the one key that changes WHEN a rule loads.

    An unrecognised key is not an error to the runtime — it is ignored — so a
    typo'd `path:` silently turns a scoped rule into one that loads in every
    context, which is the opposite of the intent and costs on every spawn.
    """
    block, body = _split(path)
    if block is None:
        # No readable block. Two ways to get here and they are not the same
        # mistake, so name the broken one before the legitimate one: a block
        # that is opened and never closed reads to the runtime as no
        # frontmatter at all, and would otherwise be reported below as a rule
        # missing its `<!-- reach:` line.
        assert not path.read_bytes().lstrip().startswith(b"---"), (
            f"{path.name}: opens a frontmatter block that is never closed — "
            f"the runtime finds no `paths:` and loads it into every context")
        # The unscoped case — today the only shipped rule. Nothing about
        # `paths:` to check, so assert what an unscoped rule must be instead:
        # it opens with its reach declaration, the one thing that says it is
        # unscoped on purpose rather than a scoped rule that lost its block.
        assert body.lstrip().startswith("<!-- reach:"), (
            f"{path.name}: no frontmatter and no leading `<!-- reach:` — an "
            f"unscoped rule declares it is unscoped on purpose")
        return
    keys = _keys(block)
    assert keys == ["paths"], f"{path.name}: unexpected frontmatter keys {keys}"
    _assert_globs_are_well_formed(path, block)


#: The frontmatter a section skill carries — exactly these, no more. `name` is
#: what a `skills:` preload resolves; `description` is the whole interactive
#: delivery; `user-invocable: false` keeps it out of the `/` menu while
#: leaving it preloadable; `paths` is the interactive trigger.
_SECTION_SKILL_KEYS = ["name", "description", "user-invocable", "paths"]

#: The runtime caps a description at 1,536 characters and the whole listing
#: at 1% of the context window, shared by every skill a consumer has. A
#: trigger is one sentence; well under that keeps the listing cheap.
_DESCRIPTION_CAP = 300


@pytest.mark.parametrize("path", _SECTION_SKILLS, ids=_label)
def test_a_section_skills_frontmatter_is_exactly_what_a_preload_needs(path: Path):
    """The keys that make a section skill preloadable, hidden, and listed.

    `disable-model-invocation: true` is the one that would look right and be
    fatal: the runtime skips such a skill at preload with a debug-log warning
    only, so the section would silently reach nobody. `user-invocable: false`
    is the key that hides it from the `/` menu and keeps it preloadable.
    """
    block, _ = _split(path)
    assert block is not None, f"{_label(path)}: no frontmatter"
    keys = _keys(block)
    assert sorted(keys) == sorted(_SECTION_SKILL_KEYS), (
        f"{_label(path)}: frontmatter keys {keys}, expected exactly "
        f"{_SECTION_SKILL_KEYS}")
    assert _scalar(block, "name") == path.parent.name, (
        f"{_label(path)}: `name:` must equal the directory — a preload resolves "
        f"the name, discovery the directory")
    assert (_scalar(block, "user-invocable") or "").lower() == "false", (
        f"{_label(path)}: a section skill is `user-invocable: false` — hidden "
        f"from the `/` menu, still preloadable")
    description = _scalar(block, "description") or ""
    assert len(description) > 40, f"{_label(path)}: description too thin to trigger on"
    assert len(description) <= _DESCRIPTION_CAP, (
        f"{_label(path)}: description is {len(description)} characters; the "
        f"listing is the whole interactive delivery and is budgeted")
    assert re.search(r"§\d", description), (
        f"{_label(path)}: the description names no section — it is the only "
        f"thing an interactive session sees, so it says what it delivers")
    _assert_globs_are_well_formed(path, block)


@pytest.mark.parametrize("path", _DELIVERED, ids=_label)
def test_each_delivered_file_names_the_section_it_delivers(path: Path):
    """The engine section is the source of truth; the delivered copy is a
    restatement.

    A reader who cannot tell which copy wins has to guess, and the copy in
    front of them is the one they will guess.
    """
    _, body = _split(path)
    assert "conventions.md" in body, f"{_label(path)}: names no source section"
    assert re.search(r"§\d", body), f"{_label(path)}: names no section number"


#: The sections ADAPTER-SPEC §7 names as delivered, each of which says so in
#: its own text. §9 joined them in 1.40.0 (issue #150).
_DELIVERED_SECTIONS = ["3", "6", "9"]


@pytest.mark.parametrize("section", _DELIVERED_SECTIONS)
def test_each_named_contract_section_is_delivered(section: str):
    """ADAPTER-SPEC §7 names §3, §6 and §9 specifically, and each says so.

    Losing one is not a syntax error anywhere: the delivered file simply stops
    existing and every role carries on with no contract in context.
    """
    delivering = [p for p in _DELIVERED if f"§{section}" in _split(p)[1]]
    assert delivering, f"no delivered file carries conventions.md §{section}"


@pytest.mark.parametrize("section", _DELIVERED_SECTIONS)
def test_the_engine_section_still_asks_to_be_delivered(section: str):
    """The other half of the contract, in the engine, where it is runtime-general.

    If the section stops requiring delivery, the delivered file above is an
    adapter inventing its own obligation — the coupling `core/` exists to
    prevent.
    """
    matches = list((_CORE / "conventions").glob(f"{section}-*.md"))
    assert len(matches) == 1, f"expected one §{section} file, got {matches}"
    assert "**delivers**" in matches[0].read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# the preload — the channel that makes a section skill a delivery
# --------------------------------------------------------------------------- #
def test_some_agent_preloads_a_skill():
    """Fails closed for the two tests below, which range over the preloads."""
    assert _AGENT_FILES, "no agents/*.md found — the glob or the layout moved"
    assert any(_preloads(agent) for agent in _AGENT_FILES), (
        "no agent spec carries `skills:` — the preload channel is gone, or the "
        "frontmatter parser here stopped seeing it")


@pytest.mark.parametrize("agent", _AGENT_FILES, ids=lambda p: p.stem)
def test_every_skill_an_agent_preloads_exists_and_can_be_preloaded(agent: Path):
    """A `skills:` entry is resolved by name at spawn, and a name that resolves
    to nothing — or to a skill the runtime refuses to preload — is not an
    error anywhere: the role starts without it, and nothing says so.
    """
    for name in _preloads(agent):
        skill = _ADAPTER / "skills" / name / "SKILL.md"
        assert skill.is_file(), (
            f"{agent.name}: preloads `{name}`, and skills/{name}/SKILL.md does "
            f"not exist — the role spawns without it, silently")
        block, _ = _split(skill)
        assert block is not None, f"{name}: no frontmatter, so no `name:` to resolve"
        assert _scalar(block, "name") == name, (
            f"{name}: SKILL.md declares name {_scalar(block, 'name')!r}")
        assert (_scalar(block, "disable-model-invocation") or "").lower() != "true", (
            f"{agent.name}: preloads `{name}`, which sets "
            f"`disable-model-invocation: true` — the runtime skips it at "
            f"preload with a debug-log warning only")


@pytest.mark.parametrize("agent", _AGENT_FILES, ids=lambda p: p.stem)
def test_every_skill_an_agent_preloads_is_a_section_skill(agent: Path):
    """The other half of the recognition, come at from the preload side.

    Since 1.42.0 a section skill is recognised by `user-invocable: false`
    alone, so a spec that loses that key would simply drop out of
    `_SECTION_SKILLS` and stop being checked as one — no failure, and a
    section delivered by a file nothing holds to a section skill's rules. A
    preload is the thing only a section skill has, so requiring every
    preloaded skill to carry the key closes that: the key and the channel
    cannot come apart in silence.

    It also catches the mirror mistake — preloading a workflow skill, which
    pays its whole body on every spawn of that role for something the role
    was going to invoke by name anyway.
    """
    for name in _preloads(agent):
        skill = _ADAPTER / "skills" / name / "SKILL.md"
        if not skill.is_file():
            continue  # named by the test above, which fails on it
        block, _ = _split(skill)
        assert (_scalar(block, "user-invocable") or "").lower() == "false", (
            f"{agent.name}: preloads `{name}`, which is not `user-invocable: "
            f"false` — either it is a section skill that lost the key (add it "
            f"back; nothing else classes it as one) or it is a workflow skill "
            f"being paid for on every spawn of this role")


@pytest.mark.parametrize("path", _SECTION_SKILLS, ids=_label)
def test_every_section_skill_is_preloaded_by_at_least_one_agent(path: Path):
    """A section skill nobody preloads is a pointer wearing a skill's name.

    Its `paths:` inject nothing on a read (issue #85) and a sub-agent's
    startup context has no skill catalogue, so without a `skills:` entry the
    section reaches no role at all — the 3% pointer, at a new address.
    """
    name = path.parent.name
    preloaded_by = [agent.stem for agent in _AGENT_FILES if name in _preloads(agent)]
    assert preloaded_by, (
        f"{name}: no agent spec names it in `skills:` — a section skill nobody "
        f"preloads delivers nothing to the loop")


# --------------------------------------------------------------------------- #
# the restatements this mechanism replaced stay retired
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path", _AGENT_FILES, ids=lambda p: p.name)
def test_no_agent_re_inlines_the_command_hygiene_block(path: Path):
    """The restatement this mechanism replaced, in the six specs that carried it.

    It was verbatim in all six and drifted anyway — `spec-reviewer` had lost the
    commit-substitution rule. A re-inlined copy is how that starts again.
    """
    body = path.read_text(encoding="utf-8")
    assert "## Command hygiene" not in body, (
        f"{path.name}: command hygiene is delivered by "
        f"rules/aide-command-hygiene.md, not restated per agent")


_INBOX_TEMPLATE_RE = re.compile(r"templates/insights\.md")


@pytest.mark.parametrize("path", _AGENT_FILES + _SKILL_FILES, ids=_label)
def test_no_agent_or_skill_tells_a_role_to_copy_the_inbox_template(path: Path):
    """The create-if-missing clause, retired in 1.26.0 (issue #85).

    All six specs and `aide-execute-item` carried "create it from
    `.aide/templates/insights.md`, copied verbatim, if missing". The engine now
    guarantees the file (`ensure_insights_inbox`, run by `check`, `claim` and
    `queue start`), so a role has nothing to copy — and the mention itself was
    the cost: it made every spec name `templates/`, which is what stops a
    template-scoped delivery from discriminating by role. Guarded on the
    template's path, not the clause's wording, because a reworded restatement
    of the same step would re-open both.
    """
    body = path.read_text(encoding="utf-8")
    assert not _INBOX_TEMPLATE_RE.search(body), (
        f"{path.name}: names templates/insights.md — the engine creates the "
        f"inbox (conventions.md §1); a role only appends to it")


_HANDOFF_HEADING = re.compile(r"^#{1,6}[ \t]*Hand-?off[ \t]*$", re.M | re.I)


@pytest.mark.parametrize("path", _SKILL_FILES, ids=_label)
def test_no_skill_ends_in_a_navigational_hand_off_tail(path: Path):
    """The restatement retired in 1.42.0 (issue #161).

    Seven skills ended with a `## Hand-off` section telling the user to start a
    fresh session and run the next entry point — a slice of the loop sequence
    each, drifting independently, and paid for on every spawn that loads the
    skill. The sequence now has one home (`README.md`) and the fresh-session
    rule one statement (`AGENT-CONTEXT.md`); a skill closes by saying what it
    produced. The two content-bearing endings survived the change under
    headings that name what they are, which is why this guards the *heading*
    rather than the content.
    """
    _, body = _split(path)
    assert not _HANDOFF_HEADING.search(body), (
        f"{_label(path)}: carries a `Hand-off` heading. The loop sequence and "
        f"the fresh-session rationale live in README.md and AGENT-CONTEXT.md; "
        f"if this ending carries content, head it with what that content is.")
