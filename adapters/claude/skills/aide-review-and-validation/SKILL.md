---
name: aide-review-and-validation
description: Load before reading an item's diff to judge it — what validation answers, what review answers, why neither covers for the other, and how a finding triages (conventions §9).
user-invocable: false
paths:
  - "**/REVIEW.md"
---

<!-- reach: reviewer, validator
     Literal, not measured: this body is preloaded into exactly the agent
     specs whose `skills:` frontmatter names `aide-review-and-validation` —
     the two roles that read a finished item's diff to judge it. Preloaded at
     spawn, so the distinction is in context before either opens the diff,
     which is the point: the failure mode §9 names is a role collapsing the
     two reads, and a role that has already collapsed them will not go and
     read a pointer. The `paths:` above inject nothing on a read (issue #85,
     measured): the description sits in every interactive session's skill
     listing regardless, and the globs only narrow when the runtime
     auto-invokes the skill on its own. `builder` receives findings but
     performs neither read, and is deliberately not listed.
     `tests/test_structural_budget.py` compares this line to the `skills:`
     lists. -->

<!-- triggers: reviewer
     The interactive half, declared so the glob evaluator stays on an
     assertion path: the roles whose named reads match the `paths:` above.
     Only `reviewer` names `REVIEW.md` — the repo's own review contract is
     the one file this section is about, and the role that is handed it is
     the only one that names it. -->

<!-- generated-from: .aide/conventions/9-review-and-validation.md
     Everything below the note is that file, down to its `Rationale` heading,
     written here by `install.py` at install time (issue #109). There is no
     hand-written copy of §9 to drift, so this file declares no `pins`
     block: that mechanism guards a restatement, and this is not one. Edit
     the section. -->

**Delivery, not a second source of truth.** What follows is
`.aide/conventions.md` §9 — `.aide/conventions/9-review-and-validation.md`, down
to its `Rationale` heading — rendered here verbatim at install time, so it
cannot say anything the engine does not. The reasoning behind each rule is in
the section below that heading; `.aide/conventions.md` resolves any `§N`.
