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


def reasons(plan) -> dict:
    return {f"{l['kind']} {l['name']}": l["reason"] for l in plan["left_alone"]}


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
    assert any("wt-gone" in l for l in plan["propose_prune"])

    why = reasons(plan)
    branch = {k[len("branch "):]: v for k, v in why.items() if k.startswith("branch ")}
    assert "not on the head of merged PR #2" in branch["reused"]
    assert "from a fork" in branch["fork"]
    assert "merged into stack-parent" in branch["otherbase"]
    assert "open PR #5 on it" == branch["openhead"]
    assert "open PR #7 stacked on it" == branch["stackbase"]
    assert "not on the head of merged PR #8" in branch["ghost"]
    for name in ("wt-dirty", "wt-busy", "wt-locked", "wt-gone", "wt-bisect"):
        assert branch[name].startswith("checked out in "), name
    assert "origin origin/reused" in why and "origin origin/wt-dirty" in why

    wt = {Path(k.split(" ")[1]).name: v for k, v in why.items()
          if k.startswith("worktree ")}
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
    assert out["plan"] == plan
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
    assert any("nothing is deleted" in n for n in out["plan"]["notes"])


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
    assert "moved to" in out["results"][0]["detail"]
    assert git(repo, "ls-remote", "origin", "refs/heads/done").startswith(newer)


def test_the_lease_itself_refuses_a_stale_sha(small):
    """Past the pre-check (origin moved after the fetch), git's lease holds."""
    repo, gh, sha = small
    newer = commit_on(repo, sha, "pushed since")
    git(repo, "push", "-q", "origin", f"{newer}:refs/heads/done")
    ok, detail = cleanup.push_delete("done", sha, repo)
    assert not ok and "refused" in detail
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
    why = {Path(k.split(" ")[1]).name: v for k, v in reasons(plan).items()
           if k.startswith("worktree ")}
    assert why["own"] == "this session's own worktree"
    if proc:
        assert why["held"] == "a process has its cwd there"
        assert plan["remove_worktrees"] == []
    else:
        assert "process check unavailable on this platform" in plan["notes"]
