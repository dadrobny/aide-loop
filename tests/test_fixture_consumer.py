"""Drive a real installed engine, in a real git repo, through the loop verbs.

The gap this closes (issue #56): every other test in this repository exercises
the framework's *source* layout. Nothing exercised the thing a consumer
actually runs — `core/` copied to `.aide/`, inside someone else's repository,
driven by verbs that shell out to git. `CLAUDE.md` said so plainly, and pointed
at a manual `install.py --update` plus a human reading the diff.

Closed #29 is the record of what that costs: four CI-only failures reached a
consumer's `main`, every one caught by a human reading the Actions tab rather
than by a gate. The CI matrix here already runs ubuntu and windows, so these
tests need no new infrastructure — they are `pytest` picking up files under
`tests/`.

Asserted on **exit codes and effects**, never prose: a message is free to be
reworded, but `claim` must create a branch, `scope` must exit 1 out of bounds,
and `merge` must land the work.

The engine is loaded from the installed `.aide/scripts/aide.py` and driven
through `main()`, not through a subprocess — conventions.md §6, and the same
rule the engine's own `cli_subprocess_test_warnings` enforces on consumers.
"""
from __future__ import annotations

import codecs
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)


# --------------------------------------------------------------------------- #
# the adapter's delivered files, at their source — the delivery mechanism
# ADAPTER-SPEC §7 makes conformant: the rules, and the section skills (a
# `SKILL.md` with `user-invocable: false`, preloaded by role — issue #85).
# `adapters/claude/tests/test_rules.py` reads this repo's tree and asserts the
# strings "rules" and "skills" are in `install.ADAPTER_CONTROL`; that is a
# check on a tuple literal, not on an install (issue #83). Derived, never
# hard-coded, so a file added or renamed is covered the moment it lands.
# --------------------------------------------------------------------------- #
SOURCE_RULES = sorted((FRAMEWORK_ROOT / "adapters" / "claude" / "rules").glob("*.md"))


def _frontmatter(path: Path):
    """The file's YAML block, read the way a runtime reads it — or ``None``.

    Bytes first, then `utf-8-sig` and CRLF normalisation: an install that
    rewrote the file — a BOM prepended, native line endings — leaves the
    delimiter unrecognised. For a rule that silently makes a scoped one
    unscoped, loaded into every context; for a section skill it loses the
    `name:` a preload resolves, so the skill reaches nobody. Nothing errors
    either way.
    """
    text = path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    return None if end == -1 else text[4:end]


#: `user-invocable: false` as a frontmatter *scalar*, matched the way the two
#: sibling modules match it: case-folded, and tolerant of trailing space. A
#: plain `"user-invocable: false" in block` would read `False` — valid YAML,
#: and still a section skill to `test_rules.py` — as a workflow skill, and this
#: module's checks on it would vanish rather than fail.
_HIDDEN = re.compile(r"^user-invocable:[ \t]*false[ \t]*$", re.M | re.I)


def _is_section_skill(path: Path) -> bool:
    """The same signal `adapters/claude/tests/test_rules.py` and
    `tests/test_structural_budget.py` recognise — `user-invocable: false`, and
    since 1.42.0 only that. A `<!-- pins:` block is no longer sufficient: a
    workflow skill may quote the contract it acts on, and the checks below —
    `paths:`, a hidden frontmatter, a resolvable preload name — are a section
    skill's, not a quoting skill's. One recognition here and another there
    would let a skill drop out of these checks silently, so the three stay
    identical, spelling included."""
    return bool(_HIDDEN.search(_frontmatter(path) or ""))


#: The skills that deliver a contract section, recognised structurally so the
#: checks below are on whatever is a section skill today rather than on a
#: list that goes stale.
SOURCE_SECTION_SKILLS = [
    p for p in sorted((FRAMEWORK_ROOT / "adapters" / "claude" / "skills").glob("*/SKILL.md"))
    if _is_section_skill(p)]

#: The two `paths:`-scoped rules 1.22.0–1.26.0 shipped and 1.27.0 retired in
#: favour of the section skills above (issue #85). Every consumer installed
#: before the manifest existed still has them, and nothing but
#: `RETIRED_ADAPTER_PATHS` can remove them.
RETIRED_RULES = (".claude/rules/aide-living-documents.md",
                 ".claude/rules/aide-test-hygiene.md")


# --------------------------------------------------------------------------- #
# the minimum living documents — one stage, one queue, two items, one spec
# --------------------------------------------------------------------------- #
PROGRESS = """\
# Fixture — Progress

> Derived from the roadmap; the single record of what has shipped.

## Stage summary

| Stage | Title | Objectives | Status |
|-------|-------|-----------|--------|
| 1 | Foundations | G1 | 🚧 |

## Objective coverage

| Objective | Delivered by | Status |
|-----------|--------------|--------|
| G1 Foundations | Stage 1 | 🚧 |

## Stage 1 — Foundations — 🚧

**Deliverables.**
- 📋 The greeter. *(Item 001)*
- 📋 The farewell. *(Item 002)*

**Acceptance.**
- [ ] Both items land.
"""

QUEUE = """\
# Fixture — Work Queue 001

> **Status:** Live · **Created:** 2026-08-24

### Item 001: The greeter
A greeting function.

### Item 002: The farewell
A farewell function.
"""

SPEC_001 = """\
# Item 001 — The greeter

> **Created:** 2026-08-24 · status tracked in [`progress.md`](../progress.md)
> **Stage:** 1 — Foundations

## Description

A greeting function.

## Assumptions

- The project has a `src/` package.

## Authorised paths

**May change:**

- `src/greeter.py` — the function itself
- `tests/test_greeter.py` — its tests

## Acceptance Criteria

- [ ] AC1: `greet("x")` returns `"hello x"`.
"""


INSIGHTS = """\
# Insight Inbox

_Entries below, newest last._

- [x] framework — the inbox has no verb *(item 001, 2026-01-09)* → aide-loop #52
  - **2026-01-10** → accepted into wave 3
- [ ] defect — greet() does not strip whitespace *(item 001, 2026-08-20)*
- [ ] gap — nothing checks the farewell *(2026-08-21)*
"""


def _git(args, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), check=check,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          encoding="utf-8")


def _branch(repo: Path) -> str:
    return _git(["rev-parse", "--abbrev-ref", "HEAD"], repo).stdout.strip()


def _branches(repo: Path) -> list:
    out = _git(["branch", "--format=%(refname:short)"], repo).stdout
    return [l.strip() for l in out.splitlines() if l.strip()]


# --------------------------------------------------------------------------- #
# fixtures — install once, copy per test
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def prototype(tmp_path_factory) -> Path:
    """A genuinely installed, scaffolded, committed consumer.

    Built once: the install is ~700 KB and every test wants its own mutable
    git repo, so copying the finished tree is far cheaper than re-installing.
    `git.mode = "local"` because the default (`auto-merge`) reaches for a
    remote; the modes that need one build their own origin below.
    """
    target = tmp_path_factory.mktemp("prototype") / "consumer"
    target.mkdir()
    assert install.main(["--into", str(target), "--yes",
                         "--git-mode", "local", "--name", "Fixture"]) == 0

    ddir = target / "docs" / "aide"
    (ddir / "queue").mkdir(parents=True)
    (ddir / "items").mkdir(parents=True)
    (ddir / "progress.md").write_text(PROGRESS, encoding="utf-8")
    (ddir / "queue" / "queue-001.md").write_text(QUEUE, encoding="utf-8")
    (ddir / "items" / "001-the-greeter.md").write_text(SPEC_001, encoding="utf-8")
    (ddir / "insights.md").write_text(INSIGHTS, encoding="utf-8")
    (target / "src").mkdir()
    (target / "tests").mkdir()

    _git(["init", "-b", "main"], target)
    _git(["config", "user.email", "fixture@example.com"], target)
    _git(["config", "user.name", "Fixture"], target)
    _git(["add", "-A"], target)
    _git(["commit", "-m", "init"], target)
    return target


