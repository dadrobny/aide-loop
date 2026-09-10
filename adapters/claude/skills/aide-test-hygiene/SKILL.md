---
name: aide-test-hygiene
description: Load before creating or editing a test file — portability rules and tests that can actually fail (conventions §6).
user-invocable: false
paths:
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/conftest.py"
  - "**/tests/**/*.py"
---

<!-- reach: test-writer
     Literal, not measured: this body is preloaded into exactly the agent
     specs whose `skills:` frontmatter names `aide-test-hygiene`, at spawn,
     before the role has opened anything — so a repo with no test to read
     still delivers it. The `paths:` above inject nothing on a read (issue
     #85, measured): the description sits in every interactive session's skill
     listing regardless, and the globs only narrow when the runtime
     auto-invokes the skill on its own. `builder` and `validator` open test
     files but write none, and are deliberately not listed.
     `tests/test_structural_budget.py` compares this line to the `skills:`
     lists. -->

<!-- triggers: test-writer
     The interactive half, declared so the glob evaluator stays on an
     assertion path: the roles whose named reads match the `paths:` above.
     Only `test-writer` names a test file (`conftest.py`); the others reach
     `project.tests_dir` without naming a file in it. -->

<!-- generated-from: .aide/conventions/6-test-hygiene.md
     Everything below the note is that file, down to its `Rationale` heading,
     written here by `install.py` at install time (issue #109). There is no
     hand-written copy of §6 to drift, so this file declares no `pins`
     block: that mechanism guards a restatement, and this is not one. Edit
     the section. -->

**Delivery, not a second source of truth.** What follows is
`.aide/conventions.md` §6 — `.aide/conventions/6-test-hygiene.md`, down to its
`Rationale` heading — rendered here verbatim at install time, so it cannot say
anything the engine does not. The defect each rule was earned by is in the
section below that heading; `.aide/conventions.md` resolves any `§N`.

The `paths:` above match by filename rather than by `project.tests_dir`, so they
hold whatever a consumer configured: the default pytest naming plus any
directory named `tests`. A project that overrides pytest's `python_files`, or
keeps tests in `spec/`, needs them widened to match.
