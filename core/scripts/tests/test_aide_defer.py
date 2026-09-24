"""Deferring an item, and a stage that rolls up to ⏸️ (issue #281).

A project owner deferred a whole roadmap stage and nothing in the CLI could
record it: `aide progress set` took only in-progress, in-review and done, so ⏸️
on a bullet was a hand edit with no why on the record; the rollup never
yielded ⏸️, so a deferred stage read 📋 like one nobody had started; and a
hand-set ⏸️ summary row was skipped by `aide check` without a word.

`aide progress set NNN deferred --reason …` now flips the item's bullets to ⏸️
with a dated `deferred: <reason>` trail line under each, the rollup reads ⏸️
once nothing but deferred work is left open, a ⏸️ item resumes under any
forward `set`, and `check` warns where a ⏸️ cell and the rollup disagree.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "aide.py"
_spec = importlib.util.spec_from_file_location("aide_cli_defer", _MODULE_PATH)
aide = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = aide
_spec.loader.exec_module(aide)  # type: ignore[union-attr]


PROGRESS = """\
# Demo — Progress

## Stage summary

| Stage | Title | Objectives | Status |
|-------|-------|-----------|--------|
| 1 | Rules | G1 | ✅ |
| 2 | Reports | G2 | 🚧 |

## Objective coverage

| Objective | Delivered by | Status |
|-----------|--------------|--------|
| G1 Rules | Stage 1 | ✅ |
| G2 Reports | Stage 2 | 🚧 |

## Stage 1 — Rules — ✅

**Deliverables.**
- ✅ Bounds. *(Item 027)*

**Acceptance.**
- [x] Rules fire.

## Stage 2 — Reports — 🚧

**Deliverables.**
- ✅ Summary. *(Item 030)*
- 🚧 Export, a deliverable long enough that its author
  wrapped it onto a second line. *(Item 031)*
- 📋 Charts. *(Item 032)*

