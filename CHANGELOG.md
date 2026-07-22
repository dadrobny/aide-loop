# Changelog

All notable changes to the AIDE framework. The version here is `core/VERSION`,
which the installer copies into a consumer as `.aide/VERSION` — that file is what
a consumer compares against to learn it is outdated
(`python install.py --into <repo> --check`).

**Bump policy** — see [README](README.md#versioning). Any commit touching `core/`
or `adapters/` bumps `core/VERSION`, because that is exactly what `--update`
copies into a consumer; docs-only and repo-test-only commits do not. The rule is
enforced by `tests/test_repo_versioning.py`, not by memory.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [SemVer](https://semver.org/spec/v2.0.0.html), where the "API" is what
a consumer installs — the document formats, the `aide` CLI surface, `aide.toml`
keys, and the adapter's agents/skills/commands.

## [Unreleased]

## [1.2.0] — 2026-07-22

Seventeen consumer-visible commits had accumulated under `1.1.0` before this
release; the version number had stopped moving while the engine changed
substantially. This release ships them and adds the policy + tooling that stop it
recurring.

### Added

- **`aide sync` / `aide gc` / `aide status`** — session preflight, claim-branch
  clean-up, and a one-call roadmap-state report. Conventions now state that the
  improvised `git fetch`/`status`/`switch` equivalents are wrong when a verb
  covers it.
- **Insight inbox** (`docs/aide/insights.md`, `core/templates/insights.md`) — the
  compound-engineering capture point. Any role appends one typed line
  (`knowledge`/`defect`/`gap`/`automation`/`framework`) and returns to its task;
  `/aide-feedback-loop` triages at the queue boundary. `aide check` shape-checks
  entries as a warning, never an error, so capture stays cheap.
- **Planned meaning-level validation** — `[validation]` environment profiles in
  `aide.toml`, evaluated by `aide env --profile <name>`, plus an optional
  `## Validation` section in item specs the validator must execute. A gated path
  that cannot run records `❓ Unverified` instead of passing silently.
- **Deterministic settings reconciliation** — a project-owned
  `.claude/settings.overlay.json`. While present, `settings.json` is regenerated
  on every install/update as a base+overlay deep-merge, so framework changes flow
  through and project additions reapply without hand-merging `.aide-merge`. The
  installer also derives a ready-to-adopt overlay for existing projects and
  templates the write-scope globs from `aide.toml` `source_dir`/`tests_dir`.
- **`loop.claim_scope`** (`live-queue` | `all-open`) — opt into claiming across
  every open queue rather than only the live one.
- **`[framework] repo`** — where `framework`-typed insights are handed over.
- **`install.py --check`** — compare a consumer's installed `.aide/VERSION`
  against `core/VERSION` and report whether it is current, behind, or ahead.
  Exits non-zero when behind, so a consumer can gate on it.

### Changed

- **Queue state is derived, not declared.** A queue is open iff any of its items
  is 📋/🚧 in `progress.md`; the `> **Status:**` line is now optional decoration,
  and `aide check` warns only when a declared status contradicts the derived one.
- **Status icons are read only at structural positions** — a table row's status
  cell, a stage header's trailing `— <icon>`, a deliverable bullet's leading
  icon. An icon in prose is plain text, so authors need not avoid the vocabulary
  in free text.
- The unattended launch contract and execution surfaces are pinned; the usage
  probe is now a documented core/adapter seam (`[loop] usage_probe`).

### Fixed

- **`/aide-review-permissions` promoted rules into a generated file.** With an
  overlay adopted, `.claude/settings.json` is regenerated on every update, so a
  rule written there was silently discarded. The command and
  `review_permissions.py` now detect the overlay and name
  `permissions.allow.add` as the destination, falling back to `settings.json`
  only when no overlay exists.
- `install.py` writes UTF-8 stdout, so installing survives a non-UTF-8 console.
- The Claude hook interpreter is probed functionally rather than by PATH
  presence, fixing the Windows Store `python.exe` alias stub.
- `settings.json` works across Windows and Linux.
- `aide progress` no longer silently no-ops when no deliverable references the
  item.

## [1.1.0] — 2026-07-14

### Added

- Environment-gated capability tracking: a capability behind an optional package
  or external tool declares itself, and CI can verify it actually ran rather than
  skipped.

## [1.0.0] — 2026-07-07

Initial standalone release: the framework extracted from its origin project into
a provider-agnostic engine (`core/`) plus swappable adapters (`adapters/`), with
`install.py` materialising them into a consumer as `.aide/` and `.claude/`.
