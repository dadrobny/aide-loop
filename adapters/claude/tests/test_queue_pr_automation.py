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
raw forms, and no agent, command, skill or rule names one. Stdlib + pytest
only.
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
