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
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)

IMPORT_LINE = "@.aide/AGENT-CONTEXT.md"


def _target(tmp_path: Path, adapter: str | None = None, *, table: bool = True) -> Path:
    """A consumer directory, optionally with an aide.toml recording *adapter*."""
    target = tmp_path / "consumer"
    target.mkdir()
    body = '[project]\nname = "Demo"\n'
    if table:
        body += "\n[aide]\nversion = \"1.0.0\"\n"
        if adapter is not None:
            body += f'adapter = "{adapter}"\n'
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
