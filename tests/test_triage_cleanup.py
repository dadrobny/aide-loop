"""The triage skill's step 6 script, `.claude/skills/triage-issues/cleanup.py`.

It deletes worktrees and branches in a checkout other sessions share, so every
rule SKILL.md step 6 states is pinned here against a real repository: a bare
origin, linked worktrees, and a `gh` that is a real program answering from a
file (the shape of `_gh_at_a_configured_path` in test_fixture_consumer.py).
One scenario carries most cases, so the git spawns are paid once per test that
needs it, not once per case.

Stdlib + pytest only; the script is loaded by path.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / ".claude" / "skills" / "triage-issues" / "cleanup.py"
_spec = importlib.util.spec_from_file_location("triage_cleanup", SCRIPT)
cleanup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cleanup)

OLD = time.time() - 3 * 24 * 3600
GITIGNORE = "__pycache__/\n*.pyc\n.pytest_cache/\nlocal.toml\n.venv/\n"


def git(cwd: Path, *args: str) -> str:
    res = subprocess.run(["git", *args], cwd=str(cwd), encoding="utf-8",
                         errors="replace", stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    assert res.returncode == 0, f"git {' '.join(args)}: {res.stderr}"
    return res.stdout.strip()


def commit_on(repo: Path, parent: str, msg: str) -> str:
    """A commit with *parent*'s tree — no checkout, no file churn."""
    return git(repo, "commit-tree", "-p", parent, "-m", msg, f"{parent}^{{tree}}")


def gh_stub(tmp_path: Path) -> Path:
    """A real `gh` printing whatever `answer.json` holds (`{"exit", "stdout"}`)."""
    tools = tmp_path / "tools"
    tools.mkdir()
    answer = tools / "answer.json"
    script = tools / "gh_stub.py"
    script.write_text(
        "import json, sys\n"
        f"a = json.load(open({str(answer)!r}, encoding='utf-8'))\n"
        "sys.stdout.write(a['stdout'])\n"
        "sys.stderr.write(a.get('stderr', ''))\n"
        "sys.exit(a['exit'])\n", encoding="utf-8")
    if os.name == "nt":
        gh = tools / "gh.cmd"
        gh.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        gh = tools / "gh"
        gh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n',
                      encoding="utf-8")
        gh.chmod(0o755)
    return gh


def answer(gh: Path, prs=None, exit=0, stdout=None) -> None:
    body = stdout if stdout is not None else json.dumps(prs or [])
    (gh.parent / "answer.json").write_text(
        json.dumps({"exit": exit, "stdout": body, "stderr": "boom\n" if exit else ""}),
        encoding="utf-8")


def pr(n, head, oid, state="MERGED", base="main", cross=False) -> dict:
    return {"number": n, "state": state, "baseRefName": base, "headRefName": head,
            "headRefOid": oid, "isCrossRepository": cross}


