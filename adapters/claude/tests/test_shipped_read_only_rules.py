"""The shipped allow-list carries the inspection commands consumers promote (issue #317).

Consumers promoted the same project-agnostic rules — print-only ``sed -n``,
read-only git plumbing, file comparison and checksums, process probes and
no-ops — review after review. Each is held here, and so is the line the
issue drew: the ``-n`` prefix keeps ``sed -i`` prompting, and ``awk`` and
``mkdir`` stay out. The line is what a call visibly does, not a sandbox:
GNU ``sed -n`` scripts can still ``w`` and ``e``, which adds nothing to the
``Bash(python:*)`` already shipped.

Coverage is read with the reviewer's own ``is_covered``, so the test asks the
question a permission review asks. Stdlib + pytest only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
ADAPTER_SETTINGS = FRAMEWORK_ROOT / "adapters" / "claude" / "settings.json"
SCRIPTS_DIR = FRAMEWORK_ROOT / "adapters" / "claude" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))
import review_permissions as rp  # noqa: E402  (path shim above)

_PERMS = json.loads(ADAPTER_SETTINGS.read_text(encoding="utf-8"))["permissions"]


@pytest.mark.parametrize("command", [
    "sed -n '1,40p' docs/aide/progress.md",
    "git grep -n aide_check",
    "git rev-list --count main..HEAD",
    "git merge-base main HEAD",
    "git cat-file -p HEAD",
    "git diff-tree --no-commit-id -r HEAD",
    "git merge-tree --write-tree main HEAD",
    "git check-attr -a src/x.py",
    "diff a.txt b.txt",
    "cmp a.bin b.bin",
    "nl src/x.py",
    "sha256sum dist/x.whl",
    "md5sum dist/x.whl",
    "ps -ef",
    "pgrep -f pytest",
    "date -u",
    "sleep 5",
    "true",
    "printf '%s\\n' x",
])
def test_read_only_inspection_commands_are_pre_approved(command):
    assert rp.is_covered("Bash", command, _PERMS["allow"])
    assert not rp.is_covered("Bash", command, _PERMS["ask"])


@pytest.mark.parametrize("command", [
    "sed -i 's/a/b/' src/x.py",
    "sed 's/a/b/' src/x.py",
    "awk '{print $1}' src/x.py",
    "mkdir build",
])
def test_the_commands_the_issue_kept_out_still_prompt(command):
    assert not rp.is_covered("Bash", command, _PERMS["allow"])
