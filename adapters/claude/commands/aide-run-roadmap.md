---
description: Drive the AIDE roadmap across MULTIPLE queues — plan a queue on its own branch behind a draft PR, stop for a human to review the plan, build it there (via /aide-run-queue), then stop again while that one PR is merged before planning the next.
---

# Run the AIDE roadmap (loop over queues)

The widest AIDE loop: iterate **over queues** across the whole roadmap. Where
`/aide-run-queue` runs the items *within one queue*, this command **generates
each queue and chains them** — create queue → run it → create the next → … —
until `docs/aide/roadmap.md` has no further stage to queue.

The **queue is the human checkpoint**, and each queue lives on its own branch,
`<prefix>queue-NNN`, which lands on `main` as **one** PR carrying the plan, any
specs and the built code. A person looks at it twice: the *plan*, before
anything is built against it — a human gate over the queue's items holds every
claim until they approve it — and the *finished batch*, when they merge the PR.
Items inside an approved queue flow freely (each merges into the queue branch,
no PR of its own), so the human reviews roughly once per ~10 items, not every
item.

**One session, one layer.** This session is the orchestrator: it drives the
current queue by loading `/aide-run-queue` **inline as a skill in this same
session** (which in turn loads `/aide-run-item` inline), and delegates only the
*leaf* work — item spec/tests/build/validate and queue *authoring* — to
**`Task` subagents** (`spec-author`, `test-writer`, `builder` or `builder-escalation`, `validator`,
`queue-planner`, and `reviewer` where `loop.review` turns it on). There is **no headless nesting**: the orchestrator never spawns
`claude -p` child processes. Each stop is a natural session boundary — the
loop pauses for the plan review and again for the merge, and the human
re-invokes after each, giving a fresh session per step.

**Command hygiene** applies to any git you issue — the shapes are delivered by
`.claude/rules/aide-command-hygiene.md` and stated canonically in
`.aide/conventions.md` §3. A `PreToolUse` hook
(`.claude/hooks/command_hygiene_guard.py`) enforces the mechanical ones.

## Orchestration model & session scope

- **Run the orchestrator on Sonnet.** Orchestration here is light dispatch and
  gating — spawn a subagent, read its short summary, decide the next step. The
  heavy cognition lives in the subagents, each on the model its agent spec
  pins. A slash command can't pin the session
  model, so if you're on Opus, `/model sonnet` before a long run.
- **All layers run inline in this one session; only leaf tasks are subagents.**
  `/aide-run-roadmap` → `/aide-run-queue` → `/aide-run-item` are loaded as skills
  in the *same* session (they are prompt expansions, not processes). The only
  parallel/isolated contexts are the `Task` subagents that do spec/test/build/
  validate/queue-authoring. This keeps orchestration state in one place and avoids
  the cold-start, stall, and cwd problems that killed the old headless design (see
  the post-mortem note below).

> **Historical note — the abandoned `--continuous` / headless-worktree design.**
> An earlier version offered a `--continuous` flag that ran the whole roadmap
> unattended by (a) spawning each layer as a nested headless `claude -p`
> subprocess and (b) isolating the loop in a dedicated git **worktree** that owned
> `main`. **Motivation:** drive the roadmap overnight without a human at each queue
> PR, bounding each layer's context by cold-starting a fresh process per queue/item.
> **Why it was removed:** on Windows the Bash tool **resets cwd to the repo root
> between calls**, so the "worktree owns `main`, `cd` in once" contract was
> impossible; headless `claude -p` children **cold-started, re-derived setup, and
> stalled on clarifying questions they couldn't answer** (a `-p` session can't be
> prompted); the 3-deep process nesting multiplied cold-start cost and failure
> points; and a parent-session death (usage-limit cutoff or restart) **lost the
> in-flight background subagent's state**. Net: it produced little reliable work.
> The single-session, git-commit-as-checkpoint model below is what replaced it —
> unattended long runs are instead a matter of relaunching this gated command
> from *outside* the framework (any scheduler; see `execution-surfaces.md` for
> the launch contract), with git commits + the resume logic below providing
> durable, restartable state.

## Determine current state first (resumable)

This loop spans sessions (it pauses for a plan review and for a merge), so
always start by working out where things stand, with the verbs rather than a
series of improvised git/gh probes:

1. `python .aide/scripts/aide.py sync` — the clean-tree preflight, before
   touching anything.
2. `python .aide/scripts/aide.py status` — branch + divergence, derived queue
   states, local branches (a queue branch is listed as one), human gates still
   blocking, and open PRs **best effort** (only where `gh` is installed and
   authenticated).
3. If a `<prefix>queue-NNN` branch exists — listed by `status`, or the head of
   an open PR — ask the forge what became of it:
   `gh pr view <prefix>queue-NNN --json number,state,isDraft`. The state is
   one of three: a queue branch whose PR is `MERGED` is done with; one whose
   PR is `CLOSED` without merging was rejected, and is never built on; one
   whose PR is `OPEN`, or that has no PR yet, is **open**. For an open one, `git switch` to it and `git pull`, and
   run `status` **again there**: the queue file, its items' states and its
   plan gate live on that branch only, so a `status` on `main` cannot see
   them. `python .aide/scripts/aide.py gate list` prints each gate's ID.

