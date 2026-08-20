# Vision — what `aide-loop` is for

> **Scope of this document.** This is the framework's **purpose and non-goals**:
> what AIDE is aiming at, and what it deliberately refuses. It holds no status
> and no ordering — [the GitHub Project](https://github.com/users/dadrobny/projects/1)
> holds those, on the issues themselves, where they cannot drift from the
> tracker. Per-issue rationale stays in issue bodies. Nothing here records
> whether any work is done.
>
> This is a plain repo document, **not a loop artifact**: `aide-loop` does not
> run its own loop (see [`CLAUDE.md`](../CLAUDE.md)), so there is no `aide.toml`,
> no `progress.md`, and nothing for `aide check` to read here. The
> [`vision.md` template](../core/templates/vision.md) the framework ships to
> consumers is a different thing entirely.

## The problem

An LLM can write the code for a work item. What it cannot do unaided is stay
pointed at the same goal across a hundred items, several weeks, and a context
window that resets constantly. Every long-running agent project rediscovers the
same failure: the plan lives in a chat transcript, so it evaporates; state lives
in an agent's head, so a restart loses it; and the mechanical work — parsing
documents, claiming the next item, reconciling status, merging — is paid for in
tokens and judgment every single time, at a quality no better than a script's.

## What AIDE is

**A loop that drives one project from a stated vision to shipped code, using
fresh role-scoped agents for judgment and deterministic scripts for everything
else.**

The durable state is **files in the project's own repo** — living documents under
`docs/aide/`, in shapes fixed tightly enough that a stdlib CLI parses them
without heuristics — plus **git commits** as the checkpoint. Nothing important
lives in a session. A run cut off mid-item re-enters cleanly, because the only
thing a session held was the reasoning, and the reasoning is reproducible from
the documents.

The framework ships as three layers: a provider-agnostic **engine**, a per-runtime
**adapter**, and the consuming project's own **config and documents**.
[`README.md`](../README.md) and [`concepts.md`](concepts.md) describe how that
works. This document says why it is shaped that way, and what would be a mistake
to add.

## Who it is for

A developer running an AI coding agent against a real codebase for longer than
one sitting, who wants the plan to survive the session and the mechanical steps
to stop costing tokens. Not a team-scale project-management product, and not a
turnkey product for someone who will not read `conventions.md`.

---

## Commitments

Each of these rules out designs that are otherwise reasonable. That is what makes
them worth stating.

**1. Deterministic work is scripted; agents are spent only on judgment.**
Prioritisation, spec and test design, implementation, and quality assessment are
genuine reasoning. Claiming an item, reconciling a status rollup, tidying a queue,
merging a branch, and checking document consistency are not — they are parsing
and file edits with a single correct answer. Anything in the second category that
is still being done by an agent is a defect, and the `automation` insight type
exists to catch it. The practical test: if two competent runs could disagree about
the output, it wants an agent; otherwise it wants a CLI verb.

**2. The engine names no provider.** Nothing under `core/` may name Claude, a
Claude model, or a `.claude/` primitive — the rule stated in
[`CLAUDE.md`](../CLAUDE.md) and the reason a different runtime can replace the
adapter wholesale and reuse the engine unchanged. Engine and adapter are
**co-equal halves**, not core plus optional glue. Where the engine genuinely needs
something provider-specific, it takes a seam with a neutral default rather than a
special case: `[loop] usage_probe` is the one such seam, and `"none"` is a
complete answer to it.

**3. An adapter translates; it never re-implements.** The contract is
[`ADAPTER-SPEC.md`](../adapters/ADAPTER-SPEC.md). An adapter re-expresses the
workflow entry-points, the role definitions, and the orchestrators in its own
primitives, and routes every mechanical action through the same
`python .aide/scripts/aide.py …` invocation. The document shapes, the status
icons, the rollup rule and the claim protocol are engine-owned; an adapter that
redefines one has forked the format, not ported the framework. This is the anchor
that makes provider-generality real rather than aspirational.

**4. The project owns its documents; the framework owns its engine.**
`install.py --update` re-copies `core/` and the adapter and **never** touches a
consumer's `aide.toml` or `docs/aide/`. A consumer extends the framework through
its own config — an overlay for JSON, its own documents for content — not by
editing installed files, because those are replaced on the next update.

**5. A stated rule must be enforced by something.** A rule that only lives in
prose decays, and this repo has proved it on itself more than once: the version
bump is a test rather than a memo, the command-hygiene rules have a hook and an
allow-list, and the 1.14.0 audit found five conventions rules that nothing
checked. So a change to a rule and a change to what enforces it belong in the
same commit. The corollary bounds the framework: a rule nothing can plausibly
check is not a rule the framework should state.

**6. Capture must stay cheap.** Recording an insight, a defect, or a gap mid-item
has to cost one appended line and nothing else — no triage, no schema decision, no
interruption to the work in hand. `aide check` shape-checks the inbox as a
**warning, never an error**, precisely so a malformed entry cannot block a run.
Anything that makes capture more expensive trades a real, recurring cost for a
tidiness that nobody was asking for.

**7. The human checkpoint sits at the queue boundary.** Roughly one review per
ten items, on the batch rather than on each merge: that is the density at which a
person can still hold the whole batch in mind while the loop stays worth running
unattended. Framework and process changes always want a reviewed PR regardless of
`git.mode`, because they cascade into every future queue.

**8. Stdlib only, cross-OS.** `aide.py`, `loop.py` and `install.py` are
stdlib-only Python (3.11+, with 3.9 workable), so the engine runs before a project
venv exists and behaves the same on Windows as on Linux. A dependency in the
engine is a dependency in every consumer, resolved before the framework can do
anything at all.

---

## Non-goals

Stated so an issue can be closed as out of scope rather than left open forever.

**Not a general-purpose agent framework.** AIDE drives *an engineering project*
through a fixed seven-step loop. It is not a harness for arbitrary agent
workflows, a prompt library, or a chat UI. A feature that only makes sense
outside the vision→roadmap→queue→item→merge path does not belong here.

**Not a project-management or issue-tracking product.** The living documents
record what the project is building and how far it has got; they are not a
substitute for a tracker, a burndown, or team assignment. The framework's own
issues live on GitHub for exactly this reason.

**Not self-hosting.** `aide-loop` does not run its own loop, and adopting the
document set here was assessed and rejected (#56). The framework is small, is
maintained by one person, and its work does not decompose into the queue-of-ten
shape the loop is built for; running the loop on it would be a demonstration
rather than a use. What the framework does need — evidence that a release works
in an installed layout — is a fixture consumer in CI, not self-adoption.

**Not language-independent.** A consuming project needs a Python interpreter even
when its own code is in another language. Full language-independence means
reimplementing the CLI as a compiled binary plus a per-OS release matrix: moderate
effort, low payoff while every consumer has an interpreter. Deferred until a real
no-Python consumer appears — the ADAPTER-SPEC is already written so that swap
changes no adapter.

**Not autonomous end to end.** The loop runs unattended *between* checkpoints, not
instead of them. Human gates, the queue-boundary review, and `git.mode = "pr"`
exist because some decisions are not the agent's to make. A proposal whose value
depends on removing the last human from the loop is out of scope.

**Not a quality guarantee.** The role split, the fresh-agent-per-item rule and the
independent validator raise the floor; they do not replace the project's own test
suite, review, or judgment. The framework's job is to make the process legible and
repeatable, not to certify the output.

**Not everything a consumer wants in its own repo.** Consumer-reported issues are
the framework's best evidence of real defects — but a fix that only makes sense
for one project's conventions belongs in that project. The question is whether the
next consumer, running a different codebase under a different runtime, hits the
same thing.

---

## How to use this document

When an issue is filed, it should be possible to say which commitment it serves,
or which non-goal it crosses. An issue that serves none of the commitments and
crosses no non-goal is not thereby wrong — it may simply be a defect, and defects
need no vision to justify fixing. But a *feature* that fits nowhere here is
either out of scope, or evidence that this document is out of date. Both are
worth saying out loud in the issue, and the second is worth a PR against this
file.
