# AGENTS.md — aide-loop

This repo is the **AIDE framework itself** — the engine (`core/`), the
Claude adapter (`adapters/claude/`), and the installer (`install.py`) that
copy into consumer repos as `.aide/` and `.claude/`. It is not a project
that uses AIDE. Full contributor context — layout, invariants, versioning,
tests — is in `CLAUDE.md` at the repo root; despite the name, it applies to
any agent working here, not only Claude.

The single most important thing to know: control files under `core/` and
`adapters/` reference `.aide/…` and `.claude/…` paths. Those describe the
*installed* result inside a consumer repo and are correct — do not "fix"
them to this repo's source layout.

## Code Review Rules

Apply `REVIEW.md` at the repo root — it defines severity, what to check,
and what not to report. Non-negotiable highlights:

- Never flag `.aide/…` or `.claude/…` paths inside `core/` or `adapters/`
  as broken; they are consumer paths, correct by design.
- Check that coupled edits land together: conventions wording ↔ adapter
  `<!-- pins: -->` quotes; rule globs / agent `skills:` ↔ `<!-- reach: -->`
  declarations; conventions §3 ↔ hygiene hook ↔ settings allow-list; any
  consumer-visible change ↔ `core/VERSION` bump + `CHANGELOG.md` entry.
- No style, formatting, or dependency suggestions — stdlib + pytest only,
  no linter, by design.
