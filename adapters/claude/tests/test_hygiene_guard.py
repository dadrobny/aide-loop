"""Adapter tests for the command-hygiene guard's rule logic (WI-7 fixes).

Loads the hook by path and exercises ``violations()`` directly — no hook
harness needed. Covers the two consumer-reported defects: rule 4 flagging
literal ``$(...)`` prose inside a single-quoted commit message, and the missing
carve-out for the documented framework-update workflow (``git -C`` on the
declared ``[framework] local_path``, sourced from the personal, gitignored
``.aide/loop/loop.local.toml`` — never the shared ``aide.toml``, which must
never carry a machine-specific filesystem path).
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "hooks" / "command_hygiene_guard.py"
_spec = importlib.util.spec_from_file_location("hygiene_guard", _MODULE_PATH)
guard = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = guard
_spec.loader.exec_module(guard)  # type: ignore[union-attr]


def _titles(cmd):
    return " ".join(guard.violations(cmd))


# --------------------------------------------------------------------------- #
# rule 4 — command substitution in commits, quote-aware
# --------------------------------------------------------------------------- #
def test_commit_single_quoted_dollar_paren_is_prose():
    cmd = "git commit -m 'document the old hook: $(command -v python3) probe'"
    assert "substitution" not in _titles(cmd)


def test_commit_unquoted_substitution_still_flagged():
    assert "substitution" in _titles('git commit -m "x" --author=$(whoami)')


def test_commit_double_quoted_substitution_still_flagged():
    # Inside double quotes bash DOES substitute — must stay a violation.
    assert "substitution" in _titles('git commit -m "built at $(date)"')


# --------------------------------------------------------------------------- #
# rule 1 — git -C carve-out for the declared framework clone
# --------------------------------------------------------------------------- #
def test_git_dash_c_blocked_without_declaration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no .aide/loop/loop.local.toml here
    assert "git -C" in _titles("git -C ../aide-loop push")


def _declare_local_path(tmp_path, path):
    loop_dir = tmp_path / ".aide" / "loop"
    loop_dir.mkdir(parents=True)
    (loop_dir / "loop.local.toml").write_text(
        f'[framework]\nlocal_path = "{path}"\n', encoding="utf-8"
    )


def test_git_dash_c_allowed_for_declared_framework_path(tmp_path, monkeypatch):
    _declare_local_path(tmp_path, "../aide-loop")
    monkeypatch.chdir(tmp_path)
    assert guard.violations("git -C ../aide-loop push") == []
    # A different path stays blocked.
    assert "git -C" in _titles("git -C ../other-repo push")


def test_git_dash_c_declaration_in_shared_aide_toml_is_not_honoured(tmp_path, monkeypatch):
    # A machine-specific path must never live in the committed aide.toml —
    # only the personal, gitignored loop.local.toml source is read.
    (tmp_path / "aide.toml").write_text(
        '[framework]\nrepo = "x/aide-loop"\nlocal_path = "../aide-loop"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert "git -C" in _titles("git -C ../aide-loop push")


# --------------------------------------------------------------------------- #
# regressions: the always-active rules still fire
# --------------------------------------------------------------------------- #
def test_chaining_and_redirection_still_flagged():
    assert "one command per Bash call" in _titles("git add -A; git commit -m 'x'")
    assert "stderr redirection" in _titles("pytest 2>&1")


def test_operators_inside_quotes_do_not_false_positive():
    assert guard.violations('git commit -m "a && b; c 2>&1 inside prose"') == []
