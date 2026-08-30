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


#: The skills that deliver a contract section — `user-invocable: false` in
#: the source tree — so the checks below are on whatever is a section skill
#: today rather than on a list that goes stale.
SOURCE_SECTION_SKILLS = [
    p for p in sorted((FRAMEWORK_ROOT / "adapters" / "claude" / "skills").glob("*/SKILL.md"))
    if "user-invocable: false" in (_frontmatter(p) or "")]

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


def _git(args, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


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
