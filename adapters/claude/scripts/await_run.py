#!/usr/bin/env python
"""Run the suite or a merge detached, and wait on it in bounded slices.

A command that outlives the Bash tool's timeout is moved to the background,
and a sub-agent that then ends its turn "to wait for the notification" hands
its caller that placeholder as its final report; it is not woken again, and
the command dies with the session. Waiting idle longer than the sub-agent's
prompt-cache lifetime re-writes its whole context on the next request.
`.aide/conventions.md` §9 states the rule; this is how the Claude adapter
follows it:

    python .claude/scripts/await_run.py start suite
    python .claude/scripts/await_run.py start merge NNN [--rounds R] [--base B]
                                                  [--findings blocking=A,minor=B,nit=C]
    python .claude/scripts/await_run.py wait <label> [--for SECONDS]
    python .claude/scripts/await_run.py stop <label>

``start`` launches the command fully detached, with its output going to a log,
and prints a label once the run is under way. It refuses while another run in
this worktree is still live, naming it: wait on that label instead. ``wait``
blocks for at most ``--for`` seconds (default 240, under a 5-minute cache;
capped at 540, under the Bash tool's 600000 ms ceiling) and returns the moment
the command exits, or the moment its supervisor is found dead. ``stop`` kills
the run's whole process tree and records it as stopped; a run that already
ended is reported, not an error.

A run is live while its supervisor holds an exclusive lock on
``<label>.lock``; the supervisor writes ``.exit`` before that lock is released
at its exit, so a free lock with no ``.exit`` means it died.

It runs **only** those two commands, so allow-listing it lets nothing else
through: ``suite`` is the project's ``[python] test_command``, resolved by the
engine exactly as ``aide merge`` resolves it (a leading ``python`` bound to the
venv), and ``merge`` is ``.aide/scripts/aide.py merge`` under this interpreter.

Exit codes:

    the command's own   wait: it finished; a red suite reads as red
    75                  wait: still running — call wait again (EX_TEMPFAIL)
    90                  wait: the run died without an exit code
    91                  wait: the run was stopped (``stop``)
    92                  start: another run is live here — wait on the label
                        it names instead
    64                  await_run itself could not do what was asked (EX_USAGE)
    127                 recorded when the command could not be started at all
    0                   start: launched; stop: stopped, or already ended

None of 64, 75 or 90–92 is a code pytest (0–5) or ``aide merge`` returns, and
none is 128+N, a signal death. State lives under the git directory
(``git rev-parse --git-dir``, which is per worktree), in
``aide-runs/<label>.{start,lock,log,exit}``, so it never dirties the working
tree or reaches ``aide scope``. It is this run's state only, never a history:
finished runs older than a week are removed by the next ``start``.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

# .claude/scripts/await_run.py -> parents[2] is the project root.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

STATE_DIR = "aide-runs"
DEFAULT_WAIT = 240
MAX_WAIT = 540
TAIL_LINES = 40
EXIT_RUNNING = 75
EXIT_USAGE = 64
EXIT_NOT_STARTED = 127
EXIT_DIED = 90
EXIT_STOPPED = 91
EXIT_BUSY = 92
_POLL = 0.5
# How long `start` waits for the supervisor to take its lock, and `stop` for
# a killed tree to let go of it.
_LOCK_BOUND = 30.0
_STOP_GRACE = 5.0
_KEEP_SECONDS = 7 * 24 * 3600
_LABEL_RE = re.compile(r"^[a-z]+(?:-\d+)?-\d{8}-\d{6}(?:-\d+)?$")
# The shape `aide merge --findings` takes; anything else never reaches it.
_FINDINGS_RE = re.compile(r"^(?:blocking|minor|nit)=\d+(?:,(?:blocking|minor|nit)=\d+)*$")

# Run by a separate interpreter, so the detached side depends on nothing but
# the stdlib. It is handed its command as data, from `start_run`; nothing on
# this script's command line can reach it, which is the allow-list property.
_SUPERVISOR = r"""
import json, os, subprocess, sys
spec = json.loads(sys.argv[1])
# Held for this process's whole life and released only by its exit, after
# `.exit` is written: a free lock with no `.exit` is a supervisor that died.
lock = os.open(spec["lock"], os.O_RDWR | os.O_CREAT)
if os.name == "nt":
    import msvcrt
    msvcrt.locking(lock, msvcrt.LK_LOCK, 1)
else:
    import fcntl
    fcntl.flock(lock, fcntl.LOCK_EX)
