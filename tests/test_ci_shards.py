"""The Windows CI shards exactly cover pytest.ini's testpaths.

The workflow splits the Windows leg into one job per group of test roots
(issue #74: ~70ms per subprocess spawn makes one job ~3.5 minutes). The split
is a list of directories in .github/workflows/tests.yml, which nothing runs
against the canonical list in pytest.ini — so a test root added to testpaths
but no shard would silently stop running on Windows. These tests close that
gap, both directions.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "tests.yml"
PYTEST_INI = REPO / "pytest.ini"


def _testpaths() -> set:
    m = re.search(r"^testpaths\s*=\s*(.+)$", PYTEST_INI.read_text(encoding="utf-8"),
                  flags=re.MULTILINE)
    assert m, "pytest.ini no longer declares testpaths"
    return set(m.group(1).split())


def _shards() -> list:
    """The quoted `tests:` values of the workflow's matrix entries."""
    entries = re.findall(r'^\s*tests:\s*"([^"]*)"\s*$',
                         WORKFLOW.read_text(encoding="utf-8"), flags=re.MULTILINE)
    assert entries, "tests.yml no longer has quoted matrix `tests:` entries"
    return entries


def test_one_leg_still_runs_the_bare_pytest():
    # The empty entry is the whole-suite job — the `pytest` every doc points at.
    assert "" in _shards()


def test_shards_cover_every_testpaths_root_exactly_once():
    roots = [r for shard in _shards() if shard for r in shard.split()]
    assert sorted(roots) == sorted(_testpaths()), (
        "the workflow's Windows shards and pytest.ini's testpaths disagree; "
        "a root missing from the shards no longer runs on Windows at all"
    )


def test_shard_roots_exist():
    for shard in _shards():
        for root in shard.split():
            assert (REPO / root).is_dir(), f"shard names a missing directory: {root}"
