"""Adapter tests for the nested-spawn model guard (issue #311).

A role pins an exact model; a helper it spawns without one inherits it. The
hook refuses such a spawn from inside a sub-agent unless the target type pins
its own model, and leaves the user's own session alone.

Load-by-path for the decision, matching `test_sibling_instructions.py`, and
the script run as a subprocess for the wire contract — what the runtime
actually reads back on stdout, and the exit status.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ADAPTER = Path(__file__).resolve().parents[1]
_MODULE_PATH = _ADAPTER / "hooks" / "spawn_model_guard.py"
_SETTINGS = _ADAPTER / "settings.json"
_spec = importlib.util.spec_from_file_location("spawn_model_guard", _MODULE_PATH)
guard = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = guard
_spec.loader.exec_module(guard)  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# harness
# --------------------------------------------------------------------------- #
def _project(tmp_path: Path, agents: dict = None) -> Path:
    """A project root with `.claude/agents/<name>.md` for each entry."""
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    for name, text in (agents or {}).items():
        (agents_dir / f"{name}.md").write_text(text, encoding="utf-8")
    return tmp_path


def _definition(model_line: str = "") -> str:
    return ("---\nname: sweeper\ndescription: >-\n  A test helper.\n"
            + model_line + "---\nBody.\n")


def _payload(subagent_type=None, model=None, nested=True, tool="Agent") -> dict:
    tool_input = {"description": "sweep", "prompt": "grep the tests"}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    if model is not None:
        tool_input["model"] = model
    payload = {"session_id": "s", "hook_event_name": "PreToolUse",
               "tool_name": tool, "tool_input": tool_input}
    if nested:
        payload["agent_id"] = "a1b2c3"
        payload["agent_type"] = "spec-author"
    return payload


def _run(stdin: str, project: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    return subprocess.run([sys.executable, str(_MODULE_PATH)], input=stdin,
                          capture_output=True, encoding="utf-8", env=env,
                          timeout=30)


# --------------------------------------------------------------------------- #
# the decision
# --------------------------------------------------------------------------- #
def test_the_main_session_is_never_touched(tmp_path):
    """No `agent_id`: the user's own session, or the orchestrator it runs."""
    project = _project(tmp_path)
    assert guard.decide(_payload("Explore", nested=False), str(project)) is None
    assert guard.decide(_payload(None, nested=False), str(project)) is None


def test_a_nested_builtin_without_a_model_is_refused_naming_haiku(tmp_path):
    reason = guard.decide(_payload("Explore"), str(_project(tmp_path)))
    assert reason is not None
    assert "`Explore`" in reason
    assert '"haiku"' in reason and '"sonnet"' in reason


def test_a_missing_subagent_type_is_general_purpose(tmp_path):
    reason = guard.decide(_payload(None), str(_project(tmp_path)))
    assert reason is not None and "`general-purpose`" in reason


@pytest.mark.parametrize("model", ["haiku", "sonnet", "opus",
                                   "claude-haiku-4-5-20251001"])
def test_an_explicit_model_is_allowed(tmp_path, model):
    assert guard.decide(_payload("Explore", model=model),
                        str(_project(tmp_path))) is None


@pytest.mark.parametrize("model", ["inherit", "INHERIT", "", "  "])
def test_inherit_or_empty_is_no_model(tmp_path, model):
    assert guard.decide(_payload("Explore", model=model),
                        str(_project(tmp_path))) is not None


def test_a_project_agent_that_pins_a_model_is_allowed(tmp_path):
    project = _project(tmp_path, {
        "sweeper": _definition("model: claude-haiku-4-5-20251001\n")})
    assert guard.decide(_payload("sweeper"), str(project)) is None


@pytest.mark.parametrize("model_line", ["", "model: inherit\n", "model:\n",
                                        'model: "inherit"\n'])
def test_a_project_agent_without_a_pinned_model_is_refused(tmp_path, model_line):
    project = _project(tmp_path, {"sweeper": _definition(model_line)})
    assert guard.decide(_payload("sweeper"), str(project)) is not None


def test_a_model_key_below_the_frontmatter_does_not_count(tmp_path):
    project = _project(tmp_path, {
        "sweeper": "---\nname: sweeper\n---\nmodel: claude-opus-5-5\n"})
    assert guard.decide(_payload("sweeper"), str(project)) is not None


def test_a_bom_and_crlf_definition_still_reads(tmp_path):
    project = _project(tmp_path)
    (project / ".claude" / "agents" / "sweeper.md").write_bytes(
        b"\xef\xbb\xbf---\r\nname: sweeper\r\nmodel: claude-sonnet-5\r\n"
        b"---\r\nBody.\r\n")
    assert guard.decide(_payload("sweeper"), str(project)) is None


@pytest.mark.parametrize("agent_type", ["../sweeper", "sub/sweeper",
                                        "plugin:sweeper", ".."])
def test_a_type_that_is_not_a_plain_stem_resolves_to_nothing(tmp_path, agent_type):
    """Nothing outside `.claude/agents/` is ever read on a type's say-so."""
    project = _project(tmp_path / "project", {})
    (tmp_path / "project" / ".claude" / "sweeper.md").write_text(
        _definition("model: claude-sonnet-5\n"), encoding="utf-8")
    assert guard.decide(_payload(agent_type), str(project)) is not None


def test_the_legacy_task_name_is_guarded_too(tmp_path):
    assert guard.decide(_payload("Explore", tool="Task"),
                        str(_project(tmp_path))) is not None


def test_another_tool_is_no_business_of_this_hook(tmp_path):
    payload = {"tool_name": "Bash", "agent_id": "x",
               "tool_input": {"command": "ls"}}
    assert guard.decide(payload, str(_project(tmp_path))) is None


# --------------------------------------------------------------------------- #
# the wire contract
# --------------------------------------------------------------------------- #
def test_a_deny_is_permission_decision_json_on_stdout(tmp_path):
    result = _run(json.dumps(_payload("Explore")), _project(tmp_path))
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "deny"
    assert '"haiku"' in out["permissionDecisionReason"]


def test_an_allow_is_silence(tmp_path):
    result = _run(json.dumps(_payload("Explore", model="haiku")),
                  _project(tmp_path))
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_the_project_dir_comes_from_the_runtime_variable(tmp_path):
    project = _project(tmp_path, {
        "sweeper": _definition("model: claude-sonnet-5\n")})
    result = _run(json.dumps(_payload("sweeper")), project)
    assert (result.returncode, result.stdout) == (0, "")


@pytest.mark.parametrize("stdin", ["", "not json", "[1, 2]", '{"tool_name": 3}',
                                   '{"tool_name": "Agent", "agent_id": "x", '
                                   '"tool_input": "oops"}'])
def test_garbage_stdin_fails_open_in_silence(tmp_path, stdin):
    result = _run(stdin, _project(tmp_path))
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


# --------------------------------------------------------------------------- #
# the registration
# --------------------------------------------------------------------------- #
def _settings() -> dict:
    return json.loads(_SETTINGS.read_text(encoding="utf-8"))


def test_settings_registers_the_guard_on_the_spawn_tool():
    groups = [g for g in _settings()["hooks"]["PreToolUse"]
              if any(h.get("command", "").endswith(
                  " _ .claude/hooks/spawn_model_guard.py")
                  for h in g.get("hooks", []))]
    assert len(groups) == 1, groups
    assert set(groups[0]["matcher"].split("|")) == {"Agent", "Task"}


def test_settings_caps_the_spawn_depth_at_two():
    """main -> role -> helper: a helper cannot spawn one of its own."""
    assert _settings()["env"]["CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"] == "2"
