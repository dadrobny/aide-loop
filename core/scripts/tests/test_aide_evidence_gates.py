"""A human gate as an acceptance criterion's evidence (issue #420).

conventions.md §1 → items.md: a criterion no loop-run test can measure names
the gate whose approval stands in for its test, `*(evidence: gate-<hex>)*` on
its line. §1 → human gates: that gate blocks nothing — its Blocks cell is `—`
— and `aide check` words it as the check it records. §9: approved covers the
criterion, awaiting holds it, declined fails it; `aide merge` refuses the item
until every such gate is approved.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "aide.py"
_spec = importlib.util.spec_from_file_location("aide_cli_evidence", _MODULE_PATH)
aide = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = aide
_spec.loader.exec_module(aide)  # type: ignore[union-attr]


AIDE_TOML = """\
[project]
name = "Demo"
docs_dir = "docs/aide"

[git]
mode = "{mode}"
main_branch = "main"
branch_prefix = "aide/"
"""

PROGRESS = """\
# Demo — Progress

## Stage summary

| Stage | Title | Objectives | Status |
|-------|-------|-----------|--------|
| 1 | Rules | G1 | 📋 |

## Objective coverage

| Objective | Delivered by | Status |
|-----------|--------------|--------|
| G1 Rules | Stage 1 | 📋 |

## Stage 1 — Rules — 📋

**Deliverables.**
- 📋 Dialog. *(Item 027)*
- 📋 Other. *(Item 028)*

**Acceptance.**
- [ ] Rules fire.
"""

QUEUE = "# Demo — Work Queue 003\n\n### Item 027: Dialog\nA.\n\n### Item 028: Other\nB.\n"

QUESTION = "Item 027's settings dialog keeps its layout at 200% zoom"


def _spec(ac2: str) -> str:
    return (
        "# Item 027 — Dialog\n\n"
        "## Acceptance Criteria\n\n"
        "- [ ] **AC1: saves.** The dialog's values are written.\n"
        f"- [ ] **AC2: layout.** {ac2}\n\n"
        "## Assumptions\n\n"
        "- **A1:** the dialog lives in the sibling GUI repo, whose own rules\n"
        "  allow no loop-run test of it, so AC2 is checked by hand.\n")


def _run(args, cwd):
    return subprocess.run(args, cwd=str(cwd), check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          encoding="utf-8")


def _gate_id(progress: str, question: str = QUESTION) -> str:
    gates = aide.human_gates(progress.splitlines())
    ids = aide.gate_ids(gates)
    return next(i for g, i in zip(gates, ids) if g.text == question)


def _with_gate(text: str, status: str = "⏳ Awaiting", blocks: str = "—",
               question: str = QUESTION) -> str:
    text = aide.add_gate_rows(text, [(question, blocks)])
    return text.replace(f"| {question} | {blocks} | ⏳ Awaiting |",
                        f"| {question} | {blocks} | {status} |")


def _docs(tmp_path: Path, progress: str, spec: str, mode: str = "local") -> Path:
    repo = tmp_path / "repo"
    d = repo / "docs" / "aide"
    (d / "queue").mkdir(parents=True)
    (d / "items").mkdir()
    (repo / "aide.toml").write_text(AIDE_TOML.format(mode=mode), encoding="utf-8")
    (d / "progress.md").write_text(progress, encoding="utf-8")
    (d / "queue" / "queue-003.md").write_text(QUEUE, encoding="utf-8")
    (d / "items" / "027-dialog.md").write_text(spec, encoding="utf-8")
    return repo


def _warnings(repo: Path):
    return aide.run_checks(repo, aide.load_config(repo))


# --------------------------------------------------------------------------- #
# the annotation's grammar
# --------------------------------------------------------------------------- #
def test_the_annotation_is_read_per_criterion_from_the_acceptance_criteria():
    text = (
        "# Item 027 — Dialog\n\n"
        "## Description\n\nSee (evidence: gate-aaaa) — prose, not a criterion.\n\n"
        "## Acceptance Criteria\n\n"
        "- [ ] **AC1: saves.** Written. *(evidence: gate-1234)*\n"
        "- [ ] **AC2: layout.** Keeps its layout,\n"
        "  checked by hand *(Evidence:  gate-abcdef12 )*\n"
        "- [ ] AC3: tested. *(closes Stage 1 criterion 1)*\n"
        "- [ ] Unnumbered. (evidence: gate-beef)\n"
        "- [ ] AC4: upper hex is no ID. *(evidence: gate-ABCD)*\n\n"
        "## Assumptions\n\n- (evidence: gate-cccc)\n")
    cited, malformed = aide.spec_evidence_annotations(text)
    assert cited == [(1, "gate-1234"), (2, "gate-abcdef12"), (None, "gate-beef")]
    assert aide.spec_evidence_gates(text) == cited
    assert malformed == [(4, "(evidence: gate-ABCD)")]


MALFORMED = ["*(evidence: gate-3FA1)*", "(evidence: gate-3fa)",
             "(evidence: gate 3fa1)", "(evidence: gate-a1b2, gate-c3d4)",
             "(evidence: gate-a1b2"]


@pytest.mark.parametrize("annotation", MALFORMED)
def test_an_annotation_that_is_not_one_gate_id_is_malformed(annotation):
    """Read as no annotation, any of these lifted the merge hold."""
    cited, malformed = aide.spec_evidence_annotations(
        _spec(f"Layout kept. {annotation}"))
    assert cited == []
    assert [ac for ac, _ in malformed] == [2]


@pytest.mark.parametrize("annotation", MALFORMED)
def test_check_errors_on_a_malformed_annotation_in_a_live_spec(
        tmp_path: Path, annotation):
    repo = _docs(tmp_path, PROGRESS, _spec(f"Layout kept. {annotation}"))
    errors, _ = _warnings(repo)
    [e] = [e for e in errors if "evidence annotation" in e]
    assert "AC2's evidence annotation" in e
    assert "does not name exactly one gate ID" in e
    assert "`aide merge 027` refuses" in e


def test_a_malformed_annotation_in_a_record_is_not_an_error(tmp_path: Path):
    repo = _docs(tmp_path, PROGRESS.replace("- 📋 Dialog.", "- ✅ Dialog."),
                 _spec("Layout kept. (evidence: gate-3FA1)"))
    errors, _ = _warnings(repo)
    assert not [e for e in errors if "evidence annotation" in e]


def test_a_spec_with_no_annotation_names_no_evidence():
    assert aide.spec_evidence_gates(_spec("Keeps its layout.")) == []


# --------------------------------------------------------------------------- #
# aide check — an evidence gate is worded as the check it records
# --------------------------------------------------------------------------- #
def test_check_reports_an_awaiting_evidence_gate_as_awaiting_the_check(tmp_path: Path):
    """Before #420 the row read "blocks nothing named … holds nothing" — a
    typo's wording, on the one gate shape whose `—` is correct."""
    progress = _with_gate(PROGRESS)
    gid = _gate_id(progress)
    repo = _docs(tmp_path, progress, _spec(f"Layout kept. *(evidence: {gid})*"))
    errors, warnings = _warnings(repo)
    assert errors == []
    mine = [w for w in warnings if gid in w]
    assert len(mine) == 1
    assert ("is awaiting a person's check — the evidence for item 027 AC2; "
            "`aide merge 027` refuses until it is ✅ Approved") in mine[0]
    assert "holds nothing" not in mine[0]


