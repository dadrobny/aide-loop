# Review instructions

Review contract for pull requests in this repo. Copilot code review and
Claude Code Review read this file directly; Codex applies it via the Code
Review Rules section of `AGENTS.md`; a local Claude `/code-review` subagent
does **not** read it on its own, so its prompt must hand it this file.
Reviewer routing — who reviews, and in what order — lives in `CLAUDE.md`
under Merge policy.

## What Important means here

Reserve Important for findings where a consumer install would behave
wrongly: a loop verb regressing, an unattended run stalling, a contract
delivered on one side of a coupling but not the other, or CI passing while
the shipped artifact is broken. Style, naming, and refactoring suggestions
are Nit at most.

## Do not report

- Paths like `.aide/…`, `.claude/…`, or `python .aide/scripts/aide.py`
  inside `core/` or `adapters/` as wrong or inconsistent with this repo's
  layout. They are **consumer paths describing the installed result, and
  they are correct** — this is the repo's number-one review false positive.
- Anything the test suite already enforces mechanically: the version-bump
  gate, pin presence, reach declarations, CI shard coverage. CI runs the
  same suite; flag only what it cannot see, such as a wrong SemVer *level*.
- Formatting and style. There is deliberately no linter or formatter.
- Suggestions to add dependencies, a venv, or tooling — the suite is
  stdlib + pytest only, by design.
- Status sections, checklists, or "current focus" headings for any document
  — status lives only in the GitHub Project, never in the repo.

## Always check

- The change does what its issue/PR description says, and nothing beyond
  it. Hunt specifically for regressions the fix itself introduces.
- Coupled edits land in the same PR:
  - section wording under `core/conventions/` ↔ the `<!-- pins: -->` quotes
    in delivered adapter files (both directions fail the pin test);
  - a rule's `paths:` globs or an agent spec's `skills:` list ↔ that file's
    `<!-- reach: -->` declaration;
  - conventions §3 ↔ `adapters/claude/hooks/command_hygiene_guard.py` ↔ the
    allow-list in `adapters/claude/settings.json`;
  - any change under `core/` or `adapters/` (minus test/spec paths) ↔ a
    `core/VERSION` bump plus a `CHANGELOG.md` entry, at the right SemVer
    level.
- Nothing under `core/` names Claude, a Claude model, or a `.claude/`
  primitive — the engine is provider-agnostic by contract.
- Path and subprocess work holds on Windows: CI runs the whole suite on a
  windows leg, and POSIX-only assumptions fail there and not locally.
- Templates use `{{slot}}` only for a literal value to substitute;
  authoring guidance is written as `_italic lines_`, never as a slot.

## Verification bar

A behavior claim needs a `file:line` citation in the source, not an
inference from naming. A defect report needs a concrete scenario: the
inputs or state, then the wrong outcome. Report at most five nits; mention
the rest as a count in the summary.
