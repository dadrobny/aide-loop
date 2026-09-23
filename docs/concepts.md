# Concepts

The mental model behind AIDE. For the hands-on path see
[`quickstart.md`](quickstart.md); for the exact document formats and the
engine↔adapter contract see [`../core/conventions.md`](../core/conventions.md) and
[`../adapters/ADAPTER-SPEC.md`](../adapters/ADAPTER-SPEC.md).

## Two principles

Everything follows from two: **lean over formal**, and **token efficiency over
over-formal process**. Concretely — *deterministic work is scripted, only genuine
reasoning is spent on agents*. The mechanical 80% (parsing documents, claiming
work, merging, checking consistency) is a plain CLI; agents are spent only on
prioritisation, spec/test/quality judgment, and implementation.

## The three layers

A working install is three layers, and it needs all three:

- **Engine** (`core/` → installed as `.aide/`) — provider-agnostic. The document
  *formats*, the deterministic CLI (`aide.py`), and the loop's decision logic. No
  knowledge of any specific LLM runtime.
- **Adapter** (`adapters/<name>/` → installed as the runtime's dir, e.g. `.claude/`)
  — how one runtime *drives* the engine: its role agents, workflow entry-points,
  orchestrators, and (optionally) a permission policy.
- **Project config** (`aide.toml` + `docs/aide/`) — this project's facts and living
  documents. Never part of the framework.

The load-bearing idea: **engine and adapter are co-equal halves**, not core +
optional glue. Swapping runtimes replaces the *adapter* wholesale and reuses the
engine unchanged — which is only possible because the engine has zero coupling to
any provider. Claude Code is the **reference adapter**; the contract every adapter
fulfils is [`ADAPTER-SPEC.md`](../adapters/ADAPTER-SPEC.md).

## The seven-step loop

Work flows through seven **entry-points**, each producing or advancing a living
document under `docs/aide/`:

| # | Step | Produces | Cadence |
|---|---|---|---|
| 1 | create-vision | `vision.md` | once |
| 2 | create-roadmap | `roadmap.md` | once |
| 3 | create-progress | `progress.md` | once |
| 4 | create-queue | `queue/queue-NNN.md` | per batch |
| 5 | create-item | `items/NNN-*.md` | per item |
| 6 | execute-item | tests + code + validation + merge; updates `progress.md` | per item |
| 7 | feedback-loop | process/document improvements | as needed |

Steps repeat 5→6 until a queue empties, then 4 mints the next. The documents have
**fixed shapes** so the CLI parses them without heuristics — that contract lives in
`conventions.md` §1 and `aide check` enforces it. An adapter expresses each
entry-point in its runtime's primitive (Claude Code: skills).

## Roles and capability tiers

The work of one item is split across **five fresh, role-scoped sub-agents** — no
role signs off its own work, and each item gets a fresh instance (no context bleed).
The contract names **capability tiers**, not model names, so each adapter binds a
tier to its own models:

| Role | Tier | Why the tier |
|---|---|---|
| queue-planner | **T3** (strongest) | one plan cascades into ~10 items |
| spec-author | **T3** | the item spec is its single source of truth, feeding 3 downstream roles |
| test-writer | **T2** (mid) | well-scoped against a fixed spec |
| builder | **T2** (escalates to T3 when a failure survives a round or is serious) | implements against a fixed spec + tests |
| validator | **T2** | quality gate against fixed acceptance criteria; reconciles + merges |

Recon/claim is **not** a role — it is deterministic (`aide claim`), so no agent and
no tier. The Claude adapter binds **T3→Opus, T2→Sonnet**. A runtime without
sub-agents degrades gracefully to "a fresh chat per role" — the roles and their
tiers still hold. Exact model IDs and effort levels per role are pinned in
[`ADAPTER-SPEC.md`](../adapters/ADAPTER-SPEC.md) §2.

Two further roles are **optional**, and an adapter may omit them: a
**reviewer** (T2), an adversarial read of an item's diff concurrent with the
validator, which produces findings and merges nothing — off unless `aide.toml`
sets `loop.review`; and a **spec-reviewer** (T3), which reads a whole queue's
specs at once, when they are written up front, and reports the conflicts
between them for a human to arbitrate.

## Orchestrators (item ⊂ queue ⊂ roadmap)

Three nested drivers sequence the roles:

- **run-item** — one claimed item end-to-end (spec → tests → build → validate →
  merge), with a bounded build↔validate cycle (`loop.validation_rounds`); the
  builder steps up a tier when a failure survives a round or is serious from
  the start.
- **run-queue** — claim + run-item each item until the queue empties. Does *not*
  create the next queue.
- **run-roadmap** — generate a queue → run it → generate the next, until the
  roadmap is exhausted.

The human checkpoint sits at the **queue boundary**: each new queue lands via a
review (a PR for Claude) — roughly one human review per ten items. Git commits are
the durable state, so a restart at any granularity re-enters cleanly. A runtime that
can't nest prompt-expansions satisfies the contract with a manual runbook calling
the same `aide.py` steps in the same order.

## The deterministic CLI (the contract's anchor)

Every adapter routes all mechanical work through the **same** stdlib CLI:

```
python .aide/scripts/aide.py {check, scope, progress, gate, queue, insights, ledger, claim, merge, env, sync, gc, status}
```

- **check** — consistency gate over `docs/aide/` (shapes, statuses, rollups).
- **scope** — an item branch's diff against the paths its spec authorises.
- **progress** — edit `progress.md` status deterministically.
- **gate** — list and resolve the human gates recorded in `progress.md`.
- **queue** — queue branch creation and maintenance (start, tidy).
- **insights** — the insight inbox: list, tick, archive, resolve.
- **ledger** — the run ledger's row for an item that never merged (`merge`
  writes every other row).