def test_an_uncited_awaiting_gate_with_an_empty_reach_still_says_it_holds_nothing(
        tmp_path: Path):
    progress = _with_gate(PROGRESS)
    repo = _docs(tmp_path, progress, _spec("Layout kept."))
    _, warnings = _warnings(repo)
    [w] = [w for w in warnings if _gate_id(progress) in w]
    assert "awaiting a decision" in w and "holds nothing" in w


def test_an_approved_evidence_gate_is_silent(tmp_path: Path):
    progress = _with_gate(PROGRESS, status="✅ Approved (2026-10-06)")
    gid = _gate_id(progress)
    repo = _docs(tmp_path, progress, _spec(f"Layout kept. *(evidence: {gid})*"))
    _, warnings = _warnings(repo)
    assert not [w for w in warnings if gid in w]


def test_a_declined_evidence_gate_a_live_spec_cites_is_not_re_planned(tmp_path: Path):
    """A declined `—` gate is silent as re-planned (#396) — but not while an
    open spec still points a criterion at it: that criterion has failed."""
    progress = _with_gate(PROGRESS, status="❌ Declined (2026-10-06)")
    gid = _gate_id(progress)
    repo = _docs(tmp_path, progress, _spec(f"Layout kept. *(evidence: {gid})*"))
    _, warnings = _warnings(repo)
    [w] = [w for w in warnings if gid in w]
    assert "was DECLINED, and it is the evidence for item 027 AC2" in w
    assert "re-point the annotation" in w


