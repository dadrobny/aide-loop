"""One reading of the adapter's **delivered files**, for every suite that has one.

A delivered file is what ADAPTER-SPEC §7 makes conformant: the unscoped
`.claude/rules/*.md`, and the **section skills** under
`.claude/skills/<name>/SKILL.md` (`user-invocable: false`, preloaded by the
agent specs whose `skills:` frontmatter names them). Four modules read them —

- `adapters/claude/tests/test_rules.py`      — the envelope and the preload channel
- `adapters/claude/tests/test_rule_pins.py`  — the quoted statements, both directions
- `tests/test_structural_budget.py`          — declared reach, and cost against a real install
- `tests/test_fixture_consumer.py`           — the files as an install leaves them

— and each carried its own copy of the same parser set: a frontmatter
splitter, a scalar/list reader for `name:`, `user-invocable:`, `paths:` and
`skills:`, the section-skill recogniser, a `_label` and an HTML-comment
stripper (issue #113). A fifth, `tests/test_floor_pins.py`, holds the engine's
own always-on page to its sections the way `test_rule_pins.py` holds the
adapter's files, and so reads a pin with the same `normalise` (issue #194).

**Why one copy now.** The duplication was tolerable while the rules it encodes
held still. In 1.42.0 the recognition rule moved — a `<!-- pins:` block stopped
being a second sufficient signal — and the edit had to land in four places in
one commit, leaving three modules carrying a comment that dated the same change
in three different wordings. That is drift in its mildest form, and the next
move of the rule would have four places to get right. The rule is stated once
in `CLAUDE.md`; it is now read once here.

**The one intentional difference, as a flag.** `tests/test_structural_budget.py`
has to see the frontmatter *the runtime sees*: with a BOM in front of it, `---`
is not at byte 0, the block does not parse, and a scoped rule silently arms
every context while a section skill loses the `name:` a preload resolves.
Reporting on the file behind the BOM would hide the one thing worth catching.
The other three read the source or a fresh copy of it, where a BOM is an
authoring accident to *report on* — so they read behind it. That is
`REFUSES_BOM` against `STRIPS_BOM` below; there is no default, because the
choice is the caller's and getting it silently wrong is the failure this module
would otherwise introduce. `text()` is BOM-insensitive under either reader: it
is what a file *says*, used for measurement and comment scanning, and no
delimiter is at stake in it.

**Nothing in here asserts.** pytest rewrites assertions in test modules only, so
a failure raised here would print without introspection and name this file
rather than the check that cared; and these functions run at collection time,
where an assertion turns an unparseable file into a collection error instead of
one red test. Every reader returns the honest answer — `None`, or an empty list
— and the caller decides what that means: for a rule, "loads into every
context"; for a skill, "reaches nobody".

**The generated half is a pointer, not a copy.** Since 1.47.0 a delivered file
may be *rendered* at install time from the engine section it names, instead of
being authored (issue #109) — and the grammar of that (`<!-- generated-from:
… -->`, the `Rationale` cut, the wrapper) lives in `install.py`, because the
installer applies it inside a consumer where `tests/` does not exist.
`generated_from`, `is_generated`, `rendered` and `rendered_body` below only
point at it. Same one-reading rule as everything else here; the copy simply
had to sit on the other side of the boundary.

**How the adapter suite reaches it.** `adapters/claude/tests/` puts the
framework root on `sys.path` to `import install` already; reaching this module
adds `tests/` the same way. This module now adds the framework root itself as
well, since it imports `install` for the readings above and two of its callers
had no reason to. A repo-root module was the alternative and the root is a
curated surface, so the shared reader lives with the suite that owns the
broadest view of an install. Stdlib only, no pytest import: this is a parser.
"""
from __future__ import annotations

import codecs
import re
import sys
from pathlib import Path

#: The framework root, put on `sys.path` here rather than by every importer:
#: two of the four callers reach this module without needing `install`
#: themselves, and a shared reader that depends on its caller's path setup is
#: the drift this module exists to end.
FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
if str(FRAMEWORK_ROOT) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)

