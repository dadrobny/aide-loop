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

**Project:** {{consumer repo}} (consumer). **Observed under engine {{X.Y.Z}}**
({{queue-NNN / item NNN}}, {{YYYY-MM-DD}}); {{what the current engine version
still does — check it, do not assume}}.

## Observation

_What happened, in the consumer, with the evidence. Name the file, the verb, the
lint, or the rule. If several items reproduced it independently, say how many —
that is the signature of a missing rule rather than a careless author, and it is
the strongest signal this tracker carries._

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
Provenance, when it came from an insight entry:
**Provenance** — `owner/repo` `docs/aide/insights.md`, entry dated YYYY-MM-DD
(item NNN), typed `<type>`.
-->
