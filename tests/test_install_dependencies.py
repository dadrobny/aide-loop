"""The installer asks the engine what the target lacks (issue #354).

`install.py` imported no `subprocess`, called no `shutil.which`, and asked for
`git.mode` without looking: it scaffolded `auto-merge` into a target with no
remote, or into one that was not a repository at all, and the first push of
the first merge was where anyone found out. Now the interactive prompt offers
`local` where there is no `origin`, and after writing, the installer prints
the offline half of `aide env`'s report — the engine's own, loaded by path,
never a second reading — as warnings. It never moves the exit code.

Stdlib + pytest only; `install.py` is imported as a module.
"""
from __future__ import annotations

import builtins
import shutil
import subprocess
import sys
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)


class _Tty:
    """A stdin that says it is a terminal, so the prompts run."""

    def isatty(self) -> bool:
        return True


def _git_init(target: Path) -> None:
    subprocess.run(["git", "init", "-q", str(target)], check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _install_pressing_enter(target: Path, monkeypatch, capsys) -> str:
    """Install interactively, accepting every default; the prompt for
    git.mode as the person saw it, then everything printed."""
    prompts = []
    monkeypatch.setattr(sys, "stdin", _Tty())
    monkeypatch.setattr(builtins, "input",
                        lambda text="": prompts.append(text) or "")
    capsys.readouterr()
    assert install.main(["--into", str(target), "--test-command",
                         "git --version"]) == 0
    mode_prompt = next(p for p in prompts if p.startswith("git.mode"))
    return mode_prompt + "\n" + capsys.readouterr().out


def _mode(target: Path) -> str:
    text = (target / "aide.toml").read_text(encoding="utf-8")
    return next(l for l in text.splitlines() if l.startswith("mode = "))


def test_a_target_with_no_remote_is_offered_local_and_told_why(
        tmp_path: Path, monkeypatch, capsys):
    _git_init(tmp_path)
    out = _install_pressing_enter(tmp_path, monkeypatch, capsys)
    assert "(local)" in out.splitlines()[0]
    assert f"git.mode defaults to local: {tmp_path} has no remote named origin" in out
    assert _mode(tmp_path) == 'mode = "local"'
    assert "needs a remote named origin" not in out     # nothing left to warn


def test_a_target_with_an_origin_keeps_auto_merge_as_the_default(
        tmp_path: Path, monkeypatch, capsys):
    _git_init(tmp_path)
    subprocess.run(["git", "remote", "add", "origin",
                    (tmp_path / "elsewhere.git").as_posix()], cwd=str(tmp_path),
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = _install_pressing_enter(tmp_path, monkeypatch, capsys)
    assert "(auto-merge)" in out.splitlines()[0]
    assert "defaults to local" not in out
    assert _mode(tmp_path) == 'mode = "auto-merge"'


def test_yes_keeps_auto_merge_and_warns(tmp_path: Path, capsys):
    _git_init(tmp_path)
    capsys.readouterr()
    assert install.main(["--into", str(tmp_path), "--yes",
                         "--test-command", "git --version"]) == 0
    out = capsys.readouterr().out
    assert _mode(tmp_path) == 'mode = "auto-merge"'
    assert ('warning: [git] mode = "auto-merge" in aide.toml needs a remote '
            'named origin — add one') in out


def test_a_target_that_is_not_a_repository_gets_its_sentence(
        tmp_path: Path, capsys):
    target = tmp_path / "plain"
    target.mkdir()
    capsys.readouterr()
    assert install.main(["--into", str(target), "--yes",
                         "--test-command", "git --version"]) == 0
    out = capsys.readouterr().out
    assert f"warning: {target} is not inside a git repository" in out
    # One cause, one sentence: no origin is asked of a directory with no git.
    assert "needs a remote named origin" not in out


def test_a_target_that_lacks_nothing_gets_no_warning(tmp_path: Path, capsys):
    _git_init(tmp_path)
    capsys.readouterr()
    assert install.main(["--into", str(tmp_path), "--yes", "--git-mode",
                         "local", "--test-command", "git --version"]) == 0
    assert "lacks what aide.toml needs" not in capsys.readouterr().out


def test_an_update_reports_what_the_kept_config_needs(tmp_path: Path, capsys):
    """`--update` never touches aide.toml, so a mode set long ago is checked
    against the machine it now runs on."""
    _git_init(tmp_path)
    assert install.main(["--into", str(tmp_path), "--yes",
                         "--test-command", "git --version"]) == 0
    capsys.readouterr()
    assert install.main(["--into", str(tmp_path), "--update"]) == 0
    assert "needs a remote named origin" in capsys.readouterr().out


def test_a_non_repository_target_is_told_what_the_pushing_modes_need(
        tmp_path: Path, monkeypatch, capsys):
    target = tmp_path / "plain"
    target.mkdir()
    out = _install_pressing_enter(target, monkeypatch, capsys)
    assert (f"git.mode defaults to local: {target} is not a git repository "
            f"yet, and auto-merge and pr need a repository with a remote "
            f"named origin") in out
    assert _mode(target) == 'mode = "local"'


def test_a_failure_asking_the_engine_never_breaks_the_prompt(
        tmp_path: Path, monkeypatch):
    class Broken:
        _TOPLEVEL: dict = {}

        @staticmethod
        def in_repository(target):
            raise RuntimeError("anything at all")
    monkeypatch.setattr(install, "_engine", lambda: Broken)
    assert install.origin_missing(tmp_path) is None


def test_an_engine_that_cannot_load_is_a_warning_never_a_failed_install(
        tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setattr(install, "_engine", lambda: (_ for _ in ()).throw(
        ImportError("no engine here")))
    assert install.dependency_warnings(tmp_path) == [
        "this machine's dependencies were not checked (no engine here) — run "
        "`python .aide/scripts/aide.py env` in the target"]
    assert install.origin_missing(tmp_path) is None


def test_a_default_runner_on_a_python3_only_host_names_python3(
        tmp_path: Path, capsys, monkeypatch):
    """The scaffold's `python -m pytest` on a host that has only python3:
    the warning says what would run, not only what does not."""
    real = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name, *a, **k: (
        None if name == "python" else
        "/usr/bin/python3" if name == "python3" else real(name, *a, **k)))
    _git_init(tmp_path)
    capsys.readouterr()
    assert install.main(["--into", str(tmp_path), "--yes",
                         "--git-mode", "local"]) == 0
    out = capsys.readouterr().out
    assert "warning: the test command's 'python' is not on PATH" in out
    assert "this machine has python3, so 'python3 -m pytest' would run" in out