def test_a_declined_evidence_gate_cited_only_by_a_record_is_silent(tmp_path: Path):
    progress = _with_gate(PROGRESS.replace("- 📋 Dialog.", "- ❌ Dialog."),
                          status="❌ Declined (2026-10-06)")
    gid = _gate_id(progress)
    repo = _docs(tmp_path, progress, _spec(f"Layout kept. *(evidence: {gid})*"))
    _, warnings = _warnings(repo)
    assert not [w for w in warnings if gid in w]


def test_one_gate_named_as_the_evidence_for_two_criteria_warns(tmp_path: Path):
    progress = _with_gate(PROGRESS, status="✅ Approved (2026-10-06)")
    gid = _gate_id(progress)
    spec = _spec(f"Layout kept. *(evidence: {gid})*").replace(
        "values are written.", f"values are written. *(evidence: {gid})*")
    repo = _docs(tmp_path, progress, spec)
    _, warnings = _warnings(repo)
    [w] = [w for w in warnings if gid in w]
    assert ("is the evidence for more than one acceptance criterion "
            "(item 027 AC1, item 027 AC2) — one gate per criterion") in w


def test_an_evidence_gate_that_blocks_its_own_item_warns(tmp_path: Path):
    progress = _with_gate(PROGRESS, blocks="027")
    gid = _gate_id(progress)
    repo = _docs(tmp_path, progress, _spec(f"Layout kept. *(evidence: {gid})*"))
    _, warnings = _warnings(repo)
    mine = [w for w in warnings if gid in w]
    assert any("is the evidence for item 027 and its Blocks cell '027' holds "
               "that item, so `aide claim` never offers it" in w for w in mine)


def test_a_cited_evidence_gate_naming_no_row_is_the_existing_error(tmp_path: Path):
    """The dangling-citation error already covers an evidence ID (§1 → human
    gates); no second finding is added for it."""
    repo = _docs(tmp_path, PROGRESS, _spec("Layout kept. *(evidence: gate-0000)*"))
    errors, warnings = _warnings(repo)
    assert len([e for e in errors if "gate-0000 names no human gate" in e]) == 1
    assert not [w for w in warnings if "gate-0000" in w]


# --------------------------------------------------------------------------- #
# aide merge — refused until the person's check is approved
# --------------------------------------------------------------------------- #
def _repo_with_claim(tmp_path: Path, spec_for, mode: str = "local") -> Path:
    """main with the documents; a claim branch carrying the spec, its gate row
    and the work, as spec-author and builder leave it."""
    repo = _docs(tmp_path, PROGRESS, _spec("Layout kept."), mode)
    _run(["git", "init", "-b", "main"], repo)
    _run(["git", "config", "user.email", "t@e.com"], repo)
    _run(["git", "config", "user.name", "T"], repo)
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "init"], repo)
    branch = "aide/027-dialog"
    _run(["git", "switch", "-c", branch], repo)
    ppath = repo / "docs" / "aide" / "progress.md"
    progress = _with_gate(PROGRESS)
    ppath.write_text(progress, encoding="utf-8")
    (repo / "docs" / "aide" / "items" / "027-dialog.md").write_text(
        spec_for(_gate_id(progress)), encoding="utf-8")
    (repo / "dialog.txt").write_text("work\n", encoding="utf-8")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "spec, gate and work"], repo)
    _run(["git", "switch", "main"], repo)
    aide._record_branch_base(repo, branch, "main")
    return repo


def _main_sha(repo: Path) -> str:
    return _run(["git", "rev-parse", "main"], repo).stdout.strip()


