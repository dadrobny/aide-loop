"""The adapter and the engine agree on what a review finding's ranks are.

`aide merge --findings blocking=A,minor=B,nit=C` parses exactly the ranks in
`LEDGER_FINDING_RANKS` and rejects anything else as a usage error (§1 →
ledger.md). The names therefore live in two trees at once: the engine's parser,
and the adapter files that teach a role to classify a finding and hand the
counts over — `commands/aide-run-item.md`, which triages and merges, and
`agents/reviewer.md`, which proposes a rank. A rank renamed on one side is not
a syntax error on the other; it is an orchestrator emitting a command the
engine refuses, at the one moment the counts still exist.

This module reads the rank names from `core/scripts/aide.py` itself rather than
spelling them a third time, so it cannot be the copy that drifts. It asserts
the *vocabulary*, not the prose: what each rank means for the loop is §9's, and
§9 reaches the reviewer as a generated skill (`test_generated_delivery.py`).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ADAPTER = _HERE.parent
_REPO = _ADAPTER.parents[1]

_spec = importlib.util.spec_from_file_location(
    "aide_cli_findings_ranks", _REPO / "core" / "scripts" / "aide.py")
aide = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = aide
_spec.loader.exec_module(aide)  # type: ignore[union-attr]

_RANKS = aide.LEDGER_FINDING_RANKS
#: The cell the engine writes where no reviewer ran — read from the engine for
#: the same reason the ranks are: the orchestrator's prose is the copy.
_MARK = aide.LEDGER_NO_REVIEW_CELL

_RUN_ITEM = _ADAPTER / "commands" / "aide-run-item.md"
_REVIEWER = _ADAPTER / "agents" / "reviewer.md"
_SECTION = _REPO / "core" / "conventions" / "9-review-and-validation.md"

#: The held merge the orchestrator runs itself, wrapped or not: `--findings`
#: with its rank=placeholder list, on the same command as `merge NNN`.
_FINDINGS_CALL = re.compile(
    r"aide\.py merge NNN[^\n]*(?:\\\s*\n\s*)?[^\n]*--findings\s+(\S+)")


def test_the_engine_names_three_ranks():
    """The guard on the guard: every assertion below is vacuous against an
    empty tuple, and one that shrank to a single rank would pass them all."""
    assert len(_RANKS) == 3, _RANKS
    assert set(_RANKS) == {"blocking", "minor", "nit"}, _RANKS


def test_the_orchestrator_passes_findings_to_the_merge_it_runs():
    """The counts reach the ledger row only through this call. Without it the
    orchestrator triages findings it then throws away, and the row's three
    cells are blank on every reviewed item."""
    text = _RUN_ITEM.read_text(encoding="utf-8")
    match = _FINDINGS_CALL.search(text)
    assert match, (
        f"{_RUN_ITEM.name} runs `aide merge NNN` without --findings — the "
        "ranks it triaged reach the ledger row nowhere else")
    argument = match.group(1)
    for rank in _RANKS:
        assert f"{rank}=" in argument, (
            f"{_RUN_ITEM.name}: --findings {argument} omits '{rank}=' — "
            f"the engine parses {', '.join(_RANKS)} and refuses the rest")


def test_the_orchestrator_names_every_rank_it_triages_on():
    """Passing the flag is not enough: the step that classifies findings has
    to name the three, or the counts are made up at the merge."""
    text = _RUN_ITEM.read_text(encoding="utf-8").lower()
    missing = [rank for rank in _RANKS if rank not in text]
    assert not missing, f"{_RUN_ITEM.name} never names {missing}"


def test_the_reviewer_asks_for_a_rank_on_each_finding():
    """The orchestrator's triage is the call, but it triages what it was
    handed: a reviewer that reports no rank makes every count a re-read."""
    text = _REVIEWER.read_text(encoding="utf-8").lower()
    assert "rank" in text
    assert "§9" in _REVIEWER.read_text(encoding="utf-8"), (
        "reviewer.md proposes a rank without pointing at the section that "
        "defines the scale — the definitions belong there, not here")


def test_the_section_defines_the_ranks_the_engine_parses():
    """The other end of the same vocabulary. §9 is generated into
    `skills/aide-review-and-validation`, so a rank defined here is a rank the
    reviewer and every other role that delivers §9 reads."""
    core = _SECTION.read_text(encoding="utf-8").split("### Rationale")[0].lower()
    missing = [rank for rank in _RANKS if rank not in core]
    assert not missing, f"§9's core defines no rank named {missing}"


# --------------------------------------------------------------------------- #
# what the orchestrator does with each rank — the half the engine cannot check
# --------------------------------------------------------------------------- #
def _bullet(text: str, opener: str) -> str:
    """One `- **…**` bullet of step 6, from *opener* to the next bullet at the
    same indent. Returned lower-cased and on one line, with markdown emphasis
    and code ticks dropped, so an assertion below is about the words and not
    the setting or the wrapping."""
    start = text.index(opener)
    rest = text[start + len(opener):]
    indent = "\n" + " " * (start - text.rindex("\n", 0, start) - 1) + "- "
    end = rest.find(indent)
    body = opener + (rest if end < 0 else rest[:end])
    return " ".join(body.translate(str.maketrans("", "", "*`_")).split()).lower()


def test_a_nit_only_fix_skips_both_gates_and_costs_no_round():
    """§9's rank is only worth writing down if the loop acts on it. The nit
    bullet has to say all three things — dispatch it, run neither gate behind
    it, and add nothing to the count — because any two of them without the
    third describe a different behaviour: a nit nobody fixes, a nit that pays
    for a validation round, or a nit that quietly re-enters the cycle."""
    bullet = _bullet(_RUN_ITEM.read_text(encoding="utf-8"), "- **Nit, in scope**")
    assert "builder" in bullet, bullet
    assert "no validator" in bullet and "no reviewer" in bullet, bullet
    assert "round" in bullet, bullet
    # And the blocking bullet still buys one, or the distinction is empty.
    blocking = _bullet(_RUN_ITEM.read_text(encoding="utf-8"),
                       "- **Blocking, in scope**")
    assert "validator" in blocking and "no validator" not in blocking, blocking


def test_the_counts_passed_to_the_merge_are_in_scope_findings_only():
    """An out-of-scope finding is carried by its `insights.md` line (§9). A
    brief that does not say so invites the one row that cannot be read back:
    counts that include findings the item never paid for."""
    text = _RUN_ITEM.read_text(encoding="utf-8").lower()
    call = text.index("--findings blocking=")
    tail = text[call:call + 1200]
    assert "in-scope findings only" in tail, tail[:400]


def test_the_unreviewed_row_is_described_as_marked_and_not_as_blank():
    """The engine writes `LEDGER_NO_REVIEW_CELL` where `[loop] review` is off,
    so an orchestrator told those cells are *blank* would be reading the row
    it merged wrongly — and a blank there now means something else entirely
    (a count that should have been passed)."""
    text = _RUN_ITEM.read_text(encoding="utf-8")
    para = next(p for p in text.split("\n\n")
                if "never passes `--findings`" in p)
    assert _MARK in para, para
    flat = " ".join(para.split())
    assert "cells are left blank" not in flat and "rather than zeroed" not in flat, flat


def test_the_reviewer_carries_the_rank_onto_the_out_of_scope_line():
    """The rank travels as the first word of the entry's free text (§9), which
    is the only place an out-of-scope finding's triage survives: the row it
    would have been counted in is never written for it."""
    text = _REVIEWER.read_text(encoding="utf-8").lower()
    assert "rank" in text.split("out-of-scope insights")[-1], (
        "reviewer.md's insights section never says the rank opens the line")
