#!/usr/bin/env python
"""Claude Code hook: surface a sibling repo's instructions the first time a
session reaches into it.

Registered on ``PreToolUse`` for the tools that can touch a path
(Bash / Edit / Write / MultiEdit / NotebookEdit) in ``.claude/settings.json``.

The runtime loads instruction files for the **working directory's** repo. A
declared sibling repository gets nothing, even when the tool is configured to
work in it — "additional working directory" does not imply "instructions
loaded". This hook extends the semantics the runtime already applies to
*subdirectory* instruction files across a repo boundary: on the first tool call
that touches a path under a declared sibling, that repo's own instruction file
is injected once, and nothing is paid by a session that never reaches across.

Contract:
- Reads the PreToolUse hook JSON on stdin (``session_id``, ``cwd``,
  ``tool_name``, ``tool_input`` …).
- When a touched path lands inside a declared sibling repo not yet surfaced in
  this session, writes ``hookSpecificOutput.additionalContext`` to **stdout** as
  JSON and exits 0.
- Otherwise writes nothing and exits 0.

Design rules:
- **JSON or nothing.** A PreToolUse hook's plain stdout is written to the debug
  log and never shown to the model — only ``hookSpecificOutput.additionalContext``
  reaches it. Printing the file would look like it worked and deliver nothing.
- **Never block.** No ``permissionDecision`` is emitted and the exit status is
  always 0, so the ordinary permission flow is untouched. Exit 2 would *block*
  the tool call, which is the opposite of the intent.
- **Fail-open, like its companion hooks.** Any parse error, unreadable config or
  internal exception exits 0 in silence. The worst case is the status quo: the
  sibling's rules are not surfaced, exactly as before this hook existed.
- **Declaration-driven, no new configuration.** The repos come from
  ``[framework] local_path`` and ``[hygiene] extra_repos`` in the personal,
  gitignored ``.aide/loop/loop.local.toml`` — already the machine's answer to
  "which repos does this project legitimately span". The instruction filename
  comes from the adapter's own ``default-context.json``, so the hook names the
  file the runtime actually loads without hard-coding it twice.
"""

import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

#: A pathological instruction file must not blow up the context window it is
#: being injected into. Beyond this the file is truncated and the reader is
#: pointed at the original.
_MAX_BYTES = 64 * 1024

#: Fallback when ``default-context.json`` is missing or unreadable. Every
#: runtime that loads an instruction file by default names it in that file; this
#: is only the Claude adapter's own answer, used when the declaration is gone.
_FALLBACK_INSTRUCTION_FILE = "CLAUDE.md"

#: Per-tool key in ``tool_input`` naming the path the call touches. ``Bash`` is
#: absent on purpose — its paths are scraped out of the command string instead.
_PATH_KEYS = {
    "Edit": "file_path",
    "MultiEdit": "file_path",
    "Write": "file_path",
    "NotebookEdit": "notebook_path",
}


def _declared_repo_paths():
    """Every repo declared in ``.aide/loop/loop.local.toml``, as written.

    Delegates to the command-hygiene guard, which already owns this parse and
    has the test suite pinning its edge cases (a malformed array grants
    nothing, a bare key does not wedge the file, a new section header ends an
    unterminated array). Two hand-rolled TOML readers over one file is one too
    many, and they sit in the same installed directory.
    """
    module_path = Path(__file__).resolve().parent / "command_hygiene_guard.py"
    spec = importlib.util.spec_from_file_location(
        "_aide_command_hygiene_guard", module_path
    )
    if spec is None or spec.loader is None:
        return []
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    return list(guard._declared_repo_paths())


def _instruction_filename(path=None):
    """The instruction file the runtime loads by default, per the adapter's
    ``default-context.json`` (ADAPTER-SPEC §7).

    A relative, non-climbing path inside the repo — the same constraint the
    installer applies to it — or the fallback. A declaration that escapes the
    repo would have this hook read a file in a directory nobody named.
    """
    declared = None
    if path is None:
        path = Path(__file__).resolve().parents[1] / "default-context.json"
    try:
        with path.open(encoding="utf-8") as fh:
            declared = json.load(fh).get("file")
    except (OSError, ValueError, AttributeError):
        return _FALLBACK_INSTRUCTION_FILE
    if not isinstance(declared, str) or not declared.strip():
        return _FALLBACK_INSTRUCTION_FILE
    declared = declared.strip()
    # Both path flavours, exactly as `install.py` checks this same field — a
    # single-flavour test is wrong on whichever platform it is not. `os.path` is
    # not enough: since 3.13 `ntpath.isabs("/etc/passwd")` is **False**, because
    # a leading-separator path is drive-relative rather than fully qualified, so
    # a POSIX absolute path would sail through on Windows as a relative name.
    posix = PurePosixPath(declared.replace("\\", "/"))
    if posix.is_absolute() or PureWindowsPath(declared).is_absolute():
        return _FALLBACK_INSTRUCTION_FILE
    if ".." in posix.parts:
        return _FALLBACK_INSTRUCTION_FILE
    return declared


def _contains(parent, child):
    """True when ``child`` is ``parent`` or sits underneath it.

    Compared as normalised text rather than via ``Path.is_relative_to`` (3.9+)
    or ``os.path.commonpath`` (raises across drives on Windows), so the hook
    keeps working on whichever interpreter the runtime happened to find.
    ``normcase`` is what makes the comparison correct on a case-insensitive
    filesystem.
    """
    parent_s = os.path.normcase(str(parent)).rstrip(os.sep)
    child_s = os.path.normcase(str(child))
    return child_s == parent_s or child_s.startswith(parent_s + os.sep)


