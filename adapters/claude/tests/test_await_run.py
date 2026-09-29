"""`await_run.py` — a long command run detached and waited on in bounded slices.

A sub-agent that ends its turn to await a background command hands its caller
the placeholder and is never woken (issue #274), so the validator starts the
suite and the merge through this script and waits inside its turn. What is
held here: the run outlives the process that started it, its exit code comes
back through ``wait``, a run still going answers with its own code, state
lives under the git directory, and the command line reaches no command but
the three fixed ones — the property that lets it be allow-listed. The third,
``ci``, polls ``aide status`` for the queue PR's CI (issue #331); its reading
is driven in-process with a scripted status and a fake clock.

The tests drive ``start_run`` with a command of their own. That seam takes an
argv; the CLI never passes one through.

Stdlib + pytest only; the script is imported as a module.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = FRAMEWORK_ROOT / "adapters" / "claude" / "scripts"
ENGINE = FRAMEWORK_ROOT / "core" / "scripts" / "aide.py"

sys.path.insert(0, str(SCRIPTS_DIR))
import await_run as ar  # noqa: E402  (path shim above)

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="no git on PATH")


def _git(args, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(["init", "-q"], root)
    return root


def _py(code: str) -> list:
    return [sys.executable, "-c", textwrap.dedent(code)]


# --------------------------------------------------------------------------- #
# state location
# --------------------------------------------------------------------------- #
def test_state_lives_under_the_git_dir_not_the_working_tree(repo: Path):
    directory = ar.state_dir(repo)
    assert directory == (repo / ".git" / ar.STATE_DIR).resolve()
    ar.start_run("suite", _py("pass"), repo, directory)
    assert ar.wait_run(sorted(directory.glob("*.start"))[0].stem, directory, 30) == 0
    # Nothing a run writes is visible to git, so `aide scope` never sees it.
    assert _git(["status", "--porcelain", "--untracked-files=all"], repo) == ""


def test_a_worktree_keeps_its_own_state(repo: Path, tmp_path: Path):
    """`--git-dir` is per worktree, so two isolated agents never share labels."""
    _git(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
          "--allow-empty", "-m", "root"], repo)
    tree = tmp_path / "wt"
    _git(["worktree", "add", "-q", str(tree)], repo)
    ours, theirs = ar.state_dir(repo), ar.state_dir(tree)
    assert ours != theirs
    assert (repo / ".git").resolve() in theirs.parents


def test_outside_a_git_checkout_is_a_usage_error(tmp_path: Path, capsys,
                                                 monkeypatch):
    bare = tmp_path / "not-a-repo"
    bare.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    assert ar.main(["wait", "suite-20260101-000000"], root=bare) == ar.EXIT_USAGE
    assert "not a git checkout" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# start / wait
# --------------------------------------------------------------------------- #
def test_the_run_survives_the_process_that_started_it(repo: Path):
    """The starter exits at once; the command finishes without it.

    The command holds until the test says go, so "the starter returned before
    the command finished" is an ordering, not a race against a sleep."""
    directory = ar.state_dir(repo)
    go = repo.parent / "go.txt"
    marker = repo.parent / "survived.txt"
    command = textwrap.dedent(f"""
        import pathlib, time
        while not pathlib.Path({str(go)!r}).exists():
            time.sleep(0.1)
        pathlib.Path({str(marker)!r}).write_text("ok")
    """)
    starter = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(SCRIPTS_DIR)!r})
        import await_run as ar
        from pathlib import Path
        cmd = [sys.executable, "-c", {command!r}]
        print(ar.start_run("suite", cmd, Path({str(repo)!r}), Path({str(directory)!r})))
    """)
    done = subprocess.run([sys.executable, "-c", starter], capture_output=True,
                          text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    label = done.stdout.strip()
    assert not marker.exists()
    go.write_text("go")
    assert ar.wait_run(label, directory, 60) == 0
    assert marker.read_text() == "ok"


def test_the_commands_exit_code_is_waits_exit_code(repo: Path, capsys):
    directory = ar.state_dir(repo)
    label = ar.start_run("suite", _py("""
        print("1 failed, 3 passed")
        raise SystemExit(1)
    """), repo, directory)
    assert ar.main(["wait", label, "--for", "60"], root=repo) == 1
    out = capsys.readouterr().out
    assert "exit 1" in out and "1 failed, 3 passed" in out


def test_a_run_still_going_answers_with_its_own_code_and_the_log_tail(repo: Path, capsys):
    directory = ar.state_dir(repo)
    label = ar.start_run("suite", _py("""
        import time
        print("collected 900 items", flush=True)
        time.sleep(15)
    """), repo, directory)
    # Long enough for the line to reach the log; far short of the run.
    code = ar.main(["wait", label, "--for", "3"], root=repo)
    out = capsys.readouterr().out
    assert code == ar.EXIT_RUNNING
    assert "still running" in out and "elapsed" in out
    assert "collected 900 items" in out
    assert f"wait {label}" in out
    ar.stop_run(label, directory)


_OWN_CODES = ("EXIT_RUNNING", "EXIT_USAGE", "EXIT_NOT_STARTED", "EXIT_DIED",
              "EXIT_STOPPED", "EXIT_BUSY", "EXIT_STOP_REFUSED")


def test_the_wrappers_own_codes_collide_with_nothing_it_reports():
    """pytest exits 0–5 and `aide merge` 0–2, a signal death reads 128+N; a
    caller must tell every one of them from the wrapper's own."""
    codes = [getattr(ar, name) for name in _OWN_CODES]
    assert len(set(codes)) == len(codes)
    for code in codes:
        assert code not in range(0, 6)
        assert not 128 < code < 256


