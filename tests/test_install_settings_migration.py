"""`migrate_settings` — the one rewrite a kept `settings.json` receives.

A consumer without an overlay keeps its `settings.json` on every update, so a
fix to a hook wrapper the framework wrote there (issue #272: the script path
was cwd-relative, and a worktree-isolated sub-agent ran the wrong copy or
none) and an allow entry an unattended run needs (issue #274:
`await_run.py`) would never reach it. The migration rewrites exactly the
strings a release wrote and adds exactly those entries — and nothing a
project chose.

Stdlib + pytest only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_DIR = FRAMEWORK_ROOT / "adapters" / "claude"

sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402

BOM = "\ufeff"

# What 2.3.0 shipped, verbatim: the strings every current consumer holds.
_WRAPPER_2_3_0 = ("sh -c 'for py in python3 python; do command -v \"$py\" "
                  ">/dev/null 2>&1 || continue; \"$py\" -c \"\" >/dev/null 2>&1 "
                  "|| continue; exec \"$py\" \"$@\"; done; exit 0' _ ")
_SCRIPTS = ("command_hygiene_guard.py", "log_permission_event.py",
            "sibling_instructions.py", "log_instructions_loaded.py")


def _base() -> dict:
    return json.loads((ADAPTER_DIR / "settings.json").read_text(encoding="utf-8"))


def _current(script: str) -> str:
    return next(h["command"] for h in install._hook_entries(_base())
                if h["command"].endswith(f"/{script}"))


def _as_2_3_0(settings: dict) -> dict:
    """*settings* with every framework hook as 2.3.0 wrote it, and without the
    allow entries 2.4.0 added."""
    for hook in install._hook_entries(settings):
        script = hook["command"].rsplit("/", 1)[-1]
        hook["command"] = _WRAPPER_2_3_0 + f".claude/hooks/{script}"
    allow = settings["permissions"]["allow"]
    settings["permissions"]["allow"] = [e for e in allow
                                        if e not in install._MIGRATED_ALLOW]
    return settings


def _write(path: Path, settings: dict, bom: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bom + json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding=install.CONSUMER_ENCODING))


def test_a_2_3_0_settings_file_becomes_the_framework_base(tmp_path: Path):
    dst = tmp_path / "settings.json"
    _write(dst, _as_2_3_0(_base()))
    edits = install.migrate_settings(_base(), dst, [])
    assert len(edits) == 5 + len(install._MIGRATED_ALLOW)
    assert _read(dst) == _base()
    # Byte for byte, too, so the comparison that follows reports it unchanged
    # rather than writing a .aide-merge over a file that now matches.
    assert dst.read_text(encoding="utf-8") == (
        ADAPTER_DIR / "settings.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("old", [
    "python .claude/hooks/command_hygiene_guard.py",
    "sh -c 'exec $(command -v python3 || command -v python) $@' _ "
    ".claude/hooks/command_hygiene_guard.py",
    _WRAPPER_2_3_0 + ".claude/hooks/command_hygiene_guard.py",
])
def test_every_wrapper_a_release_wrote_is_rewritten(tmp_path: Path, old: str):
    settings = _base()
    guard = next(h for h in install._hook_entries(settings)
                 if h["command"].endswith("command_hygiene_guard.py"))
    guard["command"] = old
    dst = tmp_path / "settings.json"
    _write(dst, settings)
    install.migrate_settings(_base(), dst, [])
    assert _current("command_hygiene_guard.py") in [
        h["command"] for h in install._hook_entries(_read(dst))]


def test_each_retired_wrapper_maps_to_a_hook_the_base_still_has():
    """A script dropped from the base would make its old strings match
    nothing, silently — say so here instead."""
    names = {h["command"].rsplit("/", 1)[-1]
             for h in install._hook_entries(_base())}
    for _template, scripts in install._RETIRED_HOOK_COMMANDS:
        assert set(scripts) <= names


def test_the_2_3_0_template_is_what_2_3_0_shipped():
    templates = [t for t, _ in install._RETIRED_HOOK_COMMANDS]
    for script in _SCRIPTS:
        assert (_WRAPPER_2_3_0 + ".claude/hooks/{}").format(script) in [
            t.format(script) for t in templates]


def test_a_projects_own_hooks_and_edited_framework_hooks_are_untouched(tmp_path: Path):
    settings = _as_2_3_0(_base())
    own = {"type": "command", "command": "python scripts/my_hook.py"}
    settings["hooks"]["PreToolUse"].append({"matcher": "Bash", "hooks": [own]})
    edited = _WRAPPER_2_3_0 + ".claude/hooks/command_hygiene_guard.py --verbose"
    guard = next(h for h in install._hook_entries(settings)
                 if "command_hygiene_guard" in h["command"])
    guard["command"] = edited
    settings["env"] = {"PROJECT": "1"}
    settings["permissions"]["deny"] = ["Bash(rm -rf:*)"]
    dst = tmp_path / "settings.json"
    _write(dst, settings)

    install.migrate_settings(_base(), dst, [])
    after = _read(dst)
    commands = [h["command"] for h in install._hook_entries(after)]
    assert "python scripts/my_hook.py" in commands
    assert edited in commands
    assert after["env"] == {"PROJECT": "1"}
    assert after["permissions"]["deny"] == ["Bash(rm -rf:*)"]
    # The untouched-by-the-project framework hooks were still rewritten.
    assert _current("log_permission_event.py") in commands


def test_allow_entries_land_after_the_engines_and_keep_the_rest_in_order(tmp_path: Path):
    settings = {"permissions": {"allow": [
        "Read", "Bash(python .aide/scripts/aide.py:*)", "Bash(ls:*)"]}}
    dst = tmp_path / "settings.json"
    _write(dst, settings)
    install.migrate_settings(_base(), dst, [])
    assert _read(dst)["permissions"]["allow"] == [
        "Read", "Bash(python .aide/scripts/aide.py:*)",
        *install._MIGRATED_ALLOW, "Bash(ls:*)"]


def test_the_migrated_allow_entries_are_the_bases():
    allow = _base()["permissions"]["allow"]
    for entry in install._MIGRATED_ALLOW:
        assert entry in allow


def test_it_is_idempotent(tmp_path: Path):
    dst = tmp_path / "settings.json"
    _write(dst, _as_2_3_0(_base()))
    assert install.migrate_settings(_base(), dst, [])
    once = dst.read_bytes()
    log: list = []
    assert install.migrate_settings(_base(), dst, log) == []
    assert log == []
    assert dst.read_bytes() == once


def test_a_file_needing_nothing_is_not_rewritten(tmp_path: Path):
    """Not even re-serialised: a consumer's formatting is theirs."""
    dst = tmp_path / "settings.json"
    text = '{"permissions": {"allow": ["Bash(python .claude/scripts/await_run.py:*)",' \
           ' "Bash(python3 .claude/scripts/await_run.py:*)"]}}'
    dst.write_text(text, encoding="utf-8")
    assert install.migrate_settings(_base(), dst, []) == []
    assert dst.read_text(encoding="utf-8") == text


