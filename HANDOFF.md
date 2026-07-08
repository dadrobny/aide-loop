# HANDOFF — extracting AIDE into this standalone repo

**Status: the framework build-out is complete and committed; only the initial
`git push` and the follow-on (making SegQC-xnat a consumer) remain.** This repo
(`aide-loop`) was bootstrapped by a clean copy from `SegQC-xnat` on 2026-07-07
(plan §6 step 2); the framework-level files (installer, adapter docs, framework
README, quickstart/concepts, LICENSE) have since been authored and dogfooded. The
governing spec is **[`docs/framework-standalone-plan.md`](docs/framework-standalone-plan.md)**.

**Provenance.** AIDE originates as an MIT-licensed Spec Kit extension by mnriem
(github.com/mnriem/spec-kit-extensions); it was then developed in-tree in
`SegQC-xnat` (github.com/dadrobny/SegQC-xnat), where the core/adapter split landed
as PR #23. This repo starts fresh (no `git filter-repo`), per plan §6 step 2.

**Verification baseline:** `python -m pytest -q` → **53 passed** (50 engine + 3
adapter/installer; `pytest.ini` sets `testpaths = core adapters`). Core is
stdlib-only; only pytest is needed.

---

## The one gotcha (still true — keep in mind for future edits)

The adapter control files (`adapters/claude/{agents,skills,commands}`) and
`core/conventions.md` reference `.aide/…`, `.claude/…`, and
`python .aide/scripts/aide.py`. Those are *consumer* paths — the layout that
`install.py` materialises in a target repo — and are CORRECT. Do NOT rewrite them
to `core/…` / `adapters/…`. The framework repo's own structure (`core/`,
`adapters/`) is the *source*; the paths in the control files describe the
*installed* result. Only the repo-level docs (README, quickstart, concepts, adapter
README) describe this repo's own structure.

---

## Completed

- **A ✅ Adapter-conformance test** — the shipped-probe `get_usage()` check plus the
  installer co-location invariant live in
  [`adapters/claude/tests/test_usage_probe.py`](adapters/claude/tests/test_usage_probe.py).
- **B ✅ `adapters/claude/README.md`** — the AIDE-concept → Claude-Code-primitive map
  (skills = entry-points, agents = role tiers, commands = orchestrators,
  `settings.json` = permission model, `usage_probe.py` = the `anthropic-oauth` probe).
- **C ✅ `core/conventions.md` §3 split** — keeps only the runtime-general command
  hygiene; the permission allow-list shaping moved into the Claude adapter README.
- **D ✅ `install.py` + `--update`** — stdlib-only, cross-OS, non-clobbering on
  `settings.json` (emits a `.aide-merge` diff), records `VERSION`; `--update` never
  touches `docs/aide/` or `aide.toml`.
- **E ✅ `README.md`** — rewritten for this repo (three-layer model, install, the
  loop, tier routing, merge policy) with provenance to the upstream extension.
- **F ✅ `docs/quickstart.md` and `docs/concepts.md`** — authored from stubs.
- **H ✅ `LICENSE`** — MIT (© David Drobny) with the mnriem derivation notice.
- **I ✅ Dogfood (mechanical seam)** — `install.py` into a scratch repo, then
  `aide check` + one item claimed→built→merged end-to-end, all green; the installed
  engine suite passes in place. *(The LLM-driven skills/agents still need a live
  Claude Code session to exercise — see below.)*

## Remaining

- **J — push.** The framework work is committed to `main`; `origin`
  (github.com/dadrobny/aide-loop) is empty, so the first push seeds `main`. This
  whole extraction is the reviewable unit.
- **G — porting stubs** (`adapters/{cursor,gemini}/README.md`, `adapters/copilot/`)
  are left as stubs. Copilot is the second *real* adapter but is **explicitly future
  work** (plan §4.2) — after SegQC becomes a consumer.
- **Full end-to-end dogfood** — exercise a real item through the actual skills/agents
  (spec-author → test-writer → builder → validator) in a Claude Code session, and
  consider a CI smoke test of the mechanical flow (task I proved that headlessly).

### Then, separately — plan §6 step 4 (back in SegQC-xnat, not here)

Convert SegQC-xnat into the **first consumer**: replace its in-tree `.aide/` and
`aide-*` `.claude/` with an `install.py --update` materialisation pinned to this
repo's `VERSION`; confirm the full suite + `aide check` still green. That PR is the
acid test that extraction preserved a working install. Reversible until it merges.

---

## Minor notes

- `core/loop/loop.local.toml.example` defaults `usage_probe = "anthropic-oauth"`
  (Claude-flavoured) although it sits in `core/`. **Still open (optional):** consider
  neutralising the core example to `"none"` and letting the Claude adapter document
  the override — minor layering tidy.
- `install.py` copies `adapters/claude/usage_probe.py` → `<target>/.aide/loop/`,
  which is what makes `core/loop/loop.py`'s sibling-import of the probe resolve in a
  consumer (the seam from plan §4.4). This mapping is load-bearing — keep it.