**Acceptance.**
- [ ] Reports render.
"""

REASON = "owner deferred the reporting stage"


def _defer(text: str = PROGRESS, num: int = 31, reason: str = REASON,
           date: str = "2026-09-24") -> str:
    return aide.defer_item(text, num, reason, date)[0]


# --------------------------------------------------------------------------- #
# defer_item — the flip, the trail, the rollup
# --------------------------------------------------------------------------- #
def test_defer_flips_the_bullet_and_writes_the_reason_under_it():
    out = _defer().splitlines()
    i = out.index("- ⏸️ Export, a deliverable long enough that its author")
    assert out[i + 1] == "  wrapped it onto a second line. *(Item 031)*"
    assert out[i + 2] == f"  - **2026-09-24** → deferred: {REASON}"
    assert aide._parse_item_status(out)[2][31] == "deferred"


def test_defer_of_one_item_beside_open_work_rolls_the_stage_to_what_is_left():
    """🚧 031 deferred beside ✅ 030 and 📋 032: the stage is 🚧 still (a ✅
    bullet with 📋 work open), and nothing else in the file moves."""
    before = PROGRESS.splitlines()
    out = _defer().splitlines()
    assert [l for l in out if l not in before] == [
        "- ⏸️ Export, a deliverable long enough that its author",
        f"  - **2026-09-24** → deferred: {REASON}",
    ]


def test_deferring_every_open_item_moves_header_summary_and_objective_to_deferred():
    out = _defer(_defer(), 32)
    assert "## Stage 2 — Reports — ⏸️" in out
    assert "| 2 | Reports | G2 | ⏸️ |" in out
    # Every stage G2 names is ✅ or ⏸️, so the objective waits on deferred
    # work alone.
    assert "| G2 Reports | Stage 2 | ⏸️ |" in out
    # Stage 1 and its objective are untouched.
    assert "## Stage 1 — Rules — ✅" in out and "| G1 Rules | Stage 1 | ✅ |" in out


def test_a_stage_whose_last_open_item_merges_beside_a_deferred_one_reads_deferred():
    """✅ + ⏸️ is ⏸️, even though ⏸️ ranks below the 🚧 the stage held — the
    writer must follow it down, or `check` reports the drift."""
    text = _defer(PROGRESS.replace("- 📋 Charts. *(Item 032)*",
                                   "- 🚧 Charts. *(Item 032)*"))
    assert "## Stage 2 — Reports — 🚧" in text
    out = aide.set_item_status(text, 32, "complete")
    assert "## Stage 2 — Reports — ⏸️" in out
    assert "| 2 | Reports | G2 | ⏸️ |" in out
    # #173: never ✅ while a ⏸️ is held.
    assert "| 2 | Reports | G2 | ✅ |" not in out


def test_deferring_the_only_in_progress_item_rolls_the_stage_back_to_planned():
    only = PROGRESS.replace("- ✅ Summary. *(Item 030)*\n", "")
    out = _defer(only)
    assert "## Stage 2 — Reports — 📋" in out
    assert "| 2 | Reports | G2 | 📋 |" in out


def test_resuming_a_deferred_item_moves_the_stage_back_up():
    deferred = _defer(_defer(), 32)
    out = aide.set_item_status(deferred, 31, "in-progress")
    assert "- 🚧 Export, a deliverable long enough that its author" in out
    assert "## Stage 2 — Reports — 🚧" in out
    assert "| 2 | Reports | G2 | 🚧 |" in out
    assert "| G2 Reports | Stage 2 | 🚧 |" in out
    # The trail stays: the deferral is history, not state.
    assert f"  - **2026-09-24** → deferred: {REASON}" in out


@pytest.mark.parametrize("status", ["in-review", "complete"])
def test_a_deferred_item_resumes_under_any_forward_status(status):
    out = aide.set_item_status(_defer(), 31, status)
    assert aide._parse_item_status(out.splitlines())[2][31] == status


def test_defer_desugars_a_shared_marker_and_moves_only_the_named_item():
    shared = PROGRESS.replace("- 📋 Charts. *(Item 032)*",
                              "- 📋 Charts and tables. *(Items 032, 033)*")
    splits = []
    out, _ = aide.defer_item(shared, 33, "tables later", "2026-09-24", splits)
    lines = out.splitlines()
    assert "- 📋 Charts and tables. *(Item 032)*" in lines
    i = lines.index("- ⏸️ Charts and tables. *(Item 033)*")
    assert lines[i + 1] == "  - **2026-09-24** → deferred: tables later"
    assert len(splits) == 1


@pytest.mark.parametrize("icon,status,hint", [
    ("✅", "complete", "reopen"), ("❌", "excluded", "")])
def test_defer_refuses_a_finished_item_and_names_its_status(icon, status, hint):
    text = PROGRESS.replace("- 📋 Charts. *(Item 032)*", f"- {icon} Charts. *(Item 032)*")
    with pytest.raises(ValueError, match=f"item 032 is {icon} {status}") as exc:
        aide.defer_item(text, 32, "x", "2026-09-24")
    assert hint in str(exc.value)


def test_defer_refuses_when_one_of_the_items_bullets_is_done():
    two = PROGRESS.replace("- 📋 Charts. *(Item 032)*",
                           "- 📋 Charts. *(Item 032)*\n- ✅ Axes. *(Item 031)*")
    with pytest.raises(ValueError, match="complete"):
        aide.defer_item(two, 31, "x", "2026-09-24")


def test_defer_refuses_an_item_no_bullet_names():
    with pytest.raises(ValueError, match="nothing to defer"):
        aide.defer_item(PROGRESS, 99, "x", "2026-09-24")


def test_deferring_a_deferred_item_again_is_no_change():
    once = _defer()
    again, message = aide.defer_item(once, 31, "again", "2026-09-30")
    assert again == once
    assert "no change" in message


@pytest.mark.parametrize("icon", ["📋", "🔍"])
def test_defer_takes_planned_and_in_review_items(icon):
    text = PROGRESS.replace("- 📋 Charts. *(Item 032)*", f"- {icon} Charts. *(Item 032)*")
    out = _defer(text, 32)
    assert "- ⏸️ Charts. *(Item 032)*" in out


def test_a_hand_set_deferred_stage_is_left_alone_by_a_set_elsewhere():
    """⏸️ set by hand over a stage whose bullets say 🚧 is the owner's intent
    until a verb moves that stage's bullets; `check` names the disagreement."""
    hand = PROGRESS.replace("## Stage 2 — Reports — 🚧", "## Stage 2 — Reports — ⏸️")
    hand = hand.replace("| 2 | Reports | G2 | 🚧 |", "| 2 | Reports | G2 | ⏸️ |")
    hand = hand.replace("| G2 Reports | Stage 2 | 🚧 |", "| G2 Reports | Stage 2 | ⏸️ |")
    other = hand.replace("- ✅ Bounds. *(Item 027)*", "- 🚧 Bounds. *(Item 027)*")
    other = other.replace("## Stage 1 — Rules — ✅", "## Stage 1 — Rules — 🚧")
    other = other.replace("| 1 | Rules | G1 | ✅ |", "| 1 | Rules | G1 | 🚧 |")
    out = aide.set_item_status(other, 27, "complete")
    assert "## Stage 2 — Reports — ⏸️" in out
    assert "| 2 | Reports | G2 | ⏸️ |" in out
    assert "| G2 Reports | Stage 2 | ⏸️ |" in out
    # A set on the stage's own bullet is the owner's next decision about it.
    moved = aide.set_item_status(out, 32, "in-progress")
    assert "## Stage 2 — Reports — 🚧" in moved
    assert "| 2 | Reports | G2 | 🚧 |" in moved
    assert "| G2 Reports | Stage 2 | 🚧 |" in moved


