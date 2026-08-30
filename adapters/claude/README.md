# Claude Code adapter (reference implementation)

The reference AIDE adapter: it drives the provider-agnostic engine (`../../core/`)
from **Claude Code**. Where [`../ADAPTER-SPEC.md`](../ADAPTER-SPEC.md) states the
*contract* every adapter fulfils in the abstract (seven entry-points, five roles on
capability tiers, three orchestrators, the shared CLI, an optional permission policy
and usage probe), this README is the concrete **AIDE-concept → Claude-Code-primitive
map**: which file expresses each contract point, and how the tiers bind to Claude
models.

`install.py --adapter claude` copies this directory into a consumer:

| Source (here) | Installed to | Role |
|---|---|---|
| `agents/` `skills/` `commands/` `rules/` `hooks/` `scripts/` `settings.json` | `<repo>/.claude/` | the Claude harness |
| `usage_probe.py` | `<repo>/.aide/loop/usage_probe.py` | the loop's usage seam (co-located with the engine `loop.py`) |
| `default-context.json` | — | not installed; declares the instruction file and import syntax `install.py` uses to link `.aide/AGENT-CONTEXT.md` |
| `README.md` (this file) | — | not installed; documents the adapter |

Everything mechanical (recon/claim, progress reconciliation, queue tidy, merge,
env, the consistency check) is **not** re-implemented here — it is the engine CLI,
invoked identically by every adapter as `python .aide/scripts/aide.py {check,
progress, queue, claim, merge, env, sync, gc, status}` ([spec §4](../ADAPTER-SPEC.md)). The files
below only translate the *human-shaped* work into Claude Code's primitives.

---

## Entry-points → **skills** (`skills/aide-*/SKILL.md`)

The spec's seven workflow steps are expressed as Claude Code **skills** — each a
scoped, invocable unit (`/aide-create-vision`, …) that reads and writes the
documents in the exact shapes `conventions.md` §1 fixes.

| Spec step | Skill |
|---|---|
| 1 · create-vision | `aide-create-vision` |
| 2 · create-roadmap | `aide-create-roadmap` |
| 3 · create-progress | `aide-create-progress` |
| 4 · create-queue | `aide-create-queue` |
| 5 · create-item | `aide-create-item` |
| 6 · execute-item | `aide-execute-item` |
| 7 · feedback-loop | `aide-feedback-loop` |

Two skills go **beyond the seven** — Claude-specific conveniences, not new contract
obligations:

- **`aide-spec-queue`** — a batch variant of step 5: author specs for *every*
  unspecced item in a queue on one branch, interactively, front-loading the human so
  execution can then run unattended.
- **`aide-status-report`** — an auxiliary reporter: an evolving HTML status summary
  from the AIDE documents, test suite, and QC outputs. Not part of the loop.

## Roles → **agents** (`agents/*.md`), tiers bound to Claude models

The five roles ([spec §2](../ADAPTER-SPEC.md)) are Claude Code **sub-agents** —
fresh, role-scoped instances with `model:`/`effort:` frontmatter. The contract names
capability *tiers*; this adapter binds **T3 → Opus, T2 → Sonnet**:

| Role (`agents/…`) | Tier | `model:` | `effort:` |
|---|---|---|---|
| `queue-planner` | T3 | `opus` | `xhigh` |
| `spec-author` | T3 | `opus` | `high` |
| `test-writer` | T2 | `sonnet` | `medium` |
| `builder` | T2 (escalates to Opus on a late retry) | `sonnet` | `medium` |
| `validator` | T2 | `sonnet` | `medium` |

Recon/claim is **not** an agent — it is deterministic `aide claim`, so no `agents/`
file and no tier. No role signs off its own work; each item gets a fresh instance.

One further agent sits **outside** the five item roles, at the queue boundary:

| Agent | Tier | `model:` | `effort:` | When |
|---|---|---|---|---|
| `spec-reviewer` | T3 | `opus` | `high` | once per queue, after `/aide-spec-queue` authors every spec and **before any is built** |

It is not a sixth role — it never touches one item's lifecycle. It reads the
whole batch at once and reports the cross-item conflicts `aide check --queue`
cannot decide, because they turn on what a criterion *means*. It reviews only:
every finding is handed to the human, who decides which side was wrong.

## Orchestrators → **commands** (`commands/aide-*.md`)

The three nested drivers (item ⊂ queue ⊂ roadmap, [spec §3](../ADAPTER-SPEC.md)) are
Claude Code **slash-commands**; Claude loads the role agents as sub-agents within one
session, so the nesting is real, not a manual runbook.

- **`aide-run-item`** — one claimed item end-to-end: spec-author → test-writer →
  builder → validator+merge, with a ≤`loop.validation_rounds` build↔validate cycle.
