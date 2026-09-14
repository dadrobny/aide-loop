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

A conforming adapter provides all of §1–§4; §5–§8 are optional and only apply to
runtimes whose feature set supports them. The unnumbered *Copies of engine text*
section below is not an adapter feature at all: it is the one rule for every copy
of engine text, of which an adapter's delivered files are one case.

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

The work is split across five fresh, role-scoped sub-agents (plus the two
optional definitions below). The contract names **capability tiers**, not
models — each adapter binds a tier to one of its own runtime's models (as high
as necessary, as low as adequate). No role signs off its
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

**Optional definition — the item reviewer.** An adapter **may** express a
**reviewer** at **T2**, dispatched over one item's diff concurrently with the
`validator` and gated by a `loop.review` key in `aide.toml` (`"off"` by
default). The two are different reads and neither covers for the other
(`conventions.md` §9): the validator is spec-relative and gates the merge, the
reviewer is adversarial and produces findings. Where an adapter expresses it,
**the merge must wait for both** — findings collected after the item lands gate
nothing — and the role writes no code, modifies no tests, does not merge and
does not touch `progress.md`; its findings triage in scope (a fix dispatched
back) or out of scope (one `insights.md` line). It is optional because a review
round costs tokens on every item and a project with CI and hosted reviewers may
decline it; the engine's default is off, so an adapter that omits the role is
conformant and its consumers are unaffected.

**Optional definition — the queue-boundary reviewer.** Where an adapter
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
themselves live in `conventions.md` §3 and are runtime-general, and this
document does not summarise them. A guard enforces the section's *mechanical*
bullets — the shapes a command must not take, carve-out included — while its
positive-form requirements (which interpreter, which CLI) stay with the prose;
only the *enforcement mechanism* and the "permission allow-list" framing are
adapter-local. A runtime with no permission
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
  exist, holding the import line plus a short note saying that the line is the
  only thing an update will rewrite, and that the rest of the file should point
  at the contract rather than carry a copy of it. A new file cannot clobber
  anything, and a silently absent channel is the failure mode worth avoiding;
  the note is there because a consumer opening a file it did not write needs to
  know which part is theirs. It is markdown, as every instruction file a runtime
  loads by default is today — an adapter whose runtime wants some other format
  is the point at which that assumption should be revisited;
- reports a missing import line under `--check` as drift, the same way it
  reports a stale `VERSION`;
- reports, under `--check`, passages of the declared file that repeat contract
  text the engine ships — **advisory, and never part of an exit code.** The
  file is the project's, so nothing here may fail a build over what a project
  wrote in it; what the installer can do is *see* the duplicate, which no
  mechanism did before. A copy in this file is unmaintainable by construction —
  the installer writes one line into it and reads it for that one line — so it
  drifts until it contradicts the contract it came from, and one consumer's
  instruction file had three engine releases narrated into its prose by hand
  before anything noticed. Seeding contract text into a project-owned file is
  the wrong repair, being the same trade with the drift hidden; the two right
  ones are pruning the copy, and moving upstream whatever it says that the
  shipped contract does not.

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
needs more than about two thirds of the contract and most need a third. Each
section is written core first — the rule, its shape examples, its
disambiguators — with the provenance under a closing `Rationale` heading, so a
delivered copy has a natural cut: everything above the heading.

Three sections say so themselves: **§3** (command hygiene) is delivered in
positive form through whatever always-loaded channel the runtime has, **§6**
(test hygiene) is delivered to a role about to write a test, and **§9** (review
and validation) is delivered to the roles that judge a finished diff — a role
told neither what validation answers nor what review does will collapse the
two, and the collapse is silent, since both reads end in a report saying the
item is fine.

Which channel carries a section follows from who needs it, in terms no runtime
owns: an **always-loaded** channel for what binds every action of every role
(§3); a **role-declared** channel — one the role's own definition names, loaded
when the role starts — for what a role always needs and other roles do not (§6
for a test author; each §1 document shape for the role that writes *that*
document); and a
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
  the reader has to know which one wins — unless it is **generated** from the
  section (below), in which case it still names it, because the reader has to
  know where the rationale and the `§N` pointers resolve.
- **It carries no rule the engine does not have.** A rule that exists only in an
  adapter binds one runtime and is invisible to every other — the failure the
  engine/adapter split exists to prevent. Add it to `conventions.md` first.

