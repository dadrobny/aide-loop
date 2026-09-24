"""Adapter conformance for the hook-command interpreter (cross-machine robustness).

The committed ``adapters/claude/settings.json`` must not hardcode a single Python
interpreter name that may be absent on a given host. Instead:

- **Hook commands** run through a self-resolving shell selector that *probes each
  candidate interpreter by actually running it*, not merely by checking ``PATH``
  presence:
  ``sh -c 'f="${CLAUDE_PROJECT_DIR:-.}/$1"; [ -f "$f" ] || { printf "aide: hook
  script not found: %s\\n" "$f" >&2; exit 1; }; for py in python3 python; do command -v
  "$py" >/dev/null 2>&1 || continue; "$py" -c "" >/dev/null 2>&1 || continue;
  exec "$py" "$f"; done; exit 0' _ <hook>``.
  A machine with only ``python3`` (Linux/macOS) *or* only ``python`` (Windows with
  git's ``sh`` on PATH) runs the hook from **one committed file**, with no
  per-machine reconciliation. The functional probe (``"$py" -c ""``) is required
  because ``command -v`` alone is fooled by Windows's **App Execution Alias**
  stubs: ``%LOCALAPPDATA%\\Microsoft\\WindowsApps\\python3.exe`` is a real file on
  ``PATH`` that ``command -v python3`` happily reports as found, but running it
  just prints a "Python was not found ... Microsoft Store" message and exits
  non-zero — silently defeating a presence-only ``||`` fallback and making every
  hook a no-op (see item history: this exact regression shipped once already).
  ``exec`` is required so a gating hook's exit code (e.g. the hygiene guard's
  block = exit 2) propagates unchanged once a working interpreter is found; a
  naive ``python3 … || python …`` would re-run on any non-zero exit instead of
  falling through to the next candidate.
- **The script resolves from the project root**, ``$CLAUDE_PROJECT_DIR``, not
  from the hook process's cwd (issue #272). In a worktree-isolated sub-agent the
  cwd is the worktree while the settings are the primary checkout's, so a
  cwd-relative path ran the worktree's committed copy of the script — or, where
  the worktree lacked it, made Python exit 2, the PreToolUse *block* code, on
  every call. ``:-.`` keeps a runtime that sets no variable working as before.
  A script that is not there is one stderr line and exit 1: a non-blocking hook
  error, visible, where a silent pass was what hid the defect.
- **The allow-list** lists both ``python`` and ``python3`` (harmless auto-approval
  patterns), so either interpreter name auto-approves regardless of host.

Stdlib + pytest only; the settings file is validated as data (no install needed).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
ADAPTER_SETTINGS = FRAMEWORK_ROOT / "adapters" / "claude" / "settings.json"


def _hook_commands(parsed: dict) -> list:
    cmds = []
    for phase in ("PreToolUse", "PostToolUse"):
        for group in parsed.get("hooks", {}).get(phase, []):
            for hook in group.get("hooks", []):
                if hook.get("type") == "command":
                    cmds.append(hook["command"])
    return cmds


def test_settings_is_valid_json():
    json.loads(ADAPTER_SETTINGS.read_text(encoding="utf-8"))


def test_hooks_use_self_resolving_selector():
    parsed = json.loads(ADAPTER_SETTINGS.read_text(encoding="utf-8"))
    cmds = _hook_commands(parsed)
    assert cmds, "expected at least one command hook"
    for cmd in cmds:
        # Presence check alone is not enough — must also probe functionality
        # (defeats Windows App Execution Alias stubs that exist on PATH but fail
        # to run).
        assert 'command -v "$py"' in cmd, cmd
        assert '"$py" -c ""' in cmd, cmd
        assert 'exec "$py" "$f"' in cmd, cmd
        # Anchored at the project root, with the old behaviour as fallback.
        assert cmd.startswith("sh -c 'f=\"${CLAUDE_PROJECT_DIR:-.}/$1\"; "), cmd
        assert ('[ -f "$f" ] || { printf "aide: hook script not found: %s\\n" '
                '"$f" >&2; exit 1; }') in cmd, cmd
        # Never blocks an unattended run just because no interpreter was found.
        assert "done; exit 0'" in cmd, cmd
        assert ".claude/hooks/" in cmd
        # No bare single-interpreter invocation that could be absent on a host.
        assert not cmd.startswith("python "), cmd
        assert not cmd.startswith("python3 "), cmd


def test_allowlist_lists_both_interpreter_names():
    parsed = json.loads(ADAPTER_SETTINGS.read_text(encoding="utf-8"))
    allow = parsed["permissions"]["allow"]
    for entry in ("Bash(python:*)", "Bash(python3:*)",
                  "Bash(python -m pytest:*)", "Bash(python3 -m pytest:*)"):
        assert entry in allow, f"missing allow entry: {entry}"


def _source_tree_guard_cmd(parsed: dict) -> str:
    """The committed command references the *installed* layout (``.claude/hooks/``,
    relative to a project root). In the aide-loop source tree the same script
    lives at ``adapters/claude/hooks/`` — rewrite the path so the command can be
    exercised directly against the source tree without a real install."""
    cmd = next(
        c for c in _hook_commands(parsed) if "command_hygiene_guard.py" in c
    )
    return cmd.replace(".claude/hooks/", "hooks/")


def _env(project_dir) -> dict:
    """The environment the runtime gives a hook: ``CLAUDE_PROJECT_DIR`` set —
    explicitly, so a value inherited from a session running this suite is
    never the one under test."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return env


