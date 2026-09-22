# Execution surfaces — where `/aide-*` runs, and what each surface guarantees

The same entry-points (`/aide-run-roadmap`, `/aide-run-queue`, …) can be
launched from three surfaces. They are **not** interchangeable: cwd behaviour,
permission handling, and session lifetime differ, and several past failures
(the abandoned `--continuous` design, Windows cwd resets) trace back to
assuming they were. This file is the single place those differences are
recorded. Cells marked **verify** are believed-but-unconfirmed on the current
Claude Code version — confirm before relying on them, and correct this table
when a divergence is observed (that correction is a `framework`-typed insight;
see the feedback loop).

## The matrix

| Concern | IDE extension chat | CLI interactive (`claude`) | Unattended (`claude -p …`, launched by a scheduler) |
|---|---|---|---|
| Session lifetime | until the chat/window closes | until the user exits | **exits when the prompt completes** — this is why an unattended launch must use `-p`; an interactive child never returns control, so whatever started it never gets to start the next one |
| cwd between Bash calls | resets to the workspace root on Windows | resets to the repo root on Windows | same as CLI |
| Settings resolution | `.claude/settings.json` + `settings.local.json` + user settings *(verify: extension-specific overrides)* | same project + user settings files | same files; **only** the committed allow-list matters in practice (see below) |
| Permission `ask` | interactive prompt in the panel | interactive prompt in the terminal | **denied without prompting** — a `-p` session cannot ask |
| Trusted-folder prompt | one-time prompt on first open *(verify)* | one-time prompt on first launch in a new directory | blocks the first run if the folder was never trusted — trust it once interactively before the first unattended run |
| Hooks (`PreToolUse` etc.) | run | run | run |
| Model selection | UI model picker; `/model` | `/model`, `--model` flag | `--model` flag only; `/model` inside the prompt text works *(verify)* |
| `Task` subagents / skill expansion | available | available | available *(verify: parity of nested skill expansion depth)* |
| Clarifying questions to the human | possible | possible | **impossible** — anything that would ask, stalls or is skipped; `loop.clarify = "assume"` is mandatory for unattended runs |

## The unattended posture (normative)

- **The committed `.claude/settings.json` allow-list *is* the orchestrator's
  permission grant.** An unattended run must need nothing beyond it. Every
  denial in an unattended run is a *gap in the allow-list*, to be fixed through
  the existing loop: permission events are logged to `docs/aide/permissions/`,
  `/aide-review-permissions` ranks them, safe recurring ones get promoted via a
  reviewed PR.
- **Never** `--dangerously-skip-permissions`, in a scheduler's launch command
  or anywhere else — it converts the permission model from a contract into a
  bypass, and one bad generated command can then do anything.
- **The launch command is `claude -p "/aide-run-roadmap"`**, top-level, with only
  flags that *narrow* behaviour added (e.g. `--model`). The framework relaunches
  nothing of its own (`../../docs/vision.md` → *Not a scheduler*), so this line is
  the contract whatever runs it — cron, a systemd timer, or the minimum, a shell
  loop:

  ```
  while true; do claude -p "/aide-run-roadmap"; sleep 300; done
  ```

- Before the **first** unattended run on a fresh clone/machine: launch `claude`
  once interactively in the repo to answer the trusted-folder prompt, and run
  `python .aide/scripts/aide.py check` — an unattended pass should never be the
  first thing to touch a virgin checkout.

## Known divergences and their standing workarounds

- **Windows cwd reset** — the Bash tool resets cwd between calls on every
  surface; never rely on a one-time `cd` (this killed the worktree-owns-`main`
  design; see `/aide-run-roadmap` → historical note). Use repo-root-relative
  paths or `git -C`.
- **No nested headless children** — the orchestrator runs everything inline in
  one session and spawns only `Task` subagents. The scheduler's own top-level
  `-p` launch is the *only* headless process in the system.
- **IDE-vs-CLI behavioural drift** — when a `/aide-*` command behaves
  differently in the extension than in the CLI, record it here with the
  version observed. If it is Claude-product behaviour rather than an AIDE bug,
  it becomes a `framework`-typed insight (feedback loop) → upstream issue or a
  documented workaround in this table.
