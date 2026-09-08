### `insights.md` (optional, additive — the compound-engineering inbox)

Where out-of-scope learning goes so it is never lost *and* never acted on out
of scope. Any role, at any time, appends **one line** and returns to its task:

```
- [ ] <type> — <one line> *(item NNN, YYYY-MM-DD, engine X.Y.Z)*
```

with `<type>` one of **knowledge** (document it), **defect** (fix it), **gap**
(plan it), **automation** (a recurring manual/agent action deterministic code
could replace — script it), **framework** (belongs to AIDE itself).

**The file exists before a role needs it — the engine puts it there.**
`aide check`, `aide claim`, `aide queue start` and `aide insights list` each
create a missing `insights.md` as a byte-exact copy of
`.aide/templates/insights.md`, and commit it when git can — on a branch, with an
identity to commit as; otherwise the file is left untracked and the notice says
why, for the next commit to carry. A role spawned by `/aide-run-queue`,
`/aide-run-roadmap` or `/aide-spec-queue` therefore finds the inbox in place,
and a capture is a plain append to a file that is already there. No role copies
the template by hand, and an existing file — malformed or not — is never
touched.

**Name where it came from, in whatever form is honest.** The provenance before
the date is free-form and optional — write `item NNN` from inside an item,
`queue-NNN` for planning or spec-authoring done before any item exists,
`items NNN-NNN` for a finding that genuinely spans several, or omit it entirely
from a role outside the loop. Those first three are the conventional spellings
and worth following so a reader can scan them, but they are not a grammar the
CLI enforces: **the ISO date is the only part that is load-bearing**, since
`archive` cuts on it. Never bend a provenance to fit a shape — collapsing
`items 099-101` to `item 099` is a rewording the immutability rule below
forbids, and it destroys the very thing the marker records.

**Name the engine you were running, after the date** — `engine X.Y.Z`, which is
one read of `.aide/VERSION` and no more work than that. The date cannot stand in
for it: a project runs an engine for as long as it likes after a release, so two
entries captured the same week may sit either side of a restructure, and a
reader who has only the date must re-derive which. It earns the most on a
`framework` entry, which leaves for another repo and is triaged there months
later by someone with no other way to know; it costs the same nothing on the
rest. Optional and unenforced like the provenance — and **never retrofitted**,
since the claim line below is immutable: an entry captured without one stays as
captured.

`aide check` shape-checks entries (warning, never error — capture must stay
cheap). It is deliberately loose either side of the date and strict about the
date, for the reason immutability makes sharp: a warning on a captured line can
never be cleared, so a check that rejects an honest capture produces permanent
noise, and permanent noise is what teaches a reader to skim the one run where a
warning was real.

**Capture is a plain append; everything after it has a verb.** Reading and
triaging the file by hand is what made triage expensive enough to defer:

```
python .aide/scripts/aide.py insights list [--open] [--type T] [--trail]
python .aide/scripts/aide.py insights tick N --pointer "<where it landed>"
python .aide/scripts/aide.py insights archive --before YYYY-MM-DD [--yes]
```

`list` numbers entries by position and prints the backlog without the closed
history around it; `tick` performs the one in-place edit below, or appends a
dated trail line when the entry is already ticked; `archive` moves **closed**
entries older than a date into `insights/archive-YYYY-QN.md`, each moved entry
and its trail carried across line for line, and says so — an archive renumbers
what remains, so re-run `list` after one. A closed entry whose line is too
malformed to yield a date can be moved by no cut at all; `archive` names each
one it had to leave behind rather than dropping it silently.
Archived entries are frozen and no longer shape-checked, since the immutability
rule leaves no way to act on a warning about one.

**The claim is immutable; its status is not.** The captured line is never
reworded, reordered, or deleted — that is what protects provenance, and it is
load-bearing precisely when an entry turns out to be *wrong*: the wrongness is
the record, and a correction written beneath it teaches what a silent rewrite
would erase. Ticking the checkbox is the one in-place edit.

Status *about* a claim is bookkeeping, and freezing bookkeeping buys nothing. An
entry may carry an **appendable status trail** — dated lines, indented under the
entry, newest last:

```
- [x] framework — <the original claim, never touched> *(item 117, 2026-08-20)*
  - **2026-08-20** → aide-loop issue #50
  - **2026-09-02** → issue rewritten; the original framing overstated the finding
  - **2026-10-11** → resolved in engine 1.16.0
```

A single routing pointer may still be appended to the entry line itself
(`- [x] … → <where it landed>`); the trail is what a *second* update goes in,
and what an entry whose premise decayed needs. Without it there is nowhere to
record that half a claim has since been fixed, so the next reader re-derives all
of it.

#### The routing table

**Triage routes each unchecked entry by its type, and this table is the whole
rule.** It is written once, here, because two roles read it — the pass that
triages the inbox and the one that authors the next queue — and a rule each of
them keeps its own copy of is a rule that has already drifted.

| Type | Where it goes | Who ticks the entry |
|---|---|---|
| `knowledge` | the owning document — the smallest edit that preserves the fact | the triaging role, on the fold |
| `defect` | a candidate item on the **maintenance queue** | the queue that absorbs it |
| `gap` | a candidate item — maintenance queue, or the stage queue when the stage was going to fill it anyway | the queue that absorbs it |
| `automation` | a candidate item adding the script/CLI verb **and** the prose that mandates it | the queue that absorbs it |
| `framework` | an issue on `[framework] repo` from `aide.toml`; unset or offline, it stays pending | the filing role, on the hand-over |

