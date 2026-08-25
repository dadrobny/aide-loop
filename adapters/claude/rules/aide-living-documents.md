---
paths:
  - "**/progress.md"
  - "**/roadmap.md"
  - "**/vision.md"
  - "**/insights.md"
  - "**/queue/*.md"
  - "**/items/*.md"
---

# Living documents

`.aide/scripts/aide.py` parses these files by exact shape. `.aide/conventions.md`
§1 is the source of truth and carries one file per document shape
(`§1 → progress.md` is `conventions/1-format-contract/progress.md`, and so on);
this file is how the parts that bind on *any* edit reach the session, and it is
**delivery, not a second source of truth**.

Scoped by document name rather than by `project.docs_dir`, so it holds whatever a
consumer configured.

**Edit through the CLI where a verb exists.** `aide progress set`, `aide progress
accept`, `aide queue tidy`, `aide gate` — hand-editing is what makes a document
unparseable, and `progress.md` in particular is only ever written by a verb.

**The six status icons, and nothing else:** 📋 Planned · 🚧 In Progress ·
🔍 In Review · ✅ Done · ⏸️ Blocked · ❓ Unverified. They are read at three
*structural* positions only — an objective heading, a stage heading, and the
leading character of a deliverable bullet. The same characters in prose or a
table cell are text, not status.

**`{{slot}}` is a literal value to substitute; an _italic line_ is authoring
guidance to read then replace.** `aide check` flags any `{{…}}` surviving into a
generated document as an unfilled slot, so guidance must never be written as a
slot.

**A captured insight is immutable.** Never reworded, reordered or deleted, not
even when it turns out to be wrong. Ticking its checkbox is the one in-place
edit; anything afterwards goes in dated lines indented beneath it.

**Only a person resolves a human gate.** Any role may add a row to the `## Human
gates` table — the worst case is work pausing. No agent runs `aide gate approve`
or `decline`.

**Durable artifacts must read cold.** No chat-local identifiers; cross-reference
by resolvable identity (issue number, path, commit, stage, dated insight);
record the decision and why it holds, not the route to it.
