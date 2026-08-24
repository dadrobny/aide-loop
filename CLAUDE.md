# CLAUDE.md — aide-loop

Project-specific notes for Claude Code. **This repo is the AIDE framework
itself**, not a project that uses it — there is no `docs/aide/`, no `aide.toml`,
no work queue here. Do not look for the loop's living documents; you are editing
the machinery that produces them elsewhere.

Start with [`README.md`](README.md) (the three-layer model, the loop, model
routing), [`docs/concepts.md`](docs/concepts.md) (the mental model), and
[`docs/vision.md`](docs/vision.md) (what the framework is for, and what it
refuses). This file holds only what an agent editing *this* repo needs and cannot
infer from the code.

## What lives where

Three layers; the first two are what a consumer installs.

| In this repo | Installed into a consumer as | What it is |
|---|---|---|
| [`core/`](core/) | `<repo>/.aide/` | The **engine** — provider-agnostic: document templates, `conventions.md`, the `aide.py` CLI, the supervisor loop |
| [`adapters/claude/`](adapters/claude/) | `<repo>/.claude/` | The **Claude adapter** — agents, skills, commands, hooks, `settings.json` |
| [`install.py`](install.py) | — | The cross-OS installer that copies both and scaffolds `aide.toml` |

Not installed, and therefore free of the version rule below:
`adapters/claude/tests/`, `adapters/ADAPTER-SPEC.md`, `adapters/*/README.md`,
`docs/`, `README.md`, `tests/`.

## The one gotcha that bites every editor

The control files under `core/` and `adapters/claude/` reference `.aide/…`,
`.claude/…`, and `python .aide/scripts/aide.py …`. **Those are consumer paths and
they are correct.** Never "fix" them to this repo's source layout (`core/…`,
`adapters/…`) — they describe the *installed* result, not where the file
currently sits. Only the repo-level docs (`README.md`, `docs/`, the adapter
READMEs, this file) describe this repo's own structure.

The same applies to relative links inside agents/skills: `../../.aide/conventions.md`
resolves correctly from `.claude/agents/` in a consumer, which is the only place
it is ever read.

## Versioning — enforced, not remembered

`core/VERSION` is the single version of a working install. **Any commit touching
`core/` or `adapters/` (minus the not-installed paths above) must bump it and add
a `CHANGELOG.md` entry** — that is exactly what `install.py --update` copies, so
a change there is a change a consumer receives. Without the bump, a consumer's
`install.py --check` reports "up to date" while running an older engine.

[`tests/test_repo_versioning.py`](tests/test_repo_versioning.py) fails the suite
when the branch diff against `main` reaches a consumer without a forward version
move, and a third test requires the version to appear in `CHANGELOG.md`. SemVer
where the "API" is what a consumer installs: patch = fix with no interface
change; minor = new verb/template/`aide.toml` key/agent/skill; major = the
consumer must edit its own files to update.

## Tests

Stdlib + pytest only — **no venv, no dependencies, no editable install**:

```
pytest                                   # whole suite (this is what CI runs)
pytest tests/test_repo_versioning.py     # the version gate alone
pytest tests/test_fixture_consumer.py    # the loop verbs against a real install
pytest core/scripts/tests/               # the aide CLI
pytest adapters/claude/tests/            # hygiene guard, settings overlay, probe
```

CI ([`.github/workflows/tests.yml`](.github/workflows/tests.yml)) runs `pytest`
on ubuntu **and** windows — the installer and the CLI both do path work, so a
POSIX-only assumption fails there and not locally. There is no linter or
formatter; `pytest` is the only gate.

Most of the suite exercises this repo's **source** layout.
[`tests/test_fixture_consumer.py`](tests/test_fixture_consumer.py) is the one
that does not: it installs into a `tmp_path`, `git init`s it, scaffolds the
minimum living documents, and drives `check`/`claim`/`scope`/`merge`/`gc`/
`status` through the engine loaded from `.aide/scripts/aide.py` — the path a
consumer executes — asserting exit codes and effects, never prose. **A change to
a verb's behaviour belongs there**, on both matrix legs.

It is still a fixture, not a project: it says the install works, not that *your*
consumer is happy. Landing a change in a real one (below) remains the last step.

## Landing a change in a consumer

The installer copies from the **local working tree**, so no push is needed to
try a change:

```
python install.py --into <consumer-repo> --update
python install.py --into <consumer-repo> --check     # writes nothing, non-zero if behind
```

`--update` re-copies engine + adapter but **never** touches the consumer's
`aide.toml` or `docs/aide/` — those are project-owned. `settings.json` is
non-clobbering by default; a consumer that has adopted
`.claude/settings.overlay.json` gets it deterministically regenerated from
framework-base + overlay instead, so it never needs manual reconciliation.

Then review the `git diff` in the consumer — it should be exactly the intended
change, since most copied files are byte-identical no-ops.

## Conventions this repo's own content must follow

- **Command hygiene** ([`core/conventions.md`](core/conventions.md) §3) is a
  contract the agent specs merely point back to. If you change the rules there,
  change [`adapters/claude/hooks/command_hygiene_guard.py`](adapters/claude/hooks/command_hygiene_guard.py)
  and the allow-list in [`adapters/claude/settings.json`](adapters/claude/settings.json)
  in the same commit — a rule the hook does not enforce is a rule that silently
  stalls an unattended run instead.
- **Template fill-in conventions**: `{{slot}}` for a literal value to substitute,
  `_italic line_` for authoring guidance to read then replace. `aide check` flags
  any `{{…}}` surviving into a consumer's `docs/aide/**`, which is why guidance
  must never be written as a slot.
- **The engine has zero Claude coupling by design.** Nothing under `core/` may
  name Claude, a Claude model, or a `.claude/` primitive. If a change needs that,
  it belongs in the adapter, and probably in
  [`adapters/ADAPTER-SPEC.md`](adapters/ADAPTER-SPEC.md) as a contract point
  every runtime must express.

## Where direction lives — three places, no overlap

[`docs/vision.md`](docs/vision.md) holds **purpose and non-goals**. The
[GitHub Project](https://github.com/users/dadrobny/projects/1) holds **order and
status**, as fields on the issues themselves. Issue bodies hold **per-item
rationale**. None of the three duplicates another — in particular, **nothing
outside the tracker records whether work is done**, so do not add a status
section, a checklist, or a "current focus" heading to any document in this repo.

Reading the Project needs network plus `gh` authenticated with the `project`
scope (`gh auth refresh -s project`); `gh project item-list 1 --owner dadrobny
--format json` is the whole interface. The board's `Wave` field is the ordering —
issues within one wave are a coherent batch, and dependencies between issues stay
as prose in their bodies, since GitHub has no native "blocks" edge.

The vision earns its keep by licensing a **close**: an issue that crosses a stated
non-goal can be closed as out of scope rather than left open forever. If a
proposal fits nowhere in it, say so in the issue — either it is out of scope, or
`docs/vision.md` is out of date and wants a PR.

## Merge policy

Work on a branch and land via a reviewed PR.