- **claim** — pick + claim the next unclaimed item (the recon step; not an agent).
- **merge** — merge a validated item per `git.mode`, re-run tests, clean up.
- **env** — venv existence / import check (+ bootstrap).
- **sync** — session preflight: fetch, clean-tree check, land on the right branch.
- **gc** — delete claim branches whose work has landed (dry-run by default).
- **status** — one-call roadmap-state report: branch + divergence, derived queue
  states, claim branches, open PRs (best effort).

This invocation is identical across providers and implementation-agnostic — a future
compiled `aide` binary exposing the same subcommands is a drop-in substitution with
no change to any adapter. It is why generality is real rather than aspirational: the
hard 80% is already shared.

**Why Python for the engine.** `aide.py` and `install.py` are stdlib-only
Python 3.11+ (3.9 works too — the CLI has a TOML fallback), so the engine runs on a
stock interpreter with no dependency resolution — the reason it works *before* a
project venv exists and behaves identically across OSes. A consuming project therefore
needs a Python interpreter even when its own code is in another language; for the
common case that costs nothing (the interpreter is near-universal). Full
*language*-independence would mean reimplementing the subcommands as a compiled single
binary (Go/Rust, or a frozen build) plus a per-OS release matrix — moderate effort,
low near-term payoff, so it stays deferred until a real no-Python consumer appears.
*Platform*-independence short of that is just the bounded CLI swap above.

## Git modes and the merge policy

`git.mode` in `aide.toml` selects how a green item lands — **`auto-merge`** (direct
to `main`), **`pr`** (push + stop for a human PR), or **`local`** (offline, no
pushes). It is enforced *only* inside `aide claim`/`aide merge`; agent instructions
are identical across modes.

Orthogonal to that: **framework/process changes always want a reviewed PR**
regardless of `git.mode`, because they cascade into every *future* queue. The rule of
thumb — *if a change alters a future queue/item it needs a PR; if it only executes the
current item, merge it.*

## Command hygiene

A small set of runtime-general rules keeps shell commands robust and
failure-localised. They are engine-level and stated once, in `conventions.md`
§3; this page points there rather than summarising them. *How* they're
enforced, and any provider-specific command shaping a permission policy
demands, are **adapter** concerns — for Claude, a `PreToolUse` hook plus a permission
allow-list (see [`../adapters/claude/README.md`](../adapters/claude/README.md)).

## Unattended runs

The loop pauses at each queue PR by design, and between those checkpoints a run is
one session. **Nothing in the framework relaunches it.** Continuous operation —
across usage windows, or across several AIDE repos — is an external scheduler's
job ([`vision.md`](vision.md) → *Not a scheduler*); the engine's side of that
bargain is that relaunching is cheap, because state lives in git commits and the
living documents and a fresh session re-reads them, so a cutoff never loses
in-flight work. The minimum scheduler is a shell loop around the launch command.

What a scheduler has to get right is the **launch contract** — which surface the
run is launched on, how permissions resolve there, and what a non-interactive
session cannot do. That is adapter-specific and written down per adapter; for
Claude, [`../adapters/claude/execution-surfaces.md`](../adapters/claude/execution-surfaces.md).

## Shared vs. personal

- **Shared (committed):** `.aide/` (minus `local.toml`), `aide.toml`, the
  `.claude/` control files, `CLAUDE.md`, the `docs/aide/` living documents.
- **Personal (git-ignored):** `.aide/local.toml`,
  `.claude/settings.local.json`, permission logs, generated status HTML, and any
  credentials. Never commit credentials.
