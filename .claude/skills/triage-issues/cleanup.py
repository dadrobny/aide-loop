#!/usr/bin/env python3
"""Step 6 of the triage pass: find the worktrees and branches already merged
into main, and remove only what is provably finished.

    python3 .claude/skills/triage-issues/cleanup.py            # plan, nothing changes
    python3 .claude/skills/triage-issues/cleanup.py --apply    # the local half
    python3 .claude/skills/triage-issues/cleanup.py --delete-remote B=SHA ...
    python3 .claude/skills/triage-issues/cleanup.py --prune

The policy is SKILL.md's step 6; this file is its mechanism. Every mode decides
from scratch — `--apply` never trusts an earlier printout — and every outcome
printed comes from git's own return code.

Run it from inside the checkout (any of its worktrees). The worktree the cwd
sits in is this session's and is never removed. `gh` comes from the skill's
`local.toml` (reorder_project.find_gh), or `--gh PATH`.

Exit codes: 0 done, 1 something was refused or failed (including a PR list
that could not be read), 2 usage.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = "dadrobny/aide-loop"
MAIN = "main"
REMOTE = "origin"
#: A worktree whose HEAD moved or whose index was written this recently may
#: belong to a session that paused after merging.
IDLE_SECONDS = 24 * 3600
GH_TIMEOUT = 20
PR_LIMIT = 1000
PR_FIELDS = "number,state,baseRefName,headRefName,headRefOid,isCrossRepository"
#: Present in a worktree's gitdir while an operation is unfinished; `sequencer`
#: outlives CHERRY_PICK_HEAD / REVERT_HEAD in a multi-commit pick or revert.
IN_PROGRESS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG",
               "rebase-merge", "rebase-apply", "sequencer")
#: Ignored entries that are regenerable, so `worktree remove` may delete them.
CACHE_DIRS = ("__pycache__", ".pytest_cache")
MAX_PATHS = 20
SHA = re.compile(r"[0-9a-f]{40}([0-9a-f]{24})?")


class Refusal(Exception):
    """A one-line reason the whole run cannot proceed."""


# --------------------------------------------------------------------------- #
# plumbing
# --------------------------------------------------------------------------- #
def git(args: List[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run git, output decoded as UTF-8 (pattern: aide.py `git`). Never raises
    on a non-zero exit; a missing git is a Refusal, not a traceback."""
    try:
        return subprocess.run(["git", *args], cwd=str(cwd),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              encoding="utf-8", errors="replace")
    except OSError as exc:
        raise Refusal(f"git could not start ({exc})") from None


def first_line(proc: subprocess.CompletedProcess) -> str:
    return next((l.strip() for l in (proc.stderr + proc.stdout).splitlines()
                 if l.strip()), "no answer")


