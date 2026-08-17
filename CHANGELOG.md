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

## [1.5.0] — 2026-08-17

Five correctness defects found running a consumer's queues 013–016 (issue #22).

### Added

- **`aide progress accept <stage> (--criterion N | --all) [--evidence "…"]`** —
  the explicit way to tick an acceptance checkbox, replacing the auto-tick
  removed below. An already-ticked box is reported and left alone rather than
  counted as newly accepted; an unknown stage or an out-of-range index is a
  loud error, never a silent no-op. `--evidence` appends an annotation beside
  the ticked box recording what was checked.

### Changed

- **`aide progress set` no longer ticks acceptance checkboxes.** It recomputed
  every stage's rollup on every call and force-ticked every `- [ ]` in any
  stage that derived complete — so a box deliberately left unticked to record
  a criterion that shipped *unmet* was silently flipped back to ticked by the
  next status change for **any** item in **any** stage, converting a recorded
  shortfall into a claim nobody had made. A consumer hit this on two separate
  stages and could not keep either honest, since `.aide/**` is generated and a
  hand-edit is overwritten on the next update.

  A derived tick is not an attestation, and the tick had no readers to serve:
  `stage_deliverable_statuses` skips checkbox lines, the rollup never sees
  them, and no `aide check` rule gates a ✅ stage on them. Acceptance is now
  attested by whoever performed the check, via `aide progress accept`;
  conventions.md §1 states that a stage may be ✅ with an unticked box, and the
  validator's PASS sequence ticks only criteria it actually verified.

  **Consumer action:** none. Already-ticked boxes stay ticked. A stage closed
  in future will show its acceptance boxes as its author left them, which for
  most projects means running `aide progress accept` once per verified
  criterion where `progress set` previously ticked them wholesale.

### Fixed

- **A queue branch was read as an item claim, and `gc` could delete it.**
  Branch-to-item resolution fell back to an unanchored digit search, so
  `aide/queue-016` — the branch name `/aide-create-queue`'s hand-off and
  `/aide-run-roadmap` both tell authors to create — resolved to *item 016*, an
  unrelated and usually long-finished work item (`aide/specs-queue-015`
  likewise). Queue numbers and item numbers share one namespace with no
  syntactic marker between them.

  The consequence went well past the spurious `aide check` warning that
  surfaced it: `gc` targets any branch whose item is ✅ **independently of
  `--merged`**, then deletes it with `git branch -D` plus a remote delete. So
  `aide gc --yes` would destroy an in-flight queue branch, local and remote,
  along with the queue file and item specs living only on it — for any project
  whose item NNN had finished, which after a few queues is all of them.

  Resolution is now a single anchored helper matching the branch shape
  conventions.md §4 already documents (`<branch_prefix>NNN-short-name`), shared
  by `check`, `merge`, `sync --item`, `status` and `gc` instead of three
  divergent copies. Queue and specs-queue branches are recognised positively
  and reported as what they are; a prefixed branch matching neither shape is
  reported as unrecognised rather than silently skipped, so anchoring cannot
  hide a real stale claim.

- **`aide check` rendered OS-native path separators in its output.** Both
  warning locations were built by f-stringing a `Path`, which calls `str()`, so
  the identical document reported as `queue/queue-002.md:80` on Linux and
  `queue\queue-002.md:80` on Windows — and only locations with a subdirectory
  component diverged, making it read as a content problem rather than a
  platform one. Now `.as_posix()`. Any consumer parsing `aide check` output
  rather than calling `run_checks` was inheriting this.

- **The unfilled-slot rule rejected GitHub Actions expressions quoted in
  prose.** `template_residue_errors` scans for a literal `{{` and *errors*, so
  any living document discussing a workflow — an item spec explaining what a CI
  step runs, an insight recording a workflow's arguments — turned `aide check`
  red on prose that was correct as written, and the only remedy was to stop
  naming the real syntax. The pattern now exempts a `$` immediately preceding
  the braces, and nothing else: AIDE slots are never `$`-prefixed. Suppressing
  matches inside backtick code spans would have been wrong, since the item
  template's own `Suggested branch` line carries a genuine slot inside one.