**Routing a `defect`, `gap` or `automation` entry never ticks it.** Triage
stands *at* the queue boundary, so the queue that would carry such an entry does
not exist yet: leaving it unchecked **is** the routing, and the open inbox is
what carries it to whoever authors that queue. The exception is the entry triage
does **not** route — see *decayed premise* below, which closes one.

#### Insight-derived fixes get a queue of their own, ahead of the stage queue

When open `defect`, `gap` or `automation` entries exist at a queue boundary they
are batched into a **maintenance queue, authored and merged before the stage
queue** — a normal queue in every respect: its own number, its own items, and it
ticks the entries it absorbs with the item numbers they became. It is not a
second live queue: **the live queue is the lowest-numbered open one**, so a
maintenance queue numbered ahead of the stage queue is served first, with no new
state anywhere and nothing for a role to choose between.

**How the pair reaches a human is the caller's business, not this section's.**
The ordering above falls out of the numbering alone, so it holds whether the two
plans go up as one review or two — or as neither, in a project whose `git.mode`
pushes nothing (§4). What the engine fixes is that the fixes are queued *ahead*,
never the shape of the checkpoint around them.

Why not simply put the fixes in the stage batch: a one-line fix that rides a
ten-item stage waits for the whole stage to merge, and every other branch picks
it up only after that. The split costs one more queue to carry and buys a small,
fast, clean merge the rest of the work can build on.

The queue's author still decides. An entry that does not warrant a queue of its
own — too small to be worth a branch, blocked on something unbuilt, out of scope
— is passed over with the reason stated, exactly as on a stage queue; and a
`gap` the upcoming stage was going to fill anyway belongs in the stage queue,
with that stage named as the reason. What is never allowed is silence.

#### Triage judges the entry; the judgement is a trail line

Routing an entry as written is not the whole of triage. An entry may repeat one
already captured, its premise may have decayed, or it may be filed under a type
that does not fit what it describes. Three findings, one form — **a dated trail
line under the entry, never an edit to the claim**:

- **Duplicate** — the same claim as an earlier entry. Route the earlier one and
  point the later at it; both stay in the file, because two roles noticing the
  same thing independently is itself a fact about the project.
- **Decayed premise** — what the entry names no longer exists, or has already
  been fixed by work done since. **A decayed premise is ticked, because there is
  nothing left for a queue to carry** — the trail line says what closed it, and
  the claim remains the record of what was true when it was captured. This is
  the one tick triage performs on a `defect`, `gap` or `automation` entry, and
  it is not a routing: nothing is being sent anywhere.
- **Wrong type** — the entry describes a defect and is filed as knowledge, or
  the reverse. Route it by what it *is* and say so in the trail; the type in the
  captured line is never rewritten.

**A ticked entry whose status is now stale gets a trail line too** — that is
triage as much as routing is, and it is what stops the next reader re-deriving
what someone already knew.

**A `framework` issue body opens with the engine version the observation was
made under** — first line, before the observation:

```
**Project:** <consumer repo> (consumer). **Observed under engine X.Y.Z**
(<item ref>, YYYY-MM-DD).
```

Triage at the destination begins by checking the claim against that engine's
history, which is why the version leads rather than sits somewhere in the prose:
a report triaged against the wrong version is closed as already-fixed when it is
not, or re-fixed when it is. Take the version from the entry; if the entry has
none, read the consumer's current `.aide/VERSION` and say in the body that it is
*the version at triage time, not at capture* — an unmarked fallback is worse than
none, because it reads as an observed fact. The issue is triaged in a repo that
cannot see this one, and "which engine was this?" is otherwise answered by hand,
per issue.

**Writing that header is the filing role's job; a form on the destination cannot
reach it.** An issue template binds a human composing in a browser and is
silently bypassed when the body is composed by the role and passed on the command
line (`gh issue create --body …`), which is how this handover files — no template
can reach that path, and that is what a template is rather than a gap in one. The
cost of writing it is nothing, because **the consumer already holds the fact**:
it is in the entry's own marker, or one read of `.aide/VERSION` away.

**When triage happens depends on the destination.** `knowledge`, `defect`,
`gap` and `automation` all land in this project — a document it owns, or a
candidate item — so they wait for the queue boundary, where the insight-review
pass runs and whoever reviews the next queue sees its routing. `framework` does not: it leaves for an issue
on another repo, and nothing about that destination needs a queue, so a
`framework` entry may be triaged **on capture or on demand**. Routing it through
the boundary too means the inbox accumulates for exactly as long as a queue
runs, and a long queue is normal.

**The open inbox is an input to queue authoring, not only an output of
triage.** An entry routed to "a candidate item" is routed to a queue that does
not exist yet — triage runs *at* the boundary, where the finished queue is
closed and the next one is unwritten — so the inbox is where such an entry
waits, and whoever authors the next queue reads it before choosing the batch:

```
python .aide/scripts/aide.py insights list --open
```

Every open `defect`, `gap` or `automation` entry is **considered, and either
queued or explicitly passed over — never silently dropped**. Queueing one is a
routing like any other, so the author who queued it ticks it with the item
number it became (`aide insights tick N --pointer "item NNN"`, which commits the
file when git can); a pass-over leaves the entry open and is stated where the queue
is reviewed, rather than left for the next reader to re-derive. That is what
makes leaving an entry unchecked at triage an honest move rather than a hope:
**an unchecked entry is still a candidate**, and the next queue's author sees
it.
