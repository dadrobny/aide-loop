# Changelog

All notable changes to the AIDE framework. The version here is `core/VERSION`,
which the installer copies into a consumer as `.aide/VERSION` — that file is what
a consumer compares against to learn it is outdated
(`python install.py --into <repo> --check`).

**Bump policy** — see [README](README.md#versioning). Any commit touching `core/`
or `adapters/` bumps `core/VERSION`, because that is exactly what `--update`
copies into a consumer; docs-only and repo-test-only commits do not. The rule is
enforced by `tests/test_repo_versioning.py`, not by memory.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [SemVer](https://semver.org/spec/v2.0.0.html), where the "API" is what
a consumer installs — the document formats, the `aide` CLI surface, `aide.toml`
keys, and the adapter's agents/skills/commands.

## Installer (unversioned)

_`install.py` is **not** part of what a consumer installs — it is what does the
installing — so a change to it alone moves no `core/VERSION` and has no release
to sit under. These entries have shipped: a consumer picks them up by pulling
this repository, not through `--update`, which is why each one closes by saying
the version is deliberately unmoved. Newest first, like the releases below.
Anything touching `core/` or `adapters/` belongs in a versioned section
instead — that is the bump policy above, and it is enforced by
`tests/test_repo_versioning.py`._

### Added

- **The managed `.gitignore` block carries an adapter-contributed section, and
  the Claude adapter's is `.claude/worktrees/` (issue #165).** Claude Code's
  `/code-review` checks the repository out under `.claude/worktrees/` to
  review a diff and leaves the scratch checkout behind; `aide sync` refuses
  on any untracked path, so an unattended run stalled on a sibling tool's
  scratch space with nothing in the message naming the cause. The consumer
  repaired it in its own `.gitignore` — a per-consumer fix for a condition
  every consumer of the adapter can reach. The block stays one file for every
  runtime: the engine's lines are runtime-agnostic, and the installer appends
  the lines of the adapter it is installing (`ADAPTER_GITIGNORE_LINES` in
  `install.py`), so the adapter path never enters the cross-runtime list and
  the cleanliness check keeps the one property that makes it worth having,
  that it is unconditional. The reconcile on `--update` carries the line to
  every existing consumer. Installer-only: nothing a consumer's `--update`
  copies changed *for this entry* — it shipped beside 1.39.0, whose bump is
  for the engine changes listed there, not for this one.

- **`install.py --check` names contract text a consumer restates in its own
  instruction file (issue #96).** The installer maintains one line in that file
  — the `@.aide/AGENT-CONTEXT.md` import — and reads it for nothing else, which
  leaves every other line project-owned and unmaintainable by any framework
  pass. That is the right ownership and the wrong outcome when those lines are
  a *copy* of contract text the engine ships: one consumer's `CLAUDE.md`
  carries the insight protocol, the durable-artifacts rules and the §4 mode
  table by hand, with three engine releases narrated into the prose after the
  fact, because nothing could see it. `--check` now compares the declared
  instruction file against the shipped contract — `AGENT-CONTEXT.md`,
  `conventions.md` and its sections, and `README.md`, which is where the
  shared-vs-personal ownership rules #96 cites as evidence actually live — and
  names each passage that repeats it: one line per *section* of the file, with
  the line number and the shipped file it duplicates, ordered as the file
  reads, capped at six once there are more than seven. A section is identified
  by where it is rather than by its title, so two sections sharing a heading
  stay two findings. The signal is a ten-word run of normalised prose, or a
  contract heading of three words or more lifted whole (the drift case, where
  the body has been reworded past any shared run); fenced code — both markers,
  indented up to three spaces — is compared on neither side, since copying a
  command is what a command is for. **Advisory, and deliberately outside every
  exit code** — the file is the project's, so the framework's standing ends at
  saying what it found; seeding contract text into a project-owned file would
  be the same trade with the drift hidden. The two repairs are in the report:
  prune what the shipped contract already covers, and move upstream anything
  it turns out to lack. A newly created instruction file now says so in its
  note; README gains "What belongs in the instruction file" for repos adopting
  the import after the fact, which the report points at by naming the framework
  checkout it ran from, since a consumer's own `.aide/README.md` has no such
  section; and ADAPTER-SPEC §7 states the check and its advisory status.
  Installer-only: nothing a consumer's `--update` copies changed, so
  `core/VERSION` is unmoved.

- **`install.py` retires adapter files the framework has dropped (issue #85,
  step 1).** `copy_tree` overwrites and adds but never deletes, and the prune
  covers `.aide/` only, so a file removed from `adapters/claude/` stayed live
  in every consumer after `--update` — still armed, still delivered — while
  `--check` reported "up to date". The control directories cannot simply be
  pruned against the source: `.claude/agents/`, `skills/` and `rules/` are
  directories a project legitimately adds its own files to. The installer
  now records what it wrote there in `.aide/adapter-manifest.txt` (one
  consumer-relative POSIX path per line, sorted, LF, no BOM), reads it back
  before the next copy, and removes every recorded file the adapter no longer
  ships — reported the way the engine prune is, tolerated the same way when a
  file cannot be removed, and previewed by `--check`, which names each such
  file, exits 1 and writes nothing. A file the installer never wrote is never
  in the manifest, so a consumer's own skill or rule beside the framework's is
  never a candidate. Consumers installed before this release have no manifest;
  `RETIRED_ADAPTER_PATHS` in `install.py` lists, per adapter, the paths earlier
  releases shipped and later dropped, and is consulted alongside the manifest
  so those consumers catch up on their first `--update`. 1.27.0 populates it with the two
  `paths:`-scoped rules the carrier swap retired. Manifest lines are validated against `HISTORIC_CONTROL_DIRS`
  — every control directory the installer has ever written — so a
  directory retired whole is still emptied file by file rather than left
  armed because its name is no longer in `ADAPTER_CONTROL`. The manifest is written after the retirement and before
  `.aide/VERSION`, so a failed update keeps the old manifest and the dropped
  files stay retirable on the re-run. Installer-only: nothing a consumer's
  `--update` copies changed, so `core/VERSION` is unmoved.

### Fixed

- **`install.py` now writes `.aide/VERSION` last, not first (issue #80).** It
  used to land in step 1 as part of the engine copy, so every later step — the
  adapter control files, `settings.json`, the usage probe, the context import,
  `.gitignore`, the prune — ran after the consumer was already marked as the
  new version. Any failure in between (a permission error, a malformed
  `settings.overlay.json`, a full disk, an interrupt) left a half-applied
  install that `--check` reported as up to date; the #79 review reproduced
  exactly that. The engine copy now defers `VERSION` and a final step writes
  it after everything else has succeeded, so a failed first install leaves no
  `VERSION` (`--check` exits 2 and says the install did not finish, rather
  than "no install found" over a directory full of engine files) and a failed
  update leaves the old one (`--check` says behind; `--update` remains the
  repair). Installer-only: nothing a consumer's `--update` copies changed, so
  `core/VERSION` is unmoved.

## [1.45.0] — 2026-09-09

The bookkeeping committer promised a rebase git would never perform. Now the
commit lands first and the rebase after it is real.

### Changed

- **`_commit_docs_files` commits first and rebases onto origin afterwards
  (issue #180).** The shared committer behind `progress set`, `insights
  tick` and `insights archive` ran `git pull --rebase` *before* committing,
  over an edit every caller had already written to the worktree — and git
  refuses to start a rebase over an unstaged change (exit 128, no marker), so
  in the ordinary path the pull never ran, the tick stayed local, and two
  machines editing the same inbox diverged until one was rejected at push.
  The order is reversed: the pathspec commit lands, the tree is then clean in
  the common case, and `git pull --rebase` replays that one commit onto the
  upstream — so a tick on one machine converges with the other's before any
  push. A collision now stops **inside** the rebase, with a marker, which is
  the state 1.44.0 taught the engine to see: the verb says the commit exists
  here, that replaying it onto origin stopped, and — when the inbox is what
  stopped it — names `aide insights resolve` and `git rebase --continue` as
  the way out, the same route `aide merge` offers. No `--autostash`: a
  stash-pop conflict leaves conflict markers with no operation in progress,
  which nothing in the engine detects and `insights resolve` cannot read.
- **Three shapes the pull deliberately leaves alone, each stated.** Under
  `git.mode = "local"`, or with no `origin`, there is no rebase at all — the
  other pull sites already skip it there, and a notice about missing tracking
  information on every tick of a local-mode consumer would be noise about a
  remote the mode says does not exist. A `HEAD` carrying a merge commit origin
  has not seen is never rebased by a bookkeeping verb, for the reason 1.31.1
  gave `aide merge` (issue #133): the rebase drops the merge and replays both
  parents, and `aide merge` itself reaches this committer with exactly that
  commit on `HEAD`, having integrated origin a moment earlier — so the skip is
  silent there by design. And a pull that comes back non-zero with the tree
  untouched — unstaged changes beside the tick, an unreachable origin, a
  branch with no upstream — is a **notice**, not a refusal: the commit is
  complete and local, and the message says it was not rebased and why, so the
  docstring's promise is either kept or visibly not.
- **The already-stopped tree is refused before the commit, not after a pull
  that could not start.** 1.44.0 caught a repository already mid-rebase as a
  side effect of the pull refusing over it; with the pull moved behind the
  commit that side effect is gone, so the committer now asks
  `_interrupted_op` first and refuses with the same sentence — "stopped in an
  earlier operation — a cherry-pick is in progress", the matching continue
  and abort, the inbox hint when it applies. It matters because git accepts a
  commit mid-rebase once the conflicts are staged, and a bookkeeping commit
  in the middle of someone's rebase is the state this exists to prevent. The
  sentence is built once, in `_stopped_state`, and shared with
  `_stalled_pull`.

## [1.44.0] — 2026-09-09

Three of the engine's `git pull --rebase` calls threw away their return value,
so a rebase that stopped on a conflict was invisible at the one moment the
repository stopped being what the next command assumed.

### Fixed

- **A stopped rebase is a sentence, not a silent state (issue #178).**
  `cmd_merge`, `cmd_sync` and `_commit_docs_files` each ran `git pull --rebase`
  with `check=False` and never looked at the result. A rebase that stops on a
  conflict returns non-zero and leaves the repository mid-rebase, and all three
  then continued into an operation that cannot run over one. `aide merge` was
  the sharpest: `git merge` refuses outright while a rebase is in progress, so
  the operator read the **merge's** failure for a stall the pull had caused, on
  a base branch left in a state neither message described. Now each site asks
  whether the pull left an operation in progress and stops with a message that
  names it — `aide merge` before it touches the merge, with the item explicitly
  not ticked and the work named on its branch; `aide sync` as the refusal a
  preflight exists to produce, in place of the `tree clean` line it used to
  print over a conflicted index; and the shared committer behind `progress
  set`, `insights tick` and `insights archive` as a returned reason that is
  also printed, because all three of those callers discard it. Where the
  unmerged path is the inbox, the stall names `aide insights resolve`, so the
  same route out is offered here as from `aide merge` (1.43.0).
- **The message names the operation git reports, never an assumed rebase.**
  The pull is not always what stopped: it also refuses because an *earlier*
  operation is still in progress, and at the shared-committer site that is the
  reachable case rather than the exotic one. So the sentence is "git pull
  --rebase could not complete — a cherry-pick is in progress", and the abort it
  offers is derived from the marker the same way the continue command already
  was — `git rebase --abort` inside a cherry-pick is not merely unhelpful, it
  fails.
- **The discriminator is the state, not the exit code.** `git pull --rebase`
  also returns non-zero when it never started — no upstream for this branch, an
  unreachable origin, a refused fetch — and those have always been tolerated
  here, correctly: the local operation that follows is still right, and
  refusing on them would stall an unattended run over a missing remote. Only a
  pull that left a `rebase-merge`/`rebase-apply` (or merge, cherry-pick, revert)
  marker behind is a refusal. `aide sync` is the one exception to the silence:
  it now says when the claim branch was **not** refreshed and why, because its
  success line claims the remotes were fetched, and still exits 0 because the
  branch is clean and work can start.
- **`_commit_docs_files`'s docstring no longer promises more than git
  delivers.** It said the pull "rebases onto the upstream first, which is right
  for an edit to a file other machines also edit (a tick, an archive)" — but
  every caller has already written that edit to the worktree, and `git pull
  --rebase` refuses over an unstaged change before it starts (exit 128, no
  marker). In the ordinary path that rebase does not run at all; what the pull
  still reaches is a repository already stopped in an earlier operation, which
  is the case the new refusal covers. Whether the pull there should be made
  real is left open, in issue #178.

## [1.43.0] — 2026-09-08

The one document the loop appends to from every branch had no way to survive
two branches doing it.

### Added

- **`aide insights resolve [--dry-run]` — an entry-level union of a conflicted
  inbox (issue #158).** `insights.md` is append-only by contract (§1 →
  `insights.md`): every role adds a line at the end, so two branches that each
  captured an insight conflict on every merge or rebase, and the conflict is
  always the same trivial shape. Resolving it by hand is where "never reword a
  captured claim" gets broken, because whoever resolves it retypes the block —
  and an agent asked to resolve one is the least reliable party in the repo to
  be holding an immutable line. The verb reads the file with the markers in
  place, parses both sides into entries, and writes the union: the history the
  two sides share, then each side's new entries in the order they were
  captured. Positional numbering needs no repair, since nothing moves. An
  entry ticked on either side ends up ticked and keeps that side's pointer;
  both sides' trail lines are kept, in date order; two ticks with two
  different pointers keep both — the second as a dated trail line — and the
  run says so, because that one needs a human. `diff3`/`zdiff3` conflict style
  is understood, and its merge-base section discarded rather than appended to
  both sides. `--dry-run` prints the union and writes nothing. Where git holds
  the path unmerged the verb stages the result, so the merge or rebase can
  simply continue — including an **add/add** conflict, which has no merge base
  at all and which a consumer reaches easily, since `check`, `claim` and
  `queue start` each create the inbox when it is missing. Run against a file
  whose markers someone already stripped by hand, it stages that as it stands
  rather than reporting "nothing to resolve" over a path git still refuses to
  commit.
- **It refuses anything that is not a pure append, and a refusal writes
  nothing.** A claim reworded, reordered or deleted on one side is a change to
  an immutable line, and so is an archive — `insights archive` cuts closed
  entries out of the middle and renumbers what remains, which is the open
  point issue #158 left for the archive boundary. Both are refused with the
  file left exactly as it was, markers included, because the only safe thing
  to do with a claim the code cannot align is leave it in front of a human.
  The check is exact rather than inferred wherever git can supply the merge
  base (`git show :1:`, which a stalled merge or rebase has): the shared
  history *is* the base, so a rewrite is caught even at the tail, where the
  two sides alone cannot tell a reworded claim from a second capture. Without
  a base it falls back to the sides' longest common prefix, which still
  catches every reorder, deletion and archive, since those leave entries
  surviving on both sides past that prefix.
- **`aide merge` names the verb where the conflict actually lands.** The
  inbox is `_ALWAYS_AUTHORISED`, so every role captures into it and two open
  branches conflict here as a matter of course — while the agent standing at
  the stall is the `validator`, which preloads `aide-review-and-validation`
  and has read nothing about the inbox. A failure message reaches every role
  and every runtime without any of them having read anything first, which a
  skill preload cannot. Both of `merge`'s refusals now carry it: the failed
  `git merge`, and the refusal to re-run over a tree left mid-merge. It says
  whether the inbox is the **only** unmerged path — which decides whether the
  verb finishes the job or is one step of several — and names the command that
  completes the stalled operation (`git commit --no-edit`, `git rebase
  --continue`, …). It stays quiet when the conflict is somewhere else.
- **The interrupted-state refusal offers resolution before abortion.** It
  previously said only "finish or abort that state first (`git rebase --abort`
  / `git merge --abort`…)", and an agent that reads that literally aborts,
  re-runs, and meets the identical conflict — a loop, and one this verb can
  end. Resolving and staging now comes first, and the message says plainly
  that aborting an unresolved conflict brings it back on the next attempt.
- **`aide check` reports a conflict marker in `insights.md` as an error.** The
  other inbox lints are warnings, deliberately — a captured line is immutable,
  so a warning on one can never be cleared. A committed marker is the
  opposite: always fixable, and fatal to every other verb. The markers are
  skipped rather than misread — they are not entry lines — which is worse,
  because both sides' entries then land in one numbered list: `list` numbers
  straight across the halves, and the `N` a reader takes from it points `tick`
  at a different claim than the one they read. The message names
  `insights resolve`. `<<<<<<<`,
  `|||||||` and `>>>>>>>` are matched; `=======` deliberately is not, because
  it is also a setext heading underline and a lint that fires on a heading is
  a lint a reader learns to skim.

## [1.42.0] — 2026-09-08

One surface, taken apart: the routing rules for insight-inbox entries existed
twice in adapter prose and had already been phrased differently, the pass that
always runs at a queue boundary could only be reached through a seven-step
retrospective, and the fixes that pass routes rode the next stage's batch.

### Added

- **`/aide-review-insights`, the inbox triage spun out of the feedback loop
  (issue #159).** Step 0 was the step that always ran, carried most of the
  skill's prose, and was the only part an unattended queue boundary needed —
  so a human who wanted to triage the inbox invoked a retrospective, and an
  agent that invoked the loop paid for all of it. It is now its own skill,
  reachable on its own, and the feedback loop names it (with
  `/aide-review-permissions`, `/aide-review-instructions` and
  `/aide-status-report`) in a table of modular passes instead of restating any
  of them; the loop keeps steps 1–5, and its own status-regeneration step is
  now one of those calls. `/aide-run-roadmap`'s pre-planning triage points at
  the new skill rather than at "`/aide-feedback-loop` §0".
- **Triage judges what it routes, and the judgement is contract (§1 →
  `insights.md`).** Routing an entry as written left three findings with
  nowhere to go: an entry that repeats an earlier one, an entry whose premise
  has decayed (what it names no longer exists, or has since been fixed), and
  an entry filed under a type that does not fit what it describes. All three
  are recorded the one way a captured claim allows — a dated trail line under
  the entry, never an edit to the claim — and so is a *ticked* entry whose
  status the triaging role now knows to be stale. Routing a `defect`, `gap` or
  `automation` entry still never ticks it, and the decayed premise is the one
  stated exception: it is ticked because there is nothing left for a queue to
  carry, which is not a routing at all. In the engine rather than in the skill,
  because the queue author reads the same rules.

### Changed

- **Insight-derived fixes get a maintenance queue ahead of the stage queue
  (issue #160).** `/aide-create-queue` turned open `defect`, `gap` and
  `automation` entries into items on the stage queue it was authoring, so a
  one-line fix waited for a ten-item stage to merge and every other branch
  picked it up only after that. When such entries exist and warrant it, one
  create call now writes **two** queues: a short maintenance queue from those
  entries, numbered first, then the stage queue. It is not a second live
  queue — the live queue is the lowest-numbered open one, so the maintenance
  queue is served, merged, and rebased onto first with no new state anywhere,
  which is the property `tests/test_fixture_consumer.py` now pins at verb
  level. The planner still decides: an entry too small, blocked or out of
  scope is passed over with the reason stated, and a `gap` the upcoming stage
  was going to fill anyway stays in the stage queue with that stage named.
  `/aide-run-roadmap` and the `queue-planner` spec expect the pair, branch and
  PR on the lower number, and carry both queue files in the one PR — the split
  decision is only reviewable with both in front of the human. The engine
  states the *ordering* and deliberately not the checkpoint shape: how the two
  plans reach a person is the caller's, which is why one adapter carries them
  in a single PR while a project whose `git.mode` pushes nothing (§4) has none
  at all.
- **One routing table, written once and pinned twice (issue #160).** Which
  entry type goes where now lives in §1 → `insights.md` as a table;
  `/aide-review-insights` and `/aide-create-queue` each carry it verbatim and
  each pin it, so the two copies and the engine's cannot drift apart in
  silence. That needed one guard to change: a `<!-- pins:` block no longer
  classes a skill as a *section* skill (it would have demanded a `paths:`
  block, a hidden frontmatter and an agent preload of a skill whose purpose is
  to be invoked by name). A section skill is now recognised by
  `user-invocable: false` alone; `test_rule_pins.py` checks any skill's pins in
  both directions and requires them only of a delivered file; and what the old
  second signal bought is bought instead from the preload side, by
  `test_every_skill_an_agent_preloads_is_a_section_skill`.
- **The seven `## Hand-off` tails are gone; the sequence has one home (issue
  #161).** Each was a slice of the loop sequence restated per skill — "start a
  fresh chat session and run `/aide-…`" — drifting independently, and no
  template carried one. `AGENT-CONTEXT.md` now states the rule once: close a
  step by saying what it produced, not by naming the next one, and start the
  next step in a fresh session, because each step derives from the *written*
  document the last one produced rather than the conversation that drafted it
  (create-vision's rationale, generalised). The step list itself stays in
  `README.md`. The two content-bearing endings survived under headings that
  name what they are — `/aide-create-queue`'s absorbed and passed-over entries
  is now "Absorbed and passed-over entries" — and `test_rules.py` fails if a
  `Hand-off` heading comes back to any skill.
- The always-on floor moves from 7,578 to 8,067 content bytes, all of it the
  fresh-session rule added to `AGENT-CONTEXT.md` above; `FLOOR_PIN` in
  `tests/test_structural_budget.py` moves with it.

## [1.41.0] — 2026-09-08

Two engine wrongs a consumer met head-on, both in the same file: a paused
deliverable that reported its stage as shipped, and a merge whose base could be
lost by a killed run and then silently guessed by the next one.

### Fixed

- **A ⏸ deliverable no longer rolls its stage up to ✅ (issue #173).**
  `rollup_status` treated `deferred` as terminal alongside `complete` and
  `excluded`, so a stage paused mid-flight derived as `complete` — and `aide
  check` then advised *"all deliverables ✅ but summary shows in-progress …
  close the stage"*, exactly the wrong action. It reached the single source of
  truth: an `aide progress set` run rewrote a consumer's stage summary row and
  section heading from 🚧 to ✅ over three unticked acceptance criteria, and a
  human restored it by hand. The terminal set is now `{complete, excluded}`,
  which is what `scope` has always meant by the same icons one layer down —
  its spent set is the same pair, and its comment says ⏸ claims are "dormant,
  not dead". A deferred deliverable is work postponed, so its stage stays 🚧;
  an excluded one is a decision not to do the work, so its stage can still
  close. A stage with no ✅ at all is unaffected and still derives `planned` —
  no new rollup state was added, deliberately: the fix is that ⏸ stops
  counting as done, not a fourth thing for a stage to be.
- **A merge killed mid-suite puts the claim branch and its base back (issue
  #174).** `merge` deletes the claim branch *before* the post-merge test run
  so the run sees the refs a fresh clone would (issue #125), and since #167
  restores both the ref and `branch.<claim>.aide-base` on the way out. That
  restore ran from exactly the two clean failure returns — there was no
  `try/finally` around the window and no signal handling anywhere in the
  module, so a run killed inside it (Ctrl-C, a CI timeout, an unattended
  runner's wall clock) left the item merged into its base with the branch gone
  and nothing recording where it had been. The window is now wrapped: an
  interrupt restores the ref and its base, says so, and re-raises, so an
  interrupted run still exits as interrupted. `SIGTERM` is included — Python's
  default handler ends the process where it stands, and SIGTERM is how every
  unattended case arrives. The window ends at the push, so a merge that
  completed does not get a stale claim branch back.

### Changed

- **`aide merge` refuses a claim branch with no recorded base, instead of
  falling back to `main_branch` (issue #174).** `SIGKILL` and an OOM kill run
  no `finally`, so the crash-safe restore above cannot be the whole guarantee:
  whatever killed the previous run, the *next* one meets a branch with no
  record — and recreating the ref by hand (`git branch <name> <sha>`) does not
  bring the config back either. `resolve_base` cannot tell "never recorded"
  from "recorded and lost with the ref", but `merge` can, because it is the
  verb that does the deleting. A consumer's re-run took the silent fallback
  and fast-forwarded a whole queue branch onto `main` and pushed it, past its
  one-reviewed-PR-per-queue gate, with nothing in the output naming `main`;
  recovery was a force-push. `merge` now stops and names the choice it will
  not make for you. **This is the breaking half**: a shape that previously
  succeeded now exits 1. `claim` records a base for every branch it creates,
  so the loop's own path is untouched — what this asks for is `--base` on a
  hand-made branch's first merge, which is one word said once. `resolve_base`
  itself is unchanged, and every other verb still defaults as before.

## [1.40.0] — 2026-09-08

The item loop gains the two moves it lacked: an adversarial read of the diff,
and a way back to the spec when the spec and the tests disagree. Both were
observed as gaps in a consumer, and both were previously unstaffed by any role.

### Added

- **`conventions.md` §9 — review and validation (issue #150).** The loop had a
  validator and no reviewer, and "review" meant three different things across
  its own documents. The new section states the split: validation is
  spec-relative, gated PASS/FAIL, and blocks the merge; review is adversarial,
  reads the diff for what the spec never anticipated, and produces findings. A
  green validator is not a review, and a clean review does not discharge
  validation — the two fail in opposite directions. Findings triage exactly the
  way insights do: in scope for the running item is a fix on its branch, out of
  scope is one `insights.md` line. Runtime-general, like §3 and §6, and named
  by `ADAPTER-SPEC.md` §7 as a third section an adapter must deliver rather
  than point at.
- **A `reviewer` agent, off by default behind `[loop] review` (issue #151).**
  `"off"` (the default) leaves the loop exactly as it was; `"background"`
  dispatches a `reviewer` the moment the builder returns, concurrent with the
  validator over the same branch, so the review costs no wall-clock — the
  validator's suite run is the long pole and a read of the diff fits inside it.
  **The merge waits for both**: under `"background"` the validator holds the
  merge and reports PASS (merge held), the orchestrator triages the findings,
  and `aide merge NNN` runs only once they are discharged — findings that
  arrive after the item lands gate nothing. The role writes no code, modifies
  no tests, does not merge and does not touch `progress.md`. Off by default
  because a review round costs tokens on every item, and a project with CI and
  hosted reviewers may reasonably decline it. `ADAPTER-SPEC.md` §2 carries it
  as an optional role definition at T2, so an adapter that omits it stays
  conformant.
- **A new section skill, `aide-review-and-validation`, delivering §9 to
  `reviewer` and `validator`.** Preloaded at spawn into exactly those two
  specs, which is what keeps the agent prose from inventing the distinction
  itself: the failure §9 names is a role collapsing the two reads, and a role
  that has already collapsed them will not go and read a pointer. 2,740 bytes,
  paid by two roles; the always-on floor is unchanged.

### Changed

- **§5 covers the downstream case: a builder that finds the spec and the tests
  in contradiction hands the item back to `spec-author` (issue #168).**
  Observed in a consumer under 1.38.0, where an acceptance criterion, its
  description and an assumption all described repeated absorption while the
  test written from it pinned a single pass. The builder implemented the test,
  recorded the conflict as a Decision, and shipped — a rule defective on its own
  terms, past a validator for which "tests pass" and "stayed in scope" were both
  true. The builder reads both and so is the first role that can see it, and has
  no standing to arbitrate: it now returns the contradiction as a distinguished
  outcome the driver routes, rather than picking a side. `spec-author` corrects
  the criterion under `loop.clarify` as an appended, dated amendment — never a
  rewrite — the tests are re-derived, and the builder is re-dispatched. Capped
  at one correction per item. `builder.md` and `/aide-run-item` carry the path;
  `loop.validation_rounds` is untouched, since a spec correction is not a
  validation round.
- **`validator.md` no longer calls itself "the skeptical reviewer".** It states
  what it is and is not (§9), why the status it writes is `in-review`, and that
  where no reviewer runs the adversarial read is genuinely unstaffed — its PASS
  means "meets its spec", never "this code is correct".

## [1.39.0] — 2026-09-08

Three engine wrongs that were silent in the direction that costs most: a
merge that retargeted itself, a progress file that stated undone work done,
and an environment check that said OK over a venv with no test runner. Each
was observed in one consumer, and each is now either fixed or loud.

### Added

- **`[python] interpreter` names what `env --bootstrap` builds the venv from
  (issue #166).** A path to an interpreter, taken whole when it names an
  existing file so `C:\Program Files\…` survives, or a command line
  (`python3.12`, `py -3.12`, a quoted path plus flags) split the way the
  platform's shell would; unset, the bootstrap uses the Python that launched
  the CLI, as before. A consumer whose dependency closure resolves
  only on a narrower range than its `requires-python` declares had nowhere to
  say so: an ambient conda 3.14 built the venv, a pinned dependency with no
  cp314 wheel fell back to a source build that failed on cmake, and the
  project's editable install was the only thing that landed. `aide env`
  reports the venv's Python beside the configured interpreter and calls a
  venv built from a different version stale, so the mismatch is visible
  before anything trusts it; a configured interpreter this machine cannot
  run is a sentence, not a traceback, and builds nothing. The scaffolded
  `aide.toml` carries the key as a commented hint.

### Fixed

- **A merge re-run resolves to the base the first run had (issue #167).**
  `merge` deletes the claim branch before the post-merge test run, and `git
  branch -d` takes the branch's config section — `branch.<claim>.aide-base`,
  the one input `resolve_base` has beyond `--base` — with the ref. On a red
  run the restore put back the ref alone, and the retry the failure message
  invites, run without `--base` because the first run needed none, fell back
  to `main_branch` and reported no difference. A consumer's re-run
  fast-forwarded a whole queue branch onto `main` and pushed it, past its
  one-reviewed-PR-per-queue gate, with nothing in the output naming `main`;
  a human noticed that `main` had moved. Every restore now records the base
  *this run merged into* — the resolved one, so a run given `--base` is
  retried where it landed and not where an older record pointed — beside
  the ref, so the retry resolves exactly as the first run did. Two belts on
  that brace:
  `merge` names the base it lands on and how it was chosen (`--base`,
  recorded at claim, or the `main_branch` default with no record on this
  machine) on every run, so a retargeted merge is at least visible in the
  transcript; and both re-run instructions now carry `--base <resolved>`.

- **A split of a shared `*(Items …)*` marker reports the copies it wrote, and
  `aide check` reports them until each is reworded (issue #169).** 1.31.0's
  desugar (#131) is correct — one status cell per item — and what it writes
  cannot be: the bullet had one sentence for N items, so N−1 copies carry
  prose describing work that is not the item named on them. One consumer
  reworded a copy by hand, in a document the CLI owns; the next copy was
  flipped to ✅ without rewording, and `progress.md` stated another two
  items' still-open work as done under it, with nothing able to tell.
  `set_item_status` now records every split, `progress set` and `merge`
  print each copy with its line number as the chore it is, and a new check
  warning names the single-item deliverable bullets in one stage whose prose
  is identical — the shape a split leaves behind and only a rewording
  removes. A consumer that genuinely writes two identical deliverables in a
  stage sees the same warning; the remedy is the same sentence either way.

- **`aide env` cannot report OK over a venv with no test runner (issue
  #166).** The check inferred the health of a whole install from the venv
  existing and one `import_check` succeeding, which a `pip install -e .[dev]`
  that aborted after the editable project satisfies. `env_report` now asks
  everything it can of the venv before saying OK: the venv exists; the last
  `--bootstrap` that built it finished, read from the record the bootstrap
  now writes beside the venv's files (`aide-bootstrap.json`, both outcomes,
  so a completed rebuild clears an earlier failure); its Python matches
  `[python] interpreter` where that is set and runnable; `import_check`
  imports; and the module `test_command` runs with `python -m` imports too.
  A bootstrap whose install fails is an exit-1 sentence rather than a
  `CalledProcessError` traceback, and the venv is reported stale until a
  bootstrap completes; a stale venv is rebuilt with `--clear` rather than
  re-pointed over the old site-packages. `env_status` keeps its three
  answers for callers that read only the word; the report line carries the
  facts.

## [1.38.0] — 2026-09-03

### Added

- **Two more failing acceptance-criterion shapes, both truth-of-the-claim
  (issues #153, #154).** §1 → `items.md` already ruled that an acceptance
  criterion is an invariant over the resulting content, with two shapes named;
  one consumer's queue produced two more in two days, and both are the same
  defect — an AC that claims more than it measured. **A shape check standing in
  for the fact it was supposed to measure**: three criteria asserting a fact
  about live state (an artifact's per-label field set, which field a rule
  reads, a completeness flag) were accepted on a check of the *sentence* — its
  length, a token in it that resolves, a flag derived from the declarations
  rather than from what they describe — and each passed a false factual claim
  into a merged artifact, each fix strengthening the next check while the next
  false claim still slipped past it. A factual AC is now a **measured equality
  against that state**, met only by a test that recomputes the fact from the
  primary source and compares. **A stage acceptance criterion closed by
  positional coincidence**: a validator mapped a five-AC item onto a
  five-criterion stage by index and attested four criteria against tests that
  measured something else entirely, all four retracted the same day. An item's
  ACs and its stage's criteria are two independent lists; an AC closes one only
  where the spec says so, and under a spec authored with the annotation
  available, silence is an answer.

- **`*(closes Stage N criterion M)*` on an item AC (`templates/item.md`).** The
  optional annotation that makes the mapping above explicit, and the only thing
  that licenses ticking a stage criterion — an AC that names none closes none,
  which is the ordinary case. **One transitional exception, which declares
  itself:** a merged spec predating the annotation is never rewritten to carry
  it and its stage does not stop being attestable, so a criterion there may be
  attested on its own subject where the evidence names the check *and* says the
  mapping was made at attestation time — a phrase that lands in `progress.md`
  permanently, so the weaker basis stays legible, and one nobody writes by
  accident on a spec that could have carried the annotation. The
  `aide-living-documents` skill delivers both statements, and `spec-author`,
  `test-writer` and `validator` point back at §1 for them.

### Changed

- **`aide progress retract` says the `aide check` warning it creates is
  permanent (issue #152).** The warning is deliberate — a withdrawn
  attestation stays visible — but a consumer that pins the tolerated warning
  set learns that at its merge gate, with a suite reddened by honest
  self-correction: four retractions turned two such tests red in a consumer
  whose merge was then blocked on the consequence rather than on any defect.
  `retract` now prints, beside the finding it captures, that the warning is
  from now on part of `check`'s output and that a test pinning the warning set
  needs widening for that stage and criterion — so the widening lands in the
  same change as the retraction. The warning itself, its wording and its
  advisory status are unchanged; `run_checks` keeps returning
  `(errors, warnings)`, which §6 instructs consumers to call in-process and
  assert on.

## [1.37.0] — 2026-09-02

### Added

- **`aide check` reports roadmap↔progress acceptance-criterion drift (issue
  #142).** The roadmap's Validation / acceptance bullets become the matching
  stage's Acceptance boxes — §1 → `progress.md` and `templates/roadmap.md`
  both say so — and it was the only mirror in §1 with no enforcement at all:
  a consumer's stage carried a fourth, load-bearing box its roadmap never
  grew, and there was no moment at which anything would have said so. Since
  1.35.0 the silence also had teeth: `aide progress reword` matches boxes to
  bullets by index and refuses on a drifted stage, so the consumer met a
  refusal with no tool naming the stages affected. `check` now compares, for
  each stage present in both documents, the Acceptance box count against the
  non-`Target:` bullets of the stage's Validation / acceptance block
  (`Target:` bullets are Outcome-target material, not boxes, and are not
  counted), and warns naming the count on each side.

  Deliberately a **warning, not an error** — a stage may legitimately be
  mid-replan, and a document set that was fine yesterday must not start
  failing today — and deliberately **counts, not text**: comparing wording
  would fire on every honest tightening of a criterion's prose, which is
  exactly what `reword` exists to make cheap. The count is the signal that a
  criterion was added or dropped on one side only. A missing `roadmap.md`, a
  stage the roadmap does not have, and a roadmap stage with no Validation /
  acceptance block at all are all silent: no mirror is a different situation
  from a mirror that disagrees, and `reword` already keeps the two apart.
  The repair is a hand edit of one document; after it, `reword` works on
  that stage again.

## [1.36.0] — 2026-09-02

### Added

- **An item spec's assumption can name the engine it was true for, and `aide
  check` says when that engine has moved (issue #144).** A spec's
  `## Assumptions` block is a durable record that outlives its branch, and it
  can legitimately pin **engine** behaviour — what `aide check` warns about,
  what a verb does. The engine then moves under it: three merged specs in one
  consumer each asserted two `aide check` warnings that 1.29.4 had
  deliberately removed, one of them calling their presence "expected output" —
  a validation item's record of what a clean run looks like, describing a run
  that is no longer possible. `install.py --update` copies the new engine and
  says nothing about the claims it has just falsified, nothing marks which
  engine an assumption was written against, and the consumer found it only by
  reading the inbox at a queue boundary.

  The marker is the one `insights.md` provenance has carried since #97, moved
  one document over and put in the bold label beside the assumption's own code:

  ```
  - **A8 (engine 1.28.1):** `aide check` will warn that `binary` is not a pin.
  ```

  `aide check` now reports, **advisory and outside every exit code**, each
  marked assumption whose engine predates the installed one — aggregated into
  a single line and capped, for the same reason the missing-`Assumptions`
  finding is: a long queue must not bury its substantive findings. Comparison
  is on the **feature line** only, because this project's own bump policy
  defines patch as a fix with no interface change, so a patch release cannot
  falsify a claim about behaviour and warning on one would be noise on a
  record the consumer is not allowed to rewrite.

  Clearing it is an **append**, never a rewrite — the discipline 1.35.0 built
  `progress amend` on, and the reason a consumer cannot fix this locally
  today: a re-check goes into the marker, `(engine 1.28.1, re-checked
  1.36.0)`, and the newest version named is the one the claim stands on. A
  merged spec is never edited to agree with a later engine; that is the
  failure mode, not the fix.

  An **unmarked** assumption is never warned about. The marker is what makes a
  claim checkable, and guessing a version for an assumption that names none
  would warn on every spec ever written — the same reasoning that keeps the
  insights engine note free-form. `conventions.md` §1 → `items.md` states the
  rule, the item template carries the authoring guidance, and `spec-author`
  points at it.

## [1.35.1] — 2026-09-02

### Fixed

- **`aide progress reword`'s annotation guard now reads an annotation that
  contains a `)` (issue #143).** `reword` is the one amendment that edits in
  place, and it is safe for exactly one reason: nothing has been claimed
  against the wording yet. That precondition is three independent checks —
  unticked, no correction trail, no `*(…)*` annotation — and the third did not
  hold on its own: its body was `[^)]*`, which stopped at the first `)` and
  left the closing `)*` nothing to match, so the guard **opened** on exactly
  the annotations most worth keeping. Evidence carrying its own parentheses is
  ordinary — "(4 cores)", "(xdist -n 4)", "(see §6)" — and `reword` replaces
  the whole box body, so such an annotation was deleted outright, with nothing
  in the trail to say it had ever been recorded. The body is now greedy with
  the close anchored at end of line. No live path reached it: the two sibling
  checks cover every state the CLI itself can produce (`accept --evidence`
  ticks the box; `retract` writes a trail), so an unticked, trail-free,
  annotated box took a hand edit of `progress.md` to reach — but a guard
  stated as one of three independent preconditions has to be one, or the next
  change to either sibling exposes it.

## [1.35.0] — 2026-09-02

### Added

- **A CLI path to correct an acceptance attestation, and to reword a criterion
  nobody has attested (issue #118).** `aide progress accept` reports an
  already-ticked box as "unchanged", so an attestation that turned out to be
  wrong had no verb at all: one consumer evidenced a Stage 0 box as run "on
  this CPU-only machine" on a workstation with four GPUs, and the correction
  eventually landed as a hand edit of `progress.md` in a PR review — the one
  edit every role is otherwise forbidden from making. Three verbs now cover
  it, and **none of them edits the original line**:

  ```
  aide progress amend   <stage> --criterion N --evidence "<the corrected basis>"
  aide progress retract <stage> --criterion N --reason   "<why it is withdrawn>"
  aide progress reword  <stage> --criterion N --text     "<the new wording>"
  ```

  `amend` appends a dated correction beneath a **ticked** box, in the same
  status-trail shape `insights.md` already uses. That is deliberately the only
  thing it can do: a verb that can only add cannot be used to make an
  inconvenient attestation agree with a shipped stage, so the guard against
  over-use is structural rather than a line of instruction a role may or may
  not have loaded. `retract` unticks a box while keeping the original
  attestation visible above the withdrawal — the record then reads as
  *claimed, then withdrawn, for this reason*, not as a box nobody ever ticked
  — and, because a retraction is a **finding**, it captures a `- [ ] gap`
  entry in `insights.md` in the same commit, exactly as §1 already requires of
  a `❌ Not met` outcome target. Neither takes `--all`, and both refuse
  without a stated reason.

  `reword` is the one amendment that edits in place, and it is safe for
  exactly one reason: nothing has been claimed yet. It refuses over a box that
  is ticked, annotated, or already carrying a correction trail — a mechanical
  precondition, so no role has to remember it — which is precisely the window
  #118 identifies as safe. Because `roadmap.md` mirrors a stage's criteria, it
  **writes both documents or neither**: the Nth box is matched to the Nth
  non-`Target:` bullet of the roadmap stage's **Validation / acceptance**
  block, and when the two cannot be lined up nothing is written and the
  message names the counts that disagreed. A stage with no acceptance block in
  the roadmap is not an error — there is simply no mirror to keep in step.

  `aide check` warns on every retracted criterion and `aide status` prints it,
  so a withdrawal stays visible instead of living only in one commit's diff.
  Correction trails carry no status icon, so they are invisible to the rollup
  and to the nested-deliverable lint; a criterion's index is unchanged by
  anything written beneath it.

## [1.34.0] — 2026-09-02

### Fixed

- **A failed `git push` is a sentence, and never a silent half-claim (issue
  #137).** `queue start`, `claim` and `merge` under `pr` mode each publish a
  branch they have just created, and all three pushed with the default
  `check=True`: every cause of a failed push — no remote configured, origin
  unreachable, expired credentials, a rejecting server-side hook — left
  `main()` on a `CalledProcessError`, i.e. a raw traceback in the flow whose
  whole point is to run unattended. `queue start` guarded exactly one cause in
  prose (the branch already on origin) and let the rest crash. All three now
  report git's own words, name the branch and what survives locally, and exit
  1: `queue start` and `claim` say the branch is on disk and how to publish or
  release it, and `merge` says the item is **not** ticked and the work is
  intact on the branch.

  **The traceback was the smaller half.** `claim`'s push is the last thing it
  does, so the crash landed *after* `switch -c`, the recorded base and the
  inbox commit — the item had a claim branch, `_pick_item` skips any item that
  has one, and the very next run printed `none left` and exited 0. The loop's
  own "is there work left?" answered no, successfully, having built nothing.
  A claim branch is kept rather than rolled back (the push may have reached
  origin before the client gave up, and deleting locally would then leave a
  remote branch holding the item with nothing left to explain it), so what
  changes is that it can no longer pass for work in flight: off `local` mode a
  claim branch origin has never seen is an **unpublished claim**, named as
  such by `claim`, by `status` (which composes the note with the stale and
  awaiting-review ones, since a branch can be both) and by `check`, which
  already carries the claim-branch/status agreement warnings §2 puts there.
  No origin at all is not an exemption — off `local` mode every push fails there, which is #137's own
  reproduction — while `local` mode, where an unpushed claim branch is the
  design, reports nothing.

- **`aide claim`'s `none left` is a diagnosis, not a silence (issue #137).**
  Exit 0 with no work is right when a queue is finished and wrong when items
  are open but unofferable, and `/aide-run-queue` reads the bare line as "the
  queue is exhausted — stop and report". The 1.29.0 gate diagnosis is now the
  general case: with items still 📋 and none offered, `claim` names each one
  and what holds it, in the order `_pick_item` rejects them — an unresolved
  human gate (unchanged, and still first), a claim already in flight, a
  dependency not landed, an unpublished claim. The first three are ordinary
  and keep exit 0; an unpublished claim exits 1. A genuinely exhausted queue
  still answers with a bare `none left`, so a finished run gains no noise.
  `conventions.md` §2 states both rules, and `/aide-run-queue`'s decision step
  distinguishes the three answers.

## [1.33.0] — 2026-09-01

### Added

- **The open insight inbox is an input to queue authoring, not only an output
  of triage (issue #134).** Triage routes each unchecked entry by type, and
  every type had a destination that exists except the two that by definition
  need *scheduling*: `defect` and `gap` were routed to "the queue being
  authored, or noted for the next `/aide-create-queue` run". Triage runs **at**
  the queue boundary — the finished queue is closed and the next one is
  unwritten — so there is no queue being authored, and nothing read such a
  note: `queue-planner` named `insights.md` once, under **Out-of-scope
  insights**, to say *append one line and carry on*, and no caller of `aide
  insights list` existed anywhere in the adapter. The triager's only honest
  move was to leave the entry unticked and hope the next planner looked. In one
  consumer that was eight open entries, several already carried past one
  boundary, in a file the role that would act on them had no instruction to
  open. The failure is quiet in the usual way — `aide insights list --open`
  reports them faithfully, the loop reports success, and nothing says "these
  were routed nowhere".

  The inbox was already the right carrier; it was not declared an input. §1 →
  `insights.md` now states that it is one, and that every open `defect`, `gap`
  or `automation` entry is **considered, and either queued or explicitly passed
  over — never silently dropped**. Queueing one is a routing like any other, so
  the author who queued it ticks it with the item number it became; a
  pass-over leaves the entry open and is stated where the queue is reviewed, so
  an unchecked entry is honestly still a candidate rather than a hope.
  `automation` is included because the engine's own route sends all three types
  to "a candidate item" — fixing two of them would leave the third stranding
  identically. Delivered to `queue-planner` through the `aide-living-documents`
  skill, which already reaches that role and already pins this section, and
  carried in the role's own steps: the read in step 1, the tick in step 6, and
  a summary that names what was queued **and** what was passed over with why,
  which is what puts both in front of the queue PR's reviewer. The
  `/aide-feedback-loop` step-0 wording that stated the obligation is corrected
  to match the mechanism now behind it — leaving a `defect`/`gap`/`automation`
  entry unchecked **is** the routing, so its "tick each routed entry"
  instruction is narrowed to the types that really terminate there.

### Changed

- **A `framework` issue body opens with the engine version, and writing that
  header is the filing role's job (issue #127).** Triage of a consumer report
  starts by asking which engine it was observed under; without it the report
  cannot be checked against this changelog, and the two failure modes are
  symmetric and both bad — a live defect closed as already-fixed, or a fixed
  one re-fixed. 1.24.0 (#97) already required the version to be *in* the body
  and said where to take it from, including the `.aide/VERSION` fallback marked
  as *the version at triage time, not at capture*. What was missing is smaller
  than it looks and is the half that bites: **where** it goes, and **who** owes
  it. The version now leads — first line, before the observation, in the shape
  `.github/ISSUE_TEMPLATE/consumer-report.md` already uses — because triage at
  the destination begins by checking the claim against that engine's history.
  And the section now says plainly that a form on the destination cannot reach
  this path: an issue template binds a human composing in a browser and is
  silently bypassed when the body is composed by the role and passed on the
  command line, which is how the handover files. That is what a template is,
  not a gap in one. The cost of the header is nothing, because the consumer
  already holds the fact — it is in the entry's own provenance marker (#97), or
  one read of `.aide/VERSION` away. The adapter's `framework` bullet, the only
  wired path that reaches `gh issue create`, now quotes the engine's shape
  instead of carrying a body structure of its own.

## [1.32.0] — 2026-09-01

### Added

- **`aide check` warns when a diff-time scope claim is written as a suite
  assertion (issue #132).** "This item did not touch X" is decided on the branch
  by `aide scope`, against the item's declared paths — that is the whole reason
  the verb exists, and §1 → authorised paths already said the claim belongs
  under **Asserts against** and is retired when its item merges. Neither
  statement reached the spec-author writing the criterion or the test-writer
  implementing it: two independent items in one consumer wrote
  `git diff main...HEAD` in a test, which is the signature of a missing check
  rather than a careless author. On a stacked queue the item's base is the
  *queue branch*, so `main` is stale by the whole queue and every sibling item's
  legitimate change is reported as this item's violation. The obvious repair is
  wrong too — deriving the base from `aide scope` holds only while the suite
  runs on the item's own claim branch, and `aide merge` re-runs it from the
  merge target — and a skip guard leaves the test permanently skipped once the
  claim branch is deleted, which §6 forbids.

  Two **literal** shapes are reported: a hardcoded `<base>...HEAD` range (the
  configured `main_branch` plus the conventional `main`/`master`, either
  direction, two dots or three, `origin/` optional) and a shell-out to
  `aide scope`. A test that *computes* its base — `git merge-base HEAD
  origin/main`, then a diff — is a claim about the branch rather than about an
  item's scope and is deliberately **not** reported; this framework's own
  version gate is that shape. Nothing in the source separates the two, so the
  lint decides only what is literal and the rule binds where it cannot look —
  the sixth decidable §6 lint, and the same "authoritative warning, partial
  silence" contract as the other five.

### Changed

- **An acceptance criterion is an invariant over the resulting content (issue
  #121).** Stated in §1 → `items.md`, where AC shape is contracted, and
  delivered to `spec-author` through the `aide-living-documents` skill. A
  criterion outlives its item — its test is in the suite long after the branch
  is gone — so two recorded shapes are ruled out: a **bounded diff against a
  pre-item baseline**, which goes vacuous or red the moment the item merges into
  the branch its baseline came from (and under a stacked queue that is the very
  next claim), and a **premise about a sibling item's schedule**, which is
  guaranteed to become false and breaks in a file the later item's Authorised
  paths do not cover, so the repair needs a spec amendment before it can be made
  at all. Where an earlier item's test must change when a later one lands, the
  later item's spec lists that test file under **May change** from the start.
  The general principle #132 is one mechanically-detectable instance of.
- **§1 → authorised paths says what not to write**, not only where the claim
  belongs, and §6 carries the rule to the role that writes the test through the
  `aide-test-hygiene` skill. The paragraph that named the right home for a
  diff-time claim was already there; what was missing is that the wrong homes
  are named too.

## [1.31.1] — 2026-09-01

### Fixed

- **The "uncommitted status tick" diagnosis now fires in the layouts a string
  compare missed.** 1.31.0 refuses to merge from a dirty tree and, when the one
  dirty file is the tick a `--no-commit` run left behind, says so instead of
  naming a file nobody edited. It said so only in the default layout: `git
  status --porcelain` **quotes and escapes** a path holding a space or a
  non-ASCII byte (`"docs/h\303\251llo/progress.md"`), and it reports every
  path relative to the git **top level**, which is not `repo_root` when
  `aide.toml` sits in a subdirectory — so a consumer in either layout silently
  got the generic message back. Dirty paths now come from `--porcelain -z`,
  which never quotes and never escapes (a rename's source field is consumed
  rather than read as a second path), and the tick is identified by resolving
  against `git rev-parse --show-toplevel` rather than by string equality.
  Degradation-only either way — the refusal itself always fired — but it was
  cosmetic exactly where nobody would notice it had stopped working.

## [1.31.0] — 2026-09-01

### Fixed

- **`aide merge` no longer walks into a tree it must not touch, and no longer
  re-merges what already landed (issue #133).** A conflict resolved by hand
  left a merge commit on the base that had not been pushed; the next
  `aide merge` ran its unconditional `switch` → `pull --rebase` → `merge`, and
  the rebase **linearised that merge** — dropping it, replaying both parents,
  and reintroducing the exact conflict the human had just resolved. The work
  survived; the resolution did not. A consumer that obeys §3 has no remaining
  place to be careful, because the unsafe sequence *is* the verb. Three
  preconditions, all before the first `switch`:
  - a **dirty tree** (tracked changes) or an interrupted operation
    (`rebase-merge`, `rebase-apply`, `MERGE_HEAD`, `CHERRY_PICK_HEAD`,
    `REVERT_HEAD`) is refused, with the recovery, the way the
    base-is-not-a-local-branch case already was. Untracked files are
    deliberately not dirty: they survive `switch` and `pull` untouched, a loop
    leaves them around constantly, and a real collision aborts the merge with
    git's own message.
  - a branch that is **already an ancestor of the base** skips the merge — the
    tick, the push and the cleanup still run. This is the case that bit: the
    branch was merged, only the push was missing. It also makes the verb
    **re-runnable**, which is what a loop needs of it.
  - a base carrying a **merge commit origin has not seen** is never rebased
    over: the verb tries `pull --ff-only` and, if origin has genuinely diverged,
    stops and says so rather than choosing between a rewrite and a stale merge.

- **A red post-merge test run blocks the ✅ and the push (issue #125).** The
  order was `_promote_item_to_complete` → push → test, so a failing run printed
  "investigate" and exited 1 with the tick already written and the merge already
  on origin: a consumer's shared queue branch was left red with the item marked
  done. The run is a **gate** now — green earns the ✅ and the push; red leaves
  the merge local, the item 🔍, and the claim branch back where it was, and says
  which. The claim branch is also deleted **before** the run rather than after,
  so the run sees the refs a fresh clone would: with it present, a test command
  including `aide check` reported the item's own branch as stale against the
  item being merged — a failure class produced by nothing but the ordering.
  Every exit after that deletion restores the branch, so the same command
  finishes the job on a retry and nobody has to hand-edit a tick.

- **A deliverable bullet whose marker names several items is no longer one
  status cell (issue #131).** `*(Items 016, 017)*` is a form §1 blesses and
  `/aide-create-queue` recommends, but a bullet carries one icon, so
  `aide merge 016` completed 017 as well — never specced, never built,
  thereafter read as ✅ by everything that parses the file and discounted from
  its queue's open count. The form stays legal and **desugars**: the first flip
  that would advance the bullet splits it into one bullet per item, same text,
  one `*(Item NNN)*` each, and moves only the item named. Ranges included
  (`*(Items 071–075)*` is five cells) — but **not** a range wider than the
  parser's 50-item typo limit, which contributes only its endpoints: splitting
  `*(Items 044-999)*` would write a bullet for a phantom item 999 that
  `check`, `claim` and every queue rollup would thereafter count as real.
  Writing fiction into the tracked document is worse than the shared cell this
  removes, so a malformed marker keeps the old behaviour — whole-bullet, so in
  `*(Items 006, 044-999)*` the sound half keeps the shared cell too. A flip that advances
  nothing splits nothing, so a no-op `progress set` still rewrites nothing. No consumer edits
  anything — hence a minor, not a major. §1 → `progress.md` and create-queue
  step 8 now say so, in the same commit as the code, because the defect existed
  precisely where they already disagreed with the engine.

### Changed

- **A failed `git push` at the end of `aide merge` is reported and non-zero.**
  It was swallowed, which leaves a ✅ on a merge origin never received — the
  same class of lie as ticking an item whose tests fail. The remote claim
  branch is kept in that case, so the work still exists somewhere other than
  one checkout.
- **A `--no-commit` tick now blocks the next merge until it is committed.**
  Both `aide progress set NNN --no-commit` and `aide merge NNN --no-commit`
  leave the status tick written but uncommitted, which is what the flag is for
  — and the dirty-tree precondition above then refuses the *next* `aide merge`,
  of any item, not just a retry of that one. The refusal is correct (git will
  not rebase over unstaged changes either), so what changes is that it names
  the cause: a tree whose only change is that tick is reported as exactly that,
  with "commit or discard it", rather than as an unexplained dirty file the
  human never edited.

## [1.30.0] — 2026-09-01

### Added

- **`aide check` warns when an Authorised-paths bullet declares more paths than
  `aide scope` reads (issue #119).** The contract is one path per bullet — the
  first backtick span of the opening line — and the two ways to break it were
  both silent. A bullet listing several comma-separated `` `path` `` spans
  authorised only the first; a path wrapped onto a continuation line was not
  read at all, since the parser inspects bullet lines only. Three of one
  consumer item's four bullets had that shape, and the narrowing surfaced much
  later as an `aide scope` FAIL naming paths the spec's own prose plainly
  authorised. Silently narrowing an authorisation is the worst of the three
  behaviours available, so the violation is now reported where it is authored,
  naming each dropped span. A **warning**, beside the other item-spec lints:
  existing specs carry the shape, the remedy (split the bullet) is the author's,
  and an unattended run must not start failing on a bullet a human reads fine.
  The lint and the parser share one section slicer, so the warning cannot
  describe a bullet `aide scope` never looked at — a test pins the dropped set
  against the parsed set rather than checking either alone.

  Only the **path position** is read — the opening line up to its reason
  separator, plus continuation lines while no reason has started, which is
  exactly the wrapped-list shape. Reading the reason too was measured against
  two real consumers first and produced 82 and 224 findings, nearly all of them
  identifiers and config keys legitimately quoted in reasons; the very spec that
  reported #119, already split one path per bullet and saying so in its own
  prose, drew six. With the limit it is 3 findings across 21 specs and 25 across
  131, and they are the real thing. A lint nobody can afford to read is the
  failure mode issue #13 was filed for, so the limit is stated rather than
  hidden: a second path written *after* the reason separator is not
  distinguishable from prose naming a file, and stays silent. §1 →
  `authorised-paths` now states the rule and its remedy outright.

### Fixed

- **A bullet's reason could start with a line-final dash and be read as more
  path.** `_bullet_path` split on ` — ` with whitespace required on *both*
  sides, so `- `path` —` with the reason wrapped below did not register as
  having a reason at all. Harmless for the parser, which stops at the first
  backtick span either way, but the new lint reads exactly as far as the reason
  and would have taken the whole thing for path position. The two now share one
  definition of where a reason starts; as a side effect a non-backticked bullet
  written `- src/a.py —` declares `src/a.py` rather than `src/a.py —`, which
  matched no file git ever reports.

- **The documented provenance shape crashed `aide progress set` repo-wide
  (issue #120).** `AGENT-CONTEXT.md` prescribes `*(item NNN, YYYY-MM-DD, engine
  X.Y.Z)*` for an insight's provenance, and `_referenced_item_numbers` read it
  as the item list `NNN, 2026, -08, -30`, where an unguarded `int()` raised
  `ValueError`. The blast radius was the verb, not the line: `progress set`
  reads every line of `progress.md`, so four evidence annotations written in
  the convention the framework itself documents took the verb down for *every*
  item in the consumer until a human approved rewording all four — there being
  no verb that amends evidence text. Both hardenings from the issue land, and
  either alone stops the crash. The reference-group regex now refuses a number
  that opens a `YYYY-MM-DD` date, with a lookahead that also forbids the
  backtrack that would let `2026` shrink to `202` and pass anyway; ranges are
  untouched, since `-092` carries one hyphen group and a date carries two. And
  the split's parts are matched against an item-number shape before being read
  as one — the invariant behind the known case: a part that is not a number is
  provenance prose to skip, never a traceback out of an unrelated verb. Every
  documented reference form parses exactly as before.

## [1.29.5] — 2026-09-01

### Fixed

- **Resolving imports made `from subprocess import *` invisible.** 1.29.4 fixed
  a false positive (an unrelated `Runner().run(text=True)`) by matching only
  through a binding the module actually makes — and a star import binds `run`
  without naming it, so the resolver saw nothing and went quiet on a call the
  name-only matching it replaced had reported. That trades a false positive for
  a false negative, which is the wrong direction in a section whose whole
  argument for this lint is that a false negative is the worst outcome
  available. A star import from `subprocess` now binds exactly the names this
  lint cares about. The re-export shape (`from helpers import subprocess`) is
  still not followed, and is now stated in the docstring's limits rather than
  left to be discovered.

- **The chained-comparison exemption was judged per node, not per operand.**
  `a == p.read_bytes() < b` is one `Compare` node meaning `a == p.read_bytes()
  and p.read_bytes() < b`, so the read really is on one side of an `==`; the
  membership/ordering carve-out added in 1.29.4 exempted every operand of any
  node carrying a non-equality operator, this one included. An operand is now
  exempt only when *neither* comparison it takes part in is an equality.

### Changed

- `_read_call_name` takes the readers it should match, and the comparison and
  hash sites pass `("read_text",)`. `read_bytes()` is collected unconditionally
  since 1.29.4, so letting those sites match it too appended every such read
  twice — harmless, because the caller dedupes by resolved path, but the two
  rules are disjoint by construction and the code now says so.

**On the version levels in this series:** 1.29.4 and 1.29.5 change what an
existing lint fires on, which is a stronger claim than the pure-prose 1.29.1 and
1.29.2. They are numbered patch because the effect is corrective — closing false
negatives and false positives in a check that already shipped — rather than new
surface. What a consumer actually experiences is unaffected by the choice: the
whole series lands as 1.28.1 → 1.29.5, a minor move, earned by 1.29.0's new lint.

## [1.29.4] — 2026-09-01

### Fixed

- **The eol-pin lint was silent on `read_bytes()` parses, and 1.29.1 said that
  was fine.** Review disproved the reasoning that release shipped. The claim —
  a committed artifact its tests *parse* is immune to the CRLF rewrite — is a
  property of **`read_text()`**, whose universal-newline translation delivers
  `\n` either way, not a property of parsing. `read_bytes()` translates
  nothing, and `_BYTE_EXACT_READS` covered both. Measured:
  `p.read_bytes().decode()` on a CRLF checkout leaves `' value\r'` in the last
  cell of a Markdown row where `read_text()` leaves `' value'` — so a chained
  `read_bytes().decode().split()`, which never lands in a comparison, was as
  exposed as a byte-compare and drew no warning.

  So the split is redrawn where it actually holds: **any** `read_bytes()` on a
  committed path is reported, `read_text()` still only where its result is
  compared or hashed. Membership and ordering tests (`b"{" in p.read_bytes()`)
  stay exempt — there the needle decides, and a literal one carrying no newline
  is immune. Measured across four real suites before landing: the widening adds
  **zero** new warnings and removes none, so the hole closes at no cost in
  noise. §6, both docstrings and the delivered §6 skill are corrected; the
  1.29.1 prose overstated and is replaced rather than extended.

- **`binary` and `-text` now count as pins.** Both are git spellings that switch
  the conversion off outright — `binary` is the macro for `-text -diff` — so a
  file under either is exactly as safe as one under `eol=lf`. Demanding
  `eol=lf` anyway made the lint tell a fixture's author to add a pin that would
  **corrupt** the file. Not hypothetical: a consumer's `.gitattributes` carries
  a comment explaining that `binary` is correct there and *"`text eol=lf` would
  corrupt them on a Windows checkout"*, and the lint was warning about those two
  files anyway. Both warnings are now correctly silent. A bare `text` still does
  not count: it *enables* the conversion.

- **The subprocess-encoding lint matched a method name with no provenance.**
  `Runner().run(text=True)` — an unrelated object that happens to share the name
  — was reported, while the docstring claimed every warning named a call that
  really would decode. It now resolves how each module spells `subprocess`
  (`import subprocess`, `import subprocess as sp`, `from subprocess import run`,
  and `as` aliases of both) and matches only through a binding the module
  actually makes; a module that never imports `subprocess` is skipped outright.
  The test that meant to cover this passed `check=True` and so would have passed
  against the broken lint too — it now uses a `Runner` carrying its own `text=`,
  which is the shape that separates matching a name from resolving an import.

## [1.29.3] — 2026-09-01

### Fixed

- **The command-hygiene hook wrote its block message in the console codepage.**
  Found by the windows CI leg on the branch that added the §6 encoding rule,
  which is the rule catching its own author. The guard's stderr carries an
  em-dash and a `§`; `sys.stderr` on a Windows console defaults to cp1252, so a
  consumer there got byte `0x97` where every other platform got UTF-8 — and
  what the runtime reads back must not depend on the platform's guess. It now
  reconfigures its stream exactly as `aide.py`'s `main()` has all along.

### Changed

- **§6 says the codec is the producing side's job too, and explains the
  `stdout is None` instance it already recorded.** That defect has sat in the
  section as an unexplained Windows quirk — *"returned `stdout is None` on a
  Windows runner, documented not to happen"*. It is not a quirk: the decode
  runs in `subprocess.run`'s reader thread, so when the reader's codec rejects
  a byte the writer produced, the `UnicodeDecodeError` never reaches the caller
  and the stream arrives as `None`. A codec disagreement surfaces as a missing
  value rather than as an error, which is why it pairs with the
  assert-it-is-recognisable rule two bullets down. §6 now states the whole
  shape — name the codec on the read, fix the writer if you own it, pass
  `errors="replace"` when you do not, then check the value is there — and the
  delivered §6 skill carries it.

  The test that caught it is kept **strict** rather than softened with
  `errors="replace"`, so it stands as the regression guard for the hook
  emitting UTF-8, with the recognisability assertion in front of it.

## [1.29.2] — 2026-09-01

### Changed

- **§6 says how to test `aide check`, and how not to count its warnings
  (issue #123).** `cli_subprocess_test_warnings` flags a test whose object
  under test is `aide check`'s own stdout, which reads like the verb flagging
  itself; an exemption for the self-referential replay was proposed and is
  **declined**. `cmd_check` calls `run_checks`, that function returns
  `(errors, warnings)` as structured data, and asserting on it in-process is
  both the fix and the better test — which is what the reporting consumer did.
  Exempting the shape would license the worse test in the one place the
  argument for it sounds strongest, so §6 states the positive instruction
  instead and a test pins the refusal.

  The report's real finding is a measurement defect and it belongs to the spec:
  a module that shells out to the CLI raises the warning count by one the
  moment it is committed, so a baseline recorded before it existed is falsified
  by the act of adding it. Measured: a spec's Assumptions held 3, the base
  commit already carrying the checking module reported 4, and the 4th was that
  module. §6 now carries the rule — never pin an exact warning or error count
  from a module that itself trips the lint being counted; assert on the warning
  you mean by matching it, not on how many there are — and the delivered §6
  skill carries both.

## [1.29.1] — 2026-09-01

### Changed

- **The `.gitattributes` eol-pin lint says what its silence does not mean
  (issue #124).** It has two causes of silence and documented only one. The
  first is resolution — a path built from a `tmp_path` or a function argument
  is skipped — and §6 already said so. The second is *shape*: a committed text
  artifact whose tests `json.loads` it, or walk a Markdown table cell by cell,
  matches no byte-exact read and draws no warning **whether or not it is
  pinned**. That is the silence that misleads, because such a file looks
  exactly like the kind the lint exists for. Recorded: a spec wrote "the
  eol-pin lint passes" as an acceptance criterion for a committed generated
  JSON artifact, which was vacuous by construction, and the pin had to be
  asserted by a project-side test instead.

  **The lint is not widened, deliberately.** `read_text()` applies
  universal-newline translation, so a CRLF-rewritten file parses to the
  identical object — covering the shape would be wrong rather than merely
  noisy. What the file may still need the pin for is a byte-reproducibility
  claim made somewhere the lint cannot look, and that claim is the project's to
  assert directly. §6, the two docstrings, and the delivered §6 skill now say
  this; §6 adds the operative instruction — never write "the eol-pin lint
  passes" as an acceptance criterion, assert the pin itself — and three tests
  pin the behaviour as a decision rather than an accident, including the
  boundary case where one `==` on the bytes makes the same artifact report.

## [1.29.0] — 2026-09-01

### Added

- **§6 states the subprocess `encoding=` rule, and `aide check` lints it
  (issue #126).** Six items in one consumer queue each independently wrote
  `subprocess.run(..., capture_output=True, text=True)` with no `encoding=`.
  All six passed the Linux-only validator — `locale.getpreferredencoding()` is
  UTF-8 there — and `windows-latest` decoded the same bytes as cp1252: a
  `KeyError` on a mangled em-dash heading in one test, and in another an
  emoji-diff guard that **matched nothing and reported PASS**. The second is a
  false negative, a gate green having verified nothing, and §7 says no gate
  inside the loop ever sees the platform that produces it. Six authors
  reproducing one shape in one queue is the signature of a missing rule, so §6
  now carries it: *a test that captures subprocess output as text passes
  `encoding="utf-8"`.* `subprocess_encoding_test_warnings` decides it by AST,
  in the shape of the eol-pin lint beside it — a `run`/`Popen`/`check_output`
  call carrying `text=` or `universal_newlines=` and no `encoding=`. Narrowed
  twice so every warning names a call that really would decode: `call` and
  `check_call` return an exit status and never a capture, and a literal
  `text=False` asks for bytes. Its limit is stated rather than left to be
  found — only direct calls are seen, so a suite that wraps its subprocess
  calls in a helper shows the lint one call site and hides the rest.

### Fixed

- **The engine decoded git and `gh` output with the platform's locale codec.**
  The rule above was already broken where it is written: `git()`,
  `aide env`'s profile check and `aide status`'s open-PR listing all passed
  `text=True` and named no codec, so on a Windows consumer a branch name, a
  changed path, a traceback or a PR title came back as different characters
  than here — and a prefix match against a mis-decoded branch name quietly
  stopped matching. All three now decode UTF-8 explicitly, with
  `errors="replace"` so a stray byte in one ref cannot raise out of
  `aide claim`. This repo's own suite carried the same shape in nine helpers;
  those are fixed too, strictly, because in a test a byte that will not decode
  is a finding rather than something to paper over.

### Changed

- §6's closing paragraph claimed the absolute-path rule was "the one rule here
  a script can decide". Three lints had already made that false and this
  release makes five; it now names the five and says plainly that the rest of
  the section binds identically and is checked by nobody.

## [1.28.1] — 2026-08-31

### Fixed

- **A declared dependency retires the `changes-pinned-state` error it makes
  inert (issue #106).** `aide check --queue NNN` reported one item's **May
  change** against another's **Asserts against** without consulting the
  ordering the specs themselves declare, so a `Validate stage N` item drew the
  error against every sibling it exists to observe — 14 of them on one consumer
  queue — and both remedies the message named were wrong for that shape:
  widening the pin drops the artifacts the item was written to pin, and
  narrowing the earlier edits removes the stage's whole point. When the pinning
  item names the changing one under `## Dependencies`, directly or through a
  chain of them, it is authored and built against a tree that already holds
  that edit, so the edit landing cannot break its pin; that pair is now
  skipped. Only links that still **order** the two items count: a dependency
  `aide claim` no longer waits for — ✅ merged, ❌ excluded, ⏸️ deferred —
  leaves the dependent claimable today, so a deferred blocker earns no
  exemption (its edit is dormant, not spent, and still lands ahead of the
  pin), and neither does a chain whose middle link is one. The exemption is per pair and directional — an item that depends on
  the pinning item builds *last*, so its edit does land after the pin and is
  still reported — and a pair with no declared dependency keeps the error,
  since an undeclared ordering is exactly what the check exists to find. The
  1.23.0 spent-item discount covered this only once the siblings merged, which
  is after the window the check is for. Deriving the order walks the same edges
  the cycle check condemns, so it is cycle-safe: a mutual pair still reports
  `dependency-cycle` rather than hanging the run that would have found it.
- **§1 said a dependency stops blocking at ✅/🚧; it stops at ✅.** `aide claim`
  and every other blocking call site treat 🚧 in-progress and 🔍 in-review as
  open — an item still being built, or one whose PR is still awaiting a human,
  is not in the base a dependent would branch from — so only ✅ merged, ❌
  excluded or ⏸️ deferred clears the way. Found while correcting the sibling
  "must be ✅/🚧" guidance below, and wrong in the same direction: a reader
  who believed it would expect a dependent to be claimable the moment its
  blocker started.
- **The error message names the third remedy.** Alongside widening the pin and
  narrowing the edit, it now says to declare the dependency when the pinning
  item is genuinely built after the changing one — the fix that both orders the
  queue and clears the finding. The item template, `spec-author` and
  `/aide-create-item` said dependencies "must be ✅/🚧", which reads as
  forbidding exactly that on a specs queue where every sibling is still 📋;
  they now say a 📋 queue-mate is a legitimate entry (`aide claim` holds the
  item until it lands) and that declaring one is how an item records that it
  pins what a sibling produces.

## [1.28.0] — 2026-08-31

The instruction-load report gets an entry point (issue #82), and the delivered
context names the verbs that own the insight inbox (issue #95, shape 2 —
closes it).

### Added

- **`/aide-review-instructions`** (`.claude/commands/aide-review-instructions.md`),
  mirroring `/aide-review-permissions`: run
  `.claude/scripts/review_instructions.py`, judge each silent rule on what it
  is — a framework rule is unscoped and loads in every context, so silent over
  a non-empty log means the hook or the trust flag; a project's own `paths:`
  rule is silent whenever no logged session read a matching file, so confirm
  its globs; a retired rule is not a fault — say what the report cannot say
  (it measures delivery, not reading, and never sees a preloaded section
  skill, whose reach is structural), and rotate the log. #79 shipped the
  instrument with no way to invoke it: a Python file in `.claude/scripts/`
  nobody was told about, which left a silently inert rule exactly as
  invisible as before. `/aide-feedback-loop` step 4 now runs it at the queue
  boundary beside the permission review, and `/aide-run-queue`'s hand-off
  names it.
- **`review_instructions.py --rotate [--reviewed PATH]`** archives the current
  log into `log.reviewed.jsonl` beside it — `docs/aide/instructions/` for the
  default log, under the same managed `.gitignore` glob; beside whichever log
  was named otherwise, so another checkout's records never land in this
  project's archive — and truncates the live one, the way the permissions
  reviewer does. A log that only grows makes "never loaded" mean less each
  session, since it averages over sessions from before a glob was last
  changed. The empty-log hint names rotation as a third cause beside the trust
  flag and a fresh install, so a just-rotated log does not read as a broken
  hook. **`--strict` stays a human-invoked check and now says so** in its
  `--help`, the module docstring and the command: the log has no notion of
  which sessions *should* have armed a rule, so over an arbitrary log a scoped
  rule false-alarms by construction; reach is asserted structurally in
  `tests/test_structural_budget.py` instead. It is never wired into CI. Over
  an empty or missing log `--strict` now exits 1 — nothing loaded there
  either, and it used to pass the one log it could say nothing about — and a
  log path that does not exist is named as such before the hint, since a
  mistyped path must not read as a clean, empty log.

### Changed

- **The delivered context names the insight verbs where the edit happens
  (issue #95, shape 2).** Shape 1 (1.25.4) put every verb on the floor's CLI
  line, so the verbs were *listed* in every context; nothing delivered said
  which edit they own. The floor's inbox section still said "ticking its
  checkbox is the one in-place edit" without naming what performs it, and the
  `aide-living-documents` skill named the owning verb for `progress.md`,
  `queue` and gates but not for `insights.md` — the pairing of verb to edit
  lived only in `/aide-feedback-loop`, which no loop role preloads. Now
  `AGENT-CONTEXT.md` says the edit is `aide insights tick N --pointer`'s, and
  the skill carries the section's own rule — *capture is a plain append;
  everything after it has a verb* — with `list`, `tick` and `archive` and the
  observed failure's shape named: a hand-flipped `[x]` is the improvised form
  of `tick`. Two new pins on §1 → `insights.md`.
- The always-on floor moves from 7,532 to 7,578 content bytes, all of it the
  verb's name; `FLOOR_PIN` follows. Per spawn, structurally: builder 12,304 →
  12,350, queue-planner 17,080 → 17,762, spec-author 16,461 → 17,143,
  spec-reviewer 15,792 → 15,838, test-writer 14,511 → 14,557, validator
  16,066 → 16,112 — the two document writers pay the skill's new paragraph,
  everyone pays the floor's 46 bytes.

### Fixed

- **Both review commands rotate the log they reviewed.** Step 5 of
  `/aide-review-permissions` ran `--rotate` with no log argument, so a review
  of a log named by argument archived and truncated the *default* log —
  records nobody had read — and left the reviewed one un-rotated. The new
  `/aide-review-instructions` inherited the shape; both now carry the same
  argument into the rotation and say why.
- **`review_instructions.py` reads a BOM-prefixed log.** It read the log as
  strict `utf-8` where `review_permissions.py` reads `utf-8-sig`; a log
  re-saved by a Windows editor lost its first record from the report — on a
  one-session log, the whole report — and `--rotate` would have archived the
  BOM inline. Both reads now use `utf-8-sig`.

## [1.27.0] — 2026-08-30

The carrier swap (issue #85, scope item 3): §6 and the §1 document shapes are
delivered **to roles by `skills:` preload**, not to files by `paths:`-scoped
rules. The rules were measured against a real consumer on 1.22.0, over two
loop sessions: `aide-living-documents.md` armed **29 and 24** times,
`aide-test-hygiene.md` **21 and 13** — roughly 201 KB and 150 KB of scoped-rule
text on top of the floor — because a `paths:` rule fires inside sub-agent
contexts on any matching *read*, and reading an item spec matches the same
globs as writing one. Six roles read the living documents; two write them.
Builder and validator open tests they never write. And the one role that
always needs §6, `test-writer`, could miss it entirely: a repo with no tests
yet gives a read-armed rule nothing to fire on, exactly when the fixture
conventions are being set.

### Added

- **Two section skills**, `.claude/skills/aide-living-documents/SKILL.md`
  (the §1 shapes) and `.claude/skills/aide-test-hygiene/SKILL.md` (§6): the
  bodies of the two rules, `user-invocable: false` (hidden from the `/` menu,
  never a command, still preloadable — `disable-model-invocation: true` would
  be silently refused at preload), carrying the same `paths:` the rules had.
  On a skill, `paths:` injects nothing on a read (measured, #85): the skill's
  one-line description is in an interactive session's listing regardless, and
  the globs only narrow when the runtime auto-invokes the skill on its own —
  so each description is written as a trigger and is the whole of the
  interactive delivery. The `<!-- reach -->` and `<!-- pins -->`
  blocks stay in the skill bodies; a preload strips HTML comments, so they
  cost the loop nothing.

### Changed

- **Three agent specs preload their section.** `spec-author` and
  `queue-planner` list `aide-living-documents` in `skills:`; `test-writer`
  lists `aide-test-hygiene`. The body is injected at spawn, before the role
  has opened anything, so `test-writer`'s "read §6 yourself, because a repo
  with no tests gives the rule nothing to fire on" clause is gone — the
  section is in its context from the first token. The other three roles get
  neither: they read the documents and tests without writing them, and
  `validator` keeps the one line about §6 it needs. Per spawn, structurally
  (content bytes, `tests/test_structural_budget.py`): builder 16,563 → 12,304,
  queue-planner 18,762 → 17,080, spec-author 18,143 → 16,461, spec-reviewer
  20,051 → 15,792, test-writer 19,961 → 14,511, validator 20,325 → 16,066.
  **The always-on floor is unmoved** at 7,532 content bytes; `FLOOR_PIN` stays
  at 1.25.4.
- **`ADAPTER-SPEC.md` §7 gains the channel guidance**, in runtime-general
  terms: an always-loaded channel for what binds every action (§3); a
  role-declared channel for what a role always needs (§6 for a test author,
  the §1 shapes for a document writer); a file-scoped channel only where it
  cannot fire inside a spawned role, otherwise it is an unconditional channel
  wearing a scope. A role-declared channel satisfies "loads without being
  chosen" fully and has nothing to measure behaviourally, only structurally.
  The three test modules generalise from "rule files" to "delivered files"
  (rules plus section skills, recognised structurally): reach is literal for a
  skill — the specs whose `skills:` list it — and the glob evaluation is
  printed as its interactive trigger, never asserted. New guards: every
  `skills:` entry names a skill that exists and is preloadable, and every
  section skill is preloaded by at least one agent.

### Removed

- **`.claude/rules/aide-test-hygiene.md` and
  `.claude/rules/aide-living-documents.md`.** `install.py --update` deletes
  both from a consumer — by the manifest where one exists, and by
  `RETIRED_ADAPTER_PATHS` for every consumer installed before 1.27.0 —
  and `--check` names them first. No replacement `paths:` rule for the
  interactive session: it would fire inside sub-agent contexts and re-pay
  exactly the cost this removes. `aide-command-hygiene.md` stays, unscoped.

What a consumer sees: after `--update`, two rules are gone from
`.claude/rules/` and two skill directories appear under `.claude/skills/`;
three agent specs gain a `skills:` line; the `/` menu is unchanged; an
interactive session working on a test or a living document sees the section
skill listed by its trigger; and every sub-agent spawn is cheaper except the
three that now carry their section unconditionally.

## [1.26.0] — 2026-08-30

The engine guarantees the insight inbox exists (issue #85, scope item 4).
Every one of the six agent specs carried the same clause — *"create it from
`.aide/templates/insights.md`, copied verbatim, if missing"* — and so did
`aide-execute-item`, §1 → `insights.md` and the template's own header: one
mechanical step restated eight times, and the one restatement that made every
spec name `templates/`, which is what stops a template-scoped delivery from
discriminating by role. Capture was meant to be a plain append; the engine
now makes that literally true.

### Added

- **`aide check` creates a missing `insights.md`** — a byte-exact copy of
  `.aide/templates/insights.md`, committed where git can (on a branch, with
  an identity to commit as; otherwise left untracked with the reason in the
  notice), announced in one `notice:` line. It is the verb's only write
  besides the file `--report` names, and its docstring and `--help` say so;
  the exit code never depends on it. Nothing happens when `docs_dir` is absent (a repo
  may adopt the CLI without the loop, and the directory itself is
  project-owned), and an existing inbox — malformed or not — is never
  touched. A missing template is reported as an incomplete install, not a
  traceback.
- **`aide claim` and `aide queue start` do the same**, through the one
  shared helper (`ensure_insights_inbox`), on the branch they just created
  and before the push. `check` alone was not enough: `/aide-run-queue`
  reaches its roles through `sync` → `claim`, and `/aide-run-roadmap`
  (queue-planner) and `/aide-spec-queue` (spec-author, spec-reviewer) through
  `queue start`, none of which runs `check` first. Both verbs already write —
  a branch and its recorded base — so the file arrives where the item or
  queue lands and the base branch is left as it was. The creation is
  committed because `aide sync` refuses a dirty tree, and an untracked new
  file would stall the next preflight of the loop it exists to serve. The
  commit names its path (`git commit -- <path>`), so a builder's staged work
  stays staged and out of it; a commit git refuses leaves the file untracked
  rather than staged; a detached `HEAD` gets the file and no dangling commit;
  a `git` that cannot be run is a sentence in the notice, not a traceback.
- **`aide insights list` on a missing inbox creates it** the same way and
  reports an empty backlog, since an empty backlog is an answer. `tick` and
  `archive` still exit 2 on a missing file — there is no entry to edit — but
  the message now points at `aide check` instead of telling a role to copy
  the template by hand.

### Fixed

- **`progress set`, `insights tick` and `insights archive` committed
  everything staged, not the path they named.** The shared committer staged
  its path and then ran a bare `git commit`, so a builder's staged-but-
  uncommitted work was swept into the bookkeeping commit mid-item — the
  docstring said "named paths, never `git add -A`" and the code did the
  equivalent. The commit now carries a pathspec (`git commit -- <path>`):
  only the named path lands, other staged content stays staged, a refused
  commit unstages the path again rather than leaving it staged for
  `aide sync` to stall on, and a `git` that cannot be run is one framed
  stderr line instead of a silent success message. Found reviewing the inbox
  creation above, which uses the same committer.

### Changed

- **The six agent specs and `aide-execute-item` drop the create-if-missing
  clause.** Each "Out-of-scope insights" section now says only: append ONE
  line to `docs/aide/insights.md` and carry on. §1 → `insights.md` states
  the guarantee in the engine's terms (which verbs, byte-exact, committed),
  and the template header no longer instructs a copy. A test in
  `adapters/claude/tests/test_rules.py` fails if any agent or skill names
  `templates/insights.md` again — guarded on the path, not the wording, since
  a reworded restatement re-opens the same cost. The always-on floor is
  unmoved: `AGENT-CONTEXT.md` already described capture as an append and
  gains nothing; `FLOOR_PIN` stays at 1.25.4's number.

What a consumer sees: after `--update`, the next `check`, `claim` or
`queue start` in a document set without an inbox creates and commits one, and
prints the notice; six agent specs each shrink by a line; nothing else
changes. Item 1 of the #85 scope (the installer manifest) lands separately.

## [1.25.5] — 2026-08-30

The consumer-visible half of the review of the #83/#84/#81/#97/#95 batch. All
three are wording; no verb, flag, output or grammar changed. The rest of that
review lands in this repo's own tests and adapter docs, which no consumer
receives.

### Fixed

- **The CLI line in `AGENT-CONTEXT.md` no longer ends two lines with a
  trailing `|`.** Inside a fenced block that is what a shell line continuation
  looks like, so the verb list read as one long pipeline rather than as a
  choice of twelve. The separators now lead the wrapped lines instead of
  trailing them — a leading `|` cannot be shell. Byte-neutral: the always-on
  floor stays at 7,532 content bytes and `FLOOR_PIN` in
  `tests/test_structural_budget.py` is unmoved, bytes and version both.
- **The ticked-entry example in `templates/insights.md` carries the engine
  version.** 1.25.3 added `, engine X.Y.Z` to the entry shape at the top of the
  file and left the triage example below it spelling the marker the old way, so
  the convention appeared and then vanished within one comment — and the
  example is the copy a role writing a tick actually looks at.
- **`aide.py` documents the one character an insight's trailing note cannot
  hold.** The note is free-form up to `)`, which closes the marker, so
  `engine 1.2.3 (rc1)` fails to parse — a permanent shape warning on an
  immutable line, and a lost date. The grammar is unchanged (widening it would
  swallow the marker); the constant now says so where the next author will
  read it.

## [1.25.4] — 2026-08-30

### Changed

- **`AGENT-CONTEXT.md`'s CLI line now names every verb the engine ships (issue
  #95, shape 1 of two).** It listed six of twelve; `insights`, `env` and
  `status` appeared nowhere in delivered context at all. `gate`, `queue` and
  `gc` did appear, but only in passing inside a `.claude/rules/` file — `queue
  start` and `gc` among the verbs `aide-command-hygiene.md` names to say the
  raw git form is wrong, `gate` and `queue tidy` among those
  `aide-living-documents.md` names to say prefer the verb to a hand edit — and
  never in the one place a role reads to learn what the CLI *is*, which is what
  makes an unnamed verb unreachable. Issue #78 measured a pointer to
  `conventions.md` as followed about 3% of the time — a verb no always-loaded
  file names effectively does not exist. On 2026-08-29 in
  consumer `spine-failure-lab` a role asked to triage the insight inbox read
  `docs/aide/insights.md` raw, unaware of `aide insights list --open`; closing
  an entry would have been a hand-edit of the checkboxes that
  `aide insights tick N --pointer` owns. The line now reads
  `check | status | env | sync | claim | scope | merge | gc |
  progress set/accept | gate list/approve/decline | insights list/tick/archive
  | queue start/tidy`, with a subcommand hint only where the subcommands are
  the whole interface. Naming alone: no verb, flag or output changed. Issue #95
  stays open for shape 2 — naming the owning verb in each document's delivered
  rule — which belongs with the #85 delivery restructure.
- The always-on floor moves from 7,421 to 7,532 content bytes, all of it that
  line. `tests/test_structural_budget.py` carries the new number.

## [1.25.3] — 2026-08-30

### Added

- **An insight entry may now name the engine version it was observed under
  (issue #97).** The marker recorded where a finding came from and when, never
  which engine was running — a value sitting on disk as `.aide/VERSION` at the
  moment of capture. The date cannot stand in for it: a project runs an engine
  for as long as it likes after a release, so two entries captured the same
  week may sit either side of a restructure. On 2026-08-29 eight `framework`
  issues landed upstream across the 1.21.0 → 1.22.0 restructure and no entry
  said which side it came from, so every older-engine claim was re-verified by
  hand. The conventional spelling is now
  `*(item NNN, YYYY-MM-DD, engine X.Y.Z)*`, documented in `conventions.md`
  §1 → `insights.md`, the `insights.md` template header and `AGENT-CONTEXT.md`,
  and carried by the capture shape the six agent specs and
  `aide-execute-item` print at the point of capture — a shape line that
  disagreed with the always-loaded one would be followed instead of it.
  Guidance, not grammar: optional, unenforced, and never retrofitted onto an
  entry captured without one, since the claim line is immutable.
- **`/aide-feedback-loop` §0 carries the version into the issue it files.** A
  `framework` entry becomes a GitHub issue in a repo that cannot see this one,
  so the body now names the engine the observation was made under — from the
  entry, or from `.aide/VERSION` at triage time *explicitly marked as the
  fallback it is*, because an unmarked guess reads there as an observed fact.
  Stated in `conventions.md` §1 → `insights.md`, delivered by the skill.

### Changed

- **`aide check`, `insights list`, `tick` and `archive` accept the trailing
  component.** Without this the new spelling was not merely undocumented but
  actively rejected: the entry pattern required `)*` immediately after the
  date, so a versioned capture drew a permanent shape warning *and* failed to
  parse — losing its date, which is what `archive` cuts on, and what `tick`
  refuses to guess at. What follows the date is now parsed as
  `InsightEntry.note` and reprinted verbatim by `insights list`, which is where
  triage reads the backlog from. Free-form, for the reason issue #76 widened
  the provenance and sharper here: entries predate the convention, and a
  rejected spelling is a warning the immutability rule leaves no way to clear.
  The date itself did not relax on either side.
- The always-on floor moves from 7,268 to 7,421 content bytes: two sentences in
  `AGENT-CONTEXT.md`, which is the copy a role actually reads at capture time —
  a convention absent from it is a convention nobody follows.
  `tests/test_structural_budget.py` carries the new number.

## [1.25.2] — 2026-08-30

### Fixed

- **A delivered rule now quotes its section, and a test holds the two copies
  in step (issue #81).** `.claude/rules/` restates `conventions/` by design, and
  a restatement drifts — the PR that forbade adapter-invented rules shipped two
  of them and a human caught both by reading two files side by side. Each rule
  file now carries `<!-- pins: <section file> … -->` blocks quoting the
  normative statements it delivers, and
  `adapters/claude/tests/test_rule_pins.py` asserts each quoted statement
  appears in the rule *and* in the section it names, after a normalisation that
  absorbs reflow, emphasis and case and nothing else. It fails in both
  directions and every rule must pin at least one statement, so a new rule
  cannot ship unguarded. Thirty-five pins across the three rules.
- **`aide-living-documents.md` listed three status icons the engine does not
  have, and mis-stated where icons are read.** It gave the six as `✅ Done`,
  `⏸️ Blocked` and `❓ Unverified` where `§1 → status-icons.md` defines
  `✅ Complete`, `⏸️ Deferred` and `❌ Excluded` — `❓ Unverified` is
  table-local vocabulary for Outcome targets and env-gated capabilities, never
  a stage or deliverable status, and `❌ Excluded` was missing entirely. It then
  named the three structural positions as "an objective heading, a stage
  heading, and the leading character of a deliverable bullet" and added that a
  table cell is prose — contradicting the engine, where a table row's Status
  (last) cell *is* one of the three. A role writing `progress.md` from the rule
  alone would have produced a document `aide check` rejects. Both now quote
  `status-icons.md`.
- **Two rules the Claude adapter enforced were missing from `conventions.md`
  §3.** The hook and the rule blocked `||` as a chaining operator and allowed a
  single `|` pipe; §3 named only `&&` and `;` and said nothing about pipes. The
  rule also required Python and pytest to run from the project venv by relative
  path (`.venv/Scripts/python -m pytest` / `.venv/bin/python -m pytest`), which
  appeared nowhere under `core/`. Both are runtime-general, so both are now
  stated in §3 and delivered from there, per ADAPTER-SPEC §7's "carries no rule
  the engine does not have". No behaviour changed; the engine caught up with
  what was already enforced.

### Changed

- The always-on floor moves from 6,324 to 7,268 content bytes: the pin block in
  the unscoped `aide-command-hygiene.md` is paid on every spawn, like the rest
  of that file. Recorded rather than absorbed — it is the price of the drift
  check, and `tests/test_structural_budget.py` carries the new number.
- `ADAPTER-SPEC.md` §7 states how the last two of the three delivery
  obligations are made checkable, so another runtime knows what the guarantee
  is rather than how this adapter spells it.

## [1.25.1] — 2026-08-30

### Added

- **Every `.claude/rules/*.md` now declares the reach it expects, and a test
  checks it (issue #84).** A one-line `<!-- reach: … -->` comment names the
  agent roles a rule expects to arm for; `tests/test_structural_budget.py`
  installs into a temp directory, extracts each role's read-set from the
  delivered agent specs, evaluates the rule's `paths:` globs against it, and
  fails on a mismatch. The first measurement confirms what 1.22.0 noted in
  prose and nothing enforced: `aide-living-documents.md` is scoped to document
  names all six roles read, so its `paths:` block scopes it to nobody and
  every spawn pays for it. That is now recorded in the rule itself and checked
  on every run, instead of resting on a human doing the arithmetic. The
  always-on floor (`AGENT-CONTEXT.md` plus every
  unscoped rule) is pinned per file, failing in both directions, so it cannot
  move without a deliberate edit; totals are printed as diagnostics rather
  than asserted against a threshold. Rule bodies gained the comments; no rule
  changed scope, wording or behaviour.
- The always-on floor moves from 5,996 to 6,324 content bytes: the declaration
  this release adds to the unscoped `aide-command-hygiene.md` is itself paid on
  every spawn. The instrument costs something, and the first number it records
  is its own — so it is stated here like every later move of it.

## [1.25.0] — 2026-08-30

Root-document authoring gets its missing gate and its missing posture
(issues #86, #87) — filed together from one consumer session that wrote a
`vision.md` free-hand, on assumptions, and was caught by nothing.

### Added

- **`aide check` now warns on a root document missing the sections its
  template marks MANDATORY (issue #86).** `templates/vision.md` has promised
  for its whole life that a validator checks *Guiding principles*, the G-code
  objectives table, *Out of scope* and *Success criteria*; `templates/roadmap.md`
  the same for the objective → stage coverage table and the `## Stage N`
  sections. No code kept the promise — a vision with none of them passed. One
  warning per dropped piece, tolerant of renumbered or re-cased headings.
  Warnings, not errors, matching the mandatory-Assumptions lint: existing
  root documents must not start failing unattended runs, and the
  queue-boundary human reads warnings. Absent files stay silent (partial
  adoption is a choice, not a defect).
- **§5 now states what `loop.clarify` does *not* govern (issues #86, #87).**
  The setting reads as a global asking-versus-assuming posture and is not one:
  it scopes to `spec-author` on queued items, whose assumptions land in an
  audited block. Root documents are authored through their loop entry point,
  interactively, whatever the setting says — a wrong assumption at the root
  has no audit surface and propagates into everything derived from it. Stated
  in `conventions/5-clarify-mode.md`; delivered always-on via
  `AGENT-CONTEXT.md` (the channel that reaches the general chat session where
  the observed failure happened) and to anyone opening a root document via the
  living-documents rule; restated as an *Asking posture* section in the
  create-vision and create-roadmap skills; and the scaffolded `aide.toml` now
  comments `clarify` as queue-execution-scoped so it cannot be read as a
  global posture.

## [1.24.1] — 2026-08-29

Two frictions hit by real sessions working across or committing from a
consumer (issues #88, #93).

### Fixed

- **The command-hygiene guard no longer reads heredoc body prose as shell
  operators (issue #88).** The guard blanks quoted spans precisely so a `;` or
  `&&` inside a commit message never false-positives — but a heredoc body got
  no such treatment, so `git commit -F - <<'EOF'` with a multi-paragraph
  message (the exact artifact the framework asks agents to write) was blocked
  for a semicolon in its prose, with advice pointing at the wrong thing.
  Heredoc bodies are now blanked before the operator lints, and blanked
  *before* quote-blanking so a prose apostrophe cannot open a phantom quote
  that hides real syntax after the terminator. Rule 4 keeps watching the one
  thing that IS live in a body: `$(…)`/backtick substitution under an unquoted
  delimiter (`<<EOF`); under a quoted one (`<<'EOF'`, `<<"EOF"`, `<<\EOF`) the
  body is fully literal and stays invisible. Here-strings (`<<<`) have no body
  and are untouched. Because a phantom opener's "body" would run to the end of
  the input and exempt everything after it from every rule, a `<<` is only an
  opener in redirection position, outside quotes and outside `((…))`
  arithmetic — a shift, a quoted mention, or prose never silences the guard —
  and a CRLF command's `\r`-suffixed terminator still ends its body. Rule 1's
  path-value scan reads bodies as blanks too, so a commit message *naming*
  `--git-dir` is not read as a second repo blocking the declared-sibling
  commit shape.

### Changed

- **The aide CLI's sibling-repo shape is now stated, delivered, and pinned
  (issue #93).** The hygiene carve-out for a declared sibling covered git's
  repo-override flags but no aide-CLI equivalent was documented anywhere — a
  session validating a declared sibling's documents had no shape to reach for
  (one resorted to a `runpy` + `os.chdir` workaround). The CLI has had a
  global `--repo <root>` flag all along; what was missing was the contract. §3
  now names the approved shape —
  `python <sibling>/.aide/scripts/aide.py --repo <sibling> <cmd>`, the
  sibling's *own* install so its documents are judged by the engine that ships
  with them, with `--repo` mandatory because the cwd walk would resolve to the
  wrong repo — §8 points at it, the Claude adapter's command-hygiene rule
  delivers it, and the guard's rule-1 bounce message offers it as the
  self-correction when a `cd <sibling>` is blocked. The fixture-consumer suite
  pins that `--repo` beats a cwd sitting inside a different consumer.

## [1.24.0] — 2026-08-29

Two mis-attributions the loop could author into itself, both observed on real
consumer queues (issues #94, #99).

### Changed

- **Only a bullet's trailing `*(Item NNN)*` marker attributes status (issue
  #99).** §1 always called the marker "the suffix [that] ties an item to the
  bullet", but the parser attributed a bullet's status to every reference form
  anywhere in its prose — so a ✅ bullet mentioning a live sibling
  ("absorbing *(Item 095)*'s scope") marked that sibling complete, overriding
  its own 📋 bullet. Since 1.23.0 discounted spent items from the cross-spec
  checks, the mis-attribution went further and silently dropped the live item
  out of the authorised-path comparison, the cycle graph, and the
  undeclared-scope/unknown-dependency warnings. Read and write now share one
  ownership rule: `check`/`status`/`claim` attribute from the trailing marker
  alone, `aide progress set` flips only the bullet whose marker names the
  item (and self-heals or errors, loudly, when none does), and a new
  `aide check` warning names any bullet whose references all sit mid-prose —
  such a bullet tracks nothing. Prose references stay free text by design.
  Two hardenings from review: the self-heal back-fill now inserts after a
  wrapped bullet's whole span instead of splitting it at the icon line —
  under the marker rule that split stranded the healed marker mid-span and
  re-owned the wrapped bullet's — and `progress set` verifies the item
  actually attributes before writing, erroring instead of printing success
  over a recording that did not happen.

### Added

- **`aide check` warns when a spec lists the same path under both May change
  and Asserts against (issue #94).** Asserts against means pinned-not-changed
  — `aide scope` prints exactly that — so the double-listing guarantees a
  contradiction the moment the item uses its own authorisation, with no
  spec-side fix visible at validation time. The warning fires at spec time,
  where the author can act: a file the item writes and then asserts against
  belongs only under May change, with the assertion behaviour in prose. The
  exact listing alone is flagged; a literal pin under a May-change glob is the
  deliberate carve-out shape and stays for `aide scope` to judge. `aide scope`
  itself is unchanged — the check stays strict. Conventions §1 →
  authorised-paths and the item template now state the rule.

## [1.23.0] — 2026-08-29

Four `aide check`/`scope` findings that could never be cleared, all observed on
one consumer queue (issues #89–#92). None changes what a passing repo sees.

### Added

- **`aide check` warns when a spec pins an always-authorised path (issue
  #90).** `progress.md`, `insights.md` and the insight archives are edited by
  the loop on every item — the mandatory status flip alone touches
  `progress.md` — so a pin under *Asserts against* can never hold, and
  `aide scope` failed such items on their routine bookkeeping. Pinning
  progress.md is the natural way to write an AC that reads a gate row, which
  is exactly why the warning fires at spec time, naming the remedy: put the
  read-only content check in an acceptance criterion's test. Conventions
  §1 → authorised-paths and the item template now say the same.

### Changed

- **Gate warnings say how much a gate holds (issue #89).** The `aide check`
  warning for an awaiting or declined `stage N` gate resolves the reach the
  way `aide claim` already does — "stage 28 — holding 8 item(s): 118, …" — so
  a mis-scoped gate is visible where it is authored instead of when a runner
  stalls on it. The breadth was computed at check time all along and thrown
  away. The count covers only items the gate still sits in front of — ✅ and
  ❌ ones are not "held", and a stage whose every item merged falls back to
  the bare reach; item-list and `all` reaches already name what they hold and
  are unchanged.

### Fixed

- **Cross-spec comparison and the cycle check discount spent items (issues
  #91, #92).** `aide check --queue` compared every spec against every other
  for the queue's whole life, so a merged item's spent May-change claim
  collided forever with each later spec touching the same file, and a
  dependency cycle whose members had all merged — proof the order was
  satisfiable — stayed an error no later item could clear without editing a
  completed item's spec. Spent items — ✅ merged or ❌ excluded — now drop out
  of both sides of the authorised-path comparison, and out of the
  `undeclared-scope` and `unknown-dependency` warnings, whose remedies are
  likewise unavailable once an item merged. The cycle graph keeps only items
  whose status still blocks a claim (the same set `aide claim` enforces, so
  ⏸️ deferred drops out of it too); deferred items stay in the path
  comparisons, since their claims are dormant, not dead. What remains is
  exactly the set of live conflicts the check exists to find.

- **A quoted gate reach is no longer read as dependency edges (issue #92).**
  In `## Dependencies`, item numbers on a line at or after a backticked or
  bold `Blocks:` label are excluded from the blocker scan, so transcribing a
  human-gate row's reach ("waits on Gate 3 — `Blocks: items 119, 120, 121`")
  no longer grows edges nobody authored — edges that blocked `aide claim`
  and yielded cycles in `aide check --queue`. The markup is what makes it a
  marker: plain-prose "blocks:" excludes nothing, so an English sentence
  naming real blockers is never silently dropped. Numbers before the marker
  on the same line still block, and the `**Downstream` rule is unchanged.

## [1.22.0] — 2026-08-25

### Changed

- **`conventions.md` is now an index; its sections are files (issue #78).**
  Each numbered section moved to `conventions/N-*.md`, and §1's document shapes
  to `conventions/1-format-contract/*.md`, so the pointer form already used in
  a hundred places resolves to a file: `§6` is `conventions/6-test-hygiene.md`,
  `§1 → insights.md` is `conventions/1-format-contract/insights.md`.
  `conventions.md` keeps its path and its opening line and now carries the
  section table.

  The move is content-preserving except in three places, all deliberate: the
  opening paragraph (below), and the §3 and §6 preambles, which now state the
  delivery obligation. No other prose changed, no heading level moved, and no
  fenced example was split across files.

  **A slicing read of the old file no longer works.** Agents were measured
  accessing `conventions.md` exclusively by `offset`/`limit` or
  `sed -n '60,100p'`; every one of those now returns index prose or nothing.
  It fails loudly rather than silently, but it is the most visible day-one
  change for a human with the habit.

  Its opening paragraph claimed "three parts" while the file had eight
  sections, and had been wrong since the bootstrap commit — §4 and §5 already
  existed there. Nobody caught it because nobody reads this file top to bottom,
  which is the same fact the rest of this entry is about. The index replaces
  the sentence rather than correcting it.

- **The Claude adapter delivers contract sections instead of pointing at them.**
  Measured across 11 sessions of a consumer on engine 1.20.0, **164 sub-agent
  spawns produced 5 reads of `conventions.md` — about 3%**, every one a slice.
  A pointer is followed only if the reader chooses to, so what was actually
  binding was the command-hygiene block restated verbatim in all six agent
  specs; one of the six had already drifted.

  **Rules that were nominally binding were not reaching agents at all.** Two
  gaps, both checkable against 1.21.0 rather than inferred:

  - §3's *first* rule — "if an `aide` verb covers it, the raw git form is
    wrong" — appeared in **none of the six** agent specs. The rule most likely
    to make an agent improvise `git switch -c` instead of `aide claim` was
    delivered to nobody.
  - The **six status icons** and the rule that they are read at three
    *structural* positions only appeared in `queue-planner` and `validator`.
    `builder`, `spec-author`, `spec-reviewer` and `test-writer` had none of it,
    and neither did `AGENT-CONTEXT.md` — the one file loaded into every
    context. `builder` sets 🚧 and `spec-author` adds a human-gate row by hand,
    both against a document shape they were never given.

  In both cases the contract existed and was reachable only by following a
  pointer, which measurement puts at about 3%. So this is a **functional fix**
  first: agents now receive rules they were previously missing. Eliminating the
  drift between six hand-maintained copies is the second benefit, not the first.

  New `adapters/claude/rules/` (installed to `.claude/rules/`):

  | File | Loads | Delivers |
  |---|---|---|
  | `aide-command-hygiene.md` | unscoped — every session and sub-agent | §3, in positive form |
  | `aide-test-hygiene.md` | `paths:` — any file pytest would collect | §6 |
  | `aide-living-documents.md` | `paths:` — the living documents by name | the §1 shapes that bind on any edit |

  The two scoped rules match **by filename, not by `project.tests_dir` /
  `project.docs_dir`**: a rule whose globs silently stop matching is the exact
  failure this replaces, and templating the globs at install time would
  reintroduce it as a config error.

  **A `paths:` rule is armed by a read, not by a write.** `Edit` requires a
  prior read, so editing an existing file always arms one; creating a *new*
  matching file does not. The globs therefore cover the files each role reads
  on the way to writing, and `test-writer` keeps an explicit instruction to go
  read §6 itself — a repo with no tests yet gives the rule nothing to fire on,
  which is exactly when the fixture conventions are being set.

  If that instruction proves too weak in your project, the mechanism that
  closes it outright is `skills:` frontmatter on the agent, which preloads a
  skill's full body at agent startup with no read involved. Move the rule's
  body to `.claude/skills/<name>/SKILL.md`, keep its `paths:` frontmatter (a
  skill accepts the same field, so it still auto-loads for everyone else), and
  add `skills: [<name>]` to `.claude/agents/test-writer.md`. That is per-role
  and costs nothing in the roles that do not name it.

  **`aide-living-documents.md` is scoped but not rare.** Its globs include
  `items/*.md` and `insights.md`, which all six roles reach, so it loads on
  effectively every spawn. It carries only the document *shapes*; the
  durable-artifact, insight-immutability and human-gate rules it first
  duplicated are in `AGENT-CONTEXT.md`, already in every context.

  The six per-agent `## Command hygiene` blocks are **removed**; a test fails if
  one comes back. `ADAPTER-SPEC.md` §7 gains a **§-level delivery** contract
  point with the three properties that make a mechanism conformant rather than
  decorative — it loads without the role choosing to, it names the section it
  delivers, and it adds no rule the engine does not have. §3 and §6 now state
  the delivery obligation themselves, runtime-generally, so an adapter is not
  inventing it.

- **`install.py --update` now removes engine files the framework has dropped.**
  `copy_tree` overwrote and added but never deleted, so every file ever shipped
  stayed in a consumer forever — the sectioning above would otherwise have left
  a superseded `.aide/conventions.md` beside the new tree in every install.

  It removes nothing the engine itself shipped today — the sectioning kept
  `conventions.md` at its path — but it is not a no-op: it deletes anything a
  consumer put under `.aide/` themselves, on `--update` **and on a plain
  re-`--install`**, since both are the same reconciliation. `--check` previews
  each such file and exits non-zero, and an update prints them in their own
  block after the log, so neither happens silently.

  **Only `.aide/` is pruned**, because that tree is framework-owned in full,
  which is what makes "absent from the source" mean "removed from the engine".
  `.claude/agents/` and its siblings are directories a project legitimately
  adds its own files to, and the same inference there would delete a consumer's
  own agent. `loop.local.toml`, `__pycache__`, `*.pyc` and the adapter-supplied
  `loop/usage_probe.py` are never candidates. If you keep hand-written files
  under `.aide/`, move them before updating.

- **Four files compacted, against a stated test.** `AGENT-CONTEXT.md` (loaded
  into every context, so its size is multiplied by every spawn) and the three
  heaviest agent specs, together about 83% of the measured per-queue budget:

  ```
  core/AGENT-CONTEXT.md   4354 -> 3666   (-16%)
  agents/validator.md    11660 -> 8596   (-26%)
  agents/test-writer.md   6436 -> 4525   (-30%)
  agents/spec-author.md   8513 -> 6414   (-25%)
  ```

  Cut: the counterfactual argument for a rejected alternative, defect-provenance
  narrative, and intra-section restatement. Kept: every normative statement, the
  fenced shape examples, the one-line *why* at a decision boundary, and the
  disambiguators that pre-empt a known misread. The test for a cut was whether
  an agent that never saw the sentence would decide differently. The largest
  single cut is the "Model & effort" paragraph in three specs, which argued for
  a value the frontmatter already sets.

  `conventions.md` was **not** compacted: at ~0.3 sliced reads per queue it is
  under 1% of the budget, and its size was never the problem.

- **What the fix costs.** Issue #78 opened with a budget question, so the
  arithmetic is stated plainly: delivering the rules above costs more than the
  compaction saves. Against issue #78's spawn model (8-item queue, ~44 spawns,
  ~4 bytes/token), over the agent specs, `AGENT-CONTEXT.md` and the rules:

  ```
  compaction (specs + AGENT-CONTEXT)              -30.8k
  unscoped command-hygiene rule   x44             +17.9k
  living-documents rule           x44             +19.5k
  test-hygiene rule               x15..x35    +8.5k..+19.9k
  ----------------------------------------------------------
  net per 8-item queue                      +15.1k..+26.5k   (+11%..+19%)
  ```

  The per-spawn floor rises from 1,088 to 1,322 tokens (`AGENT-CONTEXT.md`
  plus the unscoped rule). That is the price of the two gaps above being
  closed, not a regression against a goal: a rule that loads is not the same
  thing as a pointer that might be followed, and the six inlined hygiene blocks
  had already drifted (`spec-reviewer` was missing the commit-substitution
  rule) precisely because six hand-maintained copies is not a delivery
  mechanism either.

  A consumer who would rather have the compaction without the cost can delete
  a file from `.claude/rules/`; it degrades to the pointer that was there
  before. Issue #85 proposes getting most of the cost back by delivering
  per-role via `skills:` instead of per-file via `paths:`.

### Added

- **`InstructionsLoaded` instrumentation** — `hooks/log_instructions_loaded.py`
  records every instruction file that loads, with the runtime's reason
  (`session_start`, `path_glob_match`, …), to `docs/aide/instructions/log.jsonl`
  (per-machine, gitignored). `scripts/review_instructions.py` reports it and,
  under `--strict`, exits non-zero when a shipped rule never loaded — a
  `paths:`-scoped rule whose globs stopped matching is otherwise silently inert.

  The event's payload fields are not pinned by public documentation, so the hook
  accepts several spellings and keeps anything unrecognised, truncated, under
  `extra`: a renamed field must degrade the record, not blank it, because an
  empty `paths` reads identically to "nothing loaded".

  It measures **delivery, not reading**. Nothing loads on a `Read`, so the 3%
  above remains a transcript question.

  **It does not activate on `--update` by itself.** `settings.json` is
  non-clobbering by design, so an existing consumer gets the hook *file* but
  not its registration; the `.aide-merge` diff names what is missing. Adopt
  `.claude/settings.overlay.json` (regenerated deterministically from
  framework-base + overlay on every run) and it activates and stays activated.

### Fixed

- **`docs/aide/permissions/*.jsonl` is now actually gitignored**, and the
  managed `.gitignore` block is **reconciled on update**, not only appended on
  install. `core/README.md` had listed that path as personal and git-ignored
  since it was introduced while the block never named it — and append-only
  meant the fix would have reached no existing consumer, exactly as the new
  `docs/aide/instructions/*.jsonl` line would not have.

  The block is marker-delimited and says in its first line that the installer
  manages it, so only the lines *between* the markers are rewritten; content
  above and below is untouched, and a consumer's BOM survives. A block whose
  `# --- end AIDE ---` line has been removed is left alone with a notice
  rather than guessed at.

- **`install.py` no longer aborts an update on an unremovable file under
  `.aide/`.** The prune followed symlinks, so a link to an empty directory
  reached `rmdir()` and raised — after the engine and `.aide/VERSION` had been
  written but before the adapter was copied, leaving a consumer on a 1.22.0
  engine with a 1.21.0 adapter and an `install.py --check` that reported it up
  to date. A symlink is now removed as a link (never following it to its
  target), any `OSError` is logged and stepped over, and the prune runs **last**
  so nothing it does can leave an install half-applied.

  `--check` now previews the files an update would delete and exits non-zero,
  and an update prints them in their own block after the log rather than
  burying them in it.

## [1.21.0] — 2026-08-25

### Fixed

- **An insight's provenance is free-form; only its date is load-bearing
  (issue #76).** The entry shape accepted `*(item NNN, YYYY-MM-DD)*` or a bare
  `*(YYYY-MM-DD)*` and nothing else, which rejected two provenances **the loop
  itself produces routinely**: `queue-NNN`, for planning and spec-authoring done
  before any item exists, and `items NNN-NNN`, for a finding that genuinely
  spans several. A consumer had three such entries.

  Neither was fixable where it sat. `conventions.md` §1 makes a captured claim
  immutable — "never reworded, reordered or deleted" — so the warnings were
  permanent, and permanent noise is what teaches a reader to skim the one run
  where a warning was real. Collapsing `items 099-101` to `item 099` would be
  both a rewording and the destruction of the provenance the marker exists to
  record.

  Worse than the warning: the same pattern is what yields the date, so
  `archive --before` skipped these entries however old and however closed —
  `date is None` fails the cut silently. They were neither working set nor
  archivable, pinned in the live file forever, which is the exact failure
  1.17.0's `archive` verb exists to prevent.

  **The fix is to stop enumerating.** Anything but a close-paren or a line
  break may now stand before the date. Enumerating the accepted forms means
  predicting what an author will write, and here predicting wrong costs a
  warning that can never be cleared — `specs-queue-NNN`, `PR #73` and `stage 4`
  would each have needed another round. Only the ISO date is load-bearing
  (`archive` cuts on it, `list` prints it); nothing routes on the item number,
  and the frame already pins the checkbox, a known type, the dash, a non-empty
  claim and the date. Canonical spellings — `item NNN`, `items NNN-NNN`,
  `queue-NNN` — are documented in `conventions.md` §1 and the `insights.md`
  template header as **guidance a reader can follow**, not a grammar the CLI
  enforces.

  `InsightEntry` gains `source`, the provenance verbatim; `item` is still
  parsed, but only from a provenance naming exactly one item. `insights list`
  reprints `source` rather than rebuilding the marker from `item`, which could
  only ever print the single-item form back. `queue-planner` and `spec-reviewer`
  now show `queue-NNN` in their capture instructions, since neither has an item
  to name.

- **Which marker is the provenance, when a line carries more than one.** A
  free-form provenance means an aside inside the claim can wear the marker's
  shape, and position alone cannot decide between them: `text` is non-greedy so
  the *first* match wins, and `… default is *(prod, 2020-01-01)* not *(item 099,
  2026-07-26)*` would take the aside's date and file the entry in the wrong
  archive quarter — silently, since the line still parses. Greedy is no better;
  it takes the *last* marker, which a pointer may equally carry (`→ see *(note,
  …)*`). The provenance is now the marker that leaves a **well-formed tail** —
  nothing, or the `→` pointer `tick` writes — with the previous, looser pattern
  kept as a fallback so hand-written tails predating `tick` parse exactly as
  they did. A provenance must also end in a non-blank character, so a stray
  comma stays a shape warning rather than becoming a silently accepted
  provenance that says nothing.

- **`aide insights archive` names the closed entries it could not date.** An
  entry too malformed to parse is excluded from every `--before` cut in
  silence, with nothing reporting why the live file will not shrink — a path
  that outlives the widened shape above, since a future unparseable line still
  reaches it. `archive_insight_text` now returns those entries alongside what
  it moved, and the command prints each one with its line number, *before* the
  early return: the run where nothing moved at all is the run that needs the
  report most. Open undated entries are not reported — they never move anyway,
  so naming them would be noise rather than a finding.

## [1.20.0] — 2026-08-25

### Added

- **One constructor per branch shape, and `aide queue start NNN` (issue #72).**
  1.13.0 centralised branch *parsing*; construction was never centralised. The
  engine built exactly one branch name — `cmd_claim`'s f-string — and recognised
  three, so **two of the three shapes it depends on were produced by an agent
  copying a string out of a markdown file**, and the regex that must later parse
  them never saw a name until something had already gone wrong.

  The failure is silent, not loud. `aide claim` infers an item's base only from
  a *recognised* queue branch and otherwise falls back to `main_branch` — so a
  typo, a slug, or a consumer's own convention sends every item's merge to
  `main` instead of the queue branch, which is the exact failure the base-ref
  inference exists to close. (`aide check` warns, `aide scope` errors, `aide
  status` says `unrecognised`; the 1.13.0 data-loss hazard does *not* return,
  since `_branch_item_number` still rejects both shapes.)

  `claim_branch_name`, `queue_branch_name` and `specs_queue_branch_name` now sit
  in the helper block beside the recognisers, and `_QUEUE_BRANCH_RE` is built
  from the same `_QUEUE_TOKEN`/`_SPECS_TOKEN` literals `queue_name` uses. That
  makes the round-trip test possible for the first time — every constructor
  through its recogniser, over an adversarial prefix set (no separator, a digit
  inside the prefix, a prefix ending in the queue token itself). It also makes
  the deferred queue-slug question (#55) cheap either way: changing the shape
  becomes a one-place edit whose failure a test catches, rather than a
  mis-targeted merge in a live run.

  `aide queue start NNN [--specs] [--base R] [--dry-run]` creates and pushes the
  branch and records its base, which `_record_branch_base` previously did only
  at claim. The `git switch -c` in `aide-run-roadmap.md` and
  `aide-spec-queue/SKILL.md` was already an exception to conventions §3 (*"if an
  `aide` verb covers it, the raw git form is wrong"*); both now invoke the verb,
  and **no framework prose types a branch name**.

- **`🔍 In Review` — a status for work pushed but not yet merged (issue #71).**
  `✅` meant two different things depending on `git.mode`: under `auto-merge`
  the item was merged, under `pr` it was *pushed and awaiting a human*. Nothing
  recorded the difference and everything downstream read `✅` as "done" —
  including `aide gc`, whose default ground is "the item is ✅" and whose action
  is `git branch -D` plus a remote delete. `/aide-run-queue` sends the
  orchestrator into that state deliberately at queue exhaustion, and the line a
  human was asked to approve (`would delete aide/077-x (local+remote; item 077
  is ✅)`) read like confirmation rather than *"this is the head of an open PR"*.
  A run must be stable under either mode.

  **`✅` now means merged, in every mode**, and is written by `aide merge` when
  the merge actually happens rather than claimed by an agent ahead of one. The
  validator marks the item `in-review` — one instruction, mode-independent — and
  `merge` promotes it on the `auto-merge`/`local` path or leaves it `🔍` on the
  `pr` path. A `🔍` item holds its stage at `🚧` and its queue open; `aide check`
  no longer calls its branch stale (a warning firing on every run until a human
  merges is one that gets tuned out) and `aide status` reports it as awaiting
  review instead of recommending the destructive verb.

  Because in `pr` mode nothing inside the loop ever observes the merge, `🔍`
  needs a way home: `aide sync` and `aide status` name any `🔍` item whose work
  has since landed in the base and print the `aide progress set NNN done` that
  closes it. That reuses the content check below, so it needs **no** forge call —
  a `gh pr list` guard would degrade silently to "no open PRs found" when `gh`
  is missing or unauthenticated, which is exactly the false silence a safety
  check must not have.

  **Migration: none.** No existing document contains the new icon, so nothing
  already written changes meaning; the status legend in a consumer's
  `progress.md` is decorative (the engine never parses it) and can gain its row
  whenever convenient. `aide progress set NNN done` still works. A consumer on
  `git.mode = "auto-merge"` sees no behavioural change at all. Under `pr`, a
  stage now correctly sits `🚧` until its PRs land, where it previously read `✅`
  immediately.

### Fixed

- **`aide gc`: the dry run overstated, and the `✅` ground force-deleted without
  asking git (issue #70).** Two defects in the same loop.

  `would delete <br>` was printed for every target and only *then*, on the
  `--yes` path, was the checked-out branch skipped — so the preview was not the
  set `--yes` acted on. A preview that overstates trains the reader to skim it,
  which matters far more for the one destructive verb than anywhere else. Every
  skip is now decided before anything is printed and shown as `skipping <br>:
  <reason>` on both paths. `current` also came from `git rev-parse --abbrev-ref
  HEAD`, which returns the literal string `HEAD` on a detached HEAD; no branch
  ever equals that, so the "currently checked out" protection silently did not
  apply in that state. It now resolves to the branches at the checked-out commit.

  The `✅` ground deleted with `git branch -D` — the flag that suppresses git's
  own "this is not merged" refusal — plus `git push origin --delete`, and
  **nothing in that path asked git whether the work had landed**. `progress.md`
  is a document that agents and humans both edit; a `✅` outruns the merge
  easily (a commit added after the validator ticked it, a hand-edit, the
  `pr`-mode window above). Local loss is recoverable from the reflog until
  prune and a deleted PR head survives as `refs/pull/N/head`, but on a plain git
  remote the remote delete is not recoverable at all.

  The oracle is `git merge-tree --write-tree`, compared against the base's own
  tree: *would merging this branch change the base?* `git branch --merged` asks
  about ancestry and so misses **every** squash merge — which is precisely why
  `-D` was reached for — and `git cherry` gets a *multi-commit* squash wrong, a
  false alarm on the exact shape GitHub's "Squash and merge" produces. The same
  check strengthens `--merged`, which carried that ancestry weakness too, and it
  stays correct after the base advances with unrelated work.

  A `✅` item whose branch still carries unlanded content is **skipped**, with
  the base it was measured against named; the new `--abandon` deletes it anyway,
  for the genuinely abandoned claim (`--abandon` rather than `--force`, since
  abandoning a claim is a real part of the lifecycle per conventions §2). A
  branch that fails to parse as a claim was already invisible to this ground, so
  the exposure was entirely on correctly-named branches.

  `merge-tree --write-tree` needs **git 2.38** (Oct 2022); the only realistic
  holdout is Ubuntu 22.04 LTS (git 2.34.1, standard support to April 2027). On
  older git the `✅` ground **refuses rather than degrading** — no fallback
  oracle and no hard version requirement, so old git is always *more*
  conservative and nobody's `gc` stops working. A second merge-detection path
  would need its own adversarial tests to stay honest, which is more machinery
  than eight remaining months of 22.04 justify.

## [1.19.0] — 2026-08-24

### Added

- **`aide check` now enforces the `.gitattributes` `eol=lf` rule (issue #46).**
  §6 and §1 both stated it — *"a committed byte-exact fixture needs a
  `.gitattributes` `text eol=lf` pin"* — and nothing checked it. Without the
  pin, `core.autocrlf` rewrites the file on a Windows checkout and every byte
  comparison against it fails **on Windows only**, the platform §7 says no gate
  in this loop ever sees; the recorded instance cost 13 red tests across three
  modules, invisible to every local run. Its sibling rule got a deterministic
  lint in 1.11.0 only because a repo-root string match could decide it. The new
  `gitattributes_eol_pin_warnings` resolves a fixture path through the AST —
  `Path(__file__)` walked up and joined with string literals — and warns when
  that path exists in the checkout and no `eol=lf` pattern covers it.

  **Precision over recall, deliberately**, per the issue. The pattern matcher
  follows git's rules rather than `fnmatch`'s, since a false *silence* is the
  failure being prevented: a single `*` does not cross a `/` (so `tests/*.json`
  does not cover `tests/golden/x.json`), `**` does, and a pattern with no slash
  matches at any depth. A read only counts when it feeds an `==`/`!=`
  comparison or a hash — the narrowing that makes the lint usable, and one that
  only surfaced by running an early draft against a real consumer: flagging
  every `read_text()` produced twenty-odd warnings, nearly all of them plain
  helper reads whose callers assert a substring, which universal-newline
  translation makes immune to the rewrite anyway. Paths reached through a
  `tmp_path`, a function argument or a constant imported from another package
  resolve to nothing and are skipped in silence, because two freshly generated
  files compared to each other is a determinism check needing no pin — the
  shape of the majority of `read_bytes()` calls in a real suite.

  Validated against `dadrobny/segfacet` before landing, the way the issue asked:
  zero false positives on that fully-pinned repo, and six genuine byte-exact
  comparisons against committed files correctly resolved and read as pinned.
  §6 now records both the check and the honest limit — treat a warning as
  authoritative and its silence as partial.


## [1.18.1] — 2026-08-24

### Changed

- **The installer ships a test suite and now says whether to run it.**
  `install.py` copies `core/scripts/tests/` into every consumer as
  `.aide/scripts/tests/` — 14 modules, 462 tests — and nothing anywhere said
  whether the consumer was meant to run them. The default outcome was that
  nobody did, and for a stronger reason than the `testpaths` convention alone:
  **`.aide/` is a dot-directory**, so pytest's default `norecursedirs` (`.*`)
  skips it whether or not the repo sets `testpaths` at all — verified by
  clearing `norecursedirs` in a fixture consumer, which takes collection from 1
  test to 463. So an engine update landed with its own suite never executed, and
  a broken verb was discovered mid-loop instead. The answer is now stated in both
  places a reader can meet it: `core/README.md`'s file table gains a
  `scripts/tests/` row, and a new *"Running the engine's own suite"* section
  states the exclusion **and its mechanism** (so the claim does not quietly
  become false if the engine ever leaves a dotted directory), explains why that
  is the right default — a red test in there is not something the project can
  fix, and must not block the project's own CI — gives the explicit one-liner to
  run when accepting an update, notes that adding the path to a consumer's own
  `testpaths` is a supported choice at the cost of coupling the two CIs, and —
  the question the silence also left open — names the only two remedies when a
  shipped test goes red: `--update` forward from a newer framework checkout, or
  `--update` back from an older one. Never a hand-edit under `.aide/`, which the
  next update silently overwrites. `install.py`'s completion output now names the
  directory and the command on **both** the fresh-install and the `--update`
  path, so the answer arrives at the moment the files do — and above all on
  update, which is when a shipped test can newly go red. Guarded by
  `tests/test_install_shipped_suite_signpost.py`, whose `--update` case fails if
  the line is ever moved back inside the fresh-install-only branch.

- **`conventions.md` §4 now states what a `git.mode` choice costs in CI.** §1
  promises that per-item scope is checked on each claim branch as it merges, and
  §4 described the three modes purely in terms of pushes and merges — never
  mentioning that the choice also decides what kind of CI gate can see a claim
  branch at all. A consumer could read §1, wire a scope job, and have it report
  green forever while checking nothing. That is a gate which decays with a config
  change rather than one that never worked, which is why it goes unnoticed.
  §4 gains a table across the three modes — is the claim branch pushed, is a PR
  opened, what gate is possible — and names the distinction that actually
  governs: **PR context, not visibility.** `auto-merge` pushes the claim branch
  exactly as `pr` does, so a push-triggered workflow can see it; what it does not
  produce is a pull request, hence no `github.base_ref` to diff against (the job
  must pass `--base` itself) and a race against the in-loop merge that deletes
  the branch. Under `pr` the PR carries head and base directly, which is the diff
  `aide scope` wants with no branch-name parsing. The trade is named in both
  directions: `auto-merge` buys unattended throughput and, absent a purpose-built
  push workflow, leaves the gate enforced only by the validator in-loop — same
  machine, same platform, same checkout that built the item, the §7 blind spot
  exactly; `pr` buys the independent second-platform signal back at one human PR
  open per item. §4 also records that the branch *shape* is an independent axis:
  under the stacked queue-branch model `pr` still works, the PR's head being the
  claim branch and its base the pushed queue branch. §1's claim now points
  forward to §4 rather than standing alone. Documentation only: no verb changes
  behaviour, and `aide scope` short-circuiting on a queue branch remains
  correct.

### Fixed

- **`aide scope`'s documented base ref had lagged its own fix.** §1 said the verb
  "diffs against the merge-base with `origin/<main>`", and `--base`'s `--help`
  said the default was `origin/<main_branch>` falling back to the local ref. Both
  described behaviour that 1.8.0 deliberately replaced: the base resolves
  `--base` > the branch's **recorded** base > `main_branch`, and only the two
  *derived* answers prefer their `origin/` counterpart (an explicit `--base` is
  used verbatim). The stale wording was not merely imprecise — it was wrong in
  exactly the case the resolution order exists to get right, since an item
  claimed from a queue branch has diverged from *that*, not from `main`, and a
  reader who believed the prose would expect every sibling item already merged
  into the queue to be reported against this item's spec. §1 now states the
  resolution order, the `origin/` preference and the stacked-work case, and the
  `--help` string matches. Documentation and help text only; no behaviour
  changes. Caught by Copilot review on the PR for the two items above.

## [1.18.0] — 2026-08-24

### Added

- **A sibling repo's own instructions now reach a session that edits it.** A
  runtime loads instruction files for the **working directory's** repo — its root
  file, and subdirectory files as it reaches into them. A sibling repository gets
  nothing: *"declared as an additional working directory"* does not imply
  *"instructions loaded"*, and nothing announces the gap. An agent editing a
  sibling works without rules that were written down, that it would have
  followed, and whose absence is invisible — precisely the material that cannot
  be inferred from the code (a versioning rule enforced by that repo's own suite,
  a merge policy, a path convention that looks like a typo and is not).

  Observed directly: in a session with four sibling repos configured as
  additional working directories, only the cwd repo's `CLAUDE.md` was in context.
  That session went on to assess another repo's architecture and file eight
  issues against it without that repo's rules ever in hand.

  **This bites the framework's own maintenance hardest.** The documented update
  workflow edits the framework clone *from a consumer's checkout* — by
  construction, a session with the framework's instructions unloaded.

  - **The rule** (engine, runtime-general): `conventions.md` **§8 — Reaching into
    another repository**. A repository's own instructions bind for work inside
    it; read them before acting; where two repos disagree about a file, the repo
    that owns the file wins. Restated in `AGENT-CONTEXT.md` so it binds from the
    first message rather than when something points at it.
  - **The mechanism** (adapter): `ADAPTER-SPEC.md` **§8**, and the Claude
    adapter's `hooks/sibling_instructions.py`, registered on `PreToolUse` for the
    path-touching tools. On the first call touching a path inside a declared
    sibling, the session is pointed at that repo's instruction file once.

  **A pointer, not the file.** Injecting the body looks more helpful and is worse
  three ways. It goes **stale** — the case that motivates the rule is a session
  *editing* the sibling, so a copy taken at first touch can be wrong by the time
  it is used, and wrong invisibly, which is the failure this exists to remove. It
  is **capped** — a runtime bounds injected context, Claude Code at 10,000
  characters, past which the output is spilled to a file and replaced with a
  preview and its path, the runtime improvising this very pointer. And it is
  **paid in full every time**, where a pointer costs a few hundred characters and
  the reader spends the rest only if it opens the file. The hook does the part a
  session cannot do for itself — noticing it has crossed into a repo whose rules
  it was never given — and leaves the reading to the reader, against the file as
  it is then.

  **No new configuration.** The repos come from `[framework] local_path` and
  `[hygiene] extra_repos` in the personal, gitignored `.aide/loop/loop.local.toml`
  — already the machine's answer to "which repos does this project legitimately
  span", in the one file permitted to hold absolute paths. `extra_repos` was
  added in 1.12.0 for the hygiene guard's `git -C` carve-out and now has a second
  consumer; the instruction filename is the `file` the adapter already declares in
  `default-context.json` (§7), so it is named once. The hook reuses the guard's
  own config parser rather than growing a second reader of the same file.

  **Lazy, not eager.** An eager `SessionStart` list names every declared repo,
  most of which a given session never opens — and a block that is usually
  irrelevant is one a reader learns to skip, including on the session where it
  was not. Pointing at the moment of the crossing makes the message true of what
  is happening right then, and costs nothing in a session that never reaches
  across. Each repo is pointed at once per session — including a declared repo
  with *no* instruction file, so a missing file is not re-checked on every
  subsequent call. The check reads a bounded 4 KB prefix, never the whole file:
  this runs ahead of tool calls and the body is never injected anyway.

  **It watches; it does not gate.** No `permissionDecision` is emitted and the
  exit status is always 0, so the permission flow is untouched. Every failure
  mode — unreadable config, malformed declaration, an internal bug — is
  swallowed, leaving the session exactly as it would have been. A malformed
  `loop.local.toml` grants nothing, inherited from the guard's parse, so a typo in
  a personal config file cannot start leaking an undeclared repo's file into
  context. The per-session marker is created `0600` — it names absolute paths to
  this machine's repos, and the system temp directory is world-readable on a
  shared one.

### Changed

- **`install.py` now copies the adapter's `default-context.json` into
  `.claude/`.** It was previously read only from the framework's own tree, at
  install time. The §8 hook needs the same declaration at *runtime*, from the
  installed adapter; without the copy it would fall back to a second hard-coded
  copy of the instruction filename — the precise drift the declaration exists to
  prevent. Consumers gain one file and no behaviour change.

### Notes

- One implementation detail worth recording because it silently defeats the
  obvious approach: **a `PreToolUse` hook's plain stdout is written to the debug
  log and never shown to the model** — only
  `hookSpecificOutput.additionalContext` reaches it. Printing the file looks like
  it works and delivers nothing. This was the open question gating the design;
  `ADAPTER-SPEC.md` §8 states it as a check any runtime must make of its own
  mechanism.

## [1.17.0] — 2026-08-24

### Added

- **`aide insights` — the one living document the CLI could not read now has a
  verb.** Every other continuously-written document had the CLI doing its
  mechanical work: `progress.md` has `aide progress` and `aide gate`,
  `queue-NNN.md` has `aide queue tidy` and `aide claim --queue`, `items/NNN-*.md`
  has `aide claim`/`scope`/`check --queue`. `insights.md` had `aide check`
  shape-checking it and nothing else, so every triage pass meant an agent
  reading and hand-parsing the whole file — and that cost is why triage kept
  getting deferred.

  Measured on a consumer's inbox at 77 entries: 110,867 characters ≈ 29k tokens,
  of which the live working set was **15 open entries**. Closed and open are
  interleaved in one file, so there was no way to look at the backlog without
  loading the archive with it.

  - `insights list [--open] [--type T] [--trail]` — the backlog without the
    history around it, numbered so the other verbs have something to take.
  - `insights tick N --pointer "<where it landed>"` — the one in-place edit
    conventions.md §1 permits. On an entry that is **already** ticked it appends
    a dated status-trail line instead, which is the same section's rule that
    everything after the first routing is appendable bookkeeping. Neither path
    touches the captured claim. A pointer containing a line break is refused,
    as `aide gate`'s note already is: it is written into a single entry line,
    so a break would split one claim into two and renumber everything below.
  - `insights archive --before YYYY-MM-DD [--yes]` — moves **closed** entries
    older than a date into `insights/archive-YYYY-QN.md`, each moved entry and
    its trail carried across line for line (the module rebuilds text with `\n`
    like every other writer in it, so the promise is the claim, not the
    surrounding bytes). Dry run by default, like `aide gc`. An open entry never moves
    whatever its age: it is the working set, and archiving it would hide exactly
    what `list` exists to surface.

  Capture is deliberately unchanged — append one line to one file, atomic,
  conflict-free, no number to allocate, no network. A folder-per-insight layout
  would tax that moment with number allocation; a GitHub-issue-per-insight store
  would make it depend on network and `gh` auth, which `git.mode = "local"`
  exists to avoid.

  Entry identity is **position in the live file**, which is sound only because
  the file is append-only by contract. `archive` is the one thing that moves
  entries out, so it reports that the remaining numbers have shifted, and `tick`
  refuses an ordinal it cannot resolve rather than editing the wrong line.

### Fixed

- **`aide gate approve|decline` prepended a BOM to `progress.md`.** `_ENCODING`
  is `"utf-8-sig"`, which *strips* a leading U+FEFF on read but *writes* one on
  write — so passing it to `write_text` made every gate decision manufacture the
  exact hazard the constant exists to absorb, and the file's first git diff
  after a decision was the whole file. `cmd_gate` was the one writer in the
  module doing this; `cmd_progress`, `cmd_queue` and the new `insights` verbs
  all already wrote plain `"utf-8"`. Read tolerantly, write clean. Found by
  review while checking the new code for the same mistake, which it did not
  have.

### Changed

- **`_ALWAYS_AUTHORISED` gains `insights/archive-*.md`, deliberately.** Its
  comment argues against exactly the wildcard that would have made this
  automatic, so it was added as one bounded pattern rather than by widening the
  rule: `path_matches` anchors a bare `*` per path segment, so it reaches one
  directory and one filename shape and cannot become a subtree hole. This
  required `scope_findings` to glob-match its always-authorised set instead of
  comparing it exactly — no behaviour change for the two literal entries.

- **An archive is frozen and stays unchecked by `insight_warnings`**, now stated
  in the docstring rather than left to be discovered. A shape warning on an
  archived claim would name a defect nobody may fix, since the immutability rule
  forbids rewording the line. Unfilled `{{slot}}` markers are still caught
  there, because `template_residue_errors` walks the whole tree and that one is
  a genuine error wherever it appears.

- `aide-feedback-loop`'s triage step reads the backlog with `insights list
  --open` and ticks with `insights tick`, instead of opening the file and
  editing entries by hand.

- The `aide.py` module docstring's `Subcommands::` block lists `gate`, which
  shipped in 1.13.0 and was never added there, and `insights`. `core/README.md`
  gains both in its verb list.

## [1.16.0] — 2026-08-24

### Fixed

- **A fixture consumer now runs in CI.** The engine is developed at `core/` and
  executed at `.aide/`, inside someone else's git repository, by verbs that
  shell out to git — and none of that was under test. The only automated
  evidence a release still worked was the framework's unit tests passing against
  source files no consumer runs in that layout. Closed #29 records the cost:
  four CI-only failures reached a consumer's `main`, every one caught by a human
  reading the Actions tab rather than by a gate.

  `tests/test_fixture_consumer.py` installs into a `tmp_path`, `git init`s it,
  scaffolds the minimum living documents (one stage, one queue, two items, one
  spec), and drives the loop end to end against the engine loaded from
  `.aide/scripts/aide.py`: `check` clean on the scaffold and failing on a lost
  `progress.md`; `claim` creating, switching to and recording the branch's base;
  `scope` passing in bounds, exiting 1 out of them and 2 on an unspecced item;
  `merge` landing the work in `local` mode and refusing to touch `main` in `pr`
  mode; `gc` dry-running by default, deleting only landed claims and never a
  branch outside the prefix; `status` reporting the state the test just made.
  Also covered: `--update` leaving project-owned documents byte-identical, and
  an overlay regenerating into `settings.json`.

  Exit codes and effects, never prose. No new CI infrastructure — the matrix
  already runs ubuntu and windows, and the job is `pytest` picking up `tests/`.
  Extending `tests/test_installed_docs_links.py`'s existing real-install pattern
  rather than self-hosting AIDE in this repo, which would give every engine file
  two committed copies and make the "never hand-edit `.aide/**`" rule
  unfollowable.

- **`install.py` now reads back the adapter it recorded.** `scaffold_aide_toml`
  wrote `[aide] adapter` into a consumer's `aide.toml` and nothing ever read it:
  `run()` re-derived the adapter from `--adapter` on every invocation,
  `--update` and `--check` included, where the flag defaulted to `claude`. With
  one adapter implemented that wrong default is accidentally always right. The
  moment `adapters/copilot/` becomes real it stops being right, and the failure
  is not a clean error — it is a repo that quietly acquires a second provider's
  control files and, since 1.15.0, a root `CLAUDE.md` importing
  `AGENT-CONTEXT.md`, having never chosen Claude.

  The target now decides. `resolve_adapter` reads `[aide] adapter` through the
  engine's own config loader — the treatment `_project_scope` already gives
  `source_dir`/`tests_dir`, so installer and engine cannot disagree about one
  file — falling back to `--adapter`, then to `claude`, when nothing is
  recorded. A **typed** `--adapter` contradicting the record is an error naming
  both: switching adapters is a real intention, but not one a flag nobody typed
  should express, which is why `--adapter` now defaults to `None` rather than
  `"claude"`. The install log line reports the resolved adapter instead of the
  flag — the value that was wrong in the first place. `--update` in the docs no
  longer carries the flag at all.

  `--check` also gains a second report: another adapter's declared instruction
  file still carrying the `AGENT-CONTEXT.md` import — a superseded provider left
  behind by a mis-flagged update or a deliberate switch. It is **reported, never
  removed** (`docs/vision.md` principle 4 — the framework does not touch
  project-owned files, and a root instruction file emphatically is one), and it
  is kept separate from import drift in `report_version` because the two do not
  share a repair: no `--update` deletes a project-owned file, so that state
  exits non-zero without prescribing one.

- **An adapter name is validated as a directory name.** The adapter is joined
  onto `FRAMEWORK_ROOT / "adapters"`, and reading it back from `aide.toml` means
  it no longer arrives only from a typed flag — so a recorded `../core` would
  resolve outside `adapters/` and have `--update` copy from an unintended
  framework directory. Both sources are now checked against a whitelist
  (`ADAPTER_NAME_RE`) before use, which covers `..`, `/`, `\` and a Windows
  drive-relative `C:x` as one rule on every platform, and the refusal names
  which source to fix. Same reasoning as ADAPTER-SPEC §7's existing check on an
  adapter's declared instruction file.

- **`install.py` loads the engine by path, not by name.** Both `_project_scope`
  (pre-existing) and the new `_recorded_adapter` need the engine's `load_config`
  so the installer and the engine interpret one `aide.toml` identically. Each
  did it with a bare `sys.path.insert(0, …)` and `import aide`, which has two
  independent problems: the entry was never removed, so in a long-lived process
  duplicates accumulated at position 0 and outranked every other import path for
  the rest of the run; and `import aide` resolves through `sys.modules` as well,
  so a host process that had already bound some other `aide` won the name
  outright whatever the path said.

  `_engine_load_config()` now loads `core/scripts/aide.py` through
  `importlib.util.spec_from_file_location` — the file whose path is already
  known — touching no global import state and registering nothing in
  `sys.modules`, which is how every test module in this repo loads the engine.
  Cached, since the readers run more than once per invocation.

- **`aide check` no longer needs the full document set to run at all.**
  `run_checks` early-returned `missing <docs_dir>/progress.md` as a hard error,
  which conflated two unrelated situations: a loop repo that lost its central
  document (a real error) and a repo that never had a document set because it
  adopted only the conventions and the CLI (nothing wrong). Because the return
  discarded the warnings computed before it, **eight checks were unreachable for
  the second case — three of them test-hygiene lints that read `tests_dir` and
  have nothing to do with the loop's documents at all.**

  Those three exist because four cross-platform defects reached a consumer's
  `main` and were caught by a human reading the Actions tab rather than by any
  gate. A repo doing installer or CLI path work on a mixed CI matrix is the
  exact risk class they cover, and it was the class that could not run them.

  The cases are now distinguished the way #48 distinguished a not-yet-queued
  stage from a typo'd one — three of them, not two: **no `docs_dir` at all**
  runs the repo-agnostic checks, prints a `notice:` naming the configured
  directory, and exits 0; **`docs_dir` present without `progress.md`** keeps
  today's error verbatim; and **`docs_dir` naming something that is not a
  directory** is a misconfigured `aide.toml`, reported as an error naming the
  key to fix rather than passing as a deliberate choice not to adopt the loop.
  The
  `(errors, warnings)` return shape is unchanged — the notice is presentational,
  emitted by `cmd_check` — so nothing that parses `run_checks` is affected.

  The notice is withheld on a `--queue` run: `--queue` sends the cross-spec
  check looking for a queue file under the same absent directory, so it runs and
  errors, and "only the repo-agnostic checks ran" would be false next to that
  error. The notice exists to stop a *pass* being over-read; a failing run needs
  no such guard.

  This repository was the demonstration case: it has no `docs/aide/`, so it
  could not lint its own tests, and the one finding that surfaced the moment it
  could — an assert message in `tests/test_installed_docs_links.py` rendering a
  relative `Path` with the OS separator — is fixed here too.

## [1.15.0] — 2026-08-24

### Added

- **`AGENT-CONTEXT.md` — a channel from the framework into a session's default
  context.** Every rule the framework writes lived in `conventions.md`, which is
  read only when something points at it. That works for an agent spec in the
  unattended loop and fails for an interactive session, where a person and the
  runtime produce durable artifacts — commit messages, issue bodies,
  `insights.md` entries — with no agent spec in play. The framework had no way
  to reach that session: `core/templates/` held no instruction-file template and
  `install.py` never mentioned one.

  The engine now ships `AGENT-CONTEXT.md`, about a page of the rules that must
  bind *before* anything points at `conventions.md`, each linking to its full
  treatment there. It reaches a session **by import, not by managed block**:
  ADAPTER-SPEC gains an optional **§7** in which an adapter declares, in
  `default-context.json`, the file its runtime loads by default and that
  runtime's import syntax. The Claude adapter declares `CLAUDE.md` and `@{path}`.

  `install.py` then ensures one line — `@.aide/AGENT-CONTEXT.md` — is present in
  that file: appended if the file exists (nothing else touched; the project keeps
  everything it wrote), created with a minimal body if it does not, and reported
  as drift under `--check`, which now exits non-zero for a missing import the
  way it does for a stale `VERSION`. The imported page is framework-owned
  wholesale, the ownership pattern §5 already establishes, so there is no
  delimited region inside a project-owned document. A runtime with no
  default-context concept omits `default-context.json` and nothing runs. (#59)

- **Durable artifacts must read cold — `conventions.md` §1.** Everything the
  loop produces outlives its session, and nothing said it had to be readable
  without one. Three rules: no chat-local identifiers (a label coined for one
  conversation's convenience is scaffolding, not a name); cross-reference by
  resolvable identity (an issue number, a path, a dated entry — never "the
  companion PR"); record the decision and why it holds, not the route to it.
  Provider-agnostic, and binding on the framework's own artifact shapes, so it
  sits beside the format contract — and it is the first rule carried by
  `AGENT-CONTEXT.md`, since the sessions it binds are exactly the ones that
  never read `conventions.md`. (#59)

### Changed

- **Item and queue file naming lives behind named helpers, the way branch
  naming already did.** `_branch_item_number` and `_is_queue_branch` centralised
  the shared-namespace hazard for branches in 1.13.0 — after an unanchored match
  read `aide/queue-016` as long-finished item 016 and let `gc` delete an
  in-flight queue branch carrying the only copy of its queue file and specs.
  Filenames kept re-deriving the same convention as raw globs and f-strings at
  thirteen sites, five of them the identical `idir.glob(f"{n:03d}-*.md")`.

  `queue_name`, `queue_number`, `iter_queue_paths`, `queue_path` and
  `item_spec_paths` now hold it, and all thirteen sites call them. No live bug
  is fixed — every site was correct — so the change is containment: one place
  for the 1.13.0 class of misread to reappear, and one place that is tested.
  Two behavioural improvements fall out: `queue_path` **resolves by glob rather
  than constructing** a name, and `iter_queue_paths` orders by the parsed number
  rather than lexicographically, so a slugged queue file (#55) would be a naming
  decision rather than an engine sweep. Four parameters named `queue_number`
  were renamed, since the helper now owns that name at module scope. (#54)

- **An insight entry's *claim* is immutable; its *status* is not.**
  `conventions.md` §1 said the inbox was append-only "with exactly two
  exceptions" — ticking the checkbox and appending one `→ where it landed`
  pointer, both at triage. Triage happens once, so nothing could record that an
  entry's premise later decayed: "fixed in 1.15.0", "superseded", "this turned
  out to be wrong" were all forbidden by the letter of the rule. The checker
  never enforced it (`insight_warnings` skips indented lines and stops caring
  after the provenance date), and practice had already broken ranks — in one
  consumer's 77-entry inbox, 17 entries carried two or more pointers.

  The rule now separates the two things it was conflating. The captured line
  stays immutable — never reworded, reordered or deleted, which is what makes a
  *wrong* entry instructive rather than quietly erased — and an entry may carry
  an appendable **status trail**: dated lines, indented beneath it, newest last.
  Ticking the checkbox remains the one in-place edit. The shape already
  validated, so no checker change was needed; three tests now pin it, including
  one that runs the example in `conventions.md` itself through `aide check`, so
  the documented shape cannot drift from the accepted one. (#51)

- **`framework` insights may be triaged on capture, not only at the queue
  boundary.** The boundary is right for the types that become candidate items —
  the queue PR reviews the routing — but a `framework` entry leaves for an issue
  on another repo, and nothing about that destination needs a queue. Coupling
  them meant the inbox accumulated for exactly as long as a queue ran: 13 of 15
  open entries in the consumer above dated from one week, untouched since. (#51)

## [1.14.1] — 2026-08-20

### Fixed

- **A human gate on a stage that has no items queued yet is no longer reported
  as a typo.** `aide check` derives a stage gate's reach by resolving `stage N`
  through `progress.md` on every read — deliberately, so the reach follows the
  roadmap instead of freezing a list written when the gate was raised. That
  makes raising a gate at planning time, before anything is queued for the
  stage, the feature's primary use. The reach check read the resulting empty
  list as evidence of a mistyped stage number and told the author to "check the
  stage number", firing on the happy path and training consumers to ignore the
  one warning standing between a typo and a gate that silently guards nothing.
  The two causes of an empty reach are now separated by whether the stage
  section exists at all: an absent section keeps the blunt original wording, a
  present but unqueued one reports neutrally that the gate "has no items queued
  yet … and will block that stage's items as they are created". Reported from
  `dadrobny/segfacet` against 1.14.0. (#48)

  The section lookup both cases need is now one named helper, `stage_section`,
  rather than the same `stage_sections`/`_same_stage` generator expression
  inlined at three call sites — a helper that returns only item numbers cannot
  tell "no such stage" from "stage with nothing in it", which is precisely the
  distinction that was missing.

## [1.14.0] — 2026-08-18

### Added

- **Five conventions rules that were stated and enforced by nothing are now
  checked.** An audit of `conventions.md` against what `aide check`, the
  hygiene hook and the repo suite actually verify found the gap. It matters
  because a stated rule with no check decays, which this framework demonstrated
  on itself twice inside one week: the "guidance is never a slot" rule sat in
  `CLAUDE.md` for months and was broken in two consecutive PRs, and the first
  guard written for it had a blind spot that let it be broken again in the very
  PR that added the guard.

  Each check was measured against a real consumer before shipping, and each
  found something real there:

  - **Item spec shape** (§1, §5) — the `# Item NNN — Title` heading must agree
    with the filename, the header blockquote must carry no status **field**
    (status lives only in `progress.md`; a duplicate has no owner and only
    drifts) — a colon beside the bold is required, so prose merely emphasising
    the word is not a match — and the
    mandatory `## Assumptions` block must exist. Missing-Assumptions is reported
    as **one aggregated line**: 32 of 112 specs predated the rule in the
    consumer, and 32 separate warnings would bury the substantive ones — the
    failure mode issue #13 was filed for.
  - **Flat deliverable bullets** (§1) — the parser matches indented bullets, so
    a nested one counts as a full deliverable: a `📋` child quietly holds its ✅
    parent's stage open. Scanned across the whole stage section deliberately,
    since `stage_deliverable_statuses` reads every leading-icon bullet in it —
    an indented bullet under **Acceptance** drags the stage the same way, so
    scoping to the Deliverables block would under-report.
  - **Header blockquote** (§1) — the line *immediately* after the title, so an
    intervening heading does not satisfy it, and multi-line HTML comments are
    skipped whole (only their opening line starts with `<!--`). Scoped to the
    templated living documents.
    Checking every file under `docs_dir` was 3 false positives in 8 files: a
    generated artifact and a project note are not living documents, and
    `insights.md`'s template deliberately opens with a comment.
  - **Separator-dependent test values** (§6) — a relative `Path` rendered with
    `str()`, or interpolated into an f-string, carries the OS separator.
    Narrowed to `.relative_to(`, the shape all four recorded CI-only failures
    took, and matched through the **AST**: a regex cannot tell an f-string's
    `{...}` from a dict or set literal, and the first draft duly flagged
    `{p.relative_to(d).as_posix(): …}` in the consumer — code that already
    follows the rule. One real instance there once that was fixed.
  - **Tests shelling out to `aide.py`** (§6) — the logic is importable and
    returns structured data; the subprocess adds a stdout surface that has
    failed on Windows only, and can pass while checking nothing. Matched
    **through the AST**: the sole textual match in the consumer was a docstring
    explaining why its author had removed a subprocess, so a line-based lint
    would have flagged the file documenting the correct practice.

  All are warnings, not errors — these are documents in flight, and the point is
  visibility, not a gate. Together they add 6 findings to the consumer's `aide
  check` — 7 warnings to 13 — every one real. Two of those come from requiring
  the documented `# Item NNN — Title` heading rather than just the number: the
  two specs concerned write `# Item NNN: Title` with a colon, so the status
  report's title parse (`_spec_stage_and_title`) returns nothing for them.

  Both test-hygiene lints share one path-display helper with the pre-existing
  absolute-path check. That helper tolerates a `tests_dir` configured absolute
  or resolving outside the repo, where `relative_to` raises — a crash fixed once
  in the original lint that came straight back when two new ones were written
  beside it with the call hand-copied.

### Fixed

- **The nested-bullet warning described the opposite of what happens.** It said
  the rollup "ignores" a nested status bullet. `_BULLET_RE` allows leading
  whitespace, so the parser reads an indented bullet as a **full deliverable** —
  verified: a `📋` child under a `✅` parent yields `['complete', 'planned']` and
  rolls the stage up to 🚧. That is the real hazard, and a worse one: nesting
  says "subordinate" to a reader while the tooling counts a peer, so a sub-bullet
  quietly holds its stage open. The warning now says so.

- **The status-field check would never have fired.** The item template writes
  fields as `**Created:**`, with the colon *inside* the bold, and the first
  pattern expected `**Status**:` — so it matched nothing. Caught only because a
  test asserted the real template's spelling rather than the one assumed while
  writing the regex.

## [1.13.0] — 2026-08-18

### Fixed

- **A queue branch made an item permanently unclaimable.** `_pick_item`
  resolved a claim branch to an item number with an *unanchored* digit search,
  so `aide/queue-016` read as item 016 and `aide/specs-queue-015` as item 015 —
  marking those items already-claimed and therefore never offered again. This is
  the bug class 1.5.0 fixed by giving every branch→item call site one anchored
  helper; this call site was missed by that sweep. Found while adding gates to
  the same function.

- **`aide gate approve` with no number crashed** with a `TypeError` instead of
  reporting the missing argument.

- **A gate could silently stop blocking.** `set_gate_status` wrote the
  `--evidence` note straight into a markdown cell, so a note containing `|`
  added a column — and a row with the wrong column count is skipped by the
  parser, turning "a person must decide this" into "nothing is blocking", the
  most dangerous way this feature can fail. The CLI now refuses such a note,
  and `aide check` warns on any gates row it had to skip, so a mangled row
  (a hand edit, a paste) cannot vanish quietly either.

- **Template guidance no longer uses slot syntax to describe a format.** The
  Outcome-targets and environment-gated guidance illustrated their status
  vocabulary with `{{yyyy-mm-dd}}`, `{{evidence}}` and friends. `aide check`
  errors on any `{{...}}` surviving into a consumer's `docs/aide/**`, so a slot
  inside guidance turns "you left the guidance in" into a confusing "unfilled
  template slot" pointing at text that was never a field. Guidance now writes
  the shape plainly (`YYYY-MM-DD`); slots stay on the content lines an author
  actually substitutes. A repo-level test now holds every template to the
  convention it defines — the slip had recurred across two PRs, and a
  convention nothing enforces is one that decays.

### Added

- **Human gates — a first-class mid-queue checkpoint (issue #30).** The loop had
  no mechanism for one, so a consumer encoded it by hand and fragilely: item 105
  had to obtain maintainer approval and tick a `progress.md` checkbox, item 106
  had to halt if that box was unticked — a protocol existing only as prose in
  two specs plus a biconditional pytest invented for the purpose. An unattended
  run reaching it either blocked on a prompt nobody was there to answer or,
  worse, proceeded.

  A `## Human gates` table in `progress.md`, one row per decision only a person
  can make:

  ```
  | Gate | Blocks | Status | Decision / evidence |
  |------|--------|--------|---------------------|
  | Golden-file retirement approved | 106 | ⏳ Awaiting | — |
  | Real segmenter output available | stage 21 | ⏳ Awaiting | — |
  ```

  **Its own table, not an acceptance box.** Those are observable checks *of the
  built thing* (conventions.md §1) — something completing the deliverables can
  guarantee. A steering decision is not, and overloading the checkboxes would
  repeat exactly the conflation Outcome targets (1.4.0) were introduced to
  avoid. Same problem, same shape of answer.

  **Reach is declared per gate, and never a queue.** A queue is an *incidental*
  batch boundary — part of a stage, one stage, or several small ones — so "the
  live queue" names different work from one week to the next while the decision
  has not changed. Blocking is tied to the units that mean something:
  item numbers for a decision affecting one thread (the queue keeps producing
  other work), **`stage N`** when it could *invalidate* a stage's work, and
  **`all`** for a programme-level stop. `stage N` resolves through `progress.md`
  each time it is read, so a gate's reach follows the roadmap as the stage's
  contents change rather than freezing a list written when it was raised.

  **Where a gate is raised, and where it lives** — the same split as Outcome
  targets. A `roadmap.md` stage declares one known at planning time (usually
  `Blocks: stage N`); an item spec declares one found while specifying
  (`Blocks: NNN`); and `progress.md`'s table holds the **authoritative** row,
  because it is the single source of truth for status and the only place the CLI
  reads — a gate existing only as prose blocks nothing. `queue-planner` and
  `spec-author` are instructed accordingly.

  **Any role may raise a gate; only a person may resolve one.** Creating a
  blocker is safe: the worst case is work pausing for a human, so an agent that
  notices a decision is needed should add the row and say so.

  **A declined gate keeps blocking.** It is resolved — someone decided — but the
  answer was "no", so releasing the work would run exactly what was refused. Only
  `✅ Approved` opens a gate, and an unrecognised status blocks too, so a typo in
  the mark cannot silently open one. The remedy for a decline is to re-plan.

  Wired through the verbs it needs to be real:

  - `aide claim` refuses a blocked item and **names the gate** instead of an
    unexplained "none left" — the failure mode that makes a blocked loop look
    broken rather than waiting.
  - `aide check` warns on every gate still blocking (a normal state, not a
    defect — the point is visibility instead of prose buried in a spec).
  - `aide status` prints them, beside Outcome targets.
  - `aide gate (list | approve <n> | decline <n>) [--evidence "…"]` is the
    attestation, so it is a CLI operation no hand edit and no derived rollup can
    fake — the property #22 established for acceptance boxes, applied here.

  **No agent may resolve a gate.** A gate exists precisely because the decision
  is not derivable from the work, so an agent approving one destroys the only
  thing it protects. `/aide-run-item` and `/aide-run-queue` now stop and surface
  the gate rather than prompting an unattended run for a decision nobody is
  there to make.

## [1.12.1] — 2026-08-17

### Changed

- **"Run alongside" in a roadmap now means independence, not concurrency
  (issue #31).** The roadmap could express stage parallelism; the queue model
  cannot represent it, so the hint was silently made sequential and every
  planner re-derived the same apology — two consecutive queues each spent a paragraph
  explaining why they were *not* honouring the roadmap's instruction, leaving a
  standing contradiction between two documents meant to mirror each other.

  The issue offered two directions and asked for the hint's real usage to be
  checked before building the expensive one. Checked, and the evidence is
  decisive: **nobody ever wanted concurrency.** Three different senses were
  riding on one word.

  - The roadmap's own sentence gives itself away — *"19 and 20 are pure audit …
    should run alongside 17/18, **because** every later stage that retunes a
    rule is safer once the catalogue exists"*. The `because` clause is an
    **ordering preference** (do the audit early), not a request to run two
    things at once.
  - The queue that "failed" to honour it explains itself in the same breath:
    *"may be queued and run alongside … **but this queue stays scoped to Stage
    17 alone to keep the batch reviewable**"*. The planner made a good call and
    then apologised for it.
  - Meanwhile three other queues use "in parallel" for **item-level
    independence within one queue** — which has always worked, since `aide
    claim` offers any unblocked item.

  So the fix is vocabulary, not machinery. `conventions.md` names all three
  senses and states plainly that one queue is live at a time *by design* — the
  queue boundary is the human checkpoint, so the model offers no concurrency
  above the item level and a roadmap cannot ask for it. `/aide-create-queue`
  now tells the planner that "run alongside" means the stages do not depend on
  each other's results, so queue next sequentially **and say nothing about it**
  — rather than justifying a conflict that was never there. The roadmap
  template steers authors to write the independence claim directly, or, when
  the real point is that a stage should come early, to write that as an
  ordering constraint a planner can actually honour.

  Direction (a) — a `parallel-with:` marker and a second live queue — is
  deliberately **not** built: no recorded instance needed it, and it would trade
  away the one-review-per-batch checkpoint that the single live queue exists to
  provide.
## [1.12.0] — 2026-08-17

### Added

- **`[hygiene] extra_repos` — a project may legitimately span more than one
  repo (issue #24).** The command-hygiene guard's rule 1 blocks every form of
  "point git at a repo other than cwd" and granted exactly one exception,
  `[framework] local_path`. That baked in the assumption that the consumer repo
  is the only repo an agent ever touches, which fails the moment one project
  spans two repos developed together — a library and a sibling programme repo
  in the recorded case.

  The failure was lopsided in the worst way: `git init` and plain file writes
  both take a path argument, so an agent could **create** the sibling repo and
  **write** into it, but could not `git -C <sibling> add`/`commit` — leaving
  rescued documents uncommitted for a human to finish by hand. A lint that
  blocks the honest spelling of a legitimate operation is one an agent is
  rewarded for evading.

  Declare the repos in the personal, gitignored `.aide/loop/loop.local.toml`:

  ```toml
  [hygiene]
  extra_repos = ["../programme-repo"]
  ```

  **Named for its only consumer — this guard.** `[agent]` was the shape the
  issue sketched, but it implies broad agent configuration when the key does
  exactly one thing, and for a security-relevant setting the name should make
  the blast radius obvious. `[framework] local_path` is unchanged and still
  honoured; these are not framework clones, so overloading it would blur that
  key's narrow meaning.

  **Two invariants deliberately preserved.** Listing a repo *relaxes one lint
  and grants no permission* — the command must still match the allow-list to
  auto-approve, and `git -C …` matches none of the `Bash(git <subcommand>:*)`
  rules, so it prompts. That is the intended posture: the guard exists to stop
  shapes that would stall an unattended run, not to act as a trust boundary,
  and a blanket `Bash(git -C:*)` would have un-gated `git -C <anywhere> push
  --force` for every consumer. And **two different repos in one command stay
  blocked even when both are declared** — history read from one repo and
  applied to another's working tree is a shape no legitimate workflow needs, so
  each declared repo is tried whole rather than the paths being checked against
  a union.

  `conventions.md` §3 now states the rule runtime-generally, since a
  multi-repo project is not a Claude-specific situation.

## [1.11.0] — 2026-08-17

### Added

- **`conventions.md` §6 — test hygiene, and §7 — verify off-platform (issue
  #29).** No role in this loop sees a non-Linux checkout, a different working
  directory, or real CI status: spec → tests → build → validate → merge all run
  in one place, on one platform, against one checkout. A defect invisible under
  those conditions is invisible to the entire loop, indefinitely. **Five have
  reached a consumer's `main` that way, every one caught by a human reading a CI
  log or by a reviewer outside the loop — never by a gate inside it.**

  The existing rule was one thin line ("deterministic and cross-platform… no
  absolute paths"), correct but too general to catch any of them. §6 replaces it
  with the specifics each instance earned, in the engine rather than the adapter
  because they are provider-agnostic and a non-Claude runtime needs them just as
  much:

  - never write the repo's own working-directory path into a test — resolve from
    the test file;
  - any `Path` entering a hash, comparison or match must be `.as_posix()`, since
    `str(Path)` (an f-string included) renders the OS-native separator;
  - a committed byte-exact fixture needs a `.gitattributes` `text eol=lf` pin;
  - prefer calling the function over shelling out to the command that calls it;
  - **assert a derived value is recognisable before asserting anything about
    it** — a glob that matched nothing, an empty capture, a slice from a failed
    `find()` each flow into the assertion and pass while checking nothing.

  §7 addresses the structural half, since no amount of test-writing guidance
  substitutes for one gate that looks at a genuinely different platform:
  `validator` now checks **real CI once a push exists**, and must report the
  honest answer — including "no CI configured" or "it had not finished" — rather
  than letting a green local suite stand in for a platform the loop cannot
  reach. A leg red where local was green is treated as a portability finding
  until its log says otherwise, because every recorded instance looked like a
  content problem and was a platform one.

- **`aide check` warns on a test containing the repository's own absolute
  path** — the one §6 rule a script can decide, and the one whose recorded
  instance survived every gate for weeks. A test that hardcodes the path of the
  repo it lives in passes on the machine that wrote it (an absolute path ignores
  where the process runs, so even a fresh clone into a *different* directory
  still passed) and matches nothing anywhere else; on CI the glob returned
  nothing, the digest collapsed to SHA-256 of empty input, and all four legs
  failed. Matching the repo root literally keeps the rule exact — no judgement
  call, no false positive. Verified against the real historical defect: the lint
  fires on the exact committed line that caused it.

- **`gh run list` / `gh run view` pre-approved** in the adapter's allow-list.
  §7 is only real if the command it names can actually run: an unattended
  validator reaching a non-approved command stalls on a permission prompt
  instead, which is precisely the failure mode a documented-but-unenforced rule
  produces. `gh pr checks` was already approved but needs a PR to exist, and
  under the default `git.mode = "auto-merge"` there is none — so `gh run` is the
  form that works in every mode. Both are read-only.

## [1.10.0] — 2026-08-17

### Added

- **`spec-reviewer` — the half of cross-spec checking a script cannot do
  (issue #27).** 1.9.0 shipped the deterministic half: `aide check --queue`
  decides overlapping claims, changed pinned state, and the dependency graph.
  Two of the seven recorded conflict classes are left, and both turn on what an
  acceptance criterion *means* rather than on what a spec *declares*:

  - **An AC that requires editing a file its own spec forbids.** One item's AC
    said a dataclass "gains an optional field", while that dataclass lived in a
    file the *same spec's* Assumptions explicitly barred editing. Satisfying the
    criterion literally required editing a file the spec forbade. No path-level
    diff finds that — it needs someone who knows where the symbol lives. The
    mirror instance, same queue: an item's Authorised paths omitted a JSON
    schema whose definitions declare `additionalProperties: false`, so wiring
    the key the AC required would have broken **unrelated already-green tests**.
    Invisible to an overlap check, because the path appears nowhere to overlap.
  - **Consuming an interface a sibling left unpinned.** A producer pinned its
    iterator API precisely but never fixed its serialised JSON layout, so the
    consumer shipped a tolerant reader plus a hand-back clause where a straight
    assertion belonged — and a downstream AC was pinned against a value no code
    path produces.

  The agent runs **once per queue**, at the end of `/aide-spec-queue`, after
  every spec is authored and before any is built. It takes `aide check
  --queue`'s `--report` JSON as its worklist rather than re-deriving it, reads
  all N specs at once (that simultaneity is the point of running here), and
  **reports** — it never edits a spec. Every recorded instance needed a
  maintainer call on which side was wrong, and taking that call automatically
  destroys the evidence for it.

  It also owns **row 7**, deferred from #26 with reasons: a spec that retires or
  renames a test which a committed document still names. That is not soundly
  script-decidable — specs legitimately name tests that do not exist yet, and
  `insights.md` names deleted ones by design, so a name sweep fires on correct
  documents. Judgement is the discriminator, which is what this agent is for.

  Specs the script could not parse (no `## Authorised paths`) are routed here
  for a scope read by hand — that is what "reported, never silently skipped"
  means once it reaches a reviewer.

- **`adapters/ADAPTER-SPEC.md` gains an optional sixth definition.** The
  reviewer is deliberately *not* a sixth item role: it never enters one item's
  lifecycle. Any adapter supporting batch spec-authoring should express it at
  T3; one that omits it still gets everything a script can decide, since the
  deterministic half lives in the engine.

- **A frontmatter guard for every `agents/*.md`.** Agent files are discovered by
  filename and dispatched by their `name:`, so a mismatch is not a syntax error
  anywhere — it is an agent that silently never runs, or runs under a name no
  orchestrator invokes. Nothing else in the suite read these files.

### Fixed

- **`docs/aide/status/` was documented as derived output but never gitignored.**
  `core/README.md` and the status-report skill both treat it as regenerable, and
  the reviewer's report is written there — so without the entry a consumer would
  commit it. Added to the installer's managed `.gitignore` block. Two limits
  worth knowing: the block is appended on **fresh install only**, so an existing
  consumer must add the line by hand; and it names the **default** `docs_dir`, so
  a project that moved `docs_dir` is not covered. The reviewer is told to check
  the directory is genuinely ignored and to fall back to a temp path when it is
  not, rather than assuming either.

## [1.9.0] — 2026-08-17

### Added

- **`aide check --queue NNN` — a queue's specs checked against each other,
  before any is built (issue #26).** `validator` runs **per item, after build**.
  There was no counterpart running **per queue, before any build** — which is
  precisely the window `/aide-spec-queue` creates and left unguarded. That
  skill's whole premise is authoring N specs on one branch before any of them
  is built, so every cross-item conflict is both possible and cheaply fixable
  in exactly that window, and nothing looked.

  The invariant, from the consumer post-mortem that found it: *predicting the
  one collision a spec happens to name is not the same as proving no sibling
  assertion depends on state this item's authorised edit changes.*

  Three conflict classes, each with a recorded instance:

  - **Two items claim the same file** under **May change** (warning) — whichever
    builds second inherits the first's edits.
  - **One item may change what another pins** under **Asserts against** (error).
    Under 1.6.0's vocabulary the issue's rows 2 and 3 are *one* check: an
    "Asserts against" entry covers a byte-hash pin and a live recomputation
    alike. That matters because the live-recomputed instance is the one a
    survey hunting fragile-looking byte-hashes missed entirely.
  - **The dependency graph** — a cycle (error) deadlocks `aide claim` outright,
    since every item in it is blocked by another in it, so the queue silently
    stops producing work rather than failing; a dependency on an item with no
    spec and no queue entry (warning) is a typo that blocks an item forever.

  `--report <path>` writes the findings as JSON — the seam a reviewer pass
  (#27) consumes as its worklist rather than re-deriving what this already
  decided. It is written as plain UTF-8, deliberately not the `utf-8-sig` the
  markdown documents use, since `json.loads` rejects a leading BOM.

  **Graceful degradation, per #25.** A spec with no `## Authorised paths` is
  reported with its remedy, never silently skipped — an undeclared spec is not
  an unconstrained one. A *queued* item with no spec yet is the normal
  mid-queue state, so it is counted and named rather than flagged. And the
  cross-spec checks are opt-in: a bare `aide check` behaves exactly as before.

  **An empty May change is not "nothing declared".** A stage-validation item
  legitimately changes only the loop bookkeeping every item may write, while
  pinning the tree it validates under **Asserts against** — so a spec counts as
  undeclared only when *both* lists are empty. Otherwise the specs whose whole
  purpose is to assert would be the ones dropped from the check, and a sibling
  breaking their pins would go unreported. The same rule now governs `aide
  scope`, where checking such a spec is stricter than bailing out: everything
  outside the always-authorised bookkeeping is out of scope for it.

  Overlap detection deliberately decides only what a script can prove —
  identical patterns, a subtree wildcard swallowing the other, a literal path
  covered by the other's glob. Two unrelated globs that might one day intersect
  on some file neither spec has thought of are not guessed at. Loop bookkeeping
  (`progress.md`, `insights.md`) is excluded from the overlap check, since every
  item writes both and "conflicting" over `progress.md` is the claim protocol
  working — that was 4 of 16 warnings on a real consumer queue. It stays in the
  pinned-state check, where pinning `progress.md` would be a real assertion.

### Known gap

- The issue's **row 7** — a spec deletes a test another committed document names
  — is **not** implemented, and is routed to #27 instead. The generic form is
  not soundly script-decidable: item specs legitimately name tests that do not
  exist yet, and `insights.md` names deleted ones by design, so a name-based
  sweep would fire on correct documents. Making it decidable needs a convention
  marking which references assert a *live* test — a vocabulary addition of the
  #25 kind, not something to guess at here.

## [1.8.0] — 2026-08-17

### Added

- **A base ref the loop can land work on, not just `main` (issue #23).**
  `aide merge` hard-wired its target to `[git] main_branch` and offered no
  override, so the loop could not express the stacked branching real work
  produces. Concretely, in a consumer's queue-016 the queue file, a roadmap
  deliverable and all nine item specs lived only on the queue branch and were
  meant to land as **one** reviewed PR — so each item had to branch off *and
  merge back into* that branch. Half the machinery was already right: `aide
  claim` creates the branch from whatever is checked out, so claiming from a
  queue branch had always branched correctly. Only the merge target was fixed.

  `--base <ref>` now exists on **`claim`**, **`merge`**, **`gc`** (which ref
  `--merged` is measured against), **`status`** (what ahead/behind reports
  from) and **`scope`** (what the diff is taken against). Resolution is always
  `--base` > recorded > `main_branch`, and **`main_branch` remains the default
  everywhere** — nothing that worked before behaves differently.

  **The claim remembers what it branched off**, so the flag is rarely needed:
  `aide merge NNN` returns the item to its recorded base, which means the
  validator's documented merge step is already correct on a queue branch. That
  matters because the recorded workaround was the orchestrator merging every
  item by hand — overriding `validator.md`'s documented step once per item and
  re-implementing the verb's pre-merge suite gate, push and branch cleanup in
  prose. The alternative workaround, repointing `main_branch` in `aide.toml`,
  also repoints `sync`/`gc`/`status` and leaves a trap in a committed,
  PR-gated file.

  Inference is deliberately narrow: a base is inferred **only** from a
  recognised queue branch (`<prefix>queue-NNN`, `<prefix>specs-queue-NNN`),
  never from an arbitrary checked-out branch, which would silently retarget a
  merge. The record is local git config rather than a committed file — the base
  is a fact about this checkout's branching, so another machine falls back to
  `main_branch` and passes `--base` explicitly.

  Two invariants hold the feature together, both found in review:

  - **A claim branches *from* its base.** `git switch -c` with no start point
    uses `HEAD`, which would let a branch's real starting point disagree with
    the base it records — claiming with `--base main` while a queue branch is
    checked out would start from the queue branch and then merge the whole of
    it into `main`. Naming the start point makes the two agree by construction,
    and incidentally fixes the older case of claiming from an unrelated branch.
  - **A base must be a local branch, not merely a resolvable ref.** `git
    switch` on a tag, a raw commit, or a remote-tracking ref like `origin/main`
    detaches HEAD; a merge into a detached HEAD updates no branch at all, yet
    still reports success and lets the claim branch be deleted, leaving the
    work as an unreferenced commit. `claim` and `merge` both check the ref's
    *kind* now, and say which of the two things is wrong.

### Fixed

- **`aide scope` diffed stacked work against the wrong ref.** Its default base
  was `origin/<main_branch>`, so an item claimed from a queue branch was
  compared against `main` — reporting every sibling item already merged into
  that queue as the current item's own out-of-scope change. It now consults the
  recorded base first (still preferring the `origin/` counterpart of whatever
  it lands on), which is the gap noted when the verb shipped in 1.7.0.

## [1.7.0] — 2026-08-17

### Added

- **`aide scope` — the diff-time counterpart to a byte-hash scope fence (issue
  #28).** 1.6.0 gave an item a place to declare what it may change; this is what
  reads it. A consumer had already built the equivalent as a project script and
  wired it into CI, but it did framework-shaped work — enforcing a framework
  convention, on framework documents, in the framework's own loop — while living
  in the project, so every other consumer would have reinvented it.

  ```
  python .aide/scripts/aide.py scope [NNN] [--base <ref>]
  ```

  It asserts the claim a fence encoded — "item N changed only these files" —
  once, on the branch, instead of enshrining it as a suite assertion that
  outlives its truth. Exit `0` in scope · `1` something changed outside it · `2`
  could not check.

  Both defects the issue named are fixed in the promotion:

  - **Glob support.** `dir/*.ext` is the form specs actually write (it appears
    in the authorised paths of at least nine merged specs in the consumer that
    reported this), and the original matcher understood only an exact path or a
    `/**` suffix — so any item that legitimately regenerated a directory of
    goldens had every one of them reported as unauthorised, a false positive
    independent of the item's real scope. Matching is now per path segment via
    `fnmatch`, which keeps `*` from crossing a `/` and silently widening every
    glob into a subtree wildcard.
  - **The base ref.** The default is now the merge-base with `origin/<main>`,
    not a bare local ref. On a checkout whose local `main` sits behind the work,
    the merge-base with it *is* it, so every file the earlier items touched was
    reported against the current item's spec — ~90 of them in the recorded case,
    a violation list byte-identical with and without the item's own edits
    staged. CI was never affected (it passes an explicit base), which is exactly
    what made this a local-invocation footgun, and a costly one: item specs tell
    the builder and validator to run the scope check as a validation step.

  Three things the promotion adds beyond the consumer's script:

  - **It reads the item from the claim branch**, via the anchored branch→item
    resolution added in 1.5.0 — so a queue branch resolves to no item and is
    skipped with a reason, rather than matching a bare 3-digit run and
    hard-erroring against an unrelated, long-finished item's spec. That is the
    failure the consumer hit the first time a queue branch was ever PR'd.
  - **It understands 1.6.0's two sub-lists.** Only **May change** authorises;
    a path declared under **Asserts against** and then changed is reported as
    its own finding, because the remedy differs — one widens a list, the other
    means an assertion in this very item now pins state the item moved. Bullets
    written before either label existed still read as **May change**, so the
    flat legacy form parses rather than coming back silently empty.
  - **Loop bookkeeping is authorised without being listed** — `progress.md` and
    `insights.md`, which the CLI and the roles are mandated to write on any
    item, plus the item's own spec, where the builder records decisions.
    Otherwise every spec would repeat the same boilerplate bullets, and
    appending an insight — named in conventions.md §1 as the one write allowed
    outside an agent's edit scope — would be flagged as scope creep.

### Changed

- **`validator` runs the check instead of eyeballing the diff**, and must say so
  in its report when the check could not run (exit 2, a spec predating the
  convention) rather than passing in silence. `builder` can run it before
  handing off to see what the validator will see. `conventions.md` §3's
  "if an `aide` verb covers it, the raw git form is wrong" rule now names
  `aide scope` alongside `sync`/`claim`/`merge`/`gc`.

## [1.6.0] — 2026-08-17

### Added

- **`## Authorised paths` — an item declares its own scope (issue #25).** A
  consumer running this loop independently invented two conventions the
  framework had no notion of: a spec section declaring which files an item may
  change, and a "scope fence" — a test hashing some *other* file's bytes against
  a hardcoded literal to prove the item did not touch it. Grepping `core/` and
  `adapters/` for either returned zero hits, so every spec author re-derived
  them, and they collided with each other in a way nothing checked. Eight
  recorded instances, three of which broke CI.

  The section ships in `core/templates/item.md` and is specified in
  `core/conventions.md` §1. It carries two lists: **May change** (the paths this
  item may modify — exact path, `dir/**`, or `dir/*.ext`) and **Asserts
  against** (files and derived artifacts its tests read and pin without
  changing, *including* anything recomputed live from committed state).

  The second list is the half the consumer's post-mortems kept arriving at:
  predicting the one collision a spec happens to name is not the same as proving
  no sibling assertion depends on state this item's authorised edit changes. A
  live recomputation is *more* coupled to the underlying state than a byte-hash,
  not less, and was missed by a survey looking only for fragile-looking hashes.

  **Expected but not required.** Specs predating the convention stay workable
  without a repo-wide back-fill; a tool that reads the section and does not find
  it must report that with the remedy, never treat an undeclared spec as
  unconstrained. This is the declared vocabulary that issues #26, #27 and #28
  read — all three are unimplementable without it.

### Changed

- **Scope is proved by the diff, not by a hash.** `conventions.md` now states
  the preference outright and demotes the byte-hash scope fence to a fallback,
  with the four failure modes each instance earned: it inverts on the next
  legitimate edit of the pinned file; a whole-tree digest collides with any
  future edit beneath it; an unfiltered tree walk hashes gitignored
  `__pycache__` bytes that embed mtimes, so the pin is not reproducible even
  against an unchanged tree; and it is platform-fragile in two specific ways —
  any path component entering a hash must be `Path.as_posix()`, and a
  byte-exact committed fixture needs a `text eol=lf` pin in `.gitattributes`.

  Two rules come with it. **Re-pinning**: when a later item is authorised to
  change a pinned file, update the earlier constant in the same commit with a
  comment naming the authorising item — and distinguish a diff-time scope claim
  (belongs in **Asserts against**, retired when its item merges) from an
  artifact-integrity invariant (legitimate and durable, but belongs in a test
  named for the artifact and living beside it, not in an unrelated item's
  regression module under a `_PRE_NNN_` name). **Auditing goes by shape, not by
  name**: the distinguishing feature is a digest compared against a hardcoded
  literal, since one compared against a value computed in the same run is a
  determinism check that must stay. A sweep by constant name missed three
  surviving fences in the consumer that ran it.

- **Interface pinning between unbuilt siblings now runs both ways**
  (`conventions.md` §5, `/aide-spec-queue`). The consumer-side duty was already
  stated; the producing spec must now enumerate the **serialised** shape its
  consumers read — the JSON layout, which records appear in a walk, what strict
  mode rejects — not only its API. Left unpinned, each consumer independently
  ships a tolerant reader plus a hand-back clause where a straight assertion
  belonged, and one eventually pins an assertion against a shape no code path
  produces.

- **The declaration has readers from the moment it exists.** `spec-author` fills
  it concretely and is told not to specify a byte-hash fence; `builder` stays
  inside **May change** and hands back — naming the path — when an AC cannot be
  satisfied without more, rather than widening its own scope silently;
  `validator`'s scope check now compares the branch's changed files against the
  list, and says so explicitly when a spec has no section rather than passing in
  silence. `/aide-spec-queue` gained a batch-reconciliation step, since all N
  specs being visible at once is the one moment a cross-item collision is cheap
  to fix.

## [1.5.1] — 2026-08-17

### Fixed

- **`aide gc` and `aide check` named a problem without naming its remedy
  (issue #33).** All three gaps were signposting, not missing capability — the
  verb that resolves them already existed — and each one's cost was the same:
  the reader's next reach was the raw `git branch -d` that `.aide/README.md`
  says to prefer a verb over.

  `gc` has two independent grounds, and the item ground structurally cannot
  see a queue or unrecognised branch (deliberately, since 1.5.0). But the bare
  invocation still reported `nothing to clean` while `aide gc --merged` would
  have offered three branches — a true statement about the ground checked,
  read as a false one about the repository. It now names `--merged` when that
  ground would actually find something; the probe runs only on the empty path,
  never in the normal one.

  `gc` also only ever considers branches under `branch_prefix`, so a merged
  branch named anything else was never examined on either ground and nothing
  said so. The restriction is correct and unchanged — `gc` is the one
  destructive verb and must not delete branches it does not own — but it is no
  longer silent: an empty result now states the scope and how many other local
  branches it therefore did not consider.

  The `unrecognised branch` warning had the mirror-image shape: it explained
  the convention that was missed but never what to do about it. It now ends
  with the action (rename to the claim shape, or delete via `aide gc --merged`
  once merged).

### Added

- **A regression guard for the `str(Path)` separator class (issue #34).** A
  `Path` rendered with `str()` — or interpolated into an f-string, which calls
  `str()` — carries the host's separator into any value that is then compared,
  hashed, or matched. That class has caused four separate CI-only failures in
  a consumer, every one invisible to a Linux checkout and every one found by a
  human reading the Actions tab rather than by any gate.

  A full sweep of every Python file a consumer installs or executes found **no
  remaining site**: the surviving `str(...)` calls are config values,
  subprocess `cwd`/argv (where native separators are required), git paths
  (always POSIX by git's own contract), human-facing log output, or the
  hygiene guard's deliberate `normcase`/`normpath` comparison of two paths on
  one machine. But a clean sweep does not prevent the fifth instance, so
  `run_checks`' returned `(errors, warnings)` — the surface consumers actually
  parse — is now pinned by a test that puts findings in a subdirectory, the
  only case where separators diverge, and asserts none carries a backslash.

## [1.5.0] — 2026-08-17

Five correctness defects found running a consumer's queues 013–016 (issue #22).

### Added

- **`aide progress accept <stage> (--criterion N | --all) [--evidence "…"]`** —
  the explicit way to tick an acceptance checkbox, replacing the auto-tick
  removed below. An already-ticked box is reported and left alone rather than
  counted as newly accepted; an unknown stage or an out-of-range index is a
  loud error, never a silent no-op. `--evidence` appends an annotation beside
  the ticked box recording what was checked.

### Changed

- **`aide progress set` no longer ticks acceptance checkboxes.** It recomputed
  every stage's rollup on every call and force-ticked every `- [ ]` in any
  stage that derived complete — so a box deliberately left unticked to record
  a criterion that shipped *unmet* was silently flipped back to ticked by the
  next status change for **any** item in **any** stage, converting a recorded
  shortfall into a claim nobody had made. A consumer hit this on two separate
  stages and could not keep either honest, since `.aide/**` is generated and a
  hand-edit is overwritten on the next update.

  A derived tick is not an attestation, and the tick had no readers to serve:
  `stage_deliverable_statuses` skips checkbox lines, the rollup never sees
  them, and no `aide check` rule gates a ✅ stage on them. Acceptance is now
  attested by whoever performed the check, via `aide progress accept`;
  conventions.md §1 states that a stage may be ✅ with an unticked box, and the
  validator's PASS sequence ticks only criteria it actually verified.

  **Consumer action:** none. Already-ticked boxes stay ticked. A stage closed
  in future will show its acceptance boxes as its author left them, which for
  most projects means running `aide progress accept` once per verified
  criterion where `progress set` previously ticked them wholesale.

### Fixed

- **A queue branch was read as an item claim, and `gc` could delete it.**
  Branch-to-item resolution fell back to an unanchored digit search, so
  `aide/queue-016` — the branch name `/aide-create-queue`'s hand-off and
  `/aide-run-roadmap` both tell authors to create — resolved to *item 016*, an
  unrelated and usually long-finished work item (`aide/specs-queue-015`
  likewise). Queue numbers and item numbers share one namespace with no
  syntactic marker between them.

  The consequence went well past the spurious `aide check` warning that
  surfaced it: `gc` targets any branch whose item is ✅ **independently of
  `--merged`**, then deletes it with `git branch -D` plus a remote delete. So
  `aide gc --yes` would destroy an in-flight queue branch, local and remote,
  along with the queue file and item specs living only on it — for any project
  whose item NNN had finished, which after a few queues is all of them.

  Resolution is now a single anchored helper matching the branch shape
  conventions.md §4 already documents (`<branch_prefix>NNN-short-name`), shared
  by `check`, `merge`, `sync --item`, `status` and `gc` instead of three
  divergent copies. Queue and specs-queue branches are recognised positively
  and reported as what they are; a prefixed branch matching neither shape is
  reported as unrecognised rather than silently skipped, so anchoring cannot
  hide a real stale claim.

- **`aide check` rendered OS-native path separators in its output.** Both
  warning locations were built by f-stringing a `Path`, which calls `str()`, so
  the identical document reported as `queue/queue-002.md:80` on Linux and
  `queue\queue-002.md:80` on Windows — and only locations with a subdirectory
  component diverged, making it read as a content problem rather than a
  platform one. Now `.as_posix()`. Any consumer parsing `aide check` output
  rather than calling `run_checks` was inheriting this.

- **The unfilled-slot rule rejected GitHub Actions expressions quoted in
  prose.** `template_residue_errors` scans for a literal `{{` and *errors*, so
  any living document discussing a workflow — an item spec explaining what a CI
  step runs, an insight recording a workflow's arguments — turned `aide check`
  red on prose that was correct as written, and the only remedy was to stop
  naming the real syntax. The pattern now exempts a `$` immediately preceding
  the braces, and nothing else: AIDE slots are never `$`-prefixed. Suppressing
  matches inside backtick code spans would have been wrong, since the item
  template's own `Suggested branch` line carries a genuine slot inside one.

- **The insights inbox forbade the edit its own triage procedure requires.**
  `core/templates/insights.md` closed with "Append-only: never rewrite,
  reorder, or delete existing lines" while instructing the triager, six lines
  above, to tick the entry's checkbox in place and append a "→ where it landed"
  pointer — so every triage pass had to violate the stated rule to follow the
  stated procedure. `conventions.md` §1 carried the same contradiction
  independently. Both now permit exactly those two triage edits and prohibit
  any other rewrite, reorder or deletion.

## [1.4.2] — 2026-07-26

### Fixed

- **`_item_dependencies` only read the first number in a multi-item
  Dependencies reference, and had no directionality check.** `aide claim`'s
  blocking-dependency scan used its own naive `\bItem[s]?\s+0*(\d+)` regex
  instead of the shared, already-fixed `_referenced_item_numbers` (issue
  #15's fix, 1.3.1) — so "Items 093, 094, 095" registered only 093 as a
  blocker, and a forward-looking aside naming a *later* item ("**Downstream:**
  item 099 depends on this item's CI job") was misread as a backward
  dependency on that later item. Concretely: a stage-closing item could be
  offered by `aide claim` before its actual prerequisites existed, while an
  unrelated item was skipped because it "depended on" a downstream item that
  hadn't even been claimed yet.

  `_item_dependencies` now reuses `_referenced_item_numbers` (same
  case-insensitive, list/range-aware extraction every other item-reference
  call site uses) and stops scanning at a literal `**Downstream` marker,
  which is now a documented convention (item template + conventions.md §1)
  for noting a forward reference without it being read as a blocker.

- **The command-hygiene guard's `[framework] local_path` carve-out lived in
  the shared, committed `aide.toml`, and only recognised one of the four
  syntaxes that point git at a repo other than cwd.** A machine-specific
  filesystem path (where a developer's local `aide-loop` clone happens to
  live) has no business in a file every consumer of the project shares — the
  same principle `aide.toml`'s own `[validation]` section already states for
  its profiles. `local_path` now lives in the personal, gitignored
  `.aide/loop/loop.local.toml` (`[framework]` section, alongside the existing
  `[loop]` one) instead; `loop.local.toml.example` documents both sections.
  `install.py`'s generated `aide.toml` no longer suggests setting it there.

  Separately, the guard's rule 1 recognised only `git -C <path>` — leaving
  `--git-dir=<path>`, `--work-tree=<path>`, and the `GIT_DIR=`/
  `GIT_WORK_TREE=` environment-variable prefixes (git's own equivalents,
  achieving the identical effect) completely unchecked: an agent that hit
  the `-C` block and reached for the next thing it knew could reach the exact
  repo the exception was built to gate, without ever declaring it. All four
  forms are now recognised, checked against the same declared `local_path`
  (`--git-dir`/`GIT_DIR=` accept the conventional `<path>/.git` value too,
  not only `<path>` itself), and a command mixing a declared and an
  undeclared repo across two of the forms stays blocked rather than guessed
  at.

- **The validator's foreground-only rule didn't name `aide merge`.** The
  instruction to run the test suite synchronously in the foreground (never
  backgrounded) only covered the standalone `pytest` step; `aide merge`
  itself re-runs the full suite again under `git.mode = "auto-merge"` and
  takes just as long, but nothing told the validator that command needed the
  same discipline — in practice, sub-agents repeatedly deferred it to a
  background task and ended their turn with a placeholder, leaving the
  orchestrator with no verdict. The rule now explicitly names `aide merge`
  at both the point it's introduced and the point it's invoked.

## [1.4.1] — 2026-07-23

### Fixed

- **Any prose mention of "Item NNN" was read as a status declaration (issue
  #15).** `_parse_item_status` treated every occurrence of an item reference
  anywhere in `progress.md` as status-bearing, attributing to it whatever
  status terminated the line or its enclosing bullet. In practice that meant a
  verification-table Notes cell narrating a post-mortem across several item
  numbers, or an acceptance checkbox that merely cited the item it satisfies,
  could silently pull that item's tracked status backwards — the more
  honestly a project documented *why* something went wrong, the more spurious
  references it created.

  conventions.md §1 is specific that the only structural status declaration is
  a deliverable bullet's leading icon. `_parse_item_status` now attributes a
  reference only when it sits on such a bullet or one of its wrapped
  continuation lines (indented text with no bullet marker of its own) — a
  table cell, a checkbox, or an ordinary paragraph may name an item freely
  without affecting its status, exactly as the format contract already
  promised authors.

  **Consumer action:** none. A project whose narrative prose or acceptance
  checkboxes named item numbers may see those items' derived status move
  forward (to whatever their real deliverable bullet says, or absent if they
  have none yet) after updating; no document edit is required.

## [1.4.0] — 2026-07-23

### Added

- **Outcome targets — an expressible state for "the work shipped but the goal
  was not met" (issue #14).** The rollup deliberately equates a stage's ✅ with
  *its planned work shipped*; when a stage also carried a measured goal (an
  error-rate target, a benchmark), that goal had nowhere honest to live — it
  either became an Acceptance box that was auto-ticked into an over-claim, or
  the stage was held 🚧 forever against `aide check`'s permanent warning.
  progress.md now supports an optional `## Outcome targets` table
  (`| Target | Objective | Attempted by | Status | Evidence / follow-up |`,
  statuses `❓ Unverified` / `✅ Met` / `❌ Not met`, mirroring the env-gated
  verification table's table-local vocabulary). Semantics: a target never
  blocks its stage — it gates the **Objective coverage rows** instead.
  `aide progress` caps an objective's rollup below ✅ while a linked target is
  not Met; `aide check` errors on an objective claimed ✅ over a `❌ Not met`
  target (the goal-level mirror of the deliverable-level over-claim error) and
  warns on `❓ Unverified`; `aide status` prints every target not yet Met. A
  `❌ Not met` target routes through the insights inbox (`gap`), so follow-on
  work enters via the queue instead of retro-editing a closed stage's
  deliverable list. The roadmap template gains `Target:` bullets to mark
  outcome-shaped criteria; conventions.md §1 documents the split (stages track
  shipped work, targets track measured outcomes, objectives require both).

## [1.3.3] — 2026-07-23

### Added

- **`core/README.md`, installed as `.aide/README.md` (issue #16).** A consumer's
  `CLAUDE.md` links to `.aide/README.md` three times — for the loop, the
  orchestrators, and the merge policy — but no installer ever shipped that file.
  It existed in the original in-tree `.aide` skeleton and was deleted when the
  repo adopted the standalone framework, so the links survived the file. No
  installer change was needed: `install_engine` already copies `core/` wholesale,
  so a file added there ships automatically.

  The new file is consumer-framed (`.aide/…`, `.claude/…` paths) and covers what
  a consumer needs that `conventions.md` deliberately doesn't: what's in `.aide/`,
  the six-step loop, the three orchestrators, model routing by capability tier,
  the merge policy, and shared-vs-personal files. It excludes anything about
  maintaining the framework itself (install instructions, the version-bump
  policy, this repo's own layout) — that stays in the root `README.md`, which now
  links to `core/README.md` instead of carrying a second copy of the same
  sections.

  Also added `tests/test_installed_docs_links.py`, which installs into a temp
  directory and asserts every relative markdown link under the installed
  `.aide/` resolves — so a future file move or rename that breaks a consumer-side
  link fails the suite instead of surfacing three commits later in someone
  else's `CLAUDE.md`.

  **Also fixed:** `pytest.ini`'s `testpaths` only listed `core adapters`, so a
  bare `pytest` (what CI runs) silently skipped the whole top-level `tests/`
  suite — including `test_repo_versioning.py`, the very test that enforces the
  `core/VERSION` bump rule this entry follows. `testpaths` now includes `tests`.

## [1.3.2] — 2026-07-23

### Fixed

- **`aide check`'s stray-icon lint flagged the icon vocabulary anywhere it
  appeared in prose, drowning real warnings in noise (issue #13).**
  `_stray_icons_in_line` treated any line that wasn't a table row, a queue
  status line, or a leading-icon bullet as fair game to flag *every* icon on
  it — so an ordinary sentence, or a bullet whose text merely mentioned an
  icon mid-sentence, tripped the same warning as a genuine misplaced status
  icon. conventions.md §1 is explicit that only three positions are
  structural (a deliverable bullet's leading icon, a table row's last cell, a
  stage header's trailing icon); everywhere else the icon vocabulary is prose
  by design. The lint now only ever fires on a heading whose status-shaped
  icon sits somewhere other than the trailing position — the one remaining
  shape where a reader could plausibly misread it as the header's status.

## [1.3.1] — 2026-07-23

### Fixed

- **`*(Items A, B)*` credited only the first item, which could strand
  `aide claim` on a finished queue.** `_parse_item_status` matched
  `[Ii]tem[s]?\s+0*(\d+)` — the word "Item(s)" followed by *one* number — so in
  the multi-item reference the create-queue step explicitly tells authors to
  write (`… *(Items 006, NNN)*`, for a deliverable delivered by several items)
  every number after the first was invisible.

  Orphaned items read as `planned` forever even while sitting on a ✅
  deliverable bullet. Because a queue is open while any of its items is
  planned/in-progress, and the *live* queue is the lowest-numbered open one,
  those phantom-open items pinned the live queue to a long-finished batch;
  `aide claim`, scoped to the live queue, then reported `none left` and never
  looked at the current one. A consumer hit exactly this: seven items across
  four queues, all on green bullets, wedged the loop so that a newly created
  queue would have been invisible to it.

  The root cause was two different notions of "item NNN is referenced" in one
  module: the status parse above, and `_item_ref_re` (used by `aide progress
  set`), which matched any number literally present inside the reference. So
  `progress set` acted happily on an item `check`/`status`/`claim` believed
  untracked.

  Both now go through a single `_referenced_item_numbers`, and the accepted
  reference forms are written down in `conventions.md` §1: `*(Item 006)*`,
  `*(Items 006, 044)*`, `*(Items 089/090)*`, and inclusive ranges
  `*(Items 071–075)*` (hyphen or en-dash). **Ranges are now expanded**, so an
  item named only inside one is tracked and `aide progress set` can flip its
  bullet — previously `071–075` credited `071` alone and silently orphaned the
  three interior items. A range wider than 50 is treated as a typo and
  contributes only its endpoints.

  **Consumer action:** none. Projects whose multi-item references were being
  half-read will see the affected queues close and `aide claim` resume on the
  correct queue after updating; no document edit is required.

## [1.3.0] — 2026-07-23

### Changed

- **Living documents no longer end with a "Next: run `/aide-…`" pointer.** Every
  generated document carried one, and each was stale shortly after it was
  written: `progress.md` — edited on every merged item — still said "run
  `/aide-create-queue` to generate the first batch" at queue 7, and a reader had
  no way to tell a stale pointer from a current one. A step-scoped instruction
  stored in a project-lifetime document is guaranteed drift.

  The hand-off is now spoken rather than stored: `vision.md`, `roadmap.md`,
  `progress.md`, `queue-NNN.md`, and `items/NNN-*.md` end at their last content
  section, and the skill that writes the file names the next step in its closing
  message to the user (and, for a queue, in the PR body). The skills' `## Next
  Step` sections are renamed `## Hand-off`.

  The durable half of that information moves into each template's **header
  blockquote** — the document's step in the loop, what it derives from, and what
  derives from it. `vision.md` names itself the root of roadmap/progress/queues/
  items; `roadmap.md` names progress as its mirror; `progress.md` states that
  queue state derives from it and item specs deliberately carry no status;
  `queue-NNN.md` points at `../items/` and back at `progress.md`. Described in
  `conventions.md` §1.

  **No consumer action required** — nothing parses these lines and `aide check`
  does not flag them, so existing documents stay valid. Delete the trailing
  `Next:` line the next time you touch one.

### Added

- **`CLAUDE.md` for this repo.** aide-loop is the framework, not a consumer of
  it, and an agent arriving here would otherwise look for `docs/aide/` and an
  `aide.toml` that do not exist. Covers the source-vs-installed path trap (the
  `.aide/…` references under `core/` and `adapters/` are consumer paths and must
  not be "fixed"), the enforced `core/VERSION` bump rule, the stdlib-only test
  setup, and how to try a change in a real consumer from the local working tree.

## [1.2.2] — 2026-07-23

### Fixed

- **A malformed `aide.toml` behaved differently on different Pythons, and one of
  them was silent.** On 3.11 `tomllib` raised an uncaught `TOMLDecodeError` —
  `load_config` caught only `ModuleNotFoundError` — so the user got a traceback
  through `tomllib` internals that never named the offending file. On 3.9 the
  fallback parser *accepted* the same file: `name = "unterminated` yielded the
  truncated text as the value, so a typo became a plausible wrong answer.

  `load_config` now raises `ConfigError` on either path, with one message naming
  the path and the line. `main` catches it and prints `error: …` with exit 2, so
  no subcommand shows a traceback for a user-fixable file. The fallback parser
  rejects an unterminated quoted string rather than misreading it, which is what
  makes the two paths agree.

  A *missing* `aide.toml` is still fine — that means "unconfigured", and defaults
  are the right answer. A malformed one is not: it states facts (`source_dir`,
  git mode, test command) that the framework acts on, so continuing on defaults
  would scope the builder at the wrong directory while reporting success.

## [1.2.1] — 2026-07-22

### Fixed

- **A byte-order mark in a project-owned file silently changed how it was read.**
  Windows editors (Notepad, PowerShell `Out-File`, several IDEs' "Save as UTF-8")
  prepend U+FEFF; read as plain UTF-8 that codepoint survives into the text and
  breaks first-line parsing. Every read of a file that lives in a consumer repo —
  `aide.toml`, the `docs/aide/` living documents, `loop.local.toml`,
  `.claude/settings.json`, the settings overlay, `.gitignore`, `.aide/VERSION` —
  now uses `utf-8-sig`, which strips a BOM when present and is byte-identical to
  `utf-8` when absent.

  The worst case was silent rather than loud. `aide.toml` read with a BOM lost
  **only its first table** — the fallback TOML parser's `^\[table\]$` match fails
  on the BOM'd line while every later table parses normally — so `[project]`
  vanished and `source_dir` reverted to its default while `[git]` was still
  honoured. A half-correct config, no error, every command reporting success.
  On Python 3.11 the same file raised an uncaught `TOMLDecodeError` instead.

  Also fixed: a BOM'd `settings.json` crashed the permission reviewer's
  `load_rules`, made `install.py` see a spurious difference from the framework
  base (emitting a pointless `.aide-merge` on every run), and could cause the
  `.gitignore` block to be appended twice.

## [1.2.0] — 2026-07-22

Seventeen consumer-visible commits had accumulated under `1.1.0` before this
release; the version number had stopped moving while the engine changed
substantially. This release ships them and adds the policy + tooling that stop it
recurring.

### Added

- **`aide sync` / `aide gc` / `aide status`** — session preflight, claim-branch
  clean-up, and a one-call roadmap-state report. Conventions now state that the
  improvised `git fetch`/`status`/`switch` equivalents are wrong when a verb
  covers it.
- **Insight inbox** (`docs/aide/insights.md`, `core/templates/insights.md`) — the
  compound-engineering capture point. Any role appends one typed line
  (`knowledge`/`defect`/`gap`/`automation`/`framework`) and returns to its task;
  `/aide-feedback-loop` triages at the queue boundary. `aide check` shape-checks
  entries as a warning, never an error, so capture stays cheap.
- **Planned meaning-level validation** — `[validation]` environment profiles in
  `aide.toml`, evaluated by `aide env --profile <name>`, plus an optional
  `## Validation` section in item specs the validator must execute. A gated path
  that cannot run records `❓ Unverified` instead of passing silently.
- **Deterministic settings reconciliation** — a project-owned
  `.claude/settings.overlay.json`. While present, `settings.json` is regenerated
  on every install/update as a base+overlay deep-merge, so framework changes flow
  through and project additions reapply without hand-merging `.aide-merge`. The
  installer also derives a ready-to-adopt overlay for existing projects and
  templates the write-scope globs from `aide.toml` `source_dir`/`tests_dir`.
- **`loop.claim_scope`** (`live-queue` | `all-open`) — opt into claiming across
  every open queue rather than only the live one.
- **`[framework] repo`** — where `framework`-typed insights are handed over.
- **`install.py --check`** — compare a consumer's installed `.aide/VERSION`
  against `core/VERSION` and report whether it is current, behind, or ahead.
  Exits non-zero when behind, so a consumer can gate on it.

### Changed

- **Queue state is derived, not declared.** A queue is open iff any of its items
  is 📋/🚧 in `progress.md`; the `> **Status:**` line is now optional decoration,
  and `aide check` warns only when a declared status contradicts the derived one.
- **Status icons are read only at structural positions** — a table row's status
  cell, a stage header's trailing `— <icon>`, a deliverable bullet's leading
  icon. An icon in prose is plain text, so authors need not avoid the vocabulary
  in free text.
- The unattended launch contract and execution surfaces are pinned; the usage
  probe is now a documented core/adapter seam (`[loop] usage_probe`).

### Fixed

- **`/aide-review-permissions` promoted rules into a generated file.** With an
  overlay adopted, `.claude/settings.json` is regenerated on every update, so a
  rule written there was silently discarded. The command and
  `review_permissions.py` now detect the overlay and name
  `permissions.allow.add` as the destination, falling back to `settings.json`
  only when no overlay exists.
- `install.py` writes UTF-8 stdout, so installing survives a non-UTF-8 console.
- The Claude hook interpreter is probed functionally rather than by PATH
  presence, fixing the Windows Store `python.exe` alias stub.
- `settings.json` works across Windows and Linux.
- `aide progress` no longer silently no-ops when no deliverable references the
  item.

## [1.1.0] — 2026-07-14

### Added

- Environment-gated capability tracking: a capability behind an optional package
  or external tool declares itself, and CI can verify it actually ran rather than
  skipped.

## [1.0.0] — 2026-07-07

Initial standalone release: the framework extracted from its origin project into
a provider-agnostic engine (`core/`) plus swappable adapters (`adapters/`), with
`install.py` materialising them into a consumer as `.aide/` and `.claude/`.