#: The engine the generated delivered files are rendered from.
CORE_DIR = FRAMEWORK_ROOT / "core"

#: The frontmatter key that makes a `SKILL.md` a section skill. One key, since
#: 1.42.0 — see `Reader.is_section_skill`.
SECTION_SKILL_KEY = "user-invocable"

#: Any HTML comment. A check on what a role actually receives has to strip
#: these, or a pin would satisfy itself from its own declaration — and a
#: preload strips them too, which is why a comment addressed to an *editor* of
#: the source file costs the loop nothing even before the install drops it
#: (`strip_declarations` below).
COMMENT = re.compile(r"<!--.*?-->", re.S)


def label(path: Path) -> str:
    """A test id and a failure name: `aide-test-hygiene` for a skill, the
    filename for a rule — `SKILL.md` alone would name every skill the same."""
    return path.parent.name if path.name == "SKILL.md" else path.name


def keys(block) -> list:
    """Top-level frontmatter keys, in order. A tiny hand parser, not PyYAML —
    the suite is stdlib + pytest only, and these blocks are one level deep."""
    if block is None:
        return []
    return [line.split(":", 1)[0] for line in block.splitlines()
            if line and not line[0].isspace() and ":" in line]


def scalar(block, key: str):
    """The value of a one-line ``key: value`` frontmatter entry, or ``None``.

    The key is matched case-sensitively and at column 0, which is what the
    runtime resolves; the value is returned stripped, and callers that compare
    it case-fold their side (`user-invocable: False` is valid YAML and hides
    the skill just the same).
    """
    if block is None:
        return None
    match = re.search(rf"^{re.escape(key)}:[ \t]*(?P<value>[^\n]*)$", block, re.M)
    return match.group("value").strip() if match else None


def sequence(block, key: str) -> list:
    """The items of a ``key:`` block list (or a ``[a, b]`` flow list)."""
    if block is None:
        return []
    match = re.search(rf"^{re.escape(key)}:[ \t]*(?P<inline>[^\n]*)\n"
                      rf"(?P<items>(?:[ \t]+-[^\n]*\n?)*)", block + "\n", re.M)
    if not match:
        return []
    inline = match.group("inline").strip()
    if inline.startswith("[") and inline.endswith("]"):
        return [x.strip().strip("\"'") for x in inline[1:-1].split(",") if x.strip()]
    return [line.strip().lstrip("- ").strip("\"'")
            for line in match.group("items").splitlines() if line.strip().startswith("-")]


def glob_list(block) -> list:
    """Every `- ` item in a frontmatter block: a delivered file's `paths:`.

    Every item in the block, not only those under `paths:`, because `paths:` is
    the only key that carries a list in these files — `test_rules.py` holds a
    rule to exactly that key, so a second list would fail there rather than be
    silently mixed in here.
    """
    if block is None:
        return []
    return [line.strip().lstrip("- ").strip('"\'')
            for line in block.splitlines() if line.strip().startswith("- ")]


def strip_comments(text: str) -> str:
    """The body as a preload injects it: HTML comments removed."""
    return COMMENT.sub("", text)


#: The narrower strip an **install** applies: the `pins` / `reach` /
#: `triggers` declarations alone, which are assertions addressed to this
#: repository's suite and so have no reader in a consumer's tree. Pointed at
#: rather than re-derived, for the same reason `section_core` is — the
#: installer has to apply the rule inside a consumer, where `tests/` does not
#: exist, so `install.py` owns the grammar and this is the pointer (issue
#: #205). Two strips, deliberately different: `strip_comments` above is what a
#: *preload* does to a body, and would delete a comment written for a reader.
strip_declarations = install.strip_declarations


#: Emphasis and code markers. Dropped on both sides, so bolding a clause in one
#: copy and not the other is not a failure, while rewording it still is.
_MARKERS = str.maketrans("", "", "*_`")


