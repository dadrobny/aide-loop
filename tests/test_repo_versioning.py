"""A change a consumer receives must move the version it compares against.

`core/` and `adapters/` are exactly what `install.py --update` copies into a
consumer, so a commit touching either changes what that project runs. If
`core/VERSION` does not move with it, the consumer's `.aide/VERSION` matches ours
and every check reports "up to date" while it runs an older engine. That is not
hypothetical: seventeen consumer-visible commits once shipped under `1.1.0`.

So the rule is enforced here rather than remembered. Docs-only and
repo-test-only commits are exempt — they change nothing a consumer installs.

Stdlib + pytest only. Skips (never fails) when the comparison cannot be made:
no git, no `main` ref, a shallow clone.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = "core/VERSION"

#: Paths whose content is copied into a consumer by install.py.
CONSUMER_VISIBLE = ("core/", "adapters/")

#: Subtrees under those paths that are NOT installed, so changing them alone
#: does not reach a consumer. `adapters/claude/tests/` is this repo's own suite;
#: ADAPTER-SPEC.md is documentation about the contract. Every adapter's README
#: is too — `install.py` copies only an adapter's control directories, and says
#: so above `ADAPTER_CONTROL` — so those are excluded by shape, not by name
#: (`_is_adapter_readme`), and a new adapter's README needs no entry here.
NOT_INSTALLED = (
    "adapters/claude/tests/",
    "adapters/ADAPTER-SPEC.md",
)

sys.path.insert(0, str(REPO_ROOT))
import install  # noqa: E402  (path shim above)


def _read_version(path: Path) -> str:
    """utf-8-sig: an editor-added BOM must not become part of the version string."""
    return path.read_text(encoding="utf-8-sig").strip()


def _git(*args: str) -> subprocess.CompletedProcess:
    # conventions.md §6: name the codec. This reads changed *paths* out of a
    # diff, and a path with a non-ASCII character decodes differently under the
    # windows leg's locale — where a mis-decoded path silently misses the
    # `core/`/`adapters/` prefixes this whole gate is built on.
    return subprocess.run(["git", *args], cwd=str(REPO_ROOT), encoding="utf-8",
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _merge_base() -> str:
    """The commit this branch diverged from, or skip if it can't be determined."""
    if _git("rev-parse", "--git-dir").returncode != 0:
        pytest.skip("not a git checkout")
    for ref in ("origin/main", "main"):
        if _git("rev-parse", "--verify", "--quiet", ref).returncode != 0:
            continue
        base = _git("merge-base", "HEAD", ref)
        if base.returncode == 0 and base.stdout.strip():
            return base.stdout.strip()
    pytest.skip("no main/origin-main ref to compare against (shallow or fresh clone)")


def _changed_paths(base: str) -> set:
    """Every path changed on this branch, committed or not, vs the merge base."""
    paths: set = set()
    for cmd in (("diff", "--name-only", base, "HEAD"),  # committed on the branch
                ("diff", "--name-only", base),          # + unstaged working tree
                ("diff", "--name-only", "--cached", base)):  # + staged
        res = _git(*cmd)
        if res.returncode == 0:
            paths |= {line.strip() for line in res.stdout.splitlines() if line.strip()}
    return paths


def _is_adapter_readme(path: str) -> bool:
    parts = path.split("/")
    return len(parts) == 3 and parts[0] == "adapters" and parts[2] == "README.md"


def _reaches_a_consumer(path: str) -> bool:
    if any(path.startswith(skip) for skip in NOT_INSTALLED) or _is_adapter_readme(path):
        return False
    return any(path.startswith(prefix) for prefix in CONSUMER_VISIBLE)


def _version_at(ref: str) -> str:
    res = _git("show", f"{ref}:{VERSION_FILE}")
    if res.returncode != 0:
        pytest.skip(f"no {VERSION_FILE} at {ref}")
    return res.stdout.strip()


