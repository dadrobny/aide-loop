# Claude Code adapter (reference implementation)

The reference AIDE adapter: it drives the provider-agnostic engine (`../../core/`)
from **Claude Code**. Where [`../ADAPTER-SPEC.md`](../ADAPTER-SPEC.md) states the
*contract* every adapter fulfils in the abstract (seven entry-points, five roles on
capability tiers, three orchestrators, the shared CLI, an optional permission policy
and usage probe), this README is the concrete **AIDE-concept → Claude-Code-primitive
map**: which file expresses each contract point, and how the tiers bind to Claude
models.

`install.py --adapter claude` copies this directory into a consumer:

| Source (here) | Installed to | Role |
|---|---|---|
| `agents/` `skills/` `commands/` `rules/` `hooks/` `scripts/` `settings.json` | `<repo>/.claude/` | the Claude harness |
| `usage_probe.py` | `<repo>/.aide/loop/usage_probe.py` | the loop's usage seam (co-located with the engine `loop.py`) |
| `default-context.json` | — | not installed; declares the instruction file and import syntax `install.py` uses to link `.aide/AGENT-CONTEXT.md` |
| `README.md` (this file) | — | not installed; documents the adapter |

Everything mechanical (recon/claim, progress reconciliation, queue tidy, merge,
env, the consistency check) is **not** re-implemented here — it is the engine CLI,
invoked identically by every adapter as `python .aide/scripts/aide.py {check,
progress, queue, claim, merge, env, sync, gc, status}` ([spec §4](../ADAPTER-SPEC.md)). The files
below only translate the *human-shaped* work into Claude Code's primitives.

---

## Entry-points → **skills** (`skills/aide-*/SKILL.md`)

The spec's seven workflow steps are expressed as Claude Code **skills** — each a
scoped, invocable unit (`/aide-create-vision`, …) that reads and writes the
documents in the exact shapes `conventions.md` §1 fixes.

| Spec step | Skill |
|---|---|
| 1 · create-vision | `aide-create-vision` |
| 2 · create-roadmap | `aide-create-roadmap` |
| 3 · create-progress | `aide-create-progress` |
| 4 · create-queue | `aide-create-queue` |
| 5 · create-item | `aide-create-item` |
| 6 · execute-item | `aide-execute-item` |
| 7 · feedback-loop | `aide-feedback-loop` |

Three skills go **beyond the seven** — Claude-specific conveniences, not new
contract obligations:

- **`aide-spec-queue`** — a batch variant of step 5: author specs for *every*
  unspecced item in a queue on one branch, interactively, front-loading the human so
  execution can then run unattended.
- **`aide-review-insights`** — step 7's inbox triage, spun out of the feedback loop
  so the pass that always runs at a queue boundary can be reached without the
  retrospective around it. It routes by the §1 routing table, judges duplicates and
  decayed premises, and files `framework` entries as issues.
- **`aide-status-report`** — an auxiliary reporter: an evolving HTML status summary
  from the AIDE documents, test suite, and QC outputs. Not part of the loop.

## Roles → **agents** (`agents/*.md`), tiers bound to Claude models

The five roles ([spec §2](../ADAPTER-SPEC.md)) are Claude Code **sub-agents** —
fresh, role-scoped instances with `model:`/`effort:` frontmatter. The contract names
capability *tiers*; this adapter binds **T3 → Opus, T2 → Sonnet**:

| Role (`agents/…`) | Tier | `model:` | `effort:` |
|---|---|---|---|
| `queue-planner` | T3 | `opus` | `xhigh` |
| `spec-author` | T3 | `opus` | `high` |
| `test-writer` | T2 | `sonnet` | `medium` |
| `builder` | T2 (escalates to Opus on a late retry) | `sonnet` | `medium` |
| `validator` | T2 | `sonnet` | `medium` |

Recon/claim is **not** an agent — it is deterministic `aide claim`, so no `agents/`
file and no tier. No role signs off its own work; each item gets a fresh instance.

One further agent sits **outside** the five item roles, at the queue boundary:

