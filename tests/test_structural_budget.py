"""What a delivered file *reaches*, asserted; what it *costs*, printed.

The gap this closes (issue #84). Issue #78 asked a token-budget question and
answered it by grepping eleven stored session transcripts of a consumer. Issue
#79 then changed that budget substantially and in the wrong direction — the
compaction it introduced saves ~30.8k, the three `.claude/rules/` files it
introduced cost ~46k to ~57k across an eight-item queue — and nobody noticed
until a reviewer did the arithmetic by hand. Nothing in the suite knew what a
token was, and nothing knew which contexts a rule loads into.

**The half that is measurable is structural**, and it is a pure function of the
installed tree. **The half that is not is behavioural** — whether an agent
follows a pointer once the file is in front of it. This module stays entirely
on the first side of that line.

Two carriers deliver a contract section here, and their reach is measured
differently because it *is* different (issue #85):

- A **rule** (`.claude/rules/*.md`) loads by the runtime's own decision: an
  unscoped one into every context, a `paths:`-scoped one on a matching read —
  inside sub-agent contexts too. Its reach is *inferred*: the globs, evaluated
  against the files each agent spec names.
- A **section skill** (`.claude/skills/<name>/SKILL.md`, `user-invocable:
  false`) is preloaded at spawn into exactly the agent specs whose `skills:`
  frontmatter names it. Its reach is *literal*: the set of specs that list it.
  Its `paths:` inject nothing on a read — measured, #85 — and only surface its
  description to an interactive session's listing regardless, so the glob
  evaluation is *printed* for a skill as its interactive trigger and compared
  against the skill's own `<!-- triggers: … -->` line, which keeps the
  evaluator under test.

**It asserts on structure and prints the cost.** `assert budget < 150_000` would
be a spreadsheet wearing a test's clothes: it bakes in a spawn model and a
bytes-per-token ratio as facts, fails on any prose edit, and gets ratcheted
upward instead of investigated. So the byte totals below are diagnostic output
(`pytest -s`, or the failure text), and the assertions are three properties a
commit can silently break:

1. **A delivered file declares the reach it expects** (`<!-- reach: … -->`),
   and the declaration matches what the carrier actually does — the globs for
   a rule, the `skills:` lists for a section skill. `aide-living-documents.md`
   shipped in #79 scoped to names every role reads — an unscoped rule wearing
   a `paths:` block, invisible because nothing compared the two.
   Since 1.49.3 the declaration is read from the **source** file, because an
   install no longer ships it (issue #205): it is an assertion addressed to
   this module, and a consumer installs no copy of this module. What that
   costs is one extra property, asserted here rather than assumed —
   **the installed file is the source file minus the declarations**, so
   "reach declared in `adapters/claude/`" and "reach of the file a consumer
   loads" remain the same claim about the same bytes.
2. **Frontmatter that stopped parsing fails loudly, in the direction the
   carrier fails.** A BOM from a Windows editor makes the `---` delimiter
   unrecognisable. For a rule the runtime then loads it into every context, so
   the evaluator has to report "0 globs, arms every role" rather than skip the
   file. For a skill the runtime can no longer read its `name:`, so it is
   neither preloadable nor listed — it reaches *nobody* — and the evaluator has
   to report that too.
3. **The always-on floor does not move without a deliberate edit.**
   `AGENT-CONTEXT.md` plus every unscoped rule is paid on every single spawn, so
   that number moving is as consumer-visible as any other change. A section
   skill is not part of it: it is paid only by the roles that preload it.

Measured against a **real install** — `.claude/rules/`, `.claude/skills/`,
`.claude/agents/` and `.aide/AGENT-CONTEXT.md` at the paths a consumer's
runtime actually loads them from — rather than against this repo's source
layout, which is not what anybody pays for. The one thing read from source is
the reach declaration, for the reason above; every byte this module *costs*
is still the installed byte.
"""
from __future__ import annotations

import codecs
import re
import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
sys.path.insert(0, str(FRAMEWORK_ROOT / "tests"))
import install  # noqa: E402  (path shim above)
from _delivered import (REFUSES_BOM, label as _label,  # noqa: E402
                        strip_comments)

#: **The one reader that refuses a BOM.** Every other caller of
#: `tests/_delivered.py` reports on the file behind one; this module has to see
#: what the runtime sees, because a `---` that is not at byte 0 is the failure
#: it exists to measure — a scoped rule read as unscoped and armed everywhere,
#: a section skill with no resolvable `name:` that reaches nobody. Everything
#: below reads through it, including the two sizes: `text()` is BOM-insensitive
#: under either reader (no delimiter is at stake in a byte count), and a body
#: measured behind a delimiter this module refuses is a body nothing preloads.
_READ = REFUSES_BOM
_text = _READ.text
_frontmatter = _READ.frontmatter
_globs = _READ.globs
_skill_name = _READ.skill_name
_is_section_skill = _READ.is_section_skill
_preloads = _READ.preloads


