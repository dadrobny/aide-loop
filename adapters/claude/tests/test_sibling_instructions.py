"""Adapter tests for the sibling-repo instruction hook (issue #60).

A runtime loads instruction files for the working directory's repo only, so a
declared sibling repository's own rules are never in context — even when the
tool is configured to work in it. The hook injects them once, on the first tool
call that reaches across.

The load-by-path pattern matches ``test_hygiene_guard.py``: the module is
exercised directly rather than through a hook harness. ``main()`` is driven with
a real stdin/stdout pair so the tests assert the *wire* contract — what the
runtime actually receives — and not just internal return values, because the
whole failure mode this hook exists to avoid is output that looks delivered and
is not.
"""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS = Path(__file__).resolve().parents[1] / "hooks"
_MODULE_PATH = _HOOKS / "sibling_instructions.py"
_spec = importlib.util.spec_from_file_location("sibling_instructions", _MODULE_PATH)
hook = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = hook
_spec.loader.exec_module(hook)  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# harness
# --------------------------------------------------------------------------- #
SIBLING_RULES = "# Sibling rules\n\nNever 'fix' the consumer paths.\n"


def _consumer(tmp_path, extra_repos=(), framework=None, sibling_text=SIBLING_RULES):
    """A cwd repo declaring siblings, plus the sibling trees themselves."""
    repo = tmp_path / "consumer"
    (repo / ".aide" / "loop").mkdir(parents=True)

    declared = list(extra_repos)
    lines = []
    if framework:
        lines.append('[framework]\nlocal_path = "%s"\n' % framework)
        declared.append(framework)
    if extra_repos:
        listed = ", ".join('"%s"' % p for p in extra_repos)
        lines.append("[hygiene]\nextra_repos = [%s]\n" % listed)
    (repo / ".aide" / "loop" / "loop.local.toml").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    for rel in declared:
        sibling = (repo / rel).resolve()
        sibling.mkdir(parents=True, exist_ok=True)
        if sibling_text is not None:
            (sibling / "CLAUDE.md").write_text(sibling_text, encoding="utf-8")
    return repo


def _run(monkeypatch, repo, tool_name, tool_input, session_id="s1", cwd=None):
    """Drive ``main()`` over stdin/stdout; return the parsed JSON or None."""
    monkeypatch.chdir(repo)
    payload = {
        "session_id": session_id,
        "hook_event_name": "PreToolUse",
        "cwd": str(cwd or repo),
        "tool_name": tool_name,
        "tool_input": tool_input,
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    hook.main()
    raw = out.getvalue()
    return json.loads(raw) if raw.strip() else None


def _context(result):
    return result["hookSpecificOutput"]["additionalContext"]


@pytest.fixture(autouse=True)
def _isolate_markers(tmp_path, monkeypatch):
    """Per-test temp dir, so the once-per-session marker cannot leak between
    tests (or pick up a stale marker from the developer's own machine)."""
    markers = tmp_path / "markers"
    markers.mkdir()
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(markers))


# --------------------------------------------------------------------------- #
# the wire contract — what the runtime actually receives
# --------------------------------------------------------------------------- #
def test_reaching_into_a_declared_sibling_injects_its_instructions(tmp_path, monkeypatch):
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    result = _run(
        monkeypatch, repo, "Edit",
        {"file_path": str((repo / ".." / "sibling" / "x.py").resolve())},
    )
    assert result is not None
    assert "Never 'fix' the consumer paths." in _context(result)


def test_output_is_context_only_and_never_a_permission_decision(tmp_path, monkeypatch):
    """The hook must not touch the permission flow. A stray `permissionDecision`
    would silently start allowing or denying calls this hook has no opinion on."""
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    result = _run(
        monkeypatch, repo, "Edit",
        {"file_path": str((repo / ".." / "sibling" / "x.py").resolve())},
    )
    specific = result["hookSpecificOutput"]
    assert specific["hookEventName"] == "PreToolUse"
    assert "permissionDecision" not in specific
    assert "permissionDecision" not in result
    assert set(result) == {"hookSpecificOutput"}