PRE_25 = """\
# Demo — Progress

## Stage summary

| Stage | Title | Objectives | Status |
|-------|-------|-----------|--------|
| 2 | Reports | G1 | 🚧 |
| 4 | Charts | G1 | 📋 |
| 5 | Other | G2 | 📋 |

## Objective coverage

| Objective | Delivered by | Status |
|-----------|--------------|--------|
| G1 Reports | Stage 2, Stage 4 | {g1} |
| G2 Other | Stage 5 | 📋 |

## Stage 2 — Reports — 🚧

**Deliverables.**
- ✅ Summary. *(Item 030)*
- ⏸️ Export. *(Item 031)*

## Stage 4 — Charts — 📋

**Deliverables.**
- 📋 Charts. *(Item 040)*

## Stage 5 — Other — 📋

**Deliverables.**
- 📋 Other. *(Item 050)*
"""


def test_an_objective_follows_a_stage_that_self_heals_to_deferred():
    """PR #284 review: a pre-2.5.0 file with a ✅+⏸️ stage still under 🚧. A
    `set` for an unrelated stage's item heals that stage to ⏸️; the Objective
    row over it and a 📋 stage must follow down to what the rollup of those
    two says — 📋 — rather than stay 🚧 over stages that no longer say so."""
    out = aide.set_item_status(PRE_25.format(g1="🚧"), 50, "in-progress")
    assert "## Stage 2 — Reports — ⏸️" in out
    assert "| 2 | Reports | G1 | ⏸️ |" in out
    assert "| G1 Reports | Stage 2, Stage 4 | 📋 |" in out
    assert "| G2 Other | Stage 5 | 🚧 |" in out


def test_the_self_heal_leaves_a_hand_set_deferred_objective_alone():
    """The promotion frees the downgrade, not the hand-held ⏸️: no verb moved
    a bullet of stage 2 or 4, so the owner's ⏸️ on G1 stands."""
    out = aide.set_item_status(PRE_25.format(g1="⏸️"), 50, "in-progress")
    assert "## Stage 2 — Reports — ⏸️" in out
    assert "| G1 Reports | Stage 2, Stage 4 | ⏸️ |" in out


# --------------------------------------------------------------------------- #
# check — the ⏸️ rule (ask 3)
# --------------------------------------------------------------------------- #
AIDE_TOML = '[project]\nname = "Demo"\ndocs_dir = "docs/aide"\n'


def _repo(tmp_path: Path, progress: str = PROGRESS, name: str = "repo") -> Path:
    repo = tmp_path / name
    ddir = repo / "docs" / "aide"
    ddir.mkdir(parents=True)
    (repo / "aide.toml").write_text(AIDE_TOML, encoding="utf-8")
    (ddir / "progress.md").write_text(progress, encoding="utf-8")
    (ddir / "insights.md").write_text("# Insight Inbox\n", encoding="utf-8")
    return repo


def _checks(repo: Path):
    return aide.run_checks(repo, aide.load_config(repo), branches=[])


def test_a_hand_set_deferred_summary_over_open_bullets_is_a_warning(tmp_path: Path):
    """The issue's own file: a stage deferred by hand, its bullets still 📋 /
    🚧 — silently accepted until 2.5.0."""
    hand = PROGRESS.replace("## Stage 2 — Reports — 🚧", "## Stage 2 — Reports — ⏸️")
    hand = hand.replace("| 2 | Reports | G2 | 🚧 |", "| 2 | Reports | G2 | ⏸️ |")
    errors, warnings = _checks(_repo(tmp_path, hand))
    assert errors == []
    hits = [w for w in warnings if w.startswith("stage 2:")]
    assert len(hits) == 1, warnings
    assert "summary ⏸️ deferred and header ⏸️ deferred" in hits[0]
    assert "roll up to 🚧 in-progress" in hits[0]
    assert "aide progress set NNN deferred --reason" in hits[0]


def test_a_stage_rolling_up_to_deferred_under_a_lesser_summary_is_a_warning(
        tmp_path: Path):
    """The reverse: bullets hand-edited to ⏸️, cells left 🚧."""
    hand = PROGRESS.replace("- 🚧 Export, a", "- ⏸️ Export, a")
    hand = hand.replace("- 📋 Charts.", "- ⏸️ Charts.")
    _, warnings = _checks(_repo(tmp_path, hand))
    hits = [w for w in warnings if w.startswith("stage 2:")]
    assert len(hits) == 1, warnings
    assert "summary 🚧 in-progress and header 🚧 in-progress" in hits[0]
    assert "roll up to ⏸️ deferred" in hits[0]


