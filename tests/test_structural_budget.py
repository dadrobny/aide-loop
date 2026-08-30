"""What a rule *reaches*, asserted; what it *costs*, printed.

The gap this closes (issue #84). Issue #78 asked a token-budget question and
answered it by grepping eleven stored session transcripts of a consumer. Issue
#79 then changed that budget substantially and in the wrong direction — the
compaction it introduced saves ~30.8k, the three `.claude/rules/` files it
introduced cost ~46k to ~57k across an eight-item queue — and nobody noticed
until a reviewer did the arithmetic by hand. Nothing in the suite knew what a
token was, and nothing knew which contexts a rule loads into.

**The half that is measurable is structural**, and it is a pure function of the
installed tree: a rule's `paths:` globs, evaluated against the files each agent
spec names. **The half that is not is behavioural** — whether an agent follows a
pointer once the file is in front of it. This module stays entirely on the first
side of that line.

**It asserts on structure and prints the cost.** `assert budget < 150_000` would
be a spreadsheet wearing a test's clothes: it bakes in a spawn model and a
bytes-per-token ratio as facts, fails on any prose edit, and gets ratcheted
upward instead of investigated. So the byte totals below are diagnostic output
(`pytest -s`, or the failure text), and the assertions are three properties a
commit can silently break:

1. **A rule declares the reach it expects** (`<!-- reach: … -->`), and the
   declaration matches what its globs actually arm. `aide-living-documents.md`
   shipped in #79 scoped to names every role reads — an unscoped rule wearing a
   `paths:` block, invisible because nothing compared the two.
2. **A rule that loses its frontmatter arms everywhere.** A BOM from a Windows
   editor makes the `---` delimiter unrecognisable, and the runtime reads a
   scoped rule as an unscoped one. The evaluator has to report that as "0 globs,
   arms every role" rather than skipping the file.
3. **The always-on floor does not move without a deliberate edit.**
   `AGENT-CONTEXT.md` plus every unscoped rule is paid on every single spawn, so
   that number moving is as consumer-visible as any other change.

**Mechanism-agnostic on purpose.** Issue #85 may move this content out of
`paths:`-scoped rules and into skills. Everything here is expressed as "a
delivered file, its globs, and the roles that reach it", so a change of carrier
should move the declarations, not rewrite the tests.

Measured against a **real install** — `.claude/rules/`, `.claude/agents/` and
`.aide/AGENT-CONTEXT.md` at the paths a consumer's runtime actually loads them
from — rather than against this repo's source layout, which is not what anybody
pays for.
"""
from __future__ import annotations

import codecs
import re
import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)


# --------------------------------------------------------------------------- #
# the recorded floor
#
# A constant rather than a data file: the point is that moving it takes a
# deliberate edit a reviewer sees, and a dict literal in the diff says that as
# plainly as a JSON file would, with nothing extra to keep in step.
#
# Per-file, so a failure names which half moved. `version` is the release the
# floor last moved in, and is asserted against CHANGELOG.md below — a floor
# change reaches consumers, so it has to arrive with a version that says so.
# --------------------------------------------------------------------------- #
FLOOR_PIN = {
    "version": "1.25.1",
    "files": {
        ".aide/AGENT-CONTEXT.md": 4169,
        ".claude/rules/aide-command-hygiene.md": 2155,
    },
}


# --------------------------------------------------------------------------- #
# reading the delivered files
# --------------------------------------------------------------------------- #
def _text(path: Path) -> str:
    """The file as a runtime reads it, normalised for measurement.

    `utf-8-sig` and CRLF folding for the same reason everywhere else in this
    suite: this repo has no `.gitattributes` `text eol=lf` pin, so a Windows
    checkout hands back CRLF and the installer's `utf-8-sig` may prepend a BOM.
    Neither is content, and a byte pin that counted them would fail on one CI
    leg and hold on the other.
    """
    return path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")


def _size(path: Path) -> int:
    """Content bytes, after the normalisation above. UTF-8, so a multi-byte
    character counts as the bytes it is — closer to a token than a character
    count, without pretending to be one."""
    return len(_text(path).encode("utf-8"))