| Agent | Tier | `model:` | `effort:` | When |
|---|---|---|---|---|
| `spec-reviewer` | T3 | `opus` | `high` | once per queue, after `/aide-spec-queue` authors every spec and **before any is built** |

It is not a sixth role — it never touches one item's lifecycle. It reads the
whole batch at once and reports the cross-item conflicts `aide check --queue`
cannot decide, because they turn on what a criterion *means*. It reviews only:
every finding is handed to the human, who decides which side was wrong.

## Orchestrators → **commands** (`commands/aide-*.md`)

The three nested drivers (item ⊂ queue ⊂ roadmap, [spec §3](../ADAPTER-SPEC.md)) are
Claude Code **slash-commands**; Claude loads the role agents as sub-agents within one
session, so the nesting is real, not a manual runbook.

- **`aide-run-item`** — one claimed item end-to-end: spec-author → test-writer →
  builder → validator+merge, with a ≤`loop.validation_rounds` build↔validate cycle.
- **`aide-run-queue`** — `aide claim` each item, `aide-run-item` it, until the queue
  empties. Does **not** create the next queue.
- **`aide-run-roadmap`** — generate a queue → run it → generate the next, until the
  roadmap is exhausted. Each new queue lands via a **human-reviewed PR** — the batch
  checkpoint, one review per ~10 items. This is also the loop supervisor's default
  command (see the usage probe below).

Two more commands are not orchestrators: **`aide-review-permissions`** belongs to
the permission model below, and **`aide-review-instructions`** to the delivery
instrumentation beside it.

The `/aide-*` entry-points can be launched from the IDE extension, the
interactive CLI, or the loop supervisor's top-level `claude -p` — these surfaces
differ in cwd behaviour, permission-ask handling, and session lifetime. The
differences, the unattended permission posture, and the trusted-folder caveat
are recorded in **[`execution-surfaces.md`](execution-surfaces.md)** — read it
before the first unattended run.

## Permission model → **`settings.json`** + **`hooks/`** (Claude-specific)

This is [spec §5](../ADAPTER-SPEC.md) — **optional**, provided only because Claude
Code *has* a permission model; a runtime without one omits all of it and relies on
the hygiene rules being followed. The **command-hygiene rules themselves** are
runtime-general and live in `core/conventions.md` §3 — stated there, not
summarised here; only the **enforcement mechanism** and the **"permission
allow-list" framing** are adapter-local and documented here.

- **`settings.json`** — the allow/ask policy: a pre-approved **allow-list** (~60
  entries: reads, greps, the safe git verbs, `python .aide/scripts/aide.py …`, scoped
  `Edit`/`Write` under `docs/aide/`, `src/`, `tests/`) and an **ask-list** (~30
  entries gating the irreversible/outward-facing: `git push --force`, `gh pr
  create|merge`, edits to `.aide/**`, `CLAUDE.md`, `aide.toml`, the `.claude/`
  control files). `defaultMode` is `default`. The allow-list is what lets an
  unattended run proceed without stalling on a prompt; the ask-list is where a human
  stays in the loop. The write-scope entries (`Edit`/`Write` under `src/**` and
  `tests/**`) are **templated from `aide.toml`** at install time — `install.py`
  rewrites them to the project's `project.source_dir`/`project.tests_dir` (read via
  the engine's own config loader, so both interpret `aide.toml` identically). A
  consumer whose code lives in `lib/` and tests in `spec/` gets `Write(lib/**)` /
  `Write(spec/**)` automatically, with no manual override; the defaults leave the
  committed file byte-identical.