@pytest.fixture(scope="session")
def aide(prototype: Path):
    """The engine as a CONSUMER runs it — loaded from `.aide/scripts/`.

    Deliberately not `core/scripts/aide.py`: the point of this module is that
    the installed copy, at the path a consumer executes, is the thing under
    test. `--repo` makes one loaded module able to drive every fixture repo.
    """
    path = prototype / ".aide" / "scripts" / "aide.py"
    spec = importlib.util.spec_from_file_location("aide_installed", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture
def consumer(prototype: Path, tmp_path: Path) -> Path:
    dst = tmp_path / "consumer"
    shutil.copytree(prototype, dst)
    return dst


def _claim(aide, repo: Path, *extra: str) -> int:
    return aide.main(["--repo", str(repo), "claim", *extra])


def _commit(repo: Path, message: str) -> None:
    _git(["add", "-A"], repo)
    _git(["commit", "-m", message], repo)


def _do_the_work(repo: Path) -> None:
    """Write exactly what item 001's spec authorises, and commit it."""
    (repo / "src" / "greeter.py").write_text(
        'def greet(name):\n    return f"hello {name}"\n', encoding="utf-8")
    (repo / "tests" / "test_greeter.py").write_text(
        "def test_greet():\n    assert True\n", encoding="utf-8")
    _commit(repo, "feat: greeter")


def _land_by_squash(repo: Path, branch: str) -> None:
    """Land *branch* on main as GitHub's "Squash and merge" does — content on
    main, tip no ancestor of it. The shape `gc` reaches for `-D` to cope with."""
    _git(["switch", "main"], repo)
    _git(["merge", "--squash", branch], repo)
    _git(["commit", "-m", f"squash {branch}"], repo)


# --------------------------------------------------------------------------- #
# install — a complete, coherent tree at the paths a consumer executes
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("rel", [
    ".aide/VERSION",
    ".aide/adapter-manifest.txt",
    ".aide/scripts/aide.py",
    ".aide/conventions.md",
    ".aide/AGENT-CONTEXT.md",
    ".aide/templates/item.md",
    ".claude/settings.json",
    "aide.toml",
    "CLAUDE.md",
    ".gitignore",
])
def test_the_install_puts_every_load_bearing_file_where_a_consumer_looks(
        prototype: Path, rel: str):
    assert (prototype / rel).is_file(), f"{rel} missing from a real install"


def test_the_installed_version_matches_the_framework(prototype: Path):
    installed = (prototype / ".aide" / "VERSION").read_text(
        encoding=install.CONSUMER_ENCODING).strip()
    source = (FRAMEWORK_ROOT / "core" / "VERSION").read_text(encoding="utf-8").strip()
    assert installed == source


def test_check_reports_a_fresh_install_as_up_to_date(prototype: Path, capsys):
    assert install.main(["--into", str(prototype), "--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_check_reports_an_older_install_as_behind(consumer: Path, capsys):
    (consumer / ".aide" / "VERSION").write_text("0.0.1\n", encoding="utf-8")
    assert install.main(["--into", str(consumer), "--check"]) == 1
    assert "BEHIND" in capsys.readouterr().out


def test_update_leaves_the_project_owned_documents_alone(consumer: Path):
    """The property `--update` exists to guarantee, checked against a real tree
    rather than inferred from the code path."""
    before = (consumer / "docs" / "aide" / "progress.md").read_text(encoding="utf-8")
    toml_before = (consumer / "aide.toml").read_text(encoding="utf-8")
    assert install.main(["--into", str(consumer), "--update"]) == 0
    assert (consumer / "docs" / "aide" / "progress.md").read_text(encoding="utf-8") == before
    assert (consumer / "aide.toml").read_text(encoding="utf-8") == toml_before


def test_an_overlay_is_regenerated_into_settings_on_update(consumer: Path):
    """The one settings path that reconciles automatically. A consumer that
    adopted an overlay must receive framework updates AND keep its additions."""
    overlay = consumer / ".claude" / "settings.overlay.json"
    overlay.write_text('{"add": {"env": {"FIXTURE_MARKER": "1"}}}', encoding="utf-8")
    assert install.main(["--into", str(consumer), "--update"]) == 0
    merged = (consumer / ".claude" / "settings.json").read_text(
        encoding=install.CONSUMER_ENCODING)
    assert "FIXTURE_MARKER" in merged
    assert "permissions" in merged  # the framework base survived the merge


# --------------------------------------------------------------------------- #
# .claude/rules/ and the section skills — the contract's delivery mechanism,
# at the paths that load it
# --------------------------------------------------------------------------- #
def test_the_source_tree_has_delivered_files_to_check():
    """Fails closed. Both lists below are derived from the source tree, so an
    empty one makes its parametrised test vanish with a green suite rather than
    fail — the exact silence the rest of this block exists to break."""
    assert SOURCE_RULES, "no adapters/claude/rules/*.md — the layout moved"
    assert SOURCE_SECTION_SKILLS, ("no adapters/claude/skills/*/SKILL.md carries "
                                   "`user-invocable: false` — no section skill at source")


def test_the_install_delivers_every_rule_and_no_others(prototype: Path):
    """The directory reaches a consumer whole. A `copy_tree` that skipped it
    under some condition, a `_skip()` predicate that grew a rule, or a rename
    that updated `ADAPTER_CONTROL` and nothing else all ship a consumer with no
    contract in context, and every check in the suite still passes."""
    installed = sorted(p.name for p in (prototype / ".claude" / "rules").glob("*.md"))
    assert installed == sorted(p.name for p in SOURCE_RULES)


@pytest.mark.parametrize("source", SOURCE_RULES, ids=lambda p: p.name)
def test_a_rule_reaches_the_consumer_byte_for_byte(prototype: Path, source: Path):
    installed = prototype / ".claude" / "rules" / source.name
    assert installed.is_file(), f"{source.name} never reached .claude/rules/"
    assert installed.read_bytes() == source.read_bytes()


@pytest.mark.parametrize("source", SOURCE_SECTION_SKILLS, ids=lambda p: p.parent.name)
def test_a_section_skill_is_still_preloadable_after_the_copy(prototype: Path, source: Path):
    """A preload resolves `name:` from the frontmatter, and the copy is the one
    place a re-encode would show up — `test_rules.py` only ever reads the
    source tree, where the frontmatter is trivially intact. A BOM in front of
    `---` leaves no readable name, so the skill is skipped at spawn and absent
    from the listing: the section reaches nobody, silently."""
    name = source.parent.name
    path = prototype / ".claude" / "skills" / name / "SKILL.md"
    assert path.is_file(), f"{name}: never reached .claude/skills/"
    assert path.read_bytes() == source.read_bytes()
    raw = path.read_bytes()
    assert not raw.startswith(codecs.BOM_UTF8), f"{name}: the install added a BOM"
    assert raw.startswith(b"---"), f"{name}: no frontmatter delimiter at byte 0"
    block = _frontmatter(path)
    assert block is not None, f"{name}: frontmatter does not parse after the copy"
    assert f"name: {name}" in block, f"{name}: lost the `name:` a preload resolves"
    assert "user-invocable: false" in block, f"{name}: lost `user-invocable: false`"
    assert "paths:" in block, f"{name}: lost its `paths:`"


def test_the_retired_rules_are_not_installed_and_are_listed_for_retirement(prototype: Path):
    """Both halves of the 1.27.0 swap, at the install: neither retired rule
    reaches a fresh consumer, and each is in the bootstrap list that removes
    it from an old one. One half without the other is either double delivery
    (the rule still ships) or a consumer that keeps it forever (the list
    forgot it)."""
    for rel in RETIRED_RULES:
        assert not (prototype / rel).exists(), f"{rel}: a retired rule still ships"
        assert rel in install.RETIRED_ADAPTER_PATHS["claude"], (
            f"{rel}: not in RETIRED_ADAPTER_PATHS — a pre-manifest consumer keeps it")


def test_update_adds_the_rules_directory_to_a_consumer_that_never_had_one(
        consumer: Path):
    """The actual upgrade path: `rules/` post-dates every install made before
    it, so for most consumers `--update` is the only thing that can create it."""
    shutil.rmtree(consumer / ".claude" / "rules")
    assert install.main(["--into", str(consumer), "--update"]) == 0
    for source in SOURCE_RULES:
        installed = consumer / ".claude" / "rules" / source.name
        assert installed.is_file(), f"{source.name} missing after --update"
        assert installed.read_bytes() == source.read_bytes()


def test_the_prune_reaches_the_engine_and_stops_before_the_rules(consumer: Path):
    """`.aide/` is framework-owned and pruned by comparison with the source;
    `.claude/` is a tree a project adds to, so it deliberately is not — a
    file there goes only when the manifest says the installer wrote it (the
    test below). That asymmetry is the kind a later refactor collapses by
    accident, taking the rules with it — so the same `--update` has to be
    seen pruning, or "the rules survived" says nothing."""
    stale = consumer / ".aide" / "conventions" / "99-not-in-the-engine.md"
    stale.write_text("dropped from a later engine\n", encoding="utf-8")
    own = consumer / ".claude" / "rules" / "project-own.md"
    own.write_text("# A rule this consumer wrote\n", encoding="utf-8")

    assert install.main(["--into", str(consumer), "--update"]) == 0

    assert not stale.exists(), "the prune did not run; the rest proves nothing"
    assert own.is_file(), "the prune crossed into .claude/ and ate a project's rule"
    for source in SOURCE_RULES:
        assert (consumer / ".claude" / "rules" / source.name).read_bytes() == \
            source.read_bytes()


def test_update_retires_the_two_paths_scoped_rules_from_a_pre_swap_consumer(
        consumer: Path, capsys):
    """Issue #85, scope item 3, at the path a consumer runs: the two rules
    every 1.22.0–1.26.0 install carries, on a consumer installed **before the
    manifest existed** (no `.aide/adapter-manifest.txt` at all), so nothing
    but `RETIRED_ADAPTER_PATHS` can name them. `--check` must name both and
    exit 1; `--update` must remove both, keep `aide-command-hygiene.md`
    byte-identical, and leave the two section skills in place — otherwise the
    consumer is delivered §6 and the §1 shapes twice, once as a rule that
    still arms on every read and once as the preload that replaced it."""
    manifest = consumer / ".aide" / install.ADAPTER_MANIFEST
    manifest.unlink()                     # what a pre-manifest consumer looks like
    retired = [consumer / Path(rel) for rel in RETIRED_RULES]
    for path in retired:
        path.write_text("---\npaths:\n  - '**/*.md'\n---\n# shipped by 1.22.0\n",
                        encoding="utf-8")
    kept = consumer / ".claude" / "rules" / "aide-command-hygiene.md"
    kept_bytes = kept.read_bytes()
    capsys.readouterr()

    assert install.main(["--into", str(consumer), "--check"]) == 1
    out = capsys.readouterr().out
    for path in retired:
        assert path.name in out, f"--check did not name {path.name}"
        assert path.is_file(), "--check must never write"

    assert install.main(["--into", str(consumer), "--update"]) == 0

    for path in retired:
        assert not path.exists(), f"{path.name} is still armed in the consumer"
    assert kept.read_bytes() == kept_bytes, "the retirement touched the unscoped rule"
    for source in SOURCE_SECTION_SKILLS:
        assert (consumer / ".claude" / "skills" / source.parent.name / "SKILL.md").is_file()
    assert manifest.is_file(), "the update left the consumer without a manifest"
    assert install.main(["--into", str(consumer), "--check"]) == 0


def test_update_retires_a_rule_the_adapter_dropped_and_keeps_the_projects_own(
        consumer: Path, capsys):
    """Issue #85, step 1, at the path a consumer runs. A rule the installer
    once wrote — recorded in `.aide/adapter-manifest.txt` — and the adapter
    no longer ships must go on `--update`, after `--check` has named it; a
    rule the project wrote into the same directory, which no manifest
    records, must not. Before the manifest, `copy_tree` never deleting meant
    the dropped rule stayed armed in every consumer and `--check` said "up
    to date"."""
    manifest = consumer / ".aide" / install.ADAPTER_MANIFEST
    assert manifest.is_file(), "the install wrote no manifest; the rest proves nothing"
    dropped = consumer / ".claude" / "rules" / "aide-dropped-by-a-later-release.md"
    dropped.write_text("---\npaths: ['**/*.md']\n---\n# retired\n", encoding="utf-8")
    manifest.write_bytes(manifest.read_bytes()
                         + b".claude/rules/aide-dropped-by-a-later-release.md\n")
    own = consumer / ".claude" / "rules" / "project-own.md"
    own.write_text("# A rule this consumer wrote\n", encoding="utf-8")
    capsys.readouterr()

    assert install.main(["--into", str(consumer), "--check"]) == 1
    assert dropped.name in capsys.readouterr().out
    assert dropped.is_file(), "--check must never write"

    assert install.main(["--into", str(consumer), "--update"]) == 0

    assert not dropped.exists(), "the retired rule is still armed in the consumer"
    assert own.is_file(), "the retirement ate a project's own rule"
    assert b"aide-dropped-by-a-later-release" not in manifest.read_bytes()
    for source in SOURCE_RULES:
        assert (consumer / ".claude" / "rules" / source.name).read_bytes() == \
            source.read_bytes()
    assert install.main(["--into", str(consumer), "--check"]) == 0


# --------------------------------------------------------------------------- #
# check — against the installed engine, on a real scaffold
# --------------------------------------------------------------------------- #
def test_check_passes_clean_on_the_scaffold(aide, consumer: Path, capsys):
    assert aide.main(["--repo", str(consumer), "check"]) == 0
    assert "OK (0 warning(s))" in capsys.readouterr().out


def _installed_template(consumer: Path) -> bytes:
    template = (consumer / ".aide" / "templates" / "insights.md").read_bytes()
    assert b"insight" in template.lower()  # recognisable before it is compared
    return template


def _drop_the_inbox(consumer: Path) -> Path:
    inbox = consumer / "docs" / "aide" / "insights.md"
    inbox.unlink()
    _commit(consumer, "a document set with no inbox")
    return inbox


def _files_in_head(repo: Path) -> list:
    """What HEAD's commit touches — posix paths, as git prints them."""
    return _git(["show", "--name-only", "--format=", "HEAD"], repo).stdout.split()


def test_check_creates_a_missing_inbox_from_the_installed_template(
        aide, consumer: Path):
    inbox = _drop_the_inbox(consumer)
    assert aide.main(["--repo", str(consumer), "check"]) == 0
    assert inbox.read_bytes() == _installed_template(consumer)
    assert _git(["status", "--porcelain"], consumer).stdout.strip() == ""
    assert _files_in_head(consumer) == ["docs/aide/insights.md"]


def test_check_leaves_an_existing_inbox_byte_for_byte(aide, consumer: Path):
    inbox = consumer / "docs" / "aide" / "insights.md"
    before = inbox.read_bytes()
    assert before != _installed_template(consumer)  # the fixture's own entries
    assert aide.main(["--repo", str(consumer), "check"]) == 0
    assert inbox.read_bytes() == before


def test_check_fails_when_the_document_set_lost_its_progress(aide, consumer: Path):
    (consumer / "docs" / "aide" / "progress.md").unlink()
    assert aide.main(["--repo", str(consumer), "check"]) == 1


def test_check_warns_on_a_root_document_missing_its_mandatory_sections(
        aide, consumer: Path, capsys):
    """Issue #86: a vision written free-hand, missing every section its
    template marks MANDATORY, used to pass `check` without a word. It must
    still pass — a warning, not an error, so an unattended run does not start
    failing over a document none of its items touch — but no longer silently."""
    (consumer / "docs" / "aide" / "vision.md").write_text(
        "# Fixture — Project Vision\n\n> **Status:** Draft\n\nProse only.\n",
        encoding="utf-8")
    assert aide.main(["--repo", str(consumer), "check"]) == 0
    out = capsys.readouterr().out
    assert "vision.md" in out
    assert "0 warning(s)" not in out


def test_check_warns_on_roadmap_progress_acceptance_drift(
        aide, consumer: Path, capsys):
    """Issue #142: the roadmap's Validation / acceptance bullets become the
    stage's Acceptance boxes, and nothing checked they still agree — a stage
    grew a fourth, load-bearing box its roadmap never had, silently. Still
    exit 0: a drifted stage may be mid-replan, and an unattended run must not
    start failing on a document set that was fine yesterday. The scaffold's
    stage has one box; a roadmap listing two bullets (plus a Target:, which is
    not a box and must not be counted) is a one-sided drop."""
    (consumer / "docs" / "aide" / "roadmap.md").write_text(
        "# Fixture — Roadmap\n\n## Stage 1 — Foundations\n\n"
        "**Validation / acceptance.**\n\n"
        "- Both items land.\n"
        "- The greeter answers politely.\n"
        "- Target: the greeter answers in under a millisecond.\n",
        encoding="utf-8")
    assert aide.main(["--repo", str(consumer), "check"]) == 0
    out = capsys.readouterr().out
    assert ("stage 1: progress.md has 1 acceptance box but roadmap.md's "
            "Validation / acceptance block lists 2 bullets") in out
    assert "0 warning(s)" not in out


def test_check_warns_when_a_bullet_authorises_more_paths_than_scope_reads(
        aide, consumer: Path, capsys):
    """Issue #119: `aide scope` reads the FIRST backtick span of a bullet's
    opening line and nothing on a continuation line, so a bullet listing two
    paths authorised one and dropped the other in silence — surfacing much
    later as a scope FAIL naming a path the spec's own prose authorised. The
    warning names the dropped span, at spec time, where splitting the bullet
    is still cheap. Still exit 0: existing specs carry the shape and an
    unattended run must not start failing on one."""
    spec = consumer / "docs" / "aide" / "items" / "001-the-greeter.md"
    spec.write_text(
        SPEC_001.replace(
            "- `src/greeter.py` — the function itself",
            "- `src/greeter.py`, `src/farewell.py` — the functions"),
        encoding="utf-8")
    assert aide.main(["--repo", str(consumer), "check"]) == 0
    out = capsys.readouterr().out
    assert "'src/farewell.py'" in out
    assert "aide scope` reads none of them" in out
    assert aide.parse_authorised_paths(spec.read_text(encoding="utf-8")).may_change == [
        "src/greeter.py", "tests/test_greeter.py"]


def test_check_queue_passes_and_names_the_unspecced_item(aide, consumer: Path, capsys):
    """Item 002 is queued with no spec — a normal mid-queue state, counted and
    reported, never a failure."""
    assert aide.main(["--repo", str(consumer), "check", "--queue", "1"]) == 0
    assert "002" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# queue start — the branch shapes that are not claims
# --------------------------------------------------------------------------- #
def test_queue_start_creates_the_queue_branch_and_records_its_base(aide, consumer: Path):
    assert aide.main(["--repo", str(consumer), "queue", "start", "1"]) == 0
    branch = "aide/queue-001"
    assert _branch(consumer) == branch
    recorded = _git(["config", "--get", f"branch.{branch}.{aide._BASE_CONFIG_KEY}"],
                    consumer).stdout.strip()
    assert recorded == "main"


def test_queue_start_specs_creates_the_specs_queue_branch(aide, consumer: Path):
    assert aide.main(["--repo", str(consumer), "queue", "start", "1", "--specs"]) == 0
    assert _branch(consumer) == "aide/specs-queue-001"


def test_a_claim_off_a_started_queue_branch_merges_back_into_it(aide, consumer: Path):
    """The whole point of the verb, through the installed engine: the item's
    base is the queue branch, so the queue still lands as one reviewed PR."""
    assert aide.main(["--repo", str(consumer), "queue", "start", "1"]) == 0
    assert _claim(aide, consumer) == 0
    recorded = _git(["config", "--get",
                     f"branch.{_branch(consumer)}.{aide._BASE_CONFIG_KEY}"],
                    consumer).stdout.strip()
    assert recorded == "aide/queue-001"


def test_queue_start_creates_a_missing_inbox_on_the_queue_branch(aide, consumer: Path):
    """`/aide-run-roadmap` and `/aide-spec-queue` reach a role from here with
    no `check` in between; the inbox must already be on the branch they use."""
    inbox = _drop_the_inbox(consumer)
    assert aide.main(["--repo", str(consumer), "queue", "start", "2"]) == 0
    assert _branch(consumer) == "aide/queue-002"
    assert inbox.read_bytes() == _installed_template(consumer)
    assert _git(["status", "--porcelain"], consumer).stdout.strip() == ""
    assert _files_in_head(consumer) == ["docs/aide/insights.md"]
    on_main = _git(["ls-tree", "-r", "--name-only", "main"], consumer).stdout
    assert "docs/aide/progress.md" in on_main  # the listing is real ...
    assert "docs/aide/insights.md" not in on_main  # ... and the base untouched


def test_queue_start_refuses_to_recreate_an_existing_branch(aide, consumer: Path):
    assert aide.main(["--repo", str(consumer), "queue", "start", "1"]) == 0
    _git(["switch", "main"], consumer)
    assert aide.main(["--repo", str(consumer), "queue", "start", "1"]) == 1


# --------------------------------------------------------------------------- #
# claim — creates the branch and records its base
# --------------------------------------------------------------------------- #
def test_claim_creates_switches_to_and_records_the_branch(aide, consumer: Path):
    assert _claim(aide, consumer) == 0
    branch = "aide/001-the-greeter"
    assert _branch(consumer) == branch
    assert branch in _branches(consumer)
    recorded = _git(["config", "--get", f"branch.{branch}.{aide._BASE_CONFIG_KEY}"],
                    consumer).stdout.strip()
    assert recorded == "main"


def test_claim_creates_a_missing_inbox_on_the_claim_branch(aide, consumer: Path):
    """`/aide-run-queue` reaches its roles through `sync` and `claim`, never
    `check` — and `sync` refuses a dirty tree, so the file must arrive
    committed, on the item's branch, before any role is spawned."""
    inbox = _drop_the_inbox(consumer)
    assert _claim(aide, consumer) == 0
    assert _branch(consumer).startswith("aide/001-")
    assert inbox.read_bytes() == _installed_template(consumer)
    assert _git(["status", "--porcelain"], consumer).stdout.strip() == ""
    assert _files_in_head(consumer) == ["docs/aide/insights.md"]
    assert aide.main(["--repo", str(consumer), "sync", "--item", "1"]) == 0


def test_dry_run_claims_nothing(aide, consumer: Path):
    assert _claim(aide, consumer, "--dry-run") == 0
    assert _branch(consumer) == "main"
    assert _branches(consumer) == ["main"]


def test_claim_skips_an_item_already_marked_done(aide, consumer: Path):
    assert aide.main(["--repo", str(consumer), "progress", "set", "1", "done"]) == 0
    assert _claim(aide, consumer) == 0
    assert _branch(consumer) == "aide/002-the-farewell"


def test_a_prose_mention_on_a_done_bullet_leaves_the_sibling_claimable(
        aide, consumer: Path):
    """Issue #99 at verb level. Item 001's bullet mentions live item 002 in
    its prose; when 001 goes done, only the trailing marker attributes, so 002
    must stay planned — the queue stays open and `claim` takes 002 — instead
    of the ✅ sentence silently marking the sibling complete and closing the
    queue over unbuilt work."""
    ppath = consumer / "docs" / "aide" / "progress.md"
    ppath.write_text(ppath.read_text(encoding="utf-8").replace(
        "- 📋 The greeter. *(Item 001)*",
        "- 📋 The greeter, absorbing *(Item 002)*'s parser. *(Item 001)*"),
        encoding="utf-8")
    _commit(consumer, "docs: mention the sibling in prose")
    assert aide.main(["--repo", str(consumer), "progress", "set", "1", "done"]) == 0
    assert _claim(aide, consumer) == 0
    assert _branch(consumer) == "aide/002-the-farewell"


def test_an_exhausted_queue_is_no_longer_open_to_claim_from(aide, consumer: Path, capsys):
    """Every item ✅ makes the queue closed, not empty — so `claim` exits 1 and
    says there is no open queue. That non-zero exit is what stops
    /aide-run-queue rather than letting it spin."""
    for n in ("1", "2"):
        assert aide.main(["--repo", str(consumer), "progress", "set", n, "done"]) == 0
    capsys.readouterr()
    assert _claim(aide, consumer) == 1
    assert "no open queue" in capsys.readouterr().err
    assert _branch(consumer) == "main"


def test_a_maintenance_queue_is_served_before_the_stage_queue_behind_it(
        aide, consumer: Path):
    """The engine property #160's split rests on, exercised rather than assumed.

    `/aide-create-queue` may now write **two** queues from one call: a
    maintenance queue of the insight-derived fixes, then the stage queue after
    it. Nothing new records which of the two is live — the claim is simply
    that "the live queue is the lowest-numbered open one" already produces the
    ordering, so the fixes merge first and every other branch rebases onto
    them early. That makes the whole design one assertion deep, and this is
    it: with both queues open, `claim` takes the maintenance queue's item, and
    only reaches the stage queue when the maintenance queue is exhausted.
    """
    ddir = consumer / "docs" / "aide"
    (ddir / "queue" / "queue-002.md").write_text(
        "# Fixture — Work Queue 002 (maintenance)\n\n"
        "### Item 003: Strip the greeting whitespace\n"
        "The fix insight entry 2 asked for.\n", encoding="utf-8")
    (ddir / "queue" / "queue-003.md").write_text(
        "# Fixture — Work Queue 003\n\n"
        "### Item 004: The stage item\n"
        "The batch the roadmap was going to produce anyway.\n", encoding="utf-8")
    ppath = ddir / "progress.md"
    ppath.write_text(ppath.read_text(encoding="utf-8").replace(
        "- 📋 The farewell. *(Item 002)*",
        "- 📋 The farewell. *(Item 002)*\n"
        "- 📋 Strip the greeting whitespace. *(Item 003)*\n"
        "- 📋 The stage item. *(Item 004)*"), encoding="utf-8")
    _commit(consumer, "docs: a maintenance queue ahead of the stage queue")
    for n in ("1", "2"):
        assert aide.main(["--repo", str(consumer), "progress", "set", n, "done"]) == 0

    assert _claim(aide, consumer) == 0
    assert _branch(consumer).startswith("aide/003-"), (
        "claim reached past the maintenance queue for the stage queue behind "
        "it — the lowest-numbered-open rule is what orders the two")

    _git(["switch", "main"], consumer)
    assert aide.main(["--repo", str(consumer), "progress", "set", "3", "done"]) == 0
    assert _claim(aide, consumer) == 0
    assert _branch(consumer).startswith("aide/004-")


def test_claim_reports_none_left_when_every_open_item_is_already_claimed(
        aide, consumer: Path, capsys):
    """The queue is still open, but nothing in it is pickable. Distinct from
    the case above, and exit 0 — this is a normal end-of-batch state, not a
    failure."""
    assert aide.main(["--repo", str(consumer), "progress", "set", "2", "done"]) == 0
    assert _claim(aide, consumer) == 0          # takes 001
    capsys.readouterr()
    assert _claim(aide, consumer) == 0          # nothing left to take
    assert "none left" in capsys.readouterr().out


def test_a_failed_claim_push_is_a_sentence_and_never_none_left(
        aide, consumer: Path, tmp_path: Path, capsys):
    """#137: the push is the last thing `claim` does, so it fails *after* the
    branch exists. It used to raise `CalledProcessError` — a raw traceback in
    an unattended flow — and the next run then skipped the item as claimed and
    called the queue exhausted, exit 0, having built nothing."""
    toml = consumer / "aide.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace(
        'mode = "local"', 'mode = "auto-merge"'), encoding="utf-8")
    _commit(consumer, "chore: auto-merge mode")
    # A remote that resolves to nothing, so every push to it fails.
    _git(["remote", "add", "origin", str(tmp_path / "no-such.git")], consumer)
    capsys.readouterr()

    assert _claim(aide, consumer) == 1
    err = capsys.readouterr().err
    assert "to origin FAILED" in err
    assert "claimed LOCALLY ONLY" in err
    assert "Traceback" not in err
    # The branch is kept — the push may have reached origin before the client
    # gave up, and `git push -u origin …` is the one-line repair.
    assert _branch(consumer) == "aide/001-the-greeter"
    assert _item_status(aide, consumer, 1) != "complete"

    assert _claim(aide, consumer) == 1          # 002, and its push fails too
    capsys.readouterr()

    rc = _claim(aide, consumer)
    out = capsys.readouterr().out
    assert rc == 1                              # was 0, "none left"
    assert "2 item(s) still open" in out
    assert out.count("ORIGIN HAS NEVER SEEN") == 2


# --------------------------------------------------------------------------- #
# scope — the diff against the spec's authorised paths
# --------------------------------------------------------------------------- #
def test_scope_passes_for_a_diff_inside_the_authorised_paths(aide, consumer: Path):
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    assert aide.main(["--repo", str(consumer), "scope"]) == 0


def test_scope_fails_for_one_file_outside_them(aide, consumer: Path, capsys):
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    (consumer / "README.md").write_text("stray\n", encoding="utf-8")
    _commit(consumer, "chore: stray")
    assert aide.main(["--repo", str(consumer), "scope"]) == 1
    assert "README.md" in capsys.readouterr().out


def test_scope_cannot_check_an_unspecced_item(aide, consumer: Path):
    """Exit 2, not 1 and not 0: an undeclared spec is not an unconstrained one,
    and "could not check" must never read as "in scope"."""
    assert aide.main(["--repo", str(consumer), "scope", "2"]) == 2


def test_scope_on_main_cannot_tell_which_item_to_check(aide, consumer: Path):
    assert aide.main(["--repo", str(consumer), "scope"]) == 2


def test_scope_output_carries_no_native_separator(aide, consumer: Path, capsys):
    """The finding names a path, and on Windows a native separator here is the
    exact class of defect conventions.md §6 exists for."""
    assert _claim(aide, consumer) == 0
    (consumer / "docs" / "notes").mkdir(parents=True)
    (consumer / "docs" / "notes" / "stray.md").write_text("x\n", encoding="utf-8")
    _commit(consumer, "chore: nested stray")
    assert aide.main(["--repo", str(consumer), "scope"]) == 1
    out = capsys.readouterr().out
    assert "docs/notes/stray.md" in out and "\\" not in out


# --------------------------------------------------------------------------- #
# merge — lands per git.mode
# --------------------------------------------------------------------------- #
def test_merge_in_local_mode_lands_the_work_and_deletes_the_branch(
        aide, consumer: Path):
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    assert aide.main(["--repo", str(consumer), "merge", "1", "--no-test"]) == 0
    assert _branch(consumer) == "main"
    assert _branches(consumer) == ["main"]
    assert (consumer / "src" / "greeter.py").is_file()  # the work is ON main


def _item_status(aide, repo: Path, number: int) -> str:
    text = (repo / "docs" / "aide" / "progress.md").read_text(encoding="utf-8")
    return aide._parse_item_status(text.splitlines())[2].get(number, "planned")


def test_merge_records_the_tick_so_a_check_always_means_merged(
        aide, consumer: Path):
    """✅ is written by the process that did the merge, through the installed
    engine — so it cannot outrun the merge in any mode."""
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    assert aide.main(["--repo", str(consumer), "progress", "set", "1",
                      "in-review"]) == 0
    assert _item_status(aide, consumer, 1) == "in-review"
    assert aide.main(["--repo", str(consumer), "merge", "1", "--no-test"]) == 0
    assert _item_status(aide, consumer, 1) == "complete"


def test_a_run_under_pr_mode_never_offers_to_delete_an_open_prs_branch(
        aide, consumer: Path, capsys):
    """#71's acceptance, end to end: the queue-exhaustion sweep is safe under
    `pr` mode because the item is 🔍, not ✅ — so `gc`'s ground never matches."""
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    assert aide.main(["--repo", str(consumer), "progress", "set", "1",
                      "in-review"]) == 0
    _git(["switch", "main"], consumer)
    capsys.readouterr()
    assert aide.main(["--repo", str(consumer), "gc"]) == 0
    out = capsys.readouterr().out
    assert "would delete" not in out
    assert "aide/001-the-greeter" in _branches(consumer)
    # ...and `check` does not nag about it on every run until the human merges.
    capsys.readouterr()
    aide.main(["--repo", str(consumer), "check"])
    assert "stale claim branch" not in capsys.readouterr().out


def test_an_item_awaiting_review_keeps_its_queue_open(aide, consumer: Path, capsys):
    for n, st in (("1", "in-review"), ("2", "done")):
        assert aide.main(["--repo", str(consumer), "progress", "set", n, st]) == 0
    capsys.readouterr()
    assert aide.main(["--repo", str(consumer), "status"]) == 0
    assert "queue-001.md: open" in capsys.readouterr().out


def test_sync_points_a_landed_review_item_back_at_done(aide, consumer: Path, capsys):
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    assert aide.main(["--repo", str(consumer), "progress", "set", "1",
                      "in-review"]) == 0
    _land_by_squash(consumer, "aide/001-the-greeter")
    capsys.readouterr()
    assert aide.main(["--repo", str(consumer), "sync"]) == 0
    out = capsys.readouterr().out
    assert "item 001 is 🔍" in out
    assert "progress set 001 done" in out


def test_merge_refuses_an_item_with_no_claim_branch(aide, consumer: Path):
    assert aide.main(["--repo", str(consumer), "merge", "2", "--no-test"]) == 1


def test_merge_in_pr_mode_pushes_and_leaves_the_merge_to_a_human(
        aide, consumer: Path, tmp_path: Path, capsys):
    """`pr` mode is the human review gate. It must NOT touch main."""
    origin = tmp_path / "origin.git"
    _git(["init", "--bare", "-b", "main", str(origin)], tmp_path)
    _git(["remote", "add", "origin", str(origin)], consumer)
    _git(["push", "-u", "origin", "main"], consumer)
    toml = consumer / "aide.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace(
        'mode = "local"', 'mode = "pr"'), encoding="utf-8")
    _commit(consumer, "chore: pr mode")

    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    main_before = _git(["rev-parse", "main"], consumer).stdout.strip()
    capsys.readouterr()

    assert aide.main(["--repo", str(consumer), "merge", "1", "--no-test"]) == 0
    assert _git(["rev-parse", "main"], consumer).stdout.strip() == main_before
    assert "aide/001-the-greeter" in _branches(consumer)
    # It got pushed, so a human has something to open a PR against.
    assert "aide/001-the-greeter" in _git(
        ["branch", "--format=%(refname:short)"], origin).stdout


