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

From a clone of this framework repo:

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
`.aide-merge` diff is written for you to reconcile, then delete.

Commit the scaffold so the loop has a clean starting point.

## 2. Verify the install

From inside your repo:

```
python .aide/scripts/aide.py env      # venv present + import check (add --bootstrap to build it)
python .aide/scripts/aide.py check    # consistency gate over docs/aide/
```

`check` will report the living documents as missing — expected, you create them
next. (`env` is only relevant if your project uses a venv; set `[python]` in
`aide.toml`.)

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
the next item deterministically. Git commits are the durable checkpoint, so you can
stop and re-enter cleanly at any point.

### `git.mode` matters here

- **`auto-merge`** (default) — a green item merges straight to `main`.
- **`pr`** — a green item pushes its branch and stops for you to open the PR.
- **`local`** — no pushes at all (offline); merges locally.

Set it in `aide.toml` before a long run. Framework/process changes always want a
reviewed PR regardless (see [`../README.md`](../README.md) → Merge policy).

## 5. Unattended overnight runs (optional)

For runs longer than one sitting, the supervisor relaunches the gated command when
usage limits allow:

```
cp .aide/loop/loop.local.toml.example .aide/loop/loop.local.toml   # then edit caps
python .aide/loop/loop.py
```

With the Claude adapter, set `usage_probe = "anthropic-oauth"` in `loop.local.toml`
to gate on real usage; leave it `"none"` to relaunch on a plain time cadence. See
[`concepts.md`](concepts.md) → "The loop supervisor".

Before the first unattended run, read the adapter's
[`execution-surfaces.md`](../adapters/claude/execution-surfaces.md): the
supervisor launches a print-mode session in which a permission `ask` is
**denied, not prompted** — the committed allow-list must cover the whole run,
and the folder must have been trusted once interactively.

## 6. Pulling framework updates

```
python install.py --adapter claude --into /path/to/your-repo --update
```

Re-copies the engine + adapter (framework-owned), leaves `aide.toml` and
`docs/aide/` (yours) untouched. Pin to a `VERSION` and update deliberately.
