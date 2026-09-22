# Quickstart

From zero to a running AIDE loop in a target repo. Assumes the **Claude Code**
adapter; other adapters follow the same shape with their own runtime's primitives.
For the *why* behind each piece, read [`concepts.md`](concepts.md).

## 0. Prerequisites

- **Python 3.11+** on `PATH` (3.9 works too — the CLI has a TOML fallback). The
  engine is stdlib-only; nothing to `pip install` for AIDE itself.
- **Claude Code**, for the reference adapter's skills/commands/agents.
- A **git repo** to install into, with its own test command (e.g. `pytest`).

## 1. Install

From a checkout of this framework repo — a release tag (`git clone --branch
v<VERSION> …`, or a release's source archive) if you want a known version; the
installer copies from the tree it is run from:

```
python install.py --adapter claude --into /path/to/your-repo
```

It prompts for `source_dir`, `test_command`, and `git.mode` (or pass
`--source-dir`, `--test-command`, `--git-mode`, `--yes` to skip prompts). This
writes into your repo:

- `.aide/` — the engine (CLI, templates, conventions, loop)
- `.claude/` — the Claude adapter (agents, skills, commands, hooks, `settings.json`)
- `aide.toml` — your project config (yours to edit; `--update` never touches it)
- an appended `.gitignore` block

If a `.claude/settings.json` already exists it is **not** overwritten — a
`.aide-merge` diff is written for you to reconcile, then delete. To stop
reconciling by hand, rename the scaffolded `.claude/settings.overlay.json.example`
to `settings.overlay.json` and put your project's additions there: from then on
`settings.json` is regenerated from the framework's settings plus your overlay
on every install and `--update`.

Commit the scaffold so the loop has a clean starting point.

## 2. Verify the install

From inside your repo:

```
python .aide/scripts/aide.py env      # venv health: exists, bootstrap finished, imports, test runner (add --bootstrap to build it)
python .aide/scripts/aide.py check    # consistency gate over docs/aide/
```

`check` will report the living documents as missing — expected, you create them
next. (`env` is only relevant if your project uses a venv; set `[python]` in
`aide.toml` — `interpreter = "python3.12"` there pins what `--bootstrap`
builds the venv from, when the dependency closure resolves on a narrower
Python range than the project declares.)

## 3. Author the plan (one-time)

In Claude Code, run the three setup skills in order — each reads the previous
document and writes the next:

```
/aide-create-vision      → docs/aide/vision.md
/aide-create-roadmap     → docs/aide/roadmap.md
/aide-create-progress    → docs/aide/progress.md
```

Review each before moving on — the vision cascades into every future queue. When
they're in, `python .aide/scripts/aide.py check` should pass.

## 4. Run the loop

Two ways, same engine:

**Guided, unattended-ish (recommended).** One command drives the whole roadmap —
generate a queue → run every item → generate the next — pausing at each queue for a
human-reviewed PR:

```
/aide-run-roadmap
```

**Step by step**, if you'd rather drive it yourself:

```
/aide-create-queue                    # the next batch (≤ loop.queue_cap items)
/aide-create-item                     # one testable spec  (repeat per item)
/aide-execute-item                    # tests → build → validate → merge (repeat)
```

Each item is authored (spec-author) → tested (test-writer) → built (builder) →
validated + merged (validator) by fresh, role-scoped sub-agents; `aide claim` picks
the next item deterministically. Two further roles are optional: a reviewer reading each
item's diff alongside the validator, off until `aide.toml` sets `loop.review`,
and a spec-reviewer that `/aide-spec-queue` spawns when you write a whole
queue's specs up front. Git commits are the durable checkpoint, so you can
stop and re-enter cleanly at any point.

### `git.mode` matters here

- **`auto-merge`** (default) — a green item merges straight to `main`.
- **`pr`** — a green item pushes its branch and stops for you to open the PR.
- **`local`** — no pushes at all (offline); merges locally.

Set it in `aide.toml` before a long run. Framework/process changes always want a
reviewed PR regardless (see `.aide/README.md` → Merge policy; in this repo,
[`../core/README.md`](../core/README.md)).

## 5. Unattended overnight runs (optional)

The framework relaunches nothing; use any scheduler you like, and a shell loop is
the minimum:

```
while true; do claude -p "/aide-run-roadmap"; sleep 300; done
```

Whatever runs it, read the adapter's
[`execution-surfaces.md`](../adapters/claude/execution-surfaces.md) first — it
holds the launch contract: a top-level print-mode session, permissions from the
committed allow-list only (a permission `ask` is **denied, not prompted**), and
never a skip-permissions flag. The folder must also have been trusted once
interactively.

## 6. Pulling framework updates

```
python install.py --into /path/to/your-repo --update
```

Re-copies the engine + adapter (framework-owned), leaves `aide.toml` and
`docs/aide/` (yours) untouched. Pin to a `VERSION` by running the installer from
that version's tag, and update deliberately;
`python install.py --into /path/to/your-repo --check` says whether you are behind
the checkout it runs from, without writing anything.
