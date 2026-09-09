<!-- reach: all
     No `paths:` block, so this loads in every session and every sub-agent —
     it is part of the always-on floor every spawn pays for. Deliberate: the
     hygiene rules bind any Bash call, and there is no file whose opening
     predicts one. See `tests/test_structural_budget.py` for the convention. -->

<!-- generated-from: .aide/conventions/3-command-hygiene.md
     Everything below the shaping note is that file, down to its `Rationale`
     heading, written here by `install.py` at install time (issue #109). There
     is no hand-written copy of §3 to drift, so this file declares no `pins`
     block: that mechanism guards a restatement, and this is not one. Edit
     the section. -->

**Delivery, not a second source of truth.** What follows is
`.aide/conventions.md` §3 — `.aide/conventions/3-command-hygiene.md`, down to
its `Rationale` heading — rendered here verbatim at install time, so it cannot
say anything the engine does not. A `PreToolUse` hook enforces the mechanical
rules and bounces a violating shape back with the fix, and an unattended run
that emits a shape nothing pre-approved stalls on a permission prompt — so
getting them right first time is what keeps a long run moving.

**The shaping this runtime adds**, which §3 leaves to the adapter: **use the
Bash tool, not PowerShell** for git / `aide` / venv / grep commands — only
`Bash(...)` rules are allow-listed.
