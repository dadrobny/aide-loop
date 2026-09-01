"""Adapter conformance for the hook-command interpreter (cross-machine robustness).

The committed ``adapters/claude/settings.json`` must not hardcode a single Python
interpreter name that may be absent on a given host. Instead:

- **Hook commands** run through a self-resolving shell selector that *probes each
  candidate interpreter by actually running it*, not merely by checking ``PATH``
  presence:
  ``sh -c 'for py in python3 python; do command -v "$py" >/dev/null 2>&1 ||
  continue; "$py" -c "" >/dev/null 2>&1 || continue; exec "$py" "$@"; done;
  exit 0' _ <hook>``.
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
- **The allow-list** lists both ``python`` and ``python3`` (harmless auto-approval
  patterns), so either interpreter name auto-approves regardless of host.

Stdlib + pytest only; the settings file is validated as data (no install needed).
"""
from __future__ import annotations

import json
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
        assert cmd.startswith("sh -c 'for py in python3 python; do"), cmd
        # Presence check alone is not enough — must also probe functionality
        # (defeats Windows App Execution Alias stubs that exist on PATH but fail
        # to run).
        assert 'command -v "$py"' in cmd, cmd
        assert '"$py" -c ""' in cmd, cmd
        assert 'exec "$py" "$@"' in cmd, cmd
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
        timeout=10,
    )
    assert result.returncode == 2, result.stderr
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
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
