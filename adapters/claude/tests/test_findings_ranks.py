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
