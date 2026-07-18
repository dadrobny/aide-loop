#!/usr/bin/env python3
"""install.py — cross-OS installer for the AIDE framework.

Materialises the three-layer framework (see docs/framework-standalone-plan.md §3)
into a target repo:

    python install.py --adapter claude --into <target-repo>

  1. copy  core/                              -> <target>/.aide/
  2. copy  adapters/<adapter>/{agents,skills,commands,hooks,scripts,settings.json}
                                              -> <target>/.claude/
           (NON-CLOBBERING on settings.json — an existing one is never
            overwritten; the framework's version is emitted as a <target>/.aide-merge
            diff for a human to reconcile.)
  3. copy  adapters/<adapter>/usage_probe.py  -> <target>/.aide/loop/   (plan §4.4 seam)
  4. scaffold <target>/aide.toml from a template (prompts for source_dir,
     test_command, git.mode; skipped if aide.toml already exists)
  5. append the framework .gitignore block if absent
  6. record the installed VERSION (from core/VERSION) — in the scaffolded aide.toml
     and, authoritatively, as the copied-in <target>/.aide/VERSION

    python install.py --adapter claude --into <target-repo> --update

  re-copies core/ (+ the adapter control files, + usage_probe.py) so the engine
  tracks the framework, but NEVER touches <target>/aide.toml or <target>/docs/aide/
  (owned by the project). settings.json stays non-clobbering on --update too.

Stdlib-only, so it runs on any OS with the Python the engine already needs.
"""
from __future__ import annotations

import argparse
import difflib
import shutil
import sys
from pathlib import Path
from typing import List, Optional

FRAMEWORK_ROOT = Path(__file__).resolve().parent

# Adapter control files copied into <target>/.claude/. Everything else under
# adapters/<name>/ (README.md, usage_probe.py) is handled out of band.
ADAPTER_CONTROL = ("agents", "skills", "commands", "hooks", "scripts")
ADAPTER_SETTINGS = "settings.json"

# Names never copied out of the source tree (junk / private per-machine config).
SKIP_NAMES = {"__pycache__", ".DS_Store", "loop.local.toml"}
SKIP_SUFFIXES = {".pyc"}

GITIGNORE_MARKER = "# --- AIDE framework (managed by aide-loop install.py) ---"
GITIGNORE_BLOCK = f"""\
{GITIGNORE_MARKER}
.aide/**/__pycache__/
.aide/loop/loop.local.toml
.aide-merge
# --- end AIDE ---
"""

AIDE_TOML_TEMPLATE = """\
# aide.toml — AIDE project config. Owned by THIS project, not the framework.
# `install.py --update` never overwrites this file; edit it freely.

[project]
name = "{name}"
source_dir = "{source_dir}"
docs_dir = "docs/aide"

[python]
test_command = "{test_command}"

[git]
mode = "{git_mode}"
main_branch = "main"
branch_prefix = "aide/"

[loop]
queue_cap = 10
clarify = "assume"

[aide]
# Framework version at install time (from aide-loop core/VERSION). Informational —
# the live installed engine version is the copied-in .aide/VERSION.
version = "{version}"
adapter = "{adapter}"
"""

GIT_MODES = ("auto-merge", "pr", "local")


# --------------------------------------------------------------------------- #
# copy helpers
# --------------------------------------------------------------------------- #
def _skip(path: Path) -> bool:
    return path.name in SKIP_NAMES or path.suffix in SKIP_SUFFIXES


def copy_tree(src: Path, dst: Path, log: List[str]) -> None:
    """Recursively copy ``src`` into ``dst``, merging into an existing ``dst`` and
    skipping junk / private files. Existing files are overwritten (framework-owned)."""
    dst.mkdir(parents=True, exist_ok=True)
    for child in sorted(src.iterdir()):
        if _skip(child):
            continue
        target = dst / child.name
        if child.is_dir():
            copy_tree(child, target, log)
        else:
            existed = target.exists()
            shutil.copy2(child, target)
            log.append(f"  {'~' if existed else '+'} {target}")


def copy_file(src: Path, dst: Path, log: List[str]) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    existed = dst.exists()
    shutil.copy2(src, dst)
    log.append(f"  {'~' if existed else '+'} {dst}")


# --------------------------------------------------------------------------- #
# settings.json — non-clobbering merge
# --------------------------------------------------------------------------- #
def install_settings(adapter_dir: Path, claude_dir: Path, target: Path, log: List[str]) -> None:
    """Copy settings.json if absent; otherwise leave the existing one and emit a
    unified diff to <target>/.aide-merge for a human to reconcile."""
    src = adapter_dir / ADAPTER_SETTINGS
    if not src.is_file():
        return
    dst = claude_dir / ADAPTER_SETTINGS
    if not dst.exists():
        copy_file(src, dst, log)
        return

    existing = dst.read_text(encoding="utf-8").splitlines(keepends=True)
    incoming = src.read_text(encoding="utf-8").splitlines(keepends=True)
    if existing == incoming:
        log.append(f"  = {dst} (unchanged)")
        return

    diff = "".join(
        difflib.unified_diff(existing, incoming, fromfile="a/.claude/settings.json",
                             tofile="b/.claude/settings.json (framework)")
    )
    merge_path = target / ".aide-merge"
    header = (
        "# AIDE install: .claude/settings.json already exists and was NOT "
        "overwritten.\n"
        "# Below is a diff from your version to the framework's. Reconcile by hand,\n"
        "# then delete this file.\n\n"
    )
    merge_path.write_text(header + diff, encoding="utf-8")
    log.append(f"  ! {dst} kept (existing) — diff written to {merge_path}")