def test_a_command_that_cannot_start_is_recorded_not_left_running(repo: Path, capsys):
    directory = ar.state_dir(repo)
    label = ar.start_run("suite", [str(repo / "no-such-program")], repo, directory)
    assert ar.wait_run(label, directory, 60) == ar.EXIT_NOT_STARTED
    assert "could not start" in capsys.readouterr().out


def test_two_starts_in_one_second_get_two_labels(repo: Path):
    directory = ar.state_dir(repo)
    first = ar.start_run("suite", _py("pass"), repo, directory)
    assert ar.wait_run(first, directory, 60) == 0  # one live run at a time
    second = ar.start_run("suite", _py("pass"), repo, directory)
    assert ar.wait_run(second, directory, 60) == 0
    assert first != second
    for label in (first, second):
        assert ar._LABEL_RE.match(label), label


def test_a_torn_run_record_is_a_usage_error_not_a_traceback(repo: Path, capsys):
    directory = ar.state_dir(repo)
    label = ar.start_run("suite", _py("pass"), repo, directory)
    ar.wait_run(label, directory, 30)
    (directory / f"{label}.start").write_text('{"label": ', encoding="utf-8")
    assert ar.main(["wait", label], root=repo) == ar.EXIT_USAGE
    assert "unreadable run record" in capsys.readouterr().err
    # The record is written whole: no temporary file is left beside it.
    assert not list(directory.glob("*.tmp"))


def test_the_wait_is_capped_under_the_tool_ceiling(repo: Path, monkeypatch):
    seen = {}
    monkeypatch.setattr(ar, "wait_run",
                        lambda label, directory, seconds: seen.setdefault("s", seconds) and 0)
    ar.main(["wait", "suite-20260101-000000", "--for", "3600"], root=repo)
    assert seen["s"] == ar.MAX_WAIT
    assert ar.MAX_WAIT * 1000 < 600000


