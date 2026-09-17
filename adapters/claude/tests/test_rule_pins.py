"""A delivered file still says what its section says — asserted, not reviewed.

The gap this closes (issue #81). ADAPTER-SPEC §7 splits the contract in two:
`core/conventions/` holds the rule, the adapter delivers it — as a
`.claude/rules/` file, or since 1.27.0 as a **section skill** under
`.claude/skills/<name>/SKILL.md` preloaded by role (issue #85) — and the
delivered copy "adds no rule the engine does not have". The delivered copy is,
unavoidably, a **restatement** — and this framework's whole premise is that
restatements drift. `test_rules.py` guards the envelope (the files ship, the
frontmatter parses, each names a `§N`); every one of those stays true whatever
the rule goes on to say.

It shipped twice in the PR that forbade it, both fixed in 8bca181 by a human
reading two files side by side: `aide-living-documents.md` asserted a
progress.md rule the engine contradicts, and `aide-test-hygiene.md` carried a
determinism rule that appeared nowhere under `core/`. Nothing in the suite
could have noticed either.

**The mechanism: a curated pin.** A rule declares the normative statements it
delivers and the section file each is quoted from; this module asserts every
one still appears on *both* sides. That covers both directions of drift — a
rule reworded away from its section, and a section rewritten so the rule is now
wrong — because editing either copy alone breaks the same assertion.

    <!-- pins: .aide/conventions/6-test-hygiene.md
         Prose note, ignored: anything before the first `- ` line.
         - A test must be deterministic and pass on Windows, macOS and Linux,
           with no network access
         - Never write the repo's own working-directory path literally into a
           test
    -->

An HTML comment rather than a frontmatter key, following the `<!-- reach: … -->`
precedent from #84: `test_rules.py` pins the frontmatter keys of each carrier,
a comment carries no runtime meaning, it works on an unscoped rule that has no
frontmatter at all, and it survived #85's move of this content into skills —
where it costs nothing on the loop's path, since a preloaded skill body is
injected with its HTML comments stripped. One block per section file, so a
file delivering four sections declares four blocks. A `- ` opens a pin and any
line under it that does not continues it, so a pin may wrap.

The section path is written in **consumer** form (`.aide/conventions/…`), like
every other path inside `adapters/`, and is resolved back to `core/conventions/`
here. Source tree, not an install: this is adapter↔engine consistency, and both
sides sit in this repo.

**Who may pin.** Every delivered file must (that is the obligation above); any
other skill, agent spec or command may. A **workflow** skill that restates a
slice of the contract it acts on — `/aide-create-queue` and
`/aide-review-insights` each carry the §1 routing table verbatim, which is the
whole point of writing that table once — declares the same blocks and is held
to them the same way, in both directions; so does an agent spec carrying a
section its role is not preloaded with (`builder.md`, §5). It simply owes none,
because it delivers no section. The one difference in what may be quoted: a
delivered file's pins must sit in the section's core, above its `Rationale`
heading, while an undelivered copy may quote the tail (issue #224).

**What the pin list is not.** It is hand-curated and can go stale — but only
toward under-checking: a statement nobody pinned is unguarded exactly as it was
before, while a pinned one cannot move on one side alone. The known cost, taken
deliberately in exchange for a check that needs no natural-language judgement.

**What it is no longer for: a generated file** (1.47.0, issue #109). Where a
delivered file declares `<!-- generated-from: <section> -->`, `install.py`
writes the section's core into it verbatim at install time — so the delivered
copy is not a restatement and there is nothing for a pin to guard. Those files
are excluded from every check below and held instead by
`test_generated_delivery.py`, which asserts the stronger property this one
approximates: not "these sentences still appear on both sides" but "the
delivered body *is* the section". A pin declared in one is a category error and
fails here, because a curated quote beside a generated body is a claim nobody
maintains — the pin cannot drift from the section, so it can only go stale
against a wording it does not control.

Stdlib + pytest only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_ADAPTER = Path(__file__).resolve().parents[1]
_RULES_DIR = _ADAPTER / "rules"
_CORE = _ADAPTER.parents[1] / "core"

sys.path.insert(0, str(_ADAPTER.parents[1]))
sys.path.insert(0, str(_ADAPTER.parents[1] / "tests"))
import install  # noqa: E402  (path shim above)
from _delivered import (COMMENT as _COMMENT, STRIPS_BOM,  # noqa: E402
                        is_generated as _is_generated, label as _label,
                        normalise as _normalise)

#: The source tree, so the reader that reports on a file behind a BOM rather
#: than the one that refuses it — `tests/_delivered.py` has the difference.
_read = STRIPS_BOM.text
_body = STRIPS_BOM.body
_is_section_skill = STRIPS_BOM.is_section_skill

_RULE_FILES = sorted(_RULES_DIR.glob("*.md"))
_SKILL_FILES = sorted((_ADAPTER / "skills").glob("*/SKILL.md"))
#: The other installed markdown control files. Neither delivers a section, so
#: neither owes a pin; either may declare one, and is then held to it.
_AGENT_FILES = sorted((_ADAPTER / "agents").glob("*.md"))
_COMMAND_FILES = sorted((_ADAPTER / "commands").glob("*.md"))

#: The consumer prefix every pinned section path is written with. `.aide/` is
#: where the engine lands in an install; `core/` is where it lives here.
_CONSUMER_ENGINE_PREFIX = ".aide/"

#: `<!-- pins: <section path>` … `-->`. Non-greedy, so consecutive blocks stay
#: separate and the reach comment above them is not swallowed.
_PINS = re.compile(r"<!--[ \t]*pins:[ \t]*(?P<section>[^\s]+)[ \t]*\n"
                   r"(?P<body>.*?)-->", re.S)

#: Every `<!-- pins:` opener, whatever follows it. `_PINS` above is the
#: *grammar*; this is the count of things claiming to be written in it, and the
#: two disagreeing is how a block that silently failed to parse — a one-line
#: `<!-- pins: … -->`, a missing newline, a mangled section path — is caught
#: instead of vanishing.
_PINS_OPENER = re.compile(r"<!--[ \t]*pins:", re.I)

#: `_normalise` — the comparable form of a passage — is `_delivered.normalise`,
#: shared with `tests/test_floor_pins.py` so the two pin modules cannot read one
#: sentence two ways. Its four transforms are documented there; the tests that
#: hold it to "absorbs typography, sees a reword" stay at the bottom of this
#: module, where they were written.


#: Every file that **delivers** a contract section: the rules, and the section
#: skills.
_DELIVERING = _RULE_FILES + [p for p in _SKILL_FILES if _is_section_skill(p)]

#: The generated half — rendered from its section at install time, so it has
#: no restatement to pin and declares none.
_GENERATED = [p for p in _DELIVERING if _is_generated(p)]

#: The hand-curated half: the set that owes at least one pin. "Delivered" means
#: this from here down, because a generated file is delivered and owes nothing.
_DELIVERED = [p for p in _DELIVERING if p not in _GENERATED]

#: Every file whose pins are **checked**: the delivered files, plus any other
#: skill, agent spec or command that quotes the contract. None of those owes a
#: pin, but a pin one does declare binds it exactly as a rule's binds the rule
#: — which is what makes "one routing table, restated in two skills" a
#: checkable claim rather than a review note.
_UNDELIVERING = ([p for p in _SKILL_FILES if p not in _DELIVERING]
                 + _AGENT_FILES + _COMMAND_FILES)
_PINNING = _DELIVERED + [p for p in _UNDELIVERING if _PINS_OPENER.search(_read(p))]


def _pin_blocks(path: Path) -> list:
    """`[(section path as written, [pin, …]), …]` for one rule file.

    A line whose stripped form starts with `- ` opens a pin; a following line
    that does not continues it, joined by a space. Anything before the first
    `- ` is the block's prose note and is dropped.
    """
    blocks = []
    for match in _PINS.finditer(_read(path)):
        pins: list = []
        for line in match.group("body").split("\n"):
            line = line.strip()
            if line.startswith("- "):
                pins.append(line[2:].strip())
            elif line and pins:
                pins[-1] += " " + line
        blocks.append((match.group("section"), pins))
    return blocks


def _section_path(declared: str) -> Path:
    """A consumer-form `.aide/conventions/…` path, resolved into `core/`."""
    assert declared.startswith(_CONSUMER_ENGINE_PREFIX), (
        f"{declared!r}: a pinned section is named by its consumer path, "
        f"e.g. `.aide/conventions/6-test-hygiene.md`")
    relative = declared[len(_CONSUMER_ENGINE_PREFIX):]
    assert ".." not in relative.split("/"), f"{declared!r}: escapes the engine"
    return _CORE.joinpath(*relative.split("/"))


#: `(rule, section as written, pin)`, flattened at collection time so each pin
#: is its own test case and a failure names the sentence that moved.
_PINNED = [(rule, section, pin)
           for rule in _PINNING
           for section, pins in _pin_blocks(rule)
           for pin in pins]


def _id(case) -> str:
    rule, section, pin = case
    return f"{_label(rule)}::{section.rsplit('/', 1)[-1]}::{pin[:48]}"


# --------------------------------------------------------------------------- #
# fail closed — the corpus is recognisable before anything is asserted about it
# --------------------------------------------------------------------------- #
def test_there_are_delivered_files_and_they_declare_pins():
    """conventions.md §6: assert the derived value is recognisable first.

    A glob that stopped matching, or a `pins:` grammar nobody writes any more,
    would empty `_PINNED` and every parametrised test below would vanish
    silently — a green suite checking nothing, which is the failure mode this
    module exists to prevent elsewhere.
    """
    assert _RULE_FILES, "no rules/*.md found — the glob or the layout moved"
    assert len(_DELIVERING) > len(_RULE_FILES), (
        "no skills/*/SKILL.md reads as a section skill — the layout moved, or "
        "the recognition here stopped seeing `user-invocable: false`")
    assert _DELIVERED, (
        "every delivered file reads as generated — either the last curated one "
        "was converted (in which case this module is finished and should go, "
        "not be left passing vacuously) or `is_generated` stopped saying no")
    assert _GENERATED, (
        "no delivered file reads as generated — `<!-- generated-from: … -->` "
        "stopped parsing, and the exclusions below now describe nothing")
    assert len(_PINNING) > len(_DELIVERED), (
        "no workflow skill declares a `<!-- pins: … -->` block — the routing "
        "table `/aide-create-queue` and `/aide-review-insights` share is "
        "unpinned, or the opener regex stopped matching")
    assert _PINNED, "no delivered file declares a `<!-- pins: … -->` block"


@pytest.mark.parametrize("path", _GENERATED, ids=_label)
def test_a_generated_file_declares_no_pins(path: Path):
    """The other side of the exclusion, so it cannot be taken silently.

    A generated file that grows a pins block is not harmlessly redundant: the
    pin quotes a sentence the file does not control, so the only way it can
    ever fail is by the section being reworded — reporting drift in a copy
    that by construction has none, and inviting the fix that "updates both
    copies" of something with one copy.
    """
    assert not _PINS_OPENER.search(_read(path)), (
        f"{_label(path)}: declares a pin, and its body is rendered from "
        f"{install.generated_sections(_read(path))} at install time. The pins "
        f"mechanism guards a restatement; there is none here. Delete the "
        f"block — `test_generated_delivery.py` asserts the whole body against "
        f"the section, which is strictly stronger.")


@pytest.mark.parametrize("rule", _DELIVERED, ids=_label)
def test_every_delivered_file_pins_at_least_one_statement(rule: Path):
    """No delivered file ships unguarded, including one added tomorrow.

    A delivered file that pins nothing is not cheap — it is a restatement with
    no counterpart named, which is the exact shape #79 shipped twice. If a file
    genuinely delivers no normative engine statement, that is a question about
    why it is delivered at all, and it should surface here rather than be
    exempted in silence.

    The one exemption is not one: a **generated** file has no restatement to
    pin, and is not in this list at all (see the module docstring). It is the
    same obligation discharged by a stronger mechanism, not a waiver.
    """
    blocks = _pin_blocks(rule)
    assert blocks, (
        f"{_label(rule)}: no `<!-- pins: … -->` block. Every delivered file "
        f"quotes the statements it carries from the section they live in; see "
        f"this module's docstring for the format.")
    empty = [section for section, pins in blocks if not pins]
    assert not empty, (
        f"{_label(rule)}: pins block for {empty} has no `- ` line, so it quotes "
        f"nothing and every assertion below skips it. Name the statements the "
        f"rule delivers from that section, or drop the block — a section "
        f"declared and not quoted is the unguarded restatement this module "
        f"exists to prevent, wearing the guard's clothes.")


@pytest.mark.parametrize("rule", _PINNING, ids=_label)
def test_every_pins_comment_in_a_delivered_file_actually_parses(rule: Path):
    """A block the grammar does not recognise must be loud, not absent.

    `_PINS` requires the section path to be followed by a newline, so the
    one-line spelling the sibling declaration uses —

        <!-- pins: .aide/conventions/6-test-hygiene.md -->

    — matches nothing at all. It is a plausible thing to write: `README.md`
    documents `<!-- reach: … -->` as a one-liner two paragraphs away, and a
    rule that carried exactly one pin would read better on one line. Written
    that way it does not fail; it *disappears*, taking its statements out of
    `_PINNED` and leaving a rule that looks pinned and is not — the same silent
    under-checking the module's docstring accepts for a statement nobody
    pinned, except that here the author believes they did.

    So the openers are counted independently of the grammar and the two must
    agree. Any `<!-- pins:` the parser did not yield a block for is a failure,
    whatever went wrong with it.
    """
    text = _read(rule)
    openers = len(_PINS_OPENER.findall(text))
    parsed = len(_pin_blocks(rule))
    assert openers == parsed, (
        f"{_label(rule)}: {openers} `<!-- pins:` comment(s), {parsed} parsed. "
        f"A pins block is `<!-- pins: <section path>` on its own line, then "
        f"one `- ` line per quoted statement, then `-->` — the one-line form "
        f"borrowed from `<!-- reach: … -->` does not parse, and an unparsed "
        f"block asserts nothing while looking like it does.")


@pytest.mark.parametrize("case", _PINNED, ids=_id)
def test_a_pin_is_substantial_enough_to_be_worth_asserting(case):
    """A one-word pin would pass against almost any prose on either side.

    Only the obviously useless shape is caught — this cannot judge whether a
    pin is the *load-bearing* sentence, which stays a human call at review.
    """
    _, _, pin = case
    normalised = _normalise(pin)
    assert len(normalised) >= 6 and len(normalised.split()) >= 2, (
        f"{pin!r}: too short to identify a statement")


# --------------------------------------------------------------------------- #
# the pin itself — both directions
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", _PINNED, ids=_id)
def test_a_pinned_statement_still_appears_in_the_section_it_names(case):
    """The engine half. A section rewritten leaves the rule asserting something
    the source of truth no longer says, and the rule reads as authoritative to
    whoever has it in context."""
    rule, declared, pin = case
    section = _section_path(declared)
    assert section.is_file(), (
        f"{_label(rule)} pins {declared}, which is not a file — the section "
        f"moved or was renamed")
    assert _normalise(pin) in _normalise(_read(section)), (
        f"{_label(rule)}: pinned statement is no longer in {declared}\n"
        f"  pinned: {pin}\n"
        f"Either the section was reworded (update both copies) or the rule now "
        f"states something the engine does not (fix the rule, or add the "
        f"statement to the section and bump core/VERSION).")


@pytest.mark.parametrize("case", _PINNED, ids=_id)
def test_a_pinned_statement_still_appears_in_the_rule_that_declares_it(case):
    """The adapter half, and the reason the declaration is not a config file.

    The body is searched with every HTML comment stripped, so a pin cannot
    satisfy itself — and for a section skill that stripped body is exactly
    what a preload injects, so this half asserts on what the role receives.
    Deleting or rewording the delivered sentence while leaving the pin behind
    fails here — the pin list stops being a description of the file and
    becomes part of it.
    """
    rule, _, pin = case
    body = _COMMENT.sub(" ", _body(rule))
    assert _normalise(pin) in _normalise(body), (
        f"{_label(rule)}: declares a pin its own body no longer states\n"
        f"  pinned: {pin}\n"
        f"Drop the pin if the rule deliberately stopped delivering it.")


#: The pins a **delivered** file declares — the ones held to the section core.
_DELIVERED_PINNED = [case for case in _PINNED if case[0] in _DELIVERED]


@pytest.mark.parametrize("case", _DELIVERED_PINNED, ids=_id)
def test_a_delivered_pin_quotes_the_section_core_not_its_rationale(case):
    """ADAPTER-SPEC, *Copies of engine text*, rung 3 (issue #224).

    A delivered file carries the rule to a reader who has no other copy of it,
    so every sentence it pins is one that reader acts on — core by the
    which-side test, and therefore above the `Rationale` heading. A pin that
    only the tail satisfies is a disambiguator filed on the wrong side, or
    provenance the delivered file should not carry.

    Scoped to delivered files on purpose: an agent spec or workflow skill
    carrying a slice of a section its role does not preload may quote the
    tail (`builder.md`, `spec-reviewer.md`), and is held only by the two
    both-directions checks above.
    """
    rule, declared, pin = case
    section = _read(_section_path(declared))
    core = install.section_core(section)
    assert core is not None, (
        f"{declared} has no `Rationale` heading, so {_label(rule)}'s pins cannot "
        f"be told core from tail — every section reads core first, then the tail")
    assert _normalise(pin) in _normalise(core), (
        f"{_label(rule)}: pins a sentence that sits below {declared}'s "
        f"`Rationale` heading\n  pinned: {pin}\n"
        f"If the delivered reader acts on it, it is core — move it above the "
        f"heading in the section (and bump core/VERSION). If not, drop it from "
        f"the delivered file.")


def test_the_core_check_can_tell_a_tail_sentence_from_a_core_one():
    """The guard on the guard: a sentence lifted from below a section's
    `Rationale` heading is absent from that section's core, so the check above
    is not satisfied by the whole file."""
    section = _read(_section_path(".aide/conventions/6-test-hygiene.md"))
    core = install.section_core(section)
    assert core is not None, "6-test-hygiene.md has no Rationale heading — pick another section"
    tail_lines = [line.strip()[2:] for line in section[len(core):].splitlines()
                  if line.strip().startswith("- ") and len(line.split()) >= 8]
    assert tail_lines, "the §6 tail has no bullet to plant — pick another section"
    assert _normalise(tail_lines[0]) not in _normalise(core), tail_lines[0]
    assert _DELIVERED_PINNED, "no delivered file declares a pin — the check above is vacuous"


# --------------------------------------------------------------------------- #
# the normaliser, which is the only thing between this module and a no-op
# --------------------------------------------------------------------------- #
def test_the_normaliser_absorbs_a_reflow_and_a_change_of_emphasis():
    """The false alarms it exists to prevent: a rewrap, and bold on one side."""
    section = ("- **Any `Path` entering a hash, comparison, or match must be\n"
               "  `.as_posix()`.** `str(Path)` renders the OS-native separator.")
    pin = "Any `Path` entering a hash, comparison, or match must be `.as_posix()`"
    assert _normalise(pin) in _normalise(section)
    assert _normalise(pin) in _normalise(
        "any Path entering a hash, comparison, or match must be .as_posix().")


def test_the_normaliser_still_sees_a_reword():
    """The half that makes the module worth running.

    Each variant below is a real way a statement drifts — a dropped qualifier,
    a changed operator, a substituted word, a reordered clause. If the
    normaliser is ever loosened, one of these starts passing and the pins go
    quiet without a single test turning red.
    """
    pin = "Never chain with `&&`, `||` or `;`"
    for drifted in (
            "Never chain with `&&` or `;`",              # a dropped operator
            "Never chain with `&&`, `||` or `&`",        # a changed operator
            "Never combine with `&&`, `||` or `;`",      # a substituted verb
            "Never chain with `;`, `||` or `&&`",        # a reordered clause
    ):
        assert _normalise(pin) not in _normalise(drifted), (
            f"the normaliser lets {drifted!r} satisfy the pin {pin!r}")


def test_a_markdown_table_row_is_de_piped_but_a_prose_operator_is_not():
    """Both halves of transform 1, since they pull in opposite directions."""
    assert _normalise("| ⏸️ | Deferred | 2 |") == "⏸️ deferred 2"
    assert "||" in _normalise("Never chain with `&&`, `||` or `;`")


# --------------------------------------------------------------------------- #
# a control file that carries no pins restates nothing measurable (#205, #219)
# --------------------------------------------------------------------------- #
#: The register of a copy is its guard (ADAPTER-SPEC, *Copies of engine text*,
#: *Registering a copy*). A workflow skill, an agent spec and a command owe no
#: pin — but the licence for that is that they restate nothing, and "nothing"
#: is measurable: the ten-word runs a file shares with the contract, in **the
#: corpus `install.py --check` compares a consumer's instruction file against**
#: (`install.contract_echoes`: `AGENT-CONTEXT.md`, `conventions.md`, every
#: section whole, `core/README.md`), comments stripped the way the pin check
#: above strips them. Section cores alone would be narrower than `--check` and
#: would miss the one restatement a workflow skill has actually shipped before
#: — the `## Hand-off` tail copying `core/README.md`'s loop sequence (#161).
#: Measured on this tree the two kinds do not overlap: every hand-written
#: delivered file shares at least **53** runs (`aide-human-gates`) and every
#: file that pins nothing shares at most **3** (`reviewer.md`), so a
#: floor of twenty is a gap, not a tuned value — and the gap is asserted from
#: both sides below, so the numbers here are re-measured by the suite rather
#: than quoted. A file that crosses the floor has become a copy, and a copy is
#: either pinned or pointed.
#:
#: Until issue #219 the floor iterated skills alone, and two agent specs sat
#: above it unguarded — `builder.md`, one of its §5 sentences already reworded
#: away from the section, and `spec-reviewer.md`.
#:
#: Two limits, stated. A file that declares one pin leaves this floor for the
#: pin check, and what it quotes *beyond* its pins is a review question, not a
#: measured one — which is also why a small pinned copy (`aide-create-vision`
#: quotes one §5 sentence) is not held above the floor: the floor bounds files
#: that pin nothing, and a pin is the stronger guard at any size.

WORKFLOW_RESTATEMENT_FLOOR = 20

#: One partition of the undelivering files, derived from `_PINNING` rather than
#: spelled a second time: a file that pins is held by its pins, a file that
#: does not is held by the floor, and no file is in neither set.
_UNDELIVERING_PINNING = [p for p in _PINNING if p not in _DELIVERED]
_UNPINNED = [p for p in _UNDELIVERING if p not in _UNDELIVERING_PINNING]

#: Built once: `contract_echoes` walks every contract file, and many tests read
#: the result. Keyed by run, valued by the shipped file that carries it, so a
#: failure can name the source — a partial second copy of the map
#: `tests/test_template_conventions.py` builds for the templates, kept here
#: because the two modules must not import each other.
_CONTRACT_RUNS: dict = install.contract_echoes(_CORE)[0]


def _shared_runs(text: str) -> dict:
    """`run -> shipped contract file` for every ten-word run *text* shares."""
    prose = install._contract_prose(_COMMENT.sub(" ", text))
    return {run: _CONTRACT_RUNS[run]
            for run in set(install._contract_runs(install._contract_words(prose)))
            if run in _CONTRACT_RUNS}


def _control_label(path: Path) -> str:
    """`skills/aide-create-vision`, `agents/builder.md` — the kind is part of
    the name, since a skill and an agent may one day share one."""
    if path.name == "SKILL.md":
        return f"skills/{path.parent.name}"
    return f"{path.parent.name}/{path.name}"


def test_the_contract_corpus_and_the_control_partition_are_recognisable():
    """§6: a derived value is recognisable before anything is asserted about
    it — an empty corpus or an empty partition would pass every case below."""
    assert len(_CONTRACT_RUNS) > 1000, len(_CONTRACT_RUNS)
    assert _AGENT_FILES and _COMMAND_FILES, "agents/*.md or commands/*.md matched nothing"
    kinds = {p.parent.name if p.name != "SKILL.md" else "skills" for p in _UNPINNED}
    assert kinds == {"skills", "agents", "commands"}, kinds
    assert len(_UNPINNED) >= 15, [_control_label(p) for p in _UNPINNED]
    assert _UNDELIVERING_PINNING, "no undelivering file pins — the partition has one side"
    assert not set(_UNPINNED) & set(_UNDELIVERING_PINNING)


@pytest.mark.parametrize("path", _UNPINNED, ids=_control_label)
def test_a_control_file_without_pins_restates_nothing_measurable(path: Path):
    shared = _shared_runs(_read(path))
    assert len(shared) < WORKFLOW_RESTATEMENT_FLOOR, (
        f"{_control_label(path)} carries no <!-- pins: --> block but shares "
        f"{len(shared)} ten-word runs with the contract —\n"
        + "\n".join(f"  {src}: \u201c{run}\u201d" for run, src in sorted(shared.items())[:5])
        + "\nA control file that restates the contract is a copy: quote-pin the "
          "statements it carries (ADAPTER-SPEC, 'Copies of engine text', rung 3) "
          "or point at the source and delete them.")


def test_every_hand_written_delivered_file_sits_above_the_floor():
    """The gap the floor sits in, asserted from the other side over **every**
    hand-written delivered file, so the check separates the two kinds on this
    tree rather than passing everything, and a section skill compressed to
    under the floor fails here rather than silently narrowing the gap."""
    counts = {_label(p): len(_shared_runs(_read(p))) for p in _DELIVERED}
    below = {name: n for name, n in counts.items() if n < WORKFLOW_RESTATEMENT_FLOOR}
    assert not below, f"a delivered file shares fewer runs than the floor: {below} (all: {counts})"


def test_a_planted_restatement_crosses_the_floor():
    """The guard on the guard: a skill that pastes one section core in is
    reported, and the report names the section."""
    section = _read(_section_path(".aide/conventions/1-format-contract/human-gates.md"))
    core = install.section_core(section)
    assert core is not None, "human-gates.md has no Rationale heading — pick another section"
    shared = _shared_runs("---\nname: planted\n---\n" + core)
    assert len(shared) >= WORKFLOW_RESTATEMENT_FLOOR, len(shared)
    # The floor names the *first* contract file carrying a run, and the
    # always-on page quotes human-gate sentences too — so the section is among
    # the named sources, not necessarily the only one.
    assert ".aide/conventions/1-format-contract/human-gates.md" in set(shared.values()), set(shared.values())
