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

## [Unreleased]

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
  - **Flat deliverable bullets** (§1) — a nested bullet carrying its own status
    icon is invisible to the rollup while reading as status to a human, so the
    document and the tooling disagree with nothing to reconcile them.
  - **Header blockquote** (§1) — scoped to the templated living documents.
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
  visibility, not a gate. Together they take the consumer's `aide check` from 7
  warnings to 11, every one real.

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
