#!/usr/bin/env python3
"""install.py — cross-OS installer for the AIDE framework.

Materialises the three-layer framework (see docs/framework-standalone-plan.md §3)
into a target repo:

    python install.py --adapter claude --into <target-repo>

  1. copy  core/                              -> <target>/.aide/
  2. copy  adapters/<adapter>/{agents,skills,commands,hooks,scripts,settings.json}
                                              -> <target>/.claude/
           settings.json reconciliation depends on whether the project has
           adopted an overlay (see `install_settings`):
             * <target>/.claude/settings.overlay.json present -> settings.json is
               REGENERATED as a deterministic deep-merge of the framework base
               and the project overlay (framework updates flow through; project
               additions reapply). settings.json becomes a generated artifact —
               edit the overlay, not it.
             * no overlay, existing settings.json -> NON-CLOBBERING: the existing
               file is kept and the framework's version is emitted as a
               <target>/.aide-merge diff for a human to reconcile.
             * fresh install -> the base is copied and an inert
               settings.overlay.json.example is scaffolded so the overlay
               mechanism is discoverable.
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
import copy
import difflib
import json
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Tuple

FRAMEWORK_ROOT = Path(__file__).resolve().parent

# Adapter control files copied into <target>/.claude/. Everything else under
# adapters/<name>/ (README.md, usage_probe.py) is handled out of band.
ADAPTER_CONTROL = ("agents", "skills", "commands", "hooks", "scripts")
ADAPTER_SETTINGS = "settings.json"

# Project-owned overlay that deterministically customises the framework settings.
# When present, settings.json is regenerated from base+overlay on every run; the
# `.example` is scaffolded on a fresh install so the mechanism is discoverable.
SETTINGS_OVERLAY = "settings.overlay.json"
SETTINGS_OVERLAY_EXAMPLE = SETTINGS_OVERLAY + ".example"

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

[framework]
# Where the AIDE framework itself lives (owner/repo). The feedback loop's
# triage step hands `framework`-typed insights over as GitHub issues on this
# repo (via `gh`); empty disables the handover (entries stay pending in
# docs/aide/insights.md).
repo = ""
# Path to a local clone of the framework repo, used by the documented
# framework-update workflow. Declaring it exempts `git -C <this path>` from the
# hygiene guard's no-directory-prefix rule (the one legitimate use).
# local_path = "../aide-loop"

# [validation]
# Named environment profiles for stage-validation items — each value is a
# Python expression, true iff this machine provides the capability. Checked
# deterministically via `python .aide/scripts/aide.py env --profile <name>`.
# gpu = "__import__('torch').cuda.is_available()"
# dataset = "__import__('pathlib').Path('data/reference').is_dir()"

[aide]
# Framework version at install time (from aide-loop core/VERSION). Informational —
# the live installed engine version is the copied-in .aide/VERSION.
version = "{version}"
adapter = "{adapter}"
"""

GIT_MODES = ("auto-merge", "pr", "local")

# Inert overlay template dropped next to settings.json on a fresh install. It is a
# no-op if copied to settings.overlay.json unchanged (empty `add`), so activating
# it never changes behaviour until the project fills it in. `//` keys are comments
# and are dropped from the merged output.
SETTINGS_OVERLAY_EXAMPLE_BODY = """\
{
  "//": [
    "AIDE settings overlay — project-owned, like aide.toml. Copy this file to",
    "settings.overlay.json (drop the .example) to activate. While it exists,",
    ".claude/settings.json is REGENERATED on every install/--update as a",
    "deterministic deep-merge of the framework default and this overlay — so",
    "edit THIS file, never settings.json (your edits there are overwritten).",
    "",
    "Merge rules: objects deep-merge (overlay wins). For list values (the",
    "permission allow/ask/deny lists, hook groups) use the operator",
    "{ \\"add\\": [...], \\"remove\\": [...] } — additive by default, so a framework",
    "update that adds a new default still reaches you. A plain list replaces the",
    "framework value outright (escape hatch). Prefer adding to `deny` over",
    "removing from `allow` when tightening — deny is explicit and update-proof.",
    "Keys starting with // are comments and never appear in the output."
  ],
  "permissions": {
    "allow": { "add": [] }
  }
}
"""


class OverlayError(ValueError):
    """A settings overlay is malformed, or conflicts irreconcilably with the base.

    Raised before anything is written, so a bad overlay never yields a broken
    settings.json — fix the overlay and re-run (install is idempotent).
    """


# --------------------------------------------------------------------------- #
# settings overlay — deterministic base+overlay deep-merge
# --------------------------------------------------------------------------- #
_OPERATOR_KEYS = {"add", "remove"}


def _is_operator(value: object) -> bool:
    """True for a list-operator dict: non-empty, keys a subset of {add, remove}."""
    return (
        isinstance(value, dict)
        and len(value) > 0
        and set(value).issubset(_OPERATOR_KEYS)
    )