# --------------------------------------------------------------------------- #
# the recorded floor
#
# A constant rather than a data file: the point is that moving it takes a
# deliberate edit a reviewer sees, and a dict literal in the diff says that as
# plainly as a JSON file would, with nothing extra to keep in step.
#
# Per-file, so a failure names which half moved. `version` is the release the
# floor last moved in — not the current one — and
# `test_the_pinned_floor_names_the_release_that_last_moved_it` holds it to that
# by requiring the release's own CHANGELOG entry to record the total below. A
# floor change reaches consumers, so it has to arrive with a version that says
# so; a release that leaves the floor alone leaves both halves of this dict
# alone too.
# --------------------------------------------------------------------------- #
FLOOR_PIN = {
    "version": "1.58.0",
    "files": {
        ".aide/AGENT-CONTEXT.md": 5365,
        ".claude/rules/aide-command-hygiene.md": 3690,
    },
}


# --------------------------------------------------------------------------- #
# the declaration's source — where `reach` and `triggers` live from 1.49.3 on
#
# An install strips them (`install.strip_declarations`), so the installed file
# has no declaration to read and the source file is the only copy there is.
# The pair of readings is the point: reach is *declared* in `adapters/claude/`
# and *paid* in `.claude/`, and the equality below is what keeps them one
# statement rather than two.
# --------------------------------------------------------------------------- #
ADAPTER_SOURCE = FRAMEWORK_ROOT / "adapters" / install.DEFAULT_ADAPTER

#: Where the installer puts the adapter's control directories. Read off
#: `install` rather than spelled again, so a rename reaches this module.
CLAUDE_DIR = install.ADAPTER_INSTALL_DIR


def _source_of(installed: Path) -> Path:
    """The `adapters/<name>/…` file an installed control file was written from.

    A path walk rather than a table: the installed tree mirrors the source one
    under the adapter's install directory, so the tail after `.claude/` is the
    tail after `adapters/claude/`. A file this cannot find is a failure worth
    raising here — it means the layout moved and every declaration below would
    otherwise be read off a file that does not exist.
    """
    parts = installed.parts
    assert CLAUDE_DIR in parts, (
        f"{installed}: not under {CLAUDE_DIR}/ — the install layout moved")
    tail = parts[len(parts) - parts[::-1].index(CLAUDE_DIR):]
    source = ADAPTER_SOURCE.joinpath(*tail)
    assert source.is_file(), (
        f"{_label(installed)}: no source file at {source} — an installed "
        f"control file with nothing behind it, or the source layout moved")
    return source


# --------------------------------------------------------------------------- #
# measuring the delivered files — the parsers themselves are in `_delivered.py`
# --------------------------------------------------------------------------- #
def _size(path: Path) -> int:
    """Content bytes, BOM and CRLF normalised away by `_text`. UTF-8, so a
    multi-byte character counts as the bytes it is — closer to a token than a
    character count, without pretending to be one."""
    return len(_text(path).encode("utf-8"))


def _preload_size(path: Path) -> int:
    """Content bytes a preload injects: the body, HTML comments stripped.

    The runtime injects a preloaded skill without its frontmatter and with
    its comments removed, so the `<!-- reach -->` and `<!-- pins -->` blocks
    cost the loop nothing. This is the number a role actually pays. Measured,
    not assumed — one run per path, model self-report, recorded with its
    caveats in issue #85's comment "Measurement — what a skill body carries
    into context"; an invoked skill keeps its comments, a preloaded one does
    not. If that ever proves wrong, the comments move to frontmatter
    `metadata:` and this function measures the whole body.
    """
    return len(strip_comments(_READ.body(path)).encode("utf-8"))


#: `<!-- reach: … -->`, the whole rest of that line. A prose note goes on the
#: lines below it inside the same comment and is ignored — the declaration is
#: meant to be one glanceable line, and the reasoning is meant to be long.
_REACH = re.compile(r"<!--\s*reach:[ \t]*(?P<roles>[^\n]*)")
#: `<!-- triggers: … -->` — a section skill's second declaration: the roles
#: whose named reads match its `paths:`. What the listing keys on in a human's
#: session, and what a rule with those globs would have armed. Declared so
#: the glob evaluator below is compared against something, not only printed.
_TRIGGERS = re.compile(r"<!--\s*triggers:[ \t]*(?P<roles>[^\n]*)")