def _frontmatter(path: Path):
    """The rule's YAML block, or ``None`` — which is the *loud* answer here.

    A rule with no frontmatter is unscoped and loads into every context. That
    is a legitimate state (`aide-command-hygiene.md`) and also the failure mode
    a BOM produces, so callers must treat ``None`` as "arms everywhere" rather
    than as "nothing to check". The whole point of assertion 2.

    Read from bytes and **not** with `utf-8-sig`, unlike `_text` above: the
    other readers in this suite strip a BOM so they can report on the file
    behind it, but this one has to see what the runtime sees. With `\\ufeff` in
    front, `---` is not at byte 0, the block does not parse, and the rule loads
    everywhere — so stripping it here would hide the one thing worth catching.
    CRLF is still folded, because that is a checkout artefact the runtime
    handles and this repo has no `.gitattributes` pin against.
    """
    raw = path.read_bytes()
    if raw.startswith(codecs.BOM_UTF8):
        return None
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    return None if end == -1 else text[4:end]


def _globs(path: Path) -> list:
    """The `paths:` globs of a delivered rule; empty for an unscoped one."""
    block = _frontmatter(path)
    if block is None:
        return []
    return [line.strip().lstrip("- ").strip('"\'')
            for line in block.splitlines() if line.strip().startswith("- ")]


#: `<!-- reach: … -->`, the whole rest of that line. A prose note goes on the
#: lines below it inside the same comment and is ignored — the declaration is
#: meant to be one glanceable line, and the reasoning is meant to be long.
_REACH = re.compile(r"<!--\s*reach:[ \t]*(?P<roles>[^\n]*)")


def _declared_reach(path: Path, roles) -> set:
    """The roles a rule says it expects to arm for, as a set.

    ``all`` is the shorthand for every role — spelling six names out in a file
    that means "everyone" invites one of them to go stale on a rename.
    """
    match = _REACH.search(_text(path))
    assert match, (
        f"{path.name}: no `<!-- reach: … -->` declaration. Every delivered rule "
        f"states the roles it expects to arm for, so that a change of scope has "
        f"something to contradict; see this module's docstring.")
    raw = match.group("roles").strip()
    raw = raw[:-3].strip() if raw.endswith("-->") else raw
    assert raw, f"{path.name}: empty reach declaration"
    if raw == "all":
        return set(roles)
    declared = {part.strip() for part in raw.split(",") if part.strip()}
    unknown = declared - set(roles)
    assert not unknown, f"{path.name}: reach names no such role: {sorted(unknown)}"
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
def read_sets(consumer: Path) -> dict:
    return _read_sets(consumer / ".claude" / "agents")


# --------------------------------------------------------------------------- #
# fail closed — every derived collection below is recognisable first
# --------------------------------------------------------------------------- #
def test_the_install_delivers_something_to_measure(consumer: Path, rules: list):
    """conventions.md §6: assert the derived value is recognisable *before*
    asserting anything about it. An empty rules glob or a missing
    AGENT-CONTEXT.md would make most of this module pass while measuring
    nothing at all."""
    assert rules, "no .claude/rules/*.md in a real install — the layout moved"
    assert (consumer / ".aide" / "AGENT-CONTEXT.md").is_file()
    assert sorted((consumer / ".claude" / "agents").glob("*.md")), "no agent specs"


def test_every_role_names_files_the_globs_can_be_evaluated_against(read_sets: dict):
    """The extractor is the load-bearing part of the reach comparison, and it
    is a regex over prose. If it silently stops matching, every scoped rule
    arms nobody and a declaration of `test-writer` fails — but a declaration
    of nothing would pass, so pin the input too."""
    assert read_sets, "no agent specs were read"
    for role, files in read_sets.items():
        assert files, f"{role}: the spec names no file path — the extractor broke"
        for path in files:
            assert "\\" not in path, f"{role}: {path!r} carries a native separator"


# --------------------------------------------------------------------------- #
# 1. a rule declares its reach, and the declaration is true
# --------------------------------------------------------------------------- #
def test_a_rule_declares_the_reach_it_expects(consumer: Path, rules: list,
                                              read_sets: dict):
    """The declaration is the thing a scope change has to contradict.

    Parametrising over the installed files would need them at collection time,
    before the install exists, so the loop is inside — and each failure names
    its own rule.
    """
    for rule in rules:
        _declared_reach(rule, read_sets)  # asserts presence and well-formedness


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