# --------------------------------------------------------------------------- #
# the allow-list property — the CLI runs two fixed commands and nothing else
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("argv", [
    ["start", "python", "-c", "print(1)"],
    ["start", "suite", "--", "rm", "-rf", "/"],
    ["start", "merge", "014", "--findings", "x"],
    ["start", "merge", "014", "--findings", "nit=1;rm"],
    ["start", "merge", "014", "extra"],
    ["start", "ci", "--", "rm"],
    ["start", "ci", "aide/queue-004"],
    ["wait", "../../etc/passwd"],
])
def test_no_command_line_reaches_an_arbitrary_command(repo: Path, argv, monkeypatch):
    launched = []
    monkeypatch.setattr(ar, "start_run", lambda *a, **k: launched.append(a) or "x")
    assert ar.main(argv, root=repo, engine=ENGINE) == ar.EXIT_USAGE
    assert launched == []


def test_merge_is_the_engine_verb_with_its_flags_as_single_elements(tmp_path: Path):
    cmd = ar.merge_command(ENGINE, 14, 2, "--no-test")
    assert cmd[:4] == [sys.executable, str(ENGINE), "merge", "014"]
    # A base that looks like a flag stays the value of --base.
    assert cmd[4:] == ["--rounds=2", "--base=--no-test"]


def test_findings_pass_through_in_the_engines_shape():
    cmd = ar.merge_command(ENGINE, 14, 3, None, "blocking=0,minor=1,nit=2")
    assert cmd[4:] == ["--rounds=3", "--findings=blocking=0,minor=1,nit=2"]


def test_a_flag_shaped_base_is_refused_at_the_cli(repo: Path, monkeypatch):
    monkeypatch.setattr(ar, "start_run", lambda *a, **k: pytest.fail("launched"))
    assert ar.main(["start", "merge", "14", "--base=-x"], root=repo,
                   engine=ENGINE) == ar.EXIT_USAGE


def test_suite_is_aide_test_so_the_run_is_recorded(tmp_path: Path):
    """The engine's `test` verb, which runs the configured command exactly as
    `aide merge` does and records the result the merge may take (#275)."""
    (tmp_path / "aide.toml").write_text(
        '[python]\ntest_command = "python -m pytest -q tests/unit"\n', encoding="utf-8")
    assert ar.suite_command(tmp_path, ENGINE) == [sys.executable, str(ENGINE), "test"]


def test_an_empty_test_command_is_refused_before_launch(tmp_path: Path):
    (tmp_path / "aide.toml").write_text(
        '[python]\ntest_command = ""\n', encoding="utf-8")
    with pytest.raises(ar.UsageError, match="test_command is empty"):
        ar.suite_command(tmp_path, ENGINE)


def test_a_missing_engine_is_a_usage_error(repo: Path, capsys):
    assert ar.main(["start", "suite"], root=repo,
                   engine=repo / ".aide" / "scripts" / "aide.py") == ar.EXIT_USAGE
    assert "engine" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# ci — the queue-end step's wait on the queue PR's CI (issue #331)
# --------------------------------------------------------------------------- #
def _stack(checks: str, pr: str = "#7/open", *below: str,
           branch: str = "aide/queue-004") -> str:
    lines = ["  stack: 1/1 — bottom first",
             f"  stack 1: {branch} base=main pr={pr} checks={checks} "
             f"lower=- orphaned=no",
             *(f"    {line}" for line in below),
             "  runnable: no — the stack is at the cap"]
    return "\n".join(lines) + "\n"


def _poll(readings, *, step: float = 30.0, **bounds):
    """Run `poll_ci` over scripted `aide status` readings on a fake clock
    that advances *step* seconds per sleep; the code and the readings used."""
    now = [0.0]
    queue = list(readings)
    used = []

    def read():
        used.append(1)
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        return item if isinstance(item, tuple) else (0, item)

    def sleep(seconds):
        now[0] += step

    code = ar.poll_ci("aide/queue-004", read, clock=lambda: now[0],
                      sleep=sleep, **bounds)
    return code, len(used)


