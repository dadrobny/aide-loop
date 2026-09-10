---
name: aide-progress-file
description: Load before writing progress.md — deliverable bullets and their item markers, and the attestation verbs that correct an acceptance box without editing it (conventions §1).
user-invocable: false
paths:
  - "**/progress.md"
---

<!-- reach: queue-planner, validator
     Literal, not measured: this body is preloaded into exactly the agent
     specs whose `skills:` frontmatter names `aide-progress-file` — the two
     roles that move this file. `queue-planner` writes the deliverable
     bullets and the `*(Item NNN)*` markers item numbers are born in;
     `validator` runs `progress set`, `progress accept` and the three
     correction verbs over them. `spec-author` is deliberately not listed:
     the one edit it makes here is a human-gate row, which
     `aide-human-gates` delivers, and `builder` reaches the file only through
     `aide progress set`. The `paths:` above inject nothing on a read (issue
     #85, measured): the description sits in every interactive session's skill
     listing regardless, and the globs only narrow when the runtime
     auto-invokes the skill on its own.
     `tests/test_structural_budget.py` compares this line to the `skills:`
     lists. -->

<!-- triggers: builder, queue-planner, reviewer, spec-author, spec-reviewer, validator
     The interactive half, declared so the glob evaluator stays on an
     assertion path: the roles whose named reads match the `paths:` above.
     Every role but `test-writer` names `progress.md` — it is the single
     source of truth for status, so most roles read it and two write it. -->

<!-- pins: .aide/conventions/1-format-contract/progress.md
     Quoted from that section; `test_rule_pins.py` fails if either copy moves
     alone.
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
     - A box is ticked only by a human — or by an agent acting on a check it
       actually performed
     - A stage may be ✅ with an unticked box; say why in an annotation beside it
     - An Acceptance box is therefore an observable check **of the built thing**
     - A **measured outcome** the work aims for but cannot guarantee by
       construction (an error-rate target, a benchmark result) must NOT be an
       Acceptance box
     - A target **never blocks its stage**
     - Marking a target `❌ Not met` is a *finding*, so route it like one:
       append a `- [ ] gap — …` line to `insights.md` in the same edit
     - The attestation is immutable; what is recorded about it is not
     - Three verbs, and **none of them edits the original line**
     - `amend` appends, and only to a ticked box
     - a verb that can only add cannot be used to make an inconvenient attestation agree with a shipped stage
     - `retract` unticks, and keeps the original attestation visible
     - A retraction is a finding, so the verb routes it like one
     - `reword` is the one amendment that edits rather than appends
     - refuses over a box that is ticked, annotated, or already carries a correction trail
     - writes both documents or neither
-->

# `progress.md`

`.aide/conventions.md` §1 → `progress.md` is the source of truth; this file is
how it reaches the two roles that move the file — `queue-planner`, which writes
the deliverable bullets item numbers are born on, and `validator`, which runs
the verbs over them. It is **delivery, not a second source of truth**. That
status lives in one place is on the floor, in `AGENT-CONTEXT.md`, already in
this context; the icon vocabulary is in `aide-document-format`.

**A stage section's work is a Deliverables block of flat bullets, each
`- <icon> <text>. *(Item NNN)*` — one status icon, one item ref, no nested
status-bearing sub-bullets.** The `*(Item NNN)*` suffix is what ties an item to
the bullet whose status it moves, so an item no bullet references is untracked.
**Suffix means suffix**: only the trailing marker that ends the bullet (its
last wrapped line) attributes; a bullet whose references all sit mid-prose
tracks nothing, and `aide check` warns about it. The marker forms, all read the
same way by every command:

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

**Prefer the verb to a hand edit**: `aide progress set`, `aide progress
accept`, `aide queue tidy`. Acceptance boxes are **ticked only by
`aide progress accept` — never derived**, and no rollup ever ticks one. **A
box is ticked only by a human — or by an agent acting on a check it actually
performed** — via `aide progress accept`, whose flags `aide progress -h`
states.

**A stage may be ✅ with an unticked box; say why in an annotation beside it.**

**What a box may claim.** Stage status tracks exactly one thing — the planned
work shipped. **An Acceptance box is therefore an observable check of the built
thing** (the CLI runs, the artifact validates), something completing the
deliverables can guarantee. **A measured outcome the work aims for but cannot
guarantee by construction (an error-rate target, a benchmark result) must NOT
be an Acceptance box**: it belongs in the `## Outcome targets` table, where **a
target never blocks its stage** — the stage closes when its work ships, and the
target gates the Objective coverage rows instead. **Marking a target
`❌ Not met` is a *finding*, so route it like one: append a `- [ ] gap — …`
line to `insights.md` in the same edit.**

**Correcting an attestation has verbs too, so it is never a hand edit either.**
**The attestation is immutable; what is recorded about it is not** — the rule
`insights.md` already runs on. **Three verbs, and none of them edits the
original line**: `aide progress amend` appends a dated correction to a ticked
box, `retract` unticks one while keeping the original visible, and `reword`
fixes a criterion's wording. **`amend` appends, and only to a ticked
box** — the guard is structural, not advisory: **a verb that can only add
cannot be used to make an inconvenient attestation agree with a shipped
stage.** **`retract` unticks, and keeps the original attestation visible**;
**a retraction is a finding, so the verb routes it like one** into
`insights.md`. **`reword` is the one amendment that edits rather than
appends**, so it **refuses over a box that is ticked, annotated, or already
carries a correction trail**, and it **writes both documents or neither** —
`roadmap.md` mirrors the criteria.