- **`aide-run-queue`** — `aide claim` each item, `aide-run-item` it, until the queue
  empties. Does **not** create the next queue.
- **`aide-run-roadmap`** — generate a queue → run it → generate the next, until the
  roadmap is exhausted. Each new queue lands via a **human-reviewed PR** — the batch
  checkpoint, one review per ~10 items. This is also the loop supervisor's default
  command (see the usage probe below).

A fourth command, **`aide-review-permissions`**, is not an orchestrator — it belongs
to the permission model below.

The `/aide-*` entry-points can be launched from the IDE extension, the
interactive CLI, or the loop supervisor's top-level `claude -p` — these surfaces
differ in cwd behaviour, permission-ask handling, and session lifetime. The
differences, the unattended permission posture, and the trusted-folder caveat
are recorded in **[`execution-surfaces.md`](execution-surfaces.md)** — read it
before the first unattended run.

## Permission model → **`settings.json`** + **`hooks/`** (Claude-specific)

This is [spec §5](../ADAPTER-SPEC.md) — **optional**, provided only because Claude
Code *has* a permission model; a runtime without one omits all of it and relies on
the hygiene rules being followed. The **command-hygiene rules themselves** (one
command per call, no `cd`, no chained `&&`, no `2>&1`) are runtime-general and live
in `core/conventions.md`; only the **enforcement mechanism** and the
**"permission allow-list" framing** are adapter-local and documented here.

- **`settings.json`** — the allow/ask policy: a pre-approved **allow-list** (~60
  entries: reads, greps, the safe git verbs, `python .aide/scripts/aide.py …`, scoped
  `Edit`/`Write` under `docs/aide/`, `src/`, `tests/`) and an **ask-list** (~30
  entries gating the irreversible/outward-facing: `git push --force`, `gh pr
  create|merge`, edits to `.aide/**`, `CLAUDE.md`, `aide.toml`, the `.claude/`
  control files). `defaultMode` is `default`. The allow-list is what lets an
  unattended run proceed without stalling on a prompt; the ask-list is where a human
  stays in the loop. The write-scope entries (`Edit`/`Write` under `src/**` and
  `tests/**`) are **templated from `aide.toml`** at install time — `install.py`
  rewrites them to the project's `project.source_dir`/`project.tests_dir` (read via
  the engine's own config loader, so both interpret `aide.toml` identically). A
  consumer whose code lives in `lib/` and tests in `spec/` gets `Write(lib/**)` /
  `Write(spec/**)` automatically, with no manual override; the defaults leave the
  committed file byte-identical.
- **`settings.overlay.json`** — project-owned customisation, reconciled
  **deterministically** on every `install.py`/`--update`. While this file exists,
  `settings.json` is REGENERATED as `merge(framework base, overlay)` — so edit the
  overlay, never `settings.json` (edits there are overwritten). The merge algebra:
  objects deep-merge (overlay wins); **list** values (the `allow`/`ask`/`deny`
  lists, hook groups) take a `{ "add": [...], "remove": [...] }` operator —
  *additive by default*, so a framework update that adds a new default still reaches
  the project; a plain list replaces outright (escape hatch). Prefer adding to
  `deny` over removing from `allow` when tightening (deny is explicit and
  update-proof). A stale `remove` pin warns (never blocks); a malformed overlay
  aborts the install *before* any write, so a broken `settings.json` is never
  emitted. A fresh install scaffolds an inert `settings.overlay.json.example`.
  **Backward compatible:** with no overlay, an existing `settings.json` is still
  never clobbered — the framework's version is emitted as a `.aide-merge` diff that
  now also carries a **ready-to-adopt overlay** derived from your existing file
  (`derive_overlay`, the inverse of the merge). Save that block as
  `settings.overlay.json` and the migration is done in one step — no hand-merging.
  **Scope:** `settings.json` is the only JSON file the framework installs, so it is
  the only overlay target today; the merge engine is file-agnostic JSON and extends
  to any future framework-owned JSON with no new code. It does **not** apply to the
  Markdown control files (`agents/`, `skills/`, `commands/`, `rules/`) or the Python hooks —
  those are framework-owned wholesale, and a project diverges through its own seams
  (`CLAUDE.md`, `docs/aide/`, `aide.toml`), not by editing installed framework files.
- **`hooks/command_hygiene_guard.py`** — a `PreToolUse` hook on `Bash` that *enforces*
  the `conventions.md` hygiene contract: a reshapeable command that would otherwise
  miss the allow-list and stall the run is bounced back to be re-issued in an
  allow-listed shape, rather than hanging on a prompt.