def test_ci_waits_through_pending_and_answers_success(capsys):
    code, reads = _poll([_stack("none"), _stack("pending"), _stack("pending"),
                         _stack("success")])
    assert code == ar.CI_SUCCESS == 0 and reads == 4
    out = capsys.readouterr().out
    # Each change is logged once, and the verdict is the last line.
    assert out.count("checks=pending") == 1
    assert out.strip().splitlines()[-1] == "ci: success"


def test_ci_failure_names_the_failing_checks(capsys):
    code, _ = _poll([_stack("failure", "#7/open", "failing check: test (windows)")])
    assert code == ar.CI_FAILURE
    assert "failing check: test (windows)" in capsys.readouterr().out


def test_a_first_none_is_not_the_answer_but_a_lasting_one_is():
    """Just after `queue ready` CI may not have registered a run yet."""
    code, reads = _poll([_stack("none")], step=30.0, grace=300)
    assert code == ar.CI_NONE
    assert reads == 11                  # 0 s, 30 s, … 300 s
    code, reads = _poll([_stack("none"), _stack("success")], grace=300)
    assert (code, reads) == (ar.CI_SUCCESS, 2)


def test_unknown_is_the_answer_only_when_it_repeats():
    code, reads = _poll([_stack("unknown"), _stack("unknown"), _stack("success")])
    assert (code, reads) == (ar.CI_SUCCESS, 3)
    code, reads = _poll([_stack("unknown", "#7/open", "checks unknown: timeout")])
    assert (code, reads) == (ar.CI_UNKNOWN, ar.CI_UNKNOWN_READS)


def test_a_failed_status_run_reads_as_unknown_not_as_no_pr():
    code, reads = _poll([(1, ""), _stack("success")])
    assert (code, reads) == (ar.CI_SUCCESS, 2)


@pytest.mark.parametrize("reading", [
    _stack("-", "none"),                                # no PR, or local mode
    _stack("success", branch="aide/queue-003"),         # not this branch
    "  stack: 0/1\n",                                   # merged, or never one
])
def test_no_pr_or_no_stack_line_ends_at_once(reading):
    assert _poll([reading]) == (ar.CI_NO_PR, 1)


def test_ci_gives_up_pending_at_the_ceiling():
    code, reads = _poll([_stack("pending")], ceiling=90)
    assert (code, reads) == (ar.CI_PENDING, 4)


def test_start_ci_polls_the_branch_checked_out(repo: Path):
    _git(["-c", "user.email=t@e", "-c", "user.name=T", "commit", "-q",
          "--allow-empty", "-m", "init"], repo)
    _git(["switch", "-q", "-c", "aide/queue-004"], repo)
    cmd = ar.ci_command(repo, ENGINE)
    assert cmd[:2] == [sys.executable, str(SCRIPTS_DIR / "await_run.py")]
    assert cmd[2:] == ["poll-ci", "--branch=aide/queue-004"]
    _git(["switch", "-q", "--detach"], repo)
    with pytest.raises(ar.UsageError, match="detached"):
        ar.ci_command(repo, ENGINE)


def test_the_ci_codes_collide_with_none_of_the_wrappers_own():
    ci = [getattr(ar, n) for n in ("CI_SUCCESS", "CI_FAILURE", "CI_NONE",
                                   "CI_UNKNOWN", "CI_NO_PR", "CI_PENDING")]
    assert len(set(ci)) == len(ci)
    assert not set(ci) & {getattr(ar, n) for n in _OWN_CODES}
    assert 1 not in ci                  # a crash of the poll itself
    text = ar.build_parser().format_help()
    for code in ci[1:]:
        assert f"\n    {code} " in text, code
    assert f"{ar.CI_NONE_GRACE} s" in text and f"{ar.CI_CEILING} s" in text


