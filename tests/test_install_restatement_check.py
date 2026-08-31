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
    body = AGENT_CONTEXT.read_text(encoding="utf-8")
    match = re.search(r"^```.*?^```", body, flags=re.S | re.M)
    assert match, "AGENT-CONTEXT.md has no fenced block"
    return match.group(0)


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
    # The line number points at the passage, not at the file or the heading:
    # a consumer prunes by opening the file there.
    number = int(lines[0].split(":", 1)[1].split()[0])
    body = (target / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
    assert body[number - 1] in _delivered_paragraph().splitlines()


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


def test_a_generic_two_word_heading_is_not_a_restatement(tmp_path: Path):
    target = _consumer(tmp_path)
    _append(target, "## Install\n\nRun the project's own bootstrap script.")
    assert _restatements(target) == []


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


def test_the_report_summarises_the_rest_once_past_the_limit(tmp_path: Path):
    """A warning that fills a screen is a warning that gets scrolled past."""
    target = _consumer(tmp_path)
    pool: List[str] = []
    for path in install.contract_files(CORE):
        pool += _paragraphs(path)
    over = install.CONTRACT_ECHO_LIMIT + 2
    assert len(pool) >= over
    for number, paragraph in enumerate(pool[:over]):
        _append(target, f"## Restated section {number}\n\n{paragraph}")
    lines = _restatements(target)
    assert len(lines) == install.CONTRACT_ECHO_LIMIT + 1
    assert lines[-1].startswith("CLAUDE.md: and 2 further passage(s)")


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
    assert "What belongs in the instruction file" in out


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
    """The check names a heading; the heading has to exist, or the advice is a
    dead pointer — which is the failure mode this whole issue is about."""
    readme = (FRAMEWORK_ROOT / "README.md").read_text(encoding="utf-8")
    assert "### What belongs in the instruction file" in readme
    spec = (FRAMEWORK_ROOT / "adapters" / "ADAPTER-SPEC.md").read_text(
        encoding="utf-8")
    assert "never part of an exit code" in spec