def test_context_is_carried_under_additional_context_not_bare_stdout(tmp_path, monkeypatch):
    """A PreToolUse hook's plain stdout goes to the debug log and is never shown
    to the model — only `hookSpecificOutput.additionalContext` reaches it. This
    pins the one detail that makes the hook work at all."""
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    monkeypatch.chdir(repo)
    payload = {
        "session_id": "s1", "cwd": str(repo), "tool_name": "Edit",
        "tool_input": {"file_path": str((repo / ".." / "sibling" / "x.py").resolve())},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    hook.main()
    raw = out.getvalue()
    # Every byte written is the JSON envelope; nothing is printed loose.
    assert raw.strip().startswith("{")
    assert json.loads(raw)["hookSpecificOutput"]["additionalContext"]


def test_the_injected_block_names_the_repo_and_the_file(tmp_path, monkeypatch):
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    result = _run(
        monkeypatch, repo, "Edit",
        {"file_path": str((repo / ".." / "sibling" / "x.py").resolve())},
    )
    context = _context(result)
    sibling = (repo / ".." / "sibling").resolve()
    assert str(sibling) in context
    assert str(sibling / "CLAUDE.md") in context


# --------------------------------------------------------------------------- #
# once per session — the whole point of the lazy design
# --------------------------------------------------------------------------- #
def test_second_reach_in_the_same_session_injects_nothing(tmp_path, monkeypatch):
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    target = {"file_path": str((repo / ".." / "sibling" / "x.py").resolve())}
    assert _run(monkeypatch, repo, "Edit", target) is not None
    assert _run(monkeypatch, repo, "Edit", target) is None


def test_a_different_session_gets_its_own_injection(tmp_path, monkeypatch):
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    target = {"file_path": str((repo / ".." / "sibling" / "x.py").resolve())}
    assert _run(monkeypatch, repo, "Edit", target, session_id="s1") is not None
    assert _run(monkeypatch, repo, "Edit", target, session_id="s2") is not None


def test_a_sibling_without_an_instruction_file_is_not_rescanned(tmp_path, monkeypatch):
    """A sibling with no CLAUDE.md yields nothing — but must still be marked, or
    every tool call for the rest of the session re-stats a file that is not
    there."""
    repo = _consumer(tmp_path, extra_repos=["../sibling"], sibling_text=None)
    target = {"file_path": str((repo / ".." / "sibling" / "x.py").resolve())}
    assert _run(monkeypatch, repo, "Edit", target) is None
    marker = hook._marker_path("s1")
    assert marker.exists()
    assert str((repo / ".." / "sibling").resolve()).lower() in marker.read_text().lower()


def test_an_empty_instruction_file_injects_nothing(tmp_path, monkeypatch):
    repo = _consumer(tmp_path, extra_repos=["../sibling"], sibling_text="   \n\n")
    target = {"file_path": str((repo / ".." / "sibling" / "x.py").resolve())}
    assert _run(monkeypatch, repo, "Edit", target) is None


# --------------------------------------------------------------------------- #
# what must NOT trigger it
# --------------------------------------------------------------------------- #
def test_editing_inside_the_cwd_repo_injects_nothing(tmp_path, monkeypatch):
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    assert _run(monkeypatch, repo, "Edit", {"file_path": str(repo / "src" / "x.py")}) is None


def test_an_undeclared_repo_injects_nothing(tmp_path, monkeypatch):
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    other = tmp_path / "stranger"
    other.mkdir()
    (other / "CLAUDE.md").write_text("secret\n", encoding="utf-8")
    assert _run(monkeypatch, repo, "Edit", {"file_path": str(other / "x.py")}) is None


def test_no_declaration_at_all_injects_nothing(tmp_path, monkeypatch):
    repo = tmp_path / "consumer"
    (repo / ".aide" / "loop").mkdir(parents=True)
    assert _run(monkeypatch, repo, "Edit", {"file_path": str(tmp_path / "s" / "x.py")}) is None


def test_a_declaration_pointing_at_the_cwd_repo_injects_nothing(tmp_path, monkeypatch):
    """`local_path = "."` would otherwise re-inject the file the session already
    opened with."""
    repo = _consumer(tmp_path, framework=".")
    assert _run(monkeypatch, repo, "Edit", {"file_path": str(repo / "x.py")}) is None


def test_a_sibling_sharing_a_name_prefix_is_not_matched(tmp_path, monkeypatch):
    """`/tmp/sibling-two/x` must not be read as living under `/tmp/sibling`."""
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    decoy = (repo / ".." / "sibling-two").resolve()
    decoy.mkdir(parents=True)
    (decoy / "CLAUDE.md").write_text("decoy\n", encoding="utf-8")
    assert _run(monkeypatch, repo, "Edit", {"file_path": str(decoy / "x.py")}) is None


def test_a_tool_with_no_path_injects_nothing(tmp_path, monkeypatch):
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    assert _run(monkeypatch, repo, "WebSearch", {"query": "../sibling"}) is None


# --------------------------------------------------------------------------- #
# Bash — paths scraped out of the command string
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("command", [
    "git -C ../sibling status",
    "git --git-dir=../sibling/.git log",
    "GIT_WORK_TREE=../sibling git status",
    "cat ../sibling/CLAUDE.md",
    "pytest ../sibling/tests/",
])
def test_bash_reaching_into_a_sibling_injects(tmp_path, monkeypatch, command):
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    result = _run(monkeypatch, repo, "Bash", {"command": command})
    assert result is not None, command


def test_bash_staying_home_injects_nothing(tmp_path, monkeypatch):
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    assert _run(monkeypatch, repo, "Bash", {"command": "pytest tests/"}) is None


def test_bash_paths_resolve_against_the_session_cwd_not_the_project_root(tmp_path, monkeypatch):
    """A relative path in a Bash command is relative to the session's cwd, which
    the payload reports and which need not be the project root."""
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    nested = repo / "sub" / "dir"
    nested.mkdir(parents=True)
    # From `<repo>/sub/dir`, the sibling is three levels up, not one.
    assert _run(monkeypatch, repo, "Bash",
                {"command": "cat ../../../sibling/CLAUDE.md"}, cwd=nested) is not None


def test_option_flags_are_not_read_as_paths(tmp_path, monkeypatch):
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    assert _run(monkeypatch, repo, "Bash", {"command": "ls --color=auto -la"}) is None


# --------------------------------------------------------------------------- #
# several siblings at once
# --------------------------------------------------------------------------- #
def test_two_siblings_touched_in_one_call_are_both_injected(tmp_path, monkeypatch):
    repo = _consumer(tmp_path, extra_repos=["../one", "../two"])
    (repo / ".." / "one" / "CLAUDE.md").resolve().write_text("ONE RULES\n", encoding="utf-8")
    (repo / ".." / "two" / "CLAUDE.md").resolve().write_text("TWO RULES\n", encoding="utf-8")
    result = _run(monkeypatch, repo, "Bash", {"command": "diff ../one/a.py ../two/a.py"})
    context = _context(result)
    assert "ONE RULES" in context and "TWO RULES" in context


def test_a_second_sibling_is_injected_even_after_the_first(tmp_path, monkeypatch):
    """The marker is per repo, not per session — reaching into a second sibling
    later must still surface it."""
    repo = _consumer(tmp_path, extra_repos=["../one", "../two"])
    (repo / ".." / "one" / "CLAUDE.md").resolve().write_text("ONE RULES\n", encoding="utf-8")
    (repo / ".." / "two" / "CLAUDE.md").resolve().write_text("TWO RULES\n", encoding="utf-8")
    first = _run(monkeypatch, repo, "Edit", {"file_path": str((repo / ".." / "one" / "a.py").resolve())})
    second = _run(monkeypatch, repo, "Edit", {"file_path": str((repo / ".." / "two" / "a.py").resolve())})
    assert "ONE RULES" in _context(first)
    assert "TWO RULES" in _context(second)
    assert "ONE RULES" not in _context(second)


def test_the_framework_clone_is_a_sibling_like_any_other(tmp_path, monkeypatch):
    """`[framework] local_path` is the case the issue says this bites hardest:
    editing the framework from a consumer session."""
    repo = _consumer(tmp_path, framework="../aide-loop")
    result = _run(monkeypatch, repo, "Edit",
                  {"file_path": str((repo / ".." / "aide-loop" / "core" / "x.py").resolve())})
    assert result is not None


# --------------------------------------------------------------------------- #
# size cap
# --------------------------------------------------------------------------- #
def test_an_oversized_instruction_file_is_truncated_with_a_pointer(tmp_path, monkeypatch):
    huge = "x" * (hook._MAX_BYTES + 5000) + "\nTAIL MARKER\n"
    repo = _consumer(tmp_path, extra_repos=["../sibling"], sibling_text=huge)
    result = _run(monkeypatch, repo, "Edit",
                  {"file_path": str((repo / ".." / "sibling" / "x.py").resolve())})
    context = _context(result)
    assert "TAIL MARKER" not in context
    assert "truncated" in context
    assert len(context.encode("utf-8")) < hook._MAX_BYTES + 2000
    # The preamble must not claim completeness over a file it cut short.
    assert "in full" not in context


def test_a_truncated_block_says_so_and_points_at_the_original(tmp_path, monkeypatch):
    huge = "x" * (hook._MAX_BYTES + 5000)
    repo = _consumer(tmp_path, extra_repos=["../sibling"], sibling_text=huge)
    result = _run(monkeypatch, repo, "Edit",
                  {"file_path": str((repo / ".." / "sibling" / "x.py").resolve())})
    context = _context(result)
    original = (repo / ".." / "sibling" / "CLAUDE.md").resolve()
    assert "beginning of" in context
    assert str(original) in context


def test_an_untruncated_block_states_it_is_complete(tmp_path, monkeypatch):
    """The claim is only safe on the branch that earns it."""
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    result = _run(monkeypatch, repo, "Edit",
                  {"file_path": str((repo / ".." / "sibling" / "x.py").resolve())})
    context = _context(result)
    assert "in full" in context
    # Phrase-precise: the tmp_path this test runs in carries the test's own name,
    # so a bare `"truncated" not in context` matches "untruncated" in the path.
    assert "too large to inject whole" not in context
    assert "beginning of" not in context


def test_read_instructions_reports_truncation_to_its_caller(tmp_path):
    """The renderer needs the fact, not a guess derived from the text."""
    small = tmp_path / "small.md"
    small.write_text("short\n", encoding="utf-8")
    assert hook._read_instructions(small) == ("short\n", False)

    big = tmp_path / "big.md"
    big.write_text("y" * (hook._MAX_BYTES + 10), encoding="utf-8")
    text, truncated = hook._read_instructions(big)
    assert truncated is True
    assert text is not None

    missing = tmp_path / "nope.md"
    assert hook._read_instructions(missing) == (None, False)


# --------------------------------------------------------------------------- #
# fail-open — a hook bug must never wedge a session
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("payload", [
    "",
    "   ",
    "not json at all",
    "{}",
    '{"tool_name": "Edit"}',
    '{"tool_name": "Edit", "tool_input": null}',
    '{"tool_name": "Edit", "tool_input": "a string"}',
    '{"tool_name": null, "tool_input": {"file_path": "../sibling/x"}}',
])
def test_malformed_input_exits_zero_and_writes_nothing(tmp_path, payload):
    """Run as a real subprocess: the exit status is half the contract, and a
    non-zero PreToolUse exit would *block* the tool call."""
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    proc = subprocess.run(
        [sys.executable, str(_MODULE_PATH)],
        input=payload, capture_output=True, text=True, cwd=str(repo),
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == ""


def test_a_malformed_local_toml_injects_nothing(tmp_path, monkeypatch):
    """The guard's parse grants nothing on a shape it cannot read; this hook
    inherits that, so a typo in a personal config file cannot start leaking an
    undeclared repo's file into context."""
    repo = tmp_path / "consumer"
    (repo / ".aide" / "loop").mkdir(parents=True)
    (repo / ".aide" / "loop" / "loop.local.toml").write_text(
        '[hygiene]\nextra_repos = "../sibling"\n', encoding="utf-8"
    )
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    (sibling / "CLAUDE.md").write_text("nope\n", encoding="utf-8")
    assert _run(monkeypatch, repo, "Edit", {"file_path": str(sibling / "x.py")}) is None


def test_the_happy_path_also_exits_zero_as_a_subprocess(tmp_path):
    repo = _consumer(tmp_path, extra_repos=["../sibling"])
    payload = json.dumps({
        "session_id": "sub", "cwd": str(repo), "tool_name": "Edit",
        "tool_input": {"file_path": str((repo / ".." / "sibling" / "x.py").resolve())},
    })
    proc = subprocess.run(
        [sys.executable, str(_MODULE_PATH)],
        input=payload, capture_output=True, text=True, cwd=str(repo),
    )
    assert proc.returncode == 0, proc.stderr
    assert "Never 'fix' the consumer paths." in json.loads(proc.stdout)[
        "hookSpecificOutput"]["additionalContext"]


# --------------------------------------------------------------------------- #
# unit-level helpers
# --------------------------------------------------------------------------- #
def test_instruction_filename_comes_from_the_adapter_declaration():
    """Not hard-coded twice: the hook reads the same `default-context.json` the
    installer does (ADAPTER-SPEC §7)."""
    declared = json.loads(
        (_HOOKS.parent / "default-context.json").read_text(encoding="utf-8")
    )["file"]
    assert hook._instruction_filename() == declared


@pytest.mark.parametrize("declared", [
    "/etc/passwd", "../../outside.md", "C:\\x.md", "", "   ", None, 42,
])
def test_an_escaping_or_junk_declaration_falls_back_to_the_default(tmp_path, declared):
    """A `file` that climbs out of the repo, or is not a usable name at all,
    would have the hook read something in a directory nobody named."""
    fake = tmp_path / "default-context.json"
    fake.write_text(json.dumps({"file": declared}), encoding="utf-8")
    assert hook._instruction_filename(fake) == "CLAUDE.md"


def test_an_escaping_declaration_is_refused_in_both_path_flavours(tmp_path):
    """The check must not depend on the platform it runs on.

    `os.path.isabs` alone is wrong on whichever platform it is not: since 3.13
    `ntpath.isabs("/etc/passwd")` is **False** — a leading-separator path is
    drive-relative, not fully qualified — so a POSIX absolute path passed the
    Windows leg as an ordinary relative name. This pins both flavours the way
    `install.py` already checks the same field.
    """
    for declared in ("/etc/passwd", "\\\\server\\share\\x.md", "C:/x.md",
                     "C:\\x.md", "a/../../out.md"):
        fake = tmp_path / "default-context.json"
        fake.write_text(json.dumps({"file": declared}), encoding="utf-8")
        assert hook._instruction_filename(fake) == "CLAUDE.md", declared


def test_a_nested_declaration_is_honoured(tmp_path):
    """ADAPTER-SPEC §7 allows a nested instruction file (`.github/…`)."""
    fake = tmp_path / "default-context.json"
    fake.write_text(json.dumps({"file": ".github/AGENTS.md"}), encoding="utf-8")
    assert hook._instruction_filename(fake) == ".github/AGENTS.md"


def test_a_missing_declaration_falls_back_to_the_default(tmp_path):
    assert hook._instruction_filename(tmp_path / "nope.json") == "CLAUDE.md"


def test_contains_is_not_fooled_by_a_name_prefix():
    assert hook._contains(Path("/a/repo"), Path("/a/repo/src/x.py"))
    assert hook._contains(Path("/a/repo"), Path("/a/repo"))
    assert not hook._contains(Path("/a/repo"), Path("/a/repo-two/x.py"))
    assert not hook._contains(Path("/a/repo"), Path("/a/other/x.py"))


def test_marker_path_survives_a_hostile_session_id():
    """The session id lands in a filename; a traversal in it must not."""
    marker = hook._marker_path("../../etc/passwd")
    assert ".." not in marker.name
    assert marker.parent == Path(hook.tempfile.gettempdir())
