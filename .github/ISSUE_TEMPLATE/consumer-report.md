---
name: Consumer report
about: A failure or gap found while running the loop in a consumer repo
title: ""
labels: ""
---

<!--
The first line below is what triage reads first. Keep it, and keep it accurate:
a report triaged against the wrong engine version gets closed as already-fixed
when it is not, or re-fixed when it is. `cat .aide/VERSION` in the consumer.
-->

**Project:** {{`owner/repo` (consumer), or "a private consumer"}}. **Observed
under engine {{X.Y.Z}}** ({{insight ID, or item ref and YYYY-MM-DD}}).

_Name a public consumer as `owner/repo`; a private one is "a private consumer"
and nothing else — not its name, organisation, URL, or a path that contains
them. Everything below follows the body rule in the engine's §1 →
`insights-triage.md`, *Handing a `framework` entry over*: the issue should read
the same had any other consumer raised it. The item ref is whatever locates it
in the consumer — an insight entry's ID (`insight 2026-09-24-3fa1`, as
`aide insights list` prints it) when it came from one, never its position in the
inbox; otherwise `queue-018` or `item 134` with the date. Then say, in the same line, what the **current** engine version does: check it
against a current checkout rather than assuming the defect survived. The real
reports say it inline — "re-verified present at 1.28.1", or "the lint shipped in
1.19.0 and is unchanged through 1.28.1"._

## Observation

_What happened, in the consumer, with the evidence, written to the body rule
above: framework terms quoted, consumer-owned detail by shape, the evidence
itself verbatim with its consumer-owned tokens replaced. A few-line
`docs/aide/*` shape that reproduces it beats "run it on our repo". If several
items reproduced it independently, say how many — that is the signature of a
missing rule rather than a careless author, and it is the strongest signal
this tracker carries. One observation per issue._

## Why it is the engine's

_The framework is not the place for a project's own bug. Say what makes this one
the engine's: a rule stated but unenforced, a contract that does not reach the
role that needs it, a verb that is wrong on a platform no gate sees. If the
neighbouring cases are already handled, name them — that asymmetry is usually
the argument._

## Proposal

_The shape of the fix, not the patch. If it has two halves — a `conventions/`
section plus the `aide check` lint that decides it, say so; those land together._

## Not to be confused with

_Optional. The nearest existing behaviour this is **not**, so triage does not
close it as a duplicate._

<!--
Provenance, when it came from an insight entry — the entry's ID, never its
position in the inbox and never a URL into the consumer:
**Provenance** — insight YYYY-MM-DD-<hex> (item NNN), typed `<type>`.
-->
