# Security

aide-loop installs files into a consumer's repository and ships a permission
allow-list and a guard hook that decide which agent commands run unattended —
all of it under the consumer's own permissions. A defect in any of those is a
security defect, and so is anything that lets an installed file, a document the
loop parses, or an insight a consumer's agent appends do more than it says.

**Report privately** through GitHub's *Report a vulnerability* button on this
repository's Security tab, not as a public issue. If that button is absent,
open an issue saying only that you have a security report, with no details,
and the maintainer will open a private channel. Include the engine version
(`.aide/VERSION` in the consumer, or `core/VERSION` here) and what the
consumer's runtime is, since the adapter and the engine fail differently.

Only the latest release is supported; a fix ships as the next version and its
`CHANGELOG.md` entry says what a consumer edits, if anything. Consumers pick it
up with `python install.py --into <repo> --update`.
