## 4. Git modes (`git.mode` in `aide.toml`)

Governs what the mode changes — where a claim branch goes, how an item lands,
and what kind of CI gate can see it. The human who sets it reads this; the
validator's merge step is pointed here, and `aide claim` and `aide merge`
carry it out.

Enforced **only** inside `aide claim` / `aide merge`; agent instructions are
identical across modes.

- **`auto-merge`** (default) — claim branch pushed; on validator PASS `aide merge`
  direct-merges to `main`, deletes the claim branch, then re-runs the test
  command and `aide check`. Both are a **gate**: green earns the ✅ and the
  push, red leaves the merge local, the item 🔍 and the claim branch back where
  it was, and says so. For `aide check` only an error is red; a warning is
  reported and never blocks.
- **`pr`** — claim identical; on PASS `aide merge` pushes the branch and **stops**
  ("open a PR"). The human opens the PR (`gh pr create` stays `ask`-gated).
- **`local`** — no pushes at all (offline). Claim is a local branch only (no
  multi-machine signal); merge is local into `main`, behind the same gate.

**A red test run is compared with the base before it refuses.** Where the
test command's report names each failing test — pytest, run as a module —
`aide merge` runs the same command on the base as it stood before the merge,
in the same checkout, or reuses a run this repository already recorded for
that tree. When every failure after the merge also fails there, the failures
are **inherited**, and the gate admits the merge: it prints both sets, counts
them in the ledger row (§1 → `ledger.md`), and appends one `defect` entry to
`insights.md` naming each inherited test no open entry already names,
committed with the ✅. A failure the base does not have is the item's, and
refuses the ✅ and the push as before, listed apart from the inherited ones.
A run that cannot be compared — another runner, a command whose failures
depend on the run rather than the tree, an incomplete run, a base the
history does not identify — refuses on any failure. No flag and no
`aide.toml` key admits a failure the comparison did not, and `--no-test`
still skips the whole run. The role that started the merge does not capture
the inherited failures itself: the entry is the engine's. `aide merge -h`
states which options and exits keep the plain gate.

**A merge that lands exactly the tree validation ran does not run the suite
again.** Validation runs the suite through `aide test`, which records the
result against the tree, the command, the claim branch and the commit. Where
the post-merge tree is the claim branch's own and that branch changed nothing
but the progress document after the recorded run, `aide merge` takes the
recorded result in place of a second run — through the same gate, so a red one
still meets the base — says so, and marks the ledger row's `Suite s` cell as
reused. Every other merge runs the suite as above: a base that moved, a
commit after the run, a tree with tracked changes, a run recorded on another
branch, in another checkout or by anything but `aide test`. Taking a recorded run is not an
override, and `--no-test` takes none. `aide test -h` states the conditions
exactly.

**The mode also decides what kind of CI gate can see a claim branch — pick it for
that too.** Per-item scope is checked as each claim branch merges (§1). Whether a
CI job can run that check depends on what the mode leaves behind for CI to
trigger on:

| `git.mode` | Claim branch pushed | PR opened | Per-item scope gate in CI |
|---|---|---|---|
| `auto-merge` | yes | no | **push-triggered only** — and see the caveats below |
| `pr` | yes | yes, by the human | **works**, in PR context |
| `local` | no | no | **unreachable** — nothing leaves the machine |

The distinction that matters is **PR context**, not visibility. `auto-merge`
pushes the claim branch like `pr` does, so a push-triggered workflow matching
`<branch_prefix>**` (§2 — default `aide/**`) can see it — but there is no pull
request, so no `github.base_ref` to diff against: the job must supply `--base`
itself, and it races the in-loop merge, which deletes the branch as soon as the
item lands. Under `pr` the PR carries both refs — head `aide/NNN-…`, base the
item's recorded base — which is exactly the diff `aide scope` wants, with no
branch-name parsing at all.

So the trade is real in both directions. `auto-merge` buys unattended throughput
and, unless a push workflow is deliberately built for it, leaves the gate
enforced **only** by the validator running `aide scope` in-loop: same machine,
same platform, same checkout that built the item — the §7 blind spot exactly.
`pr` buys the independent, second-platform signal back and costs one human PR
open per item. Choose deliberately rather than inheriting the default: **a
scope job written for PR context is green forever under `auto-merge` while
checking nothing**.

The branch *shape* is an independent axis and does not decide this: under the
stacked queue-branch model below, `pr` still works, since the PR's head is the
`aide/NNN-` claim branch and its base is the pushed queue branch.

**Where "`main`" above actually means "the base".** `main_branch` is the default
and is never removed as one, but real work stacks: a queue branch carries the
queue file, a roadmap deliverable and every item spec, and lands as **one**
reviewed PR — so each of its items must branch off *and merge back into* that
branch, not `main`. Two things make that work without a flag at every call site:

- **`aide claim` records what it branched off.** It creates the branch from
  whatever is checked out and remembers that as the item's base. Inference is
  deliberately narrow — only a *recognised* queue branch (`<prefix>queue-NNN`,
  `<prefix>specs-queue-NNN`), never an arbitrary checked-out branch.
- **`aide merge` returns the item to its recorded base**, so the validator's
  documented `aide merge NNN` step is correct on a queue branch with no change.

`--base <ref>` overrides on `claim`, `merge`, `gc` (which ref `--merged` is
measured against), `status` (what ahead/behind is reported from) and `scope`
(what the diff is taken against). Resolution is always **`--base` > recorded >
`main_branch`**. The record is local git config, not a committed file, so a
different machine falls back to `main_branch` and passes `--base` explicitly.

**A base is always a local branch**, and a claim always *branches from* it — the
branch's starting point and its recorded base are the same commit by
construction, so an item can never merge back somewhere it did not come from. A
tag, a raw commit or a remote-tracking ref (`origin/main`) is refused.

