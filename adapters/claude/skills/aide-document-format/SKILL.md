---
name: aide-document-format
description: Load before writing a living AIDE document — the shapes aide.py parses, template slots, ISO dates, the header blockquote, and the only six status icons (conventions §1).
user-invocable: false
paths:
  - "**/progress.md"
  - "**/roadmap.md"
  - "**/vision.md"
  - "**/insights.md"
  - "**/queue/*.md"
  - "**/items/*.md"
---

<!-- reach: queue-planner, spec-author, validator
     Literal, not measured: this body is preloaded into exactly the agent
     specs whose `skills:` frontmatter names `aide-document-format` — the
     rules that hold for *every* shape-parsed document, so every role that
     writes one carries them. The two writers author documents from a
     template; the validator writes dated evidence and annotations into
     `progress.md` and dated lines into `insights.md`, and is the role that
     moves an item's status, so the icon vocabulary and the ISO-date rule bind
     it too — it had the ✅-means-merged half of §1 → status-icons restated
     inline in its own spec and nothing pinned it. The four roles that write
     none of the shape-parsed documents are deliberately not listed: the one
     line they do append, the insight entry, has its shape on the floor in
     `AGENT-CONTEXT.md`. The `paths:` above inject nothing on a read (issue
     #85, measured): the description sits in every interactive session's skill
     listing regardless, and the globs only narrow when the runtime
     auto-invokes the skill on its own.
     `tests/test_structural_budget.py` compares this line to the `skills:`
     lists. -->

<!-- triggers: all
     The interactive half, declared so the glob evaluator stays on an
     assertion path: the roles whose named reads match the `paths:` above —
     what a rule with these globs would arm, and what the loop no longer
     pays. Every role names an item spec or `insights.md`, so: all. -->

<!-- pins: .aide/conventions/1-format-contract.md
     Quoted from that section; `test_rule_pins.py` fails if either copy moves
     alone. One block per section file, so two blocks follow.
     - The templates in `.aide/templates/` model the shapes and `aide check`
       enforces every one the tooling reads
     - a literal value to substitute
     - authoring guidance to read then replace
     - left in a generated `docs/aide/**.md` file as an unfilled template slot
     - Dates are always **ISO 8601** (`YYYY-MM-DD`)
     - every living document opens with one, carrying its step number in the
       loop, what it derives from, and what derives from it
     - Keep the line current when a document's relationships change
     - is spoken by the skill that wrote the file, not stored in it
-->

<!-- pins: .aide/conventions/1-format-contract/status-icons.md
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
     - ✅ means merged — in every `git.mode`
     - It is written by `aide merge` when the merge actually happens, not by
       an agent ahead of one
     - 🔍 is the state between: the work is pushed and awaiting a human's merge
     - The mode never changes what a status asserts
-->

# Living-document format

`.aide/scripts/aide.py` parses these files by exact shape. The templates in
`.aide/templates/` model the shapes and `aide check` enforces every one the
tooling reads.
`.aide/conventions.md` §1 is the source of truth and carries one file per shape
(`§1 → progress.md` is `conventions/1-format-contract/progress.md`, and so on);
this file is **delivery, not a second source of truth**, and carries only what
holds for *every* shape — the icon vocabulary and the rules a document is
written under. The per-document shapes reach the role that writes each
document, one skill each; the durable-artifact, insight-immutability and
human-gate rules are in `AGENT-CONTEXT.md`, already in this context.

It is preloaded into the three roles that write a shape-parsed document —
`queue-planner`, `spec-author` and `validator` — so it is in context before the
first write, and an interactive session sees its description in the skill
listing, with the `paths:` above keeping the runtime's own invocation of it to
work on one of these files. The globs match by document name rather than by
`project.docs_dir`, so they hold whatever a consumer configured.

**The six status icons, and nothing else:** 📋 Planned · 🚧 In Progress ·
🔍 In Review · ✅ Complete · ⏸️ Deferred · ❌ Excluded (§1 → status icons).
They are read at **structural positions only** — a table row's **Status (last)
cell**, a stage header's **trailing** `— <icon>`, and the **leading** icon of a
deliverable bullet. An icon anywhere else — prose, mid-bullet, a title — is
plain text and is never read as status; `aide check` still *warns* on such
stray icons in the status-bearing documents (`progress.md`, queue files), so
keep them out of those. Rank is used when one item is referenced on several
lines: the most-advanced status wins.

**✅ means merged — in every `git.mode`.** It is written by `aide merge` when
the merge actually happens, not by an agent ahead of one; 🔍 is the state
between: the work is pushed and awaiting a human's merge. The mode never
changes what a status asserts, so a role that has validated an item writes 🔍
and leaves ✅ to the verb.

**`{{slot}}` is a literal value to substitute; an _italic line_ is authoring
guidance to read then replace.** `aide check` flags any `{{...}}` left in a
generated `docs/aide/**.md` file as an unfilled template slot, so guidance must
never be written as a slot. Dates are always **ISO 8601** (`YYYY-MM-DD`).

**Header blockquote** — every living document opens with one, carrying its step
number in the loop, what it derives from, and what derives from it. Keep the
line current when a document's relationships change. The transient hand-off
("run `/aide-…` next") is spoken by the skill that wrote the file, not stored
in it.
