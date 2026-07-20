"""Deterministic settings reconciliation — the project-owned overlay (WI-7g).

``install.py`` no longer forces a human to hand-reconcile ``.aide-merge`` for the
common case. A project keeps ``.claude/settings.overlay.json`` (owned like
``aide.toml``); while it exists, ``.claude/settings.json`` is REGENERATED on every
install/update as a deterministic deep-merge of the framework base and the
overlay. These tests pin the merge algebra (the robust core), the install-time
branching, and the backward-compatible legacy path.

Stdlib + pytest only; ``install.py`` is imported as a module.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
ADAPTER_DIR = FRAMEWORK_ROOT / "adapters" / "claude"
ADAPTER_SETTINGS = ADAPTER_DIR / "settings.json"

sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)


# --------------------------------------------------------------------------- #
# merge_overlay — the pure algebra
# --------------------------------------------------------------------------- #
def test_empty_overlay_is_identity():
    base = {"a": 1, "b": {"c": [1, 2]}}
    merged, warnings = install.merge_overlay(base, {})
    assert merged == base
    assert warnings == []


def test_scalar_and_object_deep_merge_overlay_wins():
    base = {"permissions": {"defaultMode": "default", "keep": 1}}
    overlay = {"permissions": {"defaultMode": "acceptEdits"}}
    merged, _ = install.merge_overlay(base, overlay)
    assert merged == {"permissions": {"defaultMode": "acceptEdits", "keep": 1}}


def test_add_appends_dedup_and_preserves_base_order():
    base = {"permissions": {"allow": ["Read", "Grep"]}}
    overlay = {"permissions": {"allow": {"add": ["Grep", "Write"]}}}
    merged, warnings = install.merge_overlay(base, overlay)
    # Grep already present is deduped; base order preserved, additions appended.
    assert merged["permissions"]["allow"] == ["Read", "Grep", "Write"]
    assert warnings == []


def test_remove_drops_entry():
    base = {"permissions": {"allow": ["Read", "Grep", "Glob"]}}
    overlay = {"permissions": {"allow": {"remove": ["Grep"]}}}
    merged, warnings = install.merge_overlay(base, overlay)
    assert merged["permissions"]["allow"] == ["Read", "Glob"]
    assert warnings == []


def test_remove_of_absent_entry_warns_but_does_not_fail():
    base = {"permissions": {"allow": ["Read"]}}
    overlay = {"permissions": {"allow": {"remove": ["Grep"]}}}
    merged, warnings = install.merge_overlay(base, overlay)
    assert merged["permissions"]["allow"] == ["Read"]
    assert len(warnings) == 1
    assert "stale" in warnings[0] and "Grep" in warnings[0]


def test_operator_creates_a_list_absent_from_the_base():
    # deny is not shipped by the base; an operator can still introduce it.
    base = {"permissions": {"allow": ["Read"]}}
    overlay = {"permissions": {"deny": {"add": ["Bash(python:*)"]}}}
    merged, warnings = install.merge_overlay(base, overlay)
    assert merged["permissions"]["deny"] == ["Bash(python:*)"]
    assert warnings == []


def test_operator_dedupes_objects_by_deep_equality():
    group = {"matcher": "Bash", "hooks": [{"type": "command", "command": "x"}]}
    other = {"matcher": "Edit", "hooks": []}
    base = {"hooks": {"PreToolUse": [group]}}
    overlay = {"hooks": {"PreToolUse": {"add": [dict(group), other]}}}
    merged, _ = install.merge_overlay(base, overlay)
    # The identical group is not duplicated; the genuinely new one is appended.
    assert merged["hooks"]["PreToolUse"] == [group, other]


def test_plain_list_replaces_outright():
    base = {"permissions": {"allow": ["Read", "Grep"]}}
    overlay = {"permissions": {"allow": ["OnlyThis"]}}
    merged, _ = install.merge_overlay(base, overlay)
    assert merged["permissions"]["allow"] == ["OnlyThis"]


def test_comment_keys_are_dropped_from_output():
    base = {"a": 1}
    overlay = {"//": "a note", "//help": ["more"], "b": 2}
    merged, _ = install.merge_overlay(base, overlay)
    assert merged == {"a": 1, "b": 2}


def test_operator_on_non_list_base_raises():
    base = {"permissions": {"defaultMode": "default"}}
    overlay = {"permissions": {"defaultMode": {"add": ["x"]}}}
    with pytest.raises(install.OverlayError):
        install.merge_overlay(base, overlay)


def test_object_over_scalar_raises():
    base = {"permissions": {"defaultMode": "default"}}
    overlay = {"permissions": {"defaultMode": {"nested": 1}}}
    with pytest.raises(install.OverlayError):
        install.merge_overlay(base, overlay)


def test_add_remove_must_be_lists():
    base = {"permissions": {"allow": ["Read"]}}
    overlay = {"permissions": {"allow": {"add": "Write"}}}
    with pytest.raises(install.OverlayError):
        install.merge_overlay(base, overlay)


def test_merge_is_pure_no_mutation():
    base = {"permissions": {"allow": ["Read"]}}
    overlay = {"permissions": {"allow": {"add": ["Write"]}}}
    base_snapshot = json.loads(json.dumps(base))
    install.merge_overlay(base, overlay)
    assert base == base_snapshot  # inputs untouched


def test_merge_is_idempotent():
    base = json.loads(ADAPTER_SETTINGS.read_text(encoding="utf-8"))
    overlay = {"permissions": {"allow": {"add": ["Bash(cargo test:*)"]},
                               "deny": {"add": ["Bash(python:*)"]}}}
    once, _ = install.merge_overlay(base, overlay)
    twice, _ = install.merge_overlay(once, overlay)
    assert once == twice


# --------------------------------------------------------------------------- #
# the committed example overlay is valid and inert
# --------------------------------------------------------------------------- #
def test_example_body_is_valid_json_and_a_no_op():
    base = json.loads(ADAPTER_SETTINGS.read_text(encoding="utf-8"))
    overlay = json.loads(install.SETTINGS_OVERLAY_EXAMPLE_BODY)
    merged, warnings = install.merge_overlay(base, overlay)
    assert merged == base, "activating the example unchanged must not alter settings"
    assert warnings == []


# --------------------------------------------------------------------------- #
# install_settings — the three install-time paths
# --------------------------------------------------------------------------- #
def _dirs(tmp_path: Path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    return claude, tmp_path  # (claude_dir, target)


def test_overlay_present_regenerates_settings(tmp_path):
    claude, target = _dirs(tmp_path)
    (claude / install.SETTINGS_OVERLAY).write_text(
        json.dumps({"permissions": {"allow": {"add": ["Bash(cargo test:*)"]}}}),
        encoding="utf-8",
    )
    log: list = []
    install.install_settings(ADAPTER_DIR, claude, target, log)

    generated = json.loads((claude / install.ADAPTER_SETTINGS).read_text("utf-8"))
    base = json.loads(ADAPTER_SETTINGS.read_text("utf-8"))
    assert "Bash(cargo test:*)" in generated["permissions"]["allow"]
    # everything else flows from the framework base unchanged
    assert generated["permissions"]["ask"] == base["permissions"]["ask"]
    assert not (target / ".aide-merge").exists()  # no manual reconcile


def test_overlay_present_update_pulls_new_base(tmp_path):
    """A framework update changes the base; the overlay reapplies over the NEW base."""
    claude, target = _dirs(tmp_path)
    (claude / install.SETTINGS_OVERLAY).write_text(
        json.dumps({"permissions": {"allow": {"add": ["Project(x)"]}}}), encoding="utf-8"
    )
    # a stale generated settings.json from a previous version
    (claude / install.ADAPTER_SETTINGS).write_text('{"old": true}', encoding="utf-8")

    install.install_settings(ADAPTER_DIR, claude, target, [])
    generated = json.loads((claude / install.ADAPTER_SETTINGS).read_text("utf-8"))
    assert "old" not in generated                      # stale content gone
    assert "$schema" in generated                      # new base present
    assert "Project(x)" in generated["permissions"]["allow"]


def test_fresh_install_copies_base_and_scaffolds_example(tmp_path):
    claude, target = _dirs(tmp_path)
    install.install_settings(ADAPTER_DIR, claude, target, [])

    copied = (claude / install.ADAPTER_SETTINGS).read_text("utf-8")
    assert copied == ADAPTER_SETTINGS.read_text("utf-8")   # verbatim base
    example = claude / install.SETTINGS_OVERLAY_EXAMPLE
    assert example.is_file()
    json.loads(example.read_text("utf-8"))                 # scaffold is valid JSON
    assert not (target / ".aide-merge").exists()


def test_legacy_non_clobber_when_settings_differs_and_no_overlay(tmp_path):
    claude, target = _dirs(tmp_path)
    (claude / install.ADAPTER_SETTINGS).write_text(
        '{"permissions": {"allow": ["Read"]}}', encoding="utf-8"
    )
    install.install_settings(ADAPTER_DIR, claude, target, [])

    # existing file untouched, diff emitted, and the migration path is scaffolded
    assert json.loads((claude / install.ADAPTER_SETTINGS).read_text("utf-8")) == {
        "permissions": {"allow": ["Read"]}
    }
    merge = (target / ".aide-merge").read_text("utf-8")
    assert install.SETTINGS_OVERLAY in merge  # points at the overlay migration
    assert (claude / install.SETTINGS_OVERLAY_EXAMPLE).is_file()


def test_malformed_overlay_raises_and_never_writes_settings(tmp_path):
    claude, target = _dirs(tmp_path)
    (claude / install.SETTINGS_OVERLAY).write_text("{ not json", encoding="utf-8")
    with pytest.raises(install.OverlayError):
        install.install_settings(ADAPTER_DIR, claude, target, [])
    assert not (claude / install.ADAPTER_SETTINGS).exists()  # no broken output


def test_conflicting_overlay_raises_and_never_writes_settings(tmp_path):
    claude, target = _dirs(tmp_path)
    # defaultMode is a scalar in the base; an operator against it is irreconcilable
    (claude / install.SETTINGS_OVERLAY).write_text(
        json.dumps({"permissions": {"defaultMode": {"add": ["x"]}}}), encoding="utf-8"
    )
    with pytest.raises(install.OverlayError):
        install.install_settings(ADAPTER_DIR, claude, target, [])
    assert not (claude / install.ADAPTER_SETTINGS).exists()