- **`hooks/log_permission_event.py`** — `PreToolUse` + `PostToolUse` logging of
  prompt-eligible calls (`Bash`/`Edit`/`Write`/`Web…`) to
  `docs/aide/permissions/log.jsonl`; the request/completion pair lets a reviewer infer
  grant vs deny. It never replicates the allow-list.
- **`hooks/log_instructions_loaded.py`** + **`scripts/review_instructions.py`** —
  `InstructionsLoaded` logging to `docs/aide/instructions/log.jsonl`, and the
  report over it. This is how the §7 delivery contract stays checkable: a
  `paths:`-scoped rule whose globs stop matching is silently inert, and
  `review_instructions.py --strict` is the thing that says so.
- **`scripts/review_permissions.py`** + the **`aide-review-permissions`** command —
  aggregate that log into recurring bottlenecks and propose safe, recurring prompts to
  promote into the allow-list. The human makes the final allow/ask/leave call and the
  actual edit; the script only recommends.

**Allow-list command shaping.** The allow-list matches a command **prefix** and
auto-approves a compound only if *every* part matches — so beyond the runtime-general
hygiene in `conventions.md` §3, this adapter needs commands emitted in the shape the
matcher recognises, or an unattended run stalls on a prompt. These shapes are
delivered to every session and sub-agent by `rules/aide-command-hygiene.md`,
not restated per agent:

- **Recon via the Bash tool with `grep`** (`git branch -r | grep aide/`), never the
  PowerShell tool / `Select-String` — only `Bash(...)` rules are allow-listed.
- **Python/pytest via the venv in relative form** — `.venv/Scripts/python …` (Windows)
  or `.venv/bin/python …`, not an absolute path or the PowerShell call operator: only
  the relative prefix is allow-listed.
- **The `aide` CLI** as `python .aide/scripts/aide.py <cmd>` — one allow rule covers
  every subcommand (the engine already mandates this invocation, for a different
  reason: it is venv-independent).
- **Command substitution in commits** (`$(…)`/backticks) is **never** auto-approved —
  use `-m`/`-F` per `conventions.md` §3.

These shaping rules are Claude-adapter-specific (they exist because of the permission
allow-list); the underlying hygiene they build on is runtime-general and lives in the
engine's `conventions.md` §3.

## Contract delivery → **`rules/`** (`paths:`-scoped where it helps)

This is [spec §7](../ADAPTER-SPEC.md)'s §-level half. `conventions.md` is an
index over one file per section, and a section that is only *pointed at* is
read about 3% of the time — measured over 164 sub-agent spawns in a real
consumer. `.claude/rules/` closes that: a rule file loads because the runtime
loads it, not because a role decided to follow a link.

| File | Scope | Delivers |
|---|---|---|
| `rules/aide-command-hygiene.md` | unscoped — every session and every sub-agent | `conventions.md` §3, in positive form |
| `rules/aide-test-hygiene.md` | `paths:` — any file pytest would collect | §6 |
| `rules/aide-living-documents.md` | `paths:` — `progress.md`, `roadmap.md`, `vision.md`, `insights.md`, `queue/*.md`, `items/*.md` | the §1 document shapes |

**Scoped is not the same as rare.** `aide-living-documents.md` matches
`items/*.md` and `insights.md`, which all six roles reach, so it loads on
effectively every spawn — it is scoped for *correctness* (it is always
relevant), not for economy. It carries only the shapes; the durable-artifact,
insight-immutability and human-gate rules live in `AGENT-CONTEXT.md`, already
in every context. `aide-test-hygiene.md` is the one that genuinely fires only
where it matters.

The two scoped rules are matched **by filename, not by `project.tests_dir` /
`project.docs_dir`**, so they hold whatever a consumer configured — a rule that
silently stops matching is the failure this mechanism exists to remove, and
templating the globs at install time would reintroduce it as a config error.

**A `paths:` rule is armed by a read, not by a write.** `Edit` requires the file
to have been read first, so editing an existing document always arms the rule;
creating a *new* file that matches does not, on its own. The globs therefore
cover the files each role reads on the way to writing — `test-writer` is
*instructed* to read existing tests for style, `spec-author` reads
`queue/queue-NNN.md` before writing `items/NNN-*.md`.

That leaves one real hole: **a repo with no tests yet**. `test-writer` has
nothing to open, `Write` to a new file does not arm the rule, and it is exactly
when the fixture conventions are being set. Its spec therefore still carries an
explicit instruction to go read §6 itself. If that proves insufficient, the
mechanism that closes it completely is `skills:` frontmatter, which preloads
content at agent startup with no read involved — per-role, and cheaper than an
always-on rule. `review_instructions.py` is what would show the gap: a
`path_glob_match` count far below the number of runs.

