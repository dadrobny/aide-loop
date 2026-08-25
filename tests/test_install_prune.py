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

import sys
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)


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
