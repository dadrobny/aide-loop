## 1. Format contract — `docs/aide/` documents

`.aide/scripts/aide.py` (`check`, `progress set`, `progress accept`, `queue tidy`) and
`scripts/aide_status_report.py` parse these files by exact shape. The templates
in `.aide/templates/` model the shapes and `aide check` enforces them; deviating
from them breaks the tooling.

**Template fill-in conventions:** a template uses `{{slot-name}}` for a literal
value to substitute, and an _italic line_ for authoring guidance to read then
replace with real prose. `aide check` flags any `{{...}}` left in a generated
`docs/aide/**.md` file as an unfilled template slot. Dates are always
**ISO 8601** (`YYYY-MM-DD`).

**Durable artifacts must read cold.** Everything the loop produces outlives
the session that produced it — item specs, `insights.md` entries, commit
messages, issue bodies, roadmap and progress prose — and is written to be
understood with no access to how it was made. Three rules follow, and they
apply wherever the loop writes, not only to the documents whose shape this
section fixes:

1. **No chat-local identifiers.** A label coined for the convenience of one
   conversation — "the second option", "the batch we just scoped", a letter or
   wave assigned while planning — is scaffolding, not a name. Name a thing by
   what it *is*, and title a change by the change, not by the batch it was
   scheduled in.
2. **Cross-reference by resolvable identity.** An issue number, a file path, a
   commit, a stage number, a dated `insights.md` entry — something a reader can
   look up. Never "the conventions issue", "the companion PR", or "as discussed
   above" pointing outside the artifact.
3. **Record the decision and why it holds, not the route to it.** "My earlier
   lean was wrong", "agreed direction", "settled while drafting" narrate a
   process the reader was not part of. A superseded decision is recorded by
   stating the new one and what changed, not by leaving a trail of leans.

The rules bind interactive sessions as much as unattended ones — a human and a
runtime writing a commit message or an issue body are producing exactly these
artifacts, with no agent spec in play.

**Header blockquote** — every living document opens with one, carrying its step
number in the loop, what it derives from, and what derives from it. Keep the
line current when a document's relationships change. The transient hand-off
("run `/aide-…` next") is spoken by the skill that wrote the file, not stored
in it.

One file per shape — and, where several roles act on one shape, one file per
reader. A pointer of the form `§1 → insights.md` resolves to
`1-format-contract/insights.md`:

| `§1 → …` | File | What it fixes |
|---|---|---|
| Status icons | [`status-icons.md`](1-format-contract/status-icons.md) | The only six icons, their ranks, and the three structural positions they are read at |
| `progress.md` | [`progress.md`](1-format-contract/progress.md) | The single source of truth for status — objectives, stages, deliverable bullets, outcome targets |
| `queue-NNN.md` | [`queue-NNN.md`](1-format-contract/queue-NNN.md) | A batch of one-line items, and how a superseded queue is tidied |
| items | [`items.md`](1-format-contract/items.md) | An item spec's mandatory sections and the reference forms that link it |
| Authorised paths | [`authorised-paths.md`](1-format-contract/authorised-paths.md) | An item's declared scope — the two lists `spec-author` writes |
| Scope proof | [`authorised-paths-proof.md`](1-format-contract/authorised-paths-proof.md) | How that declaration is proved: `aide scope`, `check --queue`, and what a test may never claim |
| `insights.md` | [`insights.md`](1-format-contract/insights.md) | The compound-engineering inbox every role appends to: entry shape, the verbs, immutability |
| Insight triage | [`insights-triage.md`](1-format-contract/insights-triage.md) | Routing an entry by type, judging it, handing a `framework` entry over |
| The maintenance queue | [`insights-maintenance-queue.md`](1-format-contract/insights-maintenance-queue.md) | Insight-derived fixes, queued ahead of the stage queue |
| Human gates | [`human-gates.md`](1-format-contract/human-gates.md) | The table that blocks an item until a person decides |
| Environment-gated capabilities | [`environment-gated-capabilities.md`](1-format-contract/environment-gated-capabilities.md) | Declaring a capability the loop's own machine cannot verify |

### Rationale

- **Slots and italic guidance** both render as ordinary markdown — nothing is
  swallowed by a renderer the way an unescaped `<Placeholder>` tag would be —
  and only one of the two is a machine-recognisable shape, which is what lets
  `aide check` flag a surviving slot without ever flagging guidance. It is also
  why guidance must never be written as a slot. The templates' `{{yyyy-mm-dd}}`
  slot spells the date format out so no separate lookup is needed.
- **Why a section names the template instead of repeating the shape.** The
  template is the shape's *executable* statement — `aide check` enforces it,
  and a role writing one of these files has it open — so a section that also
  draws the table is a second copy of something already checked, free to drift
  where the checked one cannot. It had drifted: a fourth copy of these shapes,
  in the runtime instructions that author the file, still named "the five-icon
  legend" — a vocabulary one short since 🔍 was added, and wrong for as long as
  nothing compared it to the template. So a section states what a shape cannot
  — what a cell may hold, what an icon at a position means, what is mandatory
  and in what order — and names the template for the rest. An example still
  earns its place where it *disambiguates a rule* (§1 → `progress.md`'s
  shorthand-marker bullet, and its correction trail); §1 → `insights.md`'s
  entry line stays for a further reason, that the two rules under it position
  themselves as "before the date" and "after the date"; and §1 → human gates
  keeps its header row for a third, that a mis-shaped row there yields no gate
  and is reported only by a warning, which stops nothing.
- **Why the reading-cold rules are on the floor.** They bind a session with no
  agent spec in play, so `.aide/AGENT-CONTEXT.md` carries them and they reach
  that session without anything having to point at this file.
- **Reading cold.** The reader who matters is someone opening the artifact
  months later with none of the conversation. A chat-local label resolves only
  for someone who was there; a reader who was not cannot even tell what the
  series contained or what happened to the rest of it. Narrated process ages
  badly: the moment a decision is revisited, prose about who once thought what
  is noise around the reasoning that is actually load-bearing.
- **The header blockquote** records structural facts that hold as long as the
  document exists, so a reader landing anywhere in `docs/aide/` can place the
  file without cross-referencing.
