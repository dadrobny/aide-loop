---
name: aide-queue-and-inbox
description: Load before authoring a queue — the queue file's derived state and item shape, and the insight inbox it is planned from: capture, the verbs, and how an open entry is routed (conventions §1).
user-invocable: false
paths:
  - "**/queue/*.md"
  - "**/insights.md"
---

<!-- reach: queue-planner
     Literal, not measured: this body is preloaded into exactly the agent
     specs whose `skills:` frontmatter names `aide-queue-and-inbox` — the one
     role that writes a queue file and the one that reads the open inbox as an
     input to the batch. Three sections in one skill because their reach is
     identical: a queue is planned from the inbox, and the maintenance-queue
     ordering is a statement about both. Triage is deliberately not among
     them — since 1.48.0 (issue #191) the routing table, the judgement and the
     `framework` hand-over are §1 → `insights-triage.md`, performed by
     `/aide-review-insights` at the same boundary; this role acts on what that
     pass left open, and `/aide-create-queue` restates the three rows it may
     queue, under pin. The other roles
     append an insight line and nothing else, and that shape is on the
     always-on floor in `AGENT-CONTEXT.md`; `spec-author` expands a queue's
     items but writes no queue file, and its own spec names the queue file it
     reads. Before this
     the queue-file section was reached by nothing that pointed at it — two
     inline restatements of the completion stamp, unpinned (issue #186's reach
     column). The `paths:` above inject nothing on a read (issue #85,
     measured): the description sits in every interactive session's skill
     listing regardless, and the globs only narrow when the runtime
     auto-invokes the skill on its own.
     `tests/test_structural_budget.py` compares this line to the `skills:`
     lists. -->

<!-- triggers: all
     The interactive half, declared so the glob evaluator stays on an
     assertion path: the roles whose named reads match the `paths:` above.
     Every role names `insights.md` — appending to it is in every spec's
     scope — so the glob set matches all of them, which is exactly why the
     loop's delivery is the preload and not these globs. -->

<!-- pins: .aide/conventions/1-format-contract/queue-NNN.md
     Quoted from that section; `test_rule_pins.py` fails if either copy moves
     alone. One block per section file, so three blocks follow.
     - Queue state is derived, not declared
     - A queue is **open** iff any of its items is 📋/🚧 in `progress.md`,
       else **done**
     - the live queue is the lowest-numbered open one
     - A 📋 item every bullet of which sits in a withdrawn stage keeps no
       queue open
     - A `> **Status:**` line is optional decoration for human readers
     - `aide queue tidy` stamps a completion note on superseded queues
     - `aide check` warns only when a declared status contradicts the derived
       state
     - Work items as `### Item NNN: Short Title` + a description paragraph
     - Item numbers are **globally sequential across all queues** — never
       restart
     - One queue is live at a time, deliberately
     - The loop builds one queue at a time
     - is a batch awaiting review, not a second live queue
     - Concurrent live queues — not offered
     - Write it as independence, not as "run alongside"
     - A queue-end item is planned only when the engine reports a need for
       one
     - Stage validation is its only trigger today
     - The planner reads that warning and never works the need out itself
     - with no such warning, the queue ends with its last deliverable
     - The same check warns on a planned queue-end item with nothing to do
     - Wherever the file lists it, it runs last
     - so an item added after planning goes above it
     - The stage variant is titled `Validate stage N: <stage title>`
-->

<!-- pins: .aide/conventions/1-format-contract/insights.md
     - The file exists before a role needs it — the engine puts it there
     - No role copies the template by hand
     - Capture has a verb, and so does everything after it
     - an archive renumbers what remains, so re-run `list` after one
     - writes the union of a conflicted inbox
     - A conflict marker left in the file is an `aide check` **error**, not a
       warning, and the message names this verb
     - Ticking the checkbox is the one in-place edit
     - It refuses anything that is not a pure append
     - Cite an entry by its ID, never by its position
     - A longer ID is the same ID
-->

<!-- pins: .aide/conventions/1-format-contract/roadmap.md
     Two sentences of a section this skill does not deliver, quoted because
     the planner picks the next stage by them (issue #454).
     - The maintenance stage is the stage titled exactly `Maintenance`
     - A stage queue never takes the maintenance stage as its next stage
     - A stage appended after it is an ordinary stage
-->

<!-- pins: .aide/conventions/1-format-contract/insights-maintenance-queue.md
     - The open inbox is an input to queue authoring, not only an output of
       triage
     - considered, and either queued or explicitly passed over — never
       silently dropped
     - Insight-derived fixes get a queue of their own, ahead of the stage
       queue
     - a maintenance queue, authored and merged before the stage queue
     - An unchecked entry is still a candidate
     - A maintenance item's deliverable bullet goes under the maintenance
       stage
     - never under the feature stage whose module it touches
     - placing it there would reopen a closed stage
     - When a maintenance queue is warranted and the roadmap has no
       maintenance stage, the queue's author hands back
     - Nothing else triggers it: a boundary with no entry that warrants a
       maintenance queue writes its stage queue as before
     - the owner adds the stage once, through the create-roadmap entry point
     - A batch that reopens a ✅ maintenance stage writes the stage's 🚧
       itself
     - Write that icon into the two cells in the same commit as the bullets
-->

# Queue files and the insight inbox

`.aide/conventions.md` §1 → `queue-NNN.md`, §1 → `insights.md` and §1 →
`insights-maintenance-queue.md` are the sources of truth; this file is how the
three reach `queue-planner`, preloaded at spawn, since a queue is planned from
the inbox and no shape here is one the role can look up mid-write. It is
**delivery, not a second source of truth**. The immutability of a captured
claim and the entry shape itself are on the floor, in `AGENT-CONTEXT.md`,
already in this context; routing an entry by type is triage's, §1 →
`insights-triage.md`, and `/aide-create-queue` carries the rows you queue
from.

**Queue state is derived, not declared.** A queue is **open** iff any of its
items is 📋/🚧 in `progress.md`, else **done**; the live queue is the
lowest-numbered open one. A 📋 item every bullet of which sits in a withdrawn
stage keeps no queue open; a 🚧 one there still does. A `> **Status:**` line
is optional decoration for human readers — `aide queue tidy` stamps a
completion note on superseded queues, and `aide check` warns only when a
declared status contradicts the derived state. Never type the stamp by hand;
run the verb.

**Work items as `### Item NNN: Short Title` + a description paragraph.** Item
numbers are **globally sequential across all queues** — never restart.

**One queue is live at a time, deliberately.** The loop builds one queue at
a time; an unmerged queue below the live one — built out, its PR awaiting
review, the live queue stacked on its branch (§4) — is a batch awaiting
review, not a second live queue. Item independence *within* a
queue is real — `aide claim` offers any unblocked item, so say it freely — and
so is stage independence, a scheduling fact that tells a planner two stages may
be queued in either order. Write it as independence, not as "run alongside":
the planner queues sequentially either way. Concurrent live queues — not
offered; `loop.claim_scope = "all-open"` widens *claiming* across every open
queue, but nothing creates a second live queue.

**A queue-end item is planned only when the engine reports a need for one**
(§1 → `queue-NNN.md`) — queue-level judgement that produces committed
artefacts, as the queue's final item. **Stage validation is its only trigger
today**: on a queue that closes a roadmap stage, `aide check --queue NNN`
warns when the stage still has work for one, and names why. **The planner
reads that warning and never works the need out itself** — with no such
warning, the queue ends with its last deliverable. **The same check warns on
a planned queue-end item with nothing to do.** **Wherever the file lists it,
it runs last**: `aide claim` holds it until the rest of its queue has left
the way, bar an item whose dependencies lead back to it or a 📋 one of a
withdrawn stage, and `aide check
--queue NNN` warns when open work that does not depend on it is listed after
it, so an item added after planning goes above it. **The stage variant is
titled `Validate stage N: <stage title>`**; `/aide-create-queue` says when to run the
check and what to write.

**The file exists before a role needs it — the engine puts it there** (§1 →
`insights.md`): `aide check`, `aide claim`, `aide queue start`,
`aide insights list` and `aide insights add` each create a missing
`insights.md` from the template. No role copies the template by hand.

**Capture has a verb, and so does everything after it** (§1 →
`insights.md`): `aide insights add <type> '<one line>' --provenance queue-NNN`
captures an entry and prints its ID, `aide insights list --open` reads the
backlog without the
closed history around it, `aide insights tick N|ID --pointer "<where it landed>"`
closes an entry — **ticking the checkbox is the one in-place edit**, and the
verb owns it, so a hand-flipped `[x]` is the improvised form of `tick` — and
`aide insights archive --before <date> --yes` moves closed entries out (a dry
run without `--yes`); an archive renumbers what remains, so re-run `list`
after one. Reading the file raw costs the whole closed history to see a
working set of a dozen lines; editing it by hand is the failure `add` and
`tick` exist to prevent.

**Cite an entry by its ID, never by its position** (§1 → `insights.md`). The
queue file routing an entry into an item, and the item spec it charters, name
it as `insight <ID>` — the date-plus-hex handle `insights list` prints, computed
from the immutable claim, so no archive or merge moves it. `N` is for the
`tick` you run straight after `list`. **A longer ID is the same ID**: `list`
lengthens one only where two claims of one date would share it, and
`aide check` errors on a cited ID that names no entry, archives included.

The fourth verb covers the one moment the whole file is in front of something
willing to rewrite it. Append-only means two branches that each captured an
insight conflict on every merge, and `aide insights resolve [--dry-run]`
writes the union of a conflicted inbox — shared history, then each side's new
entries, ticks and trails merged — instead of a hand retyping the block. **It
refuses anything that is not a pure append** (a reworded, reordered or deleted
claim, or a side that archived) and writes nothing when it does, because each
of those is a change to an immutable line that a human must see. Do not
resolve this file's conflict by hand: a conflict marker left in the file is an
`aide check` **error**, not a warning, and the message names this verb.

**The open inbox is an input to queue authoring, not only an output of triage**
(§1 → `insights-maintenance-queue.md`). Triage happens *at* the queue boundary,
when the next queue does not exist yet, so a `defect`, `gap` or `automation`
entry routed there to "a candidate item" waits in the inbox for whoever authors
that queue: `aide insights list --open` is one of its inputs, beside vision,
roadmap and progress. Every open entry of those three types is **considered,
and either queued or explicitly passed over — never silently dropped**; a
queued one is ticked with the item number it became, and a passed-over one
stays open, because **an unchecked entry is still a candidate**.

**Insight-derived fixes get a queue of their own, ahead of the stage queue**
(§1 → `insights-maintenance-queue.md`). When those open entries warrant it they
are batched into **a maintenance queue, authored and merged before the stage
queue** — its own number, its own items, ticking what it absorbs — and the
stage queue is the next number up. It is not a second live queue: the live
queue is the lowest-numbered open one, so the fixes are simply served first.
Whether an entry warrants one is yours to decide and never silent: too small
to be worth a branch, blocked on something unbuilt, out of scope, or a `gap`
the upcoming stage was going to fill anyway — say which, where the queue is
reviewed.

**A maintenance item's deliverable bullet goes under the maintenance stage**
(§1 → `insights-maintenance-queue.md`; what that stage is, §1 → `roadmap.md`),
**never under the feature stage whose module it touches**: placing it there
would reopen a closed stage. A `gap` you route to the stage queue is a stage
item, wired under that stage. **When a maintenance queue is warranted and the
roadmap has no maintenance stage, the queue's author hands back**, before
writing either queue: the owner adds the stage once, through the
create-roadmap entry point, since the answer changes `roadmap.md`. Nothing
else triggers it: a boundary with no entry that warrants a maintenance queue
writes its stage queue as before.

**The maintenance stage is the stage titled exactly `Maintenance`**, and **a
stage queue never takes the maintenance stage as its next stage** — it has no
roadmap deliverable to queue; a stage appended after it is an ordinary
stage (§1 → `roadmap.md`).

**A batch that reopens a ✅ maintenance stage writes the stage's 🚧 itself.**
No verb moves a stage when a bullet is added, so its section header and Stage
summary row still read ✅ over the new 📋 bullets, and `aide check` errors on
both. Write that icon into the two cells in the same commit as the bullets —
the value the rollup computes, so it is not drift.
