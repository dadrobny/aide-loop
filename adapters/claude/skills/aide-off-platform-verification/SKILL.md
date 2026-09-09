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

<!-- pins: .aide/conventions/7-off-platform-verification.md
     Quoted from that section; `test_rule_pins.py` fails if either copy moves
     alone.
     - No role in this loop sees a non-Linux checkout, a different working
       directory, or real CI status
     - Once work is pushed, **check the real CI result** rather than inferring
       it from a green local suite
     - Report what CI actually said, including "no CI is configured here" or
       "it had not finished"
     - never let a local pass stand in for a platform the loop cannot reach
     - When CI is red on a leg that passed locally, treat it as a
       **portability finding first** (§6), not a flake, until the log says
       otherwise
-->

# Off-platform verification

`.aide/conventions.md` §7 is the source of truth; this file is how it reaches
`validator`, the role that acts on it once the item's push exists. It is
**delivery, not a second source of truth**. §6 covers the leg this loop can
see; this is the one it cannot.

**No role in this loop sees a non-Linux checkout, a different working
directory, or real CI status**, so the honest response is to look at the one
gate that does:

- Once work is pushed, **check the real CI result** rather than inferring it
  from a green local suite. Report what CI actually said, including "no CI is
  configured here" or "it had not finished" — never let a local pass stand in
  for a platform the loop cannot reach.
- When CI is red on a leg that passed locally, treat it as a **portability
  finding first** (§6), not a flake, until the log says otherwise.