# --------------------------------------------------------------------------- #
# shipped and pre-approved
# --------------------------------------------------------------------------- #
def test_the_framework_settings_pre_approve_it_under_both_interpreter_names():
    settings = json.loads((FRAMEWORK_ROOT / "adapters" / "claude" / "settings.json")
                          .read_text(encoding="utf-8"))
    allow = settings["permissions"]["allow"]
    for py in ("python", "python3"):
        assert f"Bash({py} .claude/scripts/await_run.py:*)" in allow


def test_help_names_the_exit_codes():
    text = ar.build_parser().format_help()
    for name in _OWN_CODES:
        assert f"\n    {getattr(ar, name)} " in text, name


# --------------------------------------------------------------------------- #
# liveness by lock, stop, and one live run per worktree
# --------------------------------------------------------------------------- #
_HOLD = """
    import time
    print("started", flush=True)
    time.sleep(60)
"""


def _live(repo: Path):
    directory = ar.state_dir(repo)
    return directory, ar.start_run("suite", _py(_HOLD), repo, directory)


def test_the_lock_is_held_from_start_until_the_run_ends(repo: Path):
    directory, label = _live(repo)
    try:
        # `start` returned, so the supervisor already holds it: no race.
        assert ar._lock_held(directory / f"{label}.lock")
        assert ar.run_state(directory, label) == "live"
    finally:
        ar.stop_run(label, directory)
    assert not ar._lock_held(directory / f"{label}.lock")


@pytest.mark.skipif(sys.platform == "win32", reason="SIGKILL is POSIX")
def test_a_killed_supervisor_reads_as_died_at_once(repo: Path, capsys):
    import os
    import signal
    import time
    directory, label = _live(repo)
    record = json.loads((directory / f"{label}.start").read_text(encoding="utf-8"))
    os.kill(record["pid"], signal.SIGKILL)
    began = time.monotonic()
    try:
        assert ar.wait_run(label, directory, 60) == ar.EXIT_DIED
    finally:
        os.killpg(record["pid"], signal.SIGKILL)  # the orphaned command
    assert time.monotonic() - began < 10, "a dead run was waited on like a live one"
    assert "died without an exit code" in capsys.readouterr().out
    assert (directory / f"{label}.exit").read_text().strip() == str(ar.EXIT_DIED)


def test_stop_kills_the_command_and_its_children(repo: Path, tmp_path: Path, capsys):
    """The command spawns a grandchild; stop takes both, and the run records
    STOPPED with its log kept."""
    pid_file = tmp_path / "grandchild.pid"
    directory = ar.state_dir(repo)
    label = ar.start_run("suite", _py(f"""
        import subprocess, sys, time, pathlib
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        pathlib.Path({str(pid_file)!r}).write_text(str(child.pid))
        print("spawned", flush=True)
        time.sleep(60)
    """), repo, directory)
    for _ in range(200):
        if pid_file.exists() and pid_file.read_text():
            break
        __import__("time").sleep(0.05)
    grandchild = int(pid_file.read_text())

    assert ar.main(["stop", label], root=repo) == 0
    assert (directory / f"{label}.exit").read_text().strip() == str(ar.EXIT_STOPPED)
    assert "spawned" in capsys.readouterr().out  # the log survives
    assert ar.wait_run(label, directory, 5) == ar.EXIT_STOPPED
    assert not _running(grandchild), "stop left the command's child alive"


def _running(pid: int) -> bool:
    import time
    for _ in range(100):
        if sys.platform == "win32":
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                 capture_output=True, text=True).stdout
            alive = str(pid) in out
        else:
            import os
            try:
                os.kill(pid, 0)
                # A zombie awaiting its (killed) parent's reaper is gone too.
                stat = Path(f"/proc/{pid}/stat")
                alive = not (stat.exists() and ") Z" in stat.read_text())
            except ProcessLookupError:
                alive = False
        if not alive:
            return False
        time.sleep(0.05)
    return True


