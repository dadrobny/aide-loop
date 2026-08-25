---
paths:
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/conftest.py"
  - "tests/**/*.py"
---

# Test hygiene

`.aide/conventions.md` §6 is the source of truth, including the defect each rule
was earned by. This file is how §6 reaches a session that is about to touch a
test; it is **delivery, not a second source of truth**.

Scoped by filename rather than by `project.tests_dir`, so it holds whatever a
consumer configured — a file pytest will collect is a file these patterns match.

**The gap these close.** Every gate in this loop runs in one place, on one
platform, against one checkout, so a defect invisible under those conditions is
invisible to the whole loop. Each rule below is a class that reached `main`
regardless.

- **Never write the repo's own working-directory path literally into a test.**
  Resolve from the test file: `Path(__file__).resolve().parents[N]`. `aide
  check` warns on this — the one rule here a script can decide.
- **Any `Path` entering a hash, comparison or match must be `.as_posix()`.**
  `str(Path)` renders the OS-native separator — including a `Path` interpolated
  into an f-string, which calls `str()` — so an identical tree hashes
  differently on Windows.
- **A committed byte-exact fixture needs a `.gitattributes` `text eol=lf` pin**,
  or `core.autocrlf` rewrites it on checkout and every byte comparison fails on
  Windows only. `aide check` warns on the cases it can resolve; treat its
  silence as partial, not as clearance.
- **Prefer calling the function over shelling out to the command that calls
  it.** The CLI's logic is importable and returns structured data; a subprocess
  boundary adds stdout encoding, platform quirks, and a re-parse of what was
  structured a moment earlier.
- **Assert a derived value is recognisable *before* asserting anything about
  it.** A glob that matched nothing, a capture that came back empty, a slice
  taken from a failed `find()` — each yields a value that flows into the
  assertion and passes while checking nothing at all. A test that cannot fail is
  worse than no test.
- **Deterministic and cross-platform** (Windows + macOS + Linux), no network.
