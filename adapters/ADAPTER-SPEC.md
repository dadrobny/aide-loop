# ADAPTER-SPEC — the contract every AIDE adapter fulfils

> The AIDE install is **three layers**: the provider-agnostic **engine** (`.aide/`),
> a provider **adapter** (for Claude Code, `.claude/`), and per-repo **project
> config** (`aide.toml`, `docs/aide/`). This document is the **contract between the
> engine and an adapter** — what a runtime must express, in its own primitives, to
> drive the engine. It is engine-level (provider-neutral): the Claude adapter is
> the reference implementation, not the definition. See `README.md` for the loop
> and `conventions.md` for the format/claim/hygiene rules an adapter inherits
> unchanged.

An adapter is a translation layer, not a rewrite. The deterministic 80% —
git/document/merge/env logic — already lives in `scripts/aide.py` and is invoked
identically by every runtime. An adapter re-expresses only the ~18 markdown
control files (entry-points, roles, orchestrators) plus, optionally, a permission
policy and a usage probe. Nothing below re-implements engine logic.

A conforming adapter provides all of §1–§4; §5–§7 are optional and only apply to
runtimes whose feature set supports them.

---

## 1. Seven workflow entry-points

The AIDE loop is seven steps (README §"The AIDE loop"). An adapter exposes each as
whatever its runtime uses to launch a scoped unit of work — Claude Code uses
*skills* (`.claude/skills/aide-*`), Cursor/Copilot/Gemini use *commands/prompts*,
a raw SDK uses prompt files + a driver.

| # | Step | Produces | One-time? |
|---|---|---|---|
| 1 | create-vision | `docs/aide/vision.md` | once |
| 2 | create-roadmap | `docs/aide/roadmap.md` | once |
| 3 | create-progress | `docs/aide/progress.md` | once |
| 4 | create-queue | `docs/aide/queue/queue-NNN.md` | repeats |
| 5 | create-item | `docs/aide/items/NNN-*.md` | repeats |
| 6 | execute-item | tests + code + validation + merge; updates `progress.md` | repeats |
| 7 | feedback-loop | process/document improvements | as needed |

Every entry-point reads and writes the documents in the **exact shapes** fixed by
`conventions.md` §1 (so `aide.py` parses them) and uses the **status icons** and
**rollup rule** defined there. These formats are engine-owned; an adapter must not
redefine them.

## 2. Five role definitions, bound to capability *tiers*

The work is split across five fresh, role-scoped sub-agents. The contract names
**capability tiers**, not models — each adapter binds a tier to one of its own
runtime's models (as high as necessary, as low as adequate). No role signs off its
own work; a fresh instance per item.

| Role | Tier | Why the tier |
|---|---|---|
| queue-planner | **T3 (strongest)** | one plan cascades into ~10 items |
| spec-author | **T3** | the item spec is its single source of truth, cascading into 3 downstream roles |
| test-writer | **T2 (mid)** | well-scoped against a fixed spec |
| builder | **T2** (may escalate to **T3** on a late retry) | implements `source_dir` against a fixed spec + tests |
| validator | **T2** | quality gate against fixed AC; reconciles + merges |

Recon/claim is **not a role** — it is deterministic (`aide claim`), so no agent and
no tier. The Claude reference binds **T3→Opus, T2→Sonnet** (builder→Opus on its
third attempt), with `max` reserved for intractable one-offs. A runtime without
sub-agents degrades gracefully to "a fresh chat per role" guidance — the roles and
their tiers still hold.

