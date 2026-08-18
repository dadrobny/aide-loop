"""Tests for `## Human gates` — a decision only a person can make, blocking work.

Kept separate from acceptance boxes deliberately: conventions.md §1 defines
those as observable checks *of the built thing*, which a steering decision is
not. Same reasoning that gave Outcome targets their own table.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "aide.py"
_spec = importlib.util.spec_from_file_location("aide_cli_gates", _MODULE_PATH)
aide = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = aide
_spec.loader.exec_module(aide)  # type: ignore[union-attr]


def _progress(rows: str, stage_status: str = "🚧") -> str:
    return f"""\
# Demo — Progress

## Stage summary

| Stage | Title | Objectives | Status |
|-------|-------|-----------|--------|
| 1 | Rules | G1 | {stage_status} |

## Objective coverage

| Objective | Delivered by | Status |
|-----------|--------------|--------|
| G1 Rules | Stage 1 | {stage_status} |

## Human gates

| Gate | Blocks | Status | Decision / evidence |
|------|--------|--------|---------------------|
{rows}

## Stage 1 — Rules — {stage_status}

**Deliverables.**
- 📋 A. *(Item 027)*
- 📋 B. *(Item 028)*

**Acceptance.**
- [ ] Rules fire.
"""


AWAITING = "| Golden retirement approved | 028 | ⏳ Awaiting | — |"
APPROVED = "| Golden retirement approved | 028 | ✅ Approved (2026-08-18) | ok |"
BARRIER = "| Real segmenter output arrived | queue | ⏳ Awaiting | — |"


def _lines(rows: str):
    return _progress(rows).splitlines()


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def test_parses_a_gate_row():
    g = aide.human_gates(_lines(AWAITING))[0]
    assert g.text == "Golden retirement approved"
    assert g.blocks == [28] and g.barrier is False and g.kind == "awaiting"


def test_bare_numbers_in_blocks_are_parsed():
    """A column headed "Blocks" invites bare numbers. The shared extractor keys
    off the word "Item", so without normalisation this parses as nothing — and
    a gate blocking nothing is a gate that silently does not work."""
    rows = "| G | 106, 110–112 | ⏳ Awaiting | — |"
    assert aide.human_gates(_lines(rows))[0].blocks == [106, 110, 111, 112]


def test_item_reference_form_also_parsed():
    rows = "| G | Items 106, 108 | ⏳ Awaiting | — |"
    assert aide.human_gates(_lines(rows))[0].blocks == [106, 108]


def test_queue_barrier_is_recognised():
    g = aide.human_gates(_lines(BARRIER))[0]
    assert g.barrier is True and g.blocks == []


def test_no_table_is_no_gates():
    text = _progress(AWAITING).replace("## Human gates", "## Something else")
    assert aide.human_gates(text.splitlines()) == []


def test_header_and_separator_rows_are_skipped():
    assert len(aide.human_gates(_lines(AWAITING))) == 1


def test_table_ends_at_the_next_heading():
    """A deliverable bullet after the table must not be read as a gate row."""
    assert len(aide.human_gates(_lines(f"{AWAITING}\n{BARRIER}"))) == 2


# --------------------------------------------------------------------------- #
# resolution semantics
# --------------------------------------------------------------------------- #
def test_approved_gate_is_resolved():
    assert aide.blocking_gates(_lines(APPROVED)) == []


def test_declined_keeps_blocking():
    """A refusal is *resolved* — a person decided — but the decision was "no",
    so releasing the work would run exactly what was refused. Only approval
    opens a gate; the remedy for a decline is to re-plan."""
    rows = "| G | 028 | ❌ Declined (2026-08-18) | keep v0 |"
    pending = aide.blocking_gates(_lines(rows))
    assert len(pending) == 1 and pending[0].kind == "declined"
    blocked, _ = aide.gate_blocked_items(_lines(rows))
    assert blocked == {28}


def test_declined_warning_says_it_still_blocks():
    rows = "| G | 028 | ❌ Declined (2026-08-18) | keep v0 |"
    w = aide.gate_warnings(_lines(rows))[0]
    assert "DECLINED" in w and "still blocks" in w


def test_unrecognised_status_stays_unresolved():
    """A typo in the mark must not silently open a gate."""
    rows = "| G | 028 | approved-ish | — |"
    pending = aide.blocking_gates(_lines(rows))
    assert len(pending) == 1 and pending[0].kind is None


def test_gate_blocked_items_splits_named_from_barrier():
    blocked, barriers = aide.gate_blocked_items(_lines(f"{AWAITING}\n{BARRIER}"))
    assert blocked == {28}
    assert len(barriers) == 1


def test_approved_gate_blocks_nothing():
    blocked, barriers = aide.gate_blocked_items(_lines(APPROVED))
    assert blocked == set() and barriers == []


# --------------------------------------------------------------------------- #
# warnings
# --------------------------------------------------------------------------- #
def test_awaiting_gate_warns_with_its_reach():
    w = aide.gate_warnings(_lines(AWAITING))
    assert len(w) == 1 and "items 028" in w[0]


def test_barrier_warning_says_whole_queue():
    assert "the whole queue" in aide.gate_warnings(_lines(BARRIER))[0]


def test_unrecognised_status_warns_about_the_vocabulary():
    rows = "| G | 028 | approved-ish | — |"
    assert "unrecognised status" in aide.gate_warnings(_lines(rows))[0]


def test_resolved_gates_are_silent():
    assert aide.gate_warnings(_lines(APPROVED)) == []


def test_gate_naming_nothing_is_called_out():
    """A gate that blocks nothing is inert; say so rather than look busy."""
    rows = "| G | — | ⏳ Awaiting | — |"
    assert "nothing named" in aide.gate_warnings(_lines(rows))[0]


# --------------------------------------------------------------------------- #
# set_gate_status
# --------------------------------------------------------------------------- #
def test_approve_writes_mark_date_and_note():
    out = aide.set_gate_status(_progress(AWAITING), 1, "approved",
                               "reviewed with maintainer", today="2026-08-18")
    row = next(l for l in out.splitlines() if "Golden retirement" in l and "|" in l)
    assert "✅ Approved (2026-08-18)" in row
    assert "reviewed with maintainer" in row
    assert aide.blocking_gates(out.splitlines()) == []


def test_decline_is_recorded_distinctly():
    out = aide.set_gate_status(_progress(AWAITING), 1, "declined", "not now",
                               today="2026-08-18")
    assert "❌ Declined (2026-08-18)" in out
    assert aide.human_gates(out.splitlines())[0].kind == "declined"


def test_out_of_range_index_raises():
    import pytest
    with pytest.raises(ValueError, match="out of range"):
        aide.set_gate_status(_progress(AWAITING), 5, "approved")


def test_missing_table_raises():
    import pytest
    text = _progress(AWAITING).replace("## Human gates", "## Other")
    with pytest.raises(ValueError, match="no '## Human gates' table"):
        aide.set_gate_status(text, 1, "approved")


def test_other_rows_are_untouched():
    out = aide.set_gate_status(_progress(f"{AWAITING}\n{BARRIER}"), 1, "approved",
                               today="2026-08-18")
    gates = aide.human_gates(out.splitlines())
    assert gates[0].kind == "approved"
    assert gates[1].kind == "awaiting" and gates[1].barrier is True


def test_gate_table_does_not_disturb_the_stage_rollup():
    """The gates table sits in progress.md beside the tables the rollup reads;
    it must not be mistaken for one of them."""
    text = _progress(AWAITING)
    statuses = aide._parse_item_status(text.splitlines())[2]
    assert statuses.get(27) == "planned" and statuses.get(28) == "planned"


# --------------------------------------------------------------------------- #
# end to end — claim refuses, gate verb resolves, claim proceeds
# --------------------------------------------------------------------------- #
AIDE_TOML = '[project]\nname = "Demo"\ndocs_dir = "docs/aide"\n\n[git]\nmode = "local"\nmain_branch = "main"\nbranch_prefix = "aide/"\n'
QUEUE = "# Demo — Work Queue 003\n\n### Item 027: Alpha\nA.\n\n### Item 028: Beta\nB.\n"


def _run(args, cwd):
    return subprocess.run(args, cwd=str(cwd), check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _repo(tmp_path: Path, rows: str) -> Path:
    repo = tmp_path / "repo"
    d = repo / "docs" / "aide"
    (d / "queue").mkdir(parents=True)
    (repo / "aide.toml").write_text(AIDE_TOML, encoding="utf-8")
    (d / "progress.md").write_text(_progress(rows), encoding="utf-8")
    (d / "queue" / "queue-003.md").write_text(QUEUE, encoding="utf-8")
    _run(["git", "init", "-b", "main"], repo)
    _run(["git", "config", "user.email", "t@e.com"], repo)
    _run(["git", "config", "user.name", "T"], repo)
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "init"], repo)
    return repo


def test_claim_skips_a_gated_item_and_offers_the_next(tmp_path: Path, capsys):
    """Item-scoped by default: the queue keeps producing work. Only the items
    a gate names wait for it."""
    repo = _repo(tmp_path, AWAITING)          # blocks 028 only
    assert aide.main(["--repo", str(repo), "claim", "--dry-run"]) == 0
    assert "item 027" in capsys.readouterr().out


def test_barrier_gate_stops_the_whole_queue(tmp_path: Path, capsys):
    """A decision that could invalidate downstream work must not have the loop
    racing ahead of it."""
    repo = _repo(tmp_path, BARRIER)
    assert aide.main(["--repo", str(repo), "claim", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "held by an unresolved human gate" in out
    assert "blocks the whole queue" in out
    assert "item 027" not in out


def test_gate_list_numbers_the_rows(tmp_path: Path, capsys):
    repo = _repo(tmp_path, f"{AWAITING}\n{BARRIER}")
    assert aide.main(["--repo", str(repo), "gate", "list"]) == 0
    out = capsys.readouterr().out
    assert "1. ⏳" in out and "2. ⏳" in out
    assert "2 gate(s), 2 still blocking" in out


def test_approving_a_barrier_releases_the_queue(tmp_path: Path, capsys):
    repo = _repo(tmp_path, BARRIER)
    assert aide.main(["--repo", str(repo), "gate", "approve", "1",
                      "--evidence", "data landed", "--no-commit"]) == 0
    capsys.readouterr()
    assert aide.main(["--repo", str(repo), "claim", "--dry-run"]) == 0
    assert "item 027" in capsys.readouterr().out


def test_gate_check_reports_the_outstanding_gate(tmp_path: Path):
    repo = _repo(tmp_path, AWAITING)
    _, warnings = aide.run_checks(repo, aide.load_config(repo))
    assert any("awaiting a decision" in w for w in warnings)


def test_gate_out_of_range_is_an_error_not_a_noop(tmp_path: Path, capsys):
    repo = _repo(tmp_path, AWAITING)
    assert aide.main(["--repo", str(repo), "gate", "approve", "9", "--no-commit"]) == 2
    assert "out of range" in capsys.readouterr().err


def test_a_queue_branch_does_not_make_an_item_unclaimable(tmp_path: Path, capsys):
    """`aide/queue-027` is a queue branch, not a claim on item 027. The old
    unanchored search read the trailing digits as an item number and marked it
    permanently claimed — the 1.5.0 bug class, at the one call site that sweep
    missed."""
    repo = _repo(tmp_path, "| G | 999 | ⏳ Awaiting | — |")   # gate blocks nothing real
    _run(["git", "switch", "-c", "aide/queue-027"], repo)
    assert aide.main(["--repo", str(repo), "claim", "--dry-run"]) == 0
    assert "item 027" in capsys.readouterr().out


def test_a_real_claim_branch_still_marks_its_item_claimed(tmp_path: Path, capsys):
    repo = _repo(tmp_path, "| G | 999 | ⏳ Awaiting | — |")
    _run(["git", "switch", "-c", "aide/027-alpha"], repo)
    assert aide.main(["--repo", str(repo), "claim", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "item 028" in out and "item 027" not in out


def test_gate_approve_without_a_number_reports_rather_than_crashing(tmp_path: Path, capsys):
    repo = _repo(tmp_path, AWAITING)
    assert aide.main(["--repo", str(repo), "gate", "approve", "--no-commit"]) == 2
    assert "needs a gate number" in capsys.readouterr().err