def _apply_list_operator(base_value, op: dict, path: str, warnings: List[str]) -> list:
    """Apply an {add, remove} operator to a base list, order-stable and deduped.

    ``base_value`` absent (None) starts from an empty list (so an operator can
    introduce a list the framework does not ship, e.g. ``deny``). A base value
    that exists but is not a list is an irreconcilable conflict.
    """
    if base_value is None:
        base_list: list = []
    elif isinstance(base_value, list):
        base_list = base_value
    else:
        raise OverlayError(
            f"{path}: add/remove operator applied where the framework value is "
            f"{type(base_value).__name__}, not a list"
        )
    remove = op.get("remove", [])
    add = op.get("add", [])
    if not isinstance(remove, list) or not isinstance(add, list):
        raise OverlayError(f"{path}: 'add'/'remove' must each be a list")

    result = [item for item in base_list if item not in remove]
    for item in remove:
        if item not in base_list:
            warnings.append(
                f"{path}: remove pins {item!r} but the framework default no longer "
                f"contains it - drop this stale entry"
            )
    for item in add:
        if item not in result:  # deep equality (== on JSON values); dedupe
            result.append(item)
    return result


def _merge(base, overlay, path: str, warnings: List[str]) -> dict:
    """Deep-merge ``overlay`` (a JSON object) onto ``base``, returning a new dict."""
    if not isinstance(overlay, dict):
        raise OverlayError(f"{path or '<root>'}: overlay must be a JSON object")

    result: dict = {}
    if isinstance(base, dict):
        for key, value in base.items():
            result[key] = copy.deepcopy(value)

    for key, ov in overlay.items():
        if key == "//" or key.startswith("//"):
            continue  # comment key — never merged into the output
        here = f"{path}.{key}" if path else key
        bv = result.get(key)  # None if absent
        if _is_operator(ov):
            result[key] = _apply_list_operator(bv, ov, here, warnings)
        elif isinstance(ov, dict):
            if bv is None or isinstance(bv, dict):
                result[key] = _merge(bv or {}, ov, here, warnings)
            else:
                raise OverlayError(
                    f"{here}: cannot merge an object over the framework's "
                    f"{type(bv).__name__} value"
                )
        elif isinstance(ov, list):
            if bv is not None and not isinstance(bv, list):
                warnings.append(
                    f"{here}: overlay list replaces a non-list framework value"
                )
            result[key] = copy.deepcopy(ov)  # plain list → explicit replace
        else:
            result[key] = ov  # scalar → replace
    return result


def merge_overlay(base: dict, overlay: dict) -> Tuple[dict, List[str]]:
    """Deterministically merge a project overlay onto the framework settings base.

    Pure: neither argument is mutated. Returns ``(merged, warnings)``; warnings are
    advisory (e.g. a stale ``remove`` pin) and never block. Raises ``OverlayError``
    on an irreconcilable conflict or malformed operator.
    """
    warnings: List[str] = []
    merged = _merge(base, overlay, "", warnings)
    return merged, warnings


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
    """Reconcile .claude/settings.json against the framework base.

    Three paths (see the module docstring):
      * overlay present -> regenerate settings.json = merge(base, overlay).
      * no overlay, existing settings.json -> non-clobber + .aide-merge diff.
      * fresh install -> copy the base and scaffold the .example overlay.
    """
    src = adapter_dir / ADAPTER_SETTINGS
    if not src.is_file():
        return
    dst = claude_dir / ADAPTER_SETTINGS
    overlay_path = claude_dir / SETTINGS_OVERLAY

    if overlay_path.is_file():
        _generate_settings_from_overlay(src, dst, overlay_path, log)
        return

    if not dst.exists():
        copy_file(src, dst, log)
        _scaffold_overlay_example(claude_dir, log)
        return

    existing = dst.read_text(encoding="utf-8").splitlines(keepends=True)
    incoming = src.read_text(encoding="utf-8").splitlines(keepends=True)
    if existing == incoming:
        log.append(f"  = {dst} (unchanged)")
        _scaffold_overlay_example(claude_dir, log)
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
        "# then delete this file. To make future updates automatic, move your\n"
        f"# project-specific changes into .claude/{SETTINGS_OVERLAY} (see the\n"
        f"# {SETTINGS_OVERLAY_EXAMPLE} scaffolded alongside settings.json) — while\n"
        "# that overlay exists, settings.json is regenerated deterministically and\n"
        "# no .aide-merge is produced.\n\n"
    )
    merge_path.write_text(header + diff, encoding="utf-8")
    log.append(f"  ! {dst} kept (existing) — diff written to {merge_path}")
    _scaffold_overlay_example(claude_dir, log)


def _generate_settings_from_overlay(src: Path, dst: Path, overlay_path: Path,
                                    log: List[str]) -> None:
    """Write dst = deterministic merge of the framework base (src) and the project
    overlay. Raises OverlayError (before any write) on a malformed input."""
    try:
        base = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # a framework bug, not the project's
        raise OverlayError(f"framework {src} is not valid JSON: {exc}") from exc
    try:
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OverlayError(f"{overlay_path} is not valid JSON: {exc}") from exc

    merged, warnings = merge_overlay(base, overlay)
    text = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
    json.loads(text)  # never emit a settings.json that will not parse

    existed = dst.exists()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    log.append(f"  {'~' if existed else '+'} {dst} (generated from {overlay_path.name})")
    for warning in warnings:
        log.append(f"  ! overlay: {warning}")


def _scaffold_overlay_example(claude_dir: Path, log: List[str]) -> None:
    """Drop the inert overlay example next to settings.json (never clobbering)."""
    path = claude_dir / SETTINGS_OVERLAY_EXAMPLE
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SETTINGS_OVERLAY_EXAMPLE_BODY, encoding="utf-8")
    log.append(f"  + {path}")


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
    try:
        return run(build_parser().parse_args(argv))
    except OverlayError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("  fix .claude/settings.overlay.json and re-run (install is idempotent).",
              file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