def _set_test_command(repo: Path, command: str) -> None:
    """Point `python.test_command` at a deterministic, dependency-free command.

    `git` rather than a python one-liner: the engine only rebinds a leading
    `python` to the project venv, the fixture has no venv, and whether a bare
    `python` resolves is the CI runner's business, not this test's. Both legs
    of the matrix have git — the module under test shells out to it constantly.
    """
    toml = repo / "aide.toml"
    text = toml.read_text(encoding="utf-8")
    old = [l for l in text.splitlines() if l.startswith("test_command = ")]
    assert len(old) == 1, "aide.toml lost its test_command line"
    toml.write_text(text.replace(old[0], f'test_command = "{command}"'),
                    encoding="utf-8")


def test_merge_refuses_a_dirty_working_tree(aide, consumer: Path):
    """#133: `switch` and `pull --rebase` are not run from an unsafe tree.

    A consumer that obeys §3 never reaches for raw git, so whatever this verb
    does unconditionally is what happens to their repository. It already
    refuses a base that would detach HEAD; this is the same class.
    """
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    (consumer / "src" / "greeter.py").write_text("half-written\n", encoding="utf-8")
    main_before = _git(["rev-parse", "main"], consumer).stdout.strip()

    assert aide.main(["--repo", str(consumer), "merge", "1", "--no-test"]) == 1
    assert _git(["rev-parse", "main"], consumer).stdout.strip() == main_before
    assert _branch(consumer) == "aide/001-the-greeter"   # it did not even switch
    assert (consumer / "src" / "greeter.py").read_text(
        encoding="utf-8") == "half-written\n"           # nor touch the edit