def test_stop_on_a_finished_run_reports_it(repo: Path, capsys):
    directory = ar.state_dir(repo)
    label = ar.start_run("suite", _py("raise SystemExit(3)"), repo, directory)
    assert ar.wait_run(label, directory, 60) == 3
    capsys.readouterr()
    assert ar.main(["stop", label], root=repo) == 0
    assert "exit 3" in capsys.readouterr().out
    assert (directory / f"{label}.exit").read_text().strip() == "3"


def test_start_refuses_while_a_run_is_live_and_names_it(repo: Path, capsys):
    directory, label = _live(repo)
    try:
        assert ar.main(["start", "suite"], root=repo, engine=ENGINE) == ar.EXIT_BUSY
        out = capsys.readouterr().out
        assert label in out and "Wait on this label instead" in out
        assert "started" in out  # its log tail
        assert ar._open_runs(directory) == [label]
    finally:
        ar.stop_run(label, directory)


def test_start_proceeds_once_a_dead_run_is_marked(repo: Path):
    directory = ar.state_dir(repo)
    directory.mkdir(parents=True)
    dead = "suite-20260101-000000"
    (directory / f"{dead}.start").write_text(
        json.dumps({"label": dead, "argv": ["x"], "started": 0, "pid": 1}),
        encoding="utf-8")
    label = ar.start_run("suite", _py("pass"), repo, directory)
    assert (directory / f"{dead}.exit").read_text().strip() == str(ar.EXIT_DIED)
    assert ar.wait_run(label, directory, 60) == 0


def test_prune_removes_old_ended_runs_and_never_a_live_one(repo: Path):
    import os
    import time
    directory, live = _live(repo)
    try:
        old = "suite-20200101-000000"
        for suffix in ("start", "lock", "log", "exit"):
            path = directory / f"{old}.{suffix}"
            path.write_text("0\n", encoding="utf-8")
            os.utime(path, (0, 0))
        for path in directory.glob(f"{live}.*"):
            os.utime(path, (0, 0))
        ar._prune(directory, time.time())
        assert not list(directory.glob(f"{old}.*"))
        assert ar.run_state(directory, live) == "live"
        assert {p.suffix for p in directory.glob(f"{live}.*")} >= {
            ".start", ".lock", ".log"}
    finally:
        ar.stop_run(live, directory)


def test_stop_reaches_no_pid_but_a_valid_labels(repo: Path, monkeypatch):
    monkeypatch.setattr(ar, "_kill_tree", lambda *a, **k: pytest.fail("killed"))
    for argv in (["stop", "1234"], ["stop", "../x"], ["stop", "suite-20260101-000000"]):
        assert ar.main(argv, root=repo) == ar.EXIT_USAGE


# --------------------------------------------------------------------------- #
# the launch window — a run being started is never read as dead
# --------------------------------------------------------------------------- #
def _await_file(pattern_dir: Path, pattern: str, seconds: float = 20):
    import time
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        found = sorted(pattern_dir.glob(pattern)) if pattern_dir.is_dir() else []
        if found:
            return found[0]
        time.sleep(0.02)
    raise AssertionError(f"no {pattern} under {pattern_dir}")


def _await_log(directory: Path, label: str, text: str, seconds: float = 20):
    import time
    deadline = time.monotonic() + seconds
    log = directory / f"{label}.log"
    while time.monotonic() < deadline:
        if log.is_file() and text in log.read_text(encoding="utf-8", errors="replace"):
            return
        time.sleep(0.02)
    raise AssertionError(f"{text!r} never reached {log}")