The last two are the ones a commit breaks in silence, since a restatement that
has drifted still reads as authoritative. **What is contractual is that the two
copies cannot drift unobserved** — the unnumbered *Copies of engine text*
section below states that rule for every copy of engine text and decides which
treatment a given copy gets; the two here are how an adapter holds it for a
delivered file, and it may use either per file.

*Quote it.* A hand-written delivered copy carries `<!-- pins: <section file> …
-->` blocks quoting the normative statements it delivers, and
`adapters/claude/tests/test_rule_pins.py` asserts every quoted statement still
appears in both the delivered copy *and* the section it names, so editing
either copy alone fails. The known cost is curation: a statement nobody pinned
drifts freely. The blocks sit **in the file** because the channel the file is
shipped through — the preload — strips comments; that is the copies rule's
placement criterion, applied to a delivered file's designed reader.

*Generate it.* A delivered copy that is **rendered from the section at install
time** is not a restatement, so it cannot drift and owes no pin. The Claude
adapter writes `<!-- generated-from: <section file> -->` in the file, and
`install.py` emits that file's own text — frontmatter and whatever the
*adapter* has to say about delivering the section, its test declarations
stripped (*What an install ships*, below) — followed by
the section's core, everything above the `Rationale` heading, verbatim. What is
contractual is the property, not the spelling: a runtime that generates must
make the generation checkable (the delivered body equals the section core, and
a section that cannot be rendered fails the install rather than shipping a
delivered file with no rules in it), and must keep the adapter's own half
distinguishable from the engine's, since that half can still state a rule the
engine does not have. Generating a section is a **judgement about that
section**: its core is delivered whole, so a core three times the size of the
copy a role needs is a reason to leave the file hand-written and pinned, or to
compact the section — never to trim it in the delivered copy, which would put
the restatement back.

The same guard is available to a **workflow** entry point that restates a slice
of contract it acts on — two of this adapter's skills carry the §1 routing table
for inbox entries, which is written once in the engine precisely so the pass that
triages the inbox and the one that authors the next queue cannot route
differently. Such a skill owes no pin (it delivers no section), and a pin it does
declare binds it exactly as a delivered file's binds that file. What identifies a
delivered section skill is therefore its `user-invocable: false` frontmatter, not
the presence of a pins block — which a generated delivered file does not carry
at all, and is refused if it grows one.

The **first** obligation has a measurable half too, wherever the channel is
file-scoped: which roles a given scope actually arms is a fact about the
delivered tree, and a scope believed to be narrow while arming everyone is a
cost paid on every spawn that nothing reports. The Claude adapter states the
expectation in its **source** copy of the delivered file (`<!-- reach: … -->`,
stripped on the way into a consumer — see *What an install ships* below) and
`tests/test_structural_budget.py` compares it — against the agent specs' own
read-sets for a file-scoped rule, against the roles' `skills:` declarations for
a role-declared skill, having first asserted that the installed file is that
source file minus the declarations, so the expectation and the delivered tree
remain one claim about one file. A role-declared channel satisfies the first property
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
whose `skills:` frontmatter names it (§6 into `test-writer`; §9 into
`reviewer` and `validator`; each §1 document shape into the role that writes
that document). One skill may bundle several sections, and does wherever their
reach is identical; a section is never split across two skills, so a delivered
copy still has one section to defer to and to be generated from. The same skill files carry
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

## Copies of engine text — point, generate, pin, or advise

**Not an adapter feature, and not optional — and unnumbered for that reason.**
Every numbered section above tells an adapter how to express something. This one
decides what happens whenever engine text is *copied* — wherever the copy sits,
in the engine, in an adapter, in this repository's own documents, or in a
consumer's tree.