def make_repo(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"),
                 ("commit.gpgsign", "false"), ("maintenance.auto", "false")):
        git(repo, "config", k, v)
    (repo / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (repo / "f.txt").write_text("f\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")
    return repo


def make_old(wt: Path) -> None:
    for name in ("logs/HEAD", "index"):
        p = git(wt, "rev-parse", "--path-format=absolute", "--git-path", name)
        os.utime(p, (OLD, OLD))


def run(repo: Path, gh: Path, monkeypatch, capsys, *argv: str):
    monkeypatch.chdir(repo)
    capsys.readouterr()
    code = cleanup.main([*argv, "--json", "--gh", str(gh)])
    return code, json.loads(capsys.readouterr().out)


def same(a, b) -> bool:
    return Path(a).resolve() == Path(b).resolve()


@pytest.fixture
def scenario(tmp_path: Path):
    """One repository holding a case per rule; returns (repo, gh, worktrees)."""
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "main")
    old_head = commit_on(repo, base, "an old branch, long merged")
    # main moves on (same tree, so the main checkout stays clean)
    new_main = commit_on(repo, base, "squash of something")
    git(repo, "update-ref", "refs/heads/main", new_main)
    git(repo, "config", "status.showUntrackedFiles", "no")

    tips, prs = {}, []
    for name in ("squash", "fork", "otherbase", "openhead", "stackbase", "ghost"):
        tips[name] = commit_on(repo, new_main, name)
        git(repo, "branch", name, tips[name])
    git(repo, "branch", "reused", new_main)               # cut fresh from main
    prs += [pr(1, "squash", tips["squash"]),
            pr(2, "reused", old_head),
            pr(3, "fork", tips["fork"], cross=True),
            pr(4, "otherbase", tips["otherbase"], base="stack-parent"),
            pr(5, "openhead", tips["openhead"], state="OPEN"),
            pr(6, "stackbase", tips["stackbase"]),
            pr(7, "child", "0" * 40, state="OPEN", base="stackbase"),
            pr(8, "ghost", "1234567890" * 4)]               # object never fetched

    wts = {}
    for n, name in enumerate(("wt-clean", "wt-cache", "wt-dirty", "wt-untracked",
                              "wt-ignored", "wt-bisect", "wt-seq", "wt-busy",
                              "wt-locked", "wt-gone"), start=20):
        tips[name] = commit_on(repo, new_main, name)
        git(repo, "branch", name, tips[name])
        wts[name] = tmp_path / name
        git(repo, "worktree", "add", "-q", str(wts[name]), name)
        prs.append(pr(n, name, tips[name]))
    wts["detached"] = tmp_path / "detached"
    git(repo, "worktree", "add", "-q", "--detach", str(wts["detached"]), new_main)

    (wts["wt-cache"] / "a" / "__pycache__").mkdir(parents=True)
    (wts["wt-cache"] / "a" / "__pycache__" / "x.pyc").write_text("", encoding="utf-8")
    (wts["wt-cache"] / "b.pyc").write_text("", encoding="utf-8")
    (wts["wt-cache"] / ".pytest_cache" / "v").mkdir(parents=True)
    (wts["wt-cache"] / ".pytest_cache" / "v" / "z").write_text("", encoding="utf-8")
    git(wts["wt-dirty"], "mv", "f.txt", "g.txt")           # a rename: two -z fields
    (wts["wt-untracked"] / "junk.txt").write_text("", encoding="utf-8")
    (wts["wt-ignored"] / "local.toml").write_text("", encoding="utf-8")
    Path(git(wts["wt-bisect"], "rev-parse", "--path-format=absolute",
             "--git-path", "BISECT_LOG")).write_text("", encoding="utf-8")
    Path(git(wts["wt-seq"], "rev-parse", "--path-format=absolute",
             "--git-path", "sequencer")).mkdir()
    git(repo, "worktree", "lock", "--reason", "on a stick", str(wts["wt-locked"]))
    git(repo, "push", "-q", "origin", "--all")
    import shutil
    shutil.rmtree(wts["wt-gone"])
    for name, wt in wts.items():
        if name not in ("wt-busy", "wt-gone"):
            make_old(wt)

    gh = gh_stub(tmp_path)
    answer(gh, prs)
    return repo, gh, wts, tips


def left(plan, kind) -> dict:
    """The left-alone reasons of one kind, by worktree directory name or branch."""
    return {(Path(l["path"]).name if kind == "worktree" else l["branch"]): l["reason"]
            for l in plan["left_alone"] if l["kind"] == kind}


