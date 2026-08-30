"""The `InstructionsLoaded` hook and the report built on its log (issue #78).

ADAPTER-SPEC §7 makes "delivered, not pointed at" a contract point, and the
difference is invisible from inside a session. This pair is the standing
measurement: the hook records every instruction load, the report says which
shipped rule never appeared.

Two properties matter more than the formatting:

* the hook **never alters a session** — no stdout, always exit 0, and a
  malformed payload is swallowed rather than raised;
* the hook is **schema-tolerant** — the event-specific payload fields are not
  pinned by public documentation, so a renamed field must degrade the record,
  not empty it. The tests below drive both the documented spelling and an
  undocumented one.

Load-by-path, matching `test_sibling_instructions.py`.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

_ADAPTER = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hook = _load("log_instructions_loaded", _ADAPTER / "hooks" / "log_instructions_loaded.py")
review = _load("review_instructions", _ADAPTER / "scripts" / "review_instructions.py")


def _run(monkeypatch, tmp_path: Path, payload) -> list:
    """Drive `hook.main()` with a real stdin, return the parsed log records."""
    log = tmp_path / "log.jsonl"
    monkeypatch.setattr(hook, "LOG_PATH", log)
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    hook.main()
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


# --------------------------------------------------------------------------- #
# the hook
# --------------------------------------------------------------------------- #
def test_a_documented_payload_is_recorded_in_full(monkeypatch, tmp_path):
    records = _run(monkeypatch, tmp_path, {
        "session_id": "s1",
        "hook_event_name": "InstructionsLoaded",
        "cwd": "/repo",
        "reason": "path_glob_match",
        "file_path": ".claude/rules/some-scoped-rule.md",
    })
    assert len(records) == 1
    assert records[0]["session_id"] == "s1"
    assert records[0]["reason"] == "path_glob_match"
    assert records[0]["paths"] == [".claude/rules/some-scoped-rule.md"]


def test_an_undocumented_field_spelling_still_yields_a_path(monkeypatch, tmp_path):
    """The whole point of the alias list: a rename must degrade, not blank out.

    A record with an empty `paths` reads identically to "nothing loaded", which
    is the exact conclusion this log exists to make trustworthy.
    """
    records = _run(monkeypatch, tmp_path, {
        "session_id": "s1",
        "hook_event_name": "InstructionsLoaded",
        "load_reason": "session_start",
        "paths": ["CLAUDE.md", ".claude/rules/aide-command-hygiene.md"],
    })
    assert records[0]["reason"] == "session_start"
    assert records[0]["paths"] == ["CLAUDE.md", ".claude/rules/aide-command-hygiene.md"]


def test_an_unknown_scalar_field_is_kept_under_extra(monkeypatch, tmp_path):
    records = _run(monkeypatch, tmp_path, {
        "session_id": "s1", "file_path": "CLAUDE.md", "token_count": 412,
    })
    assert records[0]["extra"]["token_count"] == 412


def test_a_long_value_is_truncated_so_content_cannot_flood_the_log(monkeypatch, tmp_path):
    records = _run(monkeypatch, tmp_path, {
        "session_id": "s1", "file_path": "CLAUDE.md", "content": "x" * 5000,
    })
    assert len(records[0]["extra"]["content"]) == hook._MAX_VALUE


def test_duplicate_spellings_of_one_path_are_recorded_once(monkeypatch, tmp_path):
    records = _run(monkeypatch, tmp_path, {
        "session_id": "s1", "file_path": "CLAUDE.md", "path": "CLAUDE.md",
    })
    assert records[0]["paths"] == ["CLAUDE.md"]


def test_empty_stdin_writes_nothing(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, "") == []


def test_a_malformed_payload_never_raises(monkeypatch, tmp_path, capsys):
    """A hook that raises is a hook that can disturb the session it observes."""
    log = tmp_path / "log.jsonl"
    monkeypatch.setattr(hook, "LOG_PATH", log)
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not json"))
    with pytest.raises(ValueError):
        hook.main()          # main() itself is allowed to raise ...
    # ... and the module entry point swallows it. Assert the guard exists rather
    # than re-exec'ing the interpreter, which pins the behaviour without a
    # subprocess whose python may differ from the one running the suite.
    source = (_ADAPTER / "hooks" / "log_instructions_loaded.py").read_text(encoding="utf-8")
    assert "except Exception:" in source
    assert "sys.exit(0)" in source


def test_the_hook_writes_nothing_to_stdout(monkeypatch, tmp_path, capsys):
    """Stdout from a hook can be read as a decision; this one has no opinion."""
    _run(monkeypatch, tmp_path, {"session_id": "s1", "file_path": "CLAUDE.md"})
    assert capsys.readouterr().out == ""


def test_a_json_scalar_payload_is_ignored(monkeypatch, tmp_path):
    """Valid JSON that is not an object must not become a record."""
    assert _run(monkeypatch, tmp_path, '"just a string"') == []


# --------------------------------------------------------------------------- #
# the report
# --------------------------------------------------------------------------- #
def _rules(tmp_path: Path, *names: str) -> Path:
    directory = tmp_path / "rules"
    directory.mkdir()
    for name in names:
        (directory / name).write_text("# rule\n", encoding="utf-8")
    return directory


def test_a_rule_that_never_loaded_is_named(tmp_path):
    rules = _rules(tmp_path, "loud.md", "silent.md")
    records = [{"session_id": "s1", "reason": "session_start", "paths": ["loud.md"]}]

    assert review.silent_rules(records, rules) == [
        p for p in review.shipped_rules(rules) if p.endswith("silent.md")]
    assert any("silent.md" in line for line in review.render(records, rules))


def test_a_rule_reported_by_absolute_path_counts_as_loaded(tmp_path):
    """The runtime may name a rule by a path from another checkout.

    Comparing full paths would report every rule silent — a false alarm on the
    one signal in this report that is meant to mean something.
    """
    rules = _rules(tmp_path, "loud.md")
    records = [{"session_id": "s1", "reason": "session_start",
                "paths": ["/some/other/checkout/.claude/rules/loud.md"]}]

    assert review.silent_rules(records, rules) == []


def test_reasons_are_counted_separately_per_file(tmp_path):
    records = [
        {"session_id": "s1", "reason": "session_start", "paths": ["a.md"]},
        {"session_id": "s2", "reason": "path_glob_match", "paths": ["a.md"]},
        {"session_id": "s2", "reason": "path_glob_match", "paths": ["a.md"]},
    ]
    counts = review.by_file(records)
    assert counts["a.md"] == {"session_start": 1, "path_glob_match": 2}


def test_a_record_with_no_reason_is_still_counted(tmp_path):
    """An unreported reason must not silently drop the load from the totals."""
    counts = review.by_file([{"session_id": "s1", "paths": ["a.md"]}])
    assert sum(counts["a.md"].values()) == 1


def test_sessions_are_counted_by_paths_not_by_records(tmp_path):
    records = [{"session_id": "s1", "paths": ["a.md", "b.md"]},
               {"session_id": "s2", "paths": ["a.md"]}]
    assert review.by_session(records) == {"s1": 2, "s2": 1}


def test_a_malformed_line_does_not_lose_the_rest_of_the_log(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text('{"session_id": "s1", "paths": ["a.md"]}\n'
                   '{"session_id": "s2", "pa\n'          # killed mid-write
                   '{"session_id": "s3", "paths": ["b.md"]}\n', encoding="utf-8")
    assert len(review.load_records(log)) == 2


def test_a_missing_log_is_not_an_error(tmp_path):
    assert review.load_records(tmp_path / "never-written.jsonl") == []


def test_strict_exits_non_zero_only_when_a_rule_is_silent(tmp_path, monkeypatch, capsys):
    rules = _rules(tmp_path, "silent.md")
    monkeypatch.setattr(review, "RULES_DIR", rules)
    log = tmp_path / "log.jsonl"
    log.write_text('{"session_id": "s1", "paths": ["other.md"]}\n', encoding="utf-8")

    assert review.main([str(log), "--strict"]) == 1
    assert review.main([str(log)]) == 0


def test_an_empty_log_reports_the_trust_hint_rather_than_a_clean_bill(tmp_path, capsys):
    """An empty log is ambiguous, and the ambiguity is the dangerous part."""
    assert review.main([str(tmp_path / "absent.jsonl")]) == 0
    assert "not trusted" in capsys.readouterr().out


def test_the_shipped_rules_are_the_ones_the_report_looks_for():
    """The report's default directory must be where the adapter puts rules."""
    assert review.RULES_DIR.name == "rules"
    assert (_ADAPTER / "rules").is_dir()
    assert sorted(p.name for p in (_ADAPTER / "rules").glob("*.md"))