def _declared_reach(path: Path, roles, pattern=_REACH, what: str = "reach") -> set:
    """The roles a delivered file says it expects to reach, as a set.

    **Read from the source file**, because an install strips the declaration
    (issue #205): it is a sentence addressed to this module, and shipping it
    would charge every consumer for a note about a test suite they do not
    have. The file measured below is still the installed one, and
    `test_an_installed_control_file_is_its_source_minus_the_declarations`
    is what holds the two to being one file.

    ``all`` is the shorthand for every role — spelling six names out in a file
    that means "everyone" invites one of them to go stale on a rename. The
    same grammar reads a skill's `<!-- triggers: … -->` line when asked, and
    there ``none`` is the other end of it: a section about something no agent
    spec names a file for — `§7`'s CI workflow — matches nobody's read-set,
    and the empty set has to be *sayable* or such a skill can only declare a
    reach it does not have. It is asserted like any other declaration, so a
    glob widened until it matched a role still fails here; what it must never
    become is the reading of a `<!-- reach: … -->` line, where nobody is a
    defect the sibling assertions catch by requiring a preloading spec.
    """
    match = pattern.search(_text(_source_of(path)))
    assert match, (
        f"{_label(path)}: no `<!-- {what}: … -->` declaration in "
        f"{_source_of(path)}. Every delivered file states the roles it expects "
        f"to reach, so that a change of scope has something to contradict; see "
        f"this module's docstring.")
    raw = match.group("roles").strip()
    raw = raw[:-3].strip() if raw.endswith("-->") else raw
    assert raw, f"{_label(path)}: empty reach declaration"
    if raw == "all":
        return set(roles)
    if raw == "none":
        assert pattern is _TRIGGERS, (
            f"{_label(path)}: `<!-- {what}: none -->`. Only the interactive "
            f"trigger may be nobody; a delivered file that reaches no role "
            f"delivers nothing.")
        return set()
    declared = {part.strip() for part in raw.split(",") if part.strip()}
    unknown = declared - set(roles)
    assert not unknown, f"{_label(path)}: reach names no such role: {sorted(unknown)}"
    return declared


