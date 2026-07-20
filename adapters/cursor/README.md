# Cursor adapter (porting stub)

> **STUB.** Design contract: [`../ADAPTER-SPEC.md`](../ADAPTER-SPEC.md).

Maps the adapter contract to Cursor primitives. Cursor has rules/commands but **no
true sub-agents**, so the three orchestrators become guided single-agent
role-prompts; the seven entry-points become `.cursor/commands/`. Honest gap: role
isolation is advisory, not enforced.