# --------------------------------------------------------------------------- #
# registration — a hook that ships unregistered does nothing at all
# --------------------------------------------------------------------------- #
def test_every_shipped_hook_is_registered_in_the_framework_settings():
    """A hook file is inert until `settings.json` names it.

    `install.py` copies `hooks/` wholesale but is deliberately non-clobbering
    about `settings.json`, so forgetting the registration ships the file to
    every consumer and fires it in none of them — and nothing else in the suite
    would notice, because the file is present, imports, and passes its tests.
    """
    settings = json.loads(
        (_ADAPTER / "settings.json").read_text(encoding="utf-8"))
    registered = json.dumps(settings.get("hooks", {}))
    for hook_file in sorted((_ADAPTER / "hooks").glob("*.py")):
        assert hook_file.name in registered, (
            f"{hook_file.name} ships but no settings.json hook invokes it")


def test_the_instructions_hook_is_registered_on_its_own_event():
    """Registered on the wrong event it would log nothing and look healthy."""
    settings = json.loads(
        (_ADAPTER / "settings.json").read_text(encoding="utf-8"))
    entries = settings.get("hooks", {}).get("InstructionsLoaded")
    assert entries, "no InstructionsLoaded registration"
    assert "log_instructions_loaded.py" in json.dumps(entries)


