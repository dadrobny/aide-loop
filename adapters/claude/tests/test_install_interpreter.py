"""Adapter conformance for the hook-command interpreter (cross-machine robustness).

The committed ``adapters/claude/settings.json`` must not hardcode a single Python
interpreter name that may be absent on a given host. Instead:

- **Hook commands** run through a self-resolving shell selector —
  ``sh -c 'exec $(command -v python3 || command -v python) $@' _ <hook>`` — so a
  machine with only ``python3`` (Linux/macOS) *or* only ``python`` (Windows with
  git's ``sh`` on PATH) runs the hook from **one committed file**, with no
  per-machine reconciliation. ``exec`` is required so a gating hook's exit code
  (e.g. the hygiene guard's block = exit 2) propagates unchanged; a naive
  ``python3 … || python …`` would re-run on any non-zero exit.
- **The allow-list** lists both ``python`` and ``python3`` (harmless auto-approval
  patterns), so either interpreter name auto-approves regardless of host.

Stdlib + pytest only; the settings file is validated as data (no install needed).
"""
from __future__ import annotations

import json
from pathlib import Path

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
        # Self-resolving: prefers python3, falls back to python, execs the script.
        assert "command -v python3 || command -v python" in cmd, cmd
        assert cmd.startswith("sh -c 'exec "), cmd
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
