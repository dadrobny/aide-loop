---
name: triage-issues
description: Triage newly-raised aide-loop issues — version-check them against the changelog and HEAD, file them into the GitHub Project with Theme and labels, order the board, sweep the deferred pile for anything a release has un-blocked, and propose the next PR's worth of work.
---

# Triage the inbox

Consumers raise issues against the framework faster than the framework lands
them. This is the recurring pass that turns that inbox into an ordered board and
one concrete proposal.

**This skill is repo-local machinery, not framework content.** It lives in
`.claude/skills/`, which `install.py` never copies — so unlike anything under
`core/` or `adapters/`, editing it needs no `core/VERSION` bump and no
`CHANGELOG.md` entry. Do not move it into the adapter; it encodes *this*
project's tracker, not a rule every runtime should express.

## Before you start

- **`gh` is not on `PATH`.** Call `/mnt/data/ddrobny/.local/bin/gh`. Set
  `GH=/mnt/data/ddrobny/.local/bin/gh` once and use `$GH` throughout.
- The repo is **private** and the Project needs the `project` scope
  (`$GH auth refresh -s project`). `$GH auth status` should list `project` among
  the token scopes; without it every `gh project` call fails on permissions, not
  on network.
- Everything below needs network. If there is none, say so and stop — there is
  no offline half of this pass.

## What you may do without asking, and what you may not

**Apply directly** (mechanical, idempotent, reversible):
adding an issue to the Project, and reordering the board.

**Propose and wait for a go-ahead**: `Theme`, labels, `Status`, closing an issue
as already-fixed, and removing a `deferred` label. These are judgement calls, and
a wrong `Theme` is invisible afterwards in a way a wrong position is not.

Batch every proposal into **one** approval request at the end of the relevant
step — not one question per issue.

## Step 1 — Gather

Run these together; they are independent.

```bash
GH=/mnt/data/ddrobny/.local/bin/gh
$GH issue list  --repo dadrobny/aide-loop --state open --limit 200 \
    --json number,title,labels,createdAt,author > /tmp/issues.json
$GH project item-list 1 --owner dadrobny --format json --limit 200 > /tmp/items.json
$GH pr list --repo dadrobny/aide-loop --state merged --limit 20 \
    --json number,title,mergedAt,headRefName > /tmp/prs.json
cat core/VERSION
```

The **new arrivals** are the open issues whose numbers appear in `issues.json`
and not in `items.json` (`items[].content.number`). Those are what this pass is
about; issues already on the board only get re-examined in steps 4 and 5.

`gh project item-list` returns items **in board position order**, which is what
step 3 rewrites. It also carries each item's `id` (the `PVTI_…` node id), which
is the only handle the position and field mutations accept.

## Step 2 — Version-check each new issue

A consumer issue is written from a checkout that is usually behind. The body
convention carries it explicitly:

> **Project:** SegFACET (consumer). **Observed under engine 1.21.0**

If that line is missing, read the version out of the consumer itself — the local
installs are `/mnt/data/spine/codes/spine-failure-lab` and
`/mnt/data/spine/codes/SegFACET`, each with a `.aide/VERSION`. If the reporter
is not a local consumer, ask rather than guess; "unknown version" and "current
version" are not the same triage.

Then, for each issue whose observed version is behind `core/VERSION`:

1. **Read `CHANGELOG.md` between the two**, plus `[Unreleased]`. Search it for
   the surface the issue names — the verb (`aide scope`), the file
   (`conventions/6-test-hygiene.md`), the lint (`absolute_path_test_warnings`),
   the hook. The changelog here is prose-dense and one entry routinely covers
   several failures, so grep the surface, then read the whole entry.
2. **Confirm against HEAD.** The changelog is a claim about what shipped; the
   working tree is the fact. Never close an issue on a changelog entry alone —
   open the file and check the rule or the code path is actually there. Issue
   #126 does this in its own body ("§6 on 1.28.1 still carries no such rule"),
   and that is the standard to meet, not to skip.

Three verdicts:

| Verdict | Evidence | Action |
|---|---|---|
| **Already fixed** | A released entry *and* HEAD address the exact failure | Comment citing the version and the entry, then **ask before closing** |
| **Partially addressed** | The entry touches the surface, not the failure | Comment naming what landed and what remains; keep open, and propose narrowing the title |
| **Live on HEAD** | Nothing addresses it | Nothing to say; carry it into steps 3 and 5 |

The comment is not optional for the first two — a consumer's report that gets
silently closed or silently narrowed teaches them to stop filing. Cite the
version and quote the changelog line.

Watch for the fourth case the table does not cover: an issue that is **live on
HEAD but was caused by a since-changed design**. Say so in the triage report; it
usually changes the fix, not the verdict.

## Step 3 — File and order

### Add to the Project (apply directly)

```bash
$GH project item-add 1 --owner dadrobny --url https://github.com/dadrobny/aide-loop/issues/<N>
```

Adding is idempotent-ish — re-adding an existing item returns the same item —
but only add the numbers step 1 found missing.

### Theme and labels (propose first)

`Theme` is a single-select on the Project; labels live on the issue. Both must
be filled — an item with a blank `Theme` is invisible to every grouped view.
The seven Themes and their option ids, and the field/project ids, are in
[`reference.md`](reference.md); re-derive them with the query there if a
mutation rejects an id.

```bash
# Theme
$GH project item-edit --project-id PVT_kwHOByffxc4Bg9iM --id <PVTI_…> \
    --field-id PVTSSF_lAHOByffxc4Bg9iMzhf7FlI --single-select-option-id <option-id>
# Labels
$GH issue edit <N> --repo dadrobny/aide-loop --add-label enhancement
```

Choosing a `Theme`: pick the concern the *fix* belongs to, not the one the
symptom appeared in. A crash in `aide progress` is `Correctness`; a rule that
never reaches an agent is `Reaching the reader` even though it surfaced as a
correctness bug in a consumer.

Labels are the standard set plus **`deferred`**, which is the only scheduling
signal this tracker has (CLAUDE.md, "Where direction lives"). Applying
`deferred` also means editing the title to say so — the existing deferred issues
all end `(deferred — recorded, not scheduled)`, and that convention is what makes
the state legible in a plain issue list. **Do not invent a priority or ordering
label**; a `Wave` field existed, encoded one batch's ordering, and was dropped.

### Order the board (apply directly)

Desired order, and the whole of it:

1. open, not `deferred` — **fair game**
2. open, `deferred` — recorded, deliberately unscheduled
3. `Status: Done` — last

Within each bucket the existing relative order is preserved. There is no
priority axis in this tracker, so inventing one by hand-sorting inside a bucket
would encode an ordering nothing else can read.

```bash
python .claude/skills/triage-issues/reorder_project.py --dry-run   # prints the plan
python .claude/skills/triage-issues/reorder_project.py             # applies it
```

The script is a stable partition and a no-op when the board already matches, so
running it twice costs one read. Ordering only takes effect on views with no
explicit sort — view 4 (Board) and **view 5 (Table)** qualify today; a view that
grows a sort ignores position entirely.

### Retiring long-Done items is part of the same pass

The board would otherwise grow monotonically — ordering only keeps Done last, it
never removes it. One argument governs this, **`--archive-after-days`, defaulting
to 30**: Done items closed longer ago than that are archived before the reorder.

```bash
python .claude/skills/triage-issues/reorder_project.py --archive-after-days never
```

Thirty days keeps the last few PR cycles visible, which is what step 2's "did we
just fix this?" check and step 4's sweep both read. Measured on 2026-09-01, a
week would have retired 13 items — among them #46, whose lint two *still-open*
issues are about — and thirty days retired none.

Archiving is reversible (`unarchiveProjectV2Item`) and touches no issue, but it
decides what the next triage can see, which is why the `--dry-run` above is not
optional: it prints the retirement list and the reorder plan together, and that
printout is the review. An item whose Status was set to Done by hand has no close
timestamp and is never a candidate; the script says how many it skipped for that.

## Step 4 — The un-defer sweep

A `deferred` issue is not dormant: it is waiting on something. Once per pass,
check whether the something arrived. For each open `deferred` issue:

- **Did a merged PR name it?** PR titles here carry `(#NN)`, so `prs.json` from
  step 1 answers this directly. A merged PR naming a deferred issue is a **prompt
  to re-read it, not an automatic close** — PR #117 ("the windows leg stops
  paying Defender per spawn, and splits in two (#74)") landed against deferred
  issue #74 while leaving #74's own proposal, cheaper fixture spawning, untouched.
  The honest outcome there is to narrow the issue, not to close it.
- **Did the stated blocker dissolve?** Most bodies name their reason in prose —
  a dependency, a design question, a cost that was not worth paying. Check that
  sentence against HEAD.
- **Does a new arrival subsume it?** A fresh consumer report can turn a "recorded,
  not scheduled" item into one with evidence and a second reporter. That is a
  reason to un-defer.

Propose the un-defers as one batch: issue, what changed, and whether the title's
`(deferred — …)` suffix comes off with the label.

## Step 5 — Propose the next PR

One PR's worth. From this repo's own history (PRs #108–#117), that is **one
coherent surface and one to five issues** — not a themed grab-bag.

Rank the fair-game issues on two axes:

- **Shared surface.** Issues that edit the same files land together and are
  reviewed once. `aide check` lints belong with `aide check` lints; a
  `conventions/` section rewrite belongs with the pins that quote it.
- **Consumer pain and recurrence.** Weight a failure that bit several consumers,
  or that several items in one queue reproduced independently — issue #126's six
  authors writing the same defect is the signature of a missing rule, not of a
  careless author, and that is the strongest signal this tracker produces.

The proposal is **written, not started**. It states:

1. the issues, in the order they should be implemented, with the dependency
   between them if any;
2. the surface — which files, and specifically whether it touches `core/`,
   `adapters/`, or only the not-installed paths;
3. the resulting **version bump** and its SemVer class, since anything reaching
   `core/` or `adapters/` must bump `core/VERSION` and add a `CHANGELOG.md`
   entry in the same commit (CLAUDE.md, "Versioning — enforced, not remembered");
4. which existing tests will fail and must be edited deliberately — in
   particular `tests/test_structural_budget.py` (the always-on floor, pinned
   byte-for-byte) and `adapters/claude/tests/test_rule_pins.py` (both
   directions) if a delivered file or a `conventions/` section moves;
5. what is deliberately **not** in the batch, and why.

Stop there. Do not cut the branch.

## Report

Close the pass with a single report:

- **New arrivals**, one line each: number, verdict from step 2, proposed Theme
  and labels.
- **Applied**: items added, board reordered (or already ordered).
- **Awaiting your call**: Theme/label/close/un-defer proposals, batched.
- **Next PR**: the step 5 proposal.

## Filing an issue yourself

When you raise one on a consumer's behalf, use the template — it is
[`.github/ISSUE_TEMPLATE/consumer-report.md`](../../../.github/ISSUE_TEMPLATE/consumer-report.md),
and its first line is the `**Project:** … **Observed under engine X.Y.Z**` header
step 2 reads:

```bash
$GH issue create --repo dadrobny/aide-loop --template "Consumer report"
```

**A template is not a guarantee.** It fills the web-UI composer and `gh issue
create --template`; it is silently bypassed by any `gh issue create --body …`,
which is how an agent files. So when triage meets an issue with no version
header, the fix is to add the header to that issue, not to assume the next one
will carry it.

## Notes

- **Nothing outside the tracker records status.** Do not open a PR that adds a
  status section, a checklist, or a "current focus" heading to any document in
  this repo as a by-product of this pass.
- The Project also has **view 6 ("Open")**, filtered `-status:Done AND
  -label:deferred` — that is the fair-game list without any local computation,
  useful as a cross-check on step 5.
- An issue that crosses a stated non-goal in [`docs/vision.md`](../../../docs/vision.md)
  can be **closed as out of scope**; that licence is the main thing the vision
  document buys. If a proposal fits nowhere in the vision, say so in the issue —
  either it is out of scope, or the vision is out of date and wants a PR.
