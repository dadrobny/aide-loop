"""The Windows CI shards exactly cover pytest.ini's testpaths.

The workflow splits the Windows leg into one job per group of test roots
(issue #74: ~70ms per subprocess spawn makes one job ~3.5 minutes). The split
is a list of directories in .github/workflows/tests.yml, which nothing runs
against the canonical list in pytest.ini — so a test root added to testpaths
but no Windows shard, or a shard quietly moved onto another runner, would
silently stop running on Windows. These tests close that gap, both directions.
"""

import configparser
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "tests.yml"
PYTEST_INI = REPO / "pytest.ini"


def _testpaths() -> set:
    # configparser, not a regex: it folds ini continuation lines the same
    # way pytest does, so a reflow of the value cannot fail this module.
    ini = configparser.ConfigParser()
    ini.read(PYTEST_INI, encoding="utf-8")
    value = ini.get("pytest", "testpaths", fallback="")
    assert value.split(), "pytest.ini no longer declares testpaths"
    return set(value.split())


def _matrix() -> list:
    """The (os, tests) pairs of the workflow's matrix include entries."""
    text = WORKFLOW.read_text(encoding="utf-8")
    # Comment lines may sit between os: and tests:. If an entry parses as
    # neither, say so — a dropped pair must read as a parse failure here,
    # never as a coverage failure pointing the editor at the workflow.
    pairs = re.findall(
        r'-\s*os:\s*(\S+)(?:\s*\n\s*#[^\n]*)*\s*\n\s*tests:\s*"([^"]*)"', text)
    entries = len(re.findall(r"^\s*-\s*(?:os|tests):", text, flags=re.MULTILINE))
    assert pairs and len(pairs) == entries, (
        "an os: entry in tests.yml did not parse as an (os, tests) pair; "
        "fix the entry or this module's regex before trusting the pin"
    )
    return pairs


def test_one_leg_still_runs_the_bare_pytest():
    # The empty entry is the whole-suite job — the `pytest` every doc points at.
    assert ("ubuntu-latest", "") in _matrix()


def test_windows_shards_cover_every_testpaths_root_exactly_once():
    roots = [r for os_, shard in _matrix() if os_ == "windows-latest"
             for r in shard.split()]
    assert sorted(roots) == sorted(_testpaths()), (
        "the workflow's windows-latest shards and pytest.ini's testpaths "
        "disagree; a root missing from them no longer runs on Windows at all"
    )


def test_shard_roots_exist():
    for _, shard in _matrix():
        for root in shard.split():
            assert (REPO / root).is_dir(), f"shard names a missing directory: {root}"
