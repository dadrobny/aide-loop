"""The channel that puts framework rules into a session's default context.

`conventions.md` is read only when something points at it. That holds for an
agent spec in the unattended loop and fails for an interactive session, where a
person and the runtime produce durable artifacts — commit messages, issue
bodies, `insights.md` entries — with no agent spec in play. ADAPTER-SPEC §7
closes it: the adapter declares the file its runtime loads by default and that
runtime's import syntax, and the installer keeps one line in that file pointing
at the engine's `AGENT-CONTEXT.md`.

These cover the installer half — the declaration reader, the three write paths
(create / append / already-linked), and `--check` reporting a missing import as
drift. Stdlib + pytest only; `install.py` is imported as a module.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)

CLAUDE_ADAPTER = FRAMEWORK_ROOT / "adapters" / "claude"
IMPORT_LINE = "@.aide/AGENT-CONTEXT.md"
BOM = "\ufeff"  # U+FEFF, spelled out: invisible in a diff otherwise


def _import_lines(path: Path) -> int:
    """How many times the import line itself appears.

    Not a substring count: the generated body names the path in its prose so the
    file explains itself, and the installer matches whole lines precisely so
    that mention cannot read as a second import.
    """
    body = path.read_text(encoding=install.CONSUMER_ENCODING)
    return sum(1 for ln in body.splitlines() if ln.strip() == IMPORT_LINE)


def _consumer(tmp_path: Path) -> Path:
    target = tmp_path / "consumer"
    target.mkdir()
    return target


def _install(target: Path, *extra: str) -> int:
    return install.main(["--adapter", "claude", "--into", str(target), "--yes", *extra])


# --------------------------------------------------------------------------- #
# the declaration (ADAPTER-SPEC §7)
# --------------------------------------------------------------------------- #
def test_the_claude_adapter_declares_its_instruction_file_and_import_syntax():
    decl = json.loads((CLAUDE_ADAPTER / install.ADAPTER_DEFAULT_CONTEXT)
                      .read_text(encoding="utf-8"))
    assert decl["file"] == "CLAUDE.md"
    assert "{path}" in decl["import"]


def test_declaration_renders_the_import_line():
    assert install.default_context_declaration(CLAUDE_ADAPTER) == ("CLAUDE.md", IMPORT_LINE)


def test_an_adapter_that_declares_nothing_is_not_an_error(tmp_path: Path):
    """§7 is optional — a runtime with no default-context concept omits the
    file, and the installer must do nothing rather than fail."""
    assert install.default_context_declaration(tmp_path) is None


def test_a_malformed_declaration_degrades_to_nothing(tmp_path: Path):
    """An optional channel must not be able to fail an install. The drift
    report under --check is what surfaces a channel that never got linked."""
    for body in ('not json at all',
                 '{"import": "@{path}"}',            # no file
                 '{"file": "CLAUDE.md"}',            # no import syntax
                 '{"file": "", "import": "@{path}"}',
                 '{"file": "CLAUDE.md", "import": "@AGENT-CONTEXT.md"}'):  # no {path}
        (tmp_path / install.ADAPTER_DEFAULT_CONTEXT).write_text(body, encoding="utf-8")
        assert install.default_context_declaration(tmp_path) is None, body


def _fake_adapter(tmp_path: Path, file: str, syntax: str = "@{path}") -> Path:
    """An adapter declaring *file* — for the shapes this repo does not ship."""
    adapter = tmp_path / "adapter"
    adapter.mkdir(exist_ok=True)
    (adapter / install.ADAPTER_DEFAULT_CONTEXT).write_text(
        json.dumps({"file": file, "import": syntax}), encoding="utf-8")
    return adapter


def test_a_declared_path_that_escapes_the_repo_is_refused(tmp_path: Path):
    """§7's path is joined onto someone else's repo and the installer creates
    parent directories for it, so a path that is absolute or climbs out would
    have it writing where the consumer never asked. Degrades like any other
    malformed field rather than doing it."""
    for bad in ("/etc/instructions.md", "../outside.md", "a/../../outside.md",
                r"C:\Windows\instructions.md", "//host/share/x.md"):
        adapter = _fake_adapter(tmp_path, bad)
        assert install.default_context_declaration(adapter) is None, bad


def test_a_nested_declaration_is_allowed(tmp_path: Path):
    adapter = _fake_adapter(tmp_path, ".github/copilot-instructions.md")
    assert install.default_context_declaration(adapter) == (
        ".github/copilot-instructions.md", IMPORT_LINE)


def test_a_nested_declaration_creates_its_parent_directory(tmp_path: Path):
    """The directory a runtime keeps its instructions in need not exist yet."""
    target = _consumer(tmp_path)
    adapter = _fake_adapter(tmp_path, ".github/copilot-instructions.md")

    install.install_default_context(target, adapter, [])
    assert _import_lines(target / ".github" / "copilot-instructions.md") == 1


def test_a_nested_declaration_appends_to_an_existing_file(tmp_path: Path):
    target = _consumer(tmp_path)
    nested = target / ".github" / "copilot-instructions.md"
    nested.parent.mkdir(parents=True)
    nested.write_text("# Theirs\n", encoding="utf-8")
    adapter = _fake_adapter(tmp_path, ".github/copilot-instructions.md")

    install.install_default_context(target, adapter, [])
    body = nested.read_text(encoding="utf-8")
    assert body.startswith("# Theirs\n")
    assert _import_lines(nested) == 1


def test_drift_names_a_nested_file_by_its_whole_path(tmp_path: Path):
    """A basename leaves a nested declaration ambiguous about which file to
    repair — there may well be more than one `copilot-instructions.md`."""
    target = _consumer(tmp_path)
    adapter = _fake_adapter(tmp_path, ".github/copilot-instructions.md")

    drift = install.default_context_drift(target, adapter)
    assert ".github/copilot-instructions.md" in drift
    assert "is missing" in drift

    install.install_default_context(target, adapter, [])
    assert install.default_context_drift(target, adapter) is None


def test_an_adapter_declaring_nothing_reports_no_drift(tmp_path: Path):
    assert install.default_context_drift(_consumer(tmp_path), tmp_path / "none") is None


# --------------------------------------------------------------------------- #
# what a fresh install produces
# --------------------------------------------------------------------------- #
def test_the_engine_ships_agent_context(tmp_path: Path):
    target = _consumer(tmp_path)
    assert _install(target) == 0
    shipped = target / install.AGENT_CONTEXT_REL
    assert shipped.is_file()
    assert shipped.read_text(encoding="utf-8").strip()


def test_a_repo_with_no_instruction_file_gets_a_minimal_one(tmp_path: Path):
    """Creating it cannot clobber anything, and a silently absent channel is
    the failure mode the import exists to prevent."""
    target = _consumer(tmp_path)
    assert _install(target) == 0
    body = (target / "CLAUDE.md").read_text(encoding="utf-8")
    assert IMPORT_LINE in body.splitlines()


def test_the_created_file_says_which_line_the_installer_maintains(tmp_path: Path):
    """A consumer reading the generated file has to be able to tell which line
    an update will rewrite and which is theirs. Naming the import in the prose
    is safe because the installer matches whole lines, so the mention cannot
    read back as a second import."""
    target = _consumer(tmp_path)
    assert _install(target) == 0
    body = (target / "CLAUDE.md").read_text(encoding="utf-8")
    assert f"`{IMPORT_LINE}`" in body
    assert _import_lines(target / "CLAUDE.md") == 1


def test_agent_context_is_reachable_from_the_import_line(tmp_path: Path):
    """The link must resolve as written, from the repo root the runtime reads."""
    target = _consumer(tmp_path)
    assert _install(target) == 0
    line = next(l for l in (target / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
                if l.strip() == IMPORT_LINE)
    assert (target / line.strip().lstrip("@")).is_file()


# --------------------------------------------------------------------------- #
# what an existing instruction file gets
# --------------------------------------------------------------------------- #
def test_an_existing_file_keeps_everything_it_had(tmp_path: Path):
    """One line appended, nothing else touched — the project owns the rest."""
    target = _consumer(tmp_path)
    original = "# My project\n\nDo not reformat this.\n\n- a bullet\n"
    (target / "CLAUDE.md").write_text(original, encoding="utf-8")

    assert _install(target) == 0
    body = (target / "CLAUDE.md").read_text(encoding="utf-8")
    assert body.startswith(original)
    assert IMPORT_LINE in body.splitlines()


def test_the_import_lands_on_its_own_line_without_a_trailing_newline(tmp_path: Path):
    target = _consumer(tmp_path)
    (target / "CLAUDE.md").write_text("# My project", encoding="utf-8")

    assert _install(target) == 0
    lines = (target / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# My project"
    assert IMPORT_LINE in lines


def test_an_empty_instruction_file_gets_just_the_line(tmp_path: Path):
    """No leading blank lines to separate the import from nothing."""
    target = _consumer(tmp_path)
    (target / "CLAUDE.md").write_text("", encoding="utf-8")

    assert _install(target) == 0
    assert (target / "CLAUDE.md").read_text(encoding="utf-8") == IMPORT_LINE + "\n"


def test_linking_is_idempotent(tmp_path: Path):
    target = _consumer(tmp_path)
    assert _install(target) == 0
    first = (target / "CLAUDE.md").read_text(encoding="utf-8")

    assert _install(target, "--update") == 0
    second = (target / "CLAUDE.md").read_text(encoding="utf-8")
    assert first == second
    assert _import_lines(target / "CLAUDE.md") == 1


def test_update_links_a_consumer_installed_before_the_channel_existed(tmp_path: Path):
    """The reason this runs on --update and not only on a fresh install."""
    target = _consumer(tmp_path)
    (target / "CLAUDE.md").write_text("# Legacy\n", encoding="utf-8")

    assert _install(target, "--update") == 0
    assert IMPORT_LINE in (target / "CLAUDE.md").read_text(encoding="utf-8").splitlines()


def test_a_bom_prefixed_instruction_file_is_not_relinked(tmp_path: Path):
    """Windows editors prepend U+FEFF. Read as plain utf-8 the BOM survives into
    the first line, the existing import stops matching, and every run appends
    another copy."""
    target = _consumer(tmp_path)
    (target / "CLAUDE.md").write_text(BOM + IMPORT_LINE + "\n\n# Mine\n", encoding="utf-8")

    assert _install(target) == 0
    assert _import_lines(target / "CLAUDE.md") == 1


def test_a_prose_mention_is_not_an_import(tmp_path: Path):
    """Deliberately strict: the check is for the exact line, so what the
    installer maintains is a line it wrote, not a sentence it guessed at. A
    duplicate reference is harmless; a channel assumed present is not."""
    target = _consumer(tmp_path)
    (target / "CLAUDE.md").write_text(f"See {IMPORT_LINE} for the rules.\n", encoding="utf-8")

    assert _install(target) == 0
    lines = (target / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
    assert IMPORT_LINE in lines


# --------------------------------------------------------------------------- #
# --check reports a missing import as drift
# --------------------------------------------------------------------------- #
def test_check_passes_once_the_import_is_there(tmp_path: Path, capsys):
    target = _consumer(tmp_path)
    assert _install(target) == 0
    capsys.readouterr()

    assert install.main(["--into", str(target), "--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_check_reports_a_missing_import_as_drift(tmp_path: Path, capsys):
    target = _consumer(tmp_path)
    assert _install(target) == 0
    (target / "CLAUDE.md").write_text("# Mine only\n", encoding="utf-8")
    capsys.readouterr()

    assert install.main(["--into", str(target), "--check"]) == 1
    out = capsys.readouterr().out
    assert "CLAUDE.md" in out and install.AGENT_CONTEXT_REL in out
    assert "does not import" in out
    assert "--update" in out


def test_check_reports_drift_when_the_instruction_file_is_gone(tmp_path: Path, capsys):
    """A missing file and a file that lost the line are different repairs to
    reason about, so they read differently — "does not import" is a false
    description of a file that is not there."""
    target = _consumer(tmp_path)
    assert _install(target) == 0
    (target / "CLAUDE.md").unlink()
    capsys.readouterr()

    assert install.main(["--into", str(target), "--check"]) == 1
    out = capsys.readouterr().out
    assert install.AGENT_CONTEXT_REL in out
    assert "is missing" in out
    assert "does not import" not in out


def test_drift_on_an_ahead_consumer_does_not_advise_a_downgrade(tmp_path: Path, capsys):
    """Every other failing state repairs with `--update`. This one does not:
    the consumer's engine is newer than this checkout, so updating from here
    would roll it back to fix a missing line. The report has to say so, rather
    than fail with the generic advice or with none at all."""
    target = _consumer(tmp_path)
    assert _install(target) == 0
    (target / ".aide" / "VERSION").write_text("99.0.0\n", encoding="utf-8")
    (target / "CLAUDE.md").write_text("# Mine only\n", encoding="utf-8")
    capsys.readouterr()

    assert install.main(["--into", str(target), "--check"]) == 1
    out = capsys.readouterr().out
    assert "is AHEAD" in out
    assert install.AGENT_CONTEXT_REL in out
    assert "add the import by hand" in out
    assert f"--into {target} --update" not in out


def test_an_ahead_consumer_that_is_linked_still_passes(tmp_path: Path, capsys):
    """Being ahead is not itself a failure — only the missing import is."""
    target = _consumer(tmp_path)
    assert _install(target) == 0
    (target / ".aide" / "VERSION").write_text("99.0.0\n", encoding="utf-8")
    capsys.readouterr()

    assert install.main(["--into", str(target), "--check"]) == 0
    assert "is AHEAD" in capsys.readouterr().out


def test_the_created_file_matches_what_the_spec_says_it_holds(tmp_path: Path):
    """ADAPTER-SPEC §7 describes the created file as the import line plus a
    short note about which line an update rewrites. A spec that describes
    content the installer does not write is the drift this test exists to
    catch — it went unnoticed once already."""
    spec = (FRAMEWORK_ROOT / "adapters" / "ADAPTER-SPEC.md").read_text(encoding="utf-8")
    assert "holding the import line plus a two-sentence note" in spec

    target = _consumer(tmp_path)
    assert _install(target) == 0
    lines = [ln for ln in (target / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
             if ln.strip()]
    assert lines[0] == IMPORT_LINE
    assert len(lines) > 1, "the note the spec promises is missing"


def test_check_still_writes_nothing_when_it_reports_drift(tmp_path: Path):
    target = _consumer(tmp_path)
    assert _install(target) == 0
    (target / "CLAUDE.md").write_text("# Mine only\n", encoding="utf-8")
    before = {p: p.stat().st_mtime_ns for p in target.rglob("*") if p.is_file()}

    assert install.main(["--into", str(target), "--check"]) == 1
    after = {p: p.stat().st_mtime_ns for p in target.rglob("*") if p.is_file()}
    assert before == after


def test_a_missing_install_still_outranks_drift(tmp_path: Path, capsys):
    """Exit 2 means 'nothing installed here', and it must not be masked by the
    import check finding no instruction file either."""
    target = _consumer(tmp_path)
    assert install.main(["--into", str(target), "--check"]) == 2
    assert "no install found" in capsys.readouterr().err
