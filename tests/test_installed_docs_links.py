"""A framework change silently invalidating a consumer document link (issue #16:
``.aide/README.md`` vanished from ``core/`` while three ``CLAUDE.md`` links to it
survived) is otherwise nothing checks for. This asserts every relative markdown
link inside the engine, as actually installed to ``.aide/``, resolves to a real
file — so a link like ``[`.aide/README.md`](.aide/README.md)`` cannot go stale
without failing the suite that ships the very commit that would break it.

``core/templates/*.md`` is scanned separately: its relative links point at
sibling *project* documents (``progress.md``, ``../items/``) that are
deliberately generated later and do not exist in a fresh install — that is not
a broken link, so the templates are excluded from the general scan.

Stdlib + pytest only; ``install.py`` is imported as a module.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)

_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _relative_link_targets(text: str) -> list[str]:
    targets = []
    for m in _MD_LINK_RE.finditer(text):
        target = m.group(1).split("#", 1)[0]  # drop any in-page anchor
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        targets.append(target)
    return targets


def test_engine_readme_ships_and_its_links_resolve(tmp_path: Path):
    target = tmp_path / "consumer"
    target.mkdir()
    rc = install.main(["--adapter", "claude", "--into", str(target), "--yes"])
    assert rc == 0

    aide_dir = target / ".aide"
    readme = aide_dir / "README.md"
    assert readme.is_file(), "core/README.md must ship as .aide/README.md"

    checked = 0
    for md in aide_dir.rglob("*.md"):
        if aide_dir / "templates" in md.parents:
            continue  # template links point at not-yet-generated project docs
        for link in _relative_link_targets(md.read_text(encoding="utf-8")):
            resolved = (md.parent / link).resolve()
            assert resolved.exists(), (
                f"{md.relative_to(target).as_posix()} links to missing '{link}'")
            checked += 1
    assert checked > 0, "expected at least one relative markdown link to verify"