Read `docs/aide/roadmap.md`, `docs/aide/progress.md` and the queue files as
needed. What `aide` cannot tell you is the PR's state: that needs `gh`, and
without it say so and stop rather than guess. The loop runs **in-place in the
primary checkout** (see *Working in parallel* below if you need isolation).

| State | Action |
|---|---|
| **Roadmap exhausted** — no open queue branch, every stage ✅ / deferred / excluded | Report done. Stop. |
| **A queue branch's PR has merged** | `git switch` to `main`, `git pull`, then `python .aide/scripts/aide.py gc --merged` to preview and `--yes` to delete the landed branches (a squash-merged queue branch too: `--merged` compares content, not ancestry, where git is recent enough to measure it). Re-read the state on `main`. |
| **A queue branch's PR was closed without merging** | **Stop.** Say the PR was closed unmerged and ask the human whether the queue is abandoned (delete the branch and re-plan, via `/aide-feedback-loop` if the roadmap needs it) or the PR should be reopened. Never build on, approve for, or reopen a closed queue PR yourself. |
| **An open queue branch is built out** — its queue has no 📋/🚧 item left | Go to **Queue end**: mark the PR ready if it is still a draft, then **stop** — awaiting the human's merge. |
| **An open queue branch has 📋 items and its plan gate is still ⏳ Awaiting** (or ❌ Declined) | **Stop.** Tell the human to review the draft PR, and to approve the gate on that branch (see **Generate the next queue**); a declined one is re-planned, not approved. If the branch has no PR yet, open it as that section says first. |
| **An open queue branch has 📋 items and its plan gate is ✅ Approved** | Run the queue on its branch → go to **Run a queue**. |
| **A queue already on `main` still has 📋 items** — planned under the old flow, no queue branch | Run it from `main` as before → go to **Run a queue**, staying on `main`. |
| **Nothing open, and the roadmap has more stages** — or no queue exists yet | Generate the next queue → go to **Generate the next queue**. |

A queue branch that carries a maintenance queue and the stage queue after it is
one row: it is built out only when both are, and one gate holds both.

## Generate the next queue