def test_the_plan_takes_only_what_is_provably_finished(scenario, monkeypatch, capsys):
    repo, gh, wts, tips = scenario
    code, plan = run(repo, gh, monkeypatch, capsys)
    assert code == 0
    removed = {Path(w["path"]).name for w in plan["remove_worktrees"]}
    assert removed == {"wt-clean", "wt-cache", "detached"}
    deleted = {b["branch"]: b["sha"] for b in plan["delete_branches"]}
    assert deleted == {"squash": tips["squash"], "wt-clean": tips["wt-clean"],
                       "wt-cache": tips["wt-cache"]}
    proposed = {r["branch"]: r["sha"] for r in plan["propose_remote"]}
    assert proposed == deleted
    assert plan["propose_prune"] == ["worktrees/wt-gone"]
    assert "gitdir file points to non-existent location" in \
        plan["prune_reasons"]["worktrees/wt-gone"]

    branch = left(plan, "branch")
    assert "not on the head of merged PR #2" in branch["reused"]
    assert "from a fork" in branch["fork"]
    assert "merged into stack-parent" in branch["otherbase"]
    assert "open PR #5 on it" == branch["openhead"]
    assert "open PR #7 stacked on it" == branch["stackbase"]
    assert "not on the head of merged PR #8" in branch["ghost"]
    for name in ("wt-dirty", "wt-busy", "wt-locked", "wt-gone", "wt-bisect"):
        assert branch[name].startswith("checked out in "), name
    origin = left(plan, "origin")
    assert "reused" in origin and origin["wt-dirty"].startswith("checked out in ")

    wt = left(plan, "worktree")
    assert wt["wt-dirty"].startswith("not clean: R  g.txt")
    assert "f.txt" not in wt["wt-dirty"]       # the rename source is not an entry
    assert wt["wt-untracked"] == "not clean: ?? junk.txt"
    assert wt["wt-ignored"] == "not clean: !! local.toml"
    assert wt["wt-bisect"] == "operation in progress (BISECT_LOG)"
    assert wt["wt-seq"] == "operation in progress (sequencer)"
    assert wt["wt-busy"].startswith("active in the last 24 hours")
    assert wt["wt-locked"] == "locked: on a stick"
    assert wt["wt-gone"].startswith("prunable")