# --------------------------------------------------------------------------- #
# 2. frontmatter that stopped parsing arms everywhere, loudly
# --------------------------------------------------------------------------- #
def test_a_scoped_rule_that_lost_its_delimiter_is_read_as_arming_every_role(
        rules: list, read_sets: dict, tmp_path: Path):
    """The BOM case, exercised rather than described.

    A Windows editor prepends `\\ufeff`, `---` is no longer at byte 0, and the
    runtime loads a scoped rule into every context — no error, no diff worth
    reading, a cost on every spawn. `_frontmatter` must report that as "no
    globs" and `_arming_roles` must turn no globs into every role, or the two
    checks above would sail past the exact regression they exist for.
    """
    scoped = [r for r in rules if _globs(r)]
    assert scoped, "no scoped rule to corrupt — the premise is gone"

    victim = scoped[0]
    mangled = tmp_path / victim.name
    mangled.write_bytes(b"\xef\xbb\xbf" + victim.read_bytes())
    assert _globs(victim), "the original parses as scoped"
    assert _globs(mangled) == [], f"{victim.name}: a BOM left the globs readable"
    assert _arming_roles(mangled, read_sets) == set(read_sets)


def test_a_rule_with_no_paths_block_is_counted_as_arming_every_role(
        rules: list, read_sets: dict):
    """The same rule for the legitimate case, so the floor below is complete:
    an unscoped rule is not "unscoped therefore uncounted"."""
    unscoped = [r for r in rules if not _globs(r)]
    assert unscoped, "every rule is scoped — the always-on floor lost a member"
    for rule in unscoped:
        assert _arming_roles(rule, read_sets) == set(read_sets)


# --------------------------------------------------------------------------- #
# 3. the always-on floor
# --------------------------------------------------------------------------- #
def _floor(consumer: Path, rules: list) -> dict:
    """`{consumer-relative path: content bytes}` for what every spawn pays.

    `AGENT-CONTEXT.md` is linked into the runtime's default context and every
    unscoped rule loads unconditionally; together they are the constant term of
    the budget, multiplied by the number of spawns a queue makes.
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


def test_the_pinned_floor_names_a_version_the_changelog_records():
    """The pin's version is what makes it an audit trail rather than a number.

    Updating the bytes without moving the version is the shape this catches:
    the floor changed, a consumer will receive it, and nothing anywhere says
    so.
    """
    changelog = (FRAMEWORK_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    version = FLOOR_PIN["version"]
    assert f"[{version}]" in changelog or f" {version}" in changelog, (
        f"FLOOR_PIN records version {version}, which CHANGELOG.md does not "
        f"mention — a floor change that no release describes")


# --------------------------------------------------------------------------- #
# the diagnostic — printed, never asserted on
# --------------------------------------------------------------------------- #
def test_the_arming_table_accounts_for_every_rule_and_role(
        consumer: Path, rules: list, read_sets: dict, capsys):
    """Prints the table #78 built by hand from eleven session transcripts.

    Printed through `capsys.disabled()`, so it lands on every run rather than
    only under `-s`. Deliberate, and the one place this module is unusual: the
    defect being closed is "the number moved and nobody noticed", and a number
    visible only behind a flag nobody passes reproduces it. Sixteen lines is
    the price of the budget being in front of whoever reads the CI log.

    Bytes, not tokens: the ratio is a property of a tokeniser this repo does
    not ship, and quoting a token count would invite exactly the threshold
    assertion the module docstring refuses.

    The assertion is only coverage — every rule placed, every role costed —
    so the numbers can move freely and the shape cannot go missing.
    """
    floor = _floor(consumer, rules)
    floor_total = sum(floor.values())
    armed = {rule.name: _arming_roles(rule, read_sets) for rule in rules}
    scoped_size = {rule.name: _size(rule) for rule in rules if _globs(rule)}

    lines = ["", "structural budget — content bytes of the delivered tree", ""]
    for path, size in sorted(floor.items()):
        lines.append(f"  floor   {size:>6}  {path}")
    lines.append(f"  floor   {floor_total:>6}  TOTAL, paid on every spawn")
    lines.append("")
    for name, size in sorted(scoped_size.items()):
        roles = sorted(armed[name]) or ["(nobody)"]
        lines.append(f"  scoped  {size:>6}  {name} -> {', '.join(roles)}")
    lines.append("")
    for role in sorted(read_sets):
        spec = _size(consumer / ".claude" / "agents" / f"{role}.md")
        extra = sum(size for name, size in scoped_size.items() if role in armed[name])
        lines.append(f"  spawn   {floor_total + spec + extra:>6}  {role} "
                     f"(floor {floor_total} + spec {spec} + rules {extra})")
    lines.append("")
    with capsys.disabled():
        print("\n".join(lines))

    assert set(armed) == {r.name for r in rules}, "a rule went uncosted"
    for name, roles in armed.items():
        assert roles or name in scoped_size, f"{name}: unscoped and armed nobody"
    assert floor_total > 0 and all(v > 0 for v in floor.values())