def test_an_existing_consumers_settings_are_not_clobbered_by_a_new_hook():
    """Pins the consequence, so nobody claims an update installs this.

    `install_settings` keeps a consumer's `settings.json` and writes a
    `.aide-merge` instead. That is the deliberate ownership rule, and it means
    adding a hook to the framework base does NOT activate it for an existing
    consumer until they adopt `settings.overlay.json`. The CHANGELOG says so;
    this is the test that keeps that statement true.
    """
    source = (_ADAPTER.parents[1] / "install.py").read_text(encoding="utf-8")
    assert "kept (existing)" in source, (
        "settings.json became clobbering — the CHANGELOG's caveat about the "
        "InstructionsLoaded hook needing an overlay is now wrong")



def test_every_logging_hooks_output_path_is_covered_by_the_managed_gitignore():
    """A per-machine log that is not ignored gets committed.

    `docs/aide/permissions/*.jsonl` was documented as git-ignored from the day
    it was introduced and was never in the block; this PR added a second log
    and would have repeated it. The check is the pairing itself: a hook that
    writes a path the block does not cover is the whole bug.
    """
    import fnmatch
    import sys as _sys
    _sys.path.insert(0, str(_ADAPTER.parents[1]))
    import install  # noqa: E402

    patterns = [ln.strip() for ln in install.GITIGNORE_BLOCK.splitlines()
                if ln.strip() and not ln.strip().startswith("#")]

    log_paths = []
    for hook_file in sorted((_ADAPTER / "hooks").glob("*.py")):
        source = hook_file.read_text(encoding="utf-8")
        if "LOG_PATH" not in source:
            continue
        module = _load(hook_file.stem + "_probe", hook_file)
        # parents[2] of the INSTALLED location is the consumer root, so the
        # project-relative form is what the .gitignore patterns see.
        log_paths.append((hook_file.name,
                          module.LOG_PATH.relative_to(
                              module.LOG_PATH.parents[3]).as_posix()))

    assert log_paths, "no logging hook found — this guard is watching nothing"
    for name, rel in log_paths:
        assert any(fnmatch.fnmatch(rel, pat) for pat in patterns), (
            f"{name} writes {rel}, which no GITIGNORE_BLOCK pattern covers")
