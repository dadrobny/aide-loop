# AIDE — AI-Driven Engineering framework

A lean, standalone loop for driving a project from vision to shipped code with
fresh, role-scoped sub-agents and deterministic scripts for the mechanical parts.
Two principles govern everything: **lean over formal**, **token efficiency over
over-formal process** — deterministic work is scripted, only genuine reasoning is
spent on agents.

**What installing it gets you.** A set of living documents under `docs/aide/` —
vision, roadmap, progress, work queues, item specs — that hold the plan between
sessions; a stdlib CLI (`aide`) that does the claiming, scoping, merging and
consistency checking no model should spend tokens on; and, for Claude Code, the
role agents, skills and permission settings that drive the two unattended.

**Who it is for.** A developer running an AI coding agent against a real codebase
for longer than one sitting, who wants the plan to survive the session and the
mechanical steps to stop costing tokens
([`docs/vision.md`](docs/vision.md) has the rest, including what it refuses to
be). [`docs/quickstart.md`](docs/quickstart.md) goes from install to a first
merged item; [`docs/concepts.md`](docs/concepts.md) is the mental model.

**Where to report.** A defect, a rule that did not reach an agent, or a gap in
the contract: [open an issue](https://github.com/dadrobny/aide-loop/issues) and
name the engine version you observed it under (`.aide/VERSION` in your repo).

This repository (**`aide-loop`**) is the framework itself. A project installs it
with [`install.py`](install.py) and pulls updates, rather than carrying its own copy
in-tree. The rest of this README covers how the framework is built and shipped.

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

**Requires Python 3.11+** on `PATH`, and a git repository to install into.
Installer, CLI and loop are stdlib-only, so nothing is `pip install`ed for AIDE
itself. 3.9 works too: the CLI carries a TOML fallback for interpreters without
`tomllib`.

**Get a version.** Every `core/VERSION` that reaches `main` is tagged
`v<VERSION>`, and since 1.52.1 published as a
[GitHub Release](https://github.com/dadrobny/aide-loop/releases) carrying that
version's `CHANGELOG.md` section (earlier versions are tags only). Check out the tag, or download the release's
source archive and unpack it; the installer copies from **the tree it is run
from**, so which version a consumer receives is decided by which checkout
`install.py` sits in — nothing is fetched.

```
git clone --branch v<VERSION> https://github.com/dadrobny/aide-loop
python aide-loop/install.py --adapter claude --into <target-repo>
```

Cross-OS. It:

1. copies `core/` → `<target>/.aide/` (the engine)
2. copies the Claude control files → `<target>/.claude/`. `settings.json` has two
   routes, chosen by whether the project has adopted an overlay:
   - **`.claude/settings.overlay.json` present** — `settings.json` is
     *regenerated* on every install and `--update` as a deterministic deep-merge
     of the framework's settings and the overlay. Framework changes flow
     through, the project's additions reapply, and nothing is reconciled by
     hand: edit the overlay, never the result. A malformed overlay fails the
     run (exit 3) with `settings.json` left as it was; fix the overlay and
     re-run.
   - **no overlay** — **non-clobbering**: an existing `settings.json` is never
     overwritten, and the framework's version is emitted as a `.aide-merge`
     diff to reconcile by hand. An inert `settings.overlay.json.example` is
     dropped beside it; renaming that file is how a project moves to the
     first route.

   Four of the control files are **generated** rather than copied: one marked
   `<!-- generated-from: .aide/conventions/<file>.md -->` is written as the
   adapter's own text followed by that contract section's core, verbatim. A
   section that cannot be rendered aborts the install before the first write.
3. copies the usage probe → `<target>/.aide/loop/usage_probe.py` (the loop's seam)
4. scaffolds `<target>/aide.toml` (prompts for `source_dir`, `test_command`,
   `git.mode`; `--yes` + flags for non-interactive/CI use)
5. ensures the runtime's instruction file (for Claude, `<target>/CLAUDE.md`)
   imports `.aide/AGENT-CONTEXT.md` — **one line**, appended, creating the file
   if it does not exist; everything else in it stays the project's
   ([ADAPTER-SPEC §7](adapters/ADAPTER-SPEC.md))
6. appends the framework `.gitignore` block if absent
7. records the installed `VERSION` (`core/VERSION`) — copied in as
   `<target>/.aide/VERSION`

**`python install.py --into <target> --update`** re-copies the
engine and adapter (engine is framework-owned) but **never** touches `aide.toml` or
`docs/aide/` (project-owned). The generated control files are **re-rendered**,
which is what makes an edit to a `conventions/` section reach the agents it is
delivered to with no second edit, and an overlay-driven `settings.json` is
regenerated. It also removes what the framework has dropped:
engine files no longer in `core/`, and adapter files it once wrote — recorded in
`.aide/adapter-manifest.txt`, the list of every adapter file the installer
itself put there — that the adapter no longer ships; a file it did not
write is never removed. Pin a consumer to a `VERSION` by updating from that
version's tag, and `--update` from a later one to move it forward. See [`docs/quickstart.md`](docs/quickstart.md) to go from install to first
merged item.

**`python install.py --into <target> --check`** compares the consumer's installed
`.aide/VERSION` against the `core/VERSION` of **the tree the installer is run
from** — a checkout of `v1.2.0` answers "is this consumer behind 1.2.0", not
"behind the latest release" — and reports current / behind /
ahead, without writing anything. It exits non-zero when the consumer is behind —
or when the instruction file has lost its `.aide/AGENT-CONTEXT.md` import, which
no version number can express — so a project can gate on it.

### What belongs in the instruction file

Everything below the import line is the project's, and the installer reads the
file for exactly one thing: whether that line is there. So a *copy* of contract
text in it is unmaintainable by construction — no update pass owns it, and it
drifts until it contradicts the contract it was copied from. Point at the
contract instead: the import already delivers `AGENT-CONTEXT.md`, and a `§N`
pointer resolves into `.aide/conventions/`.

Adopting the import in a repo that predates it is therefore two steps. Run
`--update`, then **prune the restatements it makes redundant**. If one of them
says something the shipped contract does not, that is a gap in the contract —
[open an issue](https://github.com/dadrobny/aide-loop/issues) rather than keep
the local copy, which is the one way an unguarded duplicate earns its keep and
then outlives its usefulness. `--check` names such passages, one line per
section of the file, and **does not fail on them**: the file is yours.

## Versioning

`core/VERSION` is the single version of a working install; `install.py` copies it
into a consumer as `.aide/VERSION`, and that file is what tells a project it is
outdated. [`CHANGELOG.md`](CHANGELOG.md) records what each version changed.

SemVer, where the "API" is what a consumer installs — the document formats, the
`aide` CLI surface, `aide.toml` keys, and the adapter's agents/skills/commands:

| Bump | When |
|---|---|
| **patch** | a fix that changes no interface — `1.2.0 → 1.2.1` |
| **minor** | a new verb, template, `aide.toml` key, agent, or skill — `1.1.0 → 1.2.0` |
| **major** | a consumer must edit its own files to update (renamed key, dropped verb, changed document format) |

Every change to `core/` or `adapters/` — exactly what `--update` copies — moves
the version, and the suite fails a branch that forgets
(`tests/test_repo_versioning.py`), so an unchanged `.aide/VERSION` means an
unchanged install.

## Repo layout

```
aide-loop/
├── core/                    LAYER 1 — provider-agnostic engine
│   ├── conventions.md       the index: §N -> conventions/N-*.md
│   ├── conventions/         format contract · claim protocol · command hygiene · git/clarify modes · test hygiene · off-platform · sibling repos
│   ├── AGENT-CONTEXT.md     the page that must bind before anything points anywhere
│   ├── templates/           vision · roadmap · progress · queue · item · insights · ledger
│   ├── scripts/aide.py      the stdlib CLI (+ tests/)
│   ├── loop/loop.py         the usage-gated supervisor (+ a pluggable probe seam)
│   └── VERSION
├── adapters/
│   ├── ADAPTER-SPEC.md      the engine↔adapter contract (what any runtime must express)
│   ├── claude/              LAYER 2 — the reference adapter (agents · skills · commands · rules · hooks · settings.json · usage_probe.py · default-context.json)
│   └── copilot/ cursor/ gemini/   porting stubs (future work)
├── docs/                    vision.md · quickstart.md · concepts.md
├── install.py               the cross-OS installer
└── README.md · LICENSE · NOTICE · SECURITY.md · CONTRIBUTING.md
```

- [`core/conventions.md`](core/conventions.md) — the shared contract every agent,
  script, and human obeys, as an index over
  [`core/conventions/`](core/conventions/): one file per numbered section, so a
  `§N` pointer resolves to a file rather than an offset into a long document.
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
(`adapters/claude/{agents,skills,commands,rules}`) and `core/conventions/**` reference
`.aide/…`, `.claude/…`, and `python .aide/scripts/aide.py`. Those are *consumer*
paths — the layout `install.py` materialises in a target repo — and are **correct**;
do **not** rewrite them to this repo's source layout (`core/…`, `adapters/…`). The
framework repo's structure is the *source*; the control files describe the *installed*
result. Only the repo-level docs (this README, `docs/`, the adapter README) describe
this repo's own structure.

---

## How the loop works

The engine documents *how the loop works* — the workflow's steps, the three
nested orchestrators, model routing by capability tier, the merge policy, and
unattended long runs. That content ships to every consumer, so it lives at
[`core/README.md`](core/README.md) (installed as `.aide/README.md`) rather than
here — this README covers how the *framework itself* is built and shipped.

---

## Provenance

AIDE started from an MIT-licensed **Spec Kit extension** by mnriem
([github.com/mnriem/spec-kit-extensions](https://github.com/mnriem/spec-kit-extensions/tree/main/aide)).
What is still recognisably from there is the skeleton: the sequence vision →
roadmap → progress → queue → item → execute → feedback, and the idea of living
documents that carry a plan between sessions. Nearly everything around that
skeleton was built here — the numbered contract in `conventions/`, the
deterministic CLI and its consistency gate, role-scoped sub-agents on capability
tiers, the orchestrators and the usage-gated supervisor, the engine/adapter
split, and the installer. [`NOTICE`](NOTICE) carries the derivation; the
license is MIT.
