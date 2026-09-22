# GitHub Copilot adapter (future work — the second real adapter)

> **STUB.** Design contract: [`../ADAPTER-SPEC.md`](../ADAPTER-SPEC.md).

The first non-Claude adapter, and the real test that `core/` is genuinely
provider-agnostic: a contract with only Claude behind it can silently smuggle in
Claude assumptions, and a second concrete runtime is what flushes them out. Shape:
`.github/prompts/` for the seven entry-points, `.github/agents/` for the five role
definitions, no permission allow-list. Explicitly sequenced
**after** SegQC-xnat becomes a consumer — not part of the initial extraction.