code = int(spec["not_started"])
env = dict(os.environ, PYTHONUNBUFFERED="1")
try:
    with open(spec["log"], "ab") as log:
        try:
            code = subprocess.call(spec["argv"], cwd=spec["cwd"], env=env,
                                   stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT)
        except OSError as exc:
            log.write(("await_run: could not start %r: %s\n"
                       % (spec["argv"], exc)).encode("utf-8"))
finally:
    tmp = spec["exit"] + ".tmp"
    with open(tmp, "w") as fh:
        fh.write("%d\n" % code)
    os.replace(tmp, spec["exit"])
"""


class UsageError(Exception):
    """Something this script was asked to do and cannot; exits EXIT_USAGE."""


class BusyError(Exception):
    """A run is live in this worktree; `start` refuses with EXIT_BUSY."""

    def __init__(self, label: str):
        super().__init__(label)
        self.label = label


class _Parser(argparse.ArgumentParser):
    # argparse exits 2 on a bad command line, which is also pytest's
    # "interrupted": a caller reading the code must be able to tell them apart.
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def state_dir(root: Path) -> Path:
    """``<git-dir>/aide-runs`` for the checkout at *root* (per worktree)."""
    try:
        out = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=str(root),
                             capture_output=True, text=True, check=False)
    except OSError as exc:
        raise UsageError(f"git could not be run: {exc}") from exc
    if out.returncode != 0 or not out.stdout.strip():
        raise UsageError(f"{root} is not a git checkout: {out.stderr.strip()}")
    return (root / out.stdout.strip()).resolve() / STATE_DIR


def _load_engine(engine: Path):
    spec = importlib.util.spec_from_file_location("_aide_engine_await", engine)
    if spec is None or spec.loader is None or not engine.is_file():
        raise UsageError(f"the engine is not at {engine}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def suite_command(root: Path, engine: Path) -> List[str]:
    """The project's test command, resolved by the engine as `aide merge` does."""
    aide = _load_engine(engine)
    try:
        config = aide.load_config(root)
    except Exception as exc:  # the engine's ConfigError names the file
        raise UsageError(str(exc)) from exc
    cmd = aide.resolve_test_command(root, config)
    if not cmd:
        raise UsageError("[python] test_command is empty in aide.toml")
    return cmd


def merge_command(engine: Path, number: int, rounds: Optional[int],
                  base: Optional[str], findings: Optional[str] = None) -> List[str]:
    cmd = [sys.executable, str(engine), "merge", f"{number:03d}"]
    if rounds is not None:
        cmd.append(f"--rounds={rounds}")
    if findings is not None:
        cmd.append(f"--findings={findings}")
    if base is not None:
        # One argv element, so a value can never be read as another flag.
        cmd.append(f"--base={base}")
    return cmd


def _prune(directory: Path, now: float) -> None:
    """Remove runs that ended over a week ago. Only a run with an ``.exit``
    is a candidate, so a live one is never touched."""
    for exit_file in directory.glob("*.exit"):
        try:
            if now - exit_file.stat().st_mtime < _KEEP_SECONDS:
                continue
            for suffix in (".start", ".lock", ".log", ".exit"):
                exit_file.with_suffix(suffix).unlink(missing_ok=True)
        except OSError:
            pass


def _lock_held(lock: Path) -> bool:
    """True while some process holds *lock*; probes without blocking."""
    try:
        fd = os.open(str(lock), os.O_RDWR | os.O_CREAT)
    except OSError:
        return False
    try:
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError:
                return True
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return True
            fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def run_state(directory: Path, label: str) -> str:
    """``"ended"`` (an ``.exit`` exists), ``"live"`` or ``"dead"``."""
    exit_file = directory / f"{label}.exit"
    if exit_file.is_file():
        return "ended"
    if _lock_held(directory / f"{label}.lock"):
        return "live"
    # Re-checked: the supervisor writes `.exit` and only then lets go.
    return "ended" if exit_file.is_file() else "dead"


def _mark(directory: Path, label: str, code: int) -> None:
    _write_atomic(directory / f"{label}.exit", f"{code}\n")


