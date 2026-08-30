# Command hygiene

The rules and the reasoning behind them are `.aide/conventions.md` §3. This file
is how they reach a Claude session; it is **delivery, not a second source of
truth**. A `PreToolUse` hook enforces the mechanical ones and bounces a
violating shape back with the fix, and an unattended run that emits a shape
nothing pre-approved stalls on a permission prompt — so getting them right first
time is what keeps a long run moving.

- **Use the Bash tool, not PowerShell**, for git / `aide` / venv / grep commands
  — only `Bash(...)` rules are allow-listed.
- **One command per Bash call** — never chain with `&&`, `||` or `;`. A single
  `|` pipe (`git branch -r | grep aide/`) is fine.
- **No `cd`, and no `git -C` / `--git-dir` / `--work-tree` / `GIT_DIR=` prefix**
  — the working directory is already the repo root. The one exception is a repo
  declared in `.aide/loop/loop.local.toml` (§3).
- **No `2>&1`** or other stderr redirection — the tool captures stderr already.
- **No `$(…)` or backticks in a commit message** — use `-m "msg"`, repeated
  `-m` for paragraphs, or `git commit -F <file>`.
- **Python and pytest through the relative venv path** —
  `.venv/Scripts/python -m pytest` on Windows, `.venv/bin/python -m pytest` on
  macOS/Linux. The `aide` CLI always as `python .aide/scripts/aide.py …`, which
  is stdlib-only and works before any venv exists. Against a declared sibling
  repo, run the sibling's own install with an explicit root —
  `python <sibling>/.aide/scripts/aide.py --repo <sibling> …` (§3) — never a
  `cd` or a cwd-resolved root.
- **If an `aide` verb covers it, the raw git form is wrong** — `aide sync`,
  `claim`, `queue start`, `merge`, `gc`, `scope`. Do not improvise the
  equivalent `git fetch` / `switch -c` / `diff --name-only` sequence.
