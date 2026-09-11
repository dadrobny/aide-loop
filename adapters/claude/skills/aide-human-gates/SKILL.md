---
name: aide-human-gates
description: Load before raising a human gate — the row in progress.md that blocks work until a person decides, its Blocks and Status vocabulary, and how far a gate reaches (conventions §1).
user-invocable: false
paths:
  - "**/progress.md"
  - "**/roadmap.md"
---

<!-- reach: queue-planner, spec-author
     Literal, not measured: this body is preloaded into exactly the agent
     specs whose `skills:` frontmatter names `aide-human-gates` — the two
     roles that raise one. Raising a gate is the single `progress.md` edit
     either of them is permitted to make, and both specs carried the "a gate
     written only in the roadmap blocks nothing" clause inline with nothing
     pinning it (issue #184's table: eleven statements missing against one
     delivered, the widest gap in the old §1 bundle). `validator` is
     deliberately not listed: its spec raises no gate, and the half of this
     section it does act on — agents read a gate to know why they must stop,
     and only a person resolves one — is on the always-on floor in
     `AGENT-CONTEXT.md`. The `paths:` above inject nothing on a read (issue
     #85, measured): the description sits in every interactive session's skill
     listing regardless, and the globs only narrow when the runtime
     auto-invokes the skill on its own.
     `tests/test_structural_budget.py` compares this line to the `skills:`
     lists. -->

<!-- triggers: builder, queue-planner, reviewer, spec-author, spec-reviewer, validator
     The interactive half, declared so the glob evaluator stays on an
     assertion path: the roles whose named reads match the `paths:` above.
     A gate is recorded in `progress.md` and declared in `roadmap.md`, and
     every role but `test-writer` names one of the two — the test author
     reaches an item spec and a test file and neither of these. -->

<!-- pins: .aide/conventions/1-format-contract/human-gates.md
     Quoted from that section; `test_rule_pins.py` fails if either copy moves
     alone.
     - A **decision only a person can make**, blocking work until they make it
     - | Gate | Blocks | Status | Decision / evidence |
     - A row of any other width is not read as a gate at all
     - **Blocks** — item numbers (any §1 reference form, or bare: `106`,
       `110, 111`, `106–108`), `stage N`, or `all`
     - `⏳ Awaiting`, then `✅ Approved (date)` or `❌ Declined (date)`
     - Reach is per gate, and never a queue
     - The person raising the gate chooses the reach
     - implies `Blocks: stage N`
     - implying `Blocks: NNN`
     - the **authoritative row**, always
     - a gate that exists only as prose in a roadmap or a spec blocks nothing
     - A declined gate keeps blocking
     - The remedy is to re-plan: drop the blocked items, or change what the
       gate asks
     - Resolving is a CLI operation, never a hand edit
-->

# Human gates

`.aide/conventions.md` §1 → human gates is the source of truth; this file is
how it reaches the two roles that raise one — `queue-planner` and
`spec-author`, preloaded at spawn, since adding the row is the one
`progress.md` edit either may make and a gate noticed and not recorded blocks
nothing. It is **delivery, not a second source of truth**. That any role may
raise a gate and only a person may resolve one is on the floor, in
`AGENT-CONTEXT.md`, already in this context.

**A human gate is a decision only a person can make, blocking work until they
make it** — one row in `progress.md`'s `## Human gates` table, **four cells in
this order** (**a row of any other width is not read as a gate at all** —
`aide check` warns, but a warning stops nothing, so the work the row was
written to hold keeps flowing):

```
| Gate | Blocks | Status | Decision / evidence |
|------|--------|--------|---------------------|
| Golden-file retirement approved | 106 | ⏳ Awaiting | — |
```

**Blocks** — item numbers (any §1 reference form, or bare: `106`, `110, 111`,
`106–108`), `stage N`, or `all`. **Status** — `⏳ Awaiting`, then
`✅ Approved (date)` or `❌ Declined (date)`. **Reach is per gate, and never a
queue**: exactly those items when the decision affects one thread and the
queue keeps producing other work; `stage N` when the decision could
*invalidate* a stage's work (resolved live through `progress.md`); `all` for a
programme-level stop. The person raising the gate chooses the reach.

A gate known at planning time is stated in the `roadmap.md` stage and implies
`Blocks: stage N`; one discovered while specifying an item is noted in its
Validation or Assumptions block, implying `Blocks: NNN`; `progress.md` holds
the **authoritative row**, always — a gate that exists only as prose in a
roadmap or a spec blocks nothing. **A declined gate keeps blocking.** The
remedy is to re-plan: drop the blocked items, or change what the gate asks.

Adding the row is a hand edit because it has no verb. Everything after it does:
**resolving is a CLI operation, never a hand edit** (`aide gate` only lists,
approves and declines), and no agent runs it.
