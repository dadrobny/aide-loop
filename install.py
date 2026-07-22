#!/usr/bin/env python3
"""install.py — cross-OS installer for the AIDE framework.

Materialises the three-layer framework (see docs/concepts.md "The three layers")
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
             * fresh install -> the effective base is written and an inert
               settings.overlay.json.example is scaffolded so the overlay
               mechanism is discoverable.
           The "effective base" is the framework settings.json with its write-scope
           globs templated from the project's aide.toml source_dir/tests_dir (so a
           project whose code lives outside src/ tests/ needs no manual override);
           with the defaults it is byte-identical to the committed file.
  3. scaffold <target>/aide.toml from a template (prompts for source_dir, tests_dir,
     test_command, git.mode; skipped if aide.toml already exists) — done BEFORE (2)
     so the settings write-scope can read it.
  4. copy  adapters/<adapter>/usage_probe.py  -> <target>/.aide/loop/   (plan §4.4 seam)
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
tests_dir = "{tests_dir}"
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


def parse_version(text: str) -> Tuple[int, ...]:
    """``"1.2.0"`` -> ``(1, 2, 0)``, for ordering. Non-numeric parts sort as 0.

    Tolerant on purpose: a consumer's ``.aide/VERSION`` is a file on someone
    else's disk, and a malformed one should still yield a usable comparison
    rather than crash the check.
    """
    out: List[int] = []
    for part in (text or "").strip().lstrip("﻿").split("."):
        # Leading digits only: "0-rc1" is 0, not 1. Concatenating every digit in
        # the part would let a pre-release suffix inflate the number.
        digits = ""
        for ch in part.strip():
            if not ch.isdigit():
                break
            digits += ch
        out.append(int(digits) if digits else 0)
    return tuple(out) or (0,)


def compare_versions(installed: str, available: str) -> str:
    """``"current"`` / ``"behind"`` / ``"ahead"`` for installed vs available."""
    lhs, rhs = parse_version(installed), parse_version(available)
    width = max(len(lhs), len(rhs))
    lhs += (0,) * (width - len(lhs))
    rhs += (0,) * (width - len(rhs))
    if lhs == rhs:
        return "current"
    return "behind" if lhs < rhs else "ahead"


def report_version(available: str, installed_path: Path, target: Path) -> int:
    """``--check``: compare the target's installed VERSION against this framework.

    Writes nothing. Exit 0 when current or ahead, 1 when behind (so a consumer can
    gate on it), 2 when the target has no install to compare.
    """
    if not installed_path.is_file():
        print(f"aide {target}: no install found ({installed_path} missing) — "
              f"run install.py --into {target}", file=sys.stderr)
        return 2

    # utf-8-sig: this file lives on someone else's disk and may have picked up a
    # BOM from an editor; a stray byte must not turn into part of the version.
    installed = installed_path.read_text(encoding="utf-8-sig").strip()
    state = compare_versions(installed, available)
    if state == "current":
        print(f"aide {target}: v{installed} — up to date")
        return 0
    if state == "ahead":
        print(f"aide {target}: v{installed} is AHEAD of this framework (v{available}) — "
              f"this checkout is older than the consumer's install")
        return 0
    print(f"aide {target}: v{installed} is BEHIND v{available} — "
          f"run install.py --into {target} --update (see CHANGELOG.md)")
    return 1


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


_UNCHANGED = object()
_MISSING = object()


def _derive(base, existing, path: str, warnings: List[str]):
    """Overlay fragment that turns ``base`` into ``existing`` at this node, or
    ``_UNCHANGED``. Lists become additive {add, remove} operators (membership, not
    order — fine for permission sets); scalars/new keys become literal values."""
    if base is not _MISSING and base == existing:
        return _UNCHANGED
    if isinstance(base, dict) and isinstance(existing, dict):
        fragment: dict = {}
        for key, value in existing.items():
            here = f"{path}.{key}" if path else key
            sub = _derive(base.get(key, _MISSING), value, here, warnings)
            if sub is not _UNCHANGED:
                fragment[key] = sub
        for key in base:
            if key not in existing:
                where = f"{path}.{key}" if path else key
                warnings.append(
                    f"{where}: in the framework base but not your settings — an "
                    f"overlay cannot express deleting a key, so it is left in place"
                )
        return fragment if fragment else _UNCHANGED
    if isinstance(base, list) and isinstance(existing, list):
        add = [x for x in existing if x not in base]
        remove = [x for x in base if x not in existing]
        operator: dict = {}
        if add:
            operator["add"] = add
        if remove:
            operator["remove"] = remove
        return operator or _UNCHANGED
    return copy.deepcopy(existing)  # scalar/type change, or a key absent from base


def derive_overlay(base: dict, existing: dict) -> Tuple[dict, List[str]]:
    """Inverse of ``merge_overlay``: the minimal overlay that reproduces ``existing``
    on top of ``base``. ``merge_overlay(base, derive_overlay(base, existing)[0])``
    reproduces ``existing`` (list membership, not order). Warns on keys the project
    dropped from the base, which an additive overlay cannot express.
    """
    warnings: List[str] = []
    fragment = _derive(base, existing, "", warnings)
    return (fragment if isinstance(fragment, dict) else {}), warnings


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
def install_settings(adapter_dir: Path, claude_dir: Path, target: Path, log: List[str],
                     source_dir: str = "src", tests_dir: str = "tests") -> None:
    """Reconcile .claude/settings.json against the framework base.

    Three paths (see the module docstring):
      * overlay present -> regenerate settings.json = merge(effective base, overlay).
      * no overlay, existing settings.json -> non-clobber + .aide-merge diff.
      * fresh install -> write the effective base and scaffold the .example overlay.

    The "effective base" is the framework settings.json with its write-scope globs
    templated from the project's ``source_dir``/``tests_dir`` (defaults src/tests, in
    which case it is the base verbatim — byte-identical to the committed file).
    """
    src = adapter_dir / ADAPTER_SETTINGS
    if not src.is_file():
        return
    dst = claude_dir / ADAPTER_SETTINGS
    overlay_path = claude_dir / SETTINGS_OVERLAY
    base, base_text = _effective_base(src, source_dir, tests_dir)

    if overlay_path.is_file():
        _generate_settings_from_overlay(base, overlay_path, dst, log)
        return

    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(base_text, encoding="utf-8")
        scope = "" if base_text == src.read_text(encoding="utf-8") else \
            f" (write-scope templated to {source_dir}/, {tests_dir}/)"
        log.append(f"  + {dst}{scope}")
        _scaffold_overlay_example(claude_dir, log)
        return

    existing_text = dst.read_text(encoding="utf-8")
    if existing_text.splitlines(keepends=True) == base_text.splitlines(keepends=True):
        log.append(f"  = {dst} (unchanged)")
        _scaffold_overlay_example(claude_dir, log)
        return

    _emit_aide_merge(base, base_text, existing_text, dst, target, log)
    _scaffold_overlay_example(claude_dir, log)


# Write-scope permission entries whose directory is templated from aide.toml, so a
# project whose code/tests live outside src/ tests/ needs no manual glob override.
# Maps the framework-default entry -> (config key, format string for the new entry).
_SCOPE_TEMPLATED = {
    "Edit(src/**)": ("source_dir", "Edit({}/**)"),
    "Write(src/**)": ("source_dir", "Write({}/**)"),
    "Edit(tests/**)": ("tests_dir", "Edit({}/**)"),
    "Write(tests/**)": ("tests_dir", "Write({}/**)"),
}


def _apply_scope_template(base: dict, source_dir: str, tests_dir: str) -> dict:
    """Rewrite the default src/ tests/ write-scope globs to the project's dirs.

    Returns ``base`` unchanged (same object) when both are the defaults, so the
    common install stays byte-identical to the committed settings.json.
    """
    if source_dir == "src" and tests_dir == "tests":
        return base
    dirs = {"source_dir": source_dir, "tests_dir": tests_dir}
    result = copy.deepcopy(base)
    perms = result.get("permissions", {})
    for list_key in ("allow", "ask", "deny"):
        entries = perms.get(list_key)
        if not isinstance(entries, list):
            continue
        perms[list_key] = [
            _SCOPE_TEMPLATED[e][1].format(dirs[_SCOPE_TEMPLATED[e][0]])
            if e in _SCOPE_TEMPLATED else e
            for e in entries
        ]
    return result


def _project_scope(target: Path) -> Tuple[str, str]:
    """(source_dir, tests_dir) for the target repo, read via the engine's OWN config
    loader so install.py and the engine interpret aide.toml identically (same TOML
    subset, same defaults). Falls back to the framework defaults if unavailable."""
    try:
        sys.path.insert(0, str(FRAMEWORK_ROOT / "core" / "scripts"))
        from aide import load_config  # the engine's config reader
        project = load_config(target).get("project", {})
        return str(project.get("source_dir", "src")), str(project.get("tests_dir", "tests"))
    except Exception:  # engine import/parse failure must never break the install
        return "src", "tests"


def _effective_base(src: Path, source_dir: str, tests_dir: str) -> Tuple[dict, str]:
    """Load the framework settings.json and template its write-scope globs.

    Returns ``(dict, serialised text)``. The text is byte-identical to the committed
    file when no templating applies, else a re-serialised (2-space) render.
    """
    try:
        base = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # a framework bug, not the project's
        raise OverlayError(f"framework {src} is not valid JSON: {exc}") from exc
    templated = _apply_scope_template(base, source_dir, tests_dir)
    if templated is base:
        return base, src.read_text(encoding="utf-8")
    return templated, json.dumps(templated, indent=2, ensure_ascii=False) + "\n"


def _generate_settings_from_overlay(base: dict, overlay_path: Path, dst: Path,
                                    log: List[str]) -> None:
    """Write dst = deterministic merge of the (effective) framework base and the
    project overlay. Raises OverlayError (before any write) on a malformed input."""
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


def _emit_aide_merge(base: dict, base_text: str, existing_text: str, dst: Path,
                     target: Path, log: List[str]) -> None:
    """Legacy non-clobber path: keep the existing settings.json, and write to
    .aide-merge both a diff AND a ready-to-adopt overlay derived from the existing
    file — so the human moves the difference INTO the overlay rather than hand-merging
    the diff forever."""
    diff = "".join(
        difflib.unified_diff(
            existing_text.splitlines(keepends=True),
            base_text.splitlines(keepends=True),
            fromfile="a/.claude/settings.json",
            tofile="b/.claude/settings.json (framework)",
        )
    )
    header = (
        "# AIDE install: .claude/settings.json already exists and was NOT "
        "overwritten.\n"
        f"# Recommended: save the '{SETTINGS_OVERLAY}' block at the bottom of this\n"
        f"# file as .claude/{SETTINGS_OVERLAY}. It reproduces your CURRENT settings on\n"
        "# top of the framework base, so once adopted, settings.json is regenerated\n"
        "# deterministically on every update (project changes reapply, framework\n"
        "# changes flow through) and no .aide-merge is produced. Then delete this file.\n"
        "# The diff below (your version -> framework's) is for reference.\n\n"
    )
    body = header + diff
    suggestion = _suggested_overlay_block(base, existing_text)
    if suggestion:
        body += suggestion
    merge_path = target / ".aide-merge"
    merge_path.write_text(body, encoding="utf-8")
    tail = " + suggested overlay" if suggestion else ""
    log.append(f"  ! {dst} kept (existing) — diff{tail} written to {merge_path}")


def _suggested_overlay_block(base: dict, existing_text: str) -> str:
    """A commented, ready-to-adopt overlay reproducing the existing settings over the
    base. Empty string if the existing file cannot be parsed/derived (diff still helps)."""
    try:
        existing = json.loads(existing_text)
        suggested, warnings = derive_overlay(base, existing)
    except (json.JSONDecodeError, OverlayError):
        return ""
    lines = [
        "",
        "",
        f"# ==== suggested .claude/{SETTINGS_OVERLAY} "
        "(reproduces your settings over the framework base) ====",
    ]
    lines += [f"# note: {w}" for w in warnings]
    lines.append(json.dumps(suggested, indent=2, ensure_ascii=False))
    lines.append("")
    return "\n".join(lines)


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
    tests_dir = args.tests_dir or prompt("tests_dir", "tests", interactive)
    test_command = args.test_command or prompt("test_command", "python -m pytest", interactive)
    git_mode = args.git_mode or prompt("git.mode", "auto-merge", interactive, GIT_MODES)

    path.write_text(
        AIDE_TOML_TEMPLATE.format(
            name=name, source_dir=source_dir, tests_dir=tests_dir,
            test_command=test_command, git_mode=git_mode, version=version,
            adapter=adapter,
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

    if args.check:
        return report_version(version, aide_dir / "VERSION", target)

    mode = "update" if args.update else "install"
    print(f"AIDE {mode}: {args.adapter} v{version} -> {target}")

    # 1. engine -> .aide/
    copy_tree(core_dir, aide_dir, log)

    # 2. adapter control files -> .claude/
    for name in ADAPTER_CONTROL:
        src = adapter_dir / name
        if src.is_dir():
            copy_tree(src, claude_dir / name, log)

    # 3. project-owned aide.toml scaffold — fresh install only, and BEFORE settings
    #    so the write-scope globs can be templated from its source_dir/tests_dir.
    if not args.update:
        scaffold_aide_toml(target, args.adapter, version, args, log)
    else:
        log.append("  = aide.toml, docs/aide/ (left untouched — project-owned)")

    # 4. settings.json — reconciled against the effective (scope-templated) base.
    source_dir, tests_dir = _project_scope(target)
    install_settings(adapter_dir, claude_dir, target, log, source_dir, tests_dir)

    # 5. usage probe -> .aide/loop/  (the plan §4.4 seam)
    probe = adapter_dir / "usage_probe.py"
    if probe.is_file():
        copy_file(probe, aide_dir / "loop" / "usage_probe.py", log)

    # 6. .gitignore block — fresh install only
    if not args.update:
        append_gitignore(target, log)

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
    p.add_argument("--check", action="store_true",
                   help="report whether the target's installed .aide/VERSION is current, "
                        "behind, or ahead of this framework; writes nothing, exits 1 if behind")
    p.add_argument("--yes", action="store_true", help="accept defaults; never prompt")
    p.add_argument("--name", default=None, help="project name for aide.toml (default: target dir name)")
    p.add_argument("--source-dir", dest="source_dir", default=None, help="[project] source_dir")
    p.add_argument("--tests-dir", dest="tests_dir", default=None, help="[project] tests_dir")
    p.add_argument("--test-command", dest="test_command", default=None, help="[python] test_command")
    p.add_argument("--git-mode", dest="git_mode", choices=GIT_MODES, default=None, help="[git] mode")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    # Windows consoles often default to a non-UTF-8 codepage (cp1252), where printing
    # the em-dashes/icons in the install log raises UnicodeEncodeError and kills the
    # install instead of reporting. Reconfigure once here so no caller needs the
    # PYTHONIOENCODING env-var dance (mirrors aide.py main()).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    try:
        return run(build_parser().parse_args(argv))
    except OverlayError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("  fix .claude/settings.overlay.json and re-run (install is idempotent).",
              file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
