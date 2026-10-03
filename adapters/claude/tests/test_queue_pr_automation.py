"""The queue's own PR is opened and marked ready unattended (issue #330).

The decision: `aide queue pr` and `aide queue ready` run without a prompt,
because each can touch only the PR whose head is the queue being run, while
`gh pr create` and `gh pr ready` — which can touch any PR — stay `ask`-gated.
The engine allow rule `Bash(python .aide/scripts/aide.py:*)` already covers
every subcommand, so the decision is held here rather than by a new rule:
both verbs in the shapes a runner types are pre-approved and asked by
nothing, the raw `gh` forms still ask, and the hygiene hook passes the verbs
through. Coverage is read with the reviewer's own ``is_covered``, so the test
asks the question a permission review asks. Since issue #331 §3 forbids the
raw forms, and no agent, command, skill or rule names one. Since issue
#383 the roadmap runner checks for the queue file before `queue pr`, and the
empty branch a planner hand-back leaves is discarded by `aide queue
discard`, which runs unattended. Stdlib + pytest only.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
ADAPTER = FRAMEWORK_ROOT / "adapters" / "claude"

sys.path.insert(0, str(ADAPTER / "scripts"))
import review_permissions as rp  # noqa: E402  (path shim above)

_spec = importlib.util.spec_from_file_location(
    "hygiene_guard_queue_pr", ADAPTER / "hooks" / "command_hygiene_guard.py")
guard = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = guard
_spec.loader.exec_module(guard)  # type: ignore[union-attr]

_PERMS = json.loads((ADAPTER / "settings.json").read_text(
    encoding="utf-8"))["permissions"]

VERBS = [
    "python .aide/scripts/aide.py queue pr --body-file .aide-pr-body.md",
    "python .aide/scripts/aide.py queue pr 012 --body \"Queue 012.\"",
    "python .aide/scripts/aide.py queue ready",
    "python .aide/scripts/aide.py queue ready 012",
    "python .aide/scripts/aide.py queue ready --undo",
]


@pytest.mark.parametrize("command", VERBS)
def test_the_queue_pr_verbs_are_pre_approved_and_asked_by_nothing(command):
    assert rp.is_covered("Bash", command, _PERMS["allow"])
    assert not rp.is_covered("Bash", command, _PERMS["ask"])


@pytest.mark.parametrize("command", VERBS)
def test_the_hygiene_hook_lets_the_queue_pr_verbs_through(command):
    assert guard.violations(command) == []


@pytest.mark.parametrize("command", [
    "gh pr create --draft --base main --title x --body y",
    "gh pr ready 12",
    "gh pr ready 12 --undo",
])
def test_the_raw_forge_forms_stay_ask_gated(command):
    assert rp.is_covered("Bash", command, _PERMS["ask"])


# --------------------------------------------------------------------------- #
# §3 forbids the raw forms, and no control file instructs them (issue #331)
# --------------------------------------------------------------------------- #
_RAW = ("gh pr create", "gh pr ready")


def test_section_3_forbids_what_settings_ask_gates():
    """The rule and its enforcement move together: §3 names both raw forms,
    and the ask entry is what stops one typed anyway."""
    section = (FRAMEWORK_ROOT / "core" / "conventions" / "3-command-hygiene.md"
               ).read_text(encoding="utf-8")
    core = section.split("### Rationale")[0]
    for raw in _RAW:
        assert f"`{raw}`" in core, raw
        assert rp.is_covered("Bash", f"{raw} 12", _PERMS["ask"]), raw


@pytest.mark.parametrize("path", sorted(
    p for kind in ("agents", "commands", "skills", "rules")
    for p in (ADAPTER / kind).rglob("*.md")), ids=lambda p: p.name
    if p.name != "SKILL.md" else p.parent.name)
def test_no_control_file_instructs_a_raw_pr_command(path: Path):
    text = path.read_text(encoding="utf-8")
    assert not [raw for raw in _RAW if raw in text], (
        f"{path.relative_to(ADAPTER)} names a raw PR command §3 forbids — "
        f"`aide queue pr` / `aide queue ready` for a queue's own PR, and any "
        f"other PR is the user's to open")


# --------------------------------------------------------------------------- #
# a planner hand-back is never followed by `queue pr` (issue #383)
# --------------------------------------------------------------------------- #
_ROADMAP = ADAPTER / "commands" / "aide-run-roadmap.md"
_QUEUE_CHECK = "git ls-files docs/aide/queue/queue-NNN.md"
_DISCARD = "python .aide/scripts/aide.py queue discard NNN"


def _generate_section() -> str:
    text = _ROADMAP.read_text(encoding="utf-8")
    return text.split("## Generate the next queue", 1)[1].split("\n## ", 1)[0]


def test_the_roadmap_runner_checks_for_the_queue_file_before_queue_pr():
    """The engine refuses `queue pr` on a branch with no queue file; the
    runner must not reach it at all, and must discard the branch and stop on
    the hand-back."""
    section = _generate_section()
    spawn = section.index("**Spawn `queue-planner`**")
    check = section.index(_QUEUE_CHECK)
    pr = section.index("aide.py queue pr --body-file")
    assert spawn < check < pr
    handback = section[check:pr]
    for phrase in ("Run nothing below", "no `queue pr`", _DISCARD,
                   "**Stop**", "hand-back verbatim"):
        assert phrase in handback, phrase


def test_the_runner_discards_through_the_verb_and_never_the_raw_git():
    """The no-commit precondition lives in the verb, not in prose copies of
    it: both places the runner discards a queue branch call it, and nothing
    in the runner types the deletion by hand."""
    text = _ROADMAP.read_text(encoding="utf-8")
    assert text.count("aide.py queue discard NNN") >= 2
    for raw in ("git branch -D", "git push origin --delete", "rev-list --count"):
        assert raw not in text, raw


@pytest.mark.parametrize("command", [
    "git ls-files docs/aide/queue/queue-012.md",
    "python .aide/scripts/aide.py queue discard 012",
])
def test_the_hand_back_steps_run_unattended(command):
    """Each step is pre-approved, asked by nothing and passed by the hook, so
    an unattended run discards the branch rather than stalling on a prompt."""
    assert rp.is_covered("Bash", command, _PERMS["allow"])
    assert not rp.is_covered("Bash", command, _PERMS["ask"])
    assert guard.violations(command) == []
