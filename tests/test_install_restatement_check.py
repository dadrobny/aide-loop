"""The consumer instruction file's other half — what the project wrote itself.

`install.py` maintains exactly one line in a consumer's `CLAUDE.md`: the
`@.aide/AGENT-CONTEXT.md` import (ADAPTER-SPEC §7). Everything else is
project-owned and no update touches it — which is right, and is also why a
*copy* of contract text there is unmaintainable: no pass owns it, so it drifts
until it contradicts the contract it came from. Issue #96 recorded a consumer
carrying the insight protocol, the durable-artifacts rules and the §4 mode
table by hand, with three engine releases narrated into the prose after the
fact, because nothing could see it.

These cover the seeing: which engine files count as the contract, how a
restated passage is recognised (a ten-word run, or a heading lifted whole), how
the report is grouped and capped, and the property that makes it safe to add —
it is advisory, so it never moves the `--check` exit code. Stdlib + pytest
only; `install.py` is imported as a module.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)

CLAUDE_ADAPTER = FRAMEWORK_ROOT / "adapters" / "claude"
CORE = FRAMEWORK_ROOT / "core"
AGENT_CONTEXT = CORE / "AGENT-CONTEXT.md"


# --------------------------------------------------------------------------- #
# helpers — the fixtures are lifted from the SHIPPED contract at run time, never
# pasted here. A copy in this file would be the very thing under test, and would
# stop testing anything the day the contract was reworded.
# --------------------------------------------------------------------------- #
def _paragraphs(path: Path, minimum_words: int = 30) -> List[str]:
    """Prose paragraphs of *path*, longest-lived first (file order)."""
    body = install._contract_prose(path.read_text(encoding="utf-8"))
    out = []
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if (block and not block.lstrip().startswith("#")
                and len(install._contract_words(block)) >= minimum_words):
            out.append(block)
    return out


def _delivered_paragraph() -> str:
    return _paragraphs(AGENT_CONTEXT)[0]


def _delivered_heading() -> str:
    for line in AGENT_CONTEXT.read_text(encoding="utf-8").splitlines():
        title = install._heading_text(line)
        if title and len(install._contract_words(title)) >= 3:
            return title
    raise AssertionError("AGENT-CONTEXT.md has no multi-word heading")


def _delivered_fence() -> str:
    """The wordiest fenced block of the delivered page, markers included."""
    body = AGENT_CONTEXT.read_text(encoding="utf-8")
    fences = re.findall(r"^```.*?^```", body, flags=re.S | re.M)
    assert fences, "AGENT-CONTEXT.md has no fenced block"
    return max(fences, key=lambda block: len(install._contract_words(block)))


def _delivered_fence_body() -> str:
    """The same block with its markers removed — prose to a naive reader."""
    return "\n".join(_delivered_fence().splitlines()[1:-1])


def _short_contract_heading() -> str:
    """A two-word contract heading, which the floor deliberately ignores."""
    for path in install.contract_files(CORE):
        for line in path.read_text(encoding="utf-8").splitlines():
            title = install._heading_text(line)
            if title and len(install._contract_words(title)) == 2:
                return title
    raise AssertionError("no two-word heading in the shipped contract")


def _consumer(tmp_path: Path) -> Path:
    target = tmp_path / "consumer"
    target.mkdir()
    assert install.main(["--adapter", "claude", "--into", str(target),
                         "--yes"]) == 0
    return target


def _append(target: Path, text: str) -> None:
    with (target / "CLAUDE.md").open("a", encoding="utf-8") as fh:
        fh.write("\n" + text.strip("\n") + "\n")


def _restatements(target: Path) -> List[str]:
    return install.instruction_restatements(target, CLAUDE_ADAPTER, CORE)


# --------------------------------------------------------------------------- #
# what counts as the contract
# --------------------------------------------------------------------------- #
def test_the_contract_is_the_delivered_page_plus_the_index_and_its_sections():
    """All of it ships into `.aide/`, so a passage matching any of it is a
    second copy of a file the consumer already has."""
    names = {p.relative_to(CORE).as_posix() for p in install.contract_files(CORE)}
    assert "AGENT-CONTEXT.md" in names
    assert "conventions.md" in names
    assert any(n.startswith("conventions/") for n in names)
    # §1 is itself an index of files one level deeper; they are contract too.
    assert any(n.count("/") == 2 for n in names)
    # And the engine README, which ships as `.aide/README.md`: #96 lists a
    # consumer's hand-written shared-vs-personal ownership rules among its
    # evidence, and that section lives there rather than in `conventions/`.
    assert "README.md" in names


def test_the_engine_readmes_own_sections_are_recognised():
    """Pinned separately from the file list: reaching the README and actually
    indexing it are two different failures, and #96's evidence needs both."""
    runs, _ = install.contract_echoes(CORE)
    assert ".aide/README.md" in set(runs.values())


