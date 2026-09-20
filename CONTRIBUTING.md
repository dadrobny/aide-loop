# Contributing

Report a defect with the *Consumer report* issue template, which starts with
the engine version you observed it under. Read [`CLAUDE.md`](CLAUDE.md) before
changing anything: it holds the version rule, what is installed and what is
not, and where the contract lives. Pull requests open as drafts and are
reviewed against [`REVIEW.md`](REVIEW.md); the suite is `pytest` alone, and a
change that reaches a consumer moves `core/VERSION` and `CHANGELOG.md` in the
same commit.
