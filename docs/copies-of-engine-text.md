# Copies of engine text — the inventory

The engine's rules are written once, in `conventions.md` sections, and then
copied: into a delivered skill, into the always-on page, into a template's
header comment, into a verb's `-h`, into a consumer's own files. **The rule that
decides what each copy gets is
[`adapters/ADAPTER-SPEC.md`](../adapters/ADAPTER-SPEC.md), its unnumbered
*Copies of engine text* section** — point, generate, quote-pin (and where the
pins live), or leave advisory. It is stated
there and nowhere else; this page is the other half of it, the list of copies it
applies to.

Why a list at all: a copy nobody wrote down is a copy nobody decided. Issue #205
found the framework holding exactly one direction of drift under a written rule
— the adapter's delivered files — while every other kind of copy had whatever
guard the person who last noticed it happened to add, and two were found wrong
in two days. Adding a copy means adding its row here, in the same commit, while
the ladder is still a question rather than an excavation.

## The copies

The **Rule** column names the rung, then whether the framework is already there
(*in force*) or the row is outstanding work (*follow-up*).

| Copy | Restates | Reader, and channel | Ships? | Guard today | Rule |
|---|---|---|---|---|---|
| The 5 hand-written section skills — `aide-document-format`, `aide-human-gates`, `aide-item-specs`, `aide-progress-file`, `aide-queue-and-inbox` | compressed slices of §1 sections (and §5, in `aide-item-specs`) | the roles whose `skills:` name them, by **spawn preload**; a person, by interactive read | the text yes, `.claude/skills/`; the declarations **no** — stripped at install since 1.49.3 | `<!-- pins: -->` in the source copy (22 / 15 / 54 / 30 / 24 statements), `adapters/claude/tests/test_rule_pins.py` in both directions; `<!-- reach: -->` against `tests/test_structural_budget.py`, which reads it from source and asserts the installed file is that file minus the declarations | **quote-pin — in force**, pins in the copy: the designed reader is the preload, which strips them. The **install-strip is in force too** (1.49.3, issue #205) — the pins never leave this repository, which is a stronger version of the same criterion, and they did not move |
| The 4 generated delivered files — `rules/aide-command-hygiene.md` (§3), `aide-test-hygiene` (§6), `aide-off-platform-verification` (§7), `aide-review-and-validation` (§9) | a whole section core, verbatim | the rule: every session and every sub-agent, by the **always-loaded channel** (`.claude/rules/`, unscoped); the three skills: as above | yes, minus the declarations; `<!-- generated-from: -->` is kept, being an instruction to the installer rather than an assertion | rendered by `install.py`; `adapters/claude/tests/test_generated_delivery.py` and `tests/test_install_generated.py`; a section that will not render **aborts the install** (exit 4); a pins block on one of these fails the suite | **generate — in force** |
| The 2 workflow skills that carry a contract slice — `aide-create-queue` (11 pins), `aide-review-insights` (13) | §1 → insights triage, insights-maintenance-queue, `queue-NNN.md` | the session running that loop step | yes, minus the pins | pins, checked by the same module, which does not *require* them there | **quote-pin — in force** |
| The other 8 workflow skills — `aide-create-item`, `-progress`, `-roadmap`, `-vision`, `aide-execute-item`, `aide-feedback-loop`, `aide-spec-queue`, `aide-status-report` | measurably nothing: ≤ 7 contract word-runs each, against 171 and 295 for the two above | as above | yes | none, and none needed | **point — in force.** They point at the template, the section and `-h`; the absence of pins here is the ladder working, not a gap |
| `core/AGENT-CONTEXT.md` — the always-on floor, 5,315 B | §1, §1 → `insights.md`, §1 → `progress.md`, §1 → human gates, §2, §3, §4, §5, §8 and `core/README.md`, across nine headings — most naming one section, one (mechanical actions go through the CLI) naming §2, §4 and `core/README.md` together | every role on every spawn, by **instruction-file import**; and an interactive session with no agent spec in play | yes, `.aide/AGENT-CONTEXT.md` | `FLOOR_PINS` in `tests/test_floor_pins.py` — in the test module, core-only, **40 statements covering seven of the nine headings** (#194/#203 pinned the read-cold block; #205's pass pinned the rest and reconciled the wording both copies now share). `tests/test_structural_budget.py` pins the floor's *bytes*, which is cost, not content | **quote-pin, pins in the test — in force, and the placement is the criterion's worked case.** The other **two headings are pointers** (rung 1) carrying one sentence of the page's own, with no second copy to hold them to: *each loop step ends in its own session* is the original, written here and nowhere else (the `## Hand-off` tail came out of seven skills in its favour, #161), and *mechanical actions go through the CLI* restates none of the §2, §4 and `README.md` it names — the verb list is `argparse`'s, rung 5, `aide <verb> -h`. Pinning that one would mean adding engine sentences to a page every spawn pays for. §3 reaches a session **twice** on purpose: generated whole into `rules/aide-command-hygiene.md`, and compressed to four pinned sentences here for the read before any rule loads |
| The 6 template header comments — 10,534 B (`insights` 3,276 · `progress` 2,708 · `item` 1,766 · `vision` 1,024 · `queue` 933 · `roadmap` 827) | two different things: the **shapes**, and **mechanism** — what `aide progress` and `aide check` do with the document | the role authoring that document, which opens the template; and a **consumer author** reading `.aide/templates/` | yes, `.aide/templates/` | `tests/test_template_conventions.py`, both halves: the fill-in convention (a slot inside italic guidance), and — since 1.49.5 — `test_no_header_restates_a_rule_or_a_verbs_help`, which compares each header's ten-word runs against every section core under `core/conventions/**` and every verb's rendered `-h` description block, reusing `install.py --check`'s own `_contract_runs` and `CONTRACT_ECHO_WORDS`. Its carrier is the **leading header comment**, which is this row's copy; the template **bodies** are outside it and hold 36 shared ten-word runs of their own (`item` 23, `progress` 8, `roadmap` 5) — a candidate row recorded on #205, not this one | **Shapes: not a copy** — since #193 the section names the template rather than drawing it, so the template is the original. **Mechanism: point — in force** (1.49.5). `progress.md`'s rollup moved to `aide <verb> -h` in 1.49.1; writing the general guard found four more passages restating a section core — the Outcome-targets gate, the gated-capability definition in two headers, the item-numbering rule and the status-trail rule — and all four now point. The headers score **zero shared runs** (61 before the pass). The guard catches copies, not *wrong* copies: #205's own sentence shared no run with anything, which is what was wrong with it, and that side is the source's pins (`HELP_PINS`, the sections') |
| The `-h` description blocks — `check`, `progress`, `insights`, `claim`, `gc`, `status`, `scope` | the behaviour of the code beneath them | any role or human running `-h`; and every document that now points here instead of restating | yes, in `.aide/scripts/aide.py`; the harness ships too, as `.aide/scripts/tests/` | `HELP_PINS` in `core/scripts/tests/test_aide_help_pins.py` — **102 sentences across all seven blocks**, each naming the test — or the tuple of tests — that exercises it (106 distinct guards: 87 that already existed, 19 written for the pass, and a guard mutation-checked wherever its fit was not obvious); `test_progress_help_states_the_rollup_the_code_applies` (#192) is one of the 102 and stays where it is | **code-pinned — in force, seven of seven** (1.49.4). The pins live in the test module, not in `-h`: a `-h` block reaches its reader unstripped, and the rung's guard is a test exercising the code, not a quotation. Auditing the seven found seven wrong or incomplete sentences across four blocks, and two `conventions/` sections restating the same mechanism wrongly one copy over — all fixed in the same release |
| A consumer's instruction file (`CLAUDE.md`) | anything in `AGENT-CONTEXT.md`, `conventions.md` and its sections, or `core/README.md` | the runtime, every session | it *is* the consumer's | `install.py --check` names each restating passage — ten-word runs and whole headings — **advisory, outside every exit code** (#96) | **advisory — in force** |
| A consumer's `docs/aide/**` | the templates they were generated from | every role and every human in that project | consumer-owned | none. `aide check` enforces the *shape*; nothing records which template a document was built from | **advisory — follow-up.** #164's provenance markers are what would make the advisory report possible; re-scope it under the copies rule |
| `ADAPTER-SPEC.md` §2's tier table | the agent specs' own model bindings | a person porting a runtime, and an agent reading the spec — **interactive read**, never a preload | no (not installed) | none | **quote-pin, pins in the test — follow-up**, which is #156. The bytes reach a human unstripped, so the criterion puts the pins in the module, not in the spec |
| The command-hygiene block six agent specs carried; the `## Hand-off` tail seven skills carried | §3; `core/README.md`'s loop sequence | the roles | — | `adapters/claude/tests/test_rules.py` fails if either heading returns | **point — in force, and the copy is gone.** The precedent for rung 1: one of the six had already drifted |
| This repository's `CLAUDE.md` | the copies rule's mechanism, previously at length | an agent editing this repo | no | nothing automatic; the pointer to the rule is what keeps it from restating | **point — in force** (1.49.1). It keeps what an agent editing *this* repo cannot infer: which file is which, and which test fails when |

## What is deliberately not on this ladder

- **`README.md`, `docs/concepts.md`, `docs/vision.md`.** They explain the
  three-layer model to a person deciding whether to use the framework. An
  explanation binds nobody and no role acts on it, so it is not a delivery and
  owes no pin — the failure mode a pin prevents (a reader obeying a stale copy as
  if it were the rule) has no reader here. They are still *compared* against a
  consumer's instruction file by `install.py --check`, because `core/README.md`
  is where the shared-vs-personal ownership rules actually live. An explanation
  may still carry a copy by accident: three of them (`adapters/claude/README.md`,
  `ADAPTER-SPEC.md` §5, `docs/concepts.md`) glossed §3 in a parenthetical that
  omitted its `||`/`;` chaining, the directory-changing wrappers and the
  declared-repo carve-out — the same omission the floor's compression nearly
  shipped in 1.49.2. They point now, which is rung 1 applied to an explanation.
- **`AGENTS.md` restating `REVIEW.md`.** A copy of this repository's review
  contract, not of engine text. `CLAUDE.md`'s merge-policy section already says
  the three files must not drift, and none of them is installed.

## How the numbers were measured

On 2026-09-11, against this working tree at engine 1.49.3 — except the pin
counts and the restatement magnitudes, which are 1.49.1's and which 1.49.2 and
1.49.3 do not touch. Re-measure rather than quote: every figure here moves with
the tree.

- **Comment bytes in an install.** `install.main` into a temporary target, then
  every `<!-- … -->` span in the 18 installed skills, the one installed rule and
  `.aide/AGENT-CONTEXT.md`, counted with its delimiters, in UTF-8 bytes.
  **Before the install-strip (1.49.2): 32,147 of 124,013 (25.9%)**; worst file
  `aide-item-specs`, 7,528 of 17,859. **After it (1.49.3): 1,549 of 93,347
  (1.7%)** — the whole remainder being the four `generated-from` lines, the one
  declaration an install keeps — and `aide-item-specs` 0 of 10,317. The tree a
  consumer receives is 30,666 B smaller, 24.7%, and says exactly what it said
  before.
- **Template header bytes.** The leading comment block of each
  `core/templates/*.md`, delimiters included. These are **1.49.5's**,
  re-measured: the four headers that stopped copying grew by 191 B in
  total (10,343 → 10,534), a pointer naming its section being longer
  than the sentence it replaced. The 10,275 this row carried before was
  itself 68 B stale — `progress.md`'s header grew at 61b9827 and nothing
  re-measured — which is the argument for the sentence above: re-measure
  rather than quote.
- **Pin counts.** `- ` lines inside `<!-- pins: … -->` blocks, source tree;
  for the `-h` row, `(sentence, guard)` pairs in `HELP_PINS`, and its guard
  split is distinct `module::function` strings against `git diff main`.
- **The install-strip.** `install.strip_declarations`, applied by
  `install.py` to every markdown control file it writes: the `pins`, `reach`
  and `triggers` blocks, each with the blank line it stood on, and nothing
  else. The declarations stay in `adapters/claude/`, where the tests that read
  them are.
- **Restatement magnitude.** `install.contract_echoes` plus
  `install._contract_runs` — the same ten-word-run comparison `--check` runs over
  a consumer's instruction file — applied to each skill with its HTML comments
  removed, and to each template with its header kept. The runs **overlap**, so
  one copied sentence scores many times over: read the number as a magnitude, not
  as a count of passages. Measured on **source**, so a generated file's engine
  half is absent by construction and scores near zero — which is the point of
  generating it.

## Corrections this pass made to the record

- Issue #205's own table counted `rules/aide-command-hygiene.md` among the
  quote-pinned copies. It has been **generated** since 1.47.0 and carries no
  pins — the pinned set is five skills, not five skills and a rule.
- The issue read the unpinned workflow skills as an open question ("2 pin, the
  rest do not"). Measured, the other eight restate nothing worth pinning: ≤ 7
  word-runs each against 171 and 295 for the two that do. They are rung 1, not an
  exemption, and no follow-up work falls out of them.
- The **Ships?** column said "yes" of the declarations as well as the text they
  annotate. Since 1.49.3 that is only true of the text: `pins`, `reach` and
  `triggers` are stripped at install, so a row's answer is now about the copy
  and its guard separately.
