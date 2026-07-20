# AIDE — AI-Driven Engineering framework

A lean, standalone loop for driving a project from vision to shipped code with
fresh, role-scoped sub-agents and deterministic scripts for the mechanical parts.
Two principles govern everything: **lean over formal**, **token efficiency over
over-formal process** — deterministic work is scripted, only genuine reasoning is
spent on agents.

This repository (**`aide-loop`**) is the framework itself. A project installs it
with [`install.py`](install.py) and pulls updates, rather than carrying its own copy
in-tree.

---

## The three-layer model

A working install is **three layers**, and it needs all three:

| Layer | What it is | In this repo | Installed as | Claude-coupled? |
|---|---|---|---|---|
| **Engine** | Provider-agnostic core: document formats, the deterministic CLI, the decision loop | [`core/`](core/) | `<repo>/.aide/` | **No** |
| **Adapter** | How one runtime *drives* the engine: role agents, workflow entry-points, orchestrators, permissions | [`adapters/claude/`](adapters/claude/) | `<repo>/.claude/` | **Yes** — 100% Claude Code |
| **Project config** | This project's facts and living documents | — (created per project) | `aide.toml`, `docs/aide/` | No |

The load-bearing distinction: the **engine is the provider-agnostic half, the
adapter is the provider half** — co-equal, not core + optional glue. A different
runtime (Cursor, Copilot, Gemini CLI, a raw SDK driver) **replaces the adapter
wholesale** while reusing the engine unchanged; the engine has zero Claude coupling
by design. Claude Code is the **reference adapter** (fully built and proven here).

> **Note on paths.** In *this* repo the layers are `core/` and `adapters/…`. In a
> *consumer* they are the installed `.aide/` and `.claude/`. This README uses the
> `core/`/`adapters/` names when pointing at files here, and `.aide/`/`.claude/`
> when describing the installed result (e.g. the CLI always runs as
> `python .aide/scripts/aide.py`).

---

## Install

```
python install.py --adapter claude --into <target-repo>
```

Stdlib-only, cross-OS. It:

1. copies `core/` → `<target>/.aide/` (the engine)
2. copies the Claude control files → `<target>/.claude/` — **non-clobbering**: an
   existing `settings.json` is never overwritten; the framework's version is emitted
   as a `.aide-merge` diff to reconcile by hand
3. copies the usage probe → `<target>/.aide/loop/usage_probe.py` (the loop's seam)
4. scaffolds `<target>/aide.toml` (prompts for `source_dir`, `test_command`,
   `git.mode`; `--yes` + flags for non-interactive/CI use)
5. appends the framework `.gitignore` block if absent
6. records the installed `VERSION` (`core/VERSION`, currently `1.0.0`) — copied in as
   `<target>/.aide/VERSION`

**`python install.py --adapter claude --into <target> --update`** re-copies the
engine and adapter (engine is framework-owned) but **never** touches `aide.toml` or
`docs/aide/` (project-owned). Pin a consumer to a `VERSION` and `--update` to move it
forward. See [`docs/quickstart.md`](docs/quickstart.md) to go from install to first
merged item.

## Repo layout

```
aide-loop/
├── core/                    LAYER 1 — provider-agnostic engine
│   ├── conventions.md       format contract · claim protocol · command hygiene · git/clarify modes
│   ├── templates/           vision · roadmap · progress · queue · item
│   ├── scripts/aide.py      the stdlib CLI (+ tests/)
│   ├── loop/loop.py         the usage-gated supervisor (+ a pluggable probe seam)
│   └── VERSION
├── adapters/
│   ├── ADAPTER-SPEC.md      the engine↔adapter contract (what any runtime must express)
│   ├── claude/              LAYER 2 — the reference adapter (agents · skills · commands · hooks · settings.json · usage_probe.py)
│   └── copilot/ cursor/ gemini/   porting stubs (future work)
├── docs/                    quickstart.md · concepts.md
├── install.py               the cross-OS installer
└── README.md · LICENSE
```

- [`core/conventions.md`](core/conventions.md) — the shared contract every agent,
  script, and human obeys. Read it; the loop assumes it.
- [`adapters/ADAPTER-SPEC.md`](adapters/ADAPTER-SPEC.md) — what any runtime must
  express (seven entry-points, five role tiers, three orchestrators, the shared CLI)
  to drive the engine. The Claude adapter is its reference implementation; see
  [`adapters/claude/README.md`](adapters/claude/README.md) for the concept→primitive map.

---

## The AIDE loop

Living documents under `docs/aide/` (in the consumer). Steps 1–3 are one-time;
4–6 repeat.

1. **create-vision** → `vision.md` (once)
2. **create-roadmap** → `roadmap.md` (once)
3. **create-progress** → `progress.md` (once)
4. **create-queue** → `queue/queue-NNN.md` — the next batch (one stage / small
   phase, ≤ `loop.queue_cap` items)
5. **create-item** → `items/NNN-*.md` — one testable spec
6. **execute-item** → tests + implementation + validation + merge; updates
   `progress.md`

Repeat 5–6 until the queue empties, then back to 4. Each step is an **entry-point**
the adapter exposes in its runtime's primitive — for Claude Code, pure-markdown
skills (`.claude/skills/aide-*`) that run on any OS.

### Orchestrators (item ⊂ queue ⊂ roadmap)

Three nested drivers. The invoking session is a light **orchestrator** that spawns a
sub-agent per leaf task and gates approvals — run it on **Sonnet**.

- **`/aide-run-item NNN`** — one already-claimed item end-to-end: spec-author →
  test-writer → builder → validator+merge, with a ≤`loop.validation_rounds`
  build↔validate cycle.
- **`/aide-run-queue [NNN]`** — claims each item (`aide claim`) then runs it via
  `/aide-run-item`, until the queue empties. Does **not** create the next queue.
- **`/aide-run-roadmap`** — loops over queues: generate a queue → run it → generate
  the next, until the roadmap is exhausted. **Each new queue lands via a
  human-reviewed PR** — the batch checkpoint, one review per ~10 items.

For Claude Code these load each other **as skills in the same session** (prompt
expansions, not subprocesses); the only isolated contexts are the sub-agents doing
the leaf work. Git commits are the durable checkpoint, so a restart re-enters
cleanly. A runtime that can't nest prompt-expansions satisfies the contract with a
manual runbook calling the same `aide.py` steps in the same order.

---

## Model routing by role (capability tiers)

Five sub-agents split work by role. The contract names **capability tiers**, not
model names, so each adapter binds a tier to its own runtime's models (as high as
necessary, as low as adequate). Deterministic recon/claim is **not** an agent —
orchestrators call `aide claim`.