§7 above already holds one copy to a property: an adapter's delivered file,
where **what is contractual is that the two copies cannot drift unobserved**. Every
other copy got its own answer at the site where somebody noticed it, or none —
and copies drift exactly where nothing watches them. Two were found wrong within
two days of each other (issue #205), both shipping to every consumer:
`templates/progress.md`'s header comment restated the stage rollup in two halves,
**neither of which was ever true** — that a ❌ bullet blocks a stage's ✅, when an
excluded bullet has counted toward ✅ since the first commit, and that the rollup
then ticks that stage's acceptance boxes, which no rollup has ever done. 1.48.1
is when the *section's* identical restatement was corrected and the rule moved
into `aide progress -h` (#192); nothing compared the template's copy to either,
so it shipped on. The second was a workflow skill calling the status legend
"five-icon" — 🔍 had been the sixth since 1.20.0, forty-eight releases earlier.

### The ladder

Four treatments, in order. Take the first that applies: the earlier rungs cost
less and have less to go wrong.

**1. Point — the default.** Do not copy. Two conditions license a pointer, and
both are about the reader already holding the text, or being one step from the
only authoritative statement of it.

- **The reader already loads the section.** A role whose definition preloads
  `conventions.md` §6 does not need §6 restated inside it, and a rule the
  always-loaded channel carries (`conventions.md` §3) is in front of every
  session and every spawn already. The measurement in §7 above — 164 sub-agent
  spawns, 5 reads of `conventions.md`, about 3% — is what a pointer is worth to
  a reader who does *not* have the text. It says nothing against one aimed at a
  reader who does.
- **The text is mechanism the code owns.** A rule the CLI applies has exactly one
  authoritative statement: the help text `argparse` renders. Prose elsewhere
  describing *what a verb does* is a copy of code, and code moves faster than the
  prose about it. Point at `aide <verb> -h` and stop.

The rejected alternative is "copy just the one sentence, it is short" — which is
how a template header came to state a two-release-stale rollup. A sentence is the
easiest thing to copy and the easiest thing to leave behind.

**2. Generate.** When the copy is a **whole section core** and the channel
delivers it whole, render it from the section at install time: there is no
restatement, so nothing can drift and nothing needs pinning. The mechanics, and
the properties a runtime that generates must make checkable, are in §7 above,
under *Generate it*. The judgement is about the **section**, not the file — a core several times
the size of the copy the reader needs is a reason to leave the file hand-written
and pinned, or to compact the section, never to trim the delivered copy, which
puts the restatement back.

**3. Quote-pin.** When the copy is a **hand-compressed restatement** — the reader
needs a third of a section, or a slice assembled out of three — the copy quotes
the normative statements it delivers, and a test asserts each quotation in *both*
copies after a normalisation that absorbs reflow, emphasis and case. Both
directions is the whole point: a copy reworded away from its section fails, and
so does a section reworded under a copy that still quotes the old wording.
Curate the quotations — the load-bearing sentences, not every line. A statement
nobody pinned drifts freely; that is the known and accepted cost of this rung,
and the reason rungs 1 and 2 come first.

**Where the pins live is decided by the channel the framework ships the copy
through — its *designed* reader.** Not by every reader it could conceivably have:
any file can be opened by a person, so a criterion quantified over all readers
rules out every placement and decides nothing.

- **In the copy**, when the designed reader receives it through a channel that
  **strips comments** — a spawn preload. There the declaration is free at the
  point of use, and it sits beside the sentence it binds, which is where an
  editor needs to see it. A section skill is this case: it is *shipped to be
  preloaded*, and a person opening the `SKILL.md` in an editor is incidental to
  the delivery rather than the delivery. "The copy" is the framework's copy of
  it: the declaration is authored beside the sentence and stripped at install
  (*What an install ships*, below), so it reaches the editor who needs it and
  no consumer at all.
- **In the test module**, when the designed reader gets the bytes **unstripped**
  — an instruction-file import the engine does not own, or a template a consumer
  author opens and copies from. A declaration nobody reads still costs its own
  size: the always-on floor went *down* at 1.47.0 when a rule's pins block
  retired, because the block outweighed the rules it quoted.
  `core/AGENT-CONTEXT.md` is the worked case (issue #194) — its pins are a list
  in `tests/test_floor_pins.py`, and the failure message names the page rather
  than the test.

**What the incidental readers do buy is a different decision.** The adapter's
five hand-written delivered skills sit on the right side of the criterion — their
designed reader is the preload, so their pins stay in the copy — and that is not
an argument that the bytes are free everywhere else. Measured on an install of
1.49.2, HTML comments were 32,147 of the 124,013 bytes of the installed skills,
rules and `AGENT-CONTEXT.md` — 26% — and 7,528 of `aide-item-specs`'s 17,859.
That number was never a reason to move pins; it was the case for not shipping the
declarations at all, which is the next subsection, and which 1.49.3 acted on.

**4. Advisory.** A **consumer-owned** file — its instruction file, its
`docs/aide/**` — is not the framework's to guard. The installer may *report* a
copy it recognises and must never fail over one. The file is the project's;
rewriting it trades a visible duplicate for a silent one, and seeding contract
text into it is the same trade with the drift hidden. This is the stance §7 above
takes on the instruction file, and it generalises to everything a project
writes.

**A fifth rung, for code.** A prose statement of behaviour the **code** owns,
which survives rung 1 because it *is* the authoritative statement (a `-h` block)
or because the reader genuinely needs it in place, is **pinned by a test that
exercises the code against the prose** — not by a quotation, since there is no
second prose copy to quote. `aide progress -h`'s rollup sentence is the model
(`test_progress_help_states_the_rollup_the_code_applies`, issue #192): the test
transcribes the English as a predicate and compares it to `rollup_status` over
the whole input space, so the help may be reworded freely and a change to what
the rollup *does* fails until the sentence moves with it. All seven of this
engine's `-h` **description blocks** sit on this rung since 1.49.4 — the other
verbs carry option help only — registered together in
`core/scripts/tests/test_aide_help_pins.py`: each pinned sentence names the
test that exercises it, and the register asserts both that the sentence is
still in the rendered help and that the guard still resolves. The pins live in
the **test module**, which is where the placement criterion puts them — a `-h`
block reaches its reader whole, and there is no second prose copy to carry
them. Writing the register is also what audits the prose: pinning the six
unpinned blocks found five sentences the code had already left behind.

### What an install ships

`pins`, `reach` and `triggers` are declarations **for this repository's tests**.
A consumer's tree is not where they belong: they are bytes a consumer pays for,
in files a runtime may hand to a reader whole, describing assertions that live in
a suite the consumer never installed.

The rule is therefore that **a declaration existing for the framework's tests
does not ship**, and since 1.49.3 the installer enforces it: every markdown
control file loses its `pins`, `reach` and `triggers` blocks on the way in — a
hand-written file at copy time, a generated one before the section core is
appended. A block takes the blank line it stood on with it, and *only* these
three openers are removed, and only where one opens a line: a comment written
for the **reader** of a delivered file is content, and a strip that could not
tell the two apart would be a licence to delete it. The installed skills, rules
and always-on page fall from 124,013 to 93,347 content bytes — 24.7%.

The one reader that stood in the way was named when the rule was recorded, and
that is what made the pass mechanical: `tests/test_structural_budget.py` read
`reach` **from an install**, on purpose — the reach it checks is a fact about
the *delivered* tree. It now reads the declaration from source, keeps reading
every byte it **costs** from the install, and pays for the split with the
assertion foreseen here: the installed file is the source file minus the
declarations, and for a generated one the section core appended to that. Two
readings, one claim about one file.

`generated-from` is not in that set and differs in kind: it is an instruction to
the installer, read from **source** at render time, not an assertion about the
file. Whether the rendered copy keeps the line is a readability call — what §7
above requires of a generated file is that it *names the section it delivers*, which
its body does in prose. This adapter keeps it: one line, and the only thing that
tells a reader of the installed file that the body below is generated rather
than authored, and which section it came from.

### Registering a copy

A copy nobody decided is a copy nobody guards, and the register of a copy is
its guard. A quote-pinned copy is registered by its pins — the `<!-- pins: -->`
block in the copy, or the entry in the test module (`FLOOR_PINS`) that the
placement criterion puts there; a generated copy by its `generated-from` line;
prose the code owns by its entry in the `-h` register (`HELP_PINS`); a
template by the guard that compares it to the sections. A copy with none of
these is a pointer or advisory, and the rungs above name those instances one
by one — the eight workflow skills that restate nothing measurable, the
consumer's own files — so that a copy that is neither guarded nor named is the
thing to notice. Make a copy, give it its guard, in the same commit: that is
the last moment at which the ladder above is a question rather than an
excavation. (While #205 was that excavation, an inventory page listed every
copy with its rung and whether the row was in force; the rows are all in force
or their own issues, and a page that says which work is done is what this
repository keeps on its tracker, so the page is gone.)

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
      not have — the last held either by pins the suite checks in both
      directions, or by generating the copy from the section.
- [ ] *(if the runtime can inject context mid-session)* a lazy, non-blocking
      mechanism surfacing a declared sibling repo's instruction file, once, on
      first reach.
- [ ] *(always)* every copy of engine text the adapter makes decided by
      *Copies of engine text* — pointed at, generated, quote-pinned with its
      pins where the channel puts them, left advisory because a project owns
      the file, or, for prose the code owns, pinned by a test that exercises
      the code against it — and registered by that guard, so that a copy with
      no guard is a pointer or advisory the rule names.