def test_merge_refuses_an_item_whose_evidence_gate_is_not_approved(
        tmp_path: Path, capsys):
    repo = _repo_with_claim(
        tmp_path, lambda gid: _spec(f"Layout kept. *(evidence: {gid})*"))
    gid = _gate_id(_with_gate(PROGRESS))
    head = _main_sha(repo)
    capsys.readouterr()
    assert aide.main(["--repo", str(repo), "merge", "27", "--no-test"]) == 1
    err = capsys.readouterr().err
    assert (f"item 027 has acceptance criteria whose evidence is a human "
            f"gate not ✅ Approved — AC2: {gid} is ⏳ Awaiting —") in err
    assert "nothing was merged, pushed or written" in err
    assert ("a person checks the built item on aide/027-dialog and runs "
            "`aide gate approve <ID>` there") in err.lower().replace(
                "<id>", "<ID>")
    assert _main_sha(repo) == head
    assert not (repo / "dialog.txt").is_file()
    assert "aide/027-dialog" in _run(["git", "branch"], repo).stdout

    # Declined is refused, and its remedy is a rebuild and a re-asked gate,
    # never an approval of the "no".
    _run(["git", "switch", "aide/027-dialog"], repo)
    assert aide.main(["--repo", str(repo), "gate", "decline", gid,
                      "--evidence", "layout breaks at 200%"]) == 0
    _run(["git", "switch", "main"], repo)
    capsys.readouterr()
    assert aide.main(["--repo", str(repo), "merge", "27", "--no-test"]) == 1
    err = capsys.readouterr().err
    assert f"AC2: {gid} is ❌ Declined" in err
    assert ("For a declined gate, its criterion has failed: rebuild it, "
            "re-ask the check as a new Gate cell (a new ID) and re-point the "
            "annotation at it — never approve a declined gate") in err
    assert "aide gate approve" not in err
    assert _main_sha(repo) == head

    # The rebuild re-asks the check as a new gate and re-points the
    # annotation; the person's approval of that one, on the claim branch,
    # lets the merge land and tick the item.
    _run(["git", "switch", "aide/027-dialog"], repo)
    ppath = repo / "docs" / "aide" / "progress.md"
    again = QUESTION + ", re-checked after the fix"
    ppath.write_text(aide.add_gate_rows(ppath.read_text(encoding="utf-8"),
                                        [(again, "—")]), encoding="utf-8")
    new_id = _gate_id(ppath.read_text(encoding="utf-8"), again)
    spath = repo / "docs" / "aide" / "items" / "027-dialog.md"
    spath.write_text(spath.read_text(encoding="utf-8").replace(gid, new_id),
                     encoding="utf-8")
    _run(["git", "commit", "-am", "re-ask the check"], repo)
    assert aide.main(["--repo", str(repo), "gate", "approve", new_id,
                      "--evidence", "walked the app at 200%"]) == 0
    _run(["git", "switch", "main"], repo)
    assert aide.main(["--repo", str(repo), "merge", "27", "--no-test"]) == 0
    assert (repo / "dialog.txt").is_file()
    progress = (repo / "docs" / "aide" / "progress.md").read_text(encoding="utf-8")
    assert aide._parse_item_status(progress.splitlines())[2][27] == "complete"


def test_merge_refuses_a_malformed_annotation_before_anything_moves(
        tmp_path: Path, capsys):
    repo = _repo_with_claim(
        tmp_path, lambda gid: _spec(f"Layout kept. *(evidence: {gid.upper()})*"))
    head = _main_sha(repo)
    capsys.readouterr()
    assert aide.main(["--repo", str(repo), "merge", "27", "--no-test"]) == 1
    err = capsys.readouterr().err
    assert "is not one gate ID" in err
    assert "correct it to the one gate-<hex> ID `aide gate list` prints" in err
    assert _main_sha(repo) == head
    assert not (repo / "dialog.txt").is_file()


# --------------------------------------------------------------------------- #
# which copy of progress.md decides — the first that resolves the ID
# --------------------------------------------------------------------------- #
def _repo_gate_on_main(tmp_path: Path, status: str) -> Tuple[Path, str]:
    """The gate row committed on main with *status*; a claim branch taken
    from main after it, carrying the annotated spec and the work."""
    progress = _with_gate(PROGRESS, status=status)
    gid = _gate_id(progress)
    repo = _docs(tmp_path, progress, _spec("Layout kept."))
    _run(["git", "init", "-b", "main"], repo)
    _run(["git", "config", "user.email", "t@e.com"], repo)
    _run(["git", "config", "user.name", "T"], repo)
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "init"], repo)
    branch = "aide/027-dialog"
    _run(["git", "switch", "-c", branch], repo)
    (repo / "docs" / "aide" / "items" / "027-dialog.md").write_text(
        _spec(f"Layout kept. *(evidence: {gid})*"), encoding="utf-8")
    (repo / "dialog.txt").write_text("work\n", encoding="utf-8")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-m", "spec and work"], repo)
    _run(["git", "switch", "main"], repo)
    aide._record_branch_base(repo, branch, "main")
    return repo, gid


def test_the_claim_branch_decides_over_a_stale_approval_on_the_base(
        tmp_path: Path, capsys):
    repo, gid = _repo_gate_on_main(tmp_path, "✅ Approved (2026-10-01)")
    _run(["git", "switch", "aide/027-dialog"], repo)
    ppath = repo / "docs" / "aide" / "progress.md"
    ppath.write_text(ppath.read_text(encoding="utf-8").replace(
        "✅ Approved (2026-10-01)", "❌ Declined (2026-10-06)"), encoding="utf-8")
    _run(["git", "commit", "-am", "the person declines on the branch"], repo)
    _run(["git", "switch", "main"], repo)
    head = _main_sha(repo)
    capsys.readouterr()
    assert aide.main(["--repo", str(repo), "merge", "27", "--no-test"]) == 1
    assert f"AC2: {gid} is ❌ Declined" in capsys.readouterr().err
    assert _main_sha(repo) == head