### Rationale

- **Why the claim branch goes before the gate run.** So the run sees what a
  fresh clone sees.
- **Why `aide check` is part of the gate.** Nothing else in the loop ran it
  mechanically: a consumer's ✅ stage over ⏸️ deliverables — an error — sat on
  its base for two weeks until an engine update surfaced it, and a consumer
  without its own test pinning the check would never have seen it (issue
  #232). The merge is the one seam every item crosses whether or not a
  validator ran. It reads the whole document set rather than the item's diff,
  so an error already on the base blocks too; telling the two apart would mean
  checking the base as well, and an unattended run that lands items over a
  broken document set is the failure being fixed. Warnings never block,
  because some are permanent by design (a retracted criterion, issue #152).
- **Why a red run is compared with the base.** The gate refused on any red
  test anywhere, so one failure the item never touched blocked every item
  behind it. A consumer on engine 1.38.0 had an item pass all sixteen of its
  acceptance criteria with every changed file authorised, and the merge still
  exited 1 on nine failures proven identical at the merge-base — stale
  environment-gated capability rows and an unrelated adapter gap. A second
  time, a test pinning an inbox entry's checkbox went red when a triage commit
  on `main` ticked it, and every item merging into the queue branch was
  blocked until a fix landed. The only override was `--no-test`, which drops
  the gate rather than scoping it (issue #275).
- **Why in place, not in a separate worktree.** The post-merge run saw this
  checkout's untracked and ignored inputs — data, a built extension, the
  venv. A fresh worktree lacks them, so the base fails *more* there, and every
  extra base failure is a regression the subset rule would admit as
  inherited. The base is only run when the merge is red, so a green merge
  costs nothing extra.
- **Why a subset, and why automatic.** A
  `--accept-inherited <nodeid>…` flag was proposed and not taken: the subset
  is a fact the two runs establish, and a flag would stop an unattended run
  for a person to type what the engine already knows. A key to switch the
  comparison off was not taken either — it would switch off the one check that
  separates an item's regression from its base's. An item that renames an
  inherited failing test, or fails one differently, is still refused, since
  identity is by test id: the rule errs towards refusing.
- **Why the engine writes the inbox entry.** An admitted failure that leaves
  no trace makes a red base look normal to the next item over it. The verb
  holding the ids writes one line, and skips ids an open entry already names,
  so a queue landing ten items over the same red base carries one entry and
  not ten; the role that ran the merge writing its own would be the same
  finding twice.
- **Why only pytest.** Comparison needs a report naming each failure, and a
  test command is otherwise free-form; guessing failure identity from another
  runner's output would admit on a misreading. An order-dependent option
  (`-x`, `--maxfail`, `--lf`, `--ff`, `--sw`) makes the set a property of the
  run, and an exit other than "tests failed" means the report is not the whole
  suite — both would compare two partial pictures. Order set in the project's
  own configuration — a random-order plugin enabled by default, say — is not
  visible in the command, and is not detected: such a suite's failure set is
  as much the run's as the tree's, and a comparison over it can admit an
  order-sensitive regression by coincidence.
- **Why the base run is stored.** A retried merge — after a fix commit, or a
  failed push — would otherwise re-run the base it has already run. Results
  are kept under git's own directory, keyed by tree and exact command, never
  committed, and pruned after seven days; a run over a tree with tracked
  changes, or one that leaves a tracked change behind, is never stored, since
  it belongs to no tree — a base run's included, so a suite that rewrites a
  tracked file re-runs its base on every retry.
- **Why a validated tree is not run twice.** Under `auto-merge` validation ran
  the whole suite on the claim branch and the merge ran it again, and when the
  base had not moved the merge is a fast-forward: the second run was over a
  byte-identical tree and could prove nothing the first had not. It was the
  loop's second long wait, which on a runtime with a short idle cache also
  costs the waiting agent its context (issues #274, #275). One store serves
  both reads, the base run and the validated run, so there is one record of
  what ran where.
- **Why the progress document may differ.** Validation writes its verdict
  after its suite run — `progress set in-review` and each attested criterion
  are commits on the claim branch — so a rule demanding the identical tree
  would never be met by the loop it was built for. The progress document is
  the one file allowed to differ because the merge's own `aide check` reads it
  in full beside the gate, and what validation writes there is the engine's
  bookkeeping. Anything else, `insights.md` included, forces a run: a
  consumer's test has already gone red on an inbox checkbox (above).
- **Why the claim branch and its commit, not only the tree.** A tree key alone
  would let a run recorded for an earlier item, or on the base before this
  claim existed, stand for this one whenever the trees happened to agree. The
  recorded branch and a commit the tip contains tie the run to this claim, so
  a reused result is always one this item's own validation produced.
- **Why tracked changes refuse and untracked files do not.** A run over a tree
  with a tracked change is a run of no commit, so it is neither recorded nor
  taken. Untracked and ignored inputs — data, a built extension, the venv — are
  not in the tree at all, so a run is taken only in the checkout that
  recorded it: there the validated run and the merge saw the same ones, and
  the base run's rationale (above) is why the merge does not try to see fewer.
- **Why a CI gate can decay silently.** With no PR a PR-context scope job
  either never triggers, or triggers on a branch whose name yields no item
  number and correctly skips — so a gate can decay from a mode change alone,
  long after it was correctly built.
- **Why base inference is narrow.** Inferring a base from an arbitrary
  checked-out branch would silently retarget a merge.
- **Why the record is local.** The base is a fact about this checkout's
  branching, not about the project.
- **Why a base must be a local branch.** `git switch` to a tag, a commit or a
  remote-tracking ref would detach HEAD, and a merge into a detached HEAD
  updates no branch while still reporting success.