def test_merge_refuses_a_tree_left_mid_merge(aide, consumer: Path):
    """A real conflicted merge, not a simulated one: the state a human is
    standing in when they reach for `aide merge` again is exactly this."""
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    shared = consumer / "docs" / "aide" / "shared.md"
    shared.write_text("branch side\n", encoding="utf-8")
    _commit(consumer, "docs: branch side")
    _git(["switch", "main"], consumer)
    shared.write_text("main side\n", encoding="utf-8")
    _commit(consumer, "docs: main side")
    assert _git(["merge", "--no-edit", "aide/001-the-greeter"], consumer,
                check=False).returncode != 0
    assert (consumer / ".git" / "MERGE_HEAD").is_file()

    assert aide.main(["--repo", str(consumer), "merge", "1", "--no-test"]) == 1
    # The half-merge is still the human's to finish — nothing resolved it, and
    # nothing committed on top of it.
    assert (consumer / ".git" / "MERGE_HEAD").is_file()
    assert _item_status(aide, consumer, 1) != "complete"


def test_merge_skips_a_branch_that_has_already_landed(aide, consumer: Path):
    """#133: the merge is idempotent, so re-running the verb cannot churn.

    This is the shape that cost a consumer a hand-made conflict resolution: the
    branch was merged and only the push was missing, and the re-run reached for
    `pull --rebase` over the unpushed merge commit.
    """
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    _git(["switch", "main"], consumer)
    _git(["merge", "--no-ff", "--no-edit", "aide/001-the-greeter"], consumer)
    landed = _git(["rev-parse", "main"], consumer).stdout.strip()

    assert aide.main(["--repo", str(consumer), "merge", "1", "--no-test"]) == 0
    # No second merge commit: everything after the hand-made one is the tick.
    assert _git(["rev-list", "--merges", f"{landed}..main"],
                consumer).stdout.strip() == ""
    assert _item_status(aide, consumer, 1) == "complete"
    assert "aide/001-the-greeter" not in _branches(consumer)


def test_merge_will_not_rebase_over_an_unpushed_merge_commit(
        aide, consumer: Path, tmp_path: Path):
    """#133: `pull --rebase` drops a merge commit and replays both parents, so
    a conflict resolved by hand inside it comes back. With origin diverged the
    verb stops instead — the merge commit, and the resolution it carries, is
    still exactly where the human left it."""
    origin = tmp_path / "origin.git"
    _git(["init", "--bare", "-b", "main", str(origin)], tmp_path)
    _git(["remote", "add", "origin", str(origin)], consumer)
    _git(["push", "-u", "origin", "main"], consumer)
    toml = consumer / "aide.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace(
        'mode = "local"', 'mode = "auto-merge"'), encoding="utf-8")
    _commit(consumer, "chore: auto-merge mode")
    _git(["push"], consumer)

    # Give origin a commit this checkout does not have, so a rebase would have
    # something to replay onto...
    (consumer / "docs" / "aide" / "note.md").write_text(
        "origin side\n", encoding="utf-8")
    _commit(consumer, "docs: origin side")
    _git(["push"], consumer)
    _git(["reset", "--hard", "HEAD~1"], consumer)
    # ...and leave main carrying an unpushed merge commit, the way a resolved
    # conflict does. A previous item's landing, not this one's.
    _git(["switch", "-c", "side"], consumer)
    (consumer / "docs" / "aide" / "side.md").write_text("side\n", encoding="utf-8")
    _commit(consumer, "docs: side")
    _git(["switch", "main"], consumer)
    _git(["merge", "--no-ff", "--no-edit", "side"], consumer)
    merged = _git(["rev-parse", "main"], consumer).stdout.strip()

    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)

    assert aide.main(["--repo", str(consumer), "merge", "1", "--no-test"]) == 1
    assert _git(["rev-parse", "main"], consumer).stdout.strip() == merged
    assert _git(["rev-list", "--merges", "@{u}..HEAD"],
                consumer).stdout.strip() != ""      # still a merge, not replayed
    assert _item_status(aide, consumer, 1) != "complete"
    assert "aide/001-the-greeter" in _branches(consumer)


def test_the_post_merge_run_sees_the_refs_a_fresh_clone_would(
        aide, consumer: Path):
    """#125: the claim branch is deleted BEFORE the re-run, not after.

    The test command here succeeds exactly while the claim branch exists, so
    the merge's exit code reports what the run saw. It saw no claim branch —
    which is why a consumer's `aide check` had reported the item's own branch
    as stale against the item being merged, a failure class its acceptance
    baseline had never seen and only this ordering could produce.
    """
    _set_test_command(
        consumer, "git show-ref --verify --quiet refs/heads/aide/001-the-greeter")
    _commit(consumer, "chore: a test command that sees the claim branch")
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    assert _git(["show-ref", "--verify", "--quiet",
                 "refs/heads/aide/001-the-greeter"], consumer,
                check=False).returncode == 0        # green while the branch is there

    assert aide.main(["--repo", str(consumer), "merge", "1"]) == 1


def test_a_red_post_merge_run_blocks_the_tick_and_leaves_a_re_runnable_state(
        aide, consumer: Path):
    """#125: ✅ and the push are what a red run refuses.

    A consumer landed a red queue branch with the item marked done, because the
    run was advisory: the tick and the push had already happened by the time it
    was consulted. It is a gate now — and the state it leaves is one the same
    command can finish, which is what stops a human hand-editing the tick.
    """
    _set_test_command(consumer, "git rev-parse --verify no-such-ref")
    _commit(consumer, "chore: a failing test command")
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)

    assert aide.main(["--repo", str(consumer), "merge", "1"]) == 1
    assert _item_status(aide, consumer, 1) != "complete"
    assert (consumer / "src" / "greeter.py").is_file()     # the merge itself stands
    assert "aide/001-the-greeter" in _branches(consumer)   # and the retry has a branch

    _set_test_command(consumer, "git rev-parse --verify HEAD")
    _commit(consumer, "chore: a passing test command")
    assert aide.main(["--repo", str(consumer), "merge", "1"]) == 0
    assert _item_status(aide, consumer, 1) == "complete"
    assert "aide/001-the-greeter" not in _branches(consumer)