def test_a_concurrent_start_sees_a_launching_run_as_busy_never_dead(repo: Path):
    """The review's repro: the gap between `Popen` returning and the
    supervisor taking its lock, widened to a second by a test-only seam."""
    import threading
    directory = ar.state_dir(repo)
    first = {}
    launcher = threading.Thread(target=lambda: first.setdefault(
        "label", ar.start_run("suite", _py(_HOLD), repo, directory,
                              _pre_lock_delay=1.0)))
    launcher.start()
    try:
        label = _await_file(directory, "*.start").stem
        # Mid-launch: the run reads dead, and neither a wait nor a start may
        # act on that reading.
        assert ar.run_state(directory, label) == "dead"
        assert ar.wait_run(label, directory, 0) == ar.EXIT_RUNNING
        with pytest.raises(ar.BusyError) as busy:
            ar.start_run("suite", _py("pass"), repo, directory)
        assert busy.value.label == label
        assert not (directory / f"{label}.exit").exists()
        assert ar.run_state(directory, label) == "live"
    finally:
        launcher.join(30)
        ar.stop_run(first.get("label") or label, directory)
    assert (directory / f"{label}.exit").read_text().strip() == str(ar.EXIT_STOPPED)


# --------------------------------------------------------------------------- #
# stop on a merge — SIGTERM only, so aide merge can restore its claim branch
# --------------------------------------------------------------------------- #
_TRAPS_SIGTERM = """
    import signal, sys, time
    def restore(*_):
        print("aide merge: interrupted - claim branch restored; re-run merge", flush=True)
        sys.exit(1)
    signal.signal(signal.SIGTERM, restore)
    print("ready", flush=True)
    time.sleep(60)
"""

_IGNORES_SIGTERM = """
    import signal, time
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    print("ready", flush=True)
    time.sleep(60)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_stop_on_a_merge_sends_sigterm_only_and_its_restore_reaches_the_tail(
        repo: Path, monkeypatch, capsys):
    kills = []
    real = ar._kill_tree
    monkeypatch.setattr(ar, "_kill_tree",
                        lambda pid, hard: kills.append(hard) or real(pid, hard))
    directory = ar.state_dir(repo)
    label = ar.start_run("merge-014", _py(_TRAPS_SIGTERM), repo, directory)
    _await_log(directory, label, "ready")
    assert ar.stop_run(label, directory) == 0
    assert kills == [False], "a merge run was hard-killed"
    out = capsys.readouterr().out
    assert "claim branch restored" in out
    assert "own exit code, before the stop was recorded: 1" in out
    assert (directory / f"{label}.exit").read_text().strip() == str(ar.EXIT_STOPPED)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_a_merge_that_outlives_sigterm_is_left_running_and_reported(
        repo: Path, monkeypatch, capsys):
    import os
    import signal
    monkeypatch.setattr(ar, "_MERGE_GRACE", 1.0)
    directory = ar.state_dir(repo)
    label = ar.start_run("merge-014", _py(_IGNORES_SIGTERM), repo, directory)
    pid = json.loads((directory / f"{label}.start").read_text())["pid"]
    try:
        _await_log(directory, label, "ready")
        assert ar.main(["stop", label], root=repo) == ar.EXIT_STOP_REFUSED
        assert "NOT stopped" in capsys.readouterr().out
        assert ar.run_state(directory, label) == "live"
        assert not (directory / f"{label}.exit").exists()
    finally:
        os.killpg(pid, signal.SIGKILL)
        ar.wait_run(label, directory, 20)


def test_on_windows_a_merge_run_is_refused_not_killed(repo: Path, monkeypatch, capsys):
    monkeypatch.setattr(ar, "_NO_GRACEFUL_STOP", True)
    monkeypatch.setattr(ar, "_kill_tree", lambda *a, **k: pytest.fail("killed"))
    directory = ar.state_dir(repo)
    label = ar.start_run("merge-014", _py(_HOLD), repo, directory)
    try:
        assert ar.stop_run(label, directory) == ar.EXIT_STOP_REFUSED
        assert "never killed on Windows" in capsys.readouterr().out
        assert ar.run_state(directory, label) == "live"
    finally:
        monkeypatch.undo()
        pid = json.loads((directory / f"{label}.start").read_text())["pid"]
        ar._kill_tree(pid, hard=True)
        ar.wait_run(label, directory, 20)
