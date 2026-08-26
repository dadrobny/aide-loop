---
paths:
  - "**/progress.md"
  - "**/roadmap.md"
  - "**/vision.md"
  - "**/insights.md"
  - "**/queue/*.md"
  - "**/items/*.md"
---

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
🔍 In Review · ✅ Done · ⏸️ Blocked · ❓ Unverified. They are read at three
*structural* positions only — an objective heading, a stage heading, and the
leading character of a deliverable bullet. The same characters in prose or a
table cell are text, not status.

**`{{slot}}` is a literal value to substitute; an _italic line_ is authoring
guidance to read then replace.** `aide check` flags any `{{…}}` surviving into a
generated document as an unfilled slot, so guidance must never be written as a
slot.

**Prefer the verb to a hand edit**: `aide progress set`, `aide progress accept`,
`aide queue tidy`, `aide gate`. `progress.md`'s status rows and acceptance boxes
are written *only* by a verb — the one hand edit anyone makes there is adding a
row to the `## Human gates` table, which has no verb (`aide gate` only lists,
approves and declines).