# --------------------------------------------------------------------------- #
# gc — deletes only what landed, and never by default
# --------------------------------------------------------------------------- #
def test_gc_is_a_dry_run_by_default(aide, consumer: Path, capsys):
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    _land_by_squash(consumer, "aide/001-the-greeter")
    assert aide.main(["--repo", str(consumer), "progress", "set", "1", "done"]) == 0
    capsys.readouterr()
    assert aide.main(["--repo", str(consumer), "gc"]) == 0
    assert "would delete" in capsys.readouterr().out
    assert "aide/001-the-greeter" in _branches(consumer)


def test_gc_refuses_a_tick_whose_branch_never_landed(aide, consumer: Path, capsys):
    """A ✅ can outrun the merge — a commit added after the validator ticked it,
    a hand-edit, the `pr`-mode window. git is the authority on whether the work
    landed, and `-D` plus a remote delete is unrecoverable on a plain git host."""
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    _git(["switch", "main"], consumer)
    assert aide.main(["--repo", str(consumer), "progress", "set", "1", "done"]) == 0
    capsys.readouterr()
    assert aide.main(["--repo", str(consumer), "gc", "--yes"]) == 0
    out = capsys.readouterr().out
    assert "skipping aide/001-the-greeter" in out
    assert "main" in out  # the skip names the base it was measured against
    assert "aide/001-the-greeter" in _branches(consumer)


def test_gc_abandon_deletes_an_unlanded_tick_on_purpose(aide, consumer: Path):
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    _git(["switch", "main"], consumer)
    assert aide.main(["--repo", str(consumer), "progress", "set", "1", "done"]) == 0
    assert aide.main(["--repo", str(consumer), "gc", "--abandon", "--yes"]) == 0
    assert "aide/001-the-greeter" not in _branches(consumer)


def test_gc_previews_exactly_the_set_it_deletes(aide, consumer: Path, capsys):
    """A preview that overstates trains the reader to skim the one list a human
    is explicitly asked to approve before the one destructive verb runs."""
    def _named(out: str) -> set:
        prefixes = ("would delete ", "deleted ")
        return {line[len(pre):].split()[0]
                for line in out.splitlines() for pre in prefixes
                if line.startswith(pre)}

    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    _land_by_squash(consumer, "aide/001-the-greeter")
    assert aide.main(["--repo", str(consumer), "progress", "set", "1", "done"]) == 0
    # Sit on the branch gc would otherwise delete: the preview must not promise it.
    _git(["switch", "aide/001-the-greeter"], consumer)
    capsys.readouterr()
    assert aide.main(["--repo", str(consumer), "gc"]) == 0
    previewed = _named(capsys.readouterr().out)
    assert aide.main(["--repo", str(consumer), "gc", "--yes"]) == 0
    assert _named(capsys.readouterr().out) == previewed
    assert "aide/001-the-greeter" in _branches(consumer)


def test_gc_yes_deletes_the_branch_of_a_landed_item(aide, consumer: Path):
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    assert aide.main(["--repo", str(consumer), "merge", "1", "--no-test"]) == 0
    # Re-create the branch merge already swept, so gc has something to find.
    _git(["branch", "aide/001-the-greeter"], consumer)
    assert aide.main(["--repo", str(consumer), "progress", "set", "1", "done"]) == 0
    assert aide.main(["--repo", str(consumer), "gc", "--yes"]) == 0
    assert "aide/001-the-greeter" not in _branches(consumer)


def test_gc_leaves_a_claim_whose_item_has_not_landed(aide, consumer: Path, capsys):
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    capsys.readouterr()
    assert aide.main(["--repo", str(consumer), "gc", "--yes"]) == 0
    assert "nothing to clean" in capsys.readouterr().out
    assert "aide/001-the-greeter" in _branches(consumer)


def test_gc_never_touches_a_branch_outside_the_prefix(aide, consumer: Path):
    """gc is the one destructive verb; it must own only what it named."""
    _git(["branch", "someone-elses-work"], consumer)
    assert aide.main(["--repo", str(consumer), "progress", "set", "1", "done"]) == 0
    assert aide.main(["--repo", str(consumer), "gc", "--yes", "--merged"]) == 0
    assert "someone-elses-work" in _branches(consumer)


# --------------------------------------------------------------------------- #
# status — reports the state this test just created
# --------------------------------------------------------------------------- #
def test_status_reports_the_branch_queue_and_claim(aide, consumer: Path, capsys):
    assert _claim(aide, consumer) == 0
    capsys.readouterr()
    assert aide.main(["--repo", str(consumer), "status"]) == 0
    out = capsys.readouterr().out
    assert "aide/001-the-greeter" in out
    assert "queue-001.md" in out
    assert "clean" in out


def test_status_sees_a_dirty_tree(aide, consumer: Path, capsys):
    (consumer / "src" / "greeter.py").write_text("x = 1\n", encoding="utf-8")
    assert aide.main(["--repo", str(consumer), "status"]) == 0
    assert "dirty" in capsys.readouterr().out


def test_status_reports_a_finished_queue_as_done(aide, consumer: Path, capsys):
    for n in ("1", "2"):
        assert aide.main(["--repo", str(consumer), "progress", "set", n, "done"]) == 0
    capsys.readouterr()
    assert aide.main(["--repo", str(consumer), "status"]) == 0
    assert "queue-001.md: done" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# insights — the inbox verbs, against the installed engine
# --------------------------------------------------------------------------- #
def test_insights_list_numbers_the_whole_inbox(aide, consumer: Path, capsys):
    assert aide.main(["--repo", str(consumer), "insights", "list"]) == 0
    out = capsys.readouterr().out
    assert "3 entries, 2 open" in out
    assert "1 defect, 1 gap" in out


def test_insights_list_open_omits_the_closed_history(aide, consumer: Path, capsys):
    assert aide.main(["--repo", str(consumer), "insights", "list", "--open"]) == 0
    out = capsys.readouterr().out
    assert "the inbox has no verb" not in out
    assert "greet() does not strip whitespace" in out


def test_insights_tick_edits_and_commits_in_the_consumer(aide, consumer: Path):
    assert aide.main(["--repo", str(consumer), "insights", "tick", "2",
                      "--pointer", "item 003", "--date", "2026-08-24"]) == 0
    text = (consumer / "docs" / "aide" / "insights.md").read_text(encoding="utf-8")
    assert "- [x] defect — greet() does not strip whitespace" in text
    assert text.rstrip().endswith("*(2026-08-21)*")  # the untouched entry below it
    assert "→ item 003" in text
    assert _git(["status", "--porcelain"], consumer).stdout.strip() == ""


def test_insights_tick_on_a_closed_entry_appends_to_its_trail(aide, consumer: Path):
    assert aide.main(["--repo", str(consumer), "insights", "tick", "1",
                      "--pointer", "shipped in 1.17.0", "--date", "2026-08-24",
                      "--no-commit"]) == 0
    lines = (consumer / "docs" / "aide" / "insights.md").read_text(
        encoding="utf-8").splitlines()
    assert lines[4] == INSIGHTS.splitlines()[4]  # the claim, unaltered
    assert lines[6] == "  - **2026-08-24** → shipped in 1.17.0"


def test_insights_archive_is_a_dry_run_until_yes(aide, consumer: Path, capsys):
    inbox = consumer / "docs" / "aide" / "insights.md"
    before = inbox.read_text(encoding="utf-8")
    assert aide.main(["--repo", str(consumer), "insights", "archive",
                      "--before", "2026-06-01"]) == 0
    assert "dry run" in capsys.readouterr().out
    assert inbox.read_text(encoding="utf-8") == before
    assert not (consumer / "docs" / "aide" / "insights").exists()


def test_insights_archive_yes_moves_only_the_closed_entry(aide, consumer: Path):
    assert aide.main(["--repo", str(consumer), "insights", "archive",
                      "--before", "2026-06-01", "--yes"]) == 0
    archive = consumer / "docs" / "aide" / "insights" / "archive-2026-Q1.md"
    assert "the inbox has no verb" in archive.read_text(encoding="utf-8")
    live = (consumer / "docs" / "aide" / "insights.md").read_text(encoding="utf-8")
    assert "the inbox has no verb" not in live
    assert "greet() does not strip whitespace" in live
    assert _git(["status", "--porcelain"], consumer).stdout.strip() == ""


def test_check_stays_clean_after_an_archive(aide, consumer: Path):
    """An archived claim is frozen — the gate must not start warning about it."""
    assert aide.main(["--repo", str(consumer), "insights", "archive",
                      "--before", "2026-06-01", "--yes"]) == 0
    assert aide.main(["--repo", str(consumer), "check"]) == 0


def test_scope_authorises_the_archive_the_verb_just_wrote(aide, consumer: Path):
    """`insights archive` is loop bookkeeping, so item 001 is not out of scope."""
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    assert aide.main(["--repo", str(consumer), "insights", "archive",
                      "--before", "2026-06-01", "--yes"]) == 0
    assert aide.main(["--repo", str(consumer), "scope", "--base", "main"]) == 0


# --------------------------------------------------------------------------- #
# insights resolve — a real two-branch conflict, resolved by the verb
# --------------------------------------------------------------------------- #
def _append_insight(repo: Path, line: str, branch: str, base: str = "main") -> None:
    """Capture one insight on its own branch, the way a role does — a plain
    append to the end of the file, and a commit."""
    _git(["switch", "-c", branch, base], repo)
    inbox = repo / "docs" / "aide" / "insights.md"
    inbox.write_text(inbox.read_text(encoding="utf-8") + line + "\n",
                     encoding="utf-8")
    _commit(repo, f"docs(aide): capture on {branch}")


_OURS = "- [ ] knowledge — utf-8-sig is the right default *(item 002, 2026-08-25)*"
_THEIRS = "- [ ] automation — the archive has no dry run *(item 003, 2026-08-26)*"


def _two_branches_that_both_appended(consumer: Path) -> None:
    """Leave *consumer* mid-merge, stopped on a genuine conflict in the inbox.

    Not a hand-written conflict: two branches each append to an append-only
    file, which is the shape §1 guarantees on every merge, and git produces the
    markers itself.
    """
    _append_insight(consumer, _OURS, "aide/insight-ours")
    _append_insight(consumer, _THEIRS, "aide/insight-theirs")
    _git(["switch", "aide/insight-ours"], consumer)
    merge = _git(["merge", "aide/insight-theirs"], consumer, check=False)
    assert merge.returncode != 0, "the append-only file did not conflict"


def test_two_appends_really_do_conflict_in_an_installed_consumer(consumer: Path):
    """The premise of the verb, asserted rather than assumed."""
    _two_branches_that_both_appended(consumer)
    text = (consumer / "docs" / "aide" / "insights.md").read_text(encoding="utf-8")
    assert "<<<<<<<" in text and ">>>>>>>" in text
    assert _git(["ls-files", "-u", "--", "docs/aide/insights.md"],
                consumer).stdout.strip()


def test_check_fails_on_the_conflict_and_names_the_verb(aide, consumer: Path, capsys):
    _two_branches_that_both_appended(consumer)
    assert aide.main(["--repo", str(consumer), "check"]) == 1
    # One read: `readouterr` clears what it returns, so a second call would
    # hand back an empty stream and quietly assert over half the output.
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "conflict marker" in out and "insights resolve" in out


def test_resolve_writes_the_union_and_stages_it(aide, consumer: Path):
    """Both captures survive, neither is reworded, and the merge can continue."""
    _two_branches_that_both_appended(consumer)
    assert aide.main(["--repo", str(consumer), "insights", "resolve"]) == 0

    inbox = consumer / "docs" / "aide" / "insights.md"
    text = inbox.read_text(encoding="utf-8")
    assert "<<<<<<<" not in text
    # Every claim the two branches held, byte-for-byte, in capture order.
    assert [e.raw for e in aide.parse_insights(text)] == [
        line for line in INSIGHTS.splitlines() if line.startswith("- ")
    ] + [_OURS, _THEIRS]
    # Staged, so the conflict is marked resolved and the merge can finish.
    assert not _git(["ls-files", "-u", "--", "docs/aide/insights.md"],
                    consumer).stdout.strip()
    _git(["commit", "--no-edit"], consumer)
    assert aide.main(["--repo", str(consumer), "check"]) == 0
    assert _git(["status", "--porcelain"], consumer).stdout.strip() == ""