def test_apply_does_exactly_the_plan_and_no_more(scenario, monkeypatch, capsys):
    repo, gh, wts, tips = scenario
    _, plan = run(repo, gh, monkeypatch, capsys)
    code, out = run(repo, gh, monkeypatch, capsys, "--apply")
    assert code == 0
    # the process count in the notes is a live reading; the decisions are not
    assert {k: v for k, v in out["plan"].items() if k != "notes"} == \
        {k: v for k, v in plan.items() if k != "notes"}
    assert all(r["ok"] for r in out["results"])
    done = {r["target"] for r in out["results"]}
    assert done == ({w["path"] for w in plan["remove_worktrees"]}
                    | {f"{b['branch']} {b['sha']}" for b in plan["delete_branches"]})
    for name, wt in wts.items():
        assert wt.exists() == (name not in ("wt-clean", "wt-cache", "detached", "wt-gone"))
    left = set(git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads/").split())
    assert not left & {"squash", "wt-clean", "wt-cache"}
    assert {"reused", "fork", "wt-dirty", "wt-busy", "wt-gone"} <= left
    # nothing outward-facing moved
    assert "squash" in git(repo, "ls-remote", "origin", "refs/heads/squash")


@pytest.fixture
def small(tmp_path: Path):
    """main plus one squash-merged branch `done`, pushed."""
    repo = make_repo(tmp_path)
    sha = commit_on(repo, git(repo, "rev-parse", "main"), "done")
    git(repo, "branch", "done", sha)
    git(repo, "push", "-q", "origin", "done")
    gh = gh_stub(tmp_path)
    answer(gh, [pr(1, "done", sha)])
    return repo, gh, sha


@pytest.mark.parametrize("how", ["exit", "not-json", "limit"])
def test_an_unreadable_pr_list_deletes_nothing(small, how, monkeypatch, capsys):
    repo, gh, sha = small
    if how == "exit":
        answer(gh, exit=1)
    elif how == "not-json":
        answer(gh, stdout="<html>")
    else:
        answer(gh, [pr(n, f"b{n}", sha) for n in range(cleanup.PR_LIMIT)])
    code, out = run(repo, gh, monkeypatch, capsys, "--apply")
    assert code == 1
    assert out["results"] == []
    assert not out["plan"]["delete_branches"] and not out["plan"]["propose_remote"]
    assert git(repo, "rev-parse", "done") == sha
    assert out["plan"]["refused"].startswith("PR list")


def test_delete_remote_deletes_the_approved_tip(small, monkeypatch, capsys):
    repo, gh, sha = small
    code, out = run(repo, gh, monkeypatch, capsys, "--delete-remote", f"done={sha}")
    assert code == 0, out
    assert git(repo, "ls-remote", "origin", "refs/heads/done") == ""


def test_delete_remote_refuses_a_branch_that_moved(small, monkeypatch, capsys):
    repo, gh, sha = small
    newer = commit_on(repo, sha, "pushed since")
    git(repo, "push", "-q", "origin", f"{newer}:refs/heads/done")
    code, out = run(repo, gh, monkeypatch, capsys, "--delete-remote", f"done={sha}")
    assert code == 1
    assert f"origin is now at done={newer}; approve" in out["results"][0]["detail"]
    assert git(repo, "ls-remote", "origin", "refs/heads/done").startswith(newer)


def test_the_lease_itself_refuses_a_stale_sha(small):
    """Past the pre-check (origin moved after the fetch), git's lease holds."""
    repo, gh, sha = small
    newer = commit_on(repo, sha, "pushed since")
    git(repo, "push", "-q", "origin", f"{newer}:refs/heads/done")
    ok, detail = cleanup.push_delete("done", sha, repo)
    assert not ok and "refused" in detail and f"done={newer}" in detail
    assert git(repo, "ls-remote", "origin", "refs/heads/done").startswith(newer)


def test_a_branch_already_gone_on_origin_counts_as_deleted(small, monkeypatch, capsys):
    repo, gh, sha = small
    git(repo.parent / "origin.git", "update-ref", "-d", "refs/heads/done")
    ok, detail = cleanup.push_delete("done", sha, repo)
    assert ok and detail == "already gone on origin"
    assert git(repo, "for-each-ref", "refs/remotes/origin/done") == ""
    code, out = run(repo, gh, monkeypatch, capsys, "--delete-remote", f"done={sha}")
    assert code == 0 and out["results"][0]["detail"] == "already gone on origin"


def test_usage_errors_exit_2(small, monkeypatch):
    repo, gh, sha = small
    monkeypatch.chdir(repo)
    with pytest.raises(SystemExit) as exc:
        cleanup.main(["--delete-remote", "done=notasha", "--gh", str(gh)])
    assert exc.value.code == 2


def test_a_worktree_in_use_is_left_alone(small, tmp_path, monkeypatch, capsys):
    """The cwd's own worktree, and on Linux one a live process sits in."""
    repo, gh, sha = small
    other = commit_on(repo, sha, "other")
    git(repo, "branch", "other", other)
    answer(gh, [pr(1, "done", sha), pr(2, "other", other)])
    own, held = tmp_path / "own", tmp_path / "held"
    git(repo, "worktree", "add", "-q", str(own), "done")
    git(repo, "worktree", "add", "-q", str(held), "other")
    make_old(own)
    make_old(held)
    proc = None
    if cleanup.process_cwds() is not None:
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                cwd=str(held))
    try:
        code, plan = run(own, gh, monkeypatch, capsys)
    finally:
        if proc:
            proc.kill()
            proc.wait()
    assert code == 0
    why = left(plan, "worktree")
    assert why["own"] == "this session's own worktree"
    if proc:
        assert why["held"] == "a process has its cwd there"
        assert plan["remove_worktrees"] == []
    else:
        assert "process check unavailable on this platform" in plan["notes"]


def test_prune_runs_only_on_the_approved_set(small, tmp_path, monkeypatch, capsys):
    repo, gh, sha = small
    gone = tmp_path / "gone"
    git(repo, "worktree", "add", "-q", str(gone), "done")
    import shutil
    shutil.rmtree(gone)
    _, plan = run(repo, gh, monkeypatch, capsys)
    approved = plan["propose_prune"]
    assert approved == ["worktrees/gone"]
    code, out = run(repo, gh, monkeypatch, capsys, "--prune", *approved, "worktrees/x")
    assert code == 1 and "Nothing was pruned" in out["results"][0]["detail"]
    assert "gone" in git(repo, "worktree", "list")
    code, out = run(repo, gh, monkeypatch, capsys, "--prune", *approved)
    assert code == 0, out
    assert "gone" not in git(repo, "worktree", "list")


