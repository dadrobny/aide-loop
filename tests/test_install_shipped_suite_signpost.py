"""The shipped suite is announced where the reader meets it.

`install.py` copies `core/scripts/tests/` into every consumer as
`.aide/scripts/tests/`, and for a long while nothing said whether the consumer
was meant to run it. The default outcome was that nobody did: `.aide/` is a
dot-directory, so pytest's default ``norecursedirs`` (``.*``) skips it whether
or not the repo sets ``testpaths`` — an engine update landing with its own suite
never executed, and a broken verb found mid-loop instead.

The fix was signposting, so these are signpost tests: the completion output
names the directory and the command on **both** install paths, and the engine
README carries the row and the answer. The `--update` leg is the one that
matters and the one easiest to regress — the line sits above the
``if not args.update`` block precisely because update is when a shipped test can
newly go red.

Stdlib + pytest only; `install.py` is imported as a module.
"""
from __future__ import annotations

import sys
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)

CORE_README = FRAMEWORK_ROOT / "core" / "README.md"
SHIPPED_TESTS = ".aide/scripts/tests"


def _consumer(tmp_path: Path) -> Path:
    target = tmp_path / "consumer"
    target.mkdir()
    return target


def _install(target: Path, *extra: str) -> int:
    return install.main(["--adapter", "claude", "--into", str(target), "--yes", *extra])


def test_a_fresh_install_names_the_shipped_suite_and_how_to_run_it(tmp_path, capsys):
    target = _consumer(tmp_path)
    assert _install(target) == 0
    out = capsys.readouterr().out
    assert SHIPPED_TESTS in out
    assert f"pytest {SHIPPED_TESTS}" in out


def test_update_names_it_too__the_leg_that_actually_matters(tmp_path, capsys):
    """Update is when a shipped test can newly go red, so the line must survive
    the ``if not args.update`` branch that guards the other completion advice."""
    target = _consumer(tmp_path)
    assert _install(target) == 0
    capsys.readouterr()  # discard the fresh-install output

    assert _install(target, "--update") == 0
    out = capsys.readouterr().out
    assert SHIPPED_TESTS in out
    assert f"pytest {SHIPPED_TESTS}" in out


def test_the_signpost_points_at_a_directory_the_install_really_created(tmp_path):
    """A signpost naming a path that does not arrive is worse than silence.

    The dot-directory assertion is the README's whole basis for saying a bare
    `pytest` collects none of this: pytest's default ``norecursedirs`` skips
    ``.*``, so the exclusion holds with no pytest config at all. If the engine
    ever moved out of a dotted directory, that reasoning would silently stop
    being true while the prose still claimed it.
    """
    target = _consumer(tmp_path)
    assert _install(target) == 0
    shipped = target / ".aide" / "scripts" / "tests"
    assert shipped.is_dir()
    assert list(shipped.glob("test_*.py")), "no test modules were installed"
    assert shipped.relative_to(target).parts[0].startswith(".")


def test_the_engine_readme_answers_whether_to_run_it():
    readme = CORE_README.read_text(encoding="utf-8")
    assert "`scripts/tests/`" in readme, "no row for the shipped suite"
    assert f"pytest {SHIPPED_TESTS}" in readme, "no runnable command"
    # the question the silence also left open: what to do when one goes red
    assert "--update" in readme
