"""The Windows CI shards: which test modules run on Windows, and where.

The workflow runs the whole suite once on ubuntu (a bare `pytest`) and splits
the Windows leg into shards, because a subprocess spawn costs ~13x more there
and the suite is mostly git spawns (issues #74, #358). Nothing runs the
shards' argument lists against pytest.ini's testpaths — so a module no shard
reaches, a module two shards run, or a skip list edited on one side only would
pass silently. These tests close that gap, in both directions: every test
module under testpaths runs in exactly one Windows shard unless it is in
UBUNTU_ONLY below, and every UBUNTU_ONLY module is skipped by every Windows job
and run by the ubuntu one.

Which side a test module lands on
---------------------------------
The Windows leg exists for what differs there — path and encoding work (issues
#29, #34, #126). The default for every module, new or old, is **both legs**:
not listed below, it is picked up by the shard that names every testpaths
root. A module joins UBUNTU_ONLY only when all three hold for every test in it:

1. **No path text.** No test asserts on the text of a path the engine renders,
   relativises, compares, quotes or passes on (separators, drive letters, a
   space or non-ASCII byte in a name, a root below git's top level), nor hands
   the engine such text to parse. Opening a pathlib path the test built is not
   path text: pathlib is the same code on both legs.
2. **No bytes beyond the text.** No test asserts on a BOM, a line ending,
   `core.autocrlf`, a codec, or file contents compared as bytes.
3. **No launch but git.** No test has the engine start anything except git —
   an interpreter, a venv, a test command, `gh` or any other PATH lookup — or
   asserts on signals or file modes.

Fixture setup is not what a module tests: every module builds repositories
under tmp_path, writes UTF-8 files and runs git, and the modules on both legs
already carry that on Windows. Three things keep a module on both legs
whatever it contains: a module Windows CI has caught a bug in (`git log -i
--grep windows`, the CHANGELOG); `tests/test_fixture_consumer.py`, where verb
behaviour belongs "on both matrix legs" (CLAUDE.md); and doubt. A module that
is mostly git logic with a few tests failing a condition stays on both legs
whole — moving those tests into a module of their own is the way to list the
rest.

Listing is deliberate: UBUNTU_ONLY is the one declaration, each entry with the
reason it meets the rule, and the workflow's `UBUNTU_ONLY` env must name
exactly these files — a module cannot join or leave the Windows leg without an
edit here. A list and not a pytest marker because `core/scripts/tests/` ships
to every consumer as `.aide/scripts/tests/`, where a custom mark is
unregistered: a warning per module, and a collection error under the
consumer's `--strict-markers`. Only this repository's CI splits the suite, so
the split lives in this repository's CI.
"""

import configparser
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "tests.yml"
PYTEST_INI = REPO / "pytest.ini"

#: Test modules the Windows jobs skip, as repo-relative POSIX paths, each with
#: the reason it meets the rule in the module docstring.
UBUNTU_ONLY = {
    "core/scripts/tests/test_aide_base.py":
        "which base claim, merge, scope and gc read: asserts refs, recorded "
        "bases and counts; no path text, no bytes, no launch but git. Its one "
        "Windows-grep hit (d829185, #126) moved its own git helper to "
        "encoding=\"utf-8\" in a codec sweep; Windows caught nothing here",
    "core/scripts/tests/test_aide_queue_pr.py":
        "queue pr / queue ready and the CI rollup: `_gh` is a stand-in in "
        "every test; asserts refs, forge calls and exit codes",
    "core/scripts/tests/test_aide_restack.py":
        "queue restack: asserts the commit graph, recorded bases and exit "
        "codes; its hook and signer tests exercise git's launches, not the "
        "engine's",
}

#: The one step that runs the suite: the matrix's arguments, plus the skip
#: list on Windows only — so the ubuntu job, with `tests: ""`, is bare pytest.
RUN = "pytest ${{ matrix.tests }} ${{ runner.os == 'Windows' && env.UBUNTU_ONLY || '' }}"

# pytest's default norecursedirs, which pytest.ini does not override.
_NORECURSE = re.compile(r"^(\..*|.*\.egg|_darcs|build|CVS|dist|node_modules|venv|\{arch\}|__pycache__)$")


