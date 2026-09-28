"""The reviewer ranks only the calls that still prompt (issue #316).

Coverage is decided per call, before calls are grouped by their normalised
rule: a multi-word allow rule such as ``Bash(sed -n:*)`` normalises to the same
``Bash(sed:*)`` as the ``sed -i`` calls it leaves prompting, so grouping first
ranked the allowed traffic, counted it, and showed it as the row's sample.

Stdlib + pytest only; the reviewer script is imported as a module.
"""
from __future__ import annotations

import sys
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = FRAMEWORK_ROOT / "adapters" / "claude" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))
import review_permissions as rp  # noqa: E402  (path shim above)


def _call(detail, outcome="granted", tool="Bash"):
    return {"session_id": "s", "tool": tool, "detail": detail, "outcome": outcome}


def _rows(rows, status):
    return [r for r in rows if r["status"] == status]


def test_calls_a_multi_word_allow_rule_covers_are_not_ranked():
    calls = [_call(f"sed -n '{i},40p' docs/aide/progress.md") for i in range(10)]
    calls.append(_call("sed -i 's/a/b/' src/x.py", outcome="denied"))

    rows = rp.aggregate(calls, ["Bash(sed -n:*)"], [])

    new = _rows(rows, "new")
    assert len(new) == 1
    assert new[0]["rule"] == "Bash(sed:*)"
    assert new[0]["total"] == 1
    assert (new[0]["granted"], new[0]["denied"]) == (0, 1)
    assert new[0]["sample"] == "sed -i 's/a/b/' src/x.py"


def test_the_covered_calls_are_tallied_apart_as_context():
    calls = [_call("sed -n 1p a.md")] * 10 + [_call("sed -i x b.md")]

    rows = rp.aggregate(calls, ["Bash(sed -n:*)"], [])

    allowed = _rows(rows, "auto-allowed")
    assert len(allowed) == 1
    assert allowed[0]["total"] == 10
    assert allowed[0]["sample"] == "sed -n 1p a.md"
    # A new row outranks the allowed context however large the context is.
    assert rows[0]["status"] == "new"


def test_a_rule_whose_calls_are_all_covered_has_no_new_row():
    rows = rp.aggregate([_call("git status"), _call("git status -sb")],
                        ["Bash(git status:*)"], [])

    assert [r["status"] for r in rows] == ["auto-allowed"]
    assert rows[0]["total"] == 2


def test_an_ask_rule_wins_over_an_allow_rule_that_also_covers_the_call():
    # `git push --force` matches both lists; the runtime prompts, so it is not
    # dropped as covered.
    calls = [_call("git push origin x"), _call("git push --force origin x")]

    rows = rp.aggregate(calls, ["Bash(git push:*)"], ["Bash(git push --force:*)"])

    gated = _rows(rows, "ask-gated")
    assert len(gated) == 1
    assert gated[0]["total"] == 1
    assert gated[0]["sample"] == "git push --force origin x"
    assert _rows(rows, "auto-allowed")[0]["total"] == 1
    assert not _rows(rows, "new")


def test_an_uncovered_rule_with_no_ask_match_is_new():
    rows = rp.aggregate([_call("make build")], ["Bash(git status:*)"], [])

    assert [(r["status"], r["rule"], r["total"]) for r in rows] == [
        ("new", "Bash(make:*)", 1)
    ]
