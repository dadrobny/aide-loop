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

Stdlib + pytest only.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ADAPTER = Path(__file__).resolve().parents[1]
_RULES_DIR = _ADAPTER / "rules"
_CORE = _ADAPTER.parents[1] / "core"

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

#: Any HTML comment, stripped from a rule body before the rule side is searched
#: — otherwise every pin would match its own declaration and the rule half of
#: the check would assert nothing at all.
_COMMENT = re.compile(r"<!--.*?-->", re.S)

#: `user-invocable: false` in a skill's frontmatter — the structural signal of
#: a section skill, and since 1.42.0 the only one.
_HIDDEN = re.compile(r"^user-invocable:[ \t]*false[ \t]*$", re.M | re.I)

#: Emphasis and code markers. Dropped on both sides, so bolding a clause in one
#: copy and not the other is not a failure, while rewording it still is.
_MARKERS = str.maketrans("", "", "*_`")


def _read(path: Path) -> str:
    """`utf-8-sig`, CRLF folded — the reader used everywhere in this suite.

    A BOM from a Windows editor and a CRLF checkout are both invisible to a
    human reading the file, so neither may decide whether a pin holds. This
    repo has no `.gitattributes` `text eol=lf` pin, so the windows CI leg does
    get CRLF (conventions.md §6).
    """
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def _normalise(text: str) -> str:
    """The comparable form of a passage: what it says, not how it is set.

    Four transforms, each chosen to absorb a *typographic* difference between
    two copies of one sentence and nothing more:

    1. **A markdown table row is de-piped.** `| ⏸️ | Deferred | 2 |` becomes
       `⏸️ Deferred 2`, so a vocabulary the engine states as a table can be
       quoted as the phrase a rule states it in. Only a line that both starts
       and ends with `|` is treated this way — a prose `||` is untouched, which
       matters because "never chain with `&&`, `||` or `;`" is itself a pin.
    2. **Runs of whitespace collapse**, so a reflow across a different line
       width is not a change.
    3. **`*`, `_` and `` ` `` are dropped**, so bold/italic/code emphasis may
       differ between the two copies. A quoted identifier survives as its own
       text (`.as_posix()`), which is the load-bearing part.
    4. **Case is folded**, because whether a quoted clause starts a sentence is
       a property of where it was placed, not of what it says.

    Deliberately NOT normalised: punctuation, dashes, word order, and every
    other content-bearing byte. `test_the_normaliser_still_sees_a_reword`
    holds that line — a normaliser loose enough to let a reworded sentence pass
    would turn this whole module into a test that cannot fail.
    """
    rows = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if len(line) > 1 and line.startswith("|") and line.endswith("|"):
            line = line[1:-1].replace("|", " ")
        rows.append(line)
    return " ".join(" ".join(rows).translate(_MARKERS).split()).casefold()


def _is_section_skill(path: Path) -> bool:
    """The same recognition `test_rules.py` uses: a `SKILL.md` that hides
    itself from the `/` menu with `user-invocable: false`.

    Not "carries a pins block" — since 1.42.0 a **workflow** skill may quote
    the contract it acts on too (`aide-create-queue`, `aide-review-insights`
    and the §1 routing table), and those quotes are checked here exactly like
    a delivered file's. What separates the two sets is only the *obligation*
    below: a delivered file must pin something, a workflow skill need not.
    """
    text = _read(path)
    head = text[4:text.find("\n---\n", 4)] if text.startswith("---\n") else ""
    return bool(_HIDDEN.search(head))


#: Every file that **delivers** a contract section: the rules, and the section
#: skills. This is the set that owes at least one pin.
_DELIVERED = _RULE_FILES + [p for p in _SKILL_FILES if _is_section_skill(p)]

#: Every file whose pins are **checked**: the delivered files, plus any other
#: skill that quotes the contract. A workflow skill owes no pin, but a pin it
#: does declare binds it exactly as a rule's binds the rule — which is what
#: makes "one routing table, restated in two skills" a checkable claim rather
#: than a review note.
_PINNING = _DELIVERED + [p for p in _SKILL_FILES
                         if p not in _DELIVERED and _PINS_OPENER.search(_read(p))]


def _label(path: Path) -> str:
    """`aide-test-hygiene` for a skill, the filename for a rule."""
    return path.parent.name if path.name == "SKILL.md" else path.name


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
    assert len(_DELIVERED) > len(_RULE_FILES), (
        "no skills/*/SKILL.md reads as a section skill — the layout moved, or "
        "the recognition here stopped seeing `user-invocable: false`")
    assert len(_PINNING) > len(_DELIVERED), (
        "no workflow skill declares a `<!-- pins: … -->` block — the routing "
        "table `/aide-create-queue` and `/aide-review-insights` share is "
        "unpinned, or the opener regex stopped matching")
    assert _PINNED, "no delivered file declares a `<!-- pins: … -->` block"


@pytest.mark.parametrize("rule", _DELIVERED, ids=_label)
def test_every_delivered_file_pins_at_least_one_statement(rule: Path):
    """No delivered file ships unguarded, including one added tomorrow.

    A delivered file that pins nothing is not cheap — it is a restatement with
    no counterpart named, which is the exact shape #79 shipped twice. If a file
    genuinely delivers no normative engine statement, that is a question about
    why it is delivered at all, and it should surface here rather than be
    exempted in silence.
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
    body = _COMMENT.sub(" ", _read(rule))
    if body.startswith("---\n"):
        end = body.find("\n---\n", 4)
        body = body[end + 5:] if end != -1 else body
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