def test_a_bom_survives_the_rewrite(tmp_path: Path):
    dst = tmp_path / "settings.json"
    _write(dst, _as_2_3_0(_base()), bom=BOM)
    install.migrate_settings(_base(), dst, [])
    assert dst.read_bytes().startswith(b"\xef\xbb\xbf")
    assert _read(dst) == _base()


def test_a_file_that_does_not_parse_is_left_alone(tmp_path: Path):
    dst = tmp_path / "settings.json"
    dst.write_text("{ not json", encoding="utf-8")
    assert install.migrate_settings(_base(), dst, []) == []
    assert dst.read_text(encoding="utf-8") == "{ not json"


def test_windows_shaped_strings_are_matched_as_data(tmp_path: Path):
    """Backslashes and a drive letter in a project's own hook are data to the
    match — neither rewritten nor mangled on the way back out."""
    own = r'C:\Program Files\Python312\python.exe C:\repo\.claude\hooks\mine.py'
    settings = _as_2_3_0(_base())
    settings["hooks"]["PostToolUse"][0]["hooks"].append(
        {"type": "command", "command": own})
    dst = tmp_path / "settings.json"
    _write(dst, settings)
    install.migrate_settings(_base(), dst, [])
    assert own in [h["command"] for h in install._hook_entries(_read(dst))]


def test_install_settings_migrates_then_keeps(tmp_path: Path):
    """Through the entry point: the rewrite lands, the log names it, and a file
    that was the 2.3.0 base now matches and is reported unchanged."""
    claude = tmp_path / ".claude"
    _write(claude / "settings.json", _as_2_3_0(_base()))
    log: list = []
    install.install_settings(ADAPTER_DIR, claude, tmp_path, log)
    assert _read(claude / "settings.json") == _base()
    assert any("resolves its script from the project root" in line for line in log)
    assert any("(unchanged)" in line for line in log)
    assert not (tmp_path / ".aide-merge").exists()


def test_an_overlay_consumer_gets_the_anchored_wrapper_by_regeneration(tmp_path: Path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text(
        json.dumps(_as_2_3_0(_base()), indent=2), encoding="utf-8")
    (claude / install.SETTINGS_OVERLAY).write_text(
        '{"env": {"MARK": "1"}}', encoding="utf-8")
    install.install_settings(ADAPTER_DIR, claude, tmp_path, [])
    after = _read(claude / "settings.json")
    assert [h["command"] for h in install._hook_entries(after)] == [
        h["command"] for h in install._hook_entries(_base())]
    for entry in install._MIGRATED_ALLOW:
        assert entry in after["permissions"]["allow"]