A rule **defers to its section**: the engine copy is the source of truth, and a
rule that invents a rule of its own binds Claude and no other runtime.
[`tests/test_rules.py`](tests/test_rules.py) pins all three obligations, and
that the six agent specs never re-inline the block this replaced.

**Every rule declares its reach**, on one line, near the top of the body:

```
<!-- reach: all -->
<!-- reach: test-writer -->
```

`all`, or a comma-separated list of agent names; a note explaining the choice
goes on the lines below it inside the same comment.
[`tests/test_structural_budget.py`](../../tests/test_structural_budget.py)
installs the adapter, derives each role's read-set from the delivered agent
specs, evaluates the rule's `paths:` globs against it, and fails when the
declaration and the measurement disagree — the paragraph above about scoped
not meaning rare used to be prose nothing checked. The same module pins the
**always-on floor** (`AGENT-CONTEXT.md` plus every unscoped rule) per file, so
the constant term every spawn pays cannot move without a deliberate edit, and
prints the per-role byte table as diagnostics. The declaration is a comment
rather than a frontmatter key on purpose: it carries no runtime meaning, and it
survives the content moving to a skill.

## Usage probe → **`usage_probe.py`** (`anthropic-oauth`)

This is [spec §6](../ADAPTER-SPEC.md) — the one core/adapter seam in the loop. The
engine's supervisor (`loop/loop.py`) owns the RUN/WAIT/STOP_WEEKLY decision, and
calls a **pluggable probe** sitting next to it for the raw numbers.

- **`usage_probe.py`** implements the engine contract `get_usage(cfg) -> dict | None`
  against Anthropic's OAuth **usage endpoint** — it reads a *hard* utilisation number
  (`five_hour`/`seven_day` + `resets_at`), never scraped output, using the on-disk
  Claude Code OAuth token (`~/.claude/.credentials.json`, overridable via
  `credentials_path`). It returns `None` — degrading the loop to a plain time cadence,
  never crashing — when there is no token or the fetch fails.
- **Selection.** `[loop] usage_probe = "anthropic-oauth"` in the gitignored
  `.aide/loop/loop.local.toml` picks it; `"none"` (the engine default) ships no probe
  and relaunches on time cadence — the graceful path for any plan without a usage API.
- **Co-location** is what makes the seam resolve: `install.py` drops this file next to
  the engine `loop.py` in `.aide/loop/`, and `loop.py`'s `_import_probe_module()`
  imports the sibling by filename, never by provider name. That invariant is tested in
  [`tests/test_usage_probe.py`](tests/test_usage_probe.py).

---

## Default-context instructions → **`default-context.json`** (`CLAUDE.md` + `@path`)

This is [spec §7](../ADAPTER-SPEC.md). The engine's rules live in
`.aide/conventions.md`, which is read only when something points at it — weak in
an agent spec (about 3% of spawns follow the pointer) and absent entirely from an
interactive session, where a person and Claude Code produce durable artifacts
(commit messages, issue bodies, `insights.md` entries) with no agent spec in play.

Claude Code loads a `CLAUDE.md` at the repo root automatically and inlines `@path`
lines recursively, so the channel costs one line. The adapter declares both facts:

```json
{ "file": "CLAUDE.md", "import": "@{path}" }
```

`install.py` renders that to `@.aide/AGENT-CONTEXT.md` and ensures the line is
present in `<repo>/CLAUDE.md`, appending it (or creating a minimal file) and
touching nothing else — the project keeps everything it wrote. `--check` reports
a missing line as drift. The imported page is framework-owned wholesale: it is
part of `core/`, not a managed block inside a project-owned document, so there is
no drift detection to invent and no third ownership pattern.

---

## Layout

```
adapters/claude/
├── agents/        builder · queue-planner · spec-author · test-writer · validator
│                  spec-reviewer (queue boundary, not an item role)
├── skills/        aide-{create-vision,-roadmap,-progress,-queue,-item} ·
│                  aide-execute-item · aide-feedback-loop ·
│                  aide-spec-queue · aide-status-report
├── commands/      aide-run-{item,queue,roadmap} · aide-review-permissions
├── hooks/         command_hygiene_guard.py · log_permission_event.py
├── scripts/       review_permissions.py
├── settings.json  permission allow/ask-list + hook registration
├── usage_probe.py the anthropic-oauth usage probe (installed into .aide/loop/)
├── default-context.json   CLAUDE.md + @path — how .aide/AGENT-CONTEXT.md gets linked
└── tests/         test_usage_probe.py  (adapter/installer conformance)
```

For the *why* behind each obligation — and the conformance checklist a new adapter
works against — see [`../ADAPTER-SPEC.md`](../ADAPTER-SPEC.md).
