"""The templates must obey the template convention they define.

Two properties, both about the leading `<!-- ... -->` header comment: it uses
the fill-in convention correctly, and it states **shapes and fill-in guidance
only** — never a rule a `conventions/` section core states, nor mechanism a
verb's `-h` states. The second half is issue #205's; its banner below carries
the design.

`CLAUDE.md` and `conventions.md` §1 state it: `{{slot}}` marks a literal value
to substitute, an _italic line_ marks authoring guidance to read then replace,
and **guidance must never be written as a slot** — because `aide check` errors
on any `{{...}}` surviving into a consumer's `docs/aide/**`, so a slot sitting
inside guidance prose turns "you left the guidance in" into a confusing
"unfilled template slot" pointing at text that was never a field.

Nothing checked this, and it recurred: the same slip landed in two separate
PRs, once in prose describing a date format and once as a whole guidance
sentence written as a slot. A convention nothing enforces is a convention that
decays — the same reasoning that put the command-hygiene rules behind a hook.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

_ROOT = Path(__file__).resolve().parents[1]
# This module puts the framework root on `sys.path` itself: there is no
# `conftest.py` in this repository, and adding one would make the dependency on
# `install` invisible.
sys.path.insert(0, str(_ROOT))
import install  # noqa: E402  (path shim above)

_ENGINE_TEMPLATES = sorted((_ROOT / "core" / "templates").glob("*.md"))
_TEMPLATES = list(_ENGINE_TEMPLATES)

#: The issue template is a template this repo authors under the same convention,
#: and it sat outside this glob until a slip landed in it. Note the limit: this
#: guard decides one shape — a slot *inside* italic guidance — and the slip that
#: widened the glob was the other shape, guidance written *as* a slot, which no
#: heuristic can tell from a legitimate value slot. Covering the shape it can
#: decide still costs nothing.
_TEMPLATES += sorted((_ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.md"))


_ITALIC_DELIM_RE = re.compile(r"(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])")


def _guidance_slots(path: Path) -> list:
    """(lineno, text) for every `{{...}}` that sits *inside* an italic span.

    Scans positionally, carrying italic state across lines, so it covers all
    three shapes the templates actually use: a whole italic paragraph, a
    single-line `_guidance._`, and `**Label.** _guidance…_` that opens its
    italics mid-line.

    An earlier version tested "does the line start with `_`", which had a blind
    spot for that third shape — and the very slip this file guards against
    recurred *in the PR that added the guard* because of it. A guard with a
    blind spot is worse than none, because it is trusted (conventions.md §6).
    A `_` inside a word (`queue_cap`) is not a delimiter and never toggles.
    """
    hits, in_italic = [], False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        events = [(m.start(), "delim") for m in _ITALIC_DELIM_RE.finditer(line)]
        events += [(m.start(), "slot") for m in re.finditer(r"\{\{", line)]
        flagged = False
        for _, kind in sorted(events):
            if kind == "delim":
                in_italic = not in_italic
            elif in_italic and not flagged:
                hits.append((n, line.strip()))
                flagged = True
    return hits


def test_there_are_templates():
    assert _TEMPLATES, "no core/templates/*.md found — the glob or the layout moved"


@pytest.mark.parametrize("path", _TEMPLATES, ids=lambda p: p.name)
def test_no_slot_inside_guidance(path: Path):
    hits = _guidance_slots(path)
    assert not hits, (
        f"{path.name}: {{{{...}}}} inside italic guidance at line(s) "
        + ", ".join(str(n) for n, _ in hits)
        + ". Guidance is replaced, not filled: write the shape in plain text "
          "(YYYY-MM-DD, 'item numbers') and keep {{slots}} on the content line "
          "an author actually substitutes."
    )


def test_the_check_would_catch_a_regression(tmp_path: Path):
    """The guard on the guard — a check that cannot fail is worse than none
    (conventions.md §6)."""
    bad = tmp_path / "bad.md"
    bad.write_text("_Guidance saying `✅ Met ({{yyyy-mm-dd}})` here._\n", encoding="utf-8")
    assert _guidance_slots(bad)


def test_a_slot_on_a_content_line_is_allowed(tmp_path: Path):
    """Table rows and headings are exactly where slots belong."""
    ok = tmp_path / "ok.md"
    ok.write_text("| {{target}} | ⏳ Awaiting |\n\n_Plain guidance, no slots._\n",
                  encoding="utf-8")
    assert _guidance_slots(ok) == []


def test_guidance_opening_mid_line_is_covered(tmp_path: Path):
    """`**Label.** _guidance…_` opens its italics after a bold label. The first
    version of this check only opened a block on a LEADING underscore, so it
    missed exactly this shape — and the slip recurred in the same PR that added
    the guard."""
    bad = tmp_path / "midline.md"
    bad.write_text("**Human gate.** _OPTIONAL — the row usually reads\n"
                   "`Blocks: stage {{n}}`. A gate written only here does nothing._\n",
                   encoding="utf-8")
    assert [n for n, _ in _guidance_slots(bad)] == [2]


def test_a_word_internal_underscore_is_not_a_delimiter(tmp_path: Path):
    """`queue_cap` in prose must not be read as opening an italic block, or
    every slot after it would be falsely flagged."""
    ok = tmp_path / "snake.md"
    ok.write_text("Prose naming queue_cap and loop_clarify.\n\n| {{slot}} | x |\n",
                  encoding="utf-8")
    assert _guidance_slots(ok) == []


def test_multi_line_guidance_is_covered(tmp_path: Path):
    """Every recorded instance sat in a multi-line italic paragraph, so a
    single-line check would have missed all of them."""
    bad = tmp_path / "multi.md"
    bad.write_text("_Guidance opens here\nand mentions {{yyyy-mm-dd}} midway\n"
                   "before closing._\n", encoding="utf-8")
    assert [n for n, _ in _guidance_slots(bad)] == [2]


# --------------------------------------------------------------------------- #
# a header states shapes and guidance, and restates no rule (issue #205)
# --------------------------------------------------------------------------- #
#: The other half of the template row in `docs/copies-of-engine-text.md`. That
#: row decides two things about a header comment and this section holds both.
#:
#: **Shapes are not a copy.** Since #193 a `conventions/` section *names* the
#: template rather than drawing it, so for a table header row, a status-icon
#: legend or a bullet format string the template is the original and the section
#: is the pointer. A shape is therefore never a finding here — and it never
#: needs an exemption either, because no shape string in the six headers comes
#: near ten words: `- <icon> <text>. *(Item NNN)*` is four, the stage summary
#: row four, `### Item NNN: Short Title` + a description paragraph seven. That
#: is why there is **no allow-list**: an entry would be dead the day it was
#: written, and `_copies` consults none. A run that really is a shape would mean
#: a section is *drawing* a shape it should be naming — #193's own rule — so the
#: repair is in the section, not an exemption here.
#:
#: **Rules and mechanism are.** A rule belongs to the section core that states
#: it and mechanism to the `-h` block the code renders, and rung 1 of the copies
#: rule says the header points instead of copying. The rejected alternative is
#: "copy just the one sentence, it is short", which is how this very row's
#: header came to ship a two-release-stale rollup.
#:
#: The comparison is `install.py --check`'s, reused rather than reinvented: the
#: ten-word runs of `install._contract_runs` over `install._contract_words`,
#: after a normalisation that absorbs reflow, emphasis, case and punctuation. A
#: shared run is a copy. Ten is `install.CONTRACT_ECHO_WORDS` and is imported,
#: not restated, so both restatement channels stay tuned together — and the
#: measurement says ten is also right for a header, which is a tenth the size of
#: the passages that constant was set for. Against this tree before the #205
#: pass: **66 run/source matches (61 distinct runs) at six words, 30 (30) at
#: eight, 13 (13) at ten** — a run can match more than one source, and `_copies`
#: names the first, so the two counts separate only where sections overlap. Six
#: drowns the signal in ordinary English (`the single source of truth for`, a
#: phrase any document is entitled to). Eight flags the fill-in convention
#: itself — *authoring guidance to read then replace with real prose* — which §1
#: states and a header is *required* to state, so eight would fail the property
#: it is checking. Ten left thirteen runs and every one of them was a real copy;
#: all four passages they fell in now point, and the tree scores zero at ten
#: (29 matches / 25 distinct at six, 6 / 6 at eight).
#:
#: What ten costs is the short fragment: *ticking the checkbox is the one
#: in-place edit* is eight words of §1 → `insights.md` and survives. That is the
#: same known cost rung 3 accepts for an unpinned statement, and it is priced
#: the same way — a sentence that matters enough to pin is pinned, and the rest
#: is watched by the threshold.

_AIDE_PATH = _ROOT / "core" / "scripts" / "aide.py"
_spec = importlib.util.spec_from_file_location("aide_cli_template_guard", _AIDE_PATH)
aide = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = aide
_spec.loader.exec_module(aide)  # type: ignore[union-attr]

_HEADER_RE = re.compile(r"\A\s*<!--(.*?)-->", re.S)


def _header(path: Path) -> str:
    """The leading `<!-- … -->` comment of *path*, or `""`.

    Only the leading one: a comment further down is annotation beside the shape
    it annotates (`vision.md`'s inline MANDATORY markers), and it is the header
    that carries prose about rules.
    """
    match = _HEADER_RE.search(path.read_text(encoding="utf-8-sig"))
    return match.group(1) if match else ""


def _runs(text: str) -> Set[str]:
    return set(install._contract_runs(install._contract_words(text)))


def _read_sources() -> Dict[str, Set[str]]:
    """`name -> runs` for everything a header must not restate.

    Two kinds. Every section **core** under `core/conventions/**` — the cut is
    `install.section_core`, so a section's `Rationale` tail is out: the tail is
    provenance, and a header echoing it would be a curiosity rather than a rule
    in two places. And every verb's rendered `-h` **description block**, reached
    through the `_SubParsersAction` the way `test_aide_help_pins.py` reaches it,
    so the comparison sees the string a consumer sees.

    Fenced code is dropped from the section side and **not** from the header
    side. `install.contract_echoes` strips both, and warns that a one-sided
    strip is what a symmetric comparison cannot survive; the asymmetry here is
    the row's ruling, not an oversight. A fence in a section is a drawn shape,
    which the row gives to the template — stripping it is what keeps `insights`'
    own entry shape from reading as a copy of the section that quotes it. A
    fence in a *header* would be the header's own prose and must still be
    compared; no header fences anything today, so the choice is about the next
    one.
    """
    sources: Dict[str, Set[str]] = {}
    for path in sorted((_ROOT / "core" / "conventions").rglob("*.md")):
        text = path.read_text(encoding="utf-8-sig")
        core = install.section_core(text)
        # No `Rationale` heading means #122's split has not been applied to
        # that section, and the whole file is compared. That is the strict
        # direction — a header is then held against the tail as well, which can
        # only over-report — and over-reporting is the right way to fail while
        # a section is mid-split.
        body = install._contract_prose(core if core is not None else text)
        sources[".aide/" + path.relative_to(_ROOT / "core").as_posix()] = _runs(body)
    for verb, description in _help_descriptions().items():
        sources[f"aide {verb} -h"] = _runs(description)
    return sources


#: Built once. Ten calls read it across this module's tests, and a build is
#: 20 ms — so the memo saves about 0.2 s, which is small and is not really the
#: point: a per-call rebuild grows with every section added to the contract,
#: and this does not. Every reader treats the dict as read-only.
_SOURCE_CACHE: Dict[str, Set[str]] = {}


def _sources() -> Dict[str, Set[str]]:
    """`_read_sources()`, memoised for the module."""
    if not _SOURCE_CACHE:
        _SOURCE_CACHE.update(_read_sources())
    return _SOURCE_CACHE


def _help_descriptions() -> Dict[str, str]:
    """`verb -> description block`, for every verb that carries one."""
    parser = aide.build_parser()
    sub = next(action for action in parser._actions
               if isinstance(action, argparse._SubParsersAction))
    return {verb: (choice.description or "").strip()
            for verb, choice in sub.choices.items()
            if (choice.description or "").strip()}


def _words_of(name: str) -> List[str]:
    """The normalised words behind a source name, for the floor check below."""
    if name.endswith(" -h"):
        return install._contract_words(_help_descriptions()[name.split()[1]])
    path = _ROOT / "core" / name[len(".aide/"):]
    text = path.read_text(encoding="utf-8-sig")
    core = install.section_core(text)
    return install._contract_words(
        install._contract_prose(core if core is not None else text))


def _copies(header: str, sources: Dict[str, Set[str]]) -> List[Tuple[str, str]]:
    """`(source, run)` for every run the header shares with a source.

    The first source carrying a run is the one named, for the reason
    `install.contract_echoes` gives: the question is "does this already exist
    upstream", and one name answers it.
    """
    found: Dict[str, str] = {}
    for run in _runs(header):
        for name, runs in sources.items():
            if run in runs:
                found.setdefault(run, name)
                break
    return sorted((name, run) for run, name in found.items())


def test_there_is_something_to_compare_against():
    """A guard whose source set silently emptied would pass forever."""
    sources = _sources()
    sections = [name for name in sources if name.startswith(".aide/")]
    helps = [name for name in sources if name.endswith(" -h")]
    assert len(sections) >= 10, f"only {len(sections)} section cores read: {sections}"
    assert len(helps) >= 5, f"only {len(helps)} -h description blocks read: {helps}"
    # Only for a source long enough to *have* a run. A section core or an `-h`
    # block under `CONTRACT_ECHO_WORDS` normalised words yields none, which is
    # arithmetic rather than a broken read — failing over it would make a
    # legitimately terse source impossible to write.
    silent = sorted(name for name, runs in sources.items()
                    if not runs and len(_words_of(name)) >= install.CONTRACT_ECHO_WORDS)
    assert not silent, f"a source long enough to have runs contributed none: {silent}"


def _failure(name: str, hits: List[Tuple[str, str]]) -> str:
    """What a reader of a red run sees — the template, each run, its source.

    One function, so the two planted-copy tests below assert against the text
    that will actually be printed rather than against a private return value.
    A failure message nobody has read is the other half of a guard nobody has
    seen fail.
    """
    return (
        f"core/templates/{name}: the header comment repeats "
        f"{len(hits)} ten-word run(s) of engine text —\n"
        + "\n".join(f"  {source}: “{run}”" for source, run in hits)
        + "\n\nA header states shapes and fill-in guidance; a rule belongs to "
          "the section that states it and mechanism to the verb's -h "
          "(ADAPTER-SPEC.md, 'Copies of engine text', rung 1). Point at the "
          "source and delete the sentence. A run that is genuinely a shape "
          "means the section is drawing a shape it should be naming (#193): "
          "fix the section, not this header.")


@pytest.mark.parametrize("path", _ENGINE_TEMPLATES, ids=lambda p: p.name)
def test_no_header_restates_a_rule_or_a_verbs_help(path: Path):
    header = _header(path)
    assert header.strip(), f"{path.name}: no leading <!-- … --> header comment"
    hits = _copies(header, _sources())
    assert not hits, _failure(path.name, hits)


def test_the_guard_catches_a_sentence_planted_from_a_section(tmp_path: Path):
    """The guard on the guard (conventions.md §6), planted from §1 →
    `queue-NNN.md` — the sentence `queue.md`'s header actually carried until
    this pass."""
    planted = tmp_path / "planted.md"
    planted.write_text(
        "<!--\n  AIDE scratch template. Shapes:\n"
        "    - Each item: \"### Item NNN: Short Title\".\n"
        "  Item numbers are GLOBALLY SEQUENTIAL across all queues — never restart.\n"
        "-->\n# {{title}}\n", encoding="utf-8")
    hits = _copies(_header(planted), _sources())
    assert hits, "a sentence lifted verbatim from a section core went unreported"
    message = _failure("planted.md", hits)
    assert "core/templates/planted.md" in message, message
    assert ".aide/conventions/1-format-contract/queue-NNN.md" in message, message
    assert "globally sequential across all queues" in message, message
    assert all(source == ".aide/conventions/1-format-contract/queue-NNN.md"
               for source, _ in hits), hits


def test_the_guard_catches_a_sentence_planted_from_a_verbs_help(tmp_path: Path):
    """The other source, and the one the row calls rung 1's second condition:
    mechanism the code owns. A whole sentence of `aide progress -h`, planted.
    """
    sentence = next(
        s for s in _help_descriptions()["progress"].split(".")
        if len(install._contract_words(s)) >= install.CONTRACT_ECHO_WORDS)
    planted = tmp_path / "planted.md"
    planted.write_text(f"<!--\n  AIDE scratch template.{sentence}.\n-->\n",
                       encoding="utf-8")
    hits = _copies(_header(planted), _sources())
    assert hits, f"a sentence of `aide progress -h` went unreported: {sentence!r}"
    message = _failure("planted.md", hits)
    assert "core/templates/planted.md" in message, message
    assert "aide progress -h" in message, message
    assert any(source.endswith(" -h") for source, _ in hits), hits


#: The sentence `templates/progress.md` shipped until #205 — the drift the whole
#: row exists for. It restated the stage rollup in two halves, **neither ever
#: true**: that a ❌ bullet blocks a stage's ✅, and that the rollup then ticks
#: the stage's Acceptance boxes.
_THE_205_DRIFT = (
    "Rollup (aide progress + aide check enforce it): a stage is ✅ iff every\n"
    "  Deliverables bullet is ✅ -> then its Acceptance boxes are [x] and its\n"
    "  summary row / header / delivered objectives read ✅. Mixed -> 🚧. None\n"
    "  started -> 📋.")


def test_the_drift_that_opened_205_is_caught_by_its_neighbours_not_by_itself():
    """**The limit of this guard, stated plainly: it catches copies, not wrong
    copies.**

    A run comparison finds text two files share. The #205 sentence shared none
    — that is exactly what was wrong with it. Its rule had moved into
    `aide progress -h` two releases earlier and the sentence had been left
    behind, so by the time anyone looked it was no longer a copy of anything.
    Nothing keyed on similarity can report that; a drifted copy is caught from
    the other side, by the source's own pins — `HELP_PINS` in
    `core/scripts/tests/test_aide_help_pins.py` for a verb, a section's
    `<!-- pins: -->` readers for a section.

    What the guard would have done is still the useful half, and it is asserted
    here: opened the same file, for the same reason. The header carrying that
    sentence also restated §1 → `progress.md`'s Outcome-targets gate verbatim,
    which is a copy and is reported — so a run of this check against the tree
    of the day names `templates/progress.md`, and whoever reads the header to
    fix the reported line reads the stale rollup three lines above it.
    """
    sources = _sources()
    assert _copies(_THE_205_DRIFT, sources) == [], (
        "the drifted sentence now shares a run with a source — if a section or "
        "an -h block has been reworded back toward it, this test's premise is "
        "gone and the docstring above is wrong")

    shipped_header = _THE_205_DRIFT + (
        "\n  Stage ✅ means \"the planned work shipped\", nothing more; a MEASURED"
        "\n  goal the work cannot guarantee (an error-rate target, a benchmark)"
        "\n  belongs in the optional \"Outcome targets\" table, which gates the"
        "\n  Objective rows instead (an objective linked to a target that is not"
        "\n  ✅ Met cannot roll up to ✅).")
    hits = _copies(shipped_header, sources)
    assert any(source == ".aide/conventions/1-format-contract/progress.md"
               for source, _ in hits), hits