# --------------------------------------------------------------------------- #
# glob evaluation — posix strings only, on both CI legs
# --------------------------------------------------------------------------- #
def _glob_to_regex(glob: str) -> "re.Pattern":
    """A `paths:` glob as a regex over `/`-separated paths.

    Hand-rolled rather than `PurePath.match` or `fnmatch`: the first treats
    `**` as `*` before 3.13, the second lets `*` cross a separator, and both
    would quietly widen or narrow a rule's measured reach. Written against
    posix strings so the two CI legs evaluate the same thing — conventions.md
    §6, the rule about `str(Path)` rendering a native separator.
    """
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif glob.startswith("**", i):
            out += ".*"
            i += 2
        elif glob[i] == "*":
            out += "[^/]*"
            i += 1
        elif glob[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(glob[i])
            i += 1
    return re.compile(f"^{out}$")


def _arming_roles(rule: Path, read_sets: dict) -> set:
    """Which roles this rule loads for. No globs ⇒ every one of them."""
    globs = _globs(rule)
    if not globs:
        return set(read_sets)
    patterns = [_glob_to_regex(g) for g in globs]
    return {role for role, files in read_sets.items()
            if any(p.match(f) for f in files for p in patterns)}


def _preload_reach(skill: Path, preloads: dict) -> set:
    """Which roles this skill is preloaded into. No readable name ⇒ nobody."""
    name = _skill_name(skill)
    if name is None:
        return set()
    return {role for role, names in preloads.items() if name in names}


# --------------------------------------------------------------------------- #
# the per-role read-set — derived from the specs, never hand-maintained
# --------------------------------------------------------------------------- #
#: A backticked token. Agent specs name every path they read in backticks, so
#: this is the whole grammar; prose mentions of a document are not reads.
_TOKEN = re.compile(r"`([^`\n]+)`")
#: ...of which the path-shaped ones are those ending in a known extension.
_PATHY = re.compile(r"^[\w./*-]+\.(?:md|py|toml|json|txt)$")


def _named_paths(text: str) -> set:
    """Every concrete file path a spec names, normalised to one the globs see.

    Placeholders become a representative instance: `NNN` is the item number the
    spec is written around, and a `*` left in a basename stands for a name the
    spec does not fix. A *directory* reference — `project.tests_dir` — is
    deliberately NOT expanded: this set is "files the spec names", and a
    directory is a possibility rather than a named read. Counting it would
    arm every rule for every role and the comparison would stop meaning
    anything.
    """
    found = set()
    for backticked in _TOKEN.findall(text):
        for word in backticked.split():
            word = word.strip("()[],;:")
            if not _PATHY.match(word):
                continue
            word = word.replace("NNN", "001")
            head, _, base = word.rpartition("/")
            base = base.replace("*", "x")
            found.add(f"{head}/{base}" if head else base)
    return found


def _read_sets(agents_dir: Path) -> dict:
    """`{role: {posix path, …}}` for every delivered agent spec.

    Two passes, because a spec writes `docs/aide/progress.md` once and
    `progress.md` six times after that. The second pass resolves a bare
    filename against the directory the *corpus* pairs it with, and only when
    that pairing is unambiguous — an alias map derived from the specs
    themselves, so a document that moves carries its own resolution with it.
    A name the corpus never places stands as written, which still matches the
    `**/`-anchored globs every rule uses today.
    """
    raw = {p.stem: _named_paths(_text(p)) for p in sorted(agents_dir.glob("*.md"))}

    placements: dict = {}
    for paths in raw.values():
        for path in paths:
            if "/" in path:
                placements.setdefault(path.rsplit("/", 1)[1], set()).add(path)
    alias = {base: next(iter(seen))
             for base, seen in placements.items() if len(seen) == 1}

    return {role: {path if "/" in path else alias.get(path, path) for path in paths}
            for role, paths in raw.items()}


# --------------------------------------------------------------------------- #
# fixtures — one install, read-only from here on
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def consumer(tmp_path_factory) -> Path:
    """A real install. Nothing below writes to it, so one is enough."""
    target = tmp_path_factory.mktemp("budget") / "consumer"
    target.mkdir()
    assert install.main(["--into", str(target), "--yes",
                         "--git-mode", "local", "--name", "Budget"]) == 0
    return target


@pytest.fixture(scope="session")
def rules(consumer: Path) -> list:
    return sorted((consumer / ".claude" / "rules").glob("*.md"))


@pytest.fixture(scope="session")
def section_skills(consumer: Path) -> list:
    return [p for p in sorted((consumer / ".claude" / "skills").glob("*/SKILL.md"))
            if _is_section_skill(p)]


@pytest.fixture(scope="session")
def read_sets(consumer: Path) -> dict:
    return _read_sets(consumer / ".claude" / "agents")


@pytest.fixture(scope="session")
def preloads(consumer: Path) -> dict:
    """`{role: [skill name, …]}` — the literal reach of every section skill."""
    return {p.stem: _preloads(p)
            for p in sorted((consumer / ".claude" / "agents").glob("*.md"))}


# --------------------------------------------------------------------------- #
# fail closed — every derived collection below is recognisable first
# --------------------------------------------------------------------------- #
def test_the_install_delivers_something_to_measure(
        consumer: Path, rules: list, section_skills: list):
    """conventions.md §6: assert the derived value is recognisable *before*
    asserting anything about it. An empty rules glob, no section skill
    recognised, or a missing AGENT-CONTEXT.md would make most of this module
    pass while measuring nothing at all."""
    assert rules, "no .claude/rules/*.md in a real install — the layout moved"
    assert section_skills, ("no section skill in a real install — the layout "
                            "moved, or nothing carries `user-invocable: false`")
    assert (consumer / ".aide" / "AGENT-CONTEXT.md").is_file()
    assert sorted((consumer / ".claude" / "agents").glob("*.md")), "no agent specs"


def test_every_role_names_files_the_globs_can_be_evaluated_against(read_sets: dict):
    """The extractor is the load-bearing part of the rule-reach comparison,
    and it is a regex over prose. If it silently stops matching, every scoped
    rule arms nobody and a declaration of `test-writer` fails — but a
    declaration of nothing would pass, so pin the input too."""
    assert read_sets, "no agent specs were read"
    for role, files in read_sets.items():
        assert files, f"{role}: the spec names no file path — the extractor broke"
        for path in files:
            assert "\\" not in path, f"{role}: {path!r} carries a native separator"


def test_some_role_preloads_a_section_skill(preloads: dict, section_skills: list):
    """The `skills:` parser is the load-bearing part of the skill-reach
    comparison. If it silently stops matching, every section skill reaches
    nobody and its declaration fails — but a declaration of nothing would
    pass, so pin the input too."""
    assert preloads, "no agent specs were read"
    assert any(preloads.values()), (
        "no agent spec preloads a skill — the channel is gone, or the "
        "`skills:` parser here stopped seeing it")
    named = {name for names in preloads.values() for name in names}
    assert named & {_skill_name(s) for s in section_skills}, (
        "no preloaded name is a section skill — the two sets do not meet, so "
        "the reach comparison below would compare nothing")


# --------------------------------------------------------------------------- #
# 1. a delivered file declares its reach, and the declaration is true
# --------------------------------------------------------------------------- #
def test_a_delivered_file_declares_the_reach_it_expects(
        rules: list, section_skills: list, read_sets: dict):
    """The declaration is the thing a scope change has to contradict.

    Parametrising over the installed files would need them at collection time,
    before the install exists, so the loop is inside — and each failure names
    its own file.
    """
    for path in rules + section_skills:
        _declared_reach(path, read_sets)  # asserts presence and well-formedness


def test_an_installed_control_file_is_its_source_minus_the_declarations(
        consumer: Path):
    """What reading the declaration from source costs, paid here.

    Before 1.49.3 this module read `reach` off the installed file, and the
    declaration was true of the delivered tree because it *was* the delivered
    tree. Stripping the declarations (issue #205) separates the two copies, so
    the equality has to be asserted rather than enjoyed: every markdown control
    file a consumer receives is its source file with the declaration blocks
    removed — and, for a generated one, the engine section's core appended.
    Anything else the installer did to the bytes on the way in would show up
    here, which is the point: a strip that ate a paragraph, or a render that
    reflowed one. **And a file that stopped being copied at all**, which this
    loop cannot see by itself — it iterates the installed tree, so a missing
    file is simply one it never visits. The count of source control files is
    therefore the other half of the assertion, and the two have to agree.

    The core is read from the consumer's own `.aide/conventions/`, not from
    `core/`, so the two halves of the claim are both taken from the tree under
    test. Text, not raw bytes: an ordinary file is copied with `copy2` and
    keeps the checkout's line endings, so the windows leg compares the same
    content the ubuntu leg does (`install.source_text`'s fold, on both sides).
    """
    checked = 0
    for name in install.ADAPTER_CONTROL:
        directory = consumer / CLAUDE_DIR / name
        if not directory.is_dir():
            continue
        for installed in sorted(directory.rglob("*.md")):
            source = install.source_text(_source_of(installed))
            expected = install.strip_declarations(source)
            sections = install.generated_sections(source)
            if sections:
                cores = []
                for section in sections:
                    engine = consumer.joinpath(*section.split("/"))
                    assert engine.is_file(), (
                        f"{_label(installed)}: names {section}, which the "
                        f"install did not put in the consumer's engine copy")
                    core = install.section_core(install.source_text(engine))
                    assert core is not None, (
                        f"{section}: no closing `Rationale` heading in the "
                        f"installed copy, so it has no core to have delivered")
                    cores.append(core.rstrip("\n"))
                expected = "\n\n".join([expected.rstrip("\n")] + cores) + "\n"
            assert _text(installed) == expected, (
                f"{_label(installed)}: the installed file is not its source "
                f"minus the declarations. The reach this module asserts is "
                f"declared in {_source_of(installed)} and paid in {installed}; "
                f"if the installer now does something else to the bytes, those "
                f"are two files and the declaration says nothing about the one "
                f"a consumer loads.")
            checked += 1

    control = ADAPTER_SOURCE
    expected = sum(1 for name in install.ADAPTER_CONTROL
                   for _ in (control / name).rglob("*.md"))
    assert expected, "no adapter control files — the source layout moved"
    assert checked == expected, (
        f"{checked} of {expected} markdown control files reached the install. "
        f"A file the adapter ships and the installer does not write is a "
        f"delivered file that binds nobody, and every other assertion in this "
        f"module passes over it by never seeing it.")


def test_a_rules_declared_reach_matches_the_roles_its_globs_arm(
        rules: list, read_sets: dict):
    """The assertion #79 did not have.

    `aide-living-documents.md` went out scoped to `items/*.md` and
    `insights.md` — names every one of the six roles reads. It was an unscoped
    rule wearing a `paths:` block, and it cost every spawn, because the only
    thing that could have noticed was a human doing the arithmetic.

    A mismatch is not automatically a bug in the rule: the honest fix is often
    to correct the declaration and re-scope in a separate change. Either way it
    stops being invisible.
    """
    wrong = {}
    for rule in rules:
        declared = _declared_reach(rule, read_sets)
        actual = _arming_roles(rule, read_sets)
        if declared != actual:
            wrong[rule.name] = (sorted(declared), sorted(actual))
    assert not wrong, "\n".join(
        f"{name}: declares {declared}, globs arm {actual}"
        for name, (declared, actual) in sorted(wrong.items()))


def test_a_section_skills_declared_reach_is_the_set_of_roles_that_preload_it(
        section_skills: list, read_sets: dict, preloads: dict):
    """Reach is literal for a skill: the specs whose `skills:` name it.

    Nothing is inferred and nothing is evaluated — the globs on a skill inject
    nothing on a read (issue #85, measured), so the read-set model that
    decides a rule's reach has no bearing here. What can go wrong is exactly
    what this compares: a spec adds or drops a preload and the declaration is
    not updated, or a skill is renamed and a `skills:` entry still says the
    old name — which resolves to nothing, silently, at spawn.
    """
    wrong = {}
    for skill in section_skills:
        declared = _declared_reach(skill, read_sets)
        actual = _preload_reach(skill, preloads)
        if declared != actual:
            wrong[_label(skill)] = (sorted(declared), sorted(actual))
    assert not wrong, "\n".join(
        f"{name}: declares {declared}, preloaded by {actual}"
        for name, (declared, actual) in sorted(wrong.items()))


def test_a_section_skills_declared_triggers_match_the_roles_its_globs_would_arm(
        section_skills: list, read_sets: dict):
    """The interactive half, asserted rather than only printed.

    With no scoped rule left, the glob evaluator would otherwise be reached
    only by the printed table — the #112 review mutated `_glob_to_regex` into
    a pattern that matches nothing and the module stayed green. A skill's
    `<!-- triggers: … -->` line declares which roles' named reads match its
    `paths:` (what a rule with those globs would have armed, and what the
    listing keys on in a human's session); this compares it to the evaluator
    so a widened glob, a narrowed one, or a broken evaluator has something to
    contradict.
    """
    wrong = {}
    for skill in section_skills:
        declared = _declared_reach(skill, read_sets, _TRIGGERS, "triggers")
        actual = _arming_roles(skill, read_sets)
        if declared != actual:
            wrong[_label(skill)] = (sorted(declared), sorted(actual))
    assert not wrong, "\n".join(
        f"{name}: triggers declare {declared}, globs match {actual}"
        for name, (declared, actual) in sorted(wrong.items()))


@pytest.mark.parametrize("glob, path, matches", [
    ("**/tests/**/*.py", "a/tests/b/c.py", True),
    ("**/tests/**/*.py", "tests/c.py", True),
    ("**/tests/**/*.py", "a/b.py", False),
    ("**/test_*.py", "tests/test_x.py", True),
    ("**/test_*.py", "tests/sub/test_x.py", True),
    ("**/test_*.py", "tests/x_test.py", False),
    ("**/x.md", "x.md", True),
    ("**/x.md", "d/e/x.md", True),
    ("**/items/*.md", "docs/aide/items/001-x.md", True),
    ("**/items/*.md", "docs/aide/items/sub/001-x.md", False),   # `*` never crosses `/`
    ("src/*.py", "src/a/b.py", False),
    ("src/*.py", "src/b.py", True),
    ("a?c.md", "abc.md", True),
    ("a?c.md", "a/c.md", False),
])
def test_the_glob_compiler_reads_a_paths_glob_the_way_the_runtime_does(
        glob: str, path: str, matches: bool):
    """`_glob_to_regex` is hand-rolled (see its docstring for why), so it is
    pinned directly: `**` spans directories, `*` and `?` never cross `/`."""
    assert bool(_glob_to_regex(glob).match(path)) is matches, (glob, path)


# --------------------------------------------------------------------------- #
# 2. frontmatter that stopped parsing fails loudly, the way its carrier fails
# --------------------------------------------------------------------------- #
def test_a_scoped_rule_that_lost_its_delimiter_is_read_as_arming_every_role(
        rules: list, section_skills: list, read_sets: dict, tmp_path: Path):
    """The BOM case for a rule, exercised rather than described.

    A Windows editor prepends `\\ufeff`, `---` is no longer at byte 0, and the
    runtime loads a scoped rule into every context — no error, no diff worth
    reading, a cost on every spawn. `_frontmatter` must report that as "no
    globs" and `_arming_roles` must turn no globs into every role, or the
    check above would sail past the exact regression it exists for.

    No shipped rule carries `paths:` today (1.27.0 moved both scoped rules
    into section skills), so the block under a BOM is taken from whichever
    delivered file has one — a rule first, else a section skill's, which is
    the same `paths:` grammar. What is under test is the evaluator's reading
    of a scoped block behind a BOM, not which file it came from.
    """
    scoped = [p for p in rules + section_skills if _globs(p)]
    assert scoped, "no delivered file with `paths:` to corrupt — the premise is gone"

    victim = scoped[0]
    mangled = tmp_path / "mangled-rule.md"
    mangled.write_bytes(b"\xef\xbb\xbf" + victim.read_bytes())
    assert _globs(victim), "the original parses as scoped"
    assert _globs(mangled) == [], f"{_label(victim)}: a BOM left the globs readable"
    assert _arming_roles(mangled, read_sets) == set(read_sets)


def test_a_rule_with_no_paths_block_is_counted_as_arming_every_role(
        rules: list, read_sets: dict):
    """The same rule for the legitimate case, so the floor below is complete:
    an unscoped rule is not "unscoped therefore uncounted"."""
    unscoped = [r for r in rules if not _globs(r)]
    assert unscoped, "every rule is scoped — the always-on floor lost a member"
    for rule in unscoped:
        assert _arming_roles(rule, read_sets) == set(read_sets)


def test_a_section_skill_that_lost_its_delimiter_reaches_nobody(
        section_skills: list, preloads: dict, tmp_path: Path):
    """The BOM case for a skill, which fails the other way round.

    A rule with unreadable frontmatter arms everywhere; a skill with
    unreadable frontmatter has no `name:` the runtime can resolve, so it is
    skipped at preload and absent from the listing — the section reaches
    nobody, and nothing says so. Two things are pinned: that every *installed*
    section skill is readable from byte 0 (the install itself must not have
    added a BOM — `install.py` reads with `utf-8-sig` and could write one back)
    with a `name:` that equals its directory; and that the evaluator reports a
    BOM'd copy as reaching nobody, so a declared reach of `test-writer` would
    fail loudly against it rather than pass by default.

    One asymmetry worth knowing while reading this: a file the strip rewrites
    is decoded `utf-8-sig` and re-encoded `utf-8`, so a BOM in the source is
    **normalised away for a declaring file and copied through for any other**.
    That is a side effect of the strip, not a policy — the assertion above is
    on the installed bytes either way, so a BOM that survives is caught here
    whichever kind of file carried it.
    """
    for skill in section_skills:
        raw = skill.read_bytes()
        assert not raw.startswith(codecs.BOM_UTF8), f"{_label(skill)}: the install added a BOM"
        assert _skill_name(skill) == skill.parent.name, (
            f"{_label(skill)}: `name:` does not resolve to its directory — a "
            f"`skills:` entry naming it preloads nothing")
        assert _preload_reach(skill, preloads), (
            f"{_label(skill)}: no spec preloads it — the premise is gone")

        mangled = tmp_path / skill.parent.name / "SKILL.md"
        mangled.parent.mkdir()
        mangled.write_bytes(b"\xef\xbb\xbf" + raw)
        assert _skill_name(mangled) is None, f"{_label(skill)}: a BOM left the name readable"
        assert _preload_reach(mangled, preloads) == set()


# --------------------------------------------------------------------------- #
# 3. the always-on floor
# --------------------------------------------------------------------------- #
def _floor(consumer: Path, rules: list) -> dict:
    """`{consumer-relative path: content bytes}` for what every spawn pays.

    `AGENT-CONTEXT.md` is linked into the runtime's default context and every
    unscoped rule loads unconditionally; together they are the constant term of
    the budget, multiplied by the number of spawns a queue makes. A section
    skill is deliberately not here: it is paid per preloading role, and its
    description in the listing is the only unconditional part of it.
    """
    floor = {".aide/AGENT-CONTEXT.md": _size(consumer / ".aide" / "AGENT-CONTEXT.md")}
    for rule in rules:
        if not _globs(rule):
            floor[f".claude/rules/{rule.name}"] = _size(rule)
    return floor


def test_the_always_on_floor_matches_its_recorded_pin(consumer: Path, rules: list):
    """Not a budget cap and not a ratchet — it fails in both directions.

    The floor is paid on every spawn of every role, so it moving is a
    consumer-visible change, and the only thing wanted here is that it moves on
    purpose. Growing it is sometimes right; doing so without noticing is what
    #79 did.
    """
    measured = _floor(consumer, rules)
    assert measured == FLOOR_PIN["files"], (
        "the always-on floor moved.\n"
        f"  measured: {measured}\n"
        f"  pinned:   {FLOOR_PIN['files']}\n"
        "Every spawn pays this, so it is a consumer-visible change: bump "
        "core/VERSION, add the CHANGELOG entry, and update FLOOR_PIN in this "
        "file to the new numbers and that version — deliberately, in the same "
        "commit.")


#: A released section heading, `## [1.25.4] — 2026-08-30`. Anchored, so the
#: unversioned installer section and a prose mention of a version both fail to
#: match.
_RELEASE_HEADING = re.compile(r"^## \[(?P<version>\d+\.\d+\.\d+)\][^\n]*$", re.M)
#: How this repo records a floor move, established across 1.25.1 → 1.25.4:
#: "the always-on floor moves from X to Y content bytes". Only the *new* total
#: is read — the old one is the previous release's number.
_FLOOR_TOTAL = re.compile(r"to ([\d,]+)\s+content bytes")


def _changelog_sections() -> dict:
    """`{version: that release's entry text}` from CHANGELOG.md."""
    text = (FRAMEWORK_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    marks = list(_RELEASE_HEADING.finditer(text))
    return {m.group("version"): text[m.end():(marks[i + 1].start()
                                              if i + 1 < len(marks) else len(text))]
            for i, m in enumerate(marks)}


def _semver(version: str) -> tuple:
    parts = version.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts), (
        f"{version!r} is not a SemVer triple")
    return tuple(int(p) for p in parts)


def test_the_pinned_floor_names_the_release_that_last_moved_it():
    """The pin's version is what makes it an audit trail rather than a number.

    **The contract, in three clauses.** `FLOOR_PIN["version"]` names the
    release in which the pinned bytes were last measured, so:

    1. CHANGELOG.md carries a `## [<that version>]` heading of its own —
       exact heading match, not a substring, so a typo'd or never-released
       version cannot borrow another release's mention of it;
    2. that version is at or behind `core/VERSION`, since a floor cannot have
       moved in a release this tree has not reached;
    3. **that release's entry states the total the pin sums to**, in the form
       this repo has used since 1.25.1 — "the always-on floor moves from X to
       N content bytes".

    Clause 3 is the one that binds. Clauses 1 and 2 hold for every version ever
    released, so a pin left at a stale release passes them both; only "the
    release you named is the one that recorded *these* bytes" catches the
    shape actually worth catching — the bytes moved, the pin followed, and the
    version stayed behind, leaving the audit trail pointing at a release that
    describes a different floor.

    It also stays quiet when it should: a release that does not touch the floor
    leaves the pin — bytes *and* version — exactly as it was, so this asserts
    nothing about `core/VERSION` beyond clause 2 and forces no churn.
    """
    version = FLOOR_PIN["version"]
    total = sum(FLOOR_PIN["files"].values())
    sections = _changelog_sections()

    assert version in sections, (
        f"FLOOR_PIN records version {version}, for which CHANGELOG.md has no "
        f"`## [{version}]` heading — a floor change no release describes. "
        f"Released headings found: {sorted(sections)}")

    current = (FRAMEWORK_ROOT / "core" / "VERSION").read_text(
        encoding="utf-8-sig").strip()
    assert _semver(version) <= _semver(current), (
        f"FLOOR_PIN records version {version}, which is ahead of core/VERSION "
        f"({current}) — the floor cannot have moved in a release this tree "
        f"has not reached")

    recorded = {m.group(1).replace(",", "") for m in _FLOOR_TOTAL.finditer(
        sections[version])}
    assert str(total) in recorded, (
        f"FLOOR_PIN sums to {total:,} content bytes and names release "
        f"{version}, whose CHANGELOG entry records {sorted(recorded) or 'no'} "
        f"floor total.\n"
        f"The version is the release the floor last moved in, not the release "
        f"that happens to be current: either this entry should say "
        f"'the always-on floor moves from … to {total:,} content bytes', or "
        f"FLOOR_PIN['version'] still belongs to an earlier release and the "
        f"bytes were changed without one.")


# --------------------------------------------------------------------------- #
# the diagnostic — printed, never asserted on
# --------------------------------------------------------------------------- #
def test_the_arming_table_is_printed(
        consumer: Path, rules: list, section_skills: list, read_sets: dict,
        preloads: dict, capsys):
    """Prints the table #78 built by hand from eleven session transcripts.

    Printed through `capsys.disabled()`, so it lands on every run rather than
    only under `-s`. Deliberate, and the one place this module is unusual: the
    defect being closed is "the number moved and nobody noticed", and a number
    visible only behind a flag nobody passes reproduces it. Sixteen lines is
    the price of the budget being in front of whoever reads the CI log.

    Bytes, not tokens: the ratio is a property of a tokeniser this repo does
    not ship, and quoting a token count would invite exactly the threshold
    assertion the module docstring refuses. A section skill is costed at what
    a preload injects — body only, comments stripped — and its glob
    evaluation is printed beside it as the *interactive trigger*: the roles
    whose named reads would match if this were a rule, which is what the
    listing keys on in a human's session and what the loop never pays
    (asserted against the skill's `<!-- triggers -->` line above; printed
    here so the two halves sit side by side).

    **This one is honestly a printer**, and says so rather than dressing up.
    It once carried two assertions — that every rule appeared in the arming
    table, and that a rule arming nobody was a scoped one — and both were
    tautologies: the table is *built* by iterating the rules, and "arms nobody"
    is what having globs means. An assertion that cannot fail is worse than
    none, because it reads as coverage. What is actually checked here is what
    printing cannot do for itself: that nothing summed to zero, which is how a
    truncated read or an emptied file would show up as a quiet table of noughts
    rather than a failure. The properties worth asserting are the three above,
    and they are asserted there.
    """
    floor = _floor(consumer, rules)
    floor_total = sum(floor.values())
    armed = {rule.name: _arming_roles(rule, read_sets) for rule in rules}
    scoped_size = {rule.name: _size(rule) for rule in rules if _globs(rule)}
    skill_size = {_label(s): _preload_size(s) for s in section_skills}
    preloaded = {_label(s): _preload_reach(s, preloads) for s in section_skills}
    triggered = {_label(s): _arming_roles(s, read_sets) for s in section_skills}

    lines = ["", "structural budget — content bytes of the delivered tree", ""]
    for path, size in sorted(floor.items()):
        lines.append(f"  floor   {size:>6}  {path}")
    lines.append(f"  floor   {floor_total:>6}  TOTAL, paid on every spawn")
    lines.append("")
    for name, size in sorted(scoped_size.items()):
        roles = sorted(armed[name]) or ["(nobody)"]
        lines.append(f"  scoped  {size:>6}  {name} -> {', '.join(roles)}")
    for name, size in sorted(skill_size.items()):
        roles = sorted(preloaded[name]) or ["(nobody)"]
        trigger = sorted(triggered[name]) or ["(nobody)"]
        lines.append(f"  skill   {size:>6}  {name} -> preloaded by {', '.join(roles)}"
                     f"  [interactive trigger: {', '.join(trigger)}]")
    lines.append("")
    specs = {}
    for role in sorted(read_sets):
        specs[role] = _size(consumer / ".claude" / "agents" / f"{role}.md")
        extra = sum(size for name, size in scoped_size.items() if role in armed[name])
        skills = sum(size for name, size in skill_size.items() if role in preloaded[name])
        lines.append(f"  spawn   {floor_total + specs[role] + extra + skills:>6}  {role} "
                     f"(floor {floor_total} + spec {specs[role]} + rules {extra} "
                     f"+ skills {skills})")
    lines.append("")
    with capsys.disabled():
        print("\n".join(lines))

    empty = ([path for path, size in floor.items() if size <= 0]
             + [name for name, size in scoped_size.items() if size <= 0]
             + [name for name, size in skill_size.items() if size <= 0]
             + [f"{role}.md" for role, size in specs.items() if size <= 0])
    assert floor_total > 0 and not empty, (
        f"the table above costed {empty} at zero bytes — a delivered file that "
        f"measures empty is a broken read or a broken install, not a saving")