def normalise(text: str) -> str:
    """The comparable form of a passage: what it says, not how it is set.

    The one reading of a **pin** — a sentence quoted from a section into a
    copy of it, asserted on both sides. `adapters/claude/tests/test_rule_pins.py`
    holds the adapter's delivered files to their sections with it, and
    `tests/test_floor_pins.py` holds the engine's `AGENT-CONTEXT.md` to its
    sections with it (issue #194); two normalisers would let one copy pass a
    reword the other catches.

    Four transforms, each chosen to absorb a *typographic* difference between
    two copies of one sentence and nothing more:

    1. **A markdown table row is de-piped.** `| ⏸️ | Deferred | 2 |` becomes
       `⏸️ Deferred 2`, so a vocabulary the engine states as a table can be
       quoted as the phrase a rule states it in. Only a line that both starts
       and ends with `|` is treated this way — a prose `||` is untouched, which
       matters because "never chain with `&&`, `||` or `;`" is itself a pin.
    2. **Runs of whitespace collapse**, so a reflow across a different line
       width is not a change.
    3. **`*`, `_` and `` ` `` are dropped**, so bold/italic/code emphasis may
       differ between the two copies. A quoted identifier survives as its own
       text (`.as_posix()`), which is the load-bearing part.
    4. **Case is folded**, because whether a quoted clause starts a sentence is
       a property of where it was placed, not of what it says.

    Deliberately NOT normalised: punctuation, dashes, word order, and every
    other content-bearing byte. `test_rule_pins.py`'s
    `test_the_normaliser_still_sees_a_reword` holds that line — a normaliser
    loose enough to let a reworded sentence pass would turn both pin modules
    into tests that cannot fail.
    """
    rows = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if len(line) > 1 and line.startswith("|") and line.endswith("|"):
            line = line[1:-1].replace("|", " ")
        rows.append(line)
    return " ".join(" ".join(rows).translate(_MARKERS).split()).casefold()


def split_text(text: str) -> tuple:
    """``(frontmatter_or_None, body)`` of already-decoded text.

    The delimiter half of `Reader.split`, without the BOM policy — there is no
    BOM left to have a policy about by the time a caller holds a string. It is
    separate so the same reading serves a file on disk and the *rendered* form
    of a generated one, which never touches a disk in this repo.
    """
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    return (None, text) if end == -1 else (text[4:end], text[end + 5:])


# -- the generated delivered files ----------------------------------------- #
# One reading, and it is not written here: `install.py` owns the grammar,
# because the installer has to apply it inside a consumer where `tests/` does
# not exist. These are pointers at it, so the four modules below reach it the
# way they already reach `install` (issue #109).
def generated_from(path: Path) -> list:
    """The engine sections a delivered file declares, or ``[]`` for a copy.

    ``[]`` is the honest answer for every hand-curated file, which is most of
    them: it means "this body is authored here", and the pins are what hold it
    to its section.
    """
    return install.generated_sections(install.source_text(path))


def is_generated(path: Path) -> bool:
    """Whether an install renders this file rather than copying it."""
    return bool(generated_from(path))


def rendered(path: Path) -> str:
    """The text an install writes for a generated file — its delivered form.

    Raises `install.GenerationError` for a file that declares a section the
    engine does not have, which is the failure worth surfacing loudly: the
    caller is asking what a consumer receives, and the answer is "the install
    stops".
    """
    return install.render_delivered(install.source_text(path), CORE_DIR)


def rendered_body(path: Path) -> str:
    """`rendered()` without the frontmatter — what a role is delivered."""
    return split_text(rendered(path))[1]


def delivered_body(path: Path, reader: "Reader") -> str:
    """The body a consumer gets: rendered for a generated file, the authored
    body for a hand-curated one. The reader decides only the second case,
    since the first has no file on disk to have a BOM."""
    return rendered_body(path) if is_generated(path) else reader.body(path)


