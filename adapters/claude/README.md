# Claude Code adapter (reference implementation)

> **STUB — see `/HANDOFF.md` task B and `/docs/framework-standalone-plan.md` §3.1, §4.1.**

The reference adapter that drives the AIDE engine (`../../core/`) from Claude Code.
`install.py --adapter claude` copies `agents/ skills/ commands/ hooks/ scripts/
settings.json` into a consumer's `.claude/` and `usage_probe.py` into its
`.aide/loop/`.

TODO: write the AIDE-concept → Claude-Code-primitive map (skills = entry-points,
agents = role tiers, commands = orchestrators, settings.json = permission model,
usage_probe.py = the `anthropic-oauth` usage probe).