| Role | Tier | Claude binding | Role |
|---|---|---|---|
| `queue-planner` | **T3** (strongest) | Opus · xhigh | authors one queue batch (cascades into ~10 items) |
| `spec-author` | **T3** | Opus · high | authors one item spec (cascades into 3 downstream agents) |
| `test-writer` | **T2** (mid) | Sonnet · medium | writes AC + adversarial tests |
| `builder` | **T2** (→T3 late retry) | Sonnet (→Opus round 3) | implements `source_dir` to satisfy every AC |
| `validator` | **T2** | Sonnet · medium | quality gate: tests, AC coverage, scope, vision fit; reconciles + merges |

The Claude adapter binds **T3→Opus, T2→Sonnet** (`adapters/claude/agents/`); `max` is
reserved for genuinely intractable one-offs. No agent signs off its own work; a fresh
instance per item.

**Deterministic work is scripted, not delegated** — recon/claim, progress
reconciliation, queue tidy, merge+cleanup, venv check, the consistency check,
session preflight, branch clean-up, and the state report are `aide.py` subcommands
(`python .aide/scripts/aide.py {check, progress, queue, claim, merge, env, sync,
gc, status}`). Agents keep only the reasoning: prioritisation, AC design, test
design, implementation, quality judgment. This shared CLI is the contract's anchor — identical
across every adapter.

---

## Merge policy

- **Work-item execution** may merge straight to `main` (no PR) once green —
  `aide merge` does it per `git.mode`. Still branch per item for the claim signal.
- **Framework / process changes require a reviewed PR**: `aide.toml`, `.aide/**`,
  `docs/aide/vision.md`, `docs/aide/roadmap.md`, `CLAUDE.md`, the `.claude/`
  control files. They cascade into every future queue, so they need team agreement.

Rule of thumb: if the change alters a *future* queue/item, it needs a PR; if it only
*executes* the current item, merge it.

### Shared vs. personal (in a consumer)

- **Shared (committed):** `.aide/` (minus `loop.local.toml`), `aide.toml`,
  `.claude/{agents,commands,skills,hooks,settings.json}`, `CLAUDE.md`, the
  `docs/aide/` living documents.
- **Personal (git-ignored):** `.aide/loop/loop.local.toml`,
  `.claude/settings.local.json`, `docs/aide/permissions/*.jsonl`,
  `docs/aide/status/*.html`, credentials. Never commit credentials.

---

## Unattended long runs

`/aide-run-roadmap` pauses at each queue PR by design. For genuinely unattended
overnight runs, an **external supervisor** (`core/loop/loop.py`, installed to
`.aide/loop/` and configured by a gitignored `loop.local.toml`) relaunches the gated
command when usage limits allow, relying on git commits + resume logic for durable
state. There is no in-process headless nesting.

The supervisor is **provider-agnostic**: its RUN/WAIT/STOP decision loop lives in
`loop.py`, but the usage numbers come from a **pluggable probe** selected by
`[loop] usage_probe`. The Claude adapter ships `usage_probe.py` (`"anthropic-oauth"`,
the OAuth usage endpoint); any runtime without a usage API sets `usage_probe = "none"`
and the loop relaunches on a plain time cadence. This is the one core/adapter seam in
the loop — see [`adapters/ADAPTER-SPEC.md`](adapters/ADAPTER-SPEC.md) §6.

---

## Provenance

AIDE originated as an MIT-licensed **Spec Kit extension** by mnriem
([github.com/mnriem/spec-kit-extensions](https://github.com/mnriem/spec-kit-extensions/tree/main/aide)):
the seven-step workflow and the living-document templates come from there. This
project packages that workflow as a provider-agnostic engine plus swappable adapters
(the three-layer model above) rather than a single-runtime extension. See
[`LICENSE`](LICENSE) for the derivation notice.