- **The insights inbox forbade the edit its own triage procedure requires.**
  `core/templates/insights.md` closed with "Append-only: never rewrite,
  reorder, or delete existing lines" while instructing the triager, six lines
  above, to tick the entry's checkbox in place and append a "→ where it landed"
  pointer — so every triage pass had to violate the stated rule to follow the
  stated procedure. `conventions.md` §1 carried the same contradiction
  independently. Both now permit exactly those two triage edits and prohibit
  any other rewrite, reorder or deletion.

## [1.4.2] — 2026-07-26

### Fixed

- **`_item_dependencies` only read the first number in a multi-item
  Dependencies reference, and had no directionality check.** `aide claim`'s
  blocking-dependency scan used its own naive `\bItem[s]?\s+0*(\d+)` regex
  instead of the shared, already-fixed `_referenced_item_numbers` (issue
  #15's fix, 1.3.1) — so "Items 093, 094, 095" registered only 093 as a
  blocker, and a forward-looking aside naming a *later* item ("**Downstream:**
  item 099 depends on this item's CI job") was misread as a backward
  dependency on that later item. Concretely: a stage-closing item could be
  offered by `aide claim` before its actual prerequisites existed, while an
  unrelated item was skipped because it "depended on" a downstream item that
  hadn't even been claimed yet.

  `_item_dependencies` now reuses `_referenced_item_numbers` (same
  case-insensitive, list/range-aware extraction every other item-reference
  call site uses) and stops scanning at a literal `**Downstream` marker,
  which is now a documented convention (item template + conventions.md §1)
  for noting a forward reference without it being read as a blocker.

- **The command-hygiene guard's `[framework] local_path` carve-out lived in
  the shared, committed `aide.toml`, and only recognised one of the four
  syntaxes that point git at a repo other than cwd.** A machine-specific
  filesystem path (where a developer's local `aide-loop` clone happens to
  live) has no business in a file every consumer of the project shares — the
  same principle `aide.toml`'s own `[validation]` section already states for
  its profiles. `local_path` now lives in the personal, gitignored
  `.aide/loop/loop.local.toml` (`[framework]` section, alongside the existing
  `[loop]` one) instead; `loop.local.toml.example` documents both sections.
  `install.py`'s generated `aide.toml` no longer suggests setting it there.

  Separately, the guard's rule 1 recognised only `git -C <path>` — leaving
  `--git-dir=<path>`, `--work-tree=<path>`, and the `GIT_DIR=`/
  `GIT_WORK_TREE=` environment-variable prefixes (git's own equivalents,
  achieving the identical effect) completely unchecked: an agent that hit
  the `-C` block and reached for the next thing it knew could reach the exact
  repo the exception was built to gate, without ever declaring it. All four
  forms are now recognised, checked against the same declared `local_path`
  (`--git-dir`/`GIT_DIR=` accept the conventional `<path>/.git` value too,
  not only `<path>` itself), and a command mixing a declared and an
  undeclared repo across two of the forms stays blocked rather than guessed
  at.

- **The validator's foreground-only rule didn't name `aide merge`.** The
  instruction to run the test suite synchronously in the foreground (never
  backgrounded) only covered the standalone `pytest` step; `aide merge`
  itself re-runs the full suite again under `git.mode = "auto-merge"` and
  takes just as long, but nothing told the validator that command needed the
  same discipline — in practice, sub-agents repeatedly deferred it to a
  background task and ended their turn with a placeholder, leaving the
  orchestrator with no verdict. The rule now explicitly names `aide merge`
  at both the point it's introduced and the point it's invoked.

## [1.4.1] — 2026-07-23

### Fixed

- **Any prose mention of "Item NNN" was read as a status declaration (issue
  #15).** `_parse_item_status` treated every occurrence of an item reference
  anywhere in `progress.md` as status-bearing, attributing to it whatever
  status terminated the line or its enclosing bullet. In practice that meant a
  verification-table Notes cell narrating a post-mortem across several item
  numbers, or an acceptance checkbox that merely cited the item it satisfies,
  could silently pull that item's tracked status backwards — the more
  honestly a project documented *why* something went wrong, the more spurious
  references it created.

  conventions.md §1 is specific that the only structural status declaration is
  a deliverable bullet's leading icon. `_parse_item_status` now attributes a
  reference only when it sits on such a bullet or one of its wrapped
  continuation lines (indented text with no bullet marker of its own) — a
  table cell, a checkbox, or an ordinary paragraph may name an item freely
  without affecting its status, exactly as the format contract already
  promised authors.

  **Consumer action:** none. A project whose narrative prose or acceptance
  checkboxes named item numbers may see those items' derived status move
  forward (to whatever their real deliverable bullet says, or absent if they
  have none yet) after updating; no document edit is required.

## [1.4.0] — 2026-07-23

### Added

- **Outcome targets — an expressible state for "the work shipped but the goal
  was not met" (issue #14).** The rollup deliberately equates a stage's ✅ with
  *its planned work shipped*; when a stage also carried a measured goal (an
  error-rate target, a benchmark), that goal had nowhere honest to live — it
  either became an Acceptance box that was auto-ticked into an over-claim, or
  the stage was held 🚧 forever against `aide check`'s permanent warning.
  progress.md now supports an optional `## Outcome targets` table
  (`| Target | Objective | Attempted by | Status | Evidence / follow-up |`,
  statuses `❓ Unverified` / `✅ Met` / `❌ Not met`, mirroring the env-gated
  verification table's table-local vocabulary). Semantics: a target never
  blocks its stage — it gates the **Objective coverage rows** instead.
  `aide progress` caps an objective's rollup below ✅ while a linked target is
  not Met; `aide check` errors on an objective claimed ✅ over a `❌ Not met`
  target (the goal-level mirror of the deliverable-level over-claim error) and
  warns on `❓ Unverified`; `aide status` prints every target not yet Met. A
  `❌ Not met` target routes through the insights inbox (`gap`), so follow-on
  work enters via the queue instead of retro-editing a closed stage's
  deliverable list. The roadmap template gains `Target:` bullets to mark
  outcome-shaped criteria; conventions.md §1 documents the split (stages track
  shipped work, targets track measured outcomes, objectives require both).

## [1.3.3] — 2026-07-23

### Added

- **`core/README.md`, installed as `.aide/README.md` (issue #16).** A consumer's
  `CLAUDE.md` links to `.aide/README.md` three times — for the loop, the
  orchestrators, and the merge policy — but no installer ever shipped that file.
  It existed in the original in-tree `.aide` skeleton and was deleted when the
  repo adopted the standalone framework, so the links survived the file. No
  installer change was needed: `install_engine` already copies `core/` wholesale,
  so a file added there ships automatically.

  The new file is consumer-framed (`.aide/…`, `.claude/…` paths) and covers what
  a consumer needs that `conventions.md` deliberately doesn't: what's in `.aide/`,
  the six-step loop, the three orchestrators, model routing by capability tier,
  the merge policy, and shared-vs-personal files. It excludes anything about
  maintaining the framework itself (install instructions, the version-bump
  policy, this repo's own layout) — that stays in the root `README.md`, which now
  links to `core/README.md` instead of carrying a second copy of the same
  sections.

  Also added `tests/test_installed_docs_links.py`, which installs into a temp
  directory and asserts every relative markdown link under the installed
  `.aide/` resolves — so a future file move or rename that breaks a consumer-side
  link fails the suite instead of surfacing three commits later in someone
  else's `CLAUDE.md`.

  **Also fixed:** `pytest.ini`'s `testpaths` only listed `core adapters`, so a
  bare `pytest` (what CI runs) silently skipped the whole top-level `tests/`
  suite — including `test_repo_versioning.py`, the very test that enforces the
  `core/VERSION` bump rule this entry follows. `testpaths` now includes `tests`.

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
