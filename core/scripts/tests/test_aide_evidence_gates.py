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
    assert aide.spec_evidence_gates(text) == [
        (1, "gate-1234"), (2, "gate-abcdef12"), (None, "gate-beef")]


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
    assert (f"item 027 names human gates as acceptance-criterion evidence "
            f"that are not ✅ Approved — AC2: {gid} is ⏳ Awaiting —") in err
    assert "nothing was merged, pushed or written" in err
    assert "on aide/027-dialog and runs `aide gate approve <ID>`" in err
    assert _main_sha(repo) == head
    assert not (repo / "dialog.txt").is_file()
    assert "aide/027-dialog" in _run(["git", "branch"], repo).stdout

    # Declined is refused the same way, naming the decline.
    _run(["git", "switch", "aide/027-dialog"], repo)
    assert aide.main(["--repo", str(repo), "gate", "decline", gid,
                      "--evidence", "layout breaks at 200%"]) == 0
    _run(["git", "switch", "main"], repo)
    capsys.readouterr()
    assert aide.main(["--repo", str(repo), "merge", "27", "--no-test"]) == 1
    assert f"AC2: {gid} is ❌ Declined" in capsys.readouterr().err
    assert _main_sha(repo) == head

    # A person's approval, on the claim branch where the item was checked,
    # lets the merge land and tick the item.
    _run(["git", "switch", "aide/027-dialog"], repo)
    assert aide.main(["--repo", str(repo), "gate", "approve", gid,
                      "--evidence", "walked the app at 200%"]) == 0
    _run(["git", "switch", "main"], repo)
    assert aide.main(["--repo", str(repo), "merge", "27", "--no-test"]) == 0
    assert (repo / "dialog.txt").is_file()
    progress = (repo / "docs" / "aide" / "progress.md").read_text(encoding="utf-8")
    assert aide._parse_item_status(progress.splitlines())[2][27] == "complete"


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
