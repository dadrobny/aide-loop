# Improvement strategy — friction observations → work items

> Status: WI-1…WI-7 implemented on `feat/improvement-strategy-wi` (one commit
> per WI, awaiting review); the `.aide-merge` auto-reconcile (WI-7g) remains
> planned. · Created: 2026-07-18 · Updated: 2026-07-19
> Input: a collected list of friction points from real automated-development
> runs, plus field feedback from a consumer repo (SegQC+xnat → WI-7).
> Output: seven work items, each bundling related observations, with a
> proposed direction, concrete steps, affected surfaces, and open questions.
> Framework/process changes land via reviewed PRs (see README → Merge policy).

## How the observations map to work items

| Observation | Work item |
|---|---|
| Scripts scan for status icons; doc writers must avoid them | WI-1 |
| Queue creator sets status Live; flip on first claim; does a queue need status at all? | WI-2 |
| Claiming could span across queues (branches signal "in progress") | WI-2 |
| Stale local/remote branches left after merge | WI-3 |
| Repeated git status/branch checks, work on stale branches without fetching | WI-3 |
| Move from agent-driven to deterministic code where possible | WI-3 (concrete now) + WI-4 (ongoing process) |
| Compound engineering: capture out-of-scope insights, route them | WI-4 |
| Feedback loop: project work vs framework work, funnel to framework repo | WI-4 |
| Testing vs validation: is the code doing something *meaningful*? | WI-5 |
| Validation may need specific setups (GPU, datasets) | WI-5 |
| VSCode plugin vs CLI divergence for `/aide-run-*`; orchestrator default permissions | WI-6 |

No 1-to-1 mapping: the queue-status and cross-queue-claim points are one design
question (WI-2); the git observations split into "codify now" (WI-3) and "build
the process that keeps finding such candidates" (WI-4).

Suggested order: **WI-1 and WI-3 first** (small, immediate payoff, no design
risk), **WI-2 and WI-6 next** (contained design changes), **WI-4 and WI-5**
last (they add process surface and deserve the most review).

---

## WI-1 — Make the format contract robust to prose, not the other way round

**Friction.** `aide.py` and `aide_status_report.py` scan for the five status
icons (`conventions.md` §1). Any 📋/✅/… appearing in *free prose* — a queue
item description, a vision paragraph, an item spec — risks being parsed as
status. Today the burden is on every document author (human and agent) to
avoid the icons anywhere unstructured. That is an invisible landmine and the
wrong default: parsers should be positionally strict so prose is free.

**Direction.** Tighten every icon-consuming parser to *structural positions
only*, then add a lint so accidental ambiguity is caught, not silently
misread.

**Steps.**
1. Audit every icon read in `core/scripts/aide.py` (`_icon_status`,
   `stage_deliverable_statuses`, `_parse_item_status`, summary-table handling)
   and in the status-report generator. For each, pin the match to its
   structural anchor: table rows (`| … |` with the expected column count),
   `## Stage N — … — <icon>` headers, and Deliverables bullets matching
   `- <icon> … *(Item NNN)*`. An icon anywhere else is never status.
2. Add an `aide check` **warning** (not error) for status icons found outside
   structural positions in `docs/aide/**` — surfaces near-misses without
   blocking authors who legitimately want an emoji in prose.
