"""`await_run.py` — a long command run detached and waited on in bounded slices.

A sub-agent that ends its turn to await a background command hands its caller
the placeholder and is never woken (issue #274), so the validator starts the
suite and the merge through this script and waits inside its turn. What is
held here: the run outlives the process that started it, its exit code comes
back through ``wait``, a run still going answers with its own code, state
lives under the git directory, and the command line reaches no command but
the two fixed ones — the property that lets it be allow-listed.

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


def test_the_wrappers_own_codes_collide_with_nothing_it_reports():
    """pytest exits 0–5 and `aide merge` 0–2; a caller must tell them apart."""
    assert ar.EXIT_RUNNING not in range(0, 6)
    assert ar.EXIT_USAGE not in range(0, 6)
    assert len({ar.EXIT_RUNNING, ar.EXIT_USAGE, ar.EXIT_NOT_STARTED}) == 3


def test_a_command_that_cannot_start_is_recorded_not_left_running(repo: Path, capsys):
    directory = ar.state_dir(repo)
    label = ar.start_run("suite", [str(repo / "no-such-program")], repo, directory)
    assert ar.wait_run(label, directory, 60) == ar.EXIT_NOT_STARTED
    assert "could not start" in capsys.readouterr().out


def test_two_starts_in_one_second_get_two_labels(repo: Path):
    directory = ar.state_dir(repo)
    first = ar.start_run("suite", _py("pass"), repo, directory)
    second = ar.start_run("suite", _py("pass"), repo, directory)
    assert first != second
    for label in (first, second):
        assert ar._LABEL_RE.match(label), label
        assert ar.wait_run(label, directory, 60) == 0


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


def test_suite_is_the_test_command_the_engine_resolves(tmp_path: Path):
    """No venv: the configured command as written, exactly as `aide merge` runs it."""
    (tmp_path / "aide.toml").write_text(
        '[python]\ntest_command = "python -m pytest -q tests/unit"\n', encoding="utf-8")
    assert ar.suite_command(tmp_path, ENGINE) == [
        "python", "-m", "pytest", "-q", "tests/unit"]


def test_suite_binds_python_to_the_venv_like_the_engine(tmp_path: Path):
    venv_py = (tmp_path / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
               / ("python.exe" if sys.platform == "win32" else "python"))
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("", encoding="utf-8")
    assert ar.suite_command(tmp_path, ENGINE)[0] == str(venv_py)


def test_a_missing_engine_is_a_usage_error(repo: Path, capsys):
    assert ar.main(["start", "suite"], root=repo,
                   engine=repo / ".aide" / "scripts" / "aide.py") == ar.EXIT_USAGE
    assert "engine" in capsys.readouterr().err


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
    for code in (ar.EXIT_RUNNING, ar.EXIT_USAGE, ar.EXIT_NOT_STARTED):
        assert str(code) in text