def test_resolve_stages_a_conflict_that_has_no_merge_base_at_all(
        aide, consumer: Path):
    """An add/add conflict — both branches created the inbox — leaves stages 2
    and 3 in the index and **no stage 1**: there is no base, because the path
    exists on neither parent. Reading "is this unmerged?" off the merge base
    therefore answered no about a genuinely unmerged file, the verb silently
    skipped staging, and the next `git commit` died on unmerged files.

    (A consumer whose inbox came from `.aide/templates/insights.md` usually
    keeps a base anyway — git's rename detection matches the created file
    against the byte-identical template in the merge base. This one is
    hand-scaffolded, which is the shape that has nothing to match.)
    """
    inbox = _drop_the_inbox(consumer)
    header = "# Insight Inbox\n\n_Entries below, newest last._\n\n"
    for branch, line in (("aide/add-ours", _OURS), ("aide/add-theirs", _THEIRS)):
        _git(["switch", "-c", branch, "main"], consumer)
        inbox.write_text(header + line + "\n", encoding="utf-8")
        _commit(consumer, f"docs(aide): scaffold the inbox on {branch}")
    _git(["switch", "aide/add-ours"], consumer)
    assert _git(["merge", "aide/add-theirs"], consumer, check=False).returncode != 0

    rel = "docs/aide/insights.md"
    assert [l.split()[2] for l in
            _git(["ls-files", "-u", "--", rel], consumer).stdout.splitlines()] == ["2", "3"]
    assert _git(["show", f":1:{rel}"], consumer, check=False).returncode != 0

    assert aide.main(["--repo", str(consumer), "insights", "resolve"]) == 0
    assert not _git(["ls-files", "-u", "--", rel], consumer).stdout.strip()
    _git(["commit", "--no-edit"], consumer)          # would die if left unstaged
    assert _git(["status", "--porcelain"], consumer).stdout.strip() == ""
    text = inbox.read_text(encoding="utf-8")
    assert _OURS in text and _THEIRS in text and "<<<<<<<" not in text


def test_dry_run_prints_the_union_itself_not_only_the_counts(
        aide, consumer: Path, capsys):
    """Reviewing the merge before it is written is the whole of what the flag
    is for, and every place that documents it says it prints what would land."""
    _two_branches_that_both_appended(consumer)
    assert aide.main(["--repo", str(consumer), "insights", "resolve",
                      "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert _OURS in out and _THEIRS in out and "<<<<<<<" not in out


def test_resolve_finishes_a_hand_stripped_file_that_git_still_holds_unmerged(
        aide, consumer: Path, capsys):
    """Markers gone, path still unmerged — someone resolved it by hand and
    stopped short of staging. Reporting "nothing to resolve" and exiting 0 left
    the exact end state the staging fix removed on the other branch of the
    code: `git commit` dies on unmerged files."""
    _two_branches_that_both_appended(consumer)
    inbox = consumer / "docs" / "aide" / "insights.md"
    kept = [l for l in inbox.read_text(encoding="utf-8").splitlines()
            if not l.startswith(("<<<<<<<", "=======", ">>>>>>>"))]
    inbox.write_text("\n".join(kept) + "\n", encoding="utf-8")
    rel = "docs/aide/insights.md"
    assert _git(["ls-files", "-u", "--", rel], consumer).stdout.strip()

    assert aide.main(["--repo", str(consumer), "insights", "resolve"]) == 0
    assert "still held it unmerged" in capsys.readouterr().out
    assert not _git(["ls-files", "-u", "--", rel], consumer).stdout.strip()
    _git(["commit", "--no-edit"], consumer)          # would die if left unstaged
    assert _git(["status", "--porcelain"], consumer).stdout.strip() == ""


def test_resolve_dry_run_leaves_the_conflict_in_place(aide, consumer: Path, capsys):
    _two_branches_that_both_appended(consumer)
    before = (consumer / "docs" / "aide" / "insights.md").read_text(encoding="utf-8")
    assert aide.main(["--repo", str(consumer), "insights", "resolve",
                      "--dry-run"]) == 0
    assert "dry run" in capsys.readouterr().out
    assert (consumer / "docs" / "aide" / "insights.md").read_text(
        encoding="utf-8") == before
    assert _git(["ls-files", "-u", "--", "docs/aide/insights.md"],
                consumer).stdout.strip()


def test_resolve_refuses_when_one_side_archived_and_writes_nothing(
        aide, consumer: Path, capsys):
    """The archive boundary issue #158 left open: `archive` cuts closed entries
    out of the middle and renumbers, so the two sides are not one append.

    The collision is the realistic one — a branch archived a closed entry while
    another appended a trail line to that same entry.
    """
    _git(["switch", "-c", "aide/insight-archived", "main"], consumer)
    assert aide.main(["--repo", str(consumer), "insights", "archive",
                      "--before", "2026-06-01", "--yes"]) == 0
    _git(["switch", "-c", "aide/insight-ticked", "main"], consumer)
    assert aide.main(["--repo", str(consumer), "insights", "tick", "1",
                      "--pointer", "engine 1.43.0"]) == 0
    merge = _git(["merge", "aide/insight-archived"], consumer, check=False)
    assert merge.returncode != 0, "the archive did not collide with the trail line"
    before = (consumer / "docs" / "aide" / "insights.md").read_text(encoding="utf-8")

    assert aide.main(["--repo", str(consumer), "insights", "resolve"]) == 1
    err = capsys.readouterr().err
    assert "Resolve this one by hand" in err and "left exactly as it is" in err
    assert (consumer / "docs" / "aide" / "insights.md").read_text(
        encoding="utf-8") == before          # markers still there ...
    assert _git(["ls-files", "-u", "--", "docs/aide/insights.md"],
                consumer).stdout.strip()     # ... and still unresolved


def test_resolve_merges_a_tick_taken_on_one_branch_only(aide, consumer: Path):
    """The routine loop shape: one branch triaged the last entry while another
    captured a new one right below it. The tick survives, and the claim it sits
    on is not appended a second time."""
    _git(["switch", "-c", "aide/insight-ticked", "main"], consumer)
    assert aide.main(["--repo", str(consumer), "insights", "tick", "3",
                      "--pointer", "item 002"]) == 0
    _append_insight(consumer, _OURS, "aide/insight-ours")
    merge = _git(["merge", "aide/insight-ticked"], consumer, check=False)
    assert merge.returncode != 0, "the tick did not collide with the append"
    assert aide.main(["--repo", str(consumer), "insights", "resolve"]) == 0

    entries = aide.parse_insights(
        (consumer / "docs" / "aide" / "insights.md").read_text(encoding="utf-8"))
    assert len(entries) == 4                      # not 5 — the claim is one entry
    assert entries[2].ticked and entries[2].pointer == "item 002"
    assert "nothing checks the farewell" in entries[2].text
    assert entries[3].raw == _OURS


# --------------------------------------------------------------------------- #
# the stall names the verb — `aide merge` is where this conflict lands
# --------------------------------------------------------------------------- #
def _capture_here(repo: Path, line: str) -> None:
    """Append one insight on the branch already checked out."""
    inbox = repo / "docs" / "aide" / "insights.md"
    inbox.write_text(inbox.read_text(encoding="utf-8") + line + "\n",
                     encoding="utf-8")
    _commit(repo, "docs(aide): capture")


def _item_branch_and_main_both_capture(aide, consumer: Path) -> None:
    """The routine shape: an item branch is open while `main` gains a capture.
    Both sides appended, so `aide merge` stalls on the inbox and nothing else."""
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    _capture_here(consumer, _OURS)
    _git(["switch", "main"], consumer)
    _capture_here(consumer, _THEIRS)
    _git(["switch", "aide/001-the-greeter"], consumer)


def test_merge_names_the_verb_when_it_stalls_on_the_inbox(
        aide, consumer: Path, capsys):
    """The verb is useless to the role that needs it unless the thing that
    stalls says so: `aide merge` is run by the `validator`, which preloads a
    different skill and has read nothing about the inbox."""
    _item_branch_and_main_both_capture(aide, consumer)
    assert aide.main(["--repo", str(consumer), "merge", "1", "--no-test"]) == 1
    err = capsys.readouterr().err
    assert "insights resolve" in err
    assert "ONLY unmerged path" in err          # so the verb finishes the job
    assert "Do NOT resolve" in err and "conventions.md §1" in err


def test_the_mid_merge_refusal_resolves_before_it_offers_to_abort(
        aide, consumer: Path, capsys):
    """An agent that reads "abort" literally aborts, re-runs, and meets the
    identical conflict. The advice has to end the loop, not restart it — and
    following it here has to actually finish the merge."""
    _item_branch_and_main_both_capture(aide, consumer)
    assert aide.main(["--repo", str(consumer), "merge", "1", "--no-test"]) == 1
    capsys.readouterr()
    assert aide.main(["--repo", str(consumer), "merge", "1", "--no-test"]) == 1
    err = capsys.readouterr().err
    assert "insights resolve" in err
    assert err.index("resolve and stage") < err.index("or abort it")
    assert "brings it back on the next attempt" in err

    # And the route it names ends the stall for real.
    assert aide.main(["--repo", str(consumer), "insights", "resolve"]) == 0
    _git(["commit", "--no-edit"], consumer)
    assert not (consumer / ".git" / "MERGE_HEAD").exists()
    assert _git(["status", "--porcelain"], consumer).stdout.strip() == ""
    text = (consumer / "docs" / "aide" / "insights.md").read_text(encoding="utf-8")
    assert _OURS in text and _THEIRS in text


def test_the_inbox_hint_stays_quiet_when_the_conflict_is_somewhere_else(
        aide, consumer: Path, capsys):
    """A hint that fires on every stall is one a reader learns to skim."""
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    shared = consumer / "docs" / "aide" / "shared.md"
    shared.write_text("branch side\n", encoding="utf-8")
    _commit(consumer, "docs: branch side")
    _git(["switch", "main"], consumer)
    shared.write_text("main side\n", encoding="utf-8")
    _commit(consumer, "docs: main side")

    assert aide.main(["--repo", str(consumer), "merge", "1", "--no-test"]) == 1
    err = capsys.readouterr().err
    assert "shared.md" in err and "insights resolve" not in err


# --------------------------------------------------------------------------- #
# a stopped rebase is a sentence, not a silent state (#178)
# --------------------------------------------------------------------------- #
_ANOTHER = "- [ ] defect — the greeter drops a trailing space *(item 004, 2026-08-27)*"


def _with_origin(consumer: Path, tmp_path: Path) -> None:
    """A bare origin, pushed main, and a mode that talks to it."""
    origin = tmp_path / "origin.git"
    _git(["init", "--bare", "-b", "main", str(origin)], tmp_path)
    _git(["remote", "add", "origin", str(origin)], consumer)
    _git(["push", "-u", "origin", "main"], consumer)
    toml = consumer / "aide.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace(
        'mode = "local"', 'mode = "auto-merge"'), encoding="utf-8")
    _commit(consumer, "chore: auto-merge mode")
    _git(["push"], consumer)


def _diverge_on(consumer: Path, rel: str, theirs: str, ours: str) -> None:
    """Push *theirs* to the current branch's upstream, keep *ours* here.

    Both land at the end of the same file, which is the routine shape rather
    than a contrived one: `insights.md` is append-only and every role captures
    into it, so two machines append to its end and one pushes first. The next
    `pull --rebase` in this checkout stops on the conflict.
    """
    target = consumer / rel
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# notes\n", encoding="utf-8")
        _commit(consumer, f"docs(aide): add {rel}")
        _git(["push"], consumer)
    target.write_text(target.read_text(encoding="utf-8") + theirs + "\n",
                      encoding="utf-8")
    _commit(consumer, "docs(aide): the other machine's line")
    _git(["push"], consumer)
    _git(["reset", "--hard", "HEAD~1"], consumer)
    target.write_text(target.read_text(encoding="utf-8") + ours + "\n",
                      encoding="utf-8")
    _commit(consumer, "docs(aide): our line")


def test_merge_stops_when_its_pull_leaves_a_rebase_unfinished(
        aide, consumer: Path, tmp_path: Path, capsys):
    """The sharpest of the three sites: `git merge` refuses outright while a
    rebase is in progress, so a run that continued past the pull reported the
    MERGE's failure for a stall the pull had caused, on a base branch left in
    a state neither message described."""
    _with_origin(consumer, tmp_path)
    _diverge_on(consumer, "docs/aide/insights.md", _THEIRS, _OURS)
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    capsys.readouterr()

    assert aide.main(["--repo", str(consumer), "merge", "1", "--no-test"]) == 1
    err = capsys.readouterr().err
    assert "git pull --rebase could not complete" in err
    assert "a rebase is in progress" in err
    # The cause, not the casualty: the merge is never attempted.
    assert "merge of aide/001-the-greeter failed" not in err
    assert "NOT ticked" in err
    assert _item_status(aide, consumer, 1) != "complete"
    assert "aide/001-the-greeter" in _branches(consumer)
    # and the one verb that ends this particular stall is named
    assert "insights resolve" in err