def test_consumer_visible_change_bumps_version():
    base = _merge_base()
    changed = _changed_paths(base)

    reaching = sorted(p for p in changed if _reaches_a_consumer(p))
    if not reaching:
        pytest.skip("no consumer-visible change on this branch")

    # Touching the file is not enough — the number a consumer compares against
    # has to actually move, or `--check` still reports "up to date".
    current = _read_version(REPO_ROOT / "core" / "VERSION")
    assert install.compare_versions(_version_at(base), current) == "behind", (
        "This branch changes what a consumer installs but leaves "
        f"{VERSION_FILE} at {current!r}, so `install.py --check` would report "
        "'up to date' for a project running the older engine.\n"
        "Bump core/VERSION (patch for a fix, minor for a new surface) and add a "
        "CHANGELOG.md entry. Consumer-visible paths changed here:\n  "
        + "\n  ".join(reaching)
    )


def test_version_moved_forward_not_backward():
    """A bump must increase the version — a typo that lowers it is worse than none."""
    base = _merge_base()
    if VERSION_FILE not in _changed_paths(base):
        pytest.skip("core/VERSION unchanged on this branch")

    previous = _git("show", f"{base}:{VERSION_FILE}")
    if previous.returncode != 0:
        pytest.skip("no previous core/VERSION to compare against")

    current = _read_version(REPO_ROOT / "core" / "VERSION")
    assert install.compare_versions(previous.stdout.strip(), current) == "behind", (
        f"core/VERSION moved from {previous.stdout.strip()!r} to {current!r}, "
        "which is not forward."
    )


def test_changelog_records_the_current_version():
    """Whatever core/VERSION says must be findable in the changelog."""
    version = _read_version(REPO_ROOT / "core" / "VERSION")
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"[{version}]" in changelog, (
        f"core/VERSION is {version} but CHANGELOG.md has no '[{version}]' section. "
        "A version a consumer can see must say what changed."
    )


# --------------------------------------------------------------------------- #
# per-template versions (issue #164)
# --------------------------------------------------------------------------- #
#: `core/scripts/aide.py`'s `_TEMPLATE_MARKER_RE`, restated rather than
#: imported: this module stays importable without loading the engine, and the
#: engine's own tests hold every template to the engine's reading of the line.
_TEMPLATE_MARKER = r"^<!--\s*aide-template:\s*([a-z][a-z0-9-]*)\s+(\d+)\s*-->\s*$"


def _template_versions(text_of) -> dict:
    """`name -> version` over `core/templates/*.md`, reading each through
    *text_of(path)*, which returns the file's text or `None`."""
    versions = {}
    for path in sorted((REPO_ROOT / "core" / "templates").glob("*.md")):
        text = text_of(path)
        match = re.search(_TEMPLATE_MARKER, text or "", re.MULTILINE)
        if match:
            versions[match.group(1)] = int(match.group(2))
    return versions


def test_changelog_names_every_template_version():
    """A template's number is a consumer's cue to open the changelog, and the
    warning `aide check` prints tells it to search for `<name> template <N>`.
    A number with no such entry sends the consumer to look for a migration
    nobody wrote down."""
    versions = _template_versions(lambda p: p.read_text(encoding="utf-8-sig"))
    assert len(versions) >= 6, versions
    changelog = re.sub(r"[`*]", "", (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    missing = [f"{name} template {n}" for name, n in sorted(versions.items())
               if not re.search(rf"\b{re.escape(name)} template {n}\b", changelog)]
    assert not missing, (
        f"CHANGELOG.md names no entry for: {missing}. The entry that bumps a "
        "template's number names '<name> template <N>' and says what a consumer "
        "edits, and whether it is optional.")


def test_template_versions_moved_forward_not_backward():
    """A number that goes down tells every document built since that it is
    newer than the template — the opposite of what happened."""
    base = _merge_base()

    def at_base(path: Path):
        res = _git("show", f"{base}:{path.relative_to(REPO_ROOT).as_posix()}")
        return res.stdout if res.returncode == 0 else None

    before = _template_versions(at_base)
    after = _template_versions(lambda p: p.read_text(encoding="utf-8-sig"))
    lowered = {name: (n, after[name]) for name, n in before.items()
               if name in after and after[name] < n}
    assert not lowered, f"template versions moved backward (before, after): {lowered}"
