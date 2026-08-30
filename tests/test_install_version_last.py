"""`.aide/VERSION` is written last, so a failed install cannot claim completeness.

The failure this pins (issue #80): `copy_tree(core_dir, aide_dir, …)` used to
place `VERSION` in step 1, so every later step — adapter control files,
settings.json, the usage probe, the context import, .gitignore, the prune — ran
after the consumer was already marked as the new version. Any failure in
between left an install that was half-applied and reported "up to date" to
`--check`. Reproduced during the review of #79: a 1.22.0 engine, a 1.21.0
adapter, no `.claude/rules/` at all, and a clean `--check`.

Now `VERSION` is deferred out of step 1 and written after everything else, so:

* a first install that fails partway leaves NO `.aide/VERSION` — `--check`
  exits 2 and names the unfinished install;
* an update that fails partway leaves the OLD version — `--check` says
  "behind" and the ordinary `--update` is the repair.

The injected failure is a malformed `settings.overlay.json`: a real failure
source (OverlayError is raised before anything is written — by design — but
used to fire only after VERSION had already moved), and it exercises the whole
path through `main()`. A second test injects a failure in step 7 to pin that
even the late steps precede the write.

Stdlib + pytest only; `install.py` is imported as a module.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)

CURRENT = (FRAMEWORK_ROOT / "core" / "VERSION").read_text(encoding="utf-8").strip()


def _break_settings_step(target: Path) -> None:
    """Make step 4 (install_settings) raise OverlayError, after step 1 has run."""
    claude = target / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "settings.overlay.json").write_text("{ not json", encoding="utf-8")


def test_successful_install_still_records_the_version(tmp_path: Path):
    """The deferral must not become an omission: a clean install ends current."""
    assert install.main(["--into", str(tmp_path), "--yes"]) == 0
    version_file = tmp_path / ".aide" / "VERSION"
    assert version_file.read_text(encoding="utf-8").strip() == CURRENT
    assert install.main(["--into", str(tmp_path), "--check"]) == 0


def test_failed_first_install_leaves_no_version(tmp_path: Path, capsys):
    _break_settings_step(tmp_path)

    assert install.main(["--into", str(tmp_path), "--yes"]) == 3  # OverlayError

    aide_dir = tmp_path / ".aide"
    assert aide_dir.is_dir()  # step 1 ran: the partial install is real
    assert not (aide_dir / "VERSION").exists(), (
        "a first install that failed after step 1 must not be marked installed")

    capsys.readouterr()
    assert install.main(["--into", str(tmp_path), "--check"]) == 2
    err = capsys.readouterr().err
    assert "did not finish" in err
    assert "no install found" not in err  # a directory full of engine files is not that


def test_failed_first_install_repairs_by_rerunning(tmp_path: Path):
    """The advice `--check` gives must actually work once the cause is fixed."""
    _break_settings_step(tmp_path)
    assert install.main(["--into", str(tmp_path), "--yes"]) == 3

    (tmp_path / ".claude" / "settings.overlay.json").unlink()
    assert install.main(["--into", str(tmp_path), "--yes"]) == 0
    assert (tmp_path / ".aide" / "VERSION").read_text(
        encoding="utf-8").strip() == CURRENT


def test_failed_update_keeps_the_old_version_and_reports_behind(tmp_path: Path, capsys):
    assert install.main(["--into", str(tmp_path), "--yes"]) == 0
    version_file = tmp_path / ".aide" / "VERSION"
    version_file.write_text("0.0.1\n", encoding="utf-8")  # a consumer on an older engine
    _break_settings_step(tmp_path)

    assert install.main(["--into", str(tmp_path), "--update"]) == 3

    assert version_file.read_text(encoding="utf-8").strip() == "0.0.1", (
        "an update that failed after step 1 must not move the version forward")
    capsys.readouterr()
    assert install.main(["--into", str(tmp_path), "--check"]) == 1
    assert "BEHIND" in capsys.readouterr().out  # and --update remains the repair

    (tmp_path / ".claude" / "settings.overlay.json").unlink()
    assert install.main(["--into", str(tmp_path), "--update"]) == 0
    assert version_file.read_text(encoding="utf-8").strip() == CURRENT


def test_even_the_last_pre_version_step_precedes_the_write(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Failure injected as late as step 7 (.gitignore) still withholds VERSION."""
    def boom(target, log):
        raise OSError("disk full")

    monkeypatch.setattr(install, "append_gitignore", boom)
    with pytest.raises(OSError):
        install.main(["--into", str(tmp_path), "--yes"])

    assert (tmp_path / ".aide").is_dir()
    assert not (tmp_path / ".aide" / "VERSION").exists()