def test_sync_refuses_a_start_point_whose_rebase_stopped(
        aide, consumer: Path, tmp_path: Path, capsys):
    """`aide sync`'s contract is "exit 0 == safe to start". A claim branch
    left mid-rebase is exactly what it exists to catch, and it announced
    "tree clean" over it."""
    _with_origin(consumer, tmp_path)
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    _git(["push", "-u", "origin", "aide/001-the-greeter"], consumer, check=False)
    _diverge_on(consumer, "docs/aide/insights.md", _THEIRS, _OURS)
    capsys.readouterr()

    assert aide.main(["--repo", str(consumer), "sync", "--item", "1"]) == 1
    captured = capsys.readouterr()
    assert "git pull --rebase could not complete" in captured.err
    assert "work must not start here" in captured.err
    assert "tree clean" not in captured.out       # the line it used to print


def test_sync_says_a_claim_branch_was_not_refreshed_and_still_starts(
        aide, consumer: Path, tmp_path: Path, capsys, monkeypatch):
    """The other half of the discriminator, and the one that must NOT refuse.

    A pull that comes back non-zero without starting anything — a flake
    between the fetch and the pull, an origin that went away — leaves the
    branch checked out and clean, which is exactly what this verb promises.
    Refusing there would stall an unattended run over a remote. It still has
    to be said, because the success line claims the remotes were fetched.

    Forced rather than staged: `fetch --all --prune` runs first and prunes a
    ref that has gone, so the reachable version of this is a network flake
    between two calls, which a fixture cannot produce.
    """
    _with_origin(consumer, tmp_path)
    assert _claim(aide, consumer) == 0
    _git(["push", "-u", "origin", "aide/001-the-greeter"], consumer, check=False)
    real_git = aide.git

    def flaky(args, *rest, **kw):
        if args and args[0] == "pull":
            return subprocess.CompletedProcess(
                args, 1, "", "fatal: unable to access origin: could not resolve host\n")
        return real_git(args, *rest, **kw)

    monkeypatch.setattr(aide, "git", flaky)
    capsys.readouterr()

    assert aide.main(["--repo", str(consumer), "sync", "--item", "1"]) == 0
    captured = capsys.readouterr()
    assert "was NOT refreshed from origin" in captured.err
    assert "could not resolve host" in captured.err
    assert "work can start" in captured.err
    assert "git pull --rebase could not complete" not in captured.err
    assert "aide sync: OK" in captured.out       # and it is still a green start


def test_a_bookkeeping_commit_is_refused_over_an_unfinished_rebase(
        aide, consumer: Path, tmp_path: Path, capsys):
    """The shared committer behind `progress set`, `insights tick` and
    `insights archive` returns a reason rather than printing one, and all
    three callers discard it — so the reason is printed here too, or a verb
    announces a tick that is in no commit.

    The conflict is deliberately NOT on the inbox: the hint has to stay quiet
    when the inbox is not what stopped this.
    """
    _with_origin(consumer, tmp_path)
    _diverge_on(consumer, "docs/aide/note.md", "their note\n", "our note\n")
    stopped = _git(["pull", "--rebase"], consumer, check=False)
    assert stopped.returncode != 0, "the rebase did not stop on a conflict"
    capsys.readouterr()

    assert aide.main(["--repo", str(consumer), "insights", "tick", "1",
                      "--pointer", "item 002"]) == 0
    err = capsys.readouterr().err
    assert "could not commit" in err
    assert "git pull --rebase could not complete" in err
    assert "insights resolve" not in err        # the inbox is not the conflict
    # written to the worktree, deliberately not committed on top of the rebase
    assert "docs/aide/insights.md" in _git(
        ["status", "--porcelain"], consumer).stdout


def test_the_stall_names_the_operation_git_reports_not_a_rebase(
        aide, consumer: Path, capsys):
    """The pull is not always what stopped: it also refuses because an earlier
    operation is STILL in progress, and at the shared-committer site that is
    the reachable case. The message then has to name that operation and the
    abort that matches it — `git rebase --abort` fails inside a cherry-pick."""
    note = consumer / "docs" / "aide" / "note.md"
    note.write_text("base\n", encoding="utf-8")
    _commit(consumer, "docs(aide): add note")
    _git(["switch", "-c", "side"], consumer)
    note.write_text("side\n", encoding="utf-8")
    _commit(consumer, "docs(aide): side")
    _git(["switch", "main"], consumer)
    note.write_text("main\n", encoding="utf-8")
    _commit(consumer, "docs(aide): main")
    picked = _git(["cherry-pick", "side"], consumer, check=False)
    assert picked.returncode != 0, "the cherry-pick did not stop on a conflict"
    capsys.readouterr()

    assert aide.main(["--repo", str(consumer), "insights", "tick", "1",
                      "--pointer", "item 002"]) == 0
    err = capsys.readouterr().err
    assert "a cherry-pick is in progress" in err
    assert "git cherry-pick --abort" in err
    assert "git rebase --abort" not in err       # would fail if run
    assert "git cherry-pick --continue" in err


# --------------------------------------------------------------------------- #
# the sibling shape — `--repo` beats a cwd inside a different consumer (#93)
# --------------------------------------------------------------------------- #
def test_repo_flag_wins_over_a_cwd_inside_another_consumer(
        aide, consumer: Path, tmp_path: Path, monkeypatch):
    """conventions.md §3's approved sibling shape is
    `python <sibling>/.aide/scripts/aide.py --repo <sibling> <cmd>`, and it is
    only safe if `--repo` really overrides the cwd walk: the shape is issued
    from INSIDE another repo with its own `aide.toml`, and resolving from cwd
    would judge that repo's documents instead of the sibling's."""
    other = tmp_path / "other"
    (other / "docs" / "aide").mkdir(parents=True)
    (other / "aide.toml").write_text('[project]\nname = "Other"\n',
                                     encoding="utf-8")
    # cwd's repo carries a document set `check` must reject (a surviving
    # template slot), so the two roots are distinguishable by exit code alone.
    (other / "docs" / "aide" / "progress.md").write_text(
        "# Other — Progress\n\n> {{one_line}}\n", encoding="utf-8")
    monkeypatch.chdir(other)
    assert aide.main(["check"]) != 0
    # The same cwd with --repo judges the sibling, whose documents are sound.
    assert aide.main(["--repo", str(consumer), "check"]) == 0


# --------------------------------------------------------------------------- #
# progress amend / retract / reword — correcting an attestation, through the CLI
#
# Issue #118: `accept` reports an already-ticked box as "unchanged", so the only
# route to a wrong attestation was the hand edit of progress.md every role is
# forbidden from making. These drive the verbs the way a consumer does, and
# assert effects — the files afterwards, and the exit codes — never prose.
# --------------------------------------------------------------------------- #
_ROADMAP = """\
# Fixture — Roadmap

## Stage 1 — Foundations

**Validation / acceptance.**

- Both items land.
- Target: the greeter answers in under a millisecond.
"""


def _acceptance_block(consumer: Path) -> list:
    text = (consumer / "docs" / "aide" / "progress.md").read_text(encoding="utf-8")
    body = text.split("**Acceptance.**", 1)[1]
    return [l for l in body.splitlines() if l.strip()]


def _accept_one(aide, consumer: Path, evidence: str) -> None:
    assert aide.main(["--repo", str(consumer), "progress", "accept", "1",
                      "--criterion", "1", "--evidence", evidence]) == 0


def test_amend_appends_a_correction_without_touching_the_attestation(
        aide, consumer: Path):
    _accept_one(aide, consumer, "validator, 2026-08-29: on this CPU-only machine")
    before = _acceptance_block(consumer)[0]
    assert aide.main(["--repo", str(consumer), "progress", "amend", "1",
                      "--criterion", "1", "--date", "2026-09-01",
                      "--evidence", "the host has four GPUs"]) == 0
    after = _acceptance_block(consumer)
    assert after[0] == before            # the claim itself is never reworded
    assert after[1] == "  - **2026-09-01** → the host has four GPUs"
    assert _files_in_head(consumer) == ["docs/aide/progress.md"]


def test_amend_refuses_an_unticked_box_and_writes_nothing(aide, consumer: Path):
    before = (consumer / "docs" / "aide" / "progress.md").read_bytes()
    assert aide.main(["--repo", str(consumer), "progress", "amend", "1",
                      "--criterion", "1", "--evidence", "x"]) == 1
    assert (consumer / "docs" / "aide" / "progress.md").read_bytes() == before


def test_amend_requires_a_stated_basis(aide, consumer: Path):
    _accept_one(aide, consumer, "checked")
    assert aide.main(["--repo", str(consumer), "progress", "amend", "1",
                      "--criterion", "1", "--evidence", "   "]) == 2


def test_amend_and_retract_do_not_offer_all(aide, consumer: Path):
    _accept_one(aide, consumer, "checked")
    assert aide.main(["--repo", str(consumer), "progress", "amend", "1",
                      "--all", "--evidence", "x"]) == 2
    assert aide.main(["--repo", str(consumer), "progress", "retract", "1",
                      "--all", "--reason", "x"]) == 2


def test_retract_unticks_keeps_the_original_and_captures_a_gap(
        aide, consumer: Path):
    _accept_one(aide, consumer, "validator, 2026-08-29: on this CPU-only machine")
    assert aide.main(["--repo", str(consumer), "progress", "retract", "1",
                      "--criterion", "1", "--date", "2026-09-02",
                      "--reason", "the host was misread"]) == 0
    block = _acceptance_block(consumer)
    assert block[0].startswith("- [ ] Both items land.")
    assert "on this CPU-only machine" in block[0]      # the claim is kept
    assert block[1] == "  - **2026-09-02** → retracted: the host was misread"
    inbox = (consumer / "docs" / "aide" / "insights.md").read_text(encoding="utf-8")
    assert "- [ ] gap — acceptance criterion retracted: the host was misread" in inbox
    assert "*(stage 1 criterion 1, 2026-09-02" in inbox
    # One commit, both documents — the finding lands with the withdrawal.
    assert sorted(_files_in_head(consumer)) == [
        "docs/aide/insights.md", "docs/aide/progress.md"]


def test_retract_says_the_check_warning_it_creates_is_permanent(
        aide, consumer: Path, capsys):
    """Issue #152: the warning is by design, and a consumer that pins the
    tolerated warning set goes red on it. The verb says so at retraction time,
    so the widening lands here rather than at the merge gate."""
    _accept_one(aide, consumer, "checked")
    capsys.readouterr()
    assert aide.main(["--repo", str(consumer), "progress", "retract", "1",
                      "--criterion", "1", "--reason", "the host was misread"]) == 0
    out = capsys.readouterr().out
    assert "will warn about this retraction from now on" in out
    assert "the record is permanent" in out
    assert "pins the tolerated warning set needs widening" in out
    assert "stage 1 criterion 1" in out


def test_a_retraction_stays_visible_in_check_and_status(
        aide, consumer: Path, capsys):
    _accept_one(aide, consumer, "checked")
    assert aide.main(["--repo", str(consumer), "progress", "retract", "1",
                      "--criterion", "1", "--reason", "the host was misread"]) == 0
    capsys.readouterr()
    assert aide.main(["--repo", str(consumer), "check"]) == 0
    assert "was retracted" in capsys.readouterr().out
    assert aide.main(["--repo", str(consumer), "status"]) == 0
    assert "retracted: stage 1 criterion 1" in capsys.readouterr().out


def test_the_gap_a_retraction_captures_is_a_well_shaped_inbox_entry(
        aide, consumer: Path, capsys):
    """It must survive `check`'s own shape rule, or the verb files a warning."""
    _accept_one(aide, consumer, "checked")
    assert aide.main(["--repo", str(consumer), "progress", "retract", "1",
                      "--criterion", "1", "--reason", "the host was misread"]) == 0
    capsys.readouterr()
    assert aide.main(["--repo", str(consumer), "check"]) == 0
    assert "does not match" not in capsys.readouterr().out


