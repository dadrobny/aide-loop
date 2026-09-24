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

``start`` launches the command fully detached, with its output going to a log,
and prints a label straight away. ``wait`` blocks for at most ``--for``
seconds (default 240, under a 5-minute cache; capped at 540, under the Bash
tool's 600000 ms ceiling) and returns the moment the command exits.

It runs **only** those two commands, so allow-listing it lets nothing else
through: ``suite`` is the project's ``[python] test_command``, resolved by the
engine exactly as ``aide merge`` resolves it (a leading ``python`` bound to the
venv), and ``merge`` is ``.aide/scripts/aide.py merge`` under this interpreter.

Exit codes of ``wait``:

    the command's own   it finished; a red suite reads as red
    75                  still running — call wait again (EX_TEMPFAIL)
    64                  await_run itself could not do what was asked (EX_USAGE)
    127                 recorded when the command could not be started at all

Neither 64 nor 75 is a code pytest or ``aide merge`` returns. State lives under
the git directory (``git rev-parse --git-dir``, which is per worktree), in
``aide-runs/<label>.{start,log,exit}``, so it never dirties the working tree
or reaches ``aide scope``. Finished runs older than a week are removed by the
next ``start``.
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
_POLL = 0.5
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
    for exit_file in directory.glob("*.exit"):
        try:
            if now - exit_file.stat().st_mtime < _KEEP_SECONDS:
                continue
            for suffix in (".start", ".log", ".exit"):
                exit_file.with_suffix(suffix).unlink(missing_ok=True)
        except OSError:
            pass


def start_run(kind: str, argv: List[str], cwd: Path, directory: Path) -> str:
    """Launch *argv* detached under the supervisor; return its label.

    The seam the tests drive with a command of their own. The CLI reaches it
    only with `suite_command` or `merge_command`.
    """
    directory.mkdir(parents=True, exist_ok=True)
    now = time.time()
    _prune(directory, now)
    stem = f"{kind}-{time.strftime('%Y%m%d-%H%M%S', time.localtime(now))}"
    label, n = stem, 1
    while (directory / f"{label}.start").exists():
        n += 1
        label = f"{stem}-{n}"
    paths = {s: directory / f"{label}.{s}" for s in ("start", "log", "exit")}
    record = {"label": label, "argv": argv, "cwd": str(cwd), "started": now}
    paths["start"].write_text(json.dumps(record), encoding="utf-8")
    spec = json.dumps({"argv": argv, "cwd": str(cwd), "log": str(paths["log"]),
                       "exit": str(paths["exit"]),
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
    paths["start"].write_text(json.dumps(record), encoding="utf-8")
    return label


def _tail(log: Path, lines: int = TAIL_LINES) -> str:
    try:
        with log.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - 64 * 1024))
            data = fh.read()
    except OSError:
        return ""
    return "\n".join(data.decode("utf-8", "replace").splitlines()[-lines:])


def wait_run(label: str, directory: Path, seconds: float) -> int:
    """Block up to *seconds* for *label*; print where it stands; return a code."""
    if not _LABEL_RE.match(label):
        raise UsageError(f"not a run label: {label!r}")
    start = directory / f"{label}.start"
    if not start.is_file():
        known = sorted(p.stem for p in directory.glob("*.start"))
        raise UsageError(f"no run {label} under {directory}"
                         + (f"; known: {', '.join(known)}" if known else ""))
    record = json.loads(start.read_text(encoding="utf-8"))
    exit_file = directory / f"{label}.exit"
    log = directory / f"{label}.log"
    deadline = time.monotonic() + seconds
    while not exit_file.is_file() and time.monotonic() < deadline:
        time.sleep(_POLL)
    elapsed = int(time.time() - float(record.get("started", time.time())))
    command = " ".join(record.get("argv", []))
    if not exit_file.is_file():
        print(f"await_run: {label} still running — elapsed {elapsed}s, pid "
              f"{record.get('pid', '?')}: {command}")
        print(f"wait again: python .claude/scripts/await_run.py wait {label}")
        print(f"--- last {TAIL_LINES} lines of {log} ---")
        print(_tail(log))
        return EXIT_RUNNING
    try:
        code = int(exit_file.read_text(encoding="utf-8").strip())
    except ValueError:
        code = EXIT_NOT_STARTED
    print(f"await_run: {label} finished — exit {code} after {elapsed}s: {command}")
    print(f"--- last {TAIL_LINES} lines of {log} ---")
    print(_tail(log))
    # A signal death is recorded negative on POSIX; report it the way a shell does.
    return code if code >= 0 else 128 - code


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
    print(label)
    print(f"next: python .claude/scripts/await_run.py wait {label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
