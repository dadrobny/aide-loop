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

<!-- pins: .aide/conventions/9-review-and-validation.md
     Quoted from that section; `test_rule_pins.py` fails if either copy moves
     alone.
     - Validation and review answer different questions
     - the verdict is PASS/FAIL, and it gates the merge
     - it reads the diff adversarially for what the spec never anticipated,
       and it produces findings, not a verdict
     - A green validator is not a review, and a clean review does not
       discharge validation
     - The two fail in opposite directions and neither covers for the other
     - a review that reported nothing has said nothing about whether the item
       did what it was specified to do
     - Findings triage the way insights do
     - A review finding in scope for the running item is a fix on its branch,
       dispatched back to the role that owns the file
     - One outside it is a single line in `insights.md`
     - never a widening of the item's authorised paths, and never acted on in
       place
     - A review that lands after the merge is a report, not a review
     - the merge still waits for both
     - Neither read signs off its own work
     - the reviewer writes no code, modifies no tests, does not merge, and
       does not touch `progress.md`
     - A reviewer that fixes what it finds has destroyed the evidence for the
       call
-->

# Review and validation

`.aide/conventions.md` §9 is the source of truth. This file is how §9 reaches a
role about to judge an item's diff: it is preloaded at spawn, so it is in
context before the diff is opened, and an interactive session sees its
description in the skill listing. It is **delivery, not a second source of
truth**.

**Validation and review answer different questions.** Validation asks *does
this branch meet the Acceptance Criteria of the spec it was built from* — the
suite is green, every AC has a test that measures it, the diff is inside the
authorised paths, the Assumptions still hold. Every term is measured against
the item spec, the verdict is PASS/FAIL, and it gates the merge. Review asks
*is this code correct, and does it fit the codebase* — it reads the diff
adversarially for what the spec never anticipated, and it produces findings,
not a verdict.

**A green validator is not a review, and a clean review does not discharge
validation.** The two fail in opposite directions and neither covers for the
other. A spec cannot enumerate in advance the enumeration that drops an input,
the guard that passes while the thing it checks is absent, or the contract an
earlier item established and a later one quietly reworked — which is why a
check measured against that spec cannot find them. Equally, a reviewer reading
for defects is not counting Acceptance Criteria, running the suite, or
comparing the diff against the authorised paths: a review that reported nothing
has said nothing about whether the item did what it was specified to do.

**Findings triage the way insights do** (§1 → insights.md). A review finding in
scope for the running item is a fix on its branch, dispatched back to the role
that owns the file. One outside it is a single line in `insights.md`, for the
feedback loop to triage at the queue boundary — never a widening of the item's
authorised paths, and never acted on in place. These are the two questions
every role already answers about an out-of-scope observation, so the answer
takes the same shape.

**A review that lands after the merge is a report, not a review.** Where the
reviewer runs concurrently with validation — the placement that costs no
wall-clock, because a full suite run is the long pole and a read of the diff
fits inside it — the merge still waits for both.

**Neither read signs off its own work.** The role that wrote the code performs
neither, and the reviewer writes no code, modifies no tests, does not merge,
and does not touch `progress.md` — its output is findings for another role to
act on. A reviewer that fixes what it finds has destroyed the evidence for the
call, and has reviewed its own work by the time it is done.