def test_reword_rewrites_an_untouched_criterion_and_mirrors_the_roadmap(
        aide, consumer: Path):
    (consumer / "docs" / "aide" / "roadmap.md").write_text(_ROADMAP, encoding="utf-8")
    _commit(consumer, "a roadmap that mirrors the criteria")
    assert aide.main(["--repo", str(consumer), "progress", "reword", "1",
                      "--criterion", "1", "--text", "Both items merge to main."]) == 0
    assert _acceptance_block(consumer)[0] == "- [ ] Both items merge to main."
    roadmap = (consumer / "docs" / "aide" / "roadmap.md").read_text(encoding="utf-8")
    assert "- Both items merge to main." in roadmap.splitlines()
    # The Target: bullet is not a box, so it must not have been consumed.
    assert "- Target: the greeter answers in under a millisecond." in roadmap.splitlines()
    assert sorted(_files_in_head(consumer)) == [
        "docs/aide/progress.md", "docs/aide/roadmap.md"]


def test_reword_refuses_once_the_criterion_has_been_attested(aide, consumer: Path):
    _accept_one(aide, consumer, "checked")
    before = (consumer / "docs" / "aide" / "progress.md").read_bytes()
    assert aide.main(["--repo", str(consumer), "progress", "reword", "1",
                      "--criterion", "1", "--text", "something else"]) == 1
    assert (consumer / "docs" / "aide" / "progress.md").read_bytes() == before


def test_a_roadmap_that_cannot_be_lined_up_leaves_both_files_alone(
        aide, consumer: Path):
    """Both documents or neither — a half-landed rewording is the drift the
    verb exists to remove."""
    (consumer / "docs" / "aide" / "roadmap.md").write_text(
        _ROADMAP + "- An extra bullet progress.md never mirrored.\n", encoding="utf-8")
    _commit(consumer, "a roadmap that disagrees")
    progress = consumer / "docs" / "aide" / "progress.md"
    roadmap = consumer / "docs" / "aide" / "roadmap.md"
    before = (progress.read_bytes(), roadmap.read_bytes())
    assert aide.main(["--repo", str(consumer), "progress", "reword", "1",
                      "--criterion", "1", "--text", "should not land"]) == 1
    assert (progress.read_bytes(), roadmap.read_bytes()) == before


# --------------------------------------------------------------------------- #
# the silent engine wrongs — #167, #169, #166, #165 — through the installed engine
# --------------------------------------------------------------------------- #
def test_a_merge_re_run_after_a_red_run_still_lands_on_the_queue_branch(
        aide, consumer: Path):
    """#167: the invited re-run resolves to the base the first run had.

    `merge` deletes the claim branch before the post-merge run, and `git
    branch -d` takes `branch.<claim>.aide-base` with it. The restore used to
    put back the ref alone, so the retry a red run invites — with no `--base`,
    since the first run needed none — fell back to main_branch: a consumer's
    whole queue was fast-forwarded onto `main` and pushed past its
    one-reviewed-PR-per-queue gate, with nothing in the output naming `main`.
    """
    assert aide.main(["--repo", str(consumer), "queue", "start", "1"]) == 0
    main_before = _git(["rev-parse", "main"], consumer).stdout.strip()
    assert _claim(aide, consumer) == 0
    _set_test_command(consumer, "git rev-parse --verify no-such-ref")
    _do_the_work(consumer)

    assert aide.main(["--repo", str(consumer), "merge", "1"]) == 1
    assert _branch(consumer) == "aide/queue-001"
    assert "aide/001-the-greeter" in _branches(consumer)
    recorded = _git(["config", "--get",
                     f"branch.aide/001-the-greeter.{aide._BASE_CONFIG_KEY}"],
                    consumer).stdout.strip()
    assert recorded == "aide/queue-001"

    _set_test_command(consumer, "git rev-parse --verify HEAD")
    _commit(consumer, "chore: a passing test command")
    assert aide.main(["--repo", str(consumer), "merge", "1"]) == 0   # no --base: the invited re-run
    assert _git(["rev-parse", "main"], consumer).stdout.strip() == main_before
    assert _branch(consumer) == "aide/queue-001"
    assert (consumer / "src" / "greeter.py").is_file()
    assert _item_status(aide, consumer, 1) == "complete"
    assert "aide/001-the-greeter" not in _branches(consumer)


def test_a_merge_whose_base_was_lost_refuses_rather_than_landing_on_main(
        aide, consumer: Path, capsys):
    """#174, half 2, through the installed engine.

    A `finally` cannot run through `SIGKILL`, so half 1 cannot be the whole
    guarantee: whatever killed the previous run, the NEXT one meets a claim
    branch with no recorded base. That is the shape a consumer recovered by
    hand — `git branch <name> <sha>` puts the ref back and not the config —
    and the silent `main_branch` fallback then fast-forwarded a whole queue
    onto `main` and pushed it. Here it stops instead, with `main` untouched.
    """
    assert aide.main(["--repo", str(consumer), "queue", "start", "1"]) == 0
    _set_test_command(consumer, "git rev-parse --verify HEAD")
    _commit(consumer, "chore: a passing test command")
    main_before = _git(["rev-parse", "main"], consumer).stdout.strip()
    assert _claim(aide, consumer) == 0
    _do_the_work(consumer)
    branch = _branch(consumer)
    tip = _git(["rev-parse", branch], consumer).stdout.strip()

    # The aftermath of a killed merge, reproduced: the ref restored by hand,
    # its `aide-base` gone with the branch it was deleted alongside.
    _git(["switch", "aide/queue-001"], consumer)
    _git(["branch", "-D", branch], consumer)
    _git(["branch", branch, tip], consumer)
    assert _git(["config", "--get", f"branch.{branch}.{aide._BASE_CONFIG_KEY}"],
                consumer, check=False).stdout.strip() == ""

    assert aide.main(["--repo", str(consumer), "merge", "1"]) == 1
    err = capsys.readouterr().err
    assert "no base is recorded" in err and "--base" in err
    assert _git(["rev-parse", "main"], consumer).stdout.strip() == main_before
    assert _item_status(aide, consumer, 1) != "complete"
    assert branch in _branches(consumer)

    # `--base` is the override the refusal names, and it lands on the queue
    # branch the claim belonged to — not on main.
    assert aide.main(["--repo", str(consumer), "merge", "1",
                      "--base", "aide/queue-001"]) == 0
    assert _git(["rev-parse", "main"], consumer).stdout.strip() == main_before
    assert _item_status(aide, consumer, 1) == "complete"


def test_a_split_reports_its_copies_and_check_sees_them_until_reworded(
        aide, consumer: Path, capsys):
    """#169: the split writes the shared prose N times, and says so.

    A consumer's ✅ line for one item described two other items' undone work,
    because the copy the split wrote was flipped without rewording and nothing
    could tell. The flip now prints every copy it made, and `check` reports
    identical single-item siblings in a stage until each is reworded.
    """
    progress = consumer / "docs" / "aide" / "progress.md"
    text = progress.read_text(encoding="utf-8")
    shared = "- 📋 Both functions. *(Items 001, 002)*\n"
    text = text.replace("- 📋 The greeter. *(Item 001)*\n- 📋 The farewell. *(Item 002)*\n", shared)
    assert shared in text
    progress.write_text(text, encoding="utf-8")
    _commit(consumer, "docs: one bullet for two items")
    capsys.readouterr()

    assert aide.main(["--repo", str(consumer), "progress", "set", "1", "in-progress"]) == 0
    reported = [l.strip() for l in capsys.readouterr().out.splitlines()
                if l.strip().startswith("progress.md:")]
    assert len(reported) == 2
    assert any(l.endswith("- 🚧 Both functions. *(Item 001)*") for l in reported)
    assert any(l.endswith("- 📋 Both functions. *(Item 002)*") for l in reported)
    for line in reported:
        lineno = int(line.split(":")[1])
        assert progress.read_text(encoding="utf-8").splitlines()[lineno - 1].strip() == line.split(": ", 1)[1]

    _, warnings = aide.run_checks(consumer, aide.load_config(consumer))
    identical = [w for w in warnings if "identical prose" in w]
    assert len(identical) == 1 and "001, 002" in identical[0]

    text = progress.read_text(encoding="utf-8").replace(
        "- 📋 Both functions. *(Item 002)*", "- 📋 The farewell. *(Item 002)*")
    progress.write_text(text, encoding="utf-8")
    _, warnings = aide.run_checks(consumer, aide.load_config(consumer))
    assert not [w for w in warnings if "identical prose" in w]


def test_the_scaffold_carries_the_review_key_and_defaults_it_off(
        aide, consumer: Path):
    """1.40.0's `loop.review` (issue #151), through the engine a consumer runs.

    The key is prose-consumed by the orchestrator, the way `clarify` is, so
    there is no verb to exercise — what the engine owes is that the value
    arrives, unchanged, at the role that reads it. Both halves matter: the
    scaffold writes the key so a fresh consumer can see and change it, and the
    default is `off`, because a review round costs tokens on every item and
    turning it on is the project's decision.
    """
    text = (consumer / "aide.toml").read_text(encoding="utf-8")
    assert 'review = "off"' in text, "the aide.toml scaffold lost loop.review"
    assert aide.load_config(consumer)["loop"]["review"] == "off"


def test_a_consumer_whose_aide_toml_predates_the_review_key_still_reads_off(
        aide, consumer: Path):
    """`--update` never rewrites `aide.toml`, so every consumer installed
    before 1.40.0 reaches the new engine with no `review` line at all. The
    default has to come from the engine, not from the scaffold — otherwise the
    orchestrator reads a missing key on exactly the installs that did not opt
    in, and the value it invents there is anyone's guess.
    """
    toml = consumer / "aide.toml"
    text = toml.read_text(encoding="utf-8")
    assert 'review = "off"\n' in text
    toml.write_text(text.replace('review = "off"\n', ""), encoding="utf-8")

    assert aide.load_config(consumer)["loop"]["review"] == "off"


def test_the_review_key_reaches_the_orchestrator_as_the_project_set_it(
        aide, consumer: Path):
    """The other direction: a project that opts in gets its value back. The
    engine does not interpret it — `background` is meaningful to the item
    orchestrator and to nothing under `.aide/scripts/` — so carrying it
    verbatim is the entire contract.
    """
    toml = consumer / "aide.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace(
        'review = "off"', 'review = "background"'), encoding="utf-8")

    assert aide.load_config(consumer)["loop"]["review"] == "background"
    # and it did not disturb the sibling key it sits next to
    assert aide.load_config(consumer)["loop"]["clarify"] == "assume"


def _set_python_keys(repo: Path, **keys: str) -> None:
    toml = repo / "aide.toml"
    text = toml.read_text(encoding="utf-8")
    assert "[python]\n" in text, "aide.toml lost its [python] section"
    extra = "".join(f'{k} = "{v}"\n' for k, v in keys.items())
    toml.write_text(text.replace("[python]\n", "[python]\n" + extra, 1), encoding="utf-8")


def test_an_env_bootstrap_that_half_installs_cannot_report_ok(aide, consumer: Path):
    """#166: a bootstrap whose install aborts leaves a venv, and `env` used
    to read the venv's existence plus one import as OK. The validator trusted
    that green and failed on the environment with its item named."""
    _set_python_keys(consumer, venv=".venv", bootstrap="-m no_such_module_aide_fixture")
    assert aide.main(["--repo", str(consumer), "env"]) == 1              # missing
    assert aide.main(["--repo", str(consumer), "env", "--bootstrap"]) == 1
    assert (consumer / ".venv" / aide._BOOTSTRAP_RECORD).is_file()     # the venv exists…
    assert aide.main(["--repo", str(consumer), "env"]) == 1              # …and is not OK


def test_an_interpreter_this_machine_lacks_stops_the_bootstrap_before_the_venv(
        aide, consumer: Path):
    _set_python_keys(consumer, venv=".venv", interpreter="no-such-python-aide-fixture")
    assert aide.main(["--repo", str(consumer), "env", "--bootstrap"]) == 1
    assert not (consumer / ".venv").exists()


def test_sync_is_not_stalled_by_the_claude_runtimes_scratch_worktrees(aide, consumer: Path):
    """#165: `/code-review` leaves a scratch checkout under `.claude/worktrees/`;
    an unattended run stalled on `sync`'s unclean-tree refusal over it. The
    installed block ignores it, so the cleanliness check stays unconditional."""
    scratch = consumer / ".claude" / "worktrees" / "review-abc"
    scratch.mkdir(parents=True)
    (scratch / "README.md").write_text("a scratch checkout\n", encoding="utf-8")
    assert aide.main(["--repo", str(consumer), "sync"]) == 0
    assert aide.main(["--repo", str(consumer), "status"]) == 0