def test_an_excluded_summary_row_is_still_left_out(tmp_path: Path):
    hand = PROGRESS.replace("| 2 | Reports | G2 | 🚧 |", "| 2 | Reports | G2 | ❌ |")
    _, warnings = _checks(_repo(tmp_path, hand))
    assert not [w for w in warnings if w.startswith("stage 2:")], warnings


def test_a_file_the_verbs_wrote_raises_no_warning(tmp_path: Path, capsys):
    """Defer, merge the last open item beside it, resume: `check` says nothing
    about the stage at any step."""
    repo = _repo(tmp_path)
    path = repo / "docs" / "aide" / "progress.md"

    def stage_warnings():
        errors, warnings = _checks(repo)
        assert errors == []
        return [w for w in warnings if w.startswith("stage ")]

    base = ["--repo", str(repo), "progress", "set"]
    assert aide.main([*base, "31", "deferred", "--reason", REASON, "--no-commit"]) == 0
    assert stage_warnings() == []
    assert aide.main([*base, "32", "done", "--no-commit"]) == 0
    assert "## Stage 2 — Reports — ⏸️" in path.read_text(encoding="utf-8")
    assert stage_warnings() == []
    assert aide.main([*base, "31", "in-progress", "--no-commit"]) == 0
    assert "## Stage 2 — Reports — 🚧" in path.read_text(encoding="utf-8")
    assert stage_warnings() == []


# --------------------------------------------------------------------------- #
# the CLI — refusals
# --------------------------------------------------------------------------- #
def test_set_deferred_refuses_without_a_stated_reason_and_writes_nothing(
        tmp_path: Path, capsys):
    repo = _repo(tmp_path)
    before = (repo / "docs" / "aide" / "progress.md").read_bytes()
    for extra in ([], ["--reason", "   "], ["--reason", "two\nlines"]):
        assert aide.main(["--repo", str(repo), "progress", "set", "31",
                          "deferred", *extra, "--no-commit"]) == 2, extra
    assert "--reason is required" in capsys.readouterr().err
    assert (repo / "docs" / "aide" / "progress.md").read_bytes() == before


def test_set_deferred_refuses_a_criterion_or_all_and_writes_nothing(
        tmp_path: Path):
    """An item is deferred whole, as it is reopened whole."""
    repo = _repo(tmp_path)
    before = (repo / "docs" / "aide" / "progress.md").read_bytes()
    assert aide.main(["--repo", str(repo), "progress", "set", "31", "deferred",
                      "--criterion", "1", "--reason", "x", "--no-commit"]) == 2
    assert aide.main(["--repo", str(repo), "progress", "set", "31", "deferred",
                      "--all", "--reason", "x", "--no-commit"]) == 2
    assert (repo / "docs" / "aide" / "progress.md").read_bytes() == before


def test_set_deferred_on_a_done_item_exits_one_and_writes_nothing(
        tmp_path: Path, capsys):
    repo = _repo(tmp_path)
    before = (repo / "docs" / "aide" / "progress.md").read_bytes()
    assert aide.main(["--repo", str(repo), "progress", "set", "30", "deferred",
                      "--reason", "x", "--no-commit"]) == 1
    err = capsys.readouterr().err
    assert "item 030 is ✅ complete" in err and "reopen" in err
    assert "NOT changed" in err
    assert (repo / "docs" / "aide" / "progress.md").read_bytes() == before
    # No insight is captured by a deferral, refused or not.
    assert (repo / "docs" / "aide" / "insights.md").read_text(
        encoding="utf-8") == "# Insight Inbox\n"


def test_set_deferred_writes_no_insight(tmp_path: Path):
    repo = _repo(tmp_path)
    assert aide.main(["--repo", str(repo), "progress", "set", "31", "deferred",
                      "--reason", REASON, "--date", "2026-09-24",
                      "--no-commit"]) == 0
    text = (repo / "docs" / "aide" / "progress.md").read_text(encoding="utf-8")
    assert f"  - **2026-09-24** → deferred: {REASON}" in text
    assert (repo / "docs" / "aide" / "insights.md").read_text(
        encoding="utf-8") == "# Insight Inbox\n"


def test_set_rejects_an_unknown_status_naming_deferred(tmp_path: Path, capsys):
    repo = _repo(tmp_path)
    assert aide.main(["--repo", str(repo), "progress", "set", "31", "paused",
                      "--no-commit"]) == 2
    assert "'deferred'" in capsys.readouterr().err