def test_a_detached_rebase_or_bisect_keeps_its_branch(small, tmp_path, monkeypatch, capsys):
    """Mid-rebase or mid-bisect, `worktree list` shows no branch line."""
    repo, gh, sha = small
    rb, bb = tmp_path / "rb", tmp_path / "bb"
    git(repo, "worktree", "add", "-q", "-b", "rb", str(rb), "main")
    (rb / "f.txt").write_text("rb\n", encoding="utf-8")
    git(rb, "commit", "-q", "-am", "rb")
    git(repo, "worktree", "add", "-q", "-b", "bb", str(bb), "main")
    rb_tip, bb_tip = git(rb, "rev-parse", "HEAD"), git(bb, "rev-parse", "HEAD")
    (repo / "f.txt").write_text("main moved\n", encoding="utf-8")
    git(repo, "commit", "-q", "-am", "conflicting")
    git(repo, "push", "-q", "origin", "main", "rb", "bb")
    stopped = subprocess.run(["git", "rebase", "main"], cwd=str(rb),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert stopped.returncode != 0                 # stopped on the conflict
    git(bb, "bisect", "start")
    git(bb, "checkout", "-q", "--detach")
    for wt in (rb, bb):
        make_old(wt)
    answer(gh, [pr(1, "done", sha), pr(2, "rb", rb_tip), pr(3, "bb", bb_tip)])
    _, plan = run(repo, gh, monkeypatch, capsys)
    assert {b["branch"] for b in plan["delete_branches"]} == {"done"}
    assert {r["branch"] for r in plan["propose_remote"]} == {"done"}
    branch, origin = left(plan, "branch"), left(plan, "origin")
    for name in ("rb", "bb"):
        assert branch[name].startswith("checked out in "), name
        assert origin[name].startswith("checked out in "), name
    assert left(plan, "worktree")["rb"] == "detached mid-rebase or mid-bisect on rb"
    assert left(plan, "worktree")["bb"] == "detached mid-rebase or mid-bisect on bb"
    code, out = run(repo, gh, monkeypatch, capsys, "--delete-remote", f"rb={rb_tip}")
    assert code == 1 and out["results"][0]["detail"].startswith("checked out in ")


def test_apply_keeps_a_branch_whose_worktree_would_not_go(small, tmp_path):
    repo, gh, sha = small
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt), "done")
    make_old(wt)
    plan = cleanup.decide(repo, str(gh), None)
    assert [Path(w["path"]).name for w in plan["remove_worktrees"]] == ["wt"]
    git(repo, "worktree", "lock", str(wt))        # now `remove` refuses
    results = cleanup.apply_local(plan, repo)
    assert [r["ok"] for r in results] == [False, False]
    assert results[1]["detail"] == "its worktree is still there"
    assert git(repo, "rev-parse", "done") == sha


def test_apply_refuses_a_branch_that_moved_since_the_plan(small):
    repo, gh, sha = small
    plan = cleanup.decide(repo, str(gh), None)
    assert [b["branch"] for b in plan["delete_branches"]] == ["done"]
    newer = commit_on(repo, sha, "committed meanwhile")
    git(repo, "update-ref", "refs/heads/done", newer)
    [result] = cleanup.apply_local(plan, repo)
    assert not result["ok"] and "moved to" in result["detail"]
    assert git(repo, "rev-parse", "done") == newer


