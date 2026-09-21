# Contributing

Report a defect with the *Consumer report* issue template, which starts with
the engine version you observed it under. Read [`CLAUDE.md`](CLAUDE.md) before
changing anything: it holds the version rule, what is installed and what is
not, and where the contract lives. Pull requests open as drafts and are
reviewed against [`REVIEW.md`](REVIEW.md); the suite is `pytest` alone, and a
change to the installed parts of `core/` or `adapters/` (not the adapter
tests, spec or READMEs) moves `core/VERSION` and `CHANGELOG.md` in the same
commit, as CLAUDE.md's versioning section scopes it.