def _testpaths() -> list:
    # configparser, not a regex: it folds ini continuation lines the same
    # way pytest does, so a reflow of the value cannot fail this module.
    ini = configparser.ConfigParser()
    ini.read(PYTEST_INI, encoding="utf-8")
    value = ini.get("pytest", "testpaths", fallback="")
    assert value.split(), "pytest.ini no longer declares testpaths"
    return value.split()


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _matrix() -> list:
    """The workflow's matrix include entries, as {os, shard, tests} dicts.

    A `tests:` value is double-quoted and may fold over several lines. If an
    entry parses as anything else, say so — a dropped entry must read as a
    parse failure here, never as a coverage failure pointing the editor at the
    workflow.
    """
    text = _workflow()
    start, end = text.find("\n        include:\n"), text.find("\n    runs-on:")
    assert 0 <= start < end, "tests.yml has no matrix include: block before runs-on:"
    block = "\n".join(line for line in text[start:end].splitlines()
                      if not line.lstrip().startswith("#"))
    chunks = re.split(r"\n\s*-\s+(?=os:)", block)[1:]
    entries = []
    for chunk in chunks:
        os_ = re.search(r"^os:\s*(\S+)\s*$", chunk, flags=re.MULTILINE)
        shard = re.search(r"^\s*shard:\s*(\S[^\n]*)$", chunk, flags=re.MULTILINE)
        tests = re.search(r'^\s*tests:\s*"([^"]*)"\s*$', chunk, flags=re.MULTILINE)
        assert os_ and shard and tests, (
            f"a matrix entry in tests.yml did not parse as os/shard/tests: "
            f"{chunk.strip()!r}; fix the entry or this module's parser before "
            f"trusting the pin")
        entries.append({"os": os_.group(1), "shard": shard.group(1).strip(),
                        "tests": tests.group(1).split()})
    listed = len(re.findall(r"^\s*-\s*os:", block, flags=re.MULTILINE))
    assert entries and len(entries) == listed, (
        "an os: entry in tests.yml did not parse; fix the entry or this "
        "module's parser before trusting the pin")
    return entries


def _windows_shards() -> list:
    return [e for e in _matrix() if e["os"] == "windows-latest"]


def _env_ubuntu_only() -> list:
    """The paths the workflow's `UBUNTU_ONLY` env value --ignore's."""
    keys = re.findall(r"^[ \t]*UBUNTU_ONLY:", _workflow(), flags=re.MULTILINE)
    assert len(keys) == 1, (
        f"tests.yml sets UBUNTU_ONLY {len(keys)} times; a second value (a "
        "step-level override, say) would decide what Windows skips unpinned")
    match = re.search(r"^([ \t]*)UBUNTU_ONLY:[ \t]*>-[ \t]*\n((?:\1[ \t]+\S[^\n]*\n)+)",
                      _workflow(), flags=re.MULTILINE)
    assert match, ("tests.yml has no `UBUNTU_ONLY: >-` block of indented lines; "
                   "fix the workflow or this module's parser before trusting the pin")
    tokens = match.group(2).split()
    bad = [t for t in tokens if not t.startswith("--ignore=")]
    assert not bad, f"UBUNTU_ONLY in tests.yml carries a non---ignore token: {bad}"
    return [t[len("--ignore="):] for t in tokens]


def _split_args(tokens: list) -> tuple:
    """(positional paths, --ignore'd paths) of one shard's pytest arguments."""
    positional, ignored = [], []
    for token in tokens:
        if token.startswith("--ignore="):
            ignored.append(token[len("--ignore="):])
        else:
            assert not token.startswith("-"), (
                f"a shard passes {token!r}, an option this module does not read; "
                "teach it the option before trusting the pin")
            positional.append(token)
    return positional, ignored


def _modules_under(rel: str) -> set:
    """Repo-relative POSIX paths of the test modules pytest collects at *rel*."""
    path = REPO / rel
    if path.is_file():
        return {path.relative_to(REPO).as_posix()}
    found = set()
    for candidate in path.rglob("*.py"):
        parts = candidate.relative_to(path).parts
        if any(_NORECURSE.match(part) for part in parts[:-1]):
            continue
        name = candidate.name
        if name.startswith("test_") or name.endswith("_test.py"):
            found.add(candidate.relative_to(REPO).as_posix())
    return found


def _all_modules() -> set:
    return set().union(*(_modules_under(root) for root in _testpaths()))