def test_every_shipped_contract_file_is_named_as_a_consumer_would_see_it():
    runs, headings = install.contract_echoes(CORE)
    assert runs and headings
    assert all(src.startswith(".aide/") for src in runs.values())
    assert all(src.startswith(".aide/") for src in headings.values())


def test_a_headings_section_pointer_is_not_part_of_the_heading():
    """`## Command hygiene — §3` is copied as `## Command hygiene`; the back
    reference is the first thing a restatement drops."""
    assert install._heading_text("## Command hygiene — §3") == "Command hygiene"
    assert install._heading_text("### Durable artifacts must read cold - §1") == \
        "Durable artifacts must read cold"
    assert install._heading_text("not a heading") is None


# --------------------------------------------------------------------------- #
# the signal
# --------------------------------------------------------------------------- #
def test_a_freshly_seeded_instruction_file_restates_nothing(tmp_path: Path):
    assert _restatements(_consumer(tmp_path)) == []


def test_a_passage_lifted_from_the_delivered_page_is_named_with_line_and_source(
        tmp_path: Path):
    target = _consumer(tmp_path)
    _append(target, "## Our own rules\n\n" + _delivered_paragraph())
    lines = _restatements(target)
    assert len(lines) == 1
    assert lines[0].startswith("CLAUDE.md:")
    assert '"Our own rules"' in lines[0]
    assert ".aide/AGENT-CONTEXT.md" in lines[0]
    # The line number opens the passage — not the file, not the heading, and
    # not some line in the middle of it: a consumer prunes by opening it there.
    number = int(lines[0].split(":", 1)[1].split()[0])
    body = (target / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
    assert body[number - 1] == _delivered_paragraph().splitlines()[0]
    assert body[number - 2].strip() == ""


def test_a_heading_lifted_whole_is_caught_even_when_the_body_was_reworded(
        tmp_path: Path):
    """The drift case: the prose has been patched by hand past any shared run,
    and the heading is where the original wording survives longest."""
    target = _consumer(tmp_path)
    _append(target, f"## {_delivered_heading()}\n\n"
                    "Wholly reworded prose that shares no long run with the "
                    "engine, kept here by a maintainer who never saw it move.")
    lines = _restatements(target)
    assert len(lines) == 1
    assert f'"{_delivered_heading()}"' in lines[0]
    assert ".aide/AGENT-CONTEXT.md" in lines[0]


def test_a_short_shared_phrase_is_not_a_restatement(tmp_path: Path):
    """Below the run threshold is ordinary English about the same subject —
    every consumer is entitled to say `docs/aide/progress.md` in a sentence."""
    target = _consumer(tmp_path)
    words = install._contract_words(_delivered_paragraph())
    assert len(words) > install.CONTRACT_ECHO_WORDS
    _append(target, "## Notes\n\n"
            + " ".join(words[:install.CONTRACT_ECHO_WORDS - 1]) + ".")
    assert _restatements(target) == []


def test_a_copied_command_is_not_a_restatement(tmp_path: Path):
    """Copying a command out of the contract is what a command is for; only
    prose can restate a rule, so fenced blocks are compared on neither side."""
    target = _consumer(tmp_path)
    _append(target, "## Common commands\n\n" + _delivered_fence())
    assert _restatements(target) == []


def test_the_contract_side_alone_keeps_a_shipped_command_out_of_the_index(
        tmp_path: Path):
    """The fence stripping is on both sides, so the test above passes while
    either one works. This one fails if the *contract* side stops stripping:
    the block arrives as bare prose, and can only be silent because it never
    entered the index."""
    target = _consumer(tmp_path)
    body = _delivered_fence_body()
    assert len(install._contract_words(body)) > install.CONTRACT_ECHO_WORDS
    _append(target, "## How we run it\n\n" + body)
    assert _restatements(target) == []


def test_the_consumer_side_alone_ignores_what_a_project_puts_in_a_fence(
        tmp_path: Path):
    """The mirror image: contract *prose*, which is certainly in the index,
    quoted inside a fence. Only the consumer-side stripping can silence it."""
    target = _consumer(tmp_path)
    _append(target, "## An illustration\n\n```\n"
            + f"## {_delivered_heading()}\n\n" + _delivered_paragraph()
            + "\n```\n\nOur own prose, about our own project.")
    assert _restatements(target) == []


def test_a_tilde_fence_is_a_fence_on_both_sides(tmp_path: Path):
    """CommonMark's other marker. A consumer using it must not be told that
    the contract text it is quoting is a restatement."""
    target = _consumer(tmp_path)
    _append(target, "## An illustration\n\n~~~\n" + _delivered_paragraph()
            + "\n~~~")
    assert _restatements(target) == []
    assert install._contract_words(
        install._contract_prose("~~~\nfenced words here\n~~~\n")) == []


def test_an_indented_fence_is_a_fence(tmp_path: Path):
    """The contract itself contains one (§1 → human-gates.md), and a side that
    strips what the other keeps reads the difference as a restatement."""
    assert install._contract_words(
        install._contract_prose("   ```\n   fenced words here\n   ```\n")) == []
    target = _consumer(tmp_path)
    _append(target, "## An illustration\n\n   ```\n   "
            + _delivered_paragraph().replace("\n", "\n   ") + "\n   ```")
    assert _restatements(target) == []


def test_a_two_word_contract_heading_is_below_the_floor(tmp_path: Path):
    """`## Command hygiene` is a heading a project is entitled to write over a
    section of its own. Three words is where a title stops being a phrase."""
    short = _short_contract_heading()
    assert len(install._contract_words(short)) == 2
    target = _consumer(tmp_path)
    _append(target, f"## {short}\n\nOur own house style for shell commands.")
    assert _restatements(target) == []


def test_a_generic_short_heading_is_not_a_restatement(tmp_path: Path):
    target = _consumer(tmp_path)
    _append(target, "## Install\n\nRun the project's own bootstrap script.")
    assert _restatements(target) == []


def test_a_heading_only_a_shipped_template_contains_is_not_a_fingerprint(
        tmp_path: Path):
    """Contract headings are harvested from prose, like every other
    comparison. A `#` line inside a fenced *template* is a line of an example
    document — the contract ships several — and matching one would flag a
    consumer for having the document the template is a template for."""
    core = tmp_path / "fake-core"
    (core / "conventions").mkdir(parents=True)
    (core / "AGENT-CONTEXT.md").write_text(
        "# Top\n\nSome ordinary contract prose about the loop.\n\n"
        "```\n## Authorised paths for the item\n\nbody\n```\n",
        encoding="utf-8")
    _, headings = install.contract_echoes(core)
    assert "authorised paths for the item" not in headings


def test_the_run_window_is_exactly_the_threshold(tmp_path: Path):
    """Both edges, because both off-by-ones survive every other test here: one
    word short is no run at all, exactly the threshold is exactly one."""
    n = install.CONTRACT_ECHO_WORDS
    words = [f"w{i}" for i in range(n + 1)]
    assert list(install._contract_runs(words[:n - 1])) == []
    assert list(install._contract_runs(words[:n])) == [" ".join(words[:n])]
    assert list(install._contract_runs(words)) == [
        " ".join(words[:n]), " ".join(words[1:])]


# --------------------------------------------------------------------------- #
# the report
# --------------------------------------------------------------------------- #
def test_one_line_per_section_not_one_per_matching_paragraph(tmp_path: Path):
    target = _consumer(tmp_path)
    lifted = _paragraphs(AGENT_CONTEXT)[:3]
    assert len(lifted) == 3
    _append(target, "## Framework rules\n\n" + "\n\n".join(lifted))
    lines = _restatements(target)
    assert len(lines) == 1
    assert '"Framework rules"' in lines[0]


def test_a_section_echoing_several_files_names_each_of_them_once(tmp_path: Path):
    target = _consumer(tmp_path)
    lifted = [_delivered_paragraph(),
              _paragraphs(CORE / "conventions" / "3-command-hygiene.md")[0]]
    _append(target, "## Everything at once\n\n" + "\n\n".join(lifted))
    line = _restatements(target)[0]
    named = line.split("ships in ", 1)[1].split(", ")
    assert len(named) == len(set(named)) >= 2
    assert ".aide/AGENT-CONTEXT.md" in named


def test_two_sections_sharing_a_title_are_two_findings(tmp_path: Path):
    """A section is identified by where it is, not by what it is called.
    Keying on the words would report the first and lose the second entirely —
    including from the count the summary line is drawn from."""
    target = _consumer(tmp_path)
    lifted = _paragraphs(AGENT_CONTEXT)[:2]
    _append(target, "## Notes\n\n" + lifted[0])
    _append(target, "## Elsewhere\n\nOur own prose about our own project.")
    _append(target, "## Notes\n\n" + lifted[1])
    lines = _restatements(target)
    assert len(lines) == 2
    assert all('"Notes"' in line for line in lines)
    first, second = (int(line.split(":", 1)[1].split()[0]) for line in lines)
    assert first < second


def test_findings_are_reported_in_file_order(tmp_path: Path):
    """Not alphabetically by heading: the report is read against the file."""
    target = _consumer(tmp_path)
    lifted = _paragraphs(AGENT_CONTEXT)[:2]
    _append(target, "## Zulu section\n\n" + lifted[0])
    _append(target, "## Alpha section\n\n" + lifted[1])
    lines = _restatements(target)
    assert len(lines) == 2
    assert '"Zulu section"' in lines[0] and '"Alpha section"' in lines[1]


def _restate_sections(target: Path, count: int) -> None:
    pool: List[str] = []
    for path in install.contract_files(CORE):
        pool += _paragraphs(path)
    assert len(pool) >= count
    for number, paragraph in enumerate(pool[:count]):
        _append(target, f"## Restated section {number}\n\n{paragraph}")


def test_the_report_is_not_truncated_to_say_one_line_was_truncated(
        tmp_path: Path):
    """One over the limit: naming the last section and summarising it cost the
    same line, and only one of the two tells a reader where to look."""
    target = _consumer(tmp_path)
    _restate_sections(target, install.CONTRACT_ECHO_LIMIT + 1)
    lines = _restatements(target)
    assert len(lines) == install.CONTRACT_ECHO_LIMIT + 1
    assert not any("further passage" in line for line in lines)


def test_the_report_summarises_the_rest_once_past_the_limit(tmp_path: Path):
    """A warning that fills a screen is a warning that gets scrolled past."""
    target = _consumer(tmp_path)
    _restate_sections(target, install.CONTRACT_ECHO_LIMIT + 3)
    lines = _restatements(target)
    assert len(lines) == install.CONTRACT_ECHO_LIMIT + 1
    assert lines[-1].startswith("CLAUDE.md: and 3 further passage(s)")


# --------------------------------------------------------------------------- #
# advisory, and only advisory
# --------------------------------------------------------------------------- #
def test_check_reports_the_restatement_and_still_exits_zero(tmp_path: Path, capsys):
    """The file is the project's. The framework has no standing to fail a
    build over what a project wrote in it — only to say what it found."""
    target = _consumer(tmp_path)
    _append(target, "## Framework rules\n\n" + _delivered_paragraph())
    capsys.readouterr()
    code = install.main(["--adapter", "claude", "--into", str(target), "--check"])
    out = capsys.readouterr().out
    assert code == 0
    assert "repeats contract text the engine ships" in out
    assert "not part of the exit code" in out
    # The pointer names the README of the checkout that just ran, because the
    # consumer's own `.aide/README.md` has no such section — a repair pointing
    # at a heading the reader does not have is the failure #96 is about.
    assert "What belongs in the instruction file" in out
    assert str(FRAMEWORK_ROOT) in out


def test_check_stays_silent_when_nothing_is_restated(tmp_path: Path, capsys):
    target = _consumer(tmp_path)
    capsys.readouterr()
    assert install.main(["--adapter", "claude", "--into", str(target),
                         "--check"]) == 0
    out = capsys.readouterr().out
    assert "repeats contract text" not in out
    assert "not part of the exit code" not in out


def test_a_failing_check_still_fails_for_its_own_reason(tmp_path: Path, capsys):
    """The advisory rides along with a real failure; it neither causes one nor
    masks one."""
    target = _consumer(tmp_path)
    _append(target, "## Framework rules\n\n" + _delivered_paragraph())
    (target / ".aide" / "VERSION").write_text("0.0.1\n", encoding="utf-8")
    capsys.readouterr()
    code = install.main(["--adapter", "claude", "--into", str(target), "--check"])
    out = capsys.readouterr().out
    assert code == 1
    assert "is BEHIND" in out
    assert "repeats contract text the engine ships" in out


def test_an_adapter_that_declares_no_instruction_file_reports_nothing(
        tmp_path: Path):
    """§7 is optional — the same graceful degradation the rest of it uses."""
    target = _consumer(tmp_path)
    assert install.instruction_restatements(target, tmp_path, CORE) == []


# --------------------------------------------------------------------------- #
# the guidance an adopter reads (issue #96's other half)
# --------------------------------------------------------------------------- #
def test_a_created_instruction_file_tells_its_reader_not_to_restate_the_contract(
        tmp_path: Path):
    target = _consumer(tmp_path)
    body = (target / "CLAUDE.md").read_text(encoding="utf-8")
    assert "rather than restating it here" in body
    assert install.AGENT_CONTEXT_REL in body


def test_the_repair_is_written_down_where_an_adopter_looks():
    """The check names a heading; the heading has to exist in the file the
    check sends the reader to, or the advice is a dead pointer — which is the
    failure mode this whole issue is about."""
    readme = (FRAMEWORK_ROOT / "README.md").read_text(encoding="utf-8")
    assert "### What belongs in the instruction file" in readme
    # And it is deliberately NOT claimed to be in the engine README, which is
    # the one a consumer installs.
    engine = (CORE / "README.md").read_text(encoding="utf-8")
    assert "What belongs in the instruction file" not in engine
    spec = (FRAMEWORK_ROOT / "adapters" / "ADAPTER-SPEC.md").read_text(
        encoding="utf-8")
    assert "never part of an exit code" in spec