def _candidate_paths(tool_name, tool_input):
    """The paths a tool call touches, as written in its input."""
    if not isinstance(tool_input, dict):
        return []
    key = _PATH_KEYS.get(tool_name)
    if key:
        value = tool_input.get(key)
        return [value] if isinstance(value, str) and value else []
    if tool_name != "Bash":
        return []
    command = tool_input.get("command")
    if not isinstance(command, str):
        return []
    return _paths_in_command(command)


def _paths_in_command(command):
    """Path-shaped tokens in a shell command.

    Deliberately crude: split on shell punctuation, strip quotes, keep whatever
    still carries a separator. It catches the shapes that actually reach a
    sibling repo — ``git -C ../sibling status``, ``--git-dir=../sibling/.git``,
    ``GIT_WORK_TREE=/abs/sibling``, a plain path argument — and misses a bare
    ``cd sibling`` with no separator. Missing one is the fail-open direction:
    the session proceeds exactly as it does today.
    """
    found = []
    for token in re.split(r"[\s;|&<>()]+", command):
        token = token.strip("\"'")
        if not token:
            continue
        candidates = [token]
        # `--git-dir=<path>`, `GIT_DIR=<path>` — the path is the right-hand side.
        if "=" in token:
            candidates.append(token.split("=", 1)[1].strip("\"'"))
        for candidate in candidates:
            if candidate.startswith("-"):
                continue
            if "/" in candidate or "\\" in candidate:
                found.append(candidate)
    return found


def _marker_path(session_id):
    """Where this session records the repos it has already been shown.

    Keyed by session id in the system temp directory: the state is scoped to one
    session and belongs to no repository, so writing it into either would be
    littering in a tree the project owns.
    """
    safe = re.sub(r"[^A-Za-z0-9_-]", "", str(session_id))[:64] or "no-session"
    return Path(tempfile.gettempdir()) / ("aide-sibling-instructions-" + safe)


def _already_surfaced(marker, repo_root):
    try:
        with marker.open(encoding="utf-8") as fh:
            seen = {line.strip() for line in fh}
    except OSError:
        return False
    return os.path.normcase(str(repo_root)) in seen


def _record_surfaced(marker, repo_root):
    try:
        with marker.open("a", encoding="utf-8") as fh:
            fh.write(os.path.normcase(str(repo_root)) + "\n")
    except OSError:
        # Losing the marker costs a repeat injection later, never correctness.
        pass


def _read_instructions(instruction_path):
    try:
        text = instruction_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not text.strip():
        return None
    encoded = text.encode("utf-8")
    if len(encoded) > _MAX_BYTES:
        text = encoded[:_MAX_BYTES].decode("utf-8", errors="ignore")
        text += "\n\n[truncated — read the rest at " + str(instruction_path) + "]"
    return text


def _render(repo_root, instruction_path, text):
    return (
        "This session has reached into `" + str(repo_root) + "`, a separate "
        "repository declared in `.aide/loop/loop.local.toml`. A runtime loads "
        "instruction files for the working directory's repository only, so this "
        "one's have not been in context until now.\n\n"
        "They are reproduced in full below and govern work **inside that "
        "repository**; the working directory's own instructions continue to "
        "govern everything else. Where the two disagree about a file, the "
        "repository that owns the file wins.\n\n"
        "--- begin " + str(instruction_path) + " ---\n"
        + text.rstrip("\n") + "\n"
        "--- end " + str(instruction_path) + " ---"
    )


def _resolve(path, base):
    try:
        return (base / os.path.expanduser(str(path))).resolve()
    except (OSError, ValueError):
        return None


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        return
    payload = json.loads(raw)

    touched = _candidate_paths(payload.get("tool_name", ""), payload.get("tool_input"))
    if not touched:
        return

    declared = _declared_repo_paths()
    if not declared:
        return

    # Two different bases, deliberately. A declared repo path is relative to
    # wherever `.aide/loop/loop.local.toml` was just read from — the process cwd,
    # which the runtime sets to the project root. A path inside a Bash command is
    # relative to the session's cwd, which the payload reports and which need not
    # be the same directory.
    config_base = Path.cwd().resolve()
    session_cwd = Path(payload.get("cwd") or os.getcwd()).resolve()
    instruction_file = _instruction_filename()
    marker = _marker_path(payload.get("session_id", ""))

    resolved_touched = [p for p in (_resolve(t, session_cwd) for t in touched) if p]

    blocks = []
    for repo in declared:
        repo_root = _resolve(repo, config_base)
        if repo_root is None:
            continue
        # The cwd repo's instructions are already loaded, and a declaration that
        # points at an ancestor of cwd would inject the file the session opened
        # with. Neither is a sibling being reached into.
        if _contains(repo_root, session_cwd) or _contains(repo_root, config_base):
            continue
        if not any(_contains(repo_root, t) for t in resolved_touched):
            continue
        if _already_surfaced(marker, repo_root):
            continue
        instruction_path = repo_root / instruction_file
        text = _read_instructions(instruction_path)
        # Record either way: a sibling with no instruction file must not be
        # re-examined on every single tool call for the rest of the session.
        _record_surfaced(marker, repo_root)
        if text is None:
            continue
        blocks.append(_render(repo_root, instruction_path, text))

    if not blocks:
        return

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "\n\n".join(blocks),
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never let this hook block or alter the real tool call.
        pass
    sys.exit(0)