- **`settings.overlay.json`** — project-owned customisation, reconciled
  **deterministically** on every `install.py`/`--update`. While this file exists,
  `settings.json` is REGENERATED as `merge(framework base, overlay)` — so edit the
  overlay, never `settings.json` (edits there are overwritten). The merge algebra:
  objects deep-merge (overlay wins); **list** values (the `allow`/`ask`/`deny`
  lists, hook groups) take a `{ "add": [...], "remove": [...] }` operator —
  *additive by default*, so a framework update that adds a new default still reaches
  the project; a plain list replaces outright (escape hatch). Prefer adding to
  `deny` over removing from `allow` when tightening (deny is explicit and
  update-proof). A stale `remove` pin warns (never blocks); a malformed overlay
  aborts the install *before* any write, so a broken `settings.json` is never
  emitted. A fresh install scaffolds an inert `settings.overlay.json.example`.
  **Backward compatible:** with no overlay, an existing `settings.json` is still
  never clobbered — the framework's version is emitted as a `.aide-merge` diff that
  now also carries a **ready-to-adopt overlay** derived from your existing file
  (`derive_overlay`, the inverse of the merge). Save that block as
  `settings.overlay.json` and the migration is done in one step — no hand-merging.
  **Scope:** `settings.json` is the only JSON file the framework installs, so it is
  the only overlay target today; the merge engine is file-agnostic JSON and extends
  to any future framework-owned JSON with no new code. It does **not** apply to the
  Markdown control files (`agents/`, `skills/`, `commands/`, `rules/`) or the Python hooks —
  those are framework-owned wholesale, and a project diverges through its own seams
  (`CLAUDE.md`, `docs/aide/`, `aide.toml`), not by editing installed framework files.
- **`hooks/command_hygiene_guard.py`** — a `PreToolUse` hook on `Bash` that *enforces*
  the `conventions.md` hygiene contract: a reshapeable command that would otherwise
  miss the allow-list and stall the run is bounced back to be re-issued in an
  allow-listed shape, rather than hanging on a prompt.
- **`hooks/log_permission_event.py`** — `PreToolUse` + `PostToolUse` logging of
  prompt-eligible calls (`Bash`/`Edit`/`Write`/`Web…`) to
  `docs/aide/permissions/log.jsonl`; the request/completion pair lets a reviewer infer
  grant vs deny. It never replicates the allow-list.
- **`hooks/log_instructions_loaded.py`** + **`scripts/review_instructions.py`** +
  the **`aide-review-instructions`** command — `InstructionsLoaded` logging to
  `docs/aide/instructions/log.jsonl`, the report over it, and the command that
  runs the report, judges each silent rule and rotates the log. This is how the
  §7 delivery contract stays checkable: a `paths:`-scoped rule whose globs stop
  matching is silently inert, and `review_instructions.py --strict` is the thing
  that says so — by hand, over a log known to cover the rule's work, never as a
  CI gate, since the log cannot know which sessions *should* have armed a rule.
- **`scripts/review_permissions.py`** + the **`aide-review-permissions`** command —
  aggregate that log into recurring bottlenecks and propose safe, recurring prompts to
  promote into the allow-list. The human makes the final allow/ask/leave call and the
  actual edit; the script only recommends.

**Allow-list command shaping.** The allow-list matches a command **prefix** and
auto-approves a compound only if *every* part matches — so beyond the runtime-general
hygiene in `conventions.md` §3, this adapter needs commands emitted in the shape the
matcher recognises, or an unattended run stalls on a prompt. These shapes are
delivered to every session and sub-agent by `rules/aide-command-hygiene.md`,
not restated per agent:

- **Recon via the Bash tool with `grep`** (`git branch -r | grep aide/`), never the
  PowerShell tool / `Select-String` — only `Bash(...)` rules are allow-listed.
- **Python/pytest via the venv in relative form** — `.venv/Scripts/python …` (Windows)
  or `.venv/bin/python …`, not an absolute path or the PowerShell call operator: only
  the relative prefix is allow-listed.
- **The `aide` CLI** as `python .aide/scripts/aide.py <cmd>` — one allow rule covers
  every subcommand (the engine already mandates this invocation, for a different
  reason: it is venv-independent).
- **Command substitution in commits** (`$(…)`/backticks) is **never** auto-approved —
  use `-m`/`-F` per `conventions.md` §3.

These shaping rules are Claude-adapter-specific (they exist because of the permission
allow-list); the underlying hygiene they build on is runtime-general and lives in the
engine's `conventions.md` §3.

## Contract delivery → **`rules/`** and the **section skills**

This is [spec §7](../ADAPTER-SPEC.md)'s §-level half. `conventions.md` is an
index over one file per section, and a section that is only *pointed at* is
read about 3% of the time — measured over 164 sub-agent spawns in a real
consumer. Delivery closes that: a section is in a context because the runtime
put it there, not because a role decided to follow a link. Three layers, and
no restatement is carried twice:

