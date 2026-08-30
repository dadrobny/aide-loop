"""`--update` removes engine files the framework has dropped.

`copy_tree` overwrites and adds but never deletes, so before `prune_stale`
every file ever shipped stayed in every consumer forever. The case that made it
matter is a document reorganised into a directory: the superseded single-file
copy sits beside the new tree, both plausible, with nothing saying which is
live. An agent pointed at "the conventions" can read either.

The prune is deliberately asymmetric — `.aide/` only. These tests pin both
halves: what it removes, and the four things it must never touch.

Stdlib + pytest only; `install.py` is imported as a module.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)


def _symlinks_work(tmp_path: Path) -> bool:
    """Whether this machine can create one at all.

    Windows needs Administrator or Developer Mode. The GitHub runner happens to
    have it; a contributor's machine is not guaranteed to, and an OSError from
    the *setup* of a test reads as a failure of the code under test.
    """
    probe = tmp_path / "_symlink_probe"
    try:
        probe.symlink_to(tmp_path)
    except (OSError, NotImplementedError):
        return False
    probe.unlink()
    return True


def _tree(root: Path, *rel: str) -> Path:
    """Create each `rel` as a file with its own path as content, return `root`."""
    for r in rel:
        path = root / r
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(r, encoding="utf-8")
    return root


def test_a_file_dropped_from_the_source_is_removed(tmp_path: Path):
    src = _tree(tmp_path / "src", "conventions.md", "conventions/6-test-hygiene.md")
    dst = _tree(tmp_path / "dst", "conventions.md", "conventions/6-test-hygiene.md",
                "old-conventions.md")

    log: list = []
    install.prune_stale(src, dst, log)

    assert not (dst / "old-conventions.md").exists()
    assert (dst / "conventions.md").is_file()
    assert (dst / "conventions" / "6-test-hygiene.md").is_file()
    assert any("old-conventions.md" in line for line in log), log


def test_a_directory_the_prune_empties_is_removed_too(tmp_path: Path):
    """Otherwise `.aide/` accumulates empty skeletons of retired layouts."""
    src = _tree(tmp_path / "src", "keep.md")
    dst = _tree(tmp_path / "dst", "keep.md", "retired/a.md", "retired/nested/b.md")

    install.prune_stale(src, dst, [])

    assert not (dst / "retired").exists()
    assert (dst / "keep.md").is_file()


def test_a_directory_still_holding_a_protected_file_survives(tmp_path: Path):
    """Emptiness is checked after the files are gone, not predicted from the source."""
    src = _tree(tmp_path / "src", "keep.md")
    dst = _tree(tmp_path / "dst", "keep.md", "gone/a.md", "gone/loop.local.toml")

    install.prune_stale(src, dst, [])

    assert not (dst / "gone" / "a.md").exists()
    assert (dst / "gone" / "loop.local.toml").is_file()


def test_private_and_junk_names_are_never_prune_candidates(tmp_path: Path):
    """`copy_tree` skips these, so they are absent from the source BY DESIGN.

    Treating "not in the source" as "removed from the engine" would delete a
    consumer's gitignored per-machine config on the next update.
    """
    src = _tree(tmp_path / "src", "loop/loop.py")
    dst = _tree(tmp_path / "dst", "loop/loop.py", "loop/loop.local.toml",
                "loop/__pycache__/loop.cpython-312.pyc", "scripts/aide.pyc")

    install.prune_stale(src, dst, [])

    assert (dst / "loop" / "loop.local.toml").is_file()
    assert (dst / "loop" / "__pycache__" / "loop.cpython-312.pyc").is_file()
    assert (dst / "scripts" / "aide.pyc").is_file()


def test_a_file_the_installer_writes_from_the_adapter_is_kept(tmp_path: Path):
    """The usage probe lives under `.aide/loop/` but comes from `adapters/<n>/`.

    It is absent from `core/`, so without the keep-list the prune would delete
    the probe the same run had just installed.
    """
    src = _tree(tmp_path / "src", "loop/loop.py")
    dst = _tree(tmp_path / "dst", "loop/loop.py", "loop/usage_probe.py")

    install.prune_stale(src, dst, [], keep=install.AIDE_FOREIGN_PATHS)

    assert (dst / "loop" / "usage_probe.py").is_file()


def test_the_keep_list_names_a_path_the_installer_actually_writes(tmp_path: Path):
    """A keep-entry that no longer matches is a silent deletion waiting to happen."""
    assert "loop/usage_probe.py" in install.AIDE_FOREIGN_PATHS
    assert (FRAMEWORK_ROOT / "adapters" / "claude" / "usage_probe.py").is_file()
    assert not (FRAMEWORK_ROOT / "core" / "loop" / "usage_probe.py").exists()


def test_the_adapter_manifest_is_kept_by_the_prune(tmp_path: Path):
    """The manifest lives under `.aide/` and comes from no source file at all.

    Pruned, it would be gone on the update that wrote it, so the NEXT update
    would find nothing to retire — the retirement (issue #85) would work
    exactly once per consumer, on a fresh install, where there is nothing to
    retire.
    """
    assert install.ADAPTER_MANIFEST in install.AIDE_FOREIGN_PATHS
    assert not (FRAMEWORK_ROOT / "core" / install.ADAPTER_MANIFEST).exists()
    src = _tree(tmp_path / "src", "loop/loop.py")
    dst = _tree(tmp_path / "dst", "loop/loop.py", install.ADAPTER_MANIFEST)

    install.prune_stale(src, dst, [], keep=install.AIDE_FOREIGN_PATHS)

    assert (dst / install.ADAPTER_MANIFEST).is_file()


def test_update_keeps_the_manifest_it_wrote_end_to_end(tmp_path: Path):
    """Two updates in a row: the second must still find the first's manifest."""
    target = tmp_path / "consumer"
    target.mkdir()
    assert install.main(["--into", str(target), "--yes"]) == 0
    manifest = target / ".aide" / install.ADAPTER_MANIFEST
    assert manifest.is_file(), "the install wrote no manifest; the rest proves nothing"

    assert install.main(["--into", str(target), "--update"]) == 0
    assert manifest.is_file()
    assert install.main(["--into", str(target), "--update"]) == 0
    assert manifest.is_file()


def test_a_missing_destination_is_not_an_error(tmp_path: Path):
    """A fresh install prunes before anything has ever been written there."""
    install.prune_stale(tmp_path / "src", tmp_path / "never-installed", [])


def test_update_removes_a_stale_engine_file_end_to_end(tmp_path: Path):
    """The prune is wired into `run()`, not merely defined.

    Installs for real, plants a file the engine does not ship, and updates.
    """
    target = tmp_path / "consumer"
    target.mkdir()
    args = install.build_parser().parse_args(["--into", str(target), "--yes"])
    assert install.run(args) == 0

    stale = target / ".aide" / "conventions-old.md"
    stale.write_text("superseded\n", encoding="utf-8")
    probe = target / ".aide" / "loop" / "usage_probe.py"
    assert probe.is_file(), "the Claude adapter ships a probe; the keep-list guards it"

    args = install.build_parser().parse_args(["--into", str(target), "--update"])
    assert install.run(args) == 0

    assert not stale.exists()
    assert probe.is_file()
    assert (target / ".aide" / "conventions.md").is_file()
    assert (target / ".aide" / "conventions" / "6-test-hygiene.md").is_file()


# --------------------------------------------------------------------------- #
# the prune must never abort the install it runs inside
# --------------------------------------------------------------------------- #
def test_a_symlink_to_a_directory_is_unlinked_and_its_target_survives(tmp_path: Path):
    """`is_dir()` follows symlinks, so a link to a dir reaches `rmdir()`.

    On an EMPTY target that raised `NotADirectoryError` and aborted the whole
    update — after `.aide/VERSION` had already been rewritten, so `--check`
    then reported the half-applied install as up to date.
    """
    if not _symlinks_work(tmp_path):
        pytest.skip("this machine cannot create symlinks "
                    "(Windows without Developer Mode)")
    outside = tmp_path / "outside" / "empty"
    outside.mkdir(parents=True)
    src = _tree(tmp_path / "src", "keep.md")
    dst = _tree(tmp_path / "dst", "keep.md")
    (dst / "link").symlink_to(outside, target_is_directory=True)

    install.prune_stale(src, dst, [])

    assert not (dst / "link").exists() and not (dst / "link").is_symlink()
    assert outside.is_dir(), "removing the link must never touch the target"


def test_a_symlink_to_a_non_empty_directory_is_also_unlinked(tmp_path: Path):
    """The emptiness of the TARGET must not decide the fate of the link."""
    if not _symlinks_work(tmp_path):
        pytest.skip("this machine cannot create symlinks "
                    "(Windows without Developer Mode)")
    outside = tmp_path / "outside" / "full"
    outside.mkdir(parents=True)
    (outside / "a.md").write_text("a", encoding="utf-8")
    src = _tree(tmp_path / "src", "keep.md")
    dst = _tree(tmp_path / "dst", "keep.md")
    (dst / "link").symlink_to(outside, target_is_directory=True)

    install.prune_stale(src, dst, [])

    assert not (dst / "link").is_symlink()
    assert (outside / "a.md").is_file()


def test_a_removal_that_fails_is_logged_and_stepped_over(tmp_path, monkeypatch):
    """One unremovable file must not cost the consumer the rest of the update.

    The realistic case is Windows: `.aide/loop/loop.py` held open by a running
    supervisor, during exactly the unattended run an update interrupts.

    The failure is injected rather than staged from the filesystem. What is
    under test is the `except OSError` branch, and every way of producing a
    real one is platform-specific in a different direction — a POSIX
    unwritable directory does not stop a delete on Windows, a Windows
    read-only file does not stop one on POSIX. Staging it would test the OS.
    """
    src = _tree(tmp_path / "src", "keep.md")
    dst = _tree(tmp_path / "dst", "keep.md", "doomed/gone.md", "also-gone.md")

    real_unlink = Path.unlink

    def refuse_one(self, *args, **kwargs):
        if self.name == "gone.md":
            raise PermissionError(13, "Permission denied")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", refuse_one)
    log: list = []
    removed = install.prune_stale(src, dst, log)

    assert (dst / "doomed" / "gone.md").is_file(), "injection did not take"
    assert any("could not be removed" in line for line in log), log
    assert (dst / "doomed" / "gone.md") not in removed
    assert not (dst / "also-gone.md").exists(), "the prune stopped early"
    assert (dst / "doomed").is_dir(), (
        "a directory the prune could not empty must not be reported gone")
    assert (dst / "keep.md").is_file()


@pytest.mark.skipif(os.name == "nt",
                    reason="POSIX mode bits do not gate deletion on Windows")
def test_a_real_permission_error_is_an_oserror_the_prune_catches(tmp_path: Path):
    """The injected error above is only right if a real one has the same type.

    POSIX only, deliberately: this asserts what the operating system raises,
    which is the half the injection cannot speak for.
    """
    src = _tree(tmp_path / "src", "keep.md")
    dst = _tree(tmp_path / "dst", "keep.md", "locked/gone.md", "also-gone.md")
    (dst / "locked").chmod(0o500)          # no write bit: the unlink will fail
    log: list = []
    try:
        install.prune_stale(src, dst, log)
        assert (dst / "locked" / "gone.md").is_file(), "test setup did not lock"
        assert any("could not be removed" in line for line in log), log
        assert not (dst / "also-gone.md").exists(), "the prune stopped early"
    finally:
        (dst / "locked").chmod(0o700)


def test_dry_run_reports_the_same_paths_and_deletes_nothing(tmp_path: Path):
    """What `--check` previews has to be what `--update` then does."""
    src = _tree(tmp_path / "src", "keep.md")
    dst = _tree(tmp_path / "dst", "keep.md", "gone.md", "retired/a.md")

    preview = install.prune_stale(src, dst, [], dry_run=True)

    assert (dst / "gone.md").is_file() and (dst / "retired" / "a.md").is_file()
    assert install.prune_stale(src, dst, []) == preview


def test_check_previews_a_pending_deletion_and_writes_nothing(tmp_path: Path, capsys):
    target = tmp_path / "consumer"
    target.mkdir()
    assert install.main(["--into", str(target), "--yes"]) == 0
    stale = target / ".aide" / "notes-of-mine.md"
    stale.write_text("mine\n", encoding="utf-8")

    rc = install.main(["--into", str(target), "--check"])

    assert stale.is_file(), "--check must never write"
    assert "notes-of-mine.md" in capsys.readouterr().out
    assert rc == 1, "a pending deletion is something to act on before updating"


def test_an_update_names_every_file_it_deleted(tmp_path: Path, capsys):
    """A deletion buried in a 200-line log is a deletion nobody sees."""
    target = tmp_path / "consumer"
    target.mkdir()
    assert install.main(["--into", str(target), "--yes"]) == 0
    (target / ".aide" / "notes-of-mine.md").write_text("mine\n", encoding="utf-8")
    capsys.readouterr()

    assert install.main(["--into", str(target), "--update"]) == 0

    out = capsys.readouterr().out
    assert "Removed 1 file(s)" in out
    assert "notes-of-mine.md" in out.split("Removed 1 file(s)")[1]


def test_an_update_reconciles_the_managed_gitignore_block(tmp_path: Path):
    """Append-only meant a path ADDED to the block never reached a consumer,
    while `core/README.md` went on calling it git-ignored."""
    target = tmp_path / "consumer"
    target.mkdir()
    assert install.main(["--into", str(target), "--yes"]) == 0
    gitignore = target / ".gitignore"
    text = gitignore.read_text(encoding=install.CONSUMER_ENCODING)
    gitignore.write_text(
        text.replace("docs/aide/instructions/*.jsonl\n", ""), encoding="utf-8")

    assert install.main(["--into", str(target), "--update"]) == 0

    text = gitignore.read_text(encoding=install.CONSUMER_ENCODING)
    assert "docs/aide/instructions/*.jsonl" in text
    assert text.count(install.GITIGNORE_MARKER) == 1

