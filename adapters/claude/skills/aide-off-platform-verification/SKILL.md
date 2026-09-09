---
name: aide-off-platform-verification
description: Load before reading a pushed branch's CI result — no role in this loop sees a non-Linux checkout or real CI status, so look at the gate that does, and read a red leg as portability (conventions §7).
user-invocable: false
paths:
  - "**/.github/workflows/*.yml"
---

<!-- reach: validator
     Literal, not measured: this body is preloaded into exactly the agent
     specs whose `skills:` frontmatter names `aide-off-platform-verification`
     — the one role that acts on a CI result, once its push exists. Before
     this the section was reached by an **unpinned inline restatement** in
     `validator.md` and by two `aide.py` docstrings; nothing pointed at it
     (issue #186's reach column, the #81 shape on the undelivered side). The
     `reviewer` is deliberately not listed: it reads a diff, not a run, and
     the section it does share with the validator is §9. The `paths:` above
     inject nothing on a read (issue #85, measured): the description sits in
     every interactive session's skill listing regardless, and the globs only
     narrow when the runtime auto-invokes the skill on its own.
     `tests/test_structural_budget.py` compares this line to the `skills:`
     lists. -->

<!-- triggers: none
     The interactive half, declared so the glob evaluator stays on an
     assertion path: the roles whose named reads match the `paths:` above.
     This is the one delivered section that is not about a document the loop
     writes — it is about a gate that runs elsewhere — so the file that
     matches it is the CI workflow, which no agent spec names. `none` is the
     honest answer, and it is asserted like any other: a glob widened until it
     matched a role's read would fail here rather than pass unnoticed. -->

<!-- generated-from: .aide/conventions/7-off-platform-verification.md
     Everything below the note is that file, down to its `Rationale` heading,
     written here by `install.py` at install time (issue #109). There is no
     hand-written copy of §7 to drift, so this file declares no `pins`
     block: that mechanism guards a restatement, and this is not one. Edit
     the section. -->

**Delivery, not a second source of truth.** What follows is
`.aide/conventions.md` §7 — `.aide/conventions/7-off-platform-verification.md`,
down to its `Rationale` heading — rendered here verbatim at install time, so it
cannot say anything the engine does not. The reasoning behind each rule is in
the section below that heading; `.aide/conventions.md` resolves any `§N`.