Queue authoring is delegated to the **`queue-planner`** subagent — never
run `/aide-create-queue` inline in the orchestrator (it would pollute this
session's context and tie queue quality to the orchestration model). The planner
writes + commits `queue-NNN.md`, **tidies** the superseded `queue-(NNN-1).md`
and **raises the plan gate** on whatever branch it's on, then returns a
one-line summary. **You** (orchestrator) prepare the branch and handle push/PR
around it.

- **Triage the insight inbox first** — if `docs/aide/insights.md` has unchecked
  entries, run `/aide-review-insights` before planning. `defect`, `gap` and
  `automation` entries stay **open** through triage on purpose: the open inbox
  is an input to queue authoring, so the planner reads them with
  `insights list --open` and ticks the ones it queues. The queue's draft PR is
  where the human reviews both those and the ones it passed over.
- **Expect up to two queues from one create call.** When open `defect`, `gap` or
  `automation` entries exist, the planner writes a **maintenance queue** from
  those entries and the **stage queue** after it (`.aide/conventions.md`
  §1 → `insights-maintenance-queue.md`), numbered in that order. That is not two live queues: the live
  queue is the lowest-numbered open one, so the maintenance queue is executed
  first and the stage queue starts when it empties. Its summary says
  which queues it wrote; branch and PR on the **lower** number, and carry both
  queue files in the one PR — the split decision (what went to maintenance and
  what went to the stage) is only reviewable with both in front of the human.
- **Create the queue branch with the CLI**, off an up-to-date `main`
  (`git pull --rebase`): `python .aide/scripts/aide.py queue start NNN`. It
  builds the name, records the base, pushes it and leaves it checked out.
  Typing the name by hand risks a shape `aide claim` does not recognise, which
  silently retargets every item's merge at `main` instead of the queue branch.
- **Spawn `queue-planner`**: "Generate queue NNN on branch `aide/queue-NNN`;
  tidy the previous queue; consider the triaged insight candidates, splitting
  off a maintenance queue ahead of the stage queue if they warrant one; raise
  the plan-review gate over the new items; commit; do not push or PR." Wait
  for its summary, which names the gate's ID.
- `git push` the planner's commits — `queue start` pushed the branch when it
  was empty and set its upstream, so a bare `git push` is enough and no
  branch name is typed. Do this **before** `gh pr create`: with commits
  unpushed it prompts for where to push, and a prompt stalls an unattended
  run rather than failing loudly. Then open the queue's **draft PR**:
  `gh pr create --draft` titled `aide: work queue NNN`, body summarising the
  batch — the plan-gate ID, the inbox entries it absorbed and the ones it
  passed over, which the planner's summary names. If it wrote two queues, the
  title names the pair (`work queues NNN-NNN+1`) and the body says which is the
  maintenance queue and which the stage queue. `gh pr create` is on the `ask`
  list: an interactive session prompts, and an unattended one is refused
  without prompting — then report the exact command for the human to run.
  Nothing is lost either way: the gate row is already pushed, so nothing can
  be built against the plan until a person has looked at it.
- **STOP and tell the user**: review the draft PR — reshape the plan there if
  it needs it, and front-load the specs with `/aide-spec-queue NNN` if the
  batch warrants it, which commits them onto the same branch — then approve
  the gate **on the queue branch** and push it, so the approval travels in the
  PR as its record:
  `python .aide/scripts/aide.py gate approve <gate-ID>`, then `git push`.
  Re-invoke `/aide-run-roadmap` afterwards. **Never approve the gate
  yourself** (§1 → human gates): the decision it holds is the whole point of
  the stop.

## Run a queue

On the queue branch — `git switch <prefix>queue-NNN` if the state check left
you elsewhere — load **`/aide-run-queue NNN`** inline in this session and drive
it to empty. Claiming while the queue branch is checked out records it as each
item's base, so every item merges back into it (§4) and the batch still lands
as one PR. A legacy queue already on `main` runs from `main` instead. When it
reports the queue exhausted, go to **Queue end**; when it stopped for anything
else, surface that and stop (*When to stop and ask the user*, below).

## Queue end

The queue branch's PR is the second stop, and it carries the whole batch
once the branch is pushed — `aide merge` pushes it with each item it lands,
so run a bare `git push` only if `status` shows the branch ahead of its
upstream. Mark the PR ready for review: `gh pr ready <prefix>queue-NNN` — `ask`-gated like `gh pr create`,
and refused without prompting in an unattended run; report the command if so.
Then **STOP** and tell the user the batch is ready to review and merge. The
next queue is generated only after that PR merges, from an up-to-date `main`,
so each queue is reviewed against exactly what the one before it became. A
legacy queue run from `main` has no PR — loop straight on to **Generate the
next queue**.

## Tidy the previous queue

Tidying the now-superseded queue NNN-1 is the planner's step, not yours: it
runs `python .aide/scripts/aide.py queue tidy <NNN-1>`, which writes the
completion note, then reflects each item's final `progress.md` state so a stale
📋 list isn't left implying open work, and commits that alongside the new queue
on the `aide/queue-NNN` branch — which is branched from a `main` the previous
queue's PR has already landed on.

The shape of the stamp is `.aide/conventions.md` §1 → `queue-NNN.md`'s, and the
planner has that section preloaded — so the verb writes it and nobody types
one by hand. Ask for a tidy that did not happen; never for different wording.

## Working in parallel (optional worktree isolation)

The loop runs **in-place in the primary checkout** by default, which is correct
for a solo, sequential session. It switches branches constantly (`aide/NNN-*` →
the queue branch to merge → next), so if **you (the human) want to keep working in the repo
while the loop runs**, give the loop its own **git worktree** so your HEADs don't
collide:

- Create a sibling worktree that owns `main`: `git worktree add ../<project>-aide-loop main`,
  and keep **your** primary checkout on your own branch (git forbids `main` in two
  worktrees — that mutual exclusion is what prevents collisions).
- Give the worktree its **own venv** (`python .aide/scripts/aide.py env
  --bootstrap`, or a manual `python -m venv` + the `python.bootstrap` command from
  `aide.toml`) — an editable install otherwise resolves the project package to the
  primary `source_dir`, silently testing the wrong tree.
- Run the loop from the worktree. **Caveat:** the Bash tool resets cwd to the repo
  root between calls in this environment, so you cannot rely on a one-time `cd`;
  launch the loop *from* the worktree directory, or use `git -C <worktree>` /
  absolute paths. Remove it when done: `git worktree remove <path>`.

This is a manual convenience for genuine parallel work — not part of the automated
flow.

## If the human is unhappy with an auto-generated queue

The draft PR, while its plan gate is still ⏳, is the checkpoint to reshape a
batch *before* any code is built, so prefer editing the plan there — or decline
the gate (`aide gate decline <gate-ID> --reason "…"`) and re-plan. If items
were already built, run `/aide-feedback-loop`: adjust `vision.md`/`roadmap.md`/`progress.md` as
needed, and because merged work can't be cleanly un-merged, **identify which
already-implemented items need adapting and capture them as new corrective items**
in the next queue rather than rewriting history.

## When to stop and ask the user

- **Always, after opening each queue's draft PR** — the plan gate holds the
  build until a person approves it, and that pause is the whole point.
- **Always, at queue end** — the PR carries the whole batch, and the next queue
  waits for it to merge.
- **The state cannot be read** — `gh` is missing or unauthenticated, so
  whether a queue branch's PR is open, draft or merged is unknown.
- A queue or item needs an edit to a **framework/process** file (`vision.md`,
  `roadmap.md`, `aide.toml`, `.aide/**`, `CLAUDE.md`, `.claude/**`) — reviewed
  PR, never auto-merge.
- `/aide-run-queue` reports an item blocked, a PR/force-push need, or a
  build↔validate cycle that stopped (`/aide-run-item` step 6) — surface it and pause.