def test_one_leg_still_runs_the_bare_pytest():
    # The empty entry is the whole-suite job — the `pytest` every doc points
    # at — and the run step appends the skip list on Windows only.
    ubuntu = [e for e in _matrix() if e["os"] == "ubuntu-latest"]
    assert [e["tests"] for e in ubuntu] == [[]], (
        "the matrix no longer has exactly one ubuntu-latest entry with tests: \"\"")
    assert re.findall(r"^\s*-\s*run:\s*(pytest\b[^\n]*?)\s*$", _workflow(),
                      flags=re.MULTILINE) == [RUN], (
        f"the workflow's pytest step is no longer exactly `{RUN}` — the ubuntu "
        "job would stop being the bare pytest, or a Windows job would stop "
        "skipping UBUNTU_ONLY")


def test_every_other_entry_is_a_windows_shard():
    others = {e["os"] for e in _matrix() if e["os"] != "ubuntu-latest"}
    assert others == {"windows-latest"}, (
        f"a matrix entry runs on {others - {'windows-latest'} or 'nothing'}; "
        "the shards this module pins are the windows-latest ones")


def test_the_workflow_skips_exactly_the_modules_listed_here():
    env = _env_ubuntu_only()
    assert len(env) == len(set(env)), f"UBUNTU_ONLY in tests.yml repeats a path: {env}"
    assert set(env) == set(UBUNTU_ONLY), (
        "tests.yml's UBUNTU_ONLY and this module's UBUNTU_ONLY disagree — "
        f"only in the workflow: {sorted(set(env) - set(UBUNTU_ONLY))}; "
        f"only here: {sorted(set(UBUNTU_ONLY) - set(env))}. Listing a module "
        "is deliberate: edit both, with its reason here")


def test_every_ubuntu_only_module_is_a_test_module_with_a_reason():
    modules = _all_modules()
    for rel, reason in UBUNTU_ONLY.items():
        assert rel in modules, f"UBUNTU_ONLY names {rel}, which is no test module under testpaths"
        assert reason.strip(), f"UBUNTU_ONLY lists {rel} without the reason it meets the rule"
    assert "tests/test_fixture_consumer.py" not in UBUNTU_ONLY, (
        "verb behaviour belongs in test_fixture_consumer.py on both matrix legs")


def test_every_module_runs_in_exactly_one_windows_shard():
    seen = {}
    for entry in _windows_shards():
        positional, ignored = _split_args(entry["tests"])
        named_skips = sorted(set(positional) & set(UBUNTU_ONLY))
        assert not named_skips, (
            f"shard {entry['shard']!r} names {named_skips}, which UBUNTU_ONLY skips")
        # A file named on the command line runs even when --ignore'd too, so
        # a shard that does both is read here the way pytest reads it: never.
        both = sorted(set(positional) & set(ignored))
        assert not both, (
            f"shard {entry['shard']!r} both names and --ignores {both}; pytest "
            "runs a named file regardless")
        runs = set().union(*(_modules_under(p) for p in positional)) if positional else set()
        runs -= set().union(*(_modules_under(p) for p in ignored)) if ignored else set()
        runs -= set(UBUNTU_ONLY)
        for rel in runs:
            seen.setdefault(rel, []).append(entry["shard"])
    expected = _all_modules() - set(UBUNTU_ONLY)
    missing = sorted(expected - set(seen))
    twice = {rel: shards for rel, shards in seen.items() if len(shards) > 1}
    stray = sorted(set(seen) - expected)
    assert not missing, (
        f"no Windows shard runs {missing}; a module off the Windows leg must be "
        "listed in UBUNTU_ONLY, deliberately")
    assert not twice, f"more than one Windows shard runs {twice}"
    assert not stray, f"a Windows shard runs {stray}, outside pytest.ini's testpaths"


def test_one_windows_shard_names_every_testpaths_root():
    # So a new module lands on the Windows leg with no edit to the workflow.
    roots = set(_testpaths())
    catch_all = [e["shard"] for e in _windows_shards()
                 if roots <= set(_split_args(e["tests"])[0])]
    assert len(catch_all) == 1, (
        f"expected exactly one Windows shard naming every testpaths root "
        f"{sorted(roots)}, found {catch_all}")


def test_shard_arguments_exist():
    for entry in _windows_shards():
        positional, ignored = _split_args(entry["tests"])
        for rel in positional + ignored:
            assert (REPO / rel).exists(), (
                f"shard {entry['shard']!r} names a missing path: {rel}")
