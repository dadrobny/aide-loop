## 9. Review and validation (two reads, one diff)

Runtime-general, like §3 and §6. An adapter **delivers** this section to the
roles that perform either read rather than pointing at it: a role that has not
been told the difference will collapse the two, and the collapse is silent —
both reads end in a report that says the item is fine.

**Validation and review answer different questions.** Validation asks *does
this branch meet the Acceptance Criteria of the spec it was built from* — the
suite is green, every AC has a test that measures it, the diff is inside the
authorised paths, the Assumptions still hold. Every term is measured against
the item spec, the verdict is PASS/FAIL, and it **gates the merge**. Review
asks *is this code correct, and does it fit the codebase* — it reads the diff
adversarially for what the spec never anticipated, and it **produces findings**,
not a verdict.

**A green validator is not a review, and a clean review does not discharge
validation.** The two fail in opposite directions and neither covers for the
other. A spec cannot enumerate in advance the enumeration that drops an input,
the guard that passes while the thing it checks is absent, or the contract an
earlier item established and a later one quietly reworked — which is exactly
why a check measured against that spec cannot find them. Equally, a reviewer
reading for defects is not counting Acceptance Criteria, running the suite, or
comparing the diff against the authorised paths; a review that reported nothing
has said nothing about whether the item did what it was specified to do.

**Findings triage the way insights do (§1 → insights.md).** A review finding
in scope for the running item is a fix on its branch, dispatched back to the
role that owns the file. One outside it is a single line in `insights.md`, for
the feedback loop to triage at the queue boundary — never a widening of the
item's authorised paths, and never acted on in place. The two questions are the
same ones every role already answers about an out-of-scope observation, so the
answer is the same shape.

**A review that lands after the merge is a report, not a review.** Wherever an
adapter runs the reviewer concurrently with validation — the placement that
costs no wall-clock, because a full suite run is the long pole and a read of
the diff fits inside it — the merge still waits for both. Findings collected
after the item has landed gate nothing, and the loop is entitled to treat
"reviewed" as meaning the findings were available while the decision was still
open.

**Neither read signs off its own work.** The role that wrote the code performs
neither, and the reviewer writes no code, modifies no tests, does not merge,
and does not touch `progress.md` — its output is findings for another role to
act on. A reviewer that fixes what it finds has destroyed the evidence for the
call, and has reviewed its own work by the time it is done.