class Reader:
    """A reading of a delivered file, with one policy: what a BOM means.

    Constructed with the keyword and no default — `STRIPS_BOM` and
    `REFUSES_BOM` below are the two instances, and a caller names the one it
    means. See this module's docstring for which is which and why the
    difference is real rather than an accident of four authors.
    """

    __slots__ = ("refuse_bom",)

    def __init__(self, *, refuse_bom: bool) -> None:
        self.refuse_bom = refuse_bom

    def __repr__(self) -> str:  # pragma: no cover - a failure message's benefit
        return f"Reader(refuse_bom={self.refuse_bom})"

    # -- the file ---------------------------------------------------------- #
    def text(self, path: Path) -> str:
        """The file's content: BOM stripped, CRLF folded. Both readers agree.

        Neither is content. This repo has no `.gitattributes` `text eol=lf`
        pin, so the windows CI leg does get CRLF (conventions.md §6), and the
        installer reads with `utf-8-sig` and could write a BOM back. A byte
        count or a regex that saw either would fail on one leg and hold on the
        other.
        """
        return path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")

    def split(self, path: Path) -> tuple:
        """``(frontmatter_or_None, body)``. ``None`` is a legitimate answer.

        A rule may have no frontmatter at all — that is what unscoped means —
        and so may a file whose delimiter stopped being recognised: a BOM in
        front of it under `REFUSES_BOM`, or a block that is opened and never
        closed. All three read the same way here on purpose, because they read
        the same way to the runtime; the caller says which it was willing to
        accept.
        """
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig").replace("\r\n", "\n")
        if self.refuse_bom and raw.startswith(codecs.BOM_UTF8):
            return None, text
        return split_text(text)

    def frontmatter(self, path: Path):
        """The YAML block alone, or ``None`` — `split()` without the body."""
        return self.split(path)[0]

    def body(self, path: Path) -> str:
        """The text under the frontmatter — `split()` without the block."""
        return self.split(path)[1]

    # -- what the frontmatter says ----------------------------------------- #
    def globs(self, path: Path) -> list:
        """The `paths:` globs of a delivered file; empty for an unscoped one.

        Empty is the loud answer for a rule: no globs means it loads into every
        context, which is also what an unreadable delimiter produces.
        """
        return glob_list(self.frontmatter(path))

    def skill_name(self, path: Path):
        """The name a `skills:` preload resolves this skill by, or ``None``.

        ``None`` is the loud answer for a skill: with no readable `name:` the
        runtime cannot preload it and does not list it, so the section it
        delivers reaches nobody.
        """
        return scalar(self.frontmatter(path), "name")

    def is_section_skill(self, path: Path) -> bool:
        """A `SKILL.md` that delivers a contract section rather than a workflow.

        One signal: `user-invocable: false`, the frontmatter key that keeps a
        skill out of the `/` menu while leaving it preloadable. Structural, so
        the next section skill is covered without anyone editing a list.

        A `<!-- pins:` block used to be a second sufficient signal and is not
        any more (1.42.0): a **workflow** skill may quote the contract it acts
        on — `aide-create-queue` and `aide-review-insights` both carry the §1
        routing table — and `test_rule_pins.py` checks those quotes in both
        directions exactly as it checks a delivered file's. Classing them as
        section skills would demand a `paths:` block, a hidden frontmatter and
        an agent preload of a skill whose whole purpose is to be invoked by
        name. What the old signal bought — a section skill that loses
        `user-invocable: false` failing loudly rather than sliding into the
        workflow set — is bought instead from the preload side, by
        `test_rules.py::test_every_skill_an_agent_preloads_is_a_section_skill`.
        """
        return (scalar(self.frontmatter(path), SECTION_SKILL_KEY) or "").lower() == "false"

    def preloads(self, agent: Path) -> list:
        """The skill names an agent spec's `skills:` frontmatter preloads."""
        return sequence(self.frontmatter(agent), "skills")


#: Reads behind a BOM (`utf-8-sig`), so a file that carries one is still
#: reported on rather than read as frontmatter-less. For the source tree and
#: for copies of it — where a BOM is an authoring accident, not a fact about a
#: runtime's view.
STRIPS_BOM = Reader(refuse_bom=False)

#: Refuses a BOM: `---` is not at byte 0, so there is no frontmatter — which is
#: exactly what the runtime concludes, and the failure
#: `tests/test_structural_budget.py` exists to measure.
REFUSES_BOM = Reader(refuse_bom=True)
