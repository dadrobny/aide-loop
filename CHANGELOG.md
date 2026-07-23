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

## [1.3.2] — 2026-07-23

### Fixed

- **`aide check`'s stray-icon lint flagged the icon vocabulary anywhere it
  appeared in prose, drowning real warnings in noise (issue #13).**
  `_stray_icons_in_line` treated any line that wasn't a table row, a queue
  status line, or a leading-icon bullet as fair game to flag *every* icon on
  it — so an ordinary sentence, or a bullet whose text merely mentioned an
  icon mid-sentence, tripped the same warning as a genuine misplaced status
  icon. conventions.md §1 is explicit that only three positions are
  structural (a deliverable bullet's leading icon, a table row's last cell, a
  stage header's trailing icon); everywhere else the icon vocabulary is prose
  by design. The lint now only ever fires on a heading whose status-shaped
  icon sits somewhere other than the trailing position — the one remaining
  shape where a reader could plausibly misread it as the header's status.

## [1.3.1] — 2026-07-23

### Fixed

- **`*(Items A, B)*` credited only the first item, which could strand
  `aide claim` on a finished queue.** `_parse_item_status` matched
  `[Ii]tem[s]?\s+0*(\d+)` — the word "Item(s)" followed by *one* number — so in
  the multi-item reference the create-queue step explicitly tells authors to
  write (`… *(Items 006, NNN)*`, for a deliverable delivered by several items)
  every number after the first was invisible.

  Orphaned items read as `planned` forever even while sitting on a ✅
  deliverable bullet. Because a queue is open while any of its items is
  planned/in-progress, and the *live* queue is the lowest-numbered open one,
  those phantom-open items pinned the live queue to a long-finished batch;
  `aide claim`, scoped to the live queue, then reported `none left` and never
  looked at the current one. A consumer hit exactly this: seven items across
  four queues, all on green bullets, wedged the loop so that a newly created
  queue would have been invisible to it.

  The root cause was two different notions of "item NNN is referenced" in one
  module: the status parse above, and `_item_ref_re` (used by `aide progress
  set`), which matched any number literally present inside the reference. So
  `progress set` acted happily on an item `check`/`status`/`claim` believed
  untracked.

  Both now go through a single `_referenced_item_numbers`, and the accepted
  reference forms are written down in `conventions.md` §1: `*(Item 006)*`,
  `*(Items 006, 044)*`, `*(Items 089/090)*`, and inclusive ranges
  `*(Items 071–075)*` (hyphen or en-dash). **Ranges are now expanded**, so an
  item named only inside one is tracked and `aide progress set` can flip its
  bullet — previously `071–075` credited `071` alone and silently orphaned the
  three interior items. A range wider than 50 is treated as a typo and
  contributes only its endpoints.

  **Consumer action:** none. Projects whose multi-item references were being
  half-read will see the affected queues close and `aide claim` resume on the
  correct queue after updating; no document edit is required.

## [1.3.0] — 2026-07-23

### Changed

- **Living documents no longer end with a "Next: run `/aide-…`" pointer.** Every
  generated document carried one, and each was stale shortly after it was
  written: `progress.md` — edited on every merged item — still said "run
  `/aide-create-queue` to generate the first batch" at queue 7, and a reader had
  no way to tell a stale pointer from a current one. A step-scoped instruction
  stored in a project-lifetime document is guaranteed drift.

  The hand-off is now spoken rather than stored: `vision.md`, `roadmap.md`,
  `progress.md`, `queue-NNN.md`, and `items/NNN-*.md` end at their last content
  section, and the skill that writes the file names the next step in its closing
  message to the user (and, for a queue, in the PR body). The skills' `## Next
  Step` sections are renamed `## Hand-off`.

  The durable half of that information moves into each template's **header
  blockquote** — the document's step in the loop, what it derives from, and what
  derives from it. `vision.md` names itself the root of roadmap/progress/queues/
  items; `roadmap.md` names progress as its mirror; `progress.md` states that
  queue state derives from it and item specs deliberately carry no status;
  `queue-NNN.md` points at `../items/` and back at `progress.md`. Described in
  `conventions.md` §1.

  **No consumer action required** — nothing parses these lines and `aide check`
  does not flag them, so existing documents stay valid. Delete the trailing
  `Next:` line the next time you touch one.

### Added

- **`CLAUDE.md` for this repo.** aide-loop is the framework, not a consumer of
  it, and an agent arriving here would otherwise look for `docs/aide/` and an
  `aide.toml` that do not exist. Covers the source-vs-installed path trap (the
  `.aide/…` references under `core/` and `adapters/` are consumer paths and must
  not be "fixed"), the enforced `core/VERSION` bump rule, the stdlib-only test
  setup, and how to try a change in a real consumer from the local working tree.

## [1.2.2] — 2026-07-23

### Fixed

- **A malformed `aide.toml` behaved differently on different Pythons, and one of
  them was silent.** On 3.11 `tomllib` raised an uncaught `TOMLDecodeError` —
  `load_config` caught only `ModuleNotFoundError` — so the user got a traceback
  through `tomllib` internals that never named the offending file. On 3.9 the
  fallback parser *accepted* the same file: `name = "unterminated` yielded the
  truncated text as the value, so a typo became a plausible wrong answer.

  `load_config` now raises `ConfigError` on either path, with one message naming
  the path and the line. `main` catches it and prints `error: …` with exit 2, so
  no subcommand shows a traceback for a user-fixable file. The fallback parser
  rejects an unterminated quoted string rather than misreading it, which is what
  makes the two paths agree.

  A *missing* `aide.toml` is still fine — that means "unconfigured", and defaults
  are the right answer. A malformed one is not: it states facts (`source_dir`,
  git mode, test command) that the framework acts on, so continuing on defaults
  would scope the builder at the wrong directory while reporting success.

## [1.2.1] — 2026-07-22

### Fixed

- **A byte-order mark in a project-owned file silently changed how it was read.**
  Windows editors (Notepad, PowerShell `Out-File`, several IDEs' "Save as UTF-8")
  prepend U+FEFF; read as plain UTF-8 that codepoint survives into the text and
  breaks first-line parsing. Every read of a file that lives in a consumer repo —
  `aide.toml`, the `docs/aide/` living documents, `loop.local.toml`,
  `.claude/settings.json`, the settings overlay, `.gitignore`, `.aide/VERSION` —
  now uses `utf-8-sig`, which strips a BOM when present and is byte-identical to
  `utf-8` when absent.

  The worst case was silent rather than loud. `aide.toml` read with a BOM lost
  **only its first table** — the fallback TOML parser's `^\[table\]$` match fails
  on the BOM'd line while every later table parses normally — so `[project]`
  vanished and `source_dir` reverted to its default while `[git]` was still
  honoured. A half-correct config, no error, every command reporting success.
  On Python 3.11 the same file raised an uncaught `TOMLDecodeError` instead.

  Also fixed: a BOM'd `settings.json` crashed the permission reviewer's
  `load_rules`, made `install.py` see a spurious difference from the framework
  base (emitting a pointless `.aide-merge` on every run), and could cause the
  `.gitignore` block to be appended twice.

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
