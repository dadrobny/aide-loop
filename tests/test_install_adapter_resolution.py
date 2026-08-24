"""The installer must read back the adapter it recorded.

The recorded defect (issue #63): `scaffold_aide_toml` wrote `[aide] adapter`
into a consumer's aide.toml and nothing ever read it. `run()` re-derived the
adapter from `--adapter` on every invocation — `--update` and `--check`
included — where the flag defaulted to `claude`. With one adapter implemented
the wrong default is accidentally always right; the moment a second exists, a
plain `--update` installs a second provider's control files, and (since #59)
creates a root instruction file importing `AGENT-CONTEXT.md`, into a repo that
never chose that provider.

Testable ahead of a real second adapter: `resolve_adapter` reads only the
target, and `foreign_context_drift` reads only the adapters directory, so a
synthesised adapter under `tmp_path` is enough.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)

IMPORT_LINE = "@.aide/AGENT-CONTEXT.md"


def _target(tmp_path: Path, adapter: str | None = None, *, table: bool = True) -> Path:
    """A consumer directory, optionally with an aide.toml recording *adapter*."""
    target = tmp_path / "consumer"
    target.mkdir(parents=True)
    body = '[project]\nname = "Demo"\n'
    if table:
        body += "\n[aide]\nversion = \"1.0.0\"\n"
        if adapter is not None:
            # A backslash is an escape inside a TOML basic string, so a value
            # meant to DECODE to `a\b` has to be written doubled — otherwise
            # the file is malformed and the fallback, not the guard, is what
            # the test would be measuring.
            body += 'adapter = "%s"\n' % adapter.replace("\\", "\\\\")
    (target / "aide.toml").write_text(body, encoding="utf-8")
    return target


# --------------------------------------------------------------------------- #
# resolve_adapter — the record outranks the default
# --------------------------------------------------------------------------- #
def test_the_recorded_adapter_wins_when_no_flag_is_given(tmp_path: Path):
    """The whole defect in one assertion: a bare --update on a non-claude repo
    must not resolve to claude."""
    adapter, err = install.resolve_adapter(_target(tmp_path, "copilot"), None)
    assert err is None
    assert adapter == "copilot"


def test_a_matching_flag_is_accepted(tmp_path: Path):
    adapter, err = install.resolve_adapter(_target(tmp_path, "copilot"), "copilot")
    assert (adapter, err) == ("copilot", None)


def test_a_contradicting_flag_is_an_error_naming_both(tmp_path: Path):
    adapter, err = install.resolve_adapter(_target(tmp_path, "copilot"), "claude")
    assert adapter is None
    assert err and "copilot" in err and "claude" in err
    # The reader has to be told how to switch on purpose, or the error is a wall.
    assert "aide.toml" in err


def test_an_absent_aide_key_falls_back_to_the_flag(tmp_path: Path):
    """An install predating the [aide] table records nothing; the flag is then
    the only signal there is, and must be honoured rather than errored on."""
    target = _target(tmp_path, None)
    assert install.resolve_adapter(target, "copilot") == ("copilot", None)


def test_no_record_and_no_flag_falls_back_to_the_default(tmp_path: Path):
    target = _target(tmp_path, None, table=False)
    assert install.resolve_adapter(target, None) == (install.DEFAULT_ADAPTER, None)


def test_a_missing_aide_toml_is_not_an_error(tmp_path: Path):
    target = tmp_path / "bare"
    target.mkdir()
    assert install.resolve_adapter(target, None) == (install.DEFAULT_ADAPTER, None)


def test_an_unreadable_aide_toml_falls_back_rather_than_crashing(tmp_path: Path):
    """A broken config is the engine's error to report, not the installer's to
    die on — `_project_scope` degrades the same way."""
    target = tmp_path / "consumer"
    target.mkdir()
    (target / "aide.toml").write_text("[aide\nadapter = ", encoding="utf-8")
    adapter, err = install.resolve_adapter(target, None)
    assert err is None and adapter == install.DEFAULT_ADAPTER


def test_a_blank_recorded_adapter_is_treated_as_absent(tmp_path: Path):
    target = _target(tmp_path, "   ")
    assert install.resolve_adapter(target, None) == (install.DEFAULT_ADAPTER, None)


def test_reading_the_config_never_touches_sys_path_at_all(tmp_path: Path):
    """The engine is loaded by file path, so global import state stays out of
    it. An earlier attempt prepended `sys.path` and left one entry per call —
    in a pytest session that is dozens, silently outranking every other import
    path for the rest of the run."""
    target = _target(tmp_path, "claude")
    before = list(sys.path)
    for _ in range(5):
        install.resolve_adapter(target, None)
        install._project_scope(target)
    assert sys.path == before


def test_the_engine_wins_over_a_decoy_aide_on_the_path_and_in_sys_modules(
        tmp_path: Path):
    """The property that makes path-loading the right mechanism.

    `import aide` resolves through `sys.path` *and* `sys.modules`, and neither
    belongs to install.py. Prepending to `sys.path` answers only the first: a
    host process that bound some other `aide` before install.py ran wins the
    name outright, whatever the path order, and install.py would then read a
    different config loader than the engine uses. Both decoys are planted here;
    the engine must still answer.
    """
    decoy_dir = tmp_path / "decoy"
    decoy_dir.mkdir()
    (decoy_dir / "aide.py").write_text(
        "def load_config(target):\n"
        "    return {'aide': {'adapter': 'DECOY'}}\n", encoding="utf-8")

    decoy_mod = types.ModuleType("aide")
    decoy_mod.load_config = lambda target: {"aide": {"adapter": "DECOY"}}

    target = _target(tmp_path, "copilot")
    saved_path = list(sys.path)
    saved_mod = sys.modules.get("aide")
    saved_cache = install._ENGINE_LOAD_CONFIG
    sys.path.insert(0, str(decoy_dir))
    sys.modules["aide"] = decoy_mod
    install._ENGINE_LOAD_CONFIG = None   # force a real load, not a warm cache
    try:
        assert install.resolve_adapter(target, None) == ("copilot", None)
    finally:
        sys.path[:] = saved_path
        # Leave no decoy behind: a cached wrong `aide` would follow this test
        # into every later one in the session.
        sys.modules.pop("aide", None)
        if saved_mod is not None:
            sys.modules["aide"] = saved_mod
        install._ENGINE_LOAD_CONFIG = saved_cache


def test_a_missing_engine_file_falls_back_rather_than_crashing(tmp_path: Path,
                                                               monkeypatch):
    """The readers fall back on any exception; the loader must raise a *named*
    one rather than an AttributeError from an unusable spec."""
    monkeypatch.setattr(install, "FRAMEWORK_ROOT", tmp_path / "nowhere")
    monkeypatch.setattr(install, "_ENGINE_LOAD_CONFIG", None)
    assert install.resolve_adapter(_target(tmp_path, "copilot"),
                                   None) == (install.DEFAULT_ADAPTER, None)
    assert install._project_scope(tmp_path) == ("src", "tests")


def test_the_engine_handle_is_not_published_under_a_guessable_name(tmp_path: Path):
    """Loading by path and then registering the module in `sys.modules` would
    reintroduce the collision from the other side."""
    saved = sys.modules.get("aide")
    sys.modules.pop("aide", None)
    try:
        install.resolve_adapter(_target(tmp_path, "claude"), None)
        assert "aide" not in sys.modules
    finally:
        if saved is not None:
            sys.modules["aide"] = saved


# --------------------------------------------------------------------------- #
# an adapter name is a directory name, from either source
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", ["..", "../core", "a/b", "a\\b", "C:x", ".", "/etc"])
def test_a_recorded_value_that_is_a_path_is_refused(tmp_path: Path, bad: str):
    """The adapter is joined onto FRAMEWORK_ROOT, and since it became readable
    from a project-owned aide.toml it no longer arrives only from a typed flag.
    `../core` would resolve outside `adapters/` and have --update copy from an
    unintended framework directory."""
    adapter, err = install.resolve_adapter(_target(tmp_path, bad), None)
    assert adapter is None
    assert err and "not an adapter name" in err
    assert "aide.toml" in err  # the reader has to be told which source to fix


@pytest.mark.parametrize("bad", ["..", "../core", "a/b"])
def test_a_flag_that_is_a_path_is_refused_too(tmp_path: Path, bad: str):
    adapter, err = install.resolve_adapter(_target(tmp_path, None, table=False), bad)
    assert adapter is None
    assert err and "--adapter" in err


def test_a_legitimate_name_still_resolves(tmp_path: Path):
    """The guard must not cost an adapter a normal name."""
    for name in ("claude", "copilot", "some-runtime_2.0"):
        assert install.resolve_adapter(_target(tmp_path / name, name), None) == (name, None)
    assert install.resolve_adapter(_target(tmp_path / "f", None, table=False),
                                   "copilot") == ("copilot", None)


def test_the_traversal_never_reaches_the_filesystem(tmp_path: Path, capsys):
    """End to end: the refusal is exit 2 before anything is copied."""
    target = _target(tmp_path, "../core")
    assert install.main(["--into", str(target), "--update"]) == 2
    assert "not an adapter name" in capsys.readouterr().err
    assert not (target / ".aide").exists()


# --------------------------------------------------------------------------- #
# foreign_context_drift — the superseded provider's file, reported not removed
# --------------------------------------------------------------------------- #
def _adapters(tmp_path: Path, monkeypatch, **decls: str) -> None:
    """Point FRAMEWORK_ROOT at a tmp tree whose adapters declare *decls*
    (name -> instruction filename)."""
    root = tmp_path / "framework"
    for name, filename in decls.items():
        d = root / "adapters" / name
        d.mkdir(parents=True)
        (d / install.ADAPTER_DEFAULT_CONTEXT).write_text(
            '{"file": "%s", "import": "@{path}"}' % filename, encoding="utf-8")
    monkeypatch.setattr(install, "FRAMEWORK_ROOT", root)


def test_another_adapters_instruction_file_carrying_our_import_is_reported(
        tmp_path: Path, monkeypatch):
    target = _target(tmp_path, "copilot")
    _adapters(tmp_path, monkeypatch, claude="CLAUDE.md", copilot="COPILOT.md")
    (target / "CLAUDE.md").write_text(IMPORT_LINE + "\n", encoding="utf-8")

    found = install.foreign_context_drift(target, "copilot")
    assert len(found) == 1
    assert "CLAUDE.md" in found[0] and "claude" in found[0]
    # Reported, never removed — vision.md principle 4.
    assert (target / "CLAUDE.md").is_file()


def test_the_report_claims_no_record_when_the_adapter_was_default_resolved(
        tmp_path: Path, monkeypatch):
    """Every install predating the [aide] table resolves by fallback, not by
    record. The one message whose job is to be trusted about which provider is
    live must not claim the repo chose it."""
    target = _target(tmp_path, None, table=False)
    _adapters(tmp_path, monkeypatch, claude="CLAUDE.md", copilot="COPILOT.md")
    (target / "COPILOT.md").write_text(IMPORT_LINE + "\n", encoding="utf-8")

    adapter, err = install.resolve_adapter(target, None)
    assert (adapter, err) == ("claude", None)      # resolved by fallback
    found = install.foreign_context_drift(target, adapter)
    assert len(found) == 1 and "records" not in found[0]


def test_a_foreign_file_without_our_import_is_none_of_our_business(
        tmp_path: Path, monkeypatch):
    """A project may have a file that happens to share the name. Only the line
    the installer writes makes it ours to talk about."""
    target = _target(tmp_path, "copilot")
    _adapters(tmp_path, monkeypatch, claude="CLAUDE.md", copilot="COPILOT.md")
    (target / "CLAUDE.md").write_text("# notes\n", encoding="utf-8")
    assert install.foreign_context_drift(target, "copilot") == []


def test_our_own_instruction_file_is_not_reported_as_foreign(
        tmp_path: Path, monkeypatch):
    target = _target(tmp_path, "claude")
    _adapters(tmp_path, monkeypatch, claude="CLAUDE.md", copilot="COPILOT.md")
    (target / "CLAUDE.md").write_text(IMPORT_LINE + "\n", encoding="utf-8")
    assert install.foreign_context_drift(target, "claude") == []


def test_two_adapters_declaring_one_file_do_not_report_it(
        tmp_path: Path, monkeypatch):
    """The file is the live one, reached by both runtimes — not a leftover."""
    target = _target(tmp_path, "claude")
    _adapters(tmp_path, monkeypatch, claude="AGENTS.md", other="AGENTS.md")
    (target / "AGENTS.md").write_text(IMPORT_LINE + "\n", encoding="utf-8")
    assert install.foreign_context_drift(target, "claude") == []


def test_an_adapter_declaring_nothing_is_skipped(tmp_path: Path, monkeypatch):
    target = _target(tmp_path, "claude")
    _adapters(tmp_path, monkeypatch, claude="CLAUDE.md")
    (tmp_path / "framework" / "adapters" / "silent").mkdir()
    assert install.foreign_context_drift(target, "claude") == []


# --------------------------------------------------------------------------- #
# report_version — an orphan is non-zero, but not "run --update"
# --------------------------------------------------------------------------- #
def _installed(tmp_path: Path, version: str) -> Path:
    path = tmp_path / ".aide" / "VERSION"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(version + "\n", encoding="utf-8")
    return path


def test_an_orphan_fails_check_even_on_a_current_engine(tmp_path: Path, capsys):
    path = _installed(tmp_path, "1.2.0")
    rc = install.report_version("1.2.0", path, tmp_path, None, ["CLAUDE.md is stale"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "CLAUDE.md is stale" in out
    # No --update repairs a project-owned file, so it must not be prescribed.
    assert "--update" not in out


def test_an_orphan_fails_check_on_an_ahead_engine(tmp_path: Path):
    path = _installed(tmp_path, "9.9.9")
    assert install.report_version("1.2.0", path, tmp_path, None, ["stale"]) == 1


def test_no_orphans_leaves_the_up_to_date_path_untouched(tmp_path: Path, capsys):
    path = _installed(tmp_path, "1.2.0")
    assert install.report_version("1.2.0", path, tmp_path, None, []) == 0
    assert "up to date" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# end to end, against a real install
# --------------------------------------------------------------------------- #
def test_update_without_a_flag_resolves_the_adapter_from_the_target(
        tmp_path: Path, capsys):
    target = tmp_path / "consumer"
    target.mkdir()
    assert install.main(["--into", str(target), "--yes"]) == 0
    assert 'adapter = "claude"' in (target / "aide.toml").read_text(encoding="utf-8")

    capsys.readouterr()
    assert install.main(["--into", str(target), "--update"]) == 0
    # The log line reports the RESOLVED adapter — it used to print the flag,
    # which is the value that was wrong in the first place.
    assert "AIDE update: claude" in capsys.readouterr().out


def test_a_contradicting_flag_refuses_the_update(tmp_path: Path, capsys):
    target = tmp_path / "consumer"
    target.mkdir()
    assert install.main(["--into", str(target), "--yes"]) == 0
    capsys.readouterr()

    assert install.main(["--into", str(target), "--update", "--adapter", "copilot"]) == 2
    err = capsys.readouterr().err
    assert "copilot" in err and "claude" in err
    # It must fail on the contradiction, not on the adapter not existing yet:
    # the same refusal has to hold once adapters/copilot/ is real.
    assert "unknown adapter" not in err


def test_an_unknown_adapter_with_nothing_recorded_still_says_so(tmp_path: Path, capsys):
    target = tmp_path / "consumer"
    target.mkdir()
    assert install.main(["--into", str(target), "--adapter", "nope", "--yes"]) == 2
    assert "unknown adapter" in capsys.readouterr().err
