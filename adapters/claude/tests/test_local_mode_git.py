"""Every pull, push and fetch a control file instructs says when it is skipped
(issue #356).

§4 states it: `local` mode makes no fetch, pull or push at all. The engine's
verbs carry that out themselves; an instruction that types `git push` does
not, and the runners and queue skills used to type them unconditionally — a
push in `local` mode contradicts the mode, and with no origin it fails with
"No configured push destination". Each site now says, in a sentence of its
own, that it is skipped in `local` mode or with no origin. This holds the next
one to the same: a `git push`, `git pull` or `git fetch` in an agent spec,
command, skill or rule needs the phrases "`local` mode" and "no origin" **in
the same paragraph** — the table row itself when the line is one; else the lines between
two blank lines, or, where those are a list, the outermost list item the line
stands in, so a mention in one step does not cover the next. A prohibition
("do not improvise `git fetch`") instructs nothing, and is passed when "do
not improvise", "do **not** improvise" or "never improvise" stands right
before the command. The phrases are exact because a dense paragraph says
"origin" for other reasons — "deleted on origin" — and would otherwise pass
with its guard gone.
Stdlib + pytest only.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
ADAPTER = FRAMEWORK_ROOT / "adapters" / "claude"

CONTROL_FILES = sorted(
    list((ADAPTER / "commands").glob("*.md"))
    + list((ADAPTER / "skills").glob("*/SKILL.md"))
    + list((ADAPTER / "agents").glob("*.md"))
    + list((ADAPTER / "rules").glob("*.md")))

_GIT_REMOTE = re.compile(r"\bgit (?:push|pull|fetch)\b")
_LOCAL = re.compile(r"`local`\s+mode")
_ORIGIN = re.compile(r"\bno\s+origin\b")
#: The two prohibitions, in their exact form: "Do not improvise `git fetch`"
#: and "do **not** improvise `git fetch`" — the command right after it.
_PROHIBITION = re.compile(r"(?i)\b(?:do (?:\*\*not\*\*|not)|never) improvise `$")


def _sites(text: str) -> List[Tuple[int, str, str]]:
    """(line number, line, its paragraph) for each remote git command
    instructed in *text*."""
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        for m in _GIT_REMOTE.finditer(line):
            if _PROHIBITION.search(line[:m.start()]):
                continue
            out.append((i + 1, line, _unit(lines, i)))
    return out


_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+\.)\s")


def _unit(lines: List[str], i: int) -> str:
    """The paragraph line *i* stands in: the table row itself, else the
    lines between two blank lines — cut, where they are a list, into its
    outermost items, so one item's mention does not cover the next item."""
    if lines[i].lstrip().startswith("|"):
        return lines[i]
    lo = i
    while lo > 0 and lines[lo - 1].strip():
        lo -= 1
    hi = i
    while hi + 1 < len(lines) and lines[hi + 1].strip():
        hi += 1
    starts = [(k, len(m.group(1))) for k in range(lo, hi + 1)
              for m in [_ITEM.match(lines[k])] if m]
    if starts:
        outer = min(d for _, d in starts)
        cuts = [k for k, d in starts if d == outer]
        lo = max([lo] + [k for k in cuts if k <= i])
        hi = min([hi] + [k - 1 for k in cuts if k > i])
    return "\n".join(lines[lo:hi + 1])


def _label(path: Path) -> str:
    return path.relative_to(FRAMEWORK_ROOT).as_posix()


@pytest.mark.parametrize("path", CONTROL_FILES, ids=_label)
def test_every_pull_push_and_fetch_says_local_mode_skips_it(path: Path):
    unguarded = [
        f"{_label(path)}:{n}: {line.strip()}"
        for n, line, para in _sites(path.read_text(encoding="utf-8"))
        if not (_LOCAL.search(para) and _ORIGIN.search(para))]
    assert not unguarded, (
        "a pull, push or fetch with no mention of `local` mode and no origin "
        "in its paragraph — §4 makes none in `local` mode, and with no origin "
        "it fails; say where it is skipped:\n" + "\n".join(unguarded))


def test_the_runners_and_queue_skills_carry_guarded_sites():
    """The scan above is vacuous if the sites it was written for vanish from
    its reach — a moved directory, a renamed file."""
    by_name = {_label(p): p for p in CONTROL_FILES}
    for name in ("adapters/claude/commands/aide-run-roadmap.md",
                 "adapters/claude/skills/aide-spec-queue/SKILL.md",
                 "adapters/claude/skills/aide-create-queue/SKILL.md",
                 "adapters/claude/skills/aide-create-item/SKILL.md"):
        assert name in by_name, name
        assert _sites(by_name[name].read_text(encoding="utf-8")), name


def test_a_prohibition_is_passed_and_an_instruction_is_not():
    text = ("Do not improvise `git fetch` here.\n\n"
            "Then `git push`, deleted on origin, `local` too.\n\n"
            "Then `git pull` — not in `local` mode or with no origin.\n\n"
            "| row | `git push` |\n| row | `local` mode or no origin |\n\n"
            "1. Then `git pull`, not in `local` mode or with no origin.\n"
            "   - and `git push` under it is covered by its step.\n"
            "2. But `git push` in the next step is not.\n\n"
            "Improvise nothing, then `git pull`.\n")
    unguarded = [n for n, _, para in _sites(text)
                 if not (_LOCAL.search(para) and _ORIGIN.search(para))]
    assert unguarded == [3, 7, 12, 14]
