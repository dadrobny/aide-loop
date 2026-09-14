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
| [`core/`](core/) | `<repo>/.aide/` | The **engine** — provider-agnostic: document templates, `conventions.md` + `conventions/`, the `aide.py` CLI, the supervisor loop |
| [`adapters/claude/`](adapters/claude/) | `<repo>/.claude/` | The **Claude adapter** — agents, skills, commands, rules, hooks, `settings.json` |
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

The same applies to relative links inside agents/skills and rules: a path like
`.aide/conventions/6-test-hygiene.md` resolves in a consumer, which is the only
place it is ever read.

## The contract is sectioned, and delivered

[`core/conventions.md`](core/conventions.md) is an **index**. Each numbered
section is one file under [`core/conventions/`](core/conventions/), so `§6` is
`conventions/6-test-hygiene.md` and `§1 → insights.md` is
`conventions/1-format-contract/insights.md`. Write pointers as `§N` — the form
is used in a hundred places, it survives a file being renamed, and the index
resolves it.

**Every section reads core first, then a closing `Rationale` heading** (one
level below the file's own heading; issue #122). The core is the rule, its
shape examples and its disambiguators — what an agent that reads only it needs
to decide every case; the tail is the defect that earned a rule, the
counterfactual and the rejected alternative. Add a rule to the core and its
provenance to the tail, in the same commit. The test for which side a sentence
belongs on is #78's: would an agent that never saw it make a *different
decision*? No → tail. Unsure → it is a disambiguator; core. A pinned sentence
is core by definition, so a delivered file's pins should never point below the
heading. The style the seventeen share — opener, bullet grammar, `Rationale`
as `- **Why X.**` bullets, the consumer annotation, verb mechanism in
`-h` (pinned to the code in `core/scripts/tests/test_aide_help_pins.py`) —
is stated once, in `conventions.md` after its index table (issue #186); a
new or reshaped section follows it rather than the file next to it.

**Which copies of engine text exist, and what each one gets, is decided once —
in [`adapters/ADAPTER-SPEC.md`](adapters/ADAPTER-SPEC.md), its unnumbered
*Copies of engine text* section** (issue #205). Point, generate, quote-pin, or
leave advisory; and for a pinned copy, whether the pins live in the copy or in
the test module, decided by whether the copy's bytes reach a reader unstripped. Do not re-argue it here or at the site of a new copy:
read it, then add the copy's row to
[`docs/copies-of-engine-text.md`](docs/copies-of-engine-text.md) in the same
commit. The rest of this section is what an agent editing *this* repo needs on
top of that rule — which file is which, and which test fails when.

**Sections are runtime-general; an adapter delivers them, it does not restate
them.** The Claude adapter's **delivered files** are the one unscoped rule in
[`adapters/claude/rules/`](adapters/claude/rules/) (§3; loads in every session
and every sub-agent) and the eight **section skills** in
`adapters/claude/skills/`: `user-invocable: false`, never a command, preloaded
at spawn into exactly the agent specs whose `skills:` frontmatter names them.
Since 1.46.0 (issue #109) the set is keyed by **which document a role writes**,
one skill per distinct reach set, never one section across two skills — which
is what lets a section core be emitted whole:
`aide-document-format` (§1 index + status icons → the three roles that write a
shape-parsed document), `aide-human-gates` (§1 → human gates → the two that
raise one), `aide-progress-file`, `aide-queue-and-inbox`, `aide-item-specs`
(§1 → items, authorised paths, environment-gated capabilities; §5),
`aide-off-platform-verification` (§7), `aide-test-hygiene` (§6) and
`aide-review-and-validation` (§9). A `paths:` block on a skill injects nothing on a read —
the description is in an interactive session's listing regardless, and the
globs only narrow when the runtime auto-invokes it — so the loop's delivery is
the preload alone, and there is deliberately no
`paths:`-scoped rule left (one fires inside sub-agents too; issue #85 has the
numbers). Three obligations, pinned by
[`adapters/claude/tests/test_rules.py`](adapters/claude/tests/test_rules.py)
over rules and section skills alike and stated in `ADAPTER-SPEC.md` §7 — a
delivered file loads without the role choosing to, names the section it
delivers, and **adds no rule the engine does not have**. A rule invented in the
adapter binds one runtime and is invisible to every other; put it in
`conventions/` first. A new section skill is recognised structurally by
`user-invocable: false` alone, must be preloaded by at least one agent, and must
not set `disable-model-invocation` — the runtime silently refuses to preload
such a skill. A `<!-- pins:` block does **not** make one: a *workflow* skill may
pin too (`aide-create-queue` and `aide-review-insights` both carry the §1 routing
table), and `test_rule_pins.py` checks those quotes in both directions exactly as
it checks a delivered file's — it just does not *require* them there. The key and
the preload channel are held together from the other side, by
`test_every_skill_an_agent_preloads_is_a_section_skill`.

**Four of them are generated, and are therefore not restatements at all**
(1.47.0, #109's PR 2). A delivered file that declares `<!-- generated-from:
.aide/conventions/<file>.md -->` is written by `install.py` as its own text —
frontmatter and whatever the *adapter* has to say about delivering the
section, its test declarations stripped — followed by that section's core, everything
above the `Rationale` heading, **verbatim**: `rules/aide-command-hygiene.md`
(§3), `aide-test-hygiene` (§6), `aide-off-platform-verification` (§7) and
`aide-review-and-validation` (§9). Nothing is reflowed, re-headed or trimmed,
so a section that reads wrongly when delivered whole is a section to fix, never
a wrapper to fix. Which files are generated rather than hand-written is rung 2
of the copies rule; the five §1 skills sit on the other side of it, their cores
1.5–2.8× the copies. The source tree holds no generated body: it holds the
file with the declaration in it, which is why the four still read as
delivered files here. The grammar lives in `install.py` (the installer applies
it inside a consumer, where `tests/` does not exist);
[`adapters/claude/tests/test_generated_delivery.py`](adapters/claude/tests/test_generated_delivery.py)
asserts the render is the adapter's half plus the core byte for byte and that
an edit to the section reaches the delivered copy,
[`tests/test_install_generated.py`](tests/test_install_generated.py) holds the
installer half, and a section that cannot be rendered **aborts the install**
(exit 4) before the first write — every generated file is rendered up front,
so the target is untouched rather than three files into an update.

That reading is **written once**, in
[`tests/_delivered.py`](tests/_delivered.py) — the frontmatter grammar, the
section-skill recogniser, the `paths:`/`skills:` readers, and pointers at
`install.py`'s reading of "generated" — and the four modules that check
delivered files import it (issue #113). Four hand copies drifted the one time
the rule moved (1.42.0), so a change to the recognition rule or the frontmatter
grammar is now one edit, and the modules only say which reading of a BOM they
want.

Each delivered file also declares, in a `<!-- reach: … -->` comment near the
top of its body, the agent roles it expects to reach — `all`, or a
comma-separated list.
[`tests/test_structural_budget.py`](tests/test_structural_budget.py) installs
the adapter, reads that declaration from the **source** file (1.49.3 strips it
on the way in, below) and fails when the declaration and the carrier disagree: for a
rule, its `paths:` globs evaluated against each role's read-set derived from
the agent specs; for a section skill, **literally** the set of specs whose
`skills:` list it, plus a `<!-- triggers: … -->` line naming the roles whose
reads match its `paths:` (the interactive half, kept under test — `none` is a
legal answer there and only there, for a section about no document the loop
writes: `aide-off-platform-verification`). **Changing a rule's globs or a spec's `skills:` changes a
reach**, so update the declaration in the same commit. That module also pins
the always-on floor (`AGENT-CONTEXT.md` plus every unscoped rule; a section
skill is not part of it) byte-for-byte — it fails in both directions on
purpose, and moving it means bumping `VERSION` and editing the pin
deliberately. What it costs it still reads from the install; only the
declaration comes from source, and the equality that keeps those one claim —
installed file == source minus the declarations, plus the core for a generated
one — is asserted in the same module.

**None of the three declarations ships** (issue #205, 1.49.3). `pins`, `reach`
and `triggers` address this repository's suite, which a consumer does not
install, so `install.py` strips them from every markdown control file it
writes — hand-written at copy time, generated before the core is appended
(`strip_declarations`; the edges are
[`tests/test_install_strips_declarations.py`](tests/test_install_strips_declarations.py)).
Only those three openers, and only where one opens a line: a comment written
for the *reader* survives, and a prose mention of the grammar is prose.
`generated-from` is deliberately kept — an instruction to the installer rather
than an assertion, and the one line saying the installed body is generated and
from where. So write a declaration as a block at the start of a line, and
write it in `adapters/claude/`, which is the only tree it lives in.

And each **hand-written** delivered file **quotes the statements it delivers**,
in `<!-- pins: <section file> … -->` blocks — one block per section, each `- `
line a sentence lifted from it (rung 3 of the copies rule, with the blocks in
the copy because the channel the file is shipped through — the preload — strips
them, and because since 1.49.3 they do not leave this repository at all).
[`adapters/claude/tests/test_rule_pins.py`](adapters/claude/tests/test_rule_pins.py)
asserts every pin still appears in the delivered file *and* in the section it
names, after a normalisation that absorbs reflow, emphasis and case but nothing
else. **Both directions**: a file reworded away from its section fails, and so
does a section rewritten under a file that still quotes the old wording — edit
both copies, in one commit. Every delivered file must pin at least one
statement; one that delivers no normative engine statement is a question, not
an exemption. A **generated** file declares no pins and fails the suite if it
grows one — the mechanism guards a restatement, and there is none there.

The engine's own always-on page is a restatement too, and is pinned the same
way from the other side of the boundary:
[`tests/test_floor_pins.py`](tests/test_floor_pins.py) holds sentences of
`core/AGENT-CONTEXT.md` to the **core** of the section their heading names
(issue #194) — so far the read-cold block alone; the page's other eight headings
are unpinned until someone reconciles their wording and adds an entry. Its pins
live in that module's `FLOOR_PINS`, **not** in a comment on the page: an
instruction-file import is the unstripped side of the copies rule's placement
criterion — the page's designed reader gets the bytes whole — and the page is
that criterion's worked case. Rewording a pinned sentence on either side means
editing the page, the section and `FLOOR_PINS` together.

Do not re-inline a contract restatement into an agent spec. Six of them carried
the command-hygiene block verbatim, one had already drifted, and a test now
fails if the heading comes back. Same shape, same guard, for the `## Hand-off`
tail seven skills carried (issue #161): the loop sequence lives in
[`core/README.md`](core/README.md), the fresh-session rationale in
`AGENT-CONTEXT.md`, and `test_rules.py` fails if the heading returns to any
skill.

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
pytest                                   # whole suite (the ubuntu CI leg runs exactly this)
pytest tests/test_repo_versioning.py     # the version gate alone
pytest tests/test_fixture_consumer.py    # the loop verbs against a real install
pytest tests/test_install_generated.py   # the generator, and an install of it
pytest core/scripts/tests/               # the aide CLI
pytest adapters/claude/tests/            # hygiene guard, settings overlay, probe
```

CI ([`.github/workflows/tests.yml`](.github/workflows/tests.yml)) runs `pytest`
on ubuntu **and** windows — the installer and the CLI both do path work, so a
POSIX-only assumption fails there and not locally. The windows leg is split
into one job per group of `pytest.ini` testpaths roots (subprocess spawns cost
~13x there; issue #74), and `tests/test_ci_shards.py` pins the shards to
exactly cover testpaths. There is no linter or formatter; `pytest` is the only
gate.

Most of the suite exercises this repo's **source** layout.
[`tests/test_fixture_consumer.py`](tests/test_fixture_consumer.py) is the one
that does not: it installs into a `tmp_path`, `git init`s it, scaffolds the
minimum living documents, and drives `check`/`claim`/`scope`/`merge`/`gc`/
`status` through the engine loaded from `.aide/scripts/aide.py` — the path a
consumer executes — asserting exit codes and effects, never prose. **A change to
a verb's behaviour belongs there**, on both matrix legs.

It is still a fixture, not a project: it says the install works, not that *your*
consumer is happy. Landing a change in a real one (below) remains the last step.

The three suites share exactly one module,
[`tests/_delivered.py`](tests/_delivered.py) (above), reached the way `install`
already is: the importing module puts `tests/` on `sys.path` itself, since
there is no `conftest.py` anywhere in this repo and adding one would make the
dependency invisible. It parses and never asserts — pytest rewrites assertions
in test modules only, and these functions run at collection time — so it
returns `None` or an empty list and the caller decides what that means. Its two
readers differ in one thing, and the difference is deliberate:
`tests/test_structural_budget.py` takes `REFUSES_BOM` because it must see the
frontmatter *the runtime* sees; everything else takes `STRIPS_BOM` to report on
the file behind a BOM.

## Landing a change in a consumer

The installer copies from the **local working tree**, so no push is needed to
try a change:

```
python install.py --into <consumer-repo> --update
python install.py --into <consumer-repo> --check     # writes nothing, non-zero if behind
```

`--update` re-copies engine + adapter — re-*rendering* the four generated
delivered files, so a `conventions/` edit reaches them with no second edit — but
**never** touches the consumer's `aide.toml` or `docs/aide/`, which are
project-owned. `settings.json` is
non-clobbering by default; a consumer that has adopted
`.claude/settings.overlay.json` gets it deterministically regenerated from
framework-base + overlay instead, so it never needs manual reconciliation.
Files the framework has dropped are removed: `.aide/` by comparison with
`core/`, and the adapter's control directories (`.claude/agents/`, `skills/`,
`rules/`, …) only by the manifest of what the installer itself wrote,
`.aide/adapter-manifest.txt` — a consumer's own files there are never recorded,
so never touched. A file retired from `adapters/claude/` therefore also goes
into `RETIRED_ADAPTER_PATHS` in `install.py`, for consumers installed before
the manifest existed; a control directory retired whole leaves `ADAPTER_CONTROL`
only by moving into `HISTORIC_CONTROL_DIRS`, never by deletion.

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
  must never be written as a slot. A template states shapes and that guidance
  and **nothing else**, in its header comment *and* in the italic guidance
  below it: since 1.49.5 (headers) and 1.49.6 (bodies), two tests in
  [`tests/test_template_conventions.py`](tests/test_template_conventions.py)
  fail when either shares a ten-word run with a `conventions/` section core or
  a verb's `-h`, so a rule stated there belongs in the section and mechanism
  at `aide <verb> -h` — point, do not copy. A header says what the artifact is
  and how to interact with it; whatever is stated elsewhere is a pointer.
- **The engine has zero Claude coupling by design.** Nothing under `core/` may
  name Claude, a Claude model, or a `.claude/` primitive. If a change needs that,
  it belongs in the adapter, and probably in
  [`adapters/ADAPTER-SPEC.md`](adapters/ADAPTER-SPEC.md) as a contract point
  every runtime must express.

## Where direction lives — three places, no overlap

[`docs/vision.md`](docs/vision.md) holds **purpose and non-goals**. The
[GitHub Project](https://github.com/users/dadrobny/projects/1) holds **status and
grouping**, as fields on the issues themselves. Issue bodies hold **per-item
rationale**. None of the three duplicates another — in particular, **nothing
outside the tracker records whether work is done**, so do not add a status
section, a checklist, or a "current focus" heading to any document in this repo.

Reading the Project needs network plus `gh` authenticated with the `project`
scope (`gh auth refresh -s project`); `gh project item-list 1 --owner dadrobny
--format json` is the whole interface. Two fields carry meaning: **Status**
(Todo / In Progress / Done) and **Theme** (the concern an issue belongs to).

**There is deliberately no priority or ordering field.** A `Wave` one existed and
was dropped: it encoded the ordering of a single initial batch, mixed three
different axes (sequence, dependency role, kind of work), and went meaningless
the moment that batch finished — every non-deferred wave reached 100% Done, so
the next issue filed had no honest wave to enter. Its descriptive half duplicated
`Theme`. Do not re-add one without a reason that survives the batch it was
invented for.

**Scheduling is carried by the `deferred` label alone**: an open issue without it
is fair game, an open issue with it is recorded and deliberately not scheduled
(and its title says so too). Dependencies between issues stay as prose in their
bodies, since GitHub has no native "blocks" edge.

The vision earns its keep by licensing a **close**: an issue that crosses a stated
non-goal can be closed as out of scope rather than left open forever. If a
proposal fits nowhere in it, say so in the issue — either it is out of scope, or
`docs/vision.md` is out of date and wants a PR.

The recurring pass over that tracker — version-check newly-raised consumer
issues against `CHANGELOG.md` and HEAD, file them into the Project with `Theme`
and labels, order the board, sweep the deferred pile, and propose the next PR's
worth — is [`/triage-issues`](.claude/skills/triage-issues/SKILL.md). It is
repo-local (`.claude/` is never installed), so it is outside the version rule.

## Merge policy

Work on a branch and land via a reviewed PR — opened as a **draft**, with the
review folded in before it is marked ready.

The review contract — severity, what to check, what never to flag — is
[`REVIEW.md`](REVIEW.md). Copilot code review and Claude Code Review read it
(and this file) natively; Codex applies it through the Code Review Rules
section of [`AGENTS.md`](AGENTS.md); a **local** `/code-review` subagent reads
only CLAUDE.md, so hand it `REVIEW.md` in the prompt. Keep the three files
from drifting: `AGENTS.md` restates only `REVIEW.md` highlights, and nothing
here restates either.

Reviewer routing — request **both** external reviewers on the draft PR (their
quotas and blind spots are independent), fall back to Claude only when those
quotas are expired:

| Reviewer | Trigger | Model / effort |
|---|---|---|
| Copilot code review | GraphQL `requestReviews` mutation with `botIds` — the REST reviewers endpoint returns 200 and silently does nothing. This repo's bot node ID: `BOT_kgDOCnlnWA`. Verify via the timeline API (`issues/<PR#>/timeline` — PRs are issues there), not `requested_reviewers` | GitHub-managed; not configurable per repo |
| Codex cloud review | comment `@codex review` on the PR (needs the Codex GitHub connector enabled for the repo) | account-side setting, default `gpt-5-codex`; per-repo tuning only via `AGENTS.md` rules |
| Claude review subagent | `/code-review high <PR#>` — **quota-expired fallback** | Sonnet at `high`; cap at two rounds, round two re-asks the same agent "is the fix complete" and hunts regressions the fix introduced |

`/code-review ultra` (multi-agent cloud review, billed) is user-triggered
only — never launched by an agent on its own.