@pytest.mark.skipif(not shutil.which("sh"), reason="no sh on PATH")
def test_selector_blocks_a_hygiene_violation_end_to_end():
    """The selector must actually reach the hook and preserve its exit code."""
    parsed = json.loads(ADAPTER_SETTINGS.read_text(encoding="utf-8"))
    guard_cmd = _source_tree_guard_cmd(parsed)
    payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "git -C /tmp status"}}
    )
    result = subprocess.run(
        ["sh", "-c", guard_cmd],
        input=payload,
        capture_output=True,
        encoding="utf-8",
        cwd=FRAMEWORK_ROOT / "adapters" / "claude",
        env=_env(FRAMEWORK_ROOT / "adapters" / "claude"),
        timeout=10,
    )
    assert result.returncode == 2, result.stderr
    # conventions.md §6, both halves, and this is where CI taught them. The
    # decode happens in `subprocess.run`'s reader thread, so a byte the codec
    # rejects does not raise here — it leaves `stderr` as **None**, and `in
    # None` then fails as a TypeError that names nothing. That is the recorded
    # "stdout is None on a Windows runner" instance, reproduced: the guard was
    # writing its em-dash as cp1252. Kept strict rather than softened with
    # `errors="replace"`, so this line is the regression guard for the hook
    # emitting UTF-8 — and recognisable first, so a future one reports.
    assert result.stderr is not None, (
        "the guard's stderr did not decode as UTF-8 — it must reconfigure its "
        "stream, not inherit the console codepage")
    assert "git -C" in result.stderr or "cd" in result.stderr.lower()


@pytest.mark.skipif(not shutil.which("sh"), reason="no sh on PATH")
def test_selector_allows_a_clean_command_end_to_end():
    parsed = json.loads(ADAPTER_SETTINGS.read_text(encoding="utf-8"))
    guard_cmd = _source_tree_guard_cmd(parsed)
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}})
    result = subprocess.run(
        ["sh", "-c", guard_cmd],
        input=payload,
        capture_output=True,
        encoding="utf-8",
        cwd=FRAMEWORK_ROOT / "adapters" / "claude",
        env=_env(FRAMEWORK_ROOT / "adapters" / "claude"),
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def _all_hook_commands(parsed: dict) -> list:
    return [hook["command"]
            for groups in parsed.get("hooks", {}).values()
            for group in groups for hook in group.get("hooks", [])
            if hook.get("type") == "command"]


def test_every_registered_hook_uses_the_anchored_wrapper():
    """All five registrations, InstructionsLoaded included — `_hook_commands`
    above reads the two tool events only."""
    parsed = json.loads(ADAPTER_SETTINGS.read_text(encoding="utf-8"))
    cmds = _all_hook_commands(parsed)
    assert len(cmds) == 5, cmds
    prefixes = {c.rsplit(" _ ", 1)[0] for c in cmds}
    assert len(prefixes) == 1, "the hooks no longer share one wrapper"
    assert all(c.rsplit(" _ ", 1)[1].startswith(".claude/hooks/") for c in cmds)


def _wrapper_for(script: str) -> str:
    parsed = json.loads(ADAPTER_SETTINGS.read_text(encoding="utf-8"))
    cmd = next(c for c in _hook_commands(parsed) if "command_hygiene_guard.py" in c)
    return cmd.replace(".claude/hooks/command_hygiene_guard.py", script)


@pytest.mark.skipif(not shutil.which("sh"), reason="no sh on PATH")
def test_the_script_resolves_from_the_project_dir_not_the_cwd(tmp_path):
    """The worktree case (issue #272): cwd has no such script, or an older
    one; the project root has the right one, and that is the one that runs."""
    project = tmp_path / "primary checkout"  # a space, as on many Windows homes
    worktree = tmp_path / "worktree"
    for root in (project, worktree):
        (root / ".claude" / "hooks").mkdir(parents=True)
    (project / ".claude" / "hooks" / "probe.py").write_text(
        "print('project')\n", encoding="utf-8")
    cmd = _wrapper_for(".claude/hooks/probe.py")

    result = subprocess.run(["sh", "-c", cmd], capture_output=True,
                            encoding="utf-8", cwd=worktree,
                            env=_env(project), timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "project"

    # An older copy in the worktree loses to the project root's.
    (worktree / ".claude" / "hooks" / "probe.py").write_text(
        "print('worktree')\n", encoding="utf-8")
    result = subprocess.run(["sh", "-c", cmd], capture_output=True,
                            encoding="utf-8", cwd=worktree,
                            env=_env(project), timeout=10)
    assert result.stdout.strip() == "project"


@pytest.mark.skipif(not shutil.which("sh"), reason="no sh on PATH")
def test_without_the_variable_the_script_resolves_from_cwd_as_before(tmp_path):
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / ".claude" / "hooks" / "probe.py").write_text(
        "print('cwd')\n", encoding="utf-8")
    result = subprocess.run(["sh", "-c", _wrapper_for(".claude/hooks/probe.py")],
                            capture_output=True, encoding="utf-8", cwd=tmp_path,
                            env=_env(None), timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "cwd"


@pytest.mark.skipif(not shutil.which("sh"), reason="no sh on PATH")
def test_a_missing_script_is_a_visible_non_blocking_error(tmp_path):
    """Exit 1, not 2: a PreToolUse hook that exits 2 blocks the tool call, and
    a missing script is the framework's fault, not the command's. Not 0
    either — a silent pass is what hid issue #272."""
    result = subprocess.run(["sh", "-c", _wrapper_for(".claude/hooks/gone.py")],
                            capture_output=True, encoding="utf-8", cwd=tmp_path,
                            env=_env(tmp_path), timeout=10)
    assert result.returncode == 1
    assert result.stderr.strip() == (
        f"aide: hook script not found: {tmp_path}/.claude/hooks/gone.py")
