"""Consumer-owned files must read the same with or without a byte-order mark.

`install.py` and the permission reviewer read files that live in someone else's
repo — `.claude/settings.json`, the settings overlay, `.gitignore`, `.aide/VERSION`
— and those get opened in Windows editors that prepend U+FEFF. Read as plain
UTF-8 the BOM survives into the text, where it variously crashes a JSON parse or
fakes a difference that makes the installer emit a pointless `.aide-merge` on
every run.

Stdlib + pytest only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = FRAMEWORK_ROOT / "adapters" / "claude" / "scripts"

sys.path.insert(0, str(FRAMEWORK_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))
import install  # noqa: E402
import review_permissions as rp  # noqa: E402

BOM = "﻿"


# --------------------------------------------------------------------------- #
# the reviewer — the originally reported crash
# --------------------------------------------------------------------------- #
def test_bom_prefixed_settings_json_does_not_crash_the_reviewer(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(
        BOM + json.dumps({"permissions": {"allow": ["Bash(git status:*)"],
                                          "ask": ["Bash(gh pr create:*)"]}}),
        encoding="utf-8")

    allow, ask = rp.load_rules(settings)

    assert allow == ["Bash(git status:*)"]
    assert ask == ["Bash(gh pr create:*)"]


def test_bom_and_plain_settings_yield_the_same_rules(tmp_path):
    payload = {"permissions": {"allow": ["Bash(ls:*)"], "ask": []}}
    plain = tmp_path / "plain.json"
    bommed = tmp_path / "bom.json"
    plain.write_text(json.dumps(payload), encoding="utf-8")
    bommed.write_text(BOM + json.dumps(payload), encoding="utf-8")

    assert rp.load_rules(plain) == rp.load_rules(bommed)


def test_bom_prefixed_log_still_yields_records(tmp_path):
    log = tmp_path / "log.jsonl"
    record = {"event": "PreToolUse", "tool": "Bash", "detail": "ls", "id": "a"}
    log.write_text(BOM + json.dumps(record) + "\n", encoding="utf-8")

    assert rp.load_records(log) == [record]


def test_missing_settings_is_still_empty_not_an_error(tmp_path):
    assert rp.load_rules(tmp_path / "absent.json") == ([], [])


# --------------------------------------------------------------------------- #
# install.py — the overlay and the settings comparison
# --------------------------------------------------------------------------- #
def test_bom_prefixed_overlay_still_generates_settings(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True)
    overlay = claude / "settings.overlay.json"
    overlay.write_text(
        BOM + json.dumps({"permissions": {"allow": {"add": ["Bash(pytest:*)"]}}}),
        encoding="utf-8")
    base = {"permissions": {"allow": ["Bash(git status:*)"]}}
    dst = claude / "settings.json"
    log: list = []

    install._generate_settings_from_overlay(base, overlay, dst, log)

    merged = json.loads(dst.read_text(encoding="utf-8"))
    assert merged["permissions"]["allow"] == ["Bash(git status:*)", "Bash(pytest:*)"]


def test_bom_prefixed_settings_is_not_seen_as_different_from_the_base(tmp_path):
    """Otherwise every --update emits a .aide-merge for a file that matches."""
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True)
    dst = claude / "settings.json"
    base_text = json.dumps({"permissions": {"allow": []}}, indent=2) + "\n"
    dst.write_text(BOM + base_text, encoding="utf-8")

    existing_text = dst.read_text(encoding=install.CONSUMER_ENCODING)

    assert existing_text.splitlines(keepends=True) == base_text.splitlines(keepends=True)


def test_bom_prefixed_gitignore_is_not_appended_to_twice(tmp_path):
    """A BOM must not hide the marker and cause a second block to be appended.

    This block has no end marker, so it is also the hand-edited case: the
    reconcile refuses to guess at its extent, says so, and changes nothing.
    """
    gitignore = tmp_path / ".gitignore"
    body = BOM + install.GITIGNORE_MARKER + "\n.venv\n"
    gitignore.write_text(body, encoding="utf-8")
    log: list = []

    install.append_gitignore(tmp_path, log)

    text = gitignore.read_text(encoding=install.CONSUMER_ENCODING)
    assert text.count(install.GITIGNORE_MARKER) == 1
    assert gitignore.read_text(encoding="utf-8") == body, "left untouched"
    assert len(log) == 1 and install.GITIGNORE_END in log[0]


def test_bom_prefixed_gitignore_keeps_its_bom_through_a_reconcile(tmp_path):
    """Reconciling the managed block is not a licence to re-encode the file."""
    gitignore = tmp_path / ".gitignore"
    stale = (install.GITIGNORE_MARKER + "\nold-path/\n"
             + install.GITIGNORE_END + "\n")
    gitignore.write_text(BOM + ".venv\n" + stale, encoding="utf-8")

    install.append_gitignore(tmp_path, [])

    raw = gitignore.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "the consumer's BOM was dropped"
    text = gitignore.read_text(encoding=install.CONSUMER_ENCODING)
    assert "old-path/" not in text
    assert ".venv" in text, "content outside the block must survive"
    assert "docs/aide/instructions/*.jsonl" in text


def test_consumer_encoding_is_bom_tolerant():
    assert install.CONSUMER_ENCODING == "utf-8-sig"
    assert rp._ENCODING == "utf-8-sig"