**Optional sixth definition — the queue-boundary reviewer.** Where an adapter
supports batch spec-authoring (spec §1's spec-queue entry-point), it should also
express a **spec-reviewer** at **T3**: one pass over *all* of a queue's specs
after they are authored and before any is built, reporting the cross-item
conflicts `aide check --queue` cannot decide because they turn on what an
acceptance criterion *means* — an AC requiring a path its own spec forbids or
never named, a consumer asserting against a shape its producer never pinned, a
dependency aside pointing the wrong way. It is not an item role: it never enters
one item's lifecycle, it reviews rather than edits, and every finding is
arbitrated by the human. The deterministic half stays in the engine
(`aide check --queue`, whose `--report` JSON is this role's worklist), so an
adapter that omits the reviewer still gets everything a script can decide.

## 3. Three orchestrators (item ⊂ queue ⊂ roadmap)

The nested drivers that sequence the roles. Where a runtime can nest
prompt-expansions (Claude Code loads them as skills in one session), express them
that way; where it cannot, a **manual runbook** that calls the same `aide.py` steps
in the same order satisfies the contract.

- **run-item** — one already-claimed item end-to-end: spec-author → test-writer →
  builder → validator+merge, with a ≤`loop.validation_rounds` build↔validate cycle.
- **run-queue** — `aide claim` each item, then run-item it, until the queue empties.
  Does **not** create the next queue.
- **run-roadmap** — generate a queue → run it → generate the next, until the
  roadmap is exhausted. **Each new queue lands via a human-reviewed checkpoint**
  (for Claude, a PR) — one human review per ~10 items.

**Branch names are engine-owned, not adapter prose.** All three shapes —
`<prefix>NNN-short-name`, `<prefix>queue-NNN`, `<prefix>specs-queue-NNN` — are
both constructed and recognised by the engine, so an adapter must **invoke**
`aide claim` and `aide queue start NNN [--specs]` rather than restate a name for
its runtime to type. A name the engine did not build is a name it may not parse,
and the failure is silent: base inference falls back to `main_branch` and an
item merges past its queue branch.

Git commits are the durable checkpoint, so a restart re-enters cleanly regardless
of how the orchestrator is expressed.

## 4. The shared CLI invocation (the contract's anchor)

Every adapter invokes the **same deterministic CLI** for all mechanical work —
recon/claim, progress reconciliation, queue tidy, merge+cleanup, venv check, the
consistency check, session preflight, branch clean-up, the state report:

```
python .aide/scripts/aide.py {check, progress, queue, claim, merge, env, sync, gc, status}
```

This is the anchor that makes generality real rather than aspirational: it is
identical across providers and **implementation-agnostic** — a future compiled
`aide` binary exposing the same subcommands is a drop-in substitution (`aide check`
for `python .aide/scripts/aide.py check`) with no change to any adapter. Adapters
never re-implement these subcommands.

---

## 5. Optional: permission pre-approval + logging

Only runtimes with a permission model provide this; most do not. The Claude adapter
supplies a permission allow/ask-list (`settings.json`), a `PreToolUse`
command-hygiene guard, and permission logging/review. The **command-hygiene rules**
themselves (one command per call, no `cd`, no chained `&&`, no `2>&1`) live in
`conventions.md` §3 and are runtime-general; only the *enforcement mechanism* and
the "permission allow-list" framing are adapter-local. A runtime with no permission
model simply omits this section and relies on the hygiene rules being followed.

An adapter whose config is **JSON** survives framework updates deterministically via
`install.py`'s overlay mechanism: the project keeps a `*.overlay.json` and the
installed file is regenerated as a deep-merge of the framework base and that overlay
(see the Claude adapter's `settings.overlay.json`). Non-JSON adapter files (Markdown,
scripts) are framework-owned wholesale — projects extend them through their own
config, not by editing the installed copies.

`install.py` keeps that ownership honest in both directions. It records every
adapter control file it writes in `.aide/adapter-manifest.txt`, and an `--update`
removes any recorded file the adapter has since dropped (`--check` names it first,
without writing). A file a project adds to the same directory is never recorded,
so it is never removed. A file retired before a consumer had a manifest is listed
in `install.py`'s `RETIRED_ADAPTER_PATHS` and removed on the same grounds: at that
path, the file is the framework's old copy, not the project's.

## 6. Optional: usage probe (unattended long runs)

The engine's supervisor (`loop/loop.py`) gates unattended relaunches on real usage
numbers via a **pluggable probe** — the one core/adapter seam in the loop:

- **Engine (`loop/loop.py`)** owns the RUN/WAIT/STOP_WEEKLY decision loop,
  deadlines, and relaunch. It contains no provider specifics.
- **Adapter (`usage_probe.py`, installed next to `loop.py`)** implements
  `get_usage(cfg) -> dict | None` — the raw usage document (`five_hour`/`seven_day`
  utilisation + `resets_at`) the engine interprets, or `None` when it can't be read.
- **Config** `[loop] usage_probe` selects it: the Claude adapter ships
  `"anthropic-oauth"` (the OAuth usage endpoint); `"none"` ships no probe and the
  loop relaunches on a plain time cadence — the graceful default for any runtime or
  subscription without a usage API.

An adapter for a runtime with no usage endpoint sets `usage_probe = "none"` and
ships no probe file; the contract is still satisfied.

## 7. Optional: default-context instructions

Only runtimes that load a project instruction file automatically provide this.
The engine ships `AGENT-CONTEXT.md` — about a page of the rules that must bind
*before* anything points anywhere, each naming the `conventions.md` section that
carries its full treatment. It exists because a pointer is followed only if the
reader chooses to follow it, and in an interactive session nothing points at
`conventions.md` at all: a person and the runtime produce durable artifacts
(commit messages, issue bodies, `insights.md` entries) with no agent spec in
play.

**A pointer is weak in an agent spec too.** Measured across 11 sessions of a
consumer on engine 1.20.0, 164 sub-agent spawns produced 5 reads of
`conventions.md` — about 3% — and every one was a slice, never the whole file.
An adapter that satisfies this section by pointing has satisfied it on paper.
That is why §-level delivery below is part of the contract and not an
optimisation.

The same split as §5: the **rules** are runtime-general and live in
`conventions.md`; only the *delivery mechanism* is adapter-local. An adapter
declares two things, in `default-context.json` at the adapter root:

```json
{
  "file": "CLAUDE.md",
  "import": "@{path}"
}
```

- **`file`** — the instruction file the runtime loads by default, relative to
  the repo root. It may be nested (`.github/…`) and the installer creates the
  directory, but it must stay *inside* the repo: an absolute or `..`-climbing
  path is refused, since the installer would otherwise create directories and
  write files in a repo nobody named. Runtimes differ in this filename and the
  set moves, so pinning it is the adapter's job. Whether a runtime-neutral name
  (`AGENTS.md`) beats a provider-specific one is likewise a per-adapter
  decision, not an engine default.
- **`import`** — the runtime's syntax for inlining another file, with `{path}`
  standing for the imported file. The Claude adapter declares `@{path}`, so the
  installed line is `@.aide/AGENT-CONTEXT.md`.

Given the declaration, `install.py`:

- ensures the rendered import line is present in the declared file, appending it
  and nothing else when it is missing (idempotent — the project keeps full
  control of everything it wrote);
- creates the file — and any parent directory it names — when it does not
  exist, holding the import line plus a two-sentence note saying that the line
  is the only thing an update will rewrite. A new file cannot clobber anything,
  and a silently absent channel is the failure mode worth avoiding; the note is
  there because a consumer opening a file it did not write needs to know which
  part is theirs. It is markdown, as every instruction file a runtime loads by
  default is today — an adapter whose runtime wants some other format is the
  point at which that assumption should be revisited;
- reports a missing import line under `--check` as drift, the same way it
  reports a stale `VERSION`.

The imported file is **framework-owned wholesale** — the ownership pattern §5
already establishes for non-JSON adapter files. There is no delimited region
inside a project-owned document and no third ownership pattern to invent.

An adapter for a runtime with **no import mechanism** ships a managed delimited
block instead; one with no default-context concept at all omits `default-context.json`
and this section, and relies on `conventions.md` being read — the same graceful
degradation §5 and §6 use.

### §-level delivery

`conventions.md` is an **index**: each section is one file under
`conventions/`, so `§6` is `conventions/6-test-hygiene.md` and `§1 →
insights.md` is `conventions/1-format-contract/insights.md`. A section is
therefore addressable, and an adapter can put one in front of a role without
putting all of them in front of every role — which matters, because no role
needs more than about two thirds of the contract and most need a third.

Two sections say so themselves: **§3** (command hygiene) is delivered in
positive form through whatever always-loaded channel the runtime has, and
**§6** (test hygiene) is delivered to a role about to write a test.

Which channel carries a section follows from who needs it, in terms no runtime
owns: an **always-loaded** channel for what binds every action of every role
(§3); a **role-declared** channel — one the role's own definition names, loaded
when the role starts — for what a role always needs and other roles do not (§6
for a test author; the §1 document shapes for a document writer); and a
**file-scoped** channel, armed by a matching file, only where it cannot fire
inside a spawned role — otherwise it is an unconditional channel wearing a
scope, paid on every spawn that reads a matching file whether or not the role
writes one. That last clause is measured, not presumed: the Claude adapter's
two file-scoped rules armed in most spawns of most roles (issue #85), because
reading an item spec matches the same globs as writing one.

Three properties make a delivery mechanism conformant rather than decorative:

- **It loads without being chosen.** If the role has to decide to read it, this
  is a pointer wearing a different name, and the 3% above is what it is worth.
  A file-scoped channel is a partial exception worth stating plainly: it is
  armed by the role *opening a matching file*, so a role that creates a new one
  without ever opening a sibling can still miss it. Scope such a channel by the
  files the role must read anyway, or use an unconditional one for a rule that
  must bind before the first write.
- **It names the section it delivers, and defers to it.** The engine section is
  the source of truth; the delivered copy is a restatement that will drift, and
  the reader has to know which one wins.
- **It carries no rule the engine does not have.** A rule that exists only in an
  adapter binds one runtime and is invisible to every other — the failure the
  engine/adapter split exists to prevent. Add it to `conventions.md` first.

The last two are the ones a commit breaks in silence, since a restatement that
has drifted still reads as authoritative. The Claude adapter therefore makes
them checkable rather than reviewable: each delivered file — rule or section
skill — carries `<!-- pins: <section file> … -->` blocks quoting the normative
statements it delivers, and `adapters/claude/tests/test_rule_pins.py` asserts
every quoted statement still appears in both the delivered copy *and* the
section it names, so editing either copy alone fails. Another runtime may
express the guarantee however it likes; what is contractual is that the two
copies cannot drift unobserved.

The **first** obligation has a measurable half too, wherever the channel is
file-scoped: which roles a given scope actually arms is a fact about the
delivered tree, and a scope believed to be narrow while arming everyone is a
cost paid on every spawn that nothing reports. The Claude adapter states the
expectation in the delivered file itself (`<!-- reach: … -->`) and
`tests/test_structural_budget.py` compares it — against the agent specs' own
read-sets for a file-scoped rule, against the roles' `skills:` declarations for
a role-declared skill. A role-declared channel satisfies the first property
fully — it loads because the role was spawned — and has nothing to measure
behaviourally, only structurally: that every declaration names a section file
that exists and can be loaded, and that every section file is declared by at
least one role. Its reach is the set of roles that declare it, a fact of the
delivered tree; a runtime whose channel is unconditional has nothing to measure
and owes nothing here.

The Claude adapter uses `.claude/rules/` for the always-loaded channel — one
unscoped file for §3, loaded into every session and every sub-agent — and
`.claude/skills/aide-<section>/SKILL.md` for the role-declared one: a skill
with `user-invocable: false`, preloaded at spawn into exactly the agent specs
whose `skills:` frontmatter names it (§6 into `test-writer`; the §1 document
shapes into `spec-author` and `queue-planner`). The same skill files carry
`paths:`, which on a skill injects nothing on a read: the skill's one-line
description is in every interactive session's listing regardless, and the
globs only narrow when the runtime auto-invokes the skill on its own — so that
description is written as a trigger and is the whole of what a human's session
receives beyond the floor. No file-scoped rule remains — one
would fire inside sub-agent contexts too and re-pay what the preload saves.
A runtime with no such channel keeps pointing at the section — the same
graceful degradation as above, now with an honest account of what it costs.

---

## 8. Optional: sibling-repo instructions

Only runtimes that can inject context mid-session provide this. It is §7's
sibling and its mirror image: §7 gets a **framework-owned** file into the
project's default context once, at install time, through an import line; this
gets **another repository's own** file into a session that reaches across into
it, on demand, at the moment it does.

They stay separate sections because nothing is shared but the motivation. The
carrier differs (a durable import line vs. a per-session injection), the content
owner differs (the framework vs. a repo nobody here controls), and a runtime can
easily have one mechanism and not the other.

The **rule** — "a repository's own instructions bind for work inside it" — is
runtime-general and lives in `conventions.md` §8, restated in `AGENT-CONTEXT.md`
so it binds from the first message. Only the mechanism is adapter-local.

**The declaration already exists.** No new configuration: `[framework] local_path`
and `[hygiene] extra_repos` in the personal, gitignored `.aide/loop/loop.local.toml`
are already the machine's answer to "which repos does this project legitimately
span", in the one file permitted to hold absolute paths. The instruction filename
is the `file` an adapter already declares in `default-context.json` (§7), so it is
named once.

An adapter that provides this must:

- **point at the instruction file; do not inject its contents.** The body looks
  more helpful and is worse three ways. It goes **stale** — the case that
  motivates the rule is a session *editing* the sibling, so a copy taken at first
  touch can be wrong when used, and wrong invisibly, which is the failure the
  mechanism exists to remove. It is **capped** — runtimes bound injected context
  (Claude Code at 10,000 characters, past which output is spilled to a file and
  replaced with a preview and its path, the runtime improvising this very
  pointer). And it is **paid in full every time**, where a pointer costs a few
  hundred characters and the reader spends the rest only if it opens the file.
  The mechanism's job is the part a session cannot do for itself: noticing it has
  crossed into a repo whose rules it was never given.
- act **lazily** — point on the first action touching a path inside a repo, not
  eagerly at session start. Size is the weaker half of this argument once the
  payload is a pointer; **relevance** is the strong half. An eager list names
  every declared repo, most of which a given session never opens, and a block
  that is usually irrelevant is one a reader learns to skip — including on the
  session where it was not. Pointing at the moment of the crossing makes the
  message true of what is happening right then, and costs nothing in a session
  that never reaches across;
- point at each repo **once per session**, and mark a declared repo with no
  instruction file as done too, so a missing file is not re-checked on every call;
- **never alter the action it observes.** The mechanism watches; it does not
  gate. It must not block, deny, or approve, and a failure in it — an unreadable
  config, a malformed declaration, its own bug — must leave the session exactly
  as it would have been without it;
- **stay cheap on the hot path** — this runs before tool calls, so it must not
  read a whole instruction file to decide whether to name it.

The Claude adapter implements it as `hooks/sibling_instructions.py`, registered
on `PreToolUse` for the path-touching tools. One detail there generalises to any
runtime: **verify that the mechanism's output actually reaches the model.** A
Claude Code `PreToolUse` hook's plain stdout goes to the debug log and is never
shown — only `hookSpecificOutput.additionalContext` is — so the obvious
implementation prints the file, appears to work, and delivers nothing.

A runtime with **no way to inject context mid-session** omits this and relies on
the `conventions.md` §8 rule being read, the same graceful degradation §5, §6 and
§7 use.

---

## Conformance checklist

- [ ] Seven workflow entry-points, each honouring the `conventions.md` document shapes.
- [ ] Five roles bound to T3/T2 tiers (recon/claim left to `aide claim`).
- [ ] Three orchestrators (or a manual runbook calling the same `aide.py` steps in order).
- [ ] Every mechanical action routed through `python .aide/scripts/aide.py …`.
- [ ] *(if the runtime has one)* a permission policy enforcing `conventions.md` §3.
- [ ] *(if unattended runs are wanted)* a `usage_probe.py`, or `usage_probe = "none"`.
- [ ] *(if the runtime loads an instruction file by default)* a `default-context.json`
      declaring that file and the runtime's import syntax.
- [ ] *(if the runtime has any always-loaded instruction channel)* §3 delivered,
      not pointed at. *(if a role definition can additionally name what it
      starts with)* §6 to the test author and the §1 shapes to the document
      writers, by that declaration — not by a file-scoped channel, which fires
      inside spawned roles too. Either way: loaded without the role choosing
      to, naming the section it delivers, and adding no rule the engine does
      not have.
- [ ] *(if the runtime can inject context mid-session)* a lazy, non-blocking
      mechanism surfacing a declared sibling repo's instruction file, once, on
      first reach.
