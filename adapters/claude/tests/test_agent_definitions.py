"""Every `agents/*.md` is a well-formed Claude Code sub-agent definition.

Agent files are discovered by filename and dispatched by the `name:` in their
frontmatter, so a typo in either is not a syntax error anywhere — it is an agent
that silently never runs, or runs under a name no orchestrator invokes. Nothing
else in the suite reads these files, so this is the only guard on them.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"

# The tiers the adapter README binds: T3 -> opus, T2 -> sonnet.
_MODELS = {"opus", "sonnet", "haiku"}
_EFFORTS = {"low", "medium", "high", "xhigh", "max"}

_AGENT_FILES = sorted(_AGENTS_DIR.glob("*.md"))


def _frontmatter(path: Path) -> dict:
    """The YAML-ish frontmatter as a flat dict.

    Deliberately a tiny hand parser rather than a PyYAML dependency: the suite
    is stdlib + pytest only (CLAUDE.md), and these files use one nesting level
    plus folded `>-` blocks.
    """
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name}: no frontmatter block"
    end = text.find("\n---\n", 4)
    assert end != -1, f"{path.name}: unterminated frontmatter block"
    block = text[4:end]

    data: dict = {}
    key = None
    for line in block.splitlines():
        if line and not line[0].isspace() and ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            data[key] = value.strip()
        elif key is not None and line.strip():
            data[key] = (data[key] + " " + line.strip()).strip()
    return data


def test_there_are_agent_files():
    assert _AGENT_FILES, "no agents/*.md found — the glob or the layout moved"


@pytest.mark.parametrize("path", _AGENT_FILES, ids=lambda p: p.stem)
def test_name_matches_filename(path: Path):
    """Dispatch is by `name:`; discovery is by filename. If they disagree the
    agent is invocable under a name no orchestrator ever writes."""
    assert _frontmatter(path).get("name") == path.stem


@pytest.mark.parametrize("path", _AGENT_FILES, ids=lambda p: p.stem)
def test_description_is_present_and_substantial(path: Path):
    """The description is what the orchestrator routes on — an empty or stub
    one makes the agent effectively unselectable."""
    description = _frontmatter(path).get("description", "")
    assert description.replace(">-", "").strip(), f"{path.name}: empty description"
    assert len(description) > 40, f"{path.name}: description too thin to route on"


@pytest.mark.parametrize("path", _AGENT_FILES, ids=lambda p: p.stem)
def test_model_and_effort_are_recognised(path: Path):
    fm = _frontmatter(path)
    assert fm.get("model") in _MODELS, f"{path.name}: model={fm.get('model')!r}"
    assert fm.get("effort") in _EFFORTS, f"{path.name}: effort={fm.get('effort')!r}"


@pytest.mark.parametrize("path", _AGENT_FILES, ids=lambda p: p.stem)
def test_body_is_not_empty(path: Path):
    text = path.read_text(encoding="utf-8")
    body = text[text.find("\n---\n", 4) + 5:]
    assert body.strip(), f"{path.name}: frontmatter but no instructions"