def resolve_gh(override: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """The gh executable, or (None, why). local.toml decides, through
    reorder_project.find_gh, unless --gh overrides it."""
    if override:
        exe, source = override, "--gh"
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            from reorder_project import find_gh  # needs tomllib (3.11+)
        except ImportError as exc:
            raise Refusal(f"cannot read local.toml ({exc}); pass --gh PATH") from None
        try:
            exe, source = find_gh()
        except SystemExit as exc:     # find_gh's own one-line refusals
            raise Refusal(str(exc.code)) from None
    found = shutil.which(exe)
    if found is None:
        return None, (f"gh is not on PATH" if source == "PATH"
                      else f"no gh at {exe} (from {source})")
    return found, None


def gh(exe: Optional[str], why: Optional[str], args: List[str],
       cwd: Path) -> Tuple[Optional[str], Optional[str]]:
    """``(stdout, None)`` or ``(None, why)``; never raises (pattern: aide.py `_gh`)."""
    if exe is None:
        return None, why
    try:
        res = subprocess.run([exe, *args], cwd=str(cwd),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             encoding="utf-8", errors="replace", timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, f"gh did not answer within {GH_TIMEOUT}s"
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"gh could not start ({exc})"
    if res.returncode != 0:
        return None, f"gh exited {res.returncode}: {first_line(res)}"
    return res.stdout, None


class PRs:
    """Every PR of the repo, from one query, by head and by open base."""

    def __init__(self, rows: Optional[list], why: Optional[str]):
        self.why = why
        self.by_head: Dict[str, list] = {}
        self.open_by_base: Dict[str, list] = {}
        for pr in rows or []:
            self.by_head.setdefault(pr["headRefName"], []).append(pr)
            if pr["state"] == "OPEN":
                self.open_by_base.setdefault(pr["baseRefName"], []).append(pr)

    @classmethod
    def load(cls, exe, why, cwd: Path) -> "PRs":
        out, why = gh(exe, why, ["pr", "list", "--repo", REPO, "--state", "all",
                                 "--limit", str(PR_LIMIT), "--json", PR_FIELDS], cwd)
        if out is None:
            return cls(None, f"PR list unreadable: {why}")
        try:
            rows = json.loads(out)
            if not isinstance(rows, list):
                raise TypeError("not a list")
            for pr in rows:
                for key in PR_FIELDS.split(","):
                    pr[key]
        except (ValueError, TypeError, KeyError) as exc:
            return cls(None, f"PR list unreadable: gh answered no PR JSON ({exc})")
        if len(rows) >= PR_LIMIT:
            return cls(None, f"PR list hit --limit {PR_LIMIT} and may be incomplete")
        return cls(rows, None)

    def excluded(self, branch: str) -> Optional[str]:
        """Why *branch* is never touched, or None."""
        if self.why:
            return self.why
        heads = [p for p in self.by_head.get(branch, []) if p["state"] == "OPEN"]
        if heads:
            return f"open PR #{heads[0]['number']} on it"
        stacked = self.open_by_base.get(branch, [])
        if stacked:
            return f"open PR #{stacked[0]['number']} stacked on it"
        return None


def is_ancestor(a: str, b: str, cwd: Path) -> bool:
    """git merge-base --is-ancestor; a missing object (exit 128) is False."""
    return git(["merge-base", "--is-ancestor", a, b], cwd).returncode == 0


def merged(branch: str, tip: str, prs: PRs, cwd: Path) -> Tuple[bool, str]:
    """SKILL.md step 6's merged test: a MERGED same-repo PR into main whose
    head the tip equals or is an ancestor of."""
    done = [p for p in prs.by_head.get(branch, []) if p["state"] == "MERGED"]
    into_main = [p for p in done if p["baseRefName"] == MAIN
                 and not p["isCrossRepository"]]
    if not into_main:
        other = [p for p in done if p["baseRefName"] != MAIN]
        fork = [p for p in done if p["isCrossRepository"]]
        if fork:
            return False, f"PR #{fork[0]['number']} was merged from a fork"
        if other:
            return False, (f"PR #{other[0]['number']} was merged into "
                           f"{other[0]['baseRefName']}, not {MAIN}")
        return False, f"no PR merged into {MAIN}"
    for pr in into_main:
        if tip == pr["headRefOid"] or is_ancestor(tip, pr["headRefOid"], cwd):
            return True, f"PR #{pr['number']} merged into {MAIN}"
    return False, (f"tip {tip[:12]} is not on the head of merged PR "
                   f"#{into_main[0]['number']}")


def worktrees(cwd: Path) -> List[dict]:
    """`git worktree list --porcelain -z`, one dict per worktree; the first is
    the main checkout."""
    res = git(["worktree", "list", "--porcelain", "-z"], cwd)
    if res.returncode != 0:
        raise Refusal(f"git worktree list failed: {first_line(res)}")
    out, cur = [], None
    for field in res.stdout.split("\0"):
        if not field:
            cur = None
            continue
        key, _, value = field.partition(" ")
        if key == "worktree":
            cur = {"path": value}
            out.append(cur)
        elif cur is not None:
            cur[key] = value or True     # detached, bare, and a bare `locked`
    for wt in out:
        ref = wt.get("branch", "")
        wt["branch"] = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else None
    return out


def refs(prefix: str, cwd: Path) -> Dict[str, str]:
    res = git(["for-each-ref", "--format=%(refname)%00%(objectname)", prefix], cwd)
    if res.returncode != 0:
        raise Refusal(f"git for-each-ref failed: {first_line(res)}")
    out = {}
    for line in res.stdout.splitlines():
        name, _, sha = line.partition("\0")
        out[name[len(prefix):]] = sha
    return out


def same_path(a: str, b: str) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return False


def process_cwds() -> Optional[List[str]]:
    """Every readable /proc/*/cwd, or None where there is no /proc."""
    if not sys.platform.startswith("linux") or not os.path.isdir("/proc/self"):
        return None
    cwds = []
    for pid in os.listdir("/proc"):
        if pid.isdigit() and int(pid) != os.getpid():
            try:
                cwds.append(os.readlink(f"/proc/{pid}/cwd"))
            except OSError:
                pass
    return cwds


def git_path(wt: str, name: str, cwd: Path) -> Optional[str]:
    res = git(["-C", wt, "rev-parse", "--path-format=absolute", "--git-path", name], cwd)
    return res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else None


def is_cache(path: str) -> bool:
    parts = path.rstrip("/").split("/")
    if path.endswith("/") and parts[-1] in CACHE_DIRS:
        return True
    return parts[-1].endswith(".pyc") or any(p in CACHE_DIRS for p in parts[:-1])


def status_offenders(wt: str, cwd: Path) -> Optional[List[str]]:
    """Status lines that are not ignored caches; None when status fails."""
    res = git(["-C", wt, "--no-optional-locks", "status", "--porcelain=v1", "-z",
               "--ignored", "--untracked-files=all"], cwd)
    if res.returncode != 0:
        return None
    fields, bad, i = res.stdout.split("\0"), [], 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        if "R" in xy or "C" in xy:
            i += 1          # the rename/copy source path is its own field
        if xy == "!!" and is_cache(path):
            continue
        bad.append(f"{xy} {path}")
    return bad


# --------------------------------------------------------------------------- #
# deciding
# --------------------------------------------------------------------------- #
def decide(top: Path, gh_exe, gh_why) -> dict:
    """The whole plan; changes nothing but `git fetch --prune origin`."""
    plan = {"remove_worktrees": [], "delete_branches": [], "propose_remote": [],
            "propose_prune": [], "left_alone": [], "notes": []}

    def leave(kind, name, reason):
        plan["left_alone"].append({"kind": kind, "name": name, "reason": reason})

    has_origin = git(["remote", "get-url", REMOTE], top).returncode == 0
    if has_origin:
        f = git(["fetch", "--prune", REMOTE], top)
        if f.returncode != 0:
            plan["notes"].append(f"git fetch --prune {REMOTE} failed "
                                 f"({first_line(f)}); origin refs may be stale")
    else:
        plan["notes"].append(f"no {REMOTE} remote; nothing fetched or proposed there")

    prs = PRs.load(gh_exe, gh_why, top)
    if prs.why:
        plan["notes"].append(f"{prs.why} — nothing is deleted anywhere")
    origin_main = git(["rev-parse", "--verify", "--quiet",
                       f"refs/remotes/{REMOTE}/{MAIN}"], top).stdout.strip() or None

    here = git(["rev-parse", "--show-toplevel"], Path.cwd()).stdout.strip()
    cwds = process_cwds()
    if cwds is None:
        plan["notes"].append("process check unavailable on this platform")
    now = time.time()

    wts = worktrees(top)
    kept_branches: Dict[str, str] = {}      # branch -> worktree path that keeps it
    for n, wt in enumerate(wts):
        path, branch = wt["path"], wt["branch"]
        label = f"{path} [{branch or 'detached'}]"
        reason, why = None, f"detached HEAD on {REMOTE}/{MAIN}"
        if wt.get("bare"):
            continue
        if n == 0:
            reason = "the main checkout"
        elif here and same_path(path, here):
            reason = "this session's own worktree"
        elif wt.get("locked"):
            reason = "locked" + (f": {wt['locked']}" if wt["locked"] is not True else "")
        elif "HEAD" not in wt:
            reason = "no HEAD listed"
        elif wt.get("prunable"):
            reason = "prunable — see the prune proposal"
        elif branch == MAIN:
            reason = f"on {MAIN}"
        elif branch:
            reason = prs.excluded(branch)
            if not reason:
                ok, why = merged(branch, wt["HEAD"], prs, top)
                reason = None if ok else why
        else:
            if prs.why:
                reason = prs.why
            elif not origin_main:
                reason = f"no {REMOTE}/{MAIN} to test a detached HEAD against"
            elif not is_ancestor(wt["HEAD"], origin_main, top):
                reason = f"detached HEAD is not an ancestor of {REMOTE}/{MAIN}"
        if not reason:
            reason = worktree_busy(path, top, now, cwds)
        if reason:
            if n != 0:
                leave("worktree", label, reason)
            if branch:
                kept_branches[branch] = path
            continue
        plan["remove_worktrees"].append({"path": path, "branch": branch,
                                         "head": wt["HEAD"], "why": why})

    for branch, sha in sorted(refs("refs/heads/", top).items()):
        if branch == MAIN:
            continue
        if branch in kept_branches:
            leave("branch", branch, f"checked out in {kept_branches[branch]}")
            continue
        reason = prs.excluded(branch)
        ok, why = (False, reason) if reason else merged(branch, sha, prs, top)
        if ok:
            plan["delete_branches"].append({"branch": branch, "sha": sha, "why": why})
        else:
            leave("branch", branch, why)

    if has_origin:
        for branch, sha in sorted(refs(f"refs/remotes/{REMOTE}/", top).items()):
            if branch in (MAIN, "HEAD"):
                continue
            reason = prs.excluded(branch)
            if not reason and branch in kept_branches:   # its session may push again
                reason = f"checked out in {kept_branches[branch]}"
            ok, why = (False, reason) if reason else merged(branch, sha, prs, top)
            if ok:
                plan["propose_remote"].append({"branch": branch, "sha": sha, "why": why})
            else:
                leave("origin", f"{REMOTE}/{branch}",
                      why if reason else f"remote tip unmerged: {why}")

    dry = git(["worktree", "prune", "--dry-run", "--verbose"], top)
    plan["propose_prune"] = [l for l in (dry.stderr + dry.stdout).splitlines() if l.strip()]
    return plan


def worktree_busy(path: str, top: Path, now: float,
                  cwds: Optional[List[str]]) -> Optional[str]:
    """Why a merged worktree may still be in use, in SKILL.md's order:
    processes, timestamps, operations in progress, then status."""
    try:
        real = os.path.realpath(path)
    except OSError:
        return "path unreadable"
    for c in cwds or []:
        if c == real or c.startswith(real.rstrip(os.sep) + os.sep):
            return "a process has its cwd there"
    for name in ("logs/HEAD", "index"):
        p = git_path(path, name, top)
        try:
            age = now - os.path.getmtime(p) if p else None
        except OSError:
            age = None
        if age is None:
            return f"activity unreadable ({name})"
        if age < IDLE_SECONDS:
            return f"active in the last 24 hours ({name}, {int(age // 3600)}h ago)"
    for name in IN_PROGRESS:
        p = git_path(path, name, top)
        if p is None:
            return f"activity unreadable ({name})"
        if os.path.exists(p):
            return f"operation in progress ({name})"
    bad = status_offenders(path, top)
    if bad is None:
        return "git status failed"
    if bad:
        more = f" (+{len(bad) - MAX_PATHS} more)" if len(bad) > MAX_PATHS else ""
        return "not clean: " + ", ".join(bad[:MAX_PATHS]) + more
    return None


# --------------------------------------------------------------------------- #
# acting
# --------------------------------------------------------------------------- #
def apply_local(plan: dict, top: Path) -> List[dict]:
    results = []
    failed_paths = set()
    for wt in plan["remove_worktrees"]:
        res = git(["worktree", "remove", wt["path"]], top)        # never --force
        ok = res.returncode == 0
        if not ok and wt["branch"]:
            failed_paths.add(wt["branch"])
        results.append({"action": "remove worktree", "target": wt["path"], "ok": ok,
                        "detail": "" if ok else first_line(res)})
    for b in plan["delete_branches"]:
        name, sha = b["branch"], b["sha"]
        now = git(["rev-parse", "--verify", "--quiet", f"refs/heads/{name}"], top).stdout.strip()
        if name in failed_paths:
            ok, detail = False, "its worktree is still there"
        elif now != sha:
            ok, detail = False, f"it moved to {now[:12] or 'nothing'} since the plan"
        else:
            res = git(["branch", "-D", name], top)
            ok, detail = res.returncode == 0, "" if res.returncode == 0 else first_line(res)
        results.append({"action": "delete branch", "target": f"{name} {sha}",
                        "ok": ok, "detail": detail})
    return results


def push_delete(branch: str, sha: str, top: Path) -> Tuple[bool, str]:
    """The leased delete, and what a refusal means (pattern: aide.py
    `_queue_discard`)."""
    pushed = git(["push", f"--force-with-lease=refs/heads/{branch}:{sha}",
                  REMOTE, "--delete", branch], top)
    if pushed.returncode == 0:
        return True, "deleted"
    there = git(["ls-remote", REMOTE, f"refs/heads/{branch}"], top)
    if there.returncode == 0 and not there.stdout.strip():
        git(["update-ref", "-d", f"refs/remotes/{REMOTE}/{branch}"], top)
        return True, "already gone on origin"
    return False, (f"refused ({first_line(pushed)}) — {REMOTE} may hold a "
                   f"commit pushed since")


def delete_remote(pairs: List[Tuple[str, str]], top: Path, gh_exe, gh_why) -> List[dict]:
    f = git(["fetch", "--prune", REMOTE], top)
    prs = PRs.load(gh_exe, gh_why, top)
    checked_out = {w["branch"]: w["path"] for w in worktrees(top) if w["branch"]}
    results = []
    for branch, sha in pairs:
        target = f"{REMOTE}/{branch} {sha}"
        tip = git(["rev-parse", "--verify", "--quiet",
                   f"refs/remotes/{REMOTE}/{branch}"], top).stdout.strip()
        reason = None
        if f.returncode != 0:
            reason = f"git fetch failed ({first_line(f)})"
        elif branch == MAIN:
            reason = f"{MAIN} is never deleted"
        elif not tip:
            results.append({"action": "delete origin branch", "target": target,
                            "ok": True, "detail": "already gone on origin"})
            continue
        elif tip != sha:
            reason = f"it moved to {tip} since the plan; approve the new tip"
        elif branch in checked_out:
            reason = f"checked out in {checked_out[branch]}"
        else:
            reason = prs.excluded(branch)
            if not reason:
                ok, why = merged(branch, tip, prs, top)
                reason = None if ok else f"remote tip unmerged: {why}"
        if reason:
            results.append({"action": "delete origin branch", "target": target,
                            "ok": False, "detail": reason})
            continue
        ok, detail = push_delete(branch, sha, top)
        results.append({"action": "delete origin branch", "target": target,
                        "ok": ok, "detail": "" if detail == "deleted" else detail})
    return results


# --------------------------------------------------------------------------- #
# output
# --------------------------------------------------------------------------- #
def print_plan(plan: dict) -> None:
    def section(title, rows):
        print(title)
        for r in rows or ["(none)"]:
            print(f"  {r}")
    section("Remove worktrees (--apply):",
            [f"{w['path']} [{w['branch'] or 'detached'}] — {w['why']}"
             for w in plan["remove_worktrees"]])
    section("Delete local branches (--apply):",
            [f"{b['branch']} {b['sha']} — {b['why']}" for b in plan["delete_branches"]])
    section("Propose: delete on origin (--delete-remote BRANCH=SHA):",
            [f"{r['branch']}={r['sha']} — {r['why']}" for r in plan["propose_remote"]])
    section("Propose: git worktree prune (--prune):", plan["propose_prune"])
    section("Left alone:",
            [f"{l['kind']} {l['name']}: {l['reason']}" for l in plan["left_alone"]])
    if plan["notes"]:
        section("Notes:", plan["notes"])


def print_results(results: List[dict]) -> None:
    for r in results:
        if r["ok"]:
            print(f"{r['action']}: {r['target']}" + (f" ({r['detail']})" if r["detail"] else ""))
        else:
            print(f"could NOT {r['action']}: {r['target']} — {r['detail']}")


def parse_pair(text: str) -> Tuple[str, str]:
    branch, sep, sha = text.rpartition("=")
    if not sep or not branch or not SHA.fullmatch(sha):
        raise argparse.ArgumentTypeError(f"{text!r} is not BRANCH=<full SHA>")
    return branch, sha


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true",
                      help="re-decide, then remove the worktrees and delete the local branches")
    mode.add_argument("--delete-remote", nargs="+", type=parse_pair, metavar="BRANCH=SHA",
                      help="the approved origin deletes, each leased against its SHA")
    mode.add_argument("--prune", action="store_true", help="the approved git worktree prune")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--gh", help="the gh binary (default: local.toml, else PATH)")
    args = ap.parse_args(argv)
    try:
        res = git(["rev-parse", "--show-toplevel"], Path.cwd())
        if res.returncode != 0:
            raise Refusal(f"not inside a git checkout ({first_line(res)})")
        top = Path(res.stdout.strip())
        plan, failed = None, False
        if args.prune:
            p = git(["worktree", "prune", "--verbose"], top)
            lines = [l for l in (p.stderr + p.stdout).splitlines() if l.strip()]
            ok = p.returncode == 0
            results = [{"action": "git worktree prune", "target": l, "ok": ok,
                        "detail": ""} for l in lines] or (
                [] if ok else [{"action": "git worktree prune", "target": "",
                                "ok": False, "detail": first_line(p)}])
            failed = not ok
        else:
            gh_exe, gh_why = resolve_gh(args.gh)
            if args.delete_remote:
                results = delete_remote(args.delete_remote, top, gh_exe, gh_why)
            else:
                plan = decide(top, gh_exe, gh_why)
                # A PR list that cannot be read decided nothing: say so by exit code.
                failed = any("nothing is deleted" in n for n in plan["notes"])
                results = apply_local(plan, top) if args.apply else []
    except Refusal as exc:
        print(f"cleanup: {exc}", file=sys.stderr)
        return 1
    failed = failed or any(not r["ok"] for r in results)
    if args.json:
        out = {"results": results}
        if plan is not None:
            out = plan if not args.apply else {"plan": plan, "results": results}
        print(json.dumps(out, indent=2))
    else:
        if plan is not None:
            print_plan(plan)
            if results:
                print()
        print_results(results)
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
