"""Promoted permission rules must land in the file that survives an update.

Once a project adopts ``.claude/settings.overlay.json``, ``settings.json`` is a
GENERATED artifact — ``install.py --update`` rewrites it as base+overlay — so a
rule promoted into ``settings.json`` is silently discarded on the next update.
The reviewer therefore has to name the overlay's additive
``permissions.allow.add`` list as the destination whenever an overlay exists,
and only fall back to ``settings.json`` when it does not.

Stdlib + pytest only; the reviewer script is imported as a module.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = FRAMEWORK_ROOT / "adapters" / "claude" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))
import review_permissions as rp  # noqa: E402  (path shim above)


def _settings(tmp_path: Path) -> Path:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"permissions": {"allow": ["Bash(git status:*)"]}}),
                    encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# promotion_target — the routing decision
# --------------------------------------------------------------------------- #
def test_no_overlay_targets_settings_json(tmp_path):
    settings = _settings(tmp_path)
    overlay = tmp_path / "settings.overlay.json"  # deliberately absent

    target, location = rp.promotion_target(settings, overlay)

    assert target == settings
    assert location == "permissions.allow"


def test_adopted_overlay_targets_the_additive_list(tmp_path):
    settings = _settings(tmp_path)
    overlay = tmp_path / "settings.overlay.json"
    overlay.write_text(json.dumps({"permissions": {"allow": {"add": []}}}), encoding="utf-8")

    target, location = rp.promotion_target(settings, overlay)

    assert target == overlay
    assert location == "permissions.allow.add"


def test_overlay_wins_even_when_it_is_an_empty_object(tmp_path):
    """Adoption is signalled by the file existing, not by its content."""
    settings = _settings(tmp_path)
    overlay = tmp_path / "settings.overlay.json"
    overlay.write_text("{}", encoding="utf-8")

    target, location = rp.promotion_target(settings, overlay)

    assert target == overlay
    assert location == "permissions.allow.add"


def test_the_example_scaffold_does_not_count_as_adoption(tmp_path):
    """install.py drops a `.example` on every run; it is inert until copied."""
    settings = _settings(tmp_path)
    overlay = tmp_path / "settings.overlay.json"
    (tmp_path / "settings.overlay.json.example").write_text("{}", encoding="utf-8")

    target, location = rp.promotion_target(settings, overlay)

    assert target == settings
    assert location == "permissions.allow"


def test_a_directory_named_like_the_overlay_is_not_adoption(tmp_path):
    settings = _settings(tmp_path)
    overlay = tmp_path / "settings.overlay.json"
    overlay.mkdir()

    target, location = rp.promotion_target(settings, overlay)

    assert target == settings
    assert location == "permissions.allow"


def test_promotion_target_writes_nothing(tmp_path):
    """Pure: safe to call before the user has confirmed anything."""
    settings = _settings(tmp_path)
    overlay = tmp_path / "settings.overlay.json"
    before = sorted(p.name for p in tmp_path.iterdir())

    rp.promotion_target(settings, overlay)

    assert sorted(p.name for p in tmp_path.iterdir()) == before


# --------------------------------------------------------------------------- #
# render_promotion_hint — what the human is actually told
# --------------------------------------------------------------------------- #
def test_hint_without_overlay_names_settings_json_and_omits_the_warning(tmp_path):
    settings = _settings(tmp_path)
    overlay = tmp_path / "settings.overlay.json"

    hint = rp.render_promotion_hint(settings, overlay)

    assert "permissions.allow in settings.json" in hint
    assert "GENERATED" not in hint


def test_hint_with_overlay_names_the_add_list_and_warns_about_regeneration(tmp_path):
    settings = _settings(tmp_path)
    overlay = tmp_path / "settings.overlay.json"
    overlay.write_text("{}", encoding="utf-8")

    hint = rp.render_promotion_hint(settings, overlay)

    assert "permissions.allow.add" in hint
    assert "settings.overlay.json" in hint
    assert "GENERATED" in hint


def test_hint_always_keeps_the_pr_requirement(tmp_path):
    settings = _settings(tmp_path)
    overlay = tmp_path / "settings.overlay.json"
    assert "PR" in rp.render_promotion_hint(settings, overlay)
    overlay.write_text("{}", encoding="utf-8")
    assert "PR" in rp.render_promotion_hint(settings, overlay)


# --------------------------------------------------------------------------- #
# main — the routing reaches the reported output
# --------------------------------------------------------------------------- #
def _log_with_one_prompted_call(tmp_path: Path) -> Path:
    log = tmp_path / "log.jsonl"
    records = [
        {"event": "PreToolUse", "tool": "Bash", "detail": "gh pr view 12", "id": "a"},
        {"event": "PostToolUse", "tool": "Bash", "detail": "gh pr view 12", "id": "a"},
    ]
    log.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return log


def test_json_output_reports_the_overlay_as_the_target(tmp_path, capsys):
    settings = _settings(tmp_path)
    overlay = tmp_path / "settings.overlay.json"
    overlay.write_text("{}", encoding="utf-8")
    log = _log_with_one_prompted_call(tmp_path)

    rp.main(["--log", str(log), "--settings", str(settings),
             "--overlay", str(overlay), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["promotion_target"]["location"] == "permissions.allow.add"
    assert payload["promotion_target"]["path"] == str(overlay)


def test_json_output_falls_back_to_settings_json(tmp_path, capsys):
    settings = _settings(tmp_path)
    overlay = tmp_path / "settings.overlay.json"
    log = _log_with_one_prompted_call(tmp_path)

    rp.main(["--log", str(log), "--settings", str(settings),
             "--overlay", str(overlay), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["promotion_target"]["location"] == "permissions.allow"
    assert payload["promotion_target"]["path"] == str(settings)


def test_the_command_rotates_the_log_it_reviewed():
    """Step 5 of `/aide-review-permissions` once ran `--rotate` with no log
    argument, so a review of a log named by argument truncated the DEFAULT
    log — records nobody had read. The rotate step must say the same `--log`
    goes with it; the sibling `/aide-review-instructions` pins the same rule."""
    command = (FRAMEWORK_ROOT / "adapters" / "claude" / "commands"
               / "aide-review-permissions.md").read_text(encoding="utf-8")
    rotate_at = command.index("--rotate")
    after = command[rotate_at:rotate_at + 400]
    assert "--log" in after, "the rotate step names no --log for a reviewed argument"