def _record(directory: Path, label: str) -> dict:
    start = directory / f"{label}.start"
    try:
        return json.loads(start.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError(f"unreadable run record {start}: {exc}") from exc


def _elapsed(record: dict) -> int:
    return int(time.time() - float(record.get("started", time.time())))


def _open_runs(directory: Path) -> List[str]:
    return sorted(p.stem for p in directory.glob("*.start")
                  if not p.with_suffix(".exit").exists())


def start_run(kind: str, argv: List[str], cwd: Path, directory: Path) -> str:
    """Launch *argv* detached under the supervisor; return its label.

    The seam the tests drive with a command of their own. The CLI reaches it
    only with `suite_command` or `merge_command`.
    """
    directory.mkdir(parents=True, exist_ok=True)
    now = time.time()
    _prune(directory, now)
    # One run at a time per worktree. A live one is refused by name, which is
    # how a re-dispatched agent finds the run it should wait on; a dead one
    # is recorded as dead and stops counting.
    for other in _open_runs(directory):
        state = run_state(directory, other)
        if state == "live":
            raise BusyError(other)
        if state == "dead":
            _mark(directory, other, EXIT_DIED)
    stem = f"{kind}-{time.strftime('%Y%m%d-%H%M%S', time.localtime(now))}"
    label, n = stem, 1
    while (directory / f"{label}.start").exists():
        n += 1
        label = f"{stem}-{n}"
    paths = {s: directory / f"{label}.{s}" for s in ("start", "lock", "log", "exit")}
    record = {"label": label, "argv": argv, "cwd": str(cwd), "started": now}
    _write_atomic(paths["start"], json.dumps(record))
    spec = json.dumps({"argv": argv, "cwd": str(cwd), "log": str(paths["log"]),
                       "exit": str(paths["exit"]), "lock": str(paths["lock"]),
                       "not_started": EXIT_NOT_STARTED})
    kwargs = dict(cwd=str(cwd), stdin=subprocess.DEVNULL,
                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                  close_fds=True)
    if os.name == "nt":
        # Its own process group and no console, so neither the Bash tool's
        # cleanup nor a closing window takes the run with it.
        kwargs["creationflags"] = (subprocess.DETACHED_PROCESS
                                   | subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen([sys.executable, "-c", _SUPERVISOR, spec], **kwargs)
    except OSError as exc:
        paths["start"].unlink()
        raise UsageError(f"could not launch the run: {exc}") from exc
    record["pid"] = proc.pid
    _write_atomic(paths["start"], json.dumps(record))
    # Not returned until the supervisor holds its lock (or has already
    # finished): before that, a liveness probe would read the run as dead.
    deadline = time.monotonic() + _LOCK_BOUND
    while run_state(directory, label) == "dead":
        if proc.poll() is not None and run_state(directory, label) == "dead":
            _mark(directory, label, EXIT_DIED)
            break
        if time.monotonic() > deadline:
            raise UsageError(f"the run {label} did not start within "
                             f"{int(_LOCK_BOUND)}s (supervisor pid {proc.pid})")
        time.sleep(0.02)
    return label


def _write_atomic(path: Path, text: str) -> None:
    """Write *path* whole or not at all, as the supervisor writes ``.exit``."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(str(tmp), str(path))


def _tail(log: Path, lines: int = TAIL_LINES) -> str:
    try:
        with log.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - 64 * 1024))
            data = fh.read()
    except OSError:
        return ""
    return "\n".join(data.decode("utf-8", "replace").splitlines()[-lines:])


def _report(label: str, directory: Path, headline: str) -> None:
    log = directory / f"{label}.log"
    print(headline)
    print(f"--- last {TAIL_LINES} lines of {log} ---")
    print(_tail(log))


def _ended(label: str, directory: Path, record: dict) -> int:
    """Report a run that has an ``.exit``; return the code a caller reads."""
    try:
        code = int((directory / f"{label}.exit").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        code = EXIT_NOT_STARTED
    command = " ".join(record.get("argv", []))
    how = {EXIT_DIED: "died without an exit code",
           EXIT_STOPPED: "was stopped"}.get(code, f"finished — exit {code}")
    _report(label, directory, f"await_run: {label} {how} after "
                              f"{_elapsed(record)}s: {command}")
    # A signal death is recorded negative on POSIX; report it the way a shell does.
    return code if code >= 0 else 128 - code


def _checked_label(label: str, directory: Path) -> dict:
    if not _LABEL_RE.match(label):
        raise UsageError(f"not a run label: {label!r}")
    if not (directory / f"{label}.start").is_file():
        known = sorted(p.stem for p in directory.glob("*.start"))
        raise UsageError(f"no run {label} under {directory}"
                         + (f"; known: {', '.join(known)}" if known else ""))
    return _record(directory, label)


def wait_run(label: str, directory: Path, seconds: float) -> int:
    """Block up to *seconds* for *label*; print where it stands; return a code."""
    record = _checked_label(label, directory)
    deadline = time.monotonic() + seconds
    while True:
        state = run_state(directory, label)
        if state == "dead":
            _mark(directory, label, EXIT_DIED)
            state = "ended"
        if state == "ended":
            return _ended(label, directory, record)
        if time.monotonic() >= deadline:
            break
        time.sleep(_POLL)
    _report(label, directory,
            f"await_run: {label} still running — elapsed {_elapsed(record)}s, "
            f"pid {record.get('pid', '?')}: {' '.join(record.get('argv', []))}\n"
            f"wait again: python .claude/scripts/await_run.py wait {label}")
    return EXIT_RUNNING


def _kill_tree(pid: int, hard: bool) -> None:
    """Signal the supervisor's whole tree. POSIX: it leads its own session,
    so its process group is the run. Windows: taskkill walks the tree."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=False)
        return
    import signal
    try:
        os.killpg(pid, signal.SIGKILL if hard else signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


def _await_release(directory: Path, label: str, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while _lock_held(directory / f"{label}.lock"):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


def stop_run(label: str, directory: Path) -> int:
    """Kill a live run's tree and record it stopped; report an ended one."""
    record = _checked_label(label, directory)
    state = run_state(directory, label)
    if state == "dead":
        _mark(directory, label, EXIT_DIED)
    if state != "live":
        _ended(label, directory, record)
        return 0
    # The pid is only ever the one this run's record holds, and only acted on
    # while the lock says that supervisor is alive — so never a reused pid.
    pid = record.get("pid")
    if not isinstance(pid, int):
        raise UsageError(f"run record {label} names no pid")
    _kill_tree(pid, hard=False)
    if not _await_release(directory, label, _STOP_GRACE):
        _kill_tree(pid, hard=True)
        if not _await_release(directory, label, _STOP_GRACE):
            raise UsageError(f"{label} (pid {pid}) is still holding its lock "
                             f"after SIGKILL")
    _mark(directory, label, EXIT_STOPPED)
    _ended(label, directory, record)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="await_run.py", description=__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="verb", required=True, parser_class=_Parser)
    p_start = sub.add_parser("start", help="launch the suite or a merge detached; "
                                           "prints its label")
    what = p_start.add_subparsers(dest="what", required=True, parser_class=_Parser)
    what.add_parser("suite", help="the project's [python] test_command")
    p_merge = what.add_parser("merge", help=".aide/scripts/aide.py merge NNN")
    p_merge.add_argument("number", type=int)
    p_merge.add_argument("--rounds", type=int, default=None)
    p_merge.add_argument("--base", default=None)
    p_merge.add_argument("--findings", default=None,
                         help="blocking=A,minor=B,nit=C, passed to aide merge")
    p_wait = sub.add_parser("wait", help="block up to --for seconds for a run")
    p_wait.add_argument("label")
    p_wait.add_argument("--for", dest="seconds", type=float, default=DEFAULT_WAIT,
                        help=f"seconds to wait at most (default {DEFAULT_WAIT}, "
                             f"capped at {MAX_WAIT})")
    p_stop = sub.add_parser("stop", help="kill a run's whole process tree and "
                                         "record it stopped")
    p_stop.add_argument("label")
    return p


def main(argv: Optional[List[str]] = None, *, root: Optional[Path] = None,
         engine: Optional[Path] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:  # -h, or `_Parser.error`'s EXIT_USAGE
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    root = root or _PROJECT_ROOT
    engine = engine or root / ".aide" / "scripts" / "aide.py"
    try:
        directory = state_dir(root)
        if args.verb == "wait":
            seconds = min(max(args.seconds, 0.0), float(MAX_WAIT))
            return wait_run(args.label, directory, seconds)
        if args.verb == "stop":
            return stop_run(args.label, directory)
        if args.what == "suite":
            label = start_run("suite", suite_command(root, engine), root, directory)
        else:
            if args.number < 0 or (args.rounds is not None and args.rounds < 0):
                raise UsageError("item number and --rounds must be non-negative")
            if args.base is not None and (not args.base or args.base.startswith("-")):
                raise UsageError(f"not a base ref: {args.base!r}")
            if args.findings is not None and not _FINDINGS_RE.match(args.findings):
                raise UsageError(f"not a findings count: {args.findings!r}")
            label = start_run(f"merge-{args.number:03d}",
                              merge_command(engine, args.number, args.rounds,
                                            args.base, args.findings),
                              root, directory)
    except UsageError as exc:
        print(f"await_run: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except BusyError as busy:
        record = {}
        try:
            record = _record(directory, busy.label)
        except UsageError:
            pass
        _report(busy.label, directory,
                f"await_run: {busy.label} is still live here — elapsed "
                f"{_elapsed(record)}s; nothing was started. Wait on this label "
                f"instead: python .claude/scripts/await_run.py wait {busy.label}")
        return EXIT_BUSY
    print(label)
    print(f"next: python .claude/scripts/await_run.py wait {label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
