## 5. Clarify mode (`loop.clarify` in `aide.toml`)

Controls how `spec-author` resolves an ambiguous queued item:

- **`interactive`** — ask ≤3 targeted questions before writing the spec.
- **`assume`** (unattended default) — pick the most defensible default and record
  each choice in the spec's mandatory **Assumptions** block, which the validator
  surfaces so a human can audit at the queue boundary. Nothing ever hangs.

A spec written before its dependencies are *implemented* must pin their interfaces
as Assumptions; the builder/validator hand back if reality diverged.

**The duty runs both ways.** When several specs are authored before any is built,
the *producing* spec must enumerate the shape its declared consumers read — not
only the API it exposes but the **serialised form**: the JSON layout, which tiers
or records appear in a walk, what a strict mode rejects. Left unpinned, each
consumer independently codes defensively around it — a tolerant reader plus a
hand-back clause where a straight assertion belonged — and one of them eventually
pins an assertion against a shape no code path produces. Pinning it once, in the
spec that owns it, is cheaper than every consumer guessing separately.
