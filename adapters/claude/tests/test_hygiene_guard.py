"""Adapter tests for the command-hygiene guard's rule logic (WI-7 fixes).

Loads the hook by path and exercises ``violations()`` directly — no hook
harness needed. Covers: rule 4 flagging literal ``$(...)`` prose inside a
single-quoted commit message; the carve-out for the documented
framework-update workflow (all four repo-override forms — ``git -C``,
``--git-dir``, ``--work-tree``, ``GIT_DIR=``/``GIT_WORK_TREE=`` — on the
declared ``[framework] local_path``, sourced from the personal, gitignored
``.aide/loop/loop.local.toml``, never the shared ``aide.toml``); and that the
three non-``-C`` forms are recognised at all (they previously were not,
letting an agent achieve the identical effect ``-C`` was blocked for, via a
different flag).
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
# rule 1 — repo-override carve-out for the declared framework clone
# --------------------------------------------------------------------------- #
_OVERRIDE_MARKER = "repo other than cwd"  # distinctive substring of the rule-1 message


def test_git_dash_c_blocked_without_declaration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no .aide/loop/loop.local.toml here
    assert _OVERRIDE_MARKER in _titles("git -C ../aide-loop push")


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
    assert _OVERRIDE_MARKER in _titles("git -C ../other-repo push")


def test_git_dash_c_declaration_in_shared_aide_toml_is_not_honoured(tmp_path, monkeypatch):
    # A machine-specific path must never live in the committed aide.toml —
    # only the personal, gitignored loop.local.toml source is read.
    (tmp_path / "aide.toml").write_text(
        '[framework]\nrepo = "x/aide-loop"\nlocal_path = "../aide-loop"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles("git -C ../aide-loop push")


# --------------------------------------------------------------------------- #
# rule 1 — the three non-`-C` forms of the same operation
# --------------------------------------------------------------------------- #
def test_git_dash_dash_git_dir_blocked_without_declaration(tmp_path, monkeypatch):
    # Regression: previously only `-C` was recognised, so this achieved the
    # identical effect the `-C` block exists to gate, uncaught.
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles("git --git-dir=../aide-loop/.git status")


def test_git_dash_dash_work_tree_blocked_without_declaration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles("git --work-tree=../aide-loop status")


def test_env_prefix_git_dir_blocked_without_declaration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles("GIT_DIR=../aide-loop/.git git log")


def test_env_prefix_git_work_tree_blocked_without_declaration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles("GIT_WORK_TREE=../aide-loop git status")


def test_git_dir_and_work_tree_together_allowed_when_both_match_declared(tmp_path, monkeypatch):
    _declare_local_path(tmp_path, "../aide-loop")
    monkeypatch.chdir(tmp_path)
    assert guard.violations(
        "git --git-dir=../aide-loop/.git --work-tree=../aide-loop status"
    ) == []


def test_git_dir_alone_pointing_at_dot_git_suffix_is_declared(tmp_path, monkeypatch):
    # --git-dir's conventional value is <repo>/.git, not <repo> itself — a
    # naive exact-string comparison against the declared repo ROOT would
    # reject this, the standard way to spell it, as an undeclared repo.
    _declare_local_path(tmp_path, "../aide-loop")
    monkeypatch.chdir(tmp_path)
    assert guard.violations("git --git-dir=../aide-loop/.git log") == []


def test_work_tree_alone_must_match_declared_exactly_not_plus_dot_git(tmp_path, monkeypatch):
    # The .git-suffix leniency is --git-dir-specific; --work-tree must equal
    # the declared repo root exactly (it never conventionally carries /.git).
    _declare_local_path(tmp_path, "../aide-loop")
    monkeypatch.chdir(tmp_path)
    assert guard.violations("git --work-tree=../aide-loop status") == []
    assert _OVERRIDE_MARKER in _titles("git --work-tree=../aide-loop/.git status")


def test_git_dir_and_work_tree_on_different_repos_stays_blocked(tmp_path, monkeypatch):
    # Even with one half declared, mixing a declared and an undeclared repo
    # (history from one, working tree of another) is the dangerous shape the
    # exception must never wave through — require every override path to
    # agree, not just one of several.
    _declare_local_path(tmp_path, "../aide-loop")
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles(
        "git --git-dir=../aide-loop/.git --work-tree=../other-repo status"
    )


def test_env_prefix_form_allowed_for_declared_framework_path(tmp_path, monkeypatch):
    _declare_local_path(tmp_path, "../aide-loop")
    monkeypatch.chdir(tmp_path)
    assert guard.violations("GIT_DIR=../aide-loop git log") == []


def test_git_dir_prose_inside_quotes_does_not_false_positive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no declaration needed — nothing should fire
    assert guard.violations(
        'git commit -m "document --git-dir and GIT_DIR= usage in the README"'
    ) == []


# --------------------------------------------------------------------------- #
# regressions: the always-active rules still fire
# --------------------------------------------------------------------------- #
def test_chaining_and_redirection_still_flagged():
    assert "one command per Bash call" in _titles("git add -A; git commit -m 'x'")
    assert "stderr redirection" in _titles("pytest 2>&1")


def test_operators_inside_quotes_do_not_false_positive():
    assert guard.violations('git commit -m "a && b; c 2>&1 inside prose"') == []


# --------------------------------------------------------------------------- #
# [hygiene] extra_repos — a project may legitimately span more than one repo
# --------------------------------------------------------------------------- #
def _declare_extra_repos(tmp_path, paths, framework=None):
    loop_dir = tmp_path / ".aide" / "loop"
    loop_dir.mkdir(parents=True, exist_ok=True)
    listed = ", ".join(f'"{p}"' for p in paths)
    text = f"[hygiene]\nextra_repos = [{listed}]\n"
    if framework is not None:
        text = f'[framework]\nlocal_path = "{framework}"\n\n' + text
    (loop_dir / "loop.local.toml").write_text(text, encoding="utf-8")


def test_extra_repo_is_allowed(tmp_path, monkeypatch):
    """The recorded complaint: an agent could `git init` a sibling and write
    files into it (both take a path argument) but never `add`/`commit` them."""
    _declare_extra_repos(tmp_path, ["../programme-repo"])
    monkeypatch.chdir(tmp_path)
    assert guard.violations("git -C ../programme-repo add -A") == []
    assert guard.violations("git -C ../programme-repo commit -m 'rescue docs'") == []


def test_undeclared_repo_still_blocked_when_others_are_declared(tmp_path, monkeypatch):
    _declare_extra_repos(tmp_path, ["../programme-repo"])
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles("git -C ../somewhere-else push")


def test_several_extra_repos_are_each_allowed(tmp_path, monkeypatch):
    _declare_extra_repos(tmp_path, ["../one", "../two"])
    monkeypatch.chdir(tmp_path)
    assert guard.violations("git -C ../one status") == []
    assert guard.violations("git -C ../two status") == []


def test_framework_and_extra_repos_coexist(tmp_path, monkeypatch):
    _declare_extra_repos(tmp_path, ["../sibling"], framework="../aide-loop")
    monkeypatch.chdir(tmp_path)
    assert guard.violations("git -C ../aide-loop status") == []
    assert guard.violations("git -C ../sibling status") == []
    assert _OVERRIDE_MARKER in _titles("git -C ../third status")


def test_two_declared_repos_in_one_command_stay_blocked(tmp_path, monkeypatch):
    """Widening the list must not turn the dangerous shape into an approved
    one: history read from one repo and applied to another's working tree is
    what the single-repo rule exists to prevent, declared or not."""
    _declare_extra_repos(tmp_path, ["../one", "../two"])
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles(
        "git --git-dir=../one/.git --work-tree=../two status"
    )


def test_extra_repos_honours_the_git_dir_dot_git_flavour(tmp_path, monkeypatch):
    _declare_extra_repos(tmp_path, ["../sibling"])
    monkeypatch.chdir(tmp_path)
    assert guard.violations(
        "git --git-dir=../sibling/.git --work-tree=../sibling status") == []


def test_empty_extra_repos_keeps_the_default_posture(tmp_path, monkeypatch):
    _declare_extra_repos(tmp_path, [])
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles("git -C ../anything status")


def test_extra_repos_across_multiple_lines_is_parsed(tmp_path, monkeypatch):
    """A TOML array may be written multi-line; a reader that stops at the first
    newline would silently honour only the first entry."""
    loop_dir = tmp_path / ".aide" / "loop"
    loop_dir.mkdir(parents=True)
    (loop_dir / "loop.local.toml").write_text(
        '[hygiene]\nextra_repos = [\n  "../one",\n  "../two",\n]\n',
        encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert guard.violations("git -C ../two status") == []


def test_extra_repos_ignores_a_trailing_comment(tmp_path, monkeypatch):
    loop_dir = tmp_path / ".aide" / "loop"
    loop_dir.mkdir(parents=True)
    (loop_dir / "loop.local.toml").write_text(
        '[hygiene]\nextra_repos = ["../one"]  # the sibling programme repo\n',
        encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert guard.violations("git -C ../one status") == []


def test_extra_repos_in_shared_aide_toml_is_not_honoured(tmp_path, monkeypatch):
    """Machine-specific paths must not live in a committed file — same rule
    `[framework] local_path` already follows."""
    (tmp_path / "aide.toml").write_text(
        '[hygiene]\nextra_repos = ["../sibling"]\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles("git -C ../sibling status")


def test_extra_repos_under_another_section_is_not_honoured(tmp_path, monkeypatch):
    loop_dir = tmp_path / ".aide" / "loop"
    loop_dir.mkdir(parents=True)
    (loop_dir / "loop.local.toml").write_text(
        '[loop]\nextra_repos = ["../sibling"]\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles("git -C ../sibling status")


def _write_local_toml(tmp_path, text):
    loop_dir = tmp_path / ".aide" / "loop"
    loop_dir.mkdir(parents=True, exist_ok=True)
    (loop_dir / "loop.local.toml").write_text(text, encoding="utf-8")


def test_malformed_key_does_not_disable_the_whole_guard(tmp_path, monkeypatch):
    """`extra_repos` with no `=` used to IndexError. The hook fails open, so
    that one typo in a personal config silently switched off EVERY hygiene
    rule, not just this key — a far larger blast radius than the parse bug."""
    _write_local_toml(tmp_path, "[hygiene]\nextra_repos\n")
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles("git -C ../sibling status")   # must not raise
    # and every other rule must still fire
    assert guard.violations("git status && git log")


def test_non_array_value_grants_nothing(tmp_path, monkeypatch):
    """The key is documented as an array. Inferring a grant from an
    undocumented shape is the wrong default for a key that relaxes a guard."""
    _write_local_toml(tmp_path, '[hygiene]\nextra_repos = "../sibling"\n')
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles("git -C ../sibling status")


def test_unterminated_array_grants_nothing(tmp_path, monkeypatch):
    _write_local_toml(tmp_path, '[hygiene]\nextra_repos = [\n  "../sibling",\n')
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles("git -C ../sibling status")


def test_a_similarly_named_key_is_not_mistaken_for_it(tmp_path, monkeypatch):
    _write_local_toml(tmp_path, '[hygiene]\nextra_repos_note = ["../sibling"]\n')
    monkeypatch.chdir(tmp_path)
    assert _OVERRIDE_MARKER in _titles("git -C ../sibling status")
