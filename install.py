#!/usr/bin/env python3
"""install.py — cross-OS installer for the AIDE framework (STUB).

See /HANDOFF.md task D and /docs/framework-standalone-plan.md §3.1.

`python install.py --adapter claude --into <target-repo>` must:
  1. copy core/                       -> <target>/.aide/
  2. copy adapters/claude/{agents,skills,commands,hooks,scripts,settings.json}
                                      -> <target>/.claude/   (NON-CLOBBERING merge;
     never overwrite an existing settings.json — emit a .aide-merge diff instead)
  3. copy adapters/claude/usage_probe.py -> <target>/.aide/loop/
  4. scaffold <target>/aide.toml from a template (prompt for source_dir,
     test_command, git.mode)
  5. append the framework .gitignore block if absent
  6. record the installed VERSION in aide.toml for later `install.py --update`

`--update` re-copies core/ (+ the adapter control files) but NEVER touches
<target>/docs/aide/ or aide.toml (owned by the project). Stdlib-only.
"""
import sys
raise SystemExit("install.py is a stub — implement per /HANDOFF.md task D.")
