"""One reading of the adapter's **delivered files**, for every suite that has one.

A delivered file is what ADAPTER-SPEC §7 makes conformant: the unscoped
`.claude/rules/*.md`, and the **section skills** under
`.claude/skills/<name>/SKILL.md` (`user-invocable: false`, preloaded by the
agent specs whose `skills:` frontmatter names them). Four modules read them —

- `adapters/claude/tests/test_rules.py`      — the envelope and the preload channel
- `adapters/claude/tests/test_rule_pins.py`  — the quoted statements, both directions
- `tests/test_structural_budget.py`          — reach and cost, against a real install
- `tests/test_fixture_consumer.py`           — the files as an install leaves them

— and each carried its own copy of the same parser set: a frontmatter
splitter, a scalar/list reader for `name:`, `user-invocable:`, `paths:` and
`skills:`, the section-skill recogniser, a `_label` and an HTML-comment
stripper (issue #113).

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

**How the adapter suite reaches it.** `adapters/claude/tests/` puts the
framework root on `sys.path` to `import install` already; reaching this module
adds `tests/` the same way. A repo-root module was the alternative and the root
is a curated surface, so the shared reader lives with the suite that owns the
broadest view of an install. Stdlib only, no pytest import: this is a parser.
"""
from __future__ import annotations

import codecs
import re
from pathlib import Path

#: The frontmatter key that makes a `SKILL.md` a section skill. One key, since
#: 1.42.0 — see `Reader.is_section_skill`.
SECTION_SKILL_KEY = "user-invocable"

#: Any HTML comment. A preload strips these, so the `<!-- reach: … -->` and
#: `<!-- pins: … -->` declarations cost the loop nothing — and a check on what
#: a role actually receives has to strip them too, or a pin would satisfy
#: itself from its own declaration.
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
        if not text.startswith("---\n"):
            return None, text
        end = text.find("\n---\n", 4)
        return (None, text) if end == -1 else (text[4:end], text[end + 5:])

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
