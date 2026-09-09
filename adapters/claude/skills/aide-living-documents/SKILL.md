---
name: aide-living-documents
description: Load before writing a living AIDE document (item spec, queue, progress, roadmap, vision, insights) — the shapes aide.py parses (conventions §1).
user-invocable: false
paths:
  - "**/progress.md"
  - "**/roadmap.md"
  - "**/vision.md"
  - "**/insights.md"
  - "**/queue/*.md"
  - "**/items/*.md"
---

<!-- reach: spec-author, queue-planner
     Literal, not measured: this body is preloaded into exactly the agent
     specs whose `skills:` frontmatter names `aide-living-documents` — the two
     roles that write a living document. As a `paths:` rule it armed on
     every spawn (29 and 24 arms in two measured sessions, issue #85),
     because reading an item spec matches the same globs as writing one; the
     `paths:` above inject nothing on a read (issue #85, measured): the
     description sits in every interactive session's skill listing regardless,
     and the globs only narrow when the runtime auto-invokes the skill on its
     own. The four roles that write none of the shape-parsed documents are
     deliberately not listed — the one line they do append, the insight entry,
     has its shape on the floor in `AGENT-CONTEXT.md`. `tests/test_structural_budget.py` compares this line to the `skills:`
     lists. -->

<!-- triggers: all
     The interactive half, declared so the glob evaluator stays on an
     assertion path: the roles whose named reads match the `paths:` above —
     what a rule with these globs would arm, and what the loop no longer
     pays. Every role names an item spec or `insights.md`, so: all. -->

<!-- pins: .aide/conventions/1-format-contract/status-icons.md
     Quoted from that section; `test_rule_pins.py` fails if either copy moves
     alone. One block per section file, so seven blocks follow.
     - 📋 Planned
     - 🚧 In Progress
     - 🔍 In Review
     - ✅ Complete
     - ⏸️ Deferred
     - ❌ Excluded
     - a table row's Status (last) cell, a stage header's trailing `— <icon>`,
       and the leading icon of a deliverable bullet
     - An icon anywhere else — prose, mid-bullet, a title — is plain text and
       is never read as status
     - `aide check` still *warns* on such stray icons in the status-bearing
       documents (`progress.md`, queue files)
     - Rank is used when one item is referenced on several lines: the
       most-advanced status wins
-->

<!-- pins: .aide/conventions/1-format-contract.md
     - The templates in `.aide/templates/` model the shapes and `aide check`
       enforces them
     - a literal value to substitute
     - authoring guidance to read then replace
     - left in a generated `docs/aide/**.md` file as an unfilled template slot
     - Dates are always **ISO 8601** (`YYYY-MM-DD`)
     - every living document opens with one, carrying its step number in the
       loop, what it derives from, and what derives from it
     - Keep the line current when a document's relationships change
     - is spoken by the skill that wrote the file, not stored in it
-->

<!-- pins: .aide/conventions/1-format-contract/progress.md
     - a **Deliverables** block of **flat** bullets, each
       `- <icon> <text>. *(Item NNN)*` — one status icon, one item ref, no nested
       status-bearing sub-bullets
     - The `*(Item NNN)*` suffix is what ties an item to the bullet whose
       status it moves
     - an item no bullet references is untracked
     - **Suffix means suffix**: only the trailing marker that ends the bullet
       (its last wrapped line) attributes
     - A bullet whose references all sit mid-prose tracks nothing, and `aide
       check` warns about it
     - | `*(Items 006, 044)*` | 6, 44 — one deliverable, several items |
     - | `*(Items 071–075)*` | 71, 72, 73, 74, 75 — inclusive, hyphen or en-dash |
     - | `*(Items 006, 044–046)*` | 6, 44, 45, 46 — an element may be a range |
     - Prefer the explicit list when the items are not contiguous; a range is
       only shorthand for one
     - A marker naming several items is shorthand, never a shared status cell
     - write the shared marker freely; the file simply grows a row the first
       time its items diverge
     - enter through the queue, never by retro-editing a closed stage's
       deliverable list
     - ticked only by `aide progress accept` — never derived
     - The attestation is immutable; what is recorded about it is not
     - `amend` appends, and only to a ticked box
     - a verb that can only add cannot be used to make an inconvenient attestation agree with a shipped stage
     - `retract` unticks, and keeps the original attestation visible
     - A retraction is a finding, so the verb routes it like one
     - `reword` is the one amendment that edits rather than appends
     - refuses over a box that is ticked, annotated, or already carries a correction trail
     - writes both documents or neither
-->

<!-- pins: .aide/conventions/1-format-contract/items.md
     - Filename begins with the zero-padded number
     - First `#` heading is `# Item NNN — Title`
     - **No status field** in the header — status lives only in `progress.md`
     - The header carries `Created`, Stage, Queue, Objectives, Suggested
       branch, and a mandatory **Assumptions** block
     - An assumption that pins engine behaviour names the engine it was true
       for
     - a re-check goes into the marker, `(engine 1.28.1, re-checked 1.36.0)`,
       and the newest version named is the one the claim stands on
     - A merged spec is never rewritten to agree with a later engine
     - `## Dependencies` blocks `aide claim`
     - 🚧 and 🔍 both still block
     - Text at or after a literal `**Downstream` marker is excluded from that
       scan
     - put such asides after the marker, never before it
     - The rest of any line from a backticked or bold `Blocks:` label on is
       excluded too
     - Keep a reach quote on one line — the exclusion does not extend past it
     - An acceptance criterion is an invariant over the resulting content
     - never a bound on the diff that produced it
     - a criterion that asserts a fact about live state is a measured equality
       against that state
     - a criterion that closes a stage acceptance criterion names which one
     - recomputes that fact from the primary source and compares
     - An AC that names none closes none
-->

<!-- pins: .aide/conventions/1-format-contract/human-gates.md
     - A **decision only a person can make**, blocking work until they make it
     - | Gate | Blocks | Status | Decision / evidence |
     - **Blocks** — item numbers (any §1 reference form, or bare: `106`,
       `110, 111`, `106–108`), `stage N`, or `all`
     - `⏳ Awaiting`, then `✅ Approved (date)` or `❌ Declined (date)`
     - Reach is per gate, and never a queue
     - The person raising the gate chooses the reach
     - implies `Blocks: stage N`
     - implying `Blocks: NNN`
     - the **authoritative row**, always
     - a gate that exists only as prose in a roadmap or a spec blocks nothing
     - A declined gate keeps blocking
     - The remedy is to re-plan: drop the blocked items, or change what the
       gate asks
     - Resolving is a CLI operation, never a hand edit
-->

<!-- pins: .aide/conventions/1-format-contract/insights.md
     - Capture is a plain append; everything after it has a verb
     - Ticking the checkbox is the one in-place edit
     - It refuses anything that is not a pure append
     - The open inbox is an input to queue authoring, not only an output of
       triage
     - considered, and either queued or explicitly passed over — never
       silently dropped
-->

<!-- pins: .aide/conventions/5-clarify-mode.md
     - Root documents are authored through their loop entry point,
       interactively — whatever `loop.clarify` says
     - Do not write a root document directly, however well the template shape
       is known
     - ask until the mandatory sections are grounded in their answers, and
       never fill **Guiding principles**, **Out of scope**, or **Success
       criteria** from assumption
-->

# Living-document shapes

`.aide/scripts/aide.py` parses these files by exact shape. The templates in
`.aide/templates/` model the shapes and `aide check` enforces them.
`.aide/conventions.md` §1 is the source of truth and carries one file per shape
(`§1 → progress.md` is `conventions/1-format-contract/progress.md`, and so on);
this file is **delivery, not a second source of truth**, and carries only the
shape rules — the durable artifact, insight-immutability and human-gate rules
are in `AGENT-CONTEXT.md`, already in this context.

It is preloaded into the two roles that write a living document —
`spec-author` and `queue-planner` — so it is in context before the first
write, and an interactive session
sees its description in the skill listing, with the `paths:` above keeping the
runtime's own invocation of it to work on one of these files. The globs match
by document name rather than by `project.docs_dir`, so they hold whatever a
consumer configured.

**The six status icons, and nothing else:** 📋 Planned · 🚧 In Progress ·
🔍 In Review · ✅ Complete · ⏸️ Deferred · ❌ Excluded. They are read at
**structural positions only** — a table row's **Status (last) cell**, a stage
header's **trailing** `— <icon>`, and the **leading** icon of a deliverable
bullet. An icon anywhere else — prose, mid-bullet, a title — is plain text and
is never read as status; `aide check` still *warns* on such stray icons in the
status-bearing documents (`progress.md`, queue files), so keep them out of
those. Rank is used when one item is referenced on several lines: the
most-advanced status wins.

**`{{slot}}` is a literal value to substitute; an _italic line_ is authoring
guidance to read then replace.** `aide check` flags any `{{...}}` left in a
generated `docs/aide/**.md` file as an unfilled template slot, so guidance must
never be written as a slot. Dates are always **ISO 8601** (`YYYY-MM-DD`).

**Header blockquote** — every living document opens with one, carrying its step
number in the loop, what it derives from, and what derives from it. Keep the
line current when a document's relationships change. The transient hand-off
("run `/aide-…` next") is spoken by the skill that wrote the file, not stored
in it.

**A stage section's work is a Deliverables block of flat bullets, each
`- <icon> <text>. *(Item NNN)*` — one status icon, one item ref, no nested
status-bearing sub-bullets** (§1 → `progress.md`). The `*(Item NNN)*` suffix is
what ties an item to the bullet whose status it moves, so an item no bullet
references is untracked. **Suffix means suffix**: only the trailing marker that
ends the bullet (its last wrapped line) attributes; a bullet whose references
all sit mid-prose tracks nothing, and `aide check` warns about it. The marker
forms, all read the same way by every command:

| Form | Reads as |
|---|---|
| `*(Item 006)*` | 6 |
| `*(Items 006, 044)*` | 6, 44 — one deliverable, several items |
| `*(Items 089/090)*` | 89, 90 |
| `*(Items 071–075)*` | 71, 72, 73, 74, 75 — inclusive, hyphen or en-dash |
| `*(Items 006, 044–046)*` | 6, 44, 45, 46 — an element may be a range |

Prefer the explicit list when the items are not contiguous; a range is only
shorthand for one. **A marker naming several items is shorthand, never a shared
status cell** — write the shared marker freely; the file simply grows a row the
first time its items diverge. Follow-on deliverables enter through the queue,
never by retro-editing a closed stage's deliverable list.

**Prefer the verb to a hand edit**: `aide progress set`, `aide progress accept`,
`aide queue tidy`, `aide gate`. Acceptance boxes are **ticked only by
`aide progress accept` — never derived**, and the one hand edit anyone makes in
`progress.md` is adding a row to the `## Human gates` table, which has no verb —
**resolving is a CLI operation, never a hand edit** (`aide gate` only lists,
approves and declines).

**A human gate is a decision only a person can make, blocking work until they
make it** (§1 → human gates) — one row in that table:

```
| Gate | Blocks | Status | Decision / evidence |
|------|--------|--------|---------------------|
| Golden-file retirement approved | 106 | ⏳ Awaiting | — |
```

**Blocks** — item numbers (any §1 reference form, or bare: `106`, `110, 111`,
`106–108`), `stage N`, or `all`. **Status** — `⏳ Awaiting`, then
`✅ Approved (date)` or `❌ Declined (date)`. **Reach is per gate, and never a
queue**: exactly those items when the decision affects one thread and the
queue keeps producing other work; `stage N` when the decision could
*invalidate* a stage's work (resolved live through `progress.md`); `all` for a
programme-level stop. The person raising the gate chooses the reach. A gate
known at planning time is stated in the `roadmap.md` stage and implies
`Blocks: stage N`; one discovered while specifying an item is noted in its
Validation or Assumptions block, implying `Blocks: NNN`; `progress.md` holds
the **authoritative row**, always — a gate that exists only as prose in a
roadmap or a spec blocks nothing. **A declined gate keeps blocking.** The
remedy is to re-plan: drop the blocked items, or change what the gate asks.

**Correcting an attestation has verbs too, so it is never a hand edit either.**
**The attestation is immutable; what is recorded about it is not** (§1 →
`progress.md`) — the rule `insights.md` already runs on. `aide progress amend`
appends a dated correction to a ticked box, `retract` unticks one while keeping
the original visible, and `reword` fixes a criterion's wording. **`amend`
appends, and only to a ticked box** — the guard is structural, not advisory:
**a verb that can only add cannot be used to make an inconvenient attestation
agree with a shipped stage.** **`retract` unticks, and keeps the original
attestation visible**; **a retraction is a finding, so the verb routes it like
one** into `insights.md`. **`reword` is the one amendment that edits rather
than appends**, so it **refuses over a box that is ticked, annotated, or
already carries a correction trail**, and it **writes both documents or
neither** — `roadmap.md` mirrors the criteria.

**An item spec's filename begins with the zero-padded number, and its first
`#` heading is `# Item NNN — Title`** (§1 → `items.md`). **No status field in
the header — status lives only in `progress.md`.** The header carries
`Created`, Stage, Queue, Objectives, Suggested branch, and a mandatory
**Assumptions** block. **An assumption that pins engine behaviour names the
engine it was true for** — `- **A3 (engine 1.28.1):** …` — and is corrected by
append: a re-check goes into the marker, `(engine 1.28.1, re-checked 1.36.0)`,
and the newest version named is the one the claim stands on. A merged spec is
never rewritten to agree with a later engine.

**`## Dependencies` blocks `aide claim`**: every item number named there is
read as something this item is blocked on until that item is merged (✅), or
leaves the queue's way as ❌ excluded or ⏸️ deferred — 🚧 and 🔍 both still
block. Text at or after a literal `**Downstream` marker is excluded from that
scan, so put such asides after the marker, never before it. The rest of any
line from a backticked or bold `Blocks:` label on is excluded too, so quoting a
gate row's reach adds no edges; keep a reach quote on one line — the exclusion
does not extend past it.

**An acceptance criterion is an invariant over the resulting content** (§1 →
`items.md`) — never a bound on the diff that produced it, and never a premise
about a sibling item's schedule. Its test outlives the branch it was written on:
a criterion that cannot be re-checked once the item has merged is not one the
suite can keep. The diff-time half of such a claim ("this item did not touch X")
is `aide scope`'s, declared under `## Asserts against`; a premise that a sibling
has not landed yet is guaranteed to become false, so the later item's spec lists
that test file under **May change** from the start.

**And it is a claim about the world, not about its own wording: a criterion
that asserts a fact about live state is a measured equality against that
state, and a criterion that closes a stage acceptance criterion names which
one** (§1 → `items.md`). A factual AC — a field set, a firing set, a consumed
path, a count — is met only by a test that **recomputes that fact from the
primary source and compares**; a check its subject can satisfy while the claim
is false (a sentence's length, a token in it that resolves, a completeness flag
derived from the declarations rather than from what they describe) is not
evidence, and three of those passed three false claims into merged artifacts in
one queue. And an item's ACs are not positionally mapped onto its stage's
acceptance criteria: an AC closes one only where the spec's optional *(closes
Stage N criterion M)* annotation says so, and **an AC that names none closes
none**. `aide progress accept` is per-criterion for this reason: the evidence
names the check that closes *that* criterion, and an index is not a check.
Under a spec authored with the annotation available, silence is an answer: no
annotation means no stage criterion is closed. The one transitional exception
declares itself — a merged spec predating the annotation is not rewritten to
carry it, and its stage may still be attested on the criterion's own subject
where the evidence names the check and says the mapping was made at attestation
time.

**Capture is a plain append; everything after it has a verb** (§1 →
`insights.md`): `aide insights list --open` reads the backlog without the
closed history around it, `aide insights tick N --pointer "<where it landed>"`
closes an entry — **ticking the checkbox is the one in-place edit**, and the
verb owns it, so a hand-flipped `[x]` is the improvised form of `tick` — and
`aide insights archive --before <date> --yes` moves closed entries out (a dry
run without `--yes`). Reading the file raw costs the whole closed history to
see a working set of a dozen lines; editing it by hand is the failure `tick`
exists to prevent.

The fourth verb covers the one moment the whole file is in front of something
willing to rewrite it. Append-only means two branches that each captured an
insight conflict on every merge, and `aide insights resolve [--dry-run]` writes
the union of both sides — shared history, then each side's new entries, ticks
and trails merged — instead of a hand retyping the block. **It refuses anything
that is not a pure append** (a reworded, reordered or deleted claim, or a side
that archived) and writes nothing when it does, because each of those is a
change to an immutable line that a human must see. Do not resolve this file's
conflict by hand: a committed conflict marker is an `aide check` error, and the
message names the verb.

**The open inbox is an input to queue authoring, not only an output of triage**
(§1 → `insights.md`). Triage happens *at* the queue boundary, when the next
queue does not exist yet, so a `defect`, `gap` or `automation` entry routed
there to "a candidate item" waits in the inbox for whoever authors that queue:
`aide insights list --open` is one of its inputs, beside vision, roadmap and
progress. Every open entry of those three types is **considered, and either
queued or explicitly passed over — never silently dropped**; a queued one is
ticked with the item number it became, and a passed-over one stays open,
because an unchecked entry is still a candidate.

**Root documents are authored through their loop entry point, interactively —
whatever `loop.clarify` says** (`.aide/conventions.md` §5); here that entry point
is `/aide-create-vision` / `/aide-create-roadmap`, which carries the
existing-document check and the draft-for-review hand-off. **Do not write a root
document directly, however well the template shape is known** — ask until the
mandatory sections are grounded in their answers, and never fill **Guiding
principles**, **Out of scope**, or **Success criteria** from assumption.
