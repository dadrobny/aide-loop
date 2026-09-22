"""`install.py --check` — does a consumer learn it is outdated?

The failure this exists to prevent: a project's `.aide/VERSION` and the
framework's `core/VERSION` both read `1.1.0` while the engine differed by
hundreds of lines. Comparison is only useful if it is honest about ordering,
tolerant of a hand-edited VERSION file, and writes nothing.

Stdlib + pytest only; `install.py` is imported as a module.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)


# --------------------------------------------------------------------------- #
# parse_version / compare_versions — the ordering
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,expected", [
    ("1.2.0", (1, 2, 0)),
    ("1.2.0\n", (1, 2, 0)),
    ("  1.2.0  ", (1, 2, 0)),
    ("﻿1.2.0", (1, 2, 0)),      # editor-added BOM
    ("1.2", (1, 2)),
    ("1.2.0-rc1", (1, 2, 0)),        # pre-release suffix ignored for ordering
    ("", (0,)),
    ("garbage", (0,)),
])
def test_parse_version(text, expected):
    assert install.parse_version(text) == expected


@pytest.mark.parametrize("installed,available,state", [
    ("1.2.0", "1.2.0", "current"),
    ("1.1.0", "1.2.0", "behind"),
    ("1.2.0", "1.1.0", "ahead"),
    ("1.2.0", "2.0.0", "behind"),
    ("1.9.0", "1.10.0", "behind"),   # numeric, not lexicographic
    ("1.2", "1.2.0", "current"),     # short form is zero-padded
    ("1.2.0", "1.2", "current"),
    ("1.2.1", "1.2", "ahead"),
])
def test_compare_versions(installed, available, state):
    assert install.compare_versions(installed, available) == state


def test_comparison_is_antisymmetric():
    assert install.compare_versions("1.1.0", "1.2.0") == "behind"
    assert install.compare_versions("1.2.0", "1.1.0") == "ahead"


# --------------------------------------------------------------------------- #
# report_version — exit codes and output
# --------------------------------------------------------------------------- #
def _installed(tmp_path: Path, version: str, *, bom: bool = False) -> Path:
    aide = tmp_path / ".aide"
    aide.mkdir(parents=True, exist_ok=True)
    path = aide / "VERSION"
    path.write_text(("﻿" if bom else "") + version + "\n", encoding="utf-8")
    return path


def test_current_exits_zero(tmp_path, capsys):
    path = _installed(tmp_path, "1.2.0")
    assert install.report_version("1.2.0", path, tmp_path) == 0
    assert "up to date" in capsys.readouterr().out


def test_behind_exits_one_and_says_how_to_fix(tmp_path, capsys):
    path = _installed(tmp_path, "1.1.0")
    assert install.report_version("1.2.0", path, tmp_path) == 1
    out = capsys.readouterr().out
    assert "BEHIND" in out
    assert "--update" in out


def test_ahead_is_reported_but_not_an_error(tmp_path, capsys):
    """A stale framework checkout is the maintainer's problem, not a gate failure."""
    path = _installed(tmp_path, "1.3.0")
    assert install.report_version("1.2.0", path, tmp_path) == 0
    assert "AHEAD" in capsys.readouterr().out


def test_a_pending_config_move_is_reported_but_is_not_an_error(tmp_path, capsys):
    """The next `--update` performs the move by itself, so a preview of it is a
    notice: the install is still current, and the exit code says so."""
    path = _installed(tmp_path, "2.0.0")
    move = ("move", ".aide/loop/loop.local.toml is no longer read since 2.0.0 "
                    "— --update will MOVE it to .aide/local.toml")
    assert install.report_version("2.0.0", path, tmp_path, migration=[move]) == 0
    out = capsys.readouterr().out
    assert "--update will MOVE it" in out
    assert "up to date" in out


def test_a_config_conflict_fails_the_check_and_names_the_decision(tmp_path, capsys):
    """Both files present is the one migration case no update resolves, so an
    otherwise-current install still exits 1 — and the closing line points at
    the decision rather than at `--update`, which would send the reader in a
    circle past the line that already said what to do."""
    path = _installed(tmp_path, "2.0.0")
    conflict = ("conflict", ".aide/loop/loop.local.toml is no longer read "
                            "(2.0.0 moved the per-machine config to "
                            ".aide/local.toml, which already exists)")
    assert install.report_version("2.0.0", path, tmp_path,
                                  migration=[conflict]) == 1
    out = capsys.readouterr().out
    assert "which already exists" in out
    assert "needs a decision" in out
    assert "--update" not in out.splitlines()[-1]


def test_missing_install_is_distinct_from_outdated(tmp_path, capsys):
    assert install.report_version("1.2.0", tmp_path / ".aide" / "VERSION", tmp_path) == 2
    assert "no install found" in capsys.readouterr().err


def test_partial_install_is_distinct_from_no_install(tmp_path, capsys):
    """VERSION is written last, so `.aide/` full of files with no VERSION is a
    first install that failed partway — not "no install found"."""
    (tmp_path / ".aide").mkdir()
    (tmp_path / ".aide" / "conventions.md").write_text("x", encoding="utf-8")

    assert install.report_version("1.2.0", tmp_path / ".aide" / "VERSION", tmp_path) == 2

    err = capsys.readouterr().err
    assert "did not finish" in err
    assert "no install found" not in err


def test_unlistable_aide_dir_reports_instead_of_raising(tmp_path, capsys, monkeypatch):
    """The partial-install probe reads the filesystem; a permission error there
    must not turn a report-only command into a traceback. Simulated by patching
    iterdir rather than chmod: root ignores modes and Windows has none."""
    (tmp_path / ".aide").mkdir()

    def denied(self):
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(type(tmp_path), "iterdir", denied)

    assert install.report_version("1.2.0", tmp_path / ".aide" / "VERSION", tmp_path) == 2
    assert "no install found" in capsys.readouterr().err


def test_bom_in_the_consumers_version_file_does_not_fake_a_mismatch(tmp_path, capsys):
    path = _installed(tmp_path, "1.2.0", bom=True)
    assert install.report_version("1.2.0", path, tmp_path) == 0
    assert "up to date" in capsys.readouterr().out


def test_check_writes_nothing(tmp_path):
    path = _installed(tmp_path, "1.1.0")
    before = path.read_bytes()
    listing_before = sorted(p.name for p in tmp_path.rglob("*"))

    install.report_version("1.2.0", path, tmp_path)

    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.rglob("*")) == listing_before


def test_check_via_argv_does_not_install(tmp_path, capsys):
    """End-to-end through main(): --check must not create .claude/ or aide.toml."""
    _installed(tmp_path, "1.1.0")

    rc = install.main(["--into", str(tmp_path), "--check"])

    assert rc == 1  # behind
    assert not (tmp_path / ".claude").exists()
    assert not (tmp_path / "aide.toml").exists()