def _script_copy(tmp_path: Path, reorder_source: str):
    """cleanup.py beside a reorder_project.py, loaded from there."""
    d = tmp_path / "skill"
    d.mkdir()
    (d / "cleanup.py").write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    (d / "reorder_project.py").write_text(reorder_source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("triage_cleanup_copy", d / "cleanup.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return d, mod


REORDER = (SCRIPT.parent / "reorder_project.py").read_text(encoding="utf-8")


def test_gh_comes_from_the_local_toml_beside_the_script(tmp_path):
    pytest.importorskip("tomllib")
    gh = gh_stub(tmp_path)
    d, mod = _script_copy(tmp_path, REORDER)
    (d / "local.toml").write_text(f"gh = {json.dumps(str(gh))}\n", encoding="utf-8")
    exe, why = mod.resolve_gh(None)
    assert why is None and same(exe, gh)
    (d / "local.toml").write_text(f"gh = {json.dumps(str(tmp_path / 'nope'))}\n",
                                  encoding="utf-8")
    exe, why = mod.resolve_gh(None)
    assert exe is None and why.startswith("no gh at ")
    (d / "local.toml").write_text("gh = 5\n", encoding="utf-8")
    with pytest.raises(mod.Refusal, match="non-empty string"):
        mod.resolve_gh(None)


def test_no_tomllib_is_a_one_line_refusal(tmp_path):
    _, mod = _script_copy(tmp_path, "import tomllib_absent_on_this_python\n")
    with pytest.raises(mod.Refusal, match="pass --gh PATH"):
        mod.resolve_gh(None)


def _rebase_stopped(repo: Path, wt: Path, branch: str) -> str:
    """*branch* in worktree *wt*, rebasing onto a main that conflicts with it;
    returns the branch's tip."""
    git(repo, "worktree", "add", "-q", "-b", branch, str(wt), "main")
    (wt / "f.txt").write_text(f"{branch}\n", encoding="utf-8")
    git(wt, "commit", "-q", "-am", branch)
    (repo / "f.txt").write_text(f"main against {branch}\n", encoding="utf-8")
    git(repo, "commit", "-q", "-am", f"conflicts with {branch}")
    stopped = subprocess.run(["git", "rebase", "main"], cwd=str(wt),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert stopped.returncode != 0
    return git(repo, "rev-parse", branch)


def test_a_rebase_in_a_vanished_worktree_still_holds_its_branch(
        small, tmp_path, monkeypatch, capsys):
    """Its directory gone, the admin dir under the common dir still names it."""
    import shutil
    repo, gh, sha = small
    rb = tmp_path / "rb"
    tip = _rebase_stopped(repo, rb, "rb")
    git(repo, "push", "-q", "origin", "main", "rb")
    shutil.rmtree(rb)
    answer(gh, [pr(1, "done", sha), pr(2, "rb", tip)])
    _, plan = run(repo, gh, monkeypatch, capsys)
    assert "rb" not in {b["branch"] for b in plan["delete_branches"]}
    assert "rb" not in {r["branch"] for r in plan["propose_remote"]}
    assert left(plan, "branch")["rb"].startswith("checked out in ")
    assert left(plan, "origin")["rb"].startswith("checked out in ")
    assert plan["propose_prune"] == ["worktrees/rb"]
    code, out = run(repo, gh, monkeypatch, capsys, "--delete-remote", f"rb={tip}")
    assert code == 1 and out["results"][0]["detail"].startswith("checked out in ")
    assert git(repo, "ls-remote", "origin", "refs/heads/rb")


def test_a_detached_head_rebase_holds_no_branch(small, tmp_path, monkeypatch, capsys):
    repo, gh, sha = small
    wt = tmp_path / "dh"
    git(repo, "worktree", "add", "-q", "--detach", str(wt), "main")
    (wt / "f.txt").write_text("detached\n", encoding="utf-8")
    git(wt, "commit", "-q", "-am", "detached work")
    (repo / "f.txt").write_text("main moved\n", encoding="utf-8")
    git(repo, "commit", "-q", "-am", "conflicting")
    git(repo, "push", "-q", "origin", "main")
    assert subprocess.run(["git", "rebase", "main"], cwd=str(wt), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).returncode != 0
    make_old(wt)
    _, plan = run(repo, gh, monkeypatch, capsys)
    [entry] = [l for l in plan["left_alone"] if l["kind"] == "worktree"]
    assert Path(entry["path"]).name == "dh" and entry["branch"] is None
    assert {b["branch"] for b in plan["delete_branches"]} == {"done"}


def test_git_decides_what_is_prunable(small, monkeypatch, capsys):
    """Entries the porcelain never lists: an empty gitdir, a stray file, a
    duplicate, a gitdir-less one — and a locked one git keeps."""
    repo, gh, sha = small
    git(repo, "worktree", "add", "-q", str(repo.parent / "a"), "-b", "a")
    admin = repo / ".git" / "worktrees"
    for name in ("empty", "nogit", "dup", "kept"):
        (admin / name).mkdir()
        (admin / name / "HEAD").write_text(f"{sha}\n", encoding="utf-8")
    (admin / "empty" / "gitdir").write_text("", encoding="utf-8")
    (admin / "dup" / "gitdir").write_bytes((admin / "a" / "gitdir").read_bytes())
    (admin / "kept" / "locked").write_text("on a disk\n", encoding="utf-8")
    (admin / "strayfile").write_text("", encoding="utf-8")
    code, plan = run(repo, gh, monkeypatch, capsys, "--apply")
    pruned = ["worktrees/dup", "worktrees/empty", "worktrees/nogit", "worktrees/strayfile"]
    assert plan["plan"]["propose_prune"] == pruned
    # meanwhile the admin dirs cannot be read for certain: nothing else happens
    assert code == 1 and plan["results"] == [] and "admin dirs" in plan["plan"]["refused"]
    code, out = run(repo, gh, monkeypatch, capsys, "--prune", *pruned[:-1])
    assert code == 1 and (admin / "nogit").exists()
    code, out = run(repo, gh, monkeypatch, capsys, "--prune", *pruned)
    assert code == 0, out
    assert sorted(p.name for p in admin.iterdir()) == ["a", "kept"]


@pytest.mark.parametrize("how", ["back-pointer", "not-utf8"])
def test_an_admin_dir_in_doubt_blinds_the_run(small, tmp_path, how, monkeypatch, capsys):
    repo, gh, sha = small
    a, b = tmp_path / "a", tmp_path / "b"
    git(repo, "worktree", "add", "-q", str(a), "done")
    git(repo, "worktree", "add", "-q", "--detach", str(b), "main")
    if how == "back-pointer":
        (a / ".git").write_text("gitdir: " + git(b, "rev-parse", "--absolute-git-dir")
                                + "\n", encoding="utf-8")
    else:
        (repo / ".git" / "worktrees" / "b" / "gitdir").write_bytes(b"\xff\xfe/x/.git\n")
    for wt in (a, b):
        make_old(wt)
    code, out = run(repo, gh, monkeypatch, capsys, "--apply")
    assert code == 1 and out["results"] == []
    assert out["plan"]["refused"].startswith("admin dirs unreadable: ")
    assert not out["plan"]["delete_branches"] and not out["plan"]["propose_remote"]
    code, out = run(repo, gh, monkeypatch, capsys, "--delete-remote", f"done={sha}")
    assert code == 1 and out["results"][0]["detail"].startswith("admin dirs unreadable")


def _git_version() -> tuple:
    out = subprocess.run(["git", "--version"], stdout=subprocess.PIPE,
                         encoding="utf-8").stdout
    return tuple(int(x) for x in out.split()[2].split(".")[:2] if x.isdigit())


@pytest.mark.skipif(_git_version() < (2, 48), reason="git worktree add --relative-paths needs git 2.48")
def test_a_relative_paths_worktree_is_read(small, tmp_path, monkeypatch, capsys):
    repo, gh, sha = small
    wt = tmp_path / "rel"
    git(repo, "worktree", "add", "-q", "--relative-paths", str(wt), "done")
    make_old(wt)
    code, plan = run(repo, gh, monkeypatch, capsys)
    assert code == 0 and plan["refused"] is None
    assert [Path(w["path"]).name for w in plan["remove_worktrees"]] == ["rel"]


def test_a_push_origin_refuses_at_the_approved_tip_is_its_own_error(small):
    """The lease held (origin still at the SHA), but origin said no."""
    repo, gh, sha = small
    hook = repo.parent / "origin.git" / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'deletes are switched off here' >&2\nexit 1\n",
                    encoding="utf-8")
    hook.chmod(0o755)
    ok, detail = cleanup.push_delete("done", sha, repo)
    assert not ok and detail.startswith("refused by origin: "), detail
    assert "approve" not in detail, detail
    assert git(repo, "ls-remote", "origin", "refs/heads/done").startswith(sha)


def test_a_worktree_no_admin_dir_names_is_blind(small, tmp_path):
    repo, gh, sha = small
    ghost = {"path": str(tmp_path / "nowhere"), "HEAD": sha, "detached": True,
             "branch": None}
    with pytest.raises(cleanup.Blind, match="no admin dir"):
        cleanup.annotate([*cleanup.worktrees(repo), ghost], repo)
