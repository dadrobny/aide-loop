---
paths:
  - "**/progress.md"
  - "**/roadmap.md"
  - "**/vision.md"
  - "**/insights.md"
  - "**/queue/*.md"
  - "**/items/*.md"
---

<!-- reach: all
     Measured, not aspired to: every one of the six agent specs names a
     living document, so the `paths:` block above scopes this to nobody and
     the cost is paid on every spawn. That is issue #79's regression, still
     live; #85 is where it gets re-shaped. #84's job was only to stop it
     being invisible. See `tests/test_structural_budget.py`. -->

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

Scoped by document name rather than by `project.docs_dir`, so it holds whatever
a consumer configured. Every role reaches at least one of these files, so treat
this rule as one you will always see, not one that fires rarely.

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
