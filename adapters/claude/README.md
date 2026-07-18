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
| `agents/` `skills/` `commands/` `hooks/` `scripts/` `settings.json` | `<repo>/.claude/` | the Claude harness |
| `usage_probe.py` | `<repo>/.aide/loop/usage_probe.py` | the loop's usage seam (co-located with the engine `loop.py`) |
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
  stays in the loop. **`install.py` never clobbers an existing `settings.json`** — it
  emits a `.aide-merge` diff for the human to reconcile. The write-scope entries
  default to `src/**` and `tests/**` (the engine's default `source_dir`/`tests_dir`);
  a consumer whose code lives elsewhere aligns those two globs with its `aide.toml`.
- **`hooks/command_hygiene_guard.py`** — a `PreToolUse` hook on `Bash` that *enforces*
  the `conventions.md` hygiene contract: a reshapeable command that would otherwise
  miss the allow-list and stall the run is bounced back to be re-issued in an
  allow-listed shape, rather than hanging on a prompt.
- **`hooks/log_permission_event.py`** — `PreToolUse` + `PostToolUse` logging of
  prompt-eligible calls (`Bash`/`Edit`/`Write`/`Web…`) to
  `docs/aide/permissions/log.jsonl`; the request/completion pair lets a reviewer infer
  grant vs deny. It never replicates the allow-list.
- **`scripts/review_permissions.py`** + the **`aide-review-permissions`** command —
  aggregate that log into recurring bottlenecks and propose safe, recurring prompts to
  promote into the allow-list. The human makes the final allow/ask/leave call and the
  actual edit; the script only recommends.

**Allow-list command shaping.** The allow-list matches a command **prefix** and
auto-approves a compound only if *every* part matches — so beyond the runtime-general
hygiene in `conventions.md` §3, this adapter needs commands emitted in the shape the
matcher recognises, or an unattended run stalls on a prompt:

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
engine's `conventions.md`.

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

## Layout

```
adapters/claude/
├── agents/        builder · queue-planner · spec-author · test-writer · validator
├── skills/        aide-{create-vision,-roadmap,-progress,-queue,-item} ·
│                  aide-execute-item · aide-feedback-loop ·
│                  aide-spec-queue · aide-status-report
├── commands/      aide-run-{item,queue,roadmap} · aide-review-permissions
├── hooks/         command_hygiene_guard.py · log_permission_event.py
├── scripts/       review_permissions.py
├── settings.json  permission allow/ask-list + hook registration
├── usage_probe.py the anthropic-oauth usage probe (installed into .aide/loop/)
└── tests/         test_usage_probe.py  (adapter/installer conformance)
```

For the *why* behind each obligation — and the conformance checklist a new adapter
works against — see [`../ADAPTER-SPEC.md`](../ADAPTER-SPEC.md).
