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
     `paths:` above inject nothing on a read and only surface the description
     to an interactive session working on a matching file. The four roles
     that read these documents without writing one are deliberately not
     listed. `tests/test_structural_budget.py` compares this line to the
     `skills:` lists. -->

<!-- pins: .aide/conventions/1-format-contract/status-icons.md
     Quoted from that section; `test_rule_pins.py` fails if either copy moves
     alone. One block per section file, so five blocks follow.
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
-->

<!-- pins: .aide/conventions/1-format-contract.md
     - a literal value to substitute
     - authoring guidance to read then replace
-->

<!-- pins: .aide/conventions/1-format-contract/progress.md
     - ticked only by `aide progress accept` — never derived
-->

<!-- pins: .aide/conventions/1-format-contract/human-gates.md
     - Resolving is a CLI operation, never a hand edit
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

`.aide/scripts/aide.py` parses these files by exact shape. `.aide/conventions.md`
§1 is the source of truth and carries one file per shape (`§1 → progress.md` is
`conventions/1-format-contract/progress.md`, and so on); this file is **delivery,
not a second source of truth**, and carries only the shape rules — the durable
artifact, insight-immutability and human-gate rules are in `AGENT-CONTEXT.md`,
already in this context.

It is preloaded into the two roles that write a living document —
`spec-author` and `queue-planner` — so it is in context before the first
write, and it is listed by name to an interactive session working on one of
these files. The listing is matched by document name rather than by
`project.docs_dir`, so it holds whatever a consumer configured.

**The six status icons, and nothing else:** 📋 Planned · 🚧 In Progress ·
🔍 In Review · ✅ Complete · ⏸️ Deferred · ❌ Excluded. They are read at
**structural positions only** — a table row's **Status (last) cell**, a stage
header's **trailing** `— <icon>`, and the **leading** icon of a deliverable
bullet. An icon anywhere else — prose, mid-bullet, a title — is plain text and
is never read as status.

**`{{slot}}` is a literal value to substitute; an _italic line_ is authoring
guidance to read then replace.** `aide check` flags any `{{…}}` surviving into a
generated document as an unfilled slot, so guidance must never be written as a
slot.

**Prefer the verb to a hand edit**: `aide progress set`, `aide progress accept`,
`aide queue tidy`, `aide gate`. Acceptance boxes are **ticked only by
`aide progress accept` — never derived**, and the one hand edit anyone makes in
`progress.md` is adding a row to the `## Human gates` table, which has no verb —
**resolving is a CLI operation, never a hand edit** (`aide gate` only lists,
approves and declines).

**Root documents are authored through their loop entry point, interactively —
whatever `loop.clarify` says** (`.aide/conventions.md` §5); here that entry point
is `/aide-create-vision` / `/aide-create-roadmap`, which carries the
existing-document check and the draft-for-review hand-off. **Do not write a root
document directly, however well the template shape is known** — ask until the
mandatory sections are grounded in their answers, and never fill **Guiding
principles**, **Out of scope**, or **Success criteria** from assumption.
