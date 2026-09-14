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
other skill may. A **workflow** skill that restates a slice of the contract it
acts on — `/aide-create-queue` and `/aide-review-insights` each carry the §1
routing table verbatim, which is the whole point of writing that table once —
declares the same blocks and is held to them the same way, in both directions.
It simply owes none, because it delivers no section.

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
#: skill that quotes the contract. A workflow skill owes no pin, but a pin it
#: does declare binds it exactly as a rule's binds the rule — which is what
#: makes "one routing table, restated in two skills" a checkable claim rather
#: than a review note.
_PINNING = _DELIVERED + [p for p in _SKILL_FILES
                         if p not in _DELIVERING and _PINS_OPENER.search(_read(p))]


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
# a workflow skill that carries no pins restates nothing measurable (issue #205)
# --------------------------------------------------------------------------- #
#: The register of a copy is its guard (ADAPTER-SPEC, *Copies of engine text*,
#: *Registering a copy*). A workflow skill owes no pin — but the licence for
#: that is that it restates nothing, and "nothing" is measurable: the ten-word
#: runs it shares with the section cores, comments stripped and fenced commands
#: dropped, the comparison `install.py --check` runs over a consumer's
#: instruction file. Measured on this tree the two kinds do not overlap —
#: every skill that pins shares at least **53** runs (`aide-human-gates`), and
#: every workflow skill that does not shares at most **6** (`aide-create-vision`)
#: — so a floor of twenty is a wide gap, not a tuned one. A skill that crosses
#: it has become a copy, and a copy is either pinned or pointed; without this
#: check the eight sanctioned pointers were a list on a page, and a ninth
#: unguarded skill was indistinguishable from them.

WORKFLOW_RESTATEMENT_FLOOR = 20

_WORKFLOW_SKILLS = [p for p in _SKILL_FILES
                    if p not in _DELIVERING and not _PINS_OPENER.search(_read(p))]


def _section_core_runs() -> set:
    """Every ten-word run of every section core under `core/conventions/`."""
    runs: set = set()
    for path in sorted((_CORE / "conventions").rglob("*.md")):
        text = path.read_text(encoding="utf-8-sig")
        core = install.section_core(text)
        prose = install._contract_prose(core if core is not None else text)
        runs.update(install._contract_runs(install._contract_words(prose)))
    return runs


def _shared_runs(text: str, core_runs: set) -> set:
    from _delivered import strip_comments
    prose = install._contract_prose(strip_comments(text))
    return set(install._contract_runs(install._contract_words(prose))) & core_runs


def test_there_are_workflow_skills_without_pins():
    assert len(_WORKFLOW_SKILLS) >= 5, [p.parent.name for p in _WORKFLOW_SKILLS]


@pytest.mark.parametrize("path", _WORKFLOW_SKILLS, ids=lambda p: p.parent.name)
def test_a_workflow_skill_without_pins_restates_nothing_measurable(path: Path):
    shared = _shared_runs(_read(path), _section_core_runs())
    assert len(shared) < WORKFLOW_RESTATEMENT_FLOOR, (
        f"{path.parent.name}/SKILL.md carries no <!-- pins: --> block but shares "
        f"{len(shared)} ten-word runs with the section cores, e.g. "
        f"\u201c{sorted(shared)[0]}\u201d. A workflow skill that restates the contract "
        "is a copy: quote-pin the statements it delivers (ADAPTER-SPEC, 'Copies "
        "of engine text', rung 3) or point at the section and delete them.")


def test_the_pinning_skills_would_fail_that_floor():
    """The gap the floor sits in, asserted from the other side: every skill that
    does pin shares more than the floor, so the check separates the two kinds
    on this tree rather than passing everything."""
    core_runs = _section_core_runs()
    pinning = [p for p in _SKILL_FILES if p not in _DELIVERING and _PINS_OPENER.search(_read(p))]
    assert pinning, "no workflow skill pins — the premise of the floor is gone"
    below = {p.parent.name: len(_shared_runs(_read(p), core_runs))
             for p in pinning if len(_shared_runs(_read(p), core_runs)) < WORKFLOW_RESTATEMENT_FLOOR}
    assert not below, f"a pinning skill shares fewer runs than the floor: {below}"


def test_a_planted_restatement_crosses_the_floor(tmp_path: Path):
    """The guard on the guard: a skill that pastes one section core in would be
    reported."""
    section = (_CORE / "conventions" / "1-format-contract" / "human-gates.md").read_text(encoding="utf-8-sig")
    planted = "---\nname: planted\n---\n" + (install.section_core(section) or section)
    assert len(_shared_runs(planted, _section_core_runs())) >= WORKFLOW_RESTATEMENT_FLOOR
