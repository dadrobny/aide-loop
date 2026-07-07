# HANDOFF — finish extracting AIDE into this standalone repo

**Read this first.** This repo (`aide-loop`) was **bootstrapped by a clean copy**
from the `SegQC-xnat` project on 2026-07-07, executing **§6 step 2** of the
extraction plan. The mechanical copy + restructure is done and the engine tests
pass; what remains is authoring the framework-level files and dogfooding. The
governing spec is **[`docs/framework-standalone-plan.md`](docs/framework-standalone-plan.md)** —
this handoff is its task list.

**Provenance.** History lives in the origin project, `SegQC-xnat`
(github.com/dadrobny/SegQC-xnat); the in-place core/adapter split landed there as
PR #23. This repo starts fresh (no `git filter-repo`), per plan §6 step 2.

---

## Current state (what the bootstrap produced)

The three layers are now **physical** (plan §3):

```
core/          LAYER 1 — provider-agnostic engine (verbatim from .aide/, tree shape preserved)
  conventions.md · templates/ · scripts/aide.py+tests/ · loop/loop.py · VERSION
adapters/      LAYER 2
  ADAPTER-SPEC.md              the engine↔adapter contract
  claude/                      the reference adapter (agents/ skills/ commands/ hooks/ scripts/ settings.json)
    usage_probe.py             the anthropic-oauth probe (installer drops this into a consumer's .aide/loop/)
    README.md                  STUB
  copilot/ cursor/ gemini/     porting STUBS
docs/          framework-standalone-plan.md (the spec) · quickstart.md STUB · concepts.md STUB
install.py     STUB (full spec in its docstring)
README.md      SEED — a verbatim copy of the engine README; rewrite for this repo (task E)
```

**Verification baseline:** `python -m pytest core/scripts/tests -q` → **50 passed.**
(Core is stdlib-only; only pytest is needed. Make a `.venv` and `pip install pytest`.)

---

## ⚠️ The one gotcha that will bite you

The copied **adapter control files (`adapters/claude/{agents,skills,commands}`) and
`core/conventions.md` reference `.aide/…`, `.claude/…`, and
`python .aide/scripts/aide.py`. Those are *consumer* paths — the layout that
`install.py` materialises in a target repo — and are CORRECT. Do NOT rewrite them
to `core/…` / `adapters/…`. The framework repo's own structure (`core/`,
`adapters/`) is the *source*; the paths in the control files describe the
*installed* result. Only the repo-level docs you author (README, quickstart,
concepts, adapter README) describe this repo's own structure.

---

## Tasks (roughly in order)

- **A. Relocate the adapter-conformance test.** The "shipped Claude probe exposes
  `get_usage()`" test was removed from `core/scripts/tests/test_loop.py` (it
  asserts probe/loop co-location, a consumer-only invariant — see the NOTE there).
  Give it an adapter/installer home (e.g. `adapters/claude/tests/` or an
  `install.py` dogfood check that installs then imports the co-located probe).

- **B. Author `adapters/claude/README.md`** — the AIDE-concept → Claude-Code-primitive
  map (skills = the seven entry-points, agents = the five role tiers, commands =
  the three orchestrators, `settings.json` = permission model, `usage_probe.py` =
  the `anthropic-oauth` probe). Plan §3, §4.1.

- **C. Split `core/conventions.md` §3 (command hygiene)** per plan §4.3: the
  "permission allow-list" framing is Claude-specific → move it into the Claude
  adapter README (task B); `core/conventions.md` keeps only the runtime-general
  rules (one command per call, no `cd`, no chained `&&`, no `2>&1`).

- **D. Write `install.py` + `--update`.** Full spec is in the stub's docstring
  (plan §3.1). Stdlib-only, cross-OS, **non-clobbering** on `settings.json`
  (emit a `.aide-merge` diff), records `VERSION` in the scaffolded `aide.toml`,
  and `--update` never touches `docs/aide/` or `aide.toml`.

- **E. Rewrite `README.md`** for this repo: the three-layer model, the install
  command, the loop, model/tier routing, the merge policy. The seed is the old
  in-tree engine README — keep the good prose, fix every `.aide/`/`.claude/`
  reference to the new repo structure, and link provenance back to SegQC-xnat.

- **F. Fill `docs/quickstart.md` and `docs/concepts.md`** (stubs).

- **G. Porting stubs** (`adapters/{cursor,gemini}/README.md`, `adapters/copilot/`)
  are seeded. Copilot is the second *real* adapter but is **explicitly future
  work** (plan §4.2) — after SegQC becomes a consumer. Leave as stubs for now.

- **H. Add a `LICENSE`** (owner's choice).

- **I. Dogfood (plan §6 step 3).** `python install.py --adapter claude --into <scratch-repo>`,
  then run `aide check` + one item end-to-end in the scratch repo to prove a
  working install. Consider a smoke test in CI.

- **J. Commit + push.** `origin` (github.com/dadrobny/aide-loop) is empty — the
  first push seeds `main`. This whole extraction is the reviewable unit.

### Then, separately — plan §6 step 4 (back in SegQC-xnat, not here)

Convert SegQC-xnat into the **first consumer**: replace its in-tree `.aide/` and
`aide-*` `.claude/` with an `install.py --update` materialisation pinned to this
repo's `VERSION`; confirm the full suite + `aide check` still green. That PR is
the acid test that extraction preserved a working install. Reversible until it
merges.

---

## Minor notes

- `core/loop/loop.local.toml.example` defaults `usage_probe = "anthropic-oauth"`
  (Claude-flavoured) although it sits in `core/`. Consider neutralising the core
  example to `"none"` and letting the Claude adapter document the override — minor
  layering tidy, your call.
- `install.py` copies `adapters/claude/usage_probe.py` → `<target>/.aide/loop/`,
  which is what makes `core/loop/loop.py`'s sibling-import of the probe resolve in
  a consumer. Keep that mapping (it's the seam from plan §4.4).
