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
6. records the installed `VERSION` (`core/VERSION`) — copied in as
   `<target>/.aide/VERSION`

**`python install.py --adapter claude --into <target> --update`** re-copies the
engine and adapter (engine is framework-owned) but **never** touches `aide.toml` or
`docs/aide/` (project-owned). Pin a consumer to a `VERSION` and `--update` to move it
forward. See [`docs/quickstart.md`](docs/quickstart.md) to go from install to first
merged item.

**`python install.py --into <target> --check`** compares the consumer's installed
`.aide/VERSION` against this repo's `core/VERSION` and reports current / behind /
ahead, without writing anything. It exits non-zero when the consumer is behind, so
a project can gate on it.

## Versioning

`core/VERSION` is the single version of a working install; `install.py` copies it
into a consumer as `.aide/VERSION`, and that file is what tells a project it is
outdated. [`CHANGELOG.md`](CHANGELOG.md) records what each version changed.

**Bump on every commit that touches `core/` or `adapters/`** — those are exactly
what `--update` copies into a consumer, so a change there is a change the consumer
receives. Commits that only touch `README.md`, `docs/`, or this repo's own tests
change nothing a consumer installs and need no bump. SemVer, where the "API" is
what a consumer installs — the document formats, the `aide` CLI surface,
`aide.toml` keys, and the adapter's agents/skills/commands:

| Bump | When |
|---|---|
| **patch** | a fix that changes no interface — `1.2.0 → 1.2.1` |
| **minor** | a new verb, template, `aide.toml` key, agent, or skill — `1.1.0 → 1.2.0` |
| **major** | a consumer must edit its own files to update (renamed key, dropped verb, changed document format) |

This is **enforced, not remembered**: `tests/test_repo_versioning.py` fails the
suite when the branch's diff against `main` touches `core/` or `adapters/` while
`core/VERSION` is unchanged. The rule exists because it was already broken once —
seventeen consumer-visible commits shipped under `1.1.0`, so a consumer comparing
version numbers saw "up to date" while running a 27-commit-old engine.

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
├── docs/                    vision.md · quickstart.md · concepts.md
├── install.py               the cross-OS installer
└── README.md · LICENSE
```

- [`core/conventions.md`](core/conventions.md) — the shared contract every agent,
  script, and human obeys. Read it; the loop assumes it.
- [`adapters/ADAPTER-SPEC.md`](adapters/ADAPTER-SPEC.md) — what any runtime must
  express (seven entry-points, five role tiers, three orchestrators, the shared CLI)
  to drive the engine. The Claude adapter is its reference implementation; see
  [`adapters/claude/README.md`](adapters/claude/README.md) for the concept→primitive map.
- [`docs/vision.md`](docs/vision.md) — what the framework is *for*, the
  commitments that shape it, and the non-goals it refuses. Order and status for
  the framework's own work live in its
  [GitHub Project](https://github.com/users/dadrobny/projects/1), not in any
  document here.

**Source vs. installed paths (a gotcha for editors).** The adapter control files
(`adapters/claude/{agents,skills,commands}`) and `core/conventions.md` reference
`.aide/…`, `.claude/…`, and `python .aide/scripts/aide.py`. Those are *consumer*
paths — the layout `install.py` materialises in a target repo — and are **correct**;
do **not** rewrite them to this repo's source layout (`core/…`, `adapters/…`). The
framework repo's structure is the *source*; the control files describe the *installed*
result. Only the repo-level docs (this README, `docs/`, the adapter README) describe
this repo's own structure.

---

## How the loop works

The engine documents *how the loop works* — the six-step workflow, the three
nested orchestrators, model routing by capability tier, the merge policy, and
unattended long runs. That content ships to every consumer, so it lives at
[`core/README.md`](core/README.md) (installed as `.aide/README.md`) rather than
here — this README covers how the *framework itself* is built and shipped.

---

## Provenance

AIDE originated as an MIT-licensed **Spec Kit extension** by mnriem
([github.com/mnriem/spec-kit-extensions](https://github.com/mnriem/spec-kit-extensions/tree/main/aide)):
the seven-step workflow and the living-document templates come from there. This
project packages that workflow as a provider-agnostic engine plus swappable adapters
(the three-layer model above) rather than a single-runtime extension. See
[`LICENSE`](LICENSE) for the derivation notice.