| Layer | Carrier | Reaches |
|---|---|---|
| **Floor** | `CLAUDE.md` → `@.aide/AGENT-CONTEXT.md`, plus the one unscoped rule `rules/aide-command-hygiene.md` (`conventions.md` §3, in positive form) | every context — the human's session and every sub-agent |
| **Role sections** | the eight `skills/aide-*/SKILL.md` files that carry `user-invocable: false` and are named in an agent spec's `skills:` frontmatter | exactly the roles that list them — see the manifest below |
| **Interactive** | the same skill files carry `paths:` (the globs the rules had) | the human's session: the description is in the skill listing regardless, the globs narrow when the runtime auto-invokes it on its own — surfaced, not delivered |

**The manifest, keyed by which document a role writes (issue #109).** One
skill per distinct *reach set*, so no role carries a section it never acts on,
and — deliberately — never one section across two skills: PR 2's generator
emits a section's core whole or not at all, and a delivered copy has to have
one section to defer to.

| Section skill | Sections | Preloaded by |
|---|---|---|
| `aide-document-format` | §1 index, §1 → status icons | `queue-planner`, `spec-author`, `validator` |
| `aide-human-gates` | §1 → human gates | `queue-planner`, `spec-author` |
| `aide-progress-file` | §1 → `progress.md` | `queue-planner`, `validator` |
| `aide-queue-and-inbox` | §1 → `queue-NNN.md`, §1 → `insights.md`, §1 → the maintenance queue | `queue-planner` |
| `aide-item-specs` | §1 → items, authorised paths, environment-gated capabilities; §5 | `spec-author` |
| `aide-off-platform-verification` | §7 | `validator` |
| `aide-test-hygiene` | §6 | `test-writer` |
| `aide-review-and-validation` | §9 | `reviewer`, `validator` |

**Two §1 sections are split by reader, and no skill delivers either half's
other reader** (1.48.0, issue #191). `insights.md` is capture — the shape every
role appends, on the floor and in `aide-queue-and-inbox` — while
`insights-triage.md` (routing, judging, the `framework` hand-over) is the
workflow skill `/aide-review-insights`'s and `insights-maintenance-queue.md`
(the fixes queued ahead of the stage queue) is the queue author's, delivered by
`aide-queue-and-inbox` and restated under pin by `/aide-create-queue`.
`authorised-paths.md` is the declaration `spec-author` writes;
`authorised-paths-proof.md` — `aide scope`, `check --queue`, the fences a test
must never write — is delivered by no skill and reached by pointer from the
validator's, spec-reviewer's and test-writer's own instructions. The two skills
were carrying about 4.8 kB and 3.1 kB of other roles' rules; the split is what
lets each core be delivered whole.

Until 1.46.0 the first five were one bundle, `aide-living-documents`,
preloaded by the two writers: seven sections each, of which each wrote two or
three. The split is what makes the reach honest, and it is also what let three
sections be delivered for the first time — authorised paths and
environment-gated capabilities to `spec-author`, §7 to `validator`, each of
which had been reaching its role through an unpinned restatement in the spec
or a pointer in a template.

**Why skills and not `paths:` rules — measured, issue #85.** A `paths:` *rule*
injects its body on a matching read, and does so inside sub-agent contexts too:
over two loop sessions of a real consumer on 1.22.0, `aide-living-documents.md`
armed 29 and 24 times and `aide-test-hygiene.md` 21 and 13 — roughly 201 KB and
150 KB of scoped-rule text on top of the floor, most of it into roles that read
a document without writing one, and into `builder` and `validator`, which open
tests they never write. A `paths:` *skill* injects nothing on a read: its
`paths:` only narrow when the runtime considers auto-invoking it, and what a
session receives unconditionally is the one-line description in the listing. A
sub-agent's startup context has no skill listing at all — it has its prompt,
the task, the `CLAUDE.md` hierarchy including project rules, git status, and its
**preloaded skills** — so for the six roles `skills:` preload is the only skill
channel there is, and it is unconditional: the body is injected at spawn, with
the frontmatter dropped and HTML comments stripped, whether or not the repo has
a file to open. That closes the hole the rules shipped with — a `test-writer`
in a repo with no tests yet — and costs exactly the roles that list it. The
interactive layer is deliberately **not** backed by a thin `paths:` rule: such
a rule would fire inside sub-agent contexts on a matching read and re-pay
exactly the cost the swap removes.

**Two kinds of skill share `skills/`.** The ten **workflow skills**
(`aide-create-item`, `aide-execute-item`, …) are entry points a person invokes
and the orchestrators run. The **section skills** are `user-invocable: false` —
hidden from the `/` menu, never a command — and preloaded by role.
`disable-model-invocation: true` would look similar and is fatal: the runtime
refuses to preload such a skill, with a debug-log warning and nothing else.
A section skill's `description` is the whole of its interactive delivery, so
it is written as a **trigger** — *load before creating or editing a test file …*
— and kept short; the listing is budgeted at 1% of the context window across
every skill a consumer has.

The globs match **by filename, not by `project.tests_dir` /
`project.docs_dir`**, so they hold whatever a consumer configured — templating
them at install time would turn a silent mismatch into a config error. (The
install-time rendering below touches the *body* of a delivered file and never
its frontmatter, for that reason.)

**How a retired delivered file leaves a consumer.** `install.py --update`
removes `.claude/rules/aide-test-hygiene.md`,
`.claude/rules/aide-living-documents.md` (the two `paths:` rules 1.27.0
replaced) and `.claude/skills/aide-living-documents/SKILL.md` (the bundle
1.46.0 replaced) because `.aide/adapter-manifest.txt` records that the
installer wrote them, and `RETIRED_ADAPTER_PATHS` in `install.py` names all
three for consumers installed before the manifest existed; `--check` names them
first and writes nothing. A consumer that kept the old carrier beside the new
one would be delivered the section twice — and, for the bundle, delivered four
sections to roles that write none of them.

A delivered file **defers to its section**: the engine copy is the source of
truth, and a file that invents a rule of its own binds Claude and no other
runtime. Four of them do better than defer — they *are* the section, rendered
into place at install time (**generated delivered files**, below).
[`tests/test_rules.py`](tests/test_rules.py) pins the three
obligations over rules and section skills alike — a section skill is recognised
structurally, by `user-invocable: false` alone since 1.42.0, never by a name
list and never by a `<!-- pins:` block, which a workflow skill may carry too —
and adds the preload's own guards: every `skills:` entry names a
skill that exists and does not set `disable-model-invocation`, every section
skill is preloaded by at least one agent, and the six agent specs never
re-inline the block this replaced.

**Every delivered file declares its reach**, on one line, near the top of the
body:

```
<!-- reach: all -->
<!-- reach: spec-author, queue-planner -->
```

`all`, or a comma-separated list of agent names; a note explaining the choice
goes on the lines below it inside the same comment.
[`tests/test_structural_budget.py`](../../tests/test_structural_budget.py)
installs the adapter, reads the declaration from the file **here in the source
tree**, and fails when it and the carrier disagree.
For a rule, the carrier is its globs, evaluated against each role's read-set
derived from the delivered agent specs. For a section skill reach is
**literal** — the specs whose `skills:` list it — and its globs are
compared against a second declaration, `<!-- triggers: … -->` — the roles
whose named reads match them, which is what a rule would have armed and what
the listing keys on in a human's session. The same module
pins the **always-on floor** (`AGENT-CONTEXT.md` plus every unscoped rule) per
file, so the constant term every spawn pays cannot move without a deliberate
edit — a section skill is not part of it — and prints the per-role byte table
(floor + spec + preloaded skills) as diagnostics. Reading the declaration from
source is what it owes for the strip below, and it pays for the split by
asserting the other half: that every installed control file is its source
minus the declarations.

The declaration is a comment rather than a frontmatter key on purpose: it
carries no runtime meaning. **And it does not leave this repository** — since
1.50.0 (issue #205) `install.py` strips `<!-- reach -->`, `<!-- triggers -->`
and `<!-- pins -->` from every markdown control file it writes, because all
three address the framework's own test suite, which a consumer does not
install. Write them as a block at the start of a line, which is the shape the
strip recognises and the only shape these files use; a comment written for the
*reader* of a delivered file is content and survives. The bytes were free to
the loop before that anyway — a preload strips comments (measured, with its
caveats, in issue #85's comment "Measurement — what a skill body carries into
context"; an *invoked* skill keeps its comments, a preloaded one does not) —
but they were not free to the consumer whose tree carried them: 26% of the
installed skills, rules and always-on page at 1.49.2, and 42% of
`aide-item-specs`.

**Four delivered files are generated from their section**, and the rest quote
it. Which one a file uses is declared in the file:

```
<!-- generated-from: .aide/conventions/6-test-hygiene.md -->
```

`install.py` writes such a file as its own text — frontmatter, and whatever
*this adapter* has to say about delivering the section (§3's `PreToolUse` hook
and its "use the Bash tool, not PowerShell" shaping; §6's note on what its
globs match), its `<!-- reach -->` and `<!-- triggers -->` declarations
stripped out with every other file's — followed by the section's **core**,
everything above the closing `Rationale` heading, verbatim. Nothing is reflowed
or trimmed, so the delivered body *is* the section and the third obligation
holds by construction. The four are `rules/aide-command-hygiene.md` (§3) and the
section skills for §6, §7 and §9; each stays at the path it already had. The
`generated-from` line is the one declaration the install **keeps**: it is an
instruction to the installer read from source, not an assertion about the
file, and it is what tells a reader of the installed copy that the body is
generated and which section it came from.
[`tests/test_generated_delivery.py`](tests/test_generated_delivery.py) asserts
the render equals the adapter's half plus the core byte for byte, that a
statement added to a section reaches the delivered copy with no second edit, and
that the adapter's half stays a delivery note — it names the section, says the
engine copy wins, opens no heading of its own (the section's `## N.` heading is
the file's title) and is under half the delivered body.
[`tests/test_install_generated.py`](../../tests/test_install_generated.py)
holds the installer half, including that a section that cannot be rendered
**aborts the install** (exit 4) before the first write, the target untouched,
rather than shipping a delivered file with no rules in it. Generating a section is a judgement about *that section*: its core
arrives whole, so a core several times the size of the copy a role needs is a
reason to leave the file hand-written and pinned — which is where the five §1
skills sit — never to trim it here.

**Every hand-written delivered file quotes the statements it delivers**, in one
`<!-- pins: … -->` block per section it draws from — and this one is *not* a
one-liner:

```
<!-- pins: .aide/conventions/6-test-hygiene.md
     A prose note may sit here; anything before the first `- ` is ignored.
     - A test must be deterministic and pass on Windows, macOS and Linux,
       with no network access
     - Never write the repo's own working-directory path literally into a
       test
-->
```

The section path goes on the opener line in **consumer** form
(`.aide/conventions/…`, like every other path under `adapters/`), each `- ` line
is one sentence lifted from that section, and a pin may wrap onto the lines
below it. A file delivering four sections declares four blocks.
[`tests/test_rule_pins.py`](tests/test_rule_pins.py) asserts every pinned
statement still appears in the delivered file *and* in the section it names,
after a normalisation that absorbs reflow, emphasis and case and nothing else —
so it fails in **both** directions, and the fix is to edit both copies in one
commit. Every delivered file must pin at least one statement; a block that
quotes none, and a `<!-- pins:` comment the grammar does not recognise (the
one-line spelling `reach:` uses, notably), are both failures rather than silent
no-ops. Curate them: the load-bearing sentences, not every line. A **generated**
file declares none — there is no restatement to guard — and fails the suite if
it grows one: the quote would be of a wording the file does not control, so the
only way it could ever fail is by reporting drift that cannot happen.

`scripts/review_instructions.py` reports on `.claude/rules/` only. A preload is
not an instruction file to the runtime, so it never appears in the
`InstructionsLoaded` log — and it needs no measuring: it is unconditional per
spawn, and the budget test prints the exact per-role sum.

## Usage probe → **`usage_probe.py`** (`anthropic-oauth`)

This is [spec §6](../ADAPTER-SPEC.md) — the one core/adapter seam in the loop. The
engine's supervisor (`loop/loop.py`) owns the RUN/WAIT/STOP_WEEKLY decision, and
calls a **pluggable probe** sitting next to it for the raw numbers.

- **`usage_probe.py`** implements the engine contract `get_usage(cfg) -> dict | None`
  against Anthropic's OAuth **usage endpoint** — it reads a *hard* utilisation number
  (`five_hour`/`seven_day` + `resets_at`), never scraped output, using the on-disk
  Claude Code OAuth token (`~/.claude/.credentials.json`, overridable via
  `credentials_path`). It returns `None` — degrading the loop to a plain time cadence,
  never crashing — when there is no token or the fetch fails.
- **Selection.** `[loop] usage_probe = "anthropic-oauth"` in the gitignored
  `.aide/loop/loop.local.toml` picks it; `"none"` (the engine default) ships no probe
  and relaunches on time cadence — the graceful path for any plan without a usage API.
- **Co-location** is what makes the seam resolve: `install.py` drops this file next to
  the engine `loop.py` in `.aide/loop/`, and `loop.py`'s `_import_probe_module()`
  imports the sibling by filename, never by provider name. That invariant is tested in
  [`tests/test_usage_probe.py`](tests/test_usage_probe.py).

---

## Default-context instructions → **`default-context.json`** (`CLAUDE.md` + `@path`)

This is [spec §7](../ADAPTER-SPEC.md). The engine's rules live in
`.aide/conventions.md`, which is read only when something points at it — weak in
an agent spec (about 3% of spawns follow the pointer) and absent entirely from an
interactive session, where a person and Claude Code produce durable artifacts
(commit messages, issue bodies, `insights.md` entries) with no agent spec in play.

Claude Code loads a `CLAUDE.md` at the repo root automatically and inlines `@path`
lines recursively, so the channel costs one line. The adapter declares both facts:

```json
{ "file": "CLAUDE.md", "import": "@{path}" }
```

`install.py` renders that to `@.aide/AGENT-CONTEXT.md` and ensures the line is
present in `<repo>/CLAUDE.md`, appending it (or creating a minimal file) and
touching nothing else — the project keeps everything it wrote. `--check` reports
a missing line as drift. The imported page is framework-owned wholesale: it is
part of `core/`, not a managed block inside a project-owned document, so there is
no drift detection to invent and no third ownership pattern.

---

## Layout

```
adapters/claude/
├── agents/        builder · queue-planner · spec-author · test-writer · validator
│                  spec-reviewer (queue boundary, not an item role)
├── skills/        workflow: aide-{create-vision,-roadmap,-progress,-queue,-item} ·
│                  aide-execute-item · aide-feedback-loop · aide-spec-queue ·
│                  aide-review-insights · aide-status-report
│                  section (user-invocable: false, preloaded by role):
│                  aide-document-format · aide-human-gates · aide-progress-file ·
│                  aide-queue-and-inbox · aide-item-specs ·
│                  aide-off-platform-verification · aide-test-hygiene (§6) ·
│                  aide-review-and-validation (§9)
├── commands/      aide-run-{item,queue,roadmap} · aide-review-permissions ·
│                  aide-review-instructions
├── rules/         aide-command-hygiene.md — the one unscoped rule (§3), every context
├── hooks/         command_hygiene_guard.py · log_permission_event.py ·
│                  log_instructions_loaded.py · sibling_instructions.py
├── scripts/       review_permissions.py · review_instructions.py
├── settings.json  permission allow/ask-list + hook registration
├── usage_probe.py the anthropic-oauth usage probe (installed into .aide/loop/)
├── default-context.json   CLAUDE.md + @path — how .aide/AGENT-CONTEXT.md gets linked
└── tests/         adapter/installer conformance — rules, pins, generation, agents, hooks, probe
```

For the *why* behind each obligation — and the conformance checklist a new adapter
works against — see [`../ADAPTER-SPEC.md`](../ADAPTER-SPEC.md).
