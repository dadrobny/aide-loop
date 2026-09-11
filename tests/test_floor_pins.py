"""The always-on page still says what its sections say — asserted, not reviewed.

`core/AGENT-CONTEXT.md` is the page that binds before anything points anywhere
(ADAPTER-SPEC §7): the instruction-file import puts it in front of every role on
every spawn, and in front of an interactive session with no agent spec in play.
Most of what it carries is a compressed copy of a `conventions/` section — and
a copy inside the engine drifts exactly as one in the adapter does (issue #81):
two statements of one rule, neither pointing at the other, nothing holding them
together.

It had (issue #194). The read-cold block said never write "as discussed above"
at all; §1 says never write it *pointing outside the artifact*. That is a
different rule, stricter than the contract the page delivers, and it sat on the
one page every role reads because nothing compared the two.

**The mechanism is `adapters/claude/tests/test_rule_pins.py`'s**: a curated
list of sentences, each quoted from a section, each asserted in *both* copies
after the same normalisation (`_delivered.normalise` — reflow, emphasis and
case absorbed, punctuation and wording not). Editing either copy alone fails
the same assertion, which is what covers both directions of drift.

**Two differences, both deliberate.**

1. **The pins live here, not in the page.** An adapter file declares its pins
   in `<!-- pins: … -->` comments because a preload strips them, so the
   declaration costs its reader nothing. The page has no such channel: it
   arrives through an instruction-file import the engine does not own and
   cannot assume strips anything, and `test_structural_budget.py` costs it at
   its whole bytes on every spawn of every role. A declaration nobody reads
   would move that floor by its own size. The failure message names the page,
   which is where an editor needs to hear about it.
2. **The section side is the core only.** A pin is searched for above the
   section's closing `Rationale` heading — `install.section_core`, the cut the
   generator uses — never in the whole file. A pinned sentence is core by
   definition (CLAUDE.md), and the always-on page is the last place a reason
   should pass for a rule; a pin only the tail satisfies fails here.

**What is pinned.** Seven of the page's nine headings, one `FLOOR_PINS` entry
per section a heading names — the read-cold block since #194, the other six
since #205's floor row. What is quoted is each heading's *rules*: the page's
one-clause reasons are the sections' `Rationale` material and a pin cannot
reach them, which is the curation this rung is known to cost, not an oversight.

**The other two headings are pointers, not copies**, and a pointer is the
ladder's rung 1 rather than a gap in this list. Each names where its full
treatment lives, adds one sentence of the page's own, and restates nothing — so
there is no second copy to hold it to.

1. **"Each loop step ends in its own session"** names `core/README.md` for the
   step sequence, but the fresh-session rule is written here and nowhere else:
   the seven skills that carried a `## Hand-off` tail had it removed in favour
   of this page (issue #161). `README.md` has no closing `Rationale` heading
   either, so `install.section_core` returns `None` and the resolve test below
   would fail on such an entry.
2. **"Mechanical actions go through the CLI"** names §2, §4 and `README.md` and
   restates none of the three. The verb list is `argparse`'s surface (`aide
   <verb> -h`, the ladder's fifth rung), and the sentence under it — prefer the
   verb; it is what keeps the documents parseable — is the page's own summary.
   Pinning the heading would mean first *putting* §2 and §4 statements on the
   page for the pins to quote, which every spawn of every role then pays for.
   The floor carries what must bind before anything points anywhere, and where
   `git.mode` is enforced is not that.

**§3 is delivered twice to one session**, and deliberately: its core is
generated whole into the adapter's always-loaded rule, while the page keeps a
four-sentence compression of it for the session that reads the floor before any
rule loads. The pins are what keep the compression a subset rather than a
variant.

Stdlib + pytest only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
sys.path.insert(0, str(FRAMEWORK_ROOT / "tests"))
import install  # noqa: E402  (path shim above)
from _delivered import STRIPS_BOM, normalise, strip_comments  # noqa: E402

CORE = FRAMEWORK_ROOT / "core"
FLOOR = CORE / "AGENT-CONTEXT.md"

#: `{section file, relative to core/: [statement quoted from its core, …]}`.
#: The load-bearing sentences, not every line: a floor copy is allowed to be
#: shorter than its section (it states a subset), never to say something else.
FLOOR_PINS = {
    # Durable artifacts must read cold
    "conventions/1-format-contract.md": [
        "Durable artifacts must read cold",
        "No chat-local identifiers.",
        "Name a thing by what it is",
        "title a change by the change",
        "Cross-reference by resolvable identity",
        "an issue number, a file path, a commit, a stage number, a dated "
        "`insights.md` entry",
        '"as discussed above" pointing outside the artifact',
        "Record the decision and why it holds, not the route to it.",
        '"My earlier lean was wrong", "agreed direction", "settled while '
        'drafting" narrate a process the reader was not part of.',
    ],
    # Out-of-scope learning is captured, never acted on
    "conventions/1-format-contract/insights.md": [
        "never lost *and* never acted on out of scope",
        "Any role, at any time, appends **one line** and returns to its task",
        "the ISO date is the only part that is load-bearing",
        "`item NNN` from inside an item",
        "`engine X.Y.Z`, one read of `.aide/VERSION`",
        "never reworded, reordered, or deleted",
        "Ticking the checkbox is the one in-place edit",
        "dated lines, indented under the entry, newest last",
    ],
    # Status lives in one place
    "conventions/1-format-contract/progress.md": [
        "the single source of truth for status",
        "the only place the CLI reads",
        "A status claim written anywhere else",
        "a second truth that will disagree with the first",
        "Move it, do not copy it.",
    ],
    # Root documents go through their entry point
    "conventions/5-clarify-mode.md": [
        "carry the safeguards a free-hand file write skips",
        "whatever `loop.clarify` says",
        "the mandatory sections are grounded in the human's answers",
        "Present the result as a draft",
    ],
    # Mechanical actions go through the CLI: nothing here. The heading is a
    # pointer, not a copy — see the module docstring.
    # Command hygiene — also generated whole into the adapter's rule
    "conventions/3-command-hygiene.md": [
        "One command per call",
        "Never chain with `&&`, `||` or `;`",
        "No `cd` prefix and no directory-changing wrapper",
        "No `2>&1` or other redirections",
    ],
    # Only a person resolves a human gate
    "conventions/1-format-contract/human-gates.md": [
        "Any role may raise a gate; only a person may resolve one",
        "No agent may run `aide gate approve`/`decline`",
    ],
    # Another repository's instructions bind before you edit it
    "conventions/8-sibling-repos.md": [
        "A repository's own instructions bind for work inside it",
        "A runtime loads instruction files for the working directory's repo "
        "only",
        "the framework clone included — gets nothing, and nothing announces "
        "the gap",
        "read that repo's instruction file first",
        "the repo that owns the file wins",
    ],
}

#: `(section, pin)`, flattened so each pin is its own test case and a failure
#: names the sentence that moved.
_PINNED = [(section, pin) for section, pins in FLOOR_PINS.items() for pin in pins]


def _id(case) -> str:
    section, pin = case
    return f"{Path(section).stem}::{pin[:48]}"


def _floor_text() -> str:
    """What the page states: comments stripped, since a sentence in one is not
    a sentence the page can be relied on to deliver."""
    return strip_comments(STRIPS_BOM.text(FLOOR))


def _core(section: str):
    return install.section_core(STRIPS_BOM.text(CORE / section))


# --------------------------------------------------------------------------- #
# fail closed — the corpus is recognisable before anything is asserted about it
# --------------------------------------------------------------------------- #
def test_the_page_and_every_pinned_section_resolve():
    """An empty list or a moved file would leave every case below vacuous."""
    assert FLOOR.is_file(), "core/AGENT-CONTEXT.md moved — the floor this module guards"
    assert _PINNED, "FLOOR_PINS quotes nothing"
    for section, pins in FLOOR_PINS.items():
        assert (CORE / section).is_file(), f"{section}: not under core/ — moved or renamed"
        assert pins, f"{section}: declared with no pin, so nothing is asserted about it"
        assert _core(section) is not None, (
            f"{section}: no closing `Rationale` heading, so it has no core to "
            f"pin against")


@pytest.mark.parametrize("case", _PINNED, ids=_id)
def test_a_pin_is_substantial_enough_to_be_worth_asserting(case):
    """The same floor `test_rule_pins.py` sets: a one-word pin would pass
    against almost any prose on either side."""
    _, pin = case
    normalised = normalise(pin)
    assert len(normalised) >= 6 and len(normalised.split()) >= 2, (
        f"{pin!r}: too short to identify a statement")


# --------------------------------------------------------------------------- #
# the pin itself — both directions
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", _PINNED, ids=_id)
def test_a_pinned_statement_still_appears_in_the_core_of_its_section(case):
    """The contract half. A section reworded leaves the page asserting
    something the source of truth no longer says, on the one page every role
    reads."""
    section, pin = case
    assert normalise(pin) in normalise(_core(section)), (
        f"core/{section}: pinned statement is no longer in the section's core\n"
        f"  pinned: {pin}\n"
        f"Either the section was reworded (update core/AGENT-CONTEXT.md and "
        f"FLOOR_PINS in this file to match), or the statement only survives "
        f"under `Rationale`, which a floor copy may not deliver as a rule.")


@pytest.mark.parametrize("case", _PINNED, ids=_id)
def test_a_pinned_statement_still_appears_on_the_always_on_page(case):
    """The delivery half. The page reworded away from its section is the #194
    shape: a rule the engine does not have, read on every spawn."""
    _, pin = case
    assert normalise(pin) in normalise(_floor_text()), (
        f"core/AGENT-CONTEXT.md no longer states a pinned statement\n"
        f"  pinned: {pin}\n"
        f"Restore it in the section's wording, or — if the page deliberately "
        f"stopped delivering it — drop the pin from FLOOR_PINS in this file.")


def test_the_pins_catch_the_drift_that_earned_them():
    """The one regression this module was written for, replayed.

    Without the qualifier, the page forbade a phrase the section permits
    inside the artifact. If a later edit to the pins stops noticing that, this
    fails before the next such drift ships unobserved.

    The swap is made on the normalised page, so a reflow of those lines is
    not mistaken for the fixed wording having gone.
    """
    page = normalise(_floor_text())
    drifted = page.replace(
        normalise('"as discussed above" pointing outside the artifact'),
        normalise('"as discussed above"'))
    assert drifted != page, "the fixed wording is gone from the page"
    missing = [pin for _, pin in _PINNED if normalise(pin) not in drifted]
    assert missing, "the pre-#194 wording satisfies every pin"