def test_a_row_only_the_base_carries_decides_there(tmp_path: Path):
    """The row was raised on the base after the claim branch was taken, and
    the merge is run from the claim branch's checkout: neither the claim
    branch nor the working tree has the row, so the base's ✅ decides."""
    progress = _with_gate(PROGRESS, status="✅ Approved (2026-10-01)")
    gid = _gate_id(progress)
    repo = _repo_with_claim(
        tmp_path, lambda _: _spec(f"Layout kept. *(evidence: {gid})*"))
    ppath = repo / "docs" / "aide" / "progress.md"
    _run(["git", "switch", "aide/027-dialog"], repo)
    ppath.write_text(PROGRESS, encoding="utf-8")
    _run(["git", "commit", "-am", "the branch never raised the row"], repo)
    _run(["git", "switch", "main"], repo)
    ppath.write_text(progress, encoding="utf-8")
    _run(["git", "commit", "-am", "the row, approved, on the base"], repo)
    _run(["git", "switch", "aide/027-dialog"], repo)
    assert aide.main(["--repo", str(repo), "merge", "27", "--no-test"]) == 0
    assert (repo / "dialog.txt").is_file()


def test_a_row_only_the_working_tree_carries_decides_there(
        tmp_path: Path, capsys):
    """Neither branch has committed the row; the working tree's ⏳ decides,
    so the refusal says awaiting, not that the ID names no row."""
    repo, gid = _repo_gate_on_main(tmp_path, "⏳ Awaiting")
    ppath = repo / "docs" / "aide" / "progress.md"
    _run(["git", "switch", "aide/027-dialog"], repo)
    ppath.write_text(PROGRESS, encoding="utf-8")
    _run(["git", "commit", "-am", "the row is not on the branch"], repo)
    _run(["git", "switch", "main"], repo)
    ppath.write_text(PROGRESS, encoding="utf-8")
    _run(["git", "commit", "-am", "nor on main"], repo)
    ppath.write_text(_with_gate(PROGRESS), encoding="utf-8")   # uncommitted
    capsys.readouterr()
    assert aide.main(["--repo", str(repo), "merge", "27", "--no-test"]) == 1
    assert f"AC2: {gid} is ⏳ Awaiting" in capsys.readouterr().err


def test_merge_refuses_an_evidence_id_that_names_no_gate_row(tmp_path: Path, capsys):
    repo = _repo_with_claim(
        tmp_path, lambda gid: _spec("Layout kept. *(evidence: gate-0000)*"))
    head = _main_sha(repo)
    capsys.readouterr()
    assert aide.main(["--repo", str(repo), "merge", "27", "--no-test"]) == 1
    assert "AC2: gate-0000 names no gate row" in capsys.readouterr().err
    assert _main_sha(repo) == head


def test_merge_of_an_item_with_no_evidence_annotation_is_unchanged(
        tmp_path: Path):
    repo = _repo_with_claim(tmp_path, lambda gid: _spec("Layout kept."))
    assert aide.main(["--repo", str(repo), "merge", "27", "--no-test"]) == 0
    assert (repo / "dialog.txt").is_file()


def test_pr_mode_merge_refuses_an_unapproved_evidence_gate_before_the_push(
        tmp_path: Path, capsys):
    """Under `pr` the merge only pushes for a PR, and a PR over an item no
    person has checked invites its merge: the refusal comes first, so origin
    never sees the claim branch."""
    remote = tmp_path / "remote.git"
    _run(["git", "init", "--bare", "-b", "main", str(remote)], tmp_path)
    repo = _repo_with_claim(
        tmp_path, lambda gid: _spec(f"Layout kept. *(evidence: {gid})*"),
        mode="pr")
    _run(["git", "remote", "add", "origin", str(remote)], repo)
    _run(["git", "push", "-u", "origin", "main"], repo)
    before = _run(["git", "ls-remote", str(remote)], repo).stdout
    capsys.readouterr()
    assert aide.main(["--repo", str(repo), "merge", "27", "--no-test"]) == 1
    assert "is ⏳ Awaiting" in capsys.readouterr().err
    assert _run(["git", "ls-remote", str(remote)], repo).stdout == before
    assert "aide/027-dialog" not in before