# --------------------------------------------------------------------------- #
# aide.toml scaffold + .gitignore
# --------------------------------------------------------------------------- #
def prompt(label: str, default: str, interactive: bool, choices: Optional[tuple] = None) -> str:
    if not interactive:
        return default
    hint = f" [{'/'.join(choices)}]" if choices else ""
    while True:
        raw = input(f"{label}{hint} ({default}): ").strip()
        value = raw or default
        if choices and value not in choices:
            print(f"  choose one of {', '.join(choices)}")
            continue
        return value


def scaffold_aide_toml(target: Path, adapter: str, version: str, args: argparse.Namespace,
                       log: List[str]) -> None:
    path = target / "aide.toml"
    if path.exists():
        log.append(f"  = {path} (exists — left untouched)")
        return

    interactive = not args.yes and sys.stdin.isatty()
    name = args.name or target.resolve().name
    source_dir = args.source_dir or prompt("source_dir", "src", interactive)
    test_command = args.test_command or prompt("test_command", "python -m pytest", interactive)
    git_mode = args.git_mode or prompt("git.mode", "auto-merge", interactive, GIT_MODES)

    path.write_text(
        AIDE_TOML_TEMPLATE.format(
            name=name, source_dir=source_dir, test_command=test_command,
            git_mode=git_mode, version=version, adapter=adapter,
        ),
        encoding="utf-8",
    )
    log.append(f"  + {path}")


def append_gitignore(target: Path, log: List[str]) -> None:
    path = target / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if GITIGNORE_MARKER in existing:
        return
    sep = "" if (not existing or existing.endswith("\n")) else "\n"
    prefix = "\n" if existing and not existing.endswith("\n\n") else ""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(sep + prefix + GITIGNORE_BLOCK)
    log.append(f"  {'~' if existing else '+'} {path} (AIDE block appended)")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def run(args: argparse.Namespace) -> int:
    adapter_dir = FRAMEWORK_ROOT / "adapters" / args.adapter
    core_dir = FRAMEWORK_ROOT / "core"
    if not adapter_dir.is_dir():
        print(f"error: unknown adapter '{args.adapter}' (no {adapter_dir})", file=sys.stderr)
        return 2
    if not (core_dir / "VERSION").is_file():
        print(f"error: framework core not found at {core_dir}", file=sys.stderr)
        return 2

    target = args.into.resolve()
    if not target.is_dir():
        print(f"error: --into target does not exist: {target}", file=sys.stderr)
        return 2

    version = (core_dir / "VERSION").read_text(encoding="utf-8").strip()
    aide_dir = target / ".aide"
    claude_dir = target / ".claude"
    log: List[str] = []

    mode = "update" if args.update else "install"
    print(f"AIDE {mode}: {args.adapter} v{version} -> {target}")

    # 1. engine -> .aide/
    copy_tree(core_dir, aide_dir, log)

    # 2. adapter control files -> .claude/
    for name in ADAPTER_CONTROL:
        src = adapter_dir / name
        if src.is_dir():
            copy_tree(src, claude_dir / name, log)
    install_settings(adapter_dir, claude_dir, target, log)

    # 3. usage probe -> .aide/loop/  (the plan §4.4 seam)
    probe = adapter_dir / "usage_probe.py"
    if probe.is_file():
        copy_file(probe, aide_dir / "loop" / "usage_probe.py", log)

    # 4-6. project-owned scaffolding — fresh install only
    if not args.update:
        scaffold_aide_toml(target, args.adapter, version, args, log)
        append_gitignore(target, log)
    else:
        # --update honours the project boundary: aide.toml and docs/aide/ untouched.
        log.append("  = aide.toml, docs/aide/ (left untouched — project-owned)")

    print("\n".join(log))
    print(f"\nDone. Installed engine version recorded at {aide_dir / 'VERSION'}.")
    if not args.update:
        print("Next: `python .aide/scripts/aide.py check` in the target repo.")
        print("Before any unattended run: launch the runtime once interactively in the")
        print("repo (to answer any one-time trusted-folder prompt) — see the adapter's")
        print("execution-surfaces.md for the launch-surface contract.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Install/update the AIDE framework into a repo.")
    p.add_argument("--adapter", default="claude", help="adapter to install (default: claude)")
    p.add_argument("--into", type=Path, required=True, help="target repo to install into")
    p.add_argument("--update", action="store_true",
                   help="re-copy engine + adapter; never touch aide.toml or docs/aide/")
    p.add_argument("--yes", action="store_true", help="accept defaults; never prompt")
    p.add_argument("--name", default=None, help="project name for aide.toml (default: target dir name)")
    p.add_argument("--source-dir", dest="source_dir", default=None, help="[project] source_dir")
    p.add_argument("--test-command", dest="test_command", default=None, help="[python] test_command")
    p.add_argument("--git-mode", dest="git_mode", choices=GIT_MODES, default=None, help="[git] mode")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