3. Update `conventions.md` §1 with one new sentence stating the guarantee
   ("icons are status only in these positions; elsewhere they are plain
   text") and drop any "avoid icons in prose" guidance from templates/skills —
   the guarantee replaces the discipline.
4. Regression tests in `core/scripts/tests/`: a fixture progress/queue file
   with decoy icons in prose must parse identically with and without them.

**Affected.** `core/scripts/aide.py`, `core/conventions.md`, templates,
`scripts/aide_status_report.py` (project-owned — document the same rule in the
status-report skill), tests.

---

## WI-2 — Derive queue state instead of declaring it

**Friction.** The queue creator writes `> **Status:** Live` at creation time,
before any item is touched — so "Live" conflates "newest" with "being worked".
The suggestion to flip status when the first item is claimed treats the
symptom; the real question raised is the right one: **does a queue need a
status field at all?** "In progress" is already signalled by claim branches
(`conventions.md` §2), and item availability is governed by dependencies —
which could even span queues.

**Direction.** Make queue state *derived, not declared*. A queue file carries
only its number and creation date; `aide.py` computes its state from
`progress.md` + the queue's item list:

- **open** — has items whose status is 📋/🚧
- **done** — every item ✅/⏸️/❌

"Live" (for `aide claim`'s default pick and the status report) becomes *the
lowest-numbered open queue* — a query, not a field. `aide queue tidy` stops
rewriting status lines and instead (optionally) stamps a human-readable
completion note, which nothing parses.

**Steps.**
1. Add derived-state functions to `aide.py`; switch `_live_queue_text`,
   `check`, and `queue tidy` to them. Keep reading the old status line for one
   version (deprecation window) so existing installs don't break.
2. Simplify `core/templates/queue.md` (drop the Status slot) and the
   create-queue skill (drop requirement 6 and most of the tidy step — the
   remaining tidy work is the human-facing note).
3. **Cross-queue claiming (second phase, behind a config flag).** Let
   `aide claim` consider all open queues in number order rather than only the
   live one — dependencies and claim branches already prevent conflicts. Flag
   it (`loop.claim_scope = "live-queue" | "all-open"`) because the current
   one-queue scope is also the human-checkpoint boundary; spanning queues
   weakens "a queue = one reviewed batch" and should be a deliberate opt-in.
4. Update `concepts.md` / `conventions.md`: the claim protocol section becomes
   the single statement of "in progress"; queue files are inert item lists.

**Open question for review.** Is the exactly-one-Live invariant doing any work
today beyond parsing convenience? (From the code: no — `check` enforces it,
`claim` consumes it, nothing else. Deriving it removes a whole class of
tidy/flip bookkeeping the creator and orchestrator currently carry.)

**Affected.** `core/scripts/aide.py`, `core/templates/queue.md`,
`adapters/claude/skills/aide-create-queue/SKILL.md`, `aide-run-roadmap.md`
(tidy section), `conventions.md`, `concepts.md`, tests.

---

## WI-3 — Codify the git workflow: preflight and garbage collection

**Friction.** Two recurring, fully deterministic failure patterns:
(a) work starts on a stale branch because nobody fetched, after several
exploratory `git status`/`git branch` calls that each cost a turn; (b) merged
branches linger locally and remotely — `aide merge` deletes its own branch,
but `pr`-mode merges, human merges, and abandoned claims leak, and `aide
check` only *flags* stale claims.

**Direction.** Two new CLI verbs, then *make the skills use them* so agents
stop free-styling git.

**Steps.**
1. **`aide sync`** (preflight): `fetch --all --prune`, verify clean tree,
   report current branch vs `origin/main` divergence, and — given an item
   number — verify the checkout is that item's claim branch, up to date with
   its remote. One call replaces the 3–5 git calls every role currently
   improvises. Exit non-zero with a one-line reason when work must not start.
2. **`aide gc`**: delete local and remote claim branches whose item is ✅ in
   `progress.md` (the check `aide check` already knows how to make), plus
   `--merged` for branches merged into main. Dry-run by default, `--yes` to
   act — deletion is the one destructive verb in the CLI, so it stays
   explicit. Wire a `gc` call into `aide merge` (own-branch case already
   handled) and into the run-queue orchestrator's queue-completion step.
3. **Force adoption through the skills**: rewrite the git preambles in
   `aide-execute-item`, the three `aide-run-*` commands, and the role agents
   to a single line — "run `aide sync [--item NNN]`; do not run exploratory
   git" — and extend the command-hygiene primer (`conventions.md` §3) with the
   principle: *if an `aide` verb covers it, the raw git form is wrong*. The
   Claude hook can nudge (map `git fetch`/`git status` at session start to a
   "use `aide sync`" hint) but prose-first is enough to start.
4. Tests in `test_aide_git.py` for both verbs (temp-repo fixtures exist).

**Affected.** `core/scripts/aide.py`, `core/conventions.md` §3, claude skills
+ commands + agents, optionally `command_hygiene_guard.py`, tests.

---

## WI-4 — Compound engineering: an insight pipeline with routed destinations

**Friction.** Three observations are one missing mechanism:
- Agents gain insights out of scope for their current item (a repeated manual
  action, a doc gap, a latent bug) and today the only options are "act out of
  scope" or "drop it".
- The feedback loop conflates *project* refinement with *framework (AIDE)*
  refinement; framework work should funnel to the framework's own repo.
- The most valuable insight class — "this recurring agent behaviour could be
  deterministic code" — is exactly how WI-3 was found, by a human. The loop
  should surface these itself.

**Direction.** A lightweight **insight inbox** with typed entries, cheap to
write at the moment of discovery, triaged deterministically later. Capture is
in-band (any role, any time); routing is a batch step at the queue boundary,
where a human is present anyway.

**Steps.**
1. **Capture format.** `docs/aide/insights.md`, append-only bullets:
   `- [ ] <type> — <one line> *(item NNN, YYYY-MM-DD)*` with types
   `knowledge` (document it), `defect` (fix it), `gap` (plan it),
   `automation` (script it — the WI-3 pattern), `framework` (belongs to AIDE
   itself). One file, not a directory: append-only merges cleanly and stays
   greppable. `aide check` validates the line shape only.
2. **Capture instruction.** One short paragraph added to every role agent and
   the execute-item skill: "if you learn something true beyond this item's
   scope, append one line to the inbox and continue — never act on it".
   The strict-scope rule the roles already have becomes *enforceable* because
   there is finally somewhere for the out-of-scope thing to go.
3. **Triage step.** Extend `aide-feedback-loop` (and add it as a standing step
   in `aide-run-roadmap`'s generate-next-queue phase, before the queue PR):
   read unchecked entries, then route — `knowledge` → the relevant living doc
   or CLAUDE.md; `defect`/`gap` → candidate items for the queue being
   authored, so the queue PR reviews them; `automation` → a candidate item to
   add a CLI verb/script + the skill edit that mandates it; `framework` → see
   step 4. Tick entries off with a pointer to where they landed.
4. **Framework funnel.** New config `[framework] repo = "<owner>/aide-loop"` in
   `aide.toml` (written by `install.py`). Triage turns `framework` insights
   into `gh issue create --repo <that>` with a templated body (project,
   observation, proposal). `gh` is already the adapter's GitHub surface and an
   issue is the right handover artifact: no clone/branch needed from the host
   project, and the framework repo's own AIDE loop can consume its issues as
   roadmap input. Degrade gracefully: no `gh`/no network → leave the entry
   unticked with a "pending handover" note.
5. **Close the loop on `automation` insights** by pointing at WI-3 as the
   worked example in the feedback-loop skill: identify → script in `aide.py`
   (or project `scripts/`) → force via skill prose → hygiene rule.

**Open question for review.** Should triage run per-item (validator appends a
"insights?" check) rather than per-queue? Recommendation: capture per-item is
already allowed; *triage* per-queue keeps the batch-checkpoint rhythm and
avoids adding a fixed cost to every item.

**Affected.** New `docs/aide/insights.md` convention (`conventions.md` §1,
template), all five role agents, `aide-execute-item`, `aide-feedback-loop`,
`aide-run-roadmap`, `aide.toml` + `install.py`, `aide check`.

---

## WI-5 — Validation as a first-class stage gate, distinct from testing

**Friction.** Unit tests pass ≠ the software does something meaningful. The
validator today gates on acceptance criteria + tests, which inherits the
spec's blind spots. Meaningful evaluation may need real environments (GPU,
mounted datasets, external services) that the loop's machine lacks — the
existing **Environment-Gated Capability Verification** table (`conventions.md`
§1) already records *that* gap honestly but nothing *plans* the verification.

**Direction.** Separate three levels and give each a home: **tests** (per
item, exists), **item validation** (does the change behave meaningfully —
strengthen the validator's mandate), **stage validation** (do the use cases
work end-to-end — new, planned as explicit queue items).

**Steps.**
1. **Item template**: add an optional `## Validation` section — "how to
   observe this working beyond the tests" (a command to run, output to
   inspect, a dataset slice to process). Spec-author fills it when
   meaningful; validator must execute it, not just re-run pytest. This is the
   compound of the spec-author's use-case knowledge at the moment it is
   freshest.
2. **Stage-validation items**: extend the create-queue skill — when a queue
   closes a roadmap stage, the queue **must** contain a final
   `Validate stage N` item whose spec exercises the stage's use cases
   end-to-end and flips the relevant Environment-Gated Capability rows to
   ✅ Verified where the environment allows. This makes validation *planned
   work with a number*, not a hope.
3. **Environment profiles**: `[validation]` section in `aide.toml` declaring
   named requirements (`gpu = "torch.cuda.is_available()"`,
   `dataset = "path exists …"`). `aide env --profile <name>` evaluates them
   deterministically; a stage-validation item states which profile it needs,
   and the validator downgrades honestly to "❓ Unverified — needs <profile>"
   when the host lacks it (never a silent pass — same honesty principle as
   the capability table). CI matrix runners (the new Linux/Windows workflow)
   can carry profiles the dev machine lacks.
4. **Vision linkage**: roadmap/vision templates gain a hint that objectives
   phrased as *use cases* are what stage-validation items replay — aligning
   with "might align with use cases defined".

**Affected.** `core/templates/item.md` + `queue.md` guidance,
`aide-create-queue`, `aide-create-item`, `validator.md`, `aide.py env`,
`aide.toml` schema, `conventions.md` §1 (capability table gains its planned
producer).

---

## WI-6 — One documented execution surface: plugin vs CLI parity and orchestrator permissions

**Friction.** The same `/aide-run-*` entry-points behave differently launched
from the VSCode extension vs `claude` CLI (which is what `loop.py` execs:
`claude "/aide-run-roadmap"`). Separately, the orchestrator's default
permission posture is undefined — unattended runs stall on prompts or,
worse, get run with blanket permission bypasses; "trusted folder" state adds
another variable.

**Direction.** Investigate first, then pin down a single documented contract:
what the supported launch surfaces are, what each guarantees, and what the
unattended posture is. This is adapter territory (`adapters/claude/`), not
engine.

**Steps.**
1. **Divergence matrix (investigation deliverable).** For each surface — IDE
   extension chat, terminal CLI interactive, `claude "/cmd"` as `loop.py`
   spawns it — record: cwd behaviour, settings resolution order
   (`settings.json` vs `settings.local.json` vs trusted-folder prompts), hook
   execution, model selection, whether `Task` subagents and skill expansion
   behave identically, and what happens at a permission `ask`. Commit as
   `adapters/claude/execution-surfaces.md`. (Several past scars —
   Windows cwd resets, the abandoned headless design — are already noted in
   `aide-run-roadmap.md`; this consolidates them into one testable table.)
2. **Define the unattended posture.** The stance to validate: the committed
   `settings.json` allow-list *is* the orchestrator's permission grant —
   unattended runs must need nothing beyond it, and every stall is a gap to
   fix via the existing `/aide-review-permissions` loop, never via
   `--dangerously-skip-permissions`. Encode the chosen launch flags
   (`--permission-mode`, model pin, non-interactive expectations) in
   `loop.py`'s default command / `loop.local.toml.example` so the supervisor
   launches the *same contract* a human launches.
3. **Trusted-folder handling.** Document (and where possible pre-empt in
   `install.py` output) the one-time trust prompt so a fresh clone's first
   unattended run doesn't hang on it.
4. **Feed WI-4**: divergences that are Claude-product behaviour rather than
   AIDE bugs become `framework`-typed insights → issues upstream or
   documented workarounds in the matrix.

**Affected.** `adapters/claude/README.md` + new `execution-surfaces.md`,
`core/loop/loop.py` defaults, `loop.local.toml.example`, `install.py`
messaging.

---

## WI-7 — Field feedback from a consumer repo (SegQC+xnat)

First real consumer-run feedback — exactly the artifact the WI-4 inbox is
designed to carry (every entry below would have been an `insights.md` line).
All recurred; none were one-offs.

**Code defects (all fixed):**

- **(a) `aide merge` claimed branch deletion it never verified.** 3/3 items
  printed "deleted" while the local branch survived (`-d` refuses when
  `pull --rebase` rewrote main so the tip is no longer an ancestor). Fixed:
  delete result is checked, escalates to `-D` (safe — this process just merged
  the branch), the remote delete is verified too, and failure prints an honest
  message pointing at `aide gc` instead of a false success.
- **(b) Status icons crashed `aide.py` on non-UTF-8 Windows consoles**
  (cp1252 → `UnicodeEncodeError`, command dies instead of reporting). Fixed:
  `stream.reconfigure(encoding="utf-8", errors="replace")` once at `main()`
  entry — no more per-call `PYTHONIOENCODING` dance.
- **(c) Hygiene-guard rule 4 checked the raw command** while rules 1–3/5 check
  the quote-blanked one, so literal `$(...)` *prose* in a commit message was
  blocked as real substitution. Fixed quote-aware: single-quoted spans are
  prose (bash keeps them literal); unquoted **and double-quoted** `$(`/backtick
  still flag, because bash substitutes inside double quotes.
- **(d) `progress set` hard-failed on a missing `*(Item NNN)*` back-fill**,
  making two builders hand-patch `progress.md`. The queue-planner back-fill
  (create-queue req. 8) evidently isn't reliable, so the CLI now
  **self-heals**: it inserts the deliverable bullet from the item spec's own
  Stage/title header when unambiguous, and only hard-errors when no spec/stage
  context exists.
- **(e) No escape hatch for the documented framework-update workflow**, which
  structurally needs `git -C` into a second repo. Fixed: `[framework]
  local_path` in `aide.toml` declares that clone; the guard exempts `git -C
  <that path>` only — everything else stays blocked.

**Instruction gaps (fixed in agent definitions, not dispatch prompts):**

- **(f) Validator stalls on background test runs** (~1.5 h Monitor stall,
  likely a permission prompt): `validator.md` now mandates a synchronous
  foreground pytest, never background/Monitor.
- **(g) Round-1 validation failures dominated by stale-test assertions** when
  a spec intentionally changes an existing default: `spec-author` now sweeps
  `tests_dir` for tests pinning the old behaviour and lists them in the spec;
  `test-writer` reconciles exactly those in the same pass (its one sanctioned
  edit to pre-existing tests). Kills the guaranteed extra validation round.
- The orchestrator's own hygiene lapses (`;`-chained calls) were masked by
  the broken guard — (c) fixing the guard re-arms enforcement for the main
  thread too; no further change needed.

**Automation opportunities:**

- **`aide status` (implemented)** — one call replacing the several git/gh
  round-trips of roadmap-state discovery on re-invocation: branch +
  divergence, derived queue states with open items, claim branches (stale
  flagged), open PRs best-effort.
- **`.aide-merge` auto-reconciliation (planned, not yet implemented)** — most
  of a settings reconcile is mechanical (framework version wins except
  project-pinned lines). Direction: an `aide.toml` list of pinned JSON paths
  (e.g. the `Edit`/`Write` scoping globs) that `install.py` preserves,
  auto-applying everything else and leaving a diff only for genuine conflicts.
  Deserves its own small PR against `install.py` + adapter README.

## What this strategy deliberately does not do

- **No status flip-on-claim for queues** (the original suggestion): WI-2's
  derived state supersedes it — flipping a declared field on first claim adds
  a write that can be missed; deriving removes the field.
- **No per-item human gates for validation**: WI-5 keeps the human at the
  queue boundary; meaning is checked by planned items, not more pauses.
- **No new agent roles**: every WI lands as CLI verbs, template/skill edits,
  or documents. This is the framework's own principle applied to itself —
  deterministic work into `aide.py`, judgment stays where it is.
