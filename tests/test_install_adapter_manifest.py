"""`--update` retires adapter files the framework has dropped — by manifest.

The defect (issue #85, step 1): `copy_tree` overwrites and adds but never
deletes, and `prune_stale` covers `.aide/` only, so a file removed from
`adapters/<name>/` stayed live in every consumer after `--update` — and
`--check` reported "up to date" over it. The prune cannot simply be extended
to `.claude/`: those are directories a project legitimately adds its own
agents, skills and rules to, and "absent from the source" would delete them.

So the installer records what it wrote — `.aide/adapter-manifest.txt`, one
consumer-relative POSIX path per line — and an update removes only a
*recorded* path the adapter no longer ships. A consumer's own file is never
recorded, so it is never a candidate. `RETIRED_ADAPTER_PATHS` bootstraps the
consumers installed before the manifest existed.

Two roots are used below: the real framework, and a copy of it whose adapter
ships one file more. Installing from the copy and updating from the real tree
is what "the adapter dropped a file" looks like from a consumer.

Stdlib + pytest only; `install.py` is imported as a module and driven through
`main()`, never a subprocess (conventions §6).
"""
from __future__ import annotations

import codecs
import shutil
import sys
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRAMEWORK_ROOT))
import install  # noqa: E402  (path shim above)

REAL_ADAPTER = FRAMEWORK_ROOT / "adapters" / "claude"

#: Files a later release might drop, one per shape the adapter ships: a flat
#: rule, and a skill that lives in a directory of its own.
DROPPED = {
    ".claude/rules/aide-retired-by-test.md": "# a rule a later release drops\n",
    ".claude/skills/aide-retired-by-test/SKILL.md": "# a skill a later release drops\n",
}


def _manifest(target: Path) -> Path:
    return target / ".aide" / install.ADAPTER_MANIFEST


def _manifest_lines(target: Path) -> list:
    return install.read_adapter_manifest(target / ".aide")


def _control_files(target: Path) -> list:
    """Every file under `.claude/<control dir>/`, consumer-relative, POSIX."""
    out = []
    for name in install.ADAPTER_CONTROL:
        root = target / ".claude" / name
        if root.is_dir():
            out += [p.relative_to(target).as_posix()
                    for p in root.rglob("*") if p.is_file()]
    return sorted(out)


def _install(target: Path) -> None:
    target.mkdir(exist_ok=True)
    assert install.main(["--into", str(target), "--yes"]) == 0


def _framework_that_also_ships(tmp_path: Path, monkeypatch, extra: dict) -> Path:
    """Point `install` at a copy of this framework whose adapter ships *extra*.

    Copied, not symlinked: Windows may not be able to create a link, and the
    point is a tree the real one has since moved on from.
    """
    root = tmp_path / "framework"
    junk = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(FRAMEWORK_ROOT / "core", root / "core", ignore=junk)
    shutil.copytree(REAL_ADAPTER, root / "adapters" / "claude", ignore=junk)
    for rel, body in extra.items():
        path = root / "adapters" / rel.replace(".claude/", "claude/", 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    monkeypatch.setattr(install, "FRAMEWORK_ROOT", root)
    return root


def _installed_from_an_older_adapter(tmp_path: Path, monkeypatch) -> Path:
    """A consumer installed from a tree that shipped `DROPPED`, with `install`
    pointed back at the real tree — i.e. the framework has dropped them."""
    _framework_that_also_ships(tmp_path, monkeypatch, DROPPED)
    target = tmp_path / "consumer"
    _install(target)
    for rel in DROPPED:
        assert (target / rel).is_file(), f"{rel}: the older adapter did not ship it"
        assert rel in _manifest_lines(target), f"{rel}: written but not recorded"
    monkeypatch.setattr(install, "FRAMEWORK_ROOT", FRAMEWORK_ROOT)
    return target


# --------------------------------------------------------------------------- #
# the manifest — what it lists and how it is written
# --------------------------------------------------------------------------- #
def test_a_fresh_install_records_exactly_the_control_files_it_wrote(tmp_path: Path):
    """Not `settings.json` (merged, not copied), nothing outside the control
    directories, nothing missing — the list is what the retirement trusts."""
    target = tmp_path / "consumer"
    _install(target)

    listed = _manifest_lines(target)
    assert listed, "an install wrote no manifest"
    assert listed == _control_files(target)
    assert ".claude/settings.json" not in listed
    assert install.ADAPTER_INSTALL_DIR == ".claude"   # the consumer path, literally
    assert all(line.startswith(".claude/") for line in listed)
    assert (target / ".claude" / "rules" / "aide-command-hygiene.md").is_file()
    assert ".claude/rules/aide-command-hygiene.md" in listed


def test_the_manifest_is_posix_lf_and_bom_free_on_every_platform(tmp_path: Path):
    """The file is read on whichever machine runs the next update. A `\\` or
    a CRLF from a Windows writer would make every line miss on the next read,
    and a miss is a file that is never retired — silently."""
    target = tmp_path / "consumer"
    _install(target)

    raw = _manifest(target).read_bytes()
    assert not raw.startswith(codecs.BOM_UTF8)
    assert b"\r" not in raw
    assert b"\\" not in raw
    assert raw.endswith(b"\n")
    lines = raw.decode("utf-8").split("\n")[:-1]
    assert lines[0].startswith("#"), "the header comment names the adapter"
    assert "claude" in lines[0]
    body = lines[1:]
    assert body == sorted(body) and len(body) == len(set(body))


def test_the_writer_sorts_and_deduplicates(tmp_path: Path):
    aide = tmp_path / ".aide"
    aide.mkdir()
    install.write_adapter_manifest(
        aide, "claude", [".claude/rules/b.md", ".claude/rules/a.md", ".claude/rules/b.md"], [])
    assert install.read_adapter_manifest(aide) == [".claude/rules/a.md", ".claude/rules/b.md"]


def test_the_reader_tolerates_a_consumers_editor(tmp_path: Path):
    """A BOM, CRLFs and blank lines are what a Windows editor leaves behind.
    Any of them turning a listed path into an unlisted one is a retirement
    that never happens."""
    aide = tmp_path / ".aide"
    aide.mkdir()
    (aide / install.ADAPTER_MANIFEST).write_bytes(
        codecs.BOM_UTF8 + b"# header\r\n.claude/rules/a.md\r\n\r\n  .claude/rules/b.md  \r\n")
    assert install.read_adapter_manifest(aide) == [".claude/rules/a.md", ".claude/rules/b.md"]


def test_no_manifest_reads_as_nothing_to_retire(tmp_path: Path):
    """Every consumer installed before this change is in this state."""
    assert install.read_adapter_manifest(tmp_path / "never-installed") == []


def test_an_update_from_the_same_tree_is_a_no_op_for_the_manifest(tmp_path: Path, capsys):
    target = tmp_path / "consumer"
    _install(target)
    before = _manifest(target).read_bytes()
    capsys.readouterr()

    assert install.main(["--into", str(target), "--update"]) == 0

    assert _manifest(target).read_bytes() == before
    assert "no longer ships" not in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# retirement — a dropped file goes, a consumer's own file stays
# --------------------------------------------------------------------------- #
def test_update_removes_what_the_adapter_dropped_and_reports_it(
        tmp_path: Path, monkeypatch, capsys):
    target = _installed_from_an_older_adapter(tmp_path, monkeypatch)
    capsys.readouterr()

    assert install.main(["--into", str(target), "--update"]) == 0

    for rel in DROPPED:
        assert not (target / rel).exists(), f"{rel} survived the update"
        assert rel not in _manifest_lines(target), f"{rel} still recorded"
    out = capsys.readouterr().out
    assert f"Removed {len(DROPPED)} file(s)" in out
    tail = out.split(f"Removed {len(DROPPED)} file(s)")[1]
    assert all(Path(rel).name in tail for rel in DROPPED), out
    assert "'claude' adapter" in tail


def test_a_skill_directory_the_adapter_dropped_goes_whole_but_rules_stays(
        tmp_path: Path, monkeypatch):
    """Empty parents are removed only where the adapter has no such directory.
    `.claude/rules/` still ships, so it must survive even when every file the
    update removed lived inside it."""
    target = _installed_from_an_older_adapter(tmp_path, monkeypatch)

    assert install.main(["--into", str(target), "--update"]) == 0

    assert not (target / ".claude" / "skills" / "aide-retired-by-test").exists()
    assert (target / ".claude" / "rules").is_dir()
    assert (target / ".claude" / "skills").is_dir()
    assert (target / ".claude" / "rules" / "aide-command-hygiene.md").is_file()


def test_a_consumers_own_files_in_the_same_directories_survive(
        tmp_path: Path, monkeypatch):
    """The reason this is a manifest and not a prune. Each is absent from the
    source exactly like a dropped file; the difference is that nobody
    recorded writing it."""
    target = _installed_from_an_older_adapter(tmp_path, monkeypatch)
    own = [
        target / ".claude" / "skills" / "my-skill" / "SKILL.md",
        target / ".claude" / "rules" / "project-own.md",
        target / ".claude" / "agents" / "my-agent.md",
        target / ".claude" / "skills" / "aide-retired-by-test" / "NOTES.md",
    ]
    for path in own:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("mine\n", encoding="utf-8")

    assert install.main(["--into", str(target), "--update"]) == 0

    for path in own:
        assert path.is_file(), f"{path.relative_to(target).as_posix()}: eaten by the update"
        assert path.relative_to(target).as_posix() not in _manifest_lines(target)
    assert not (target / ".claude" / "skills" / "aide-retired-by-test" / "SKILL.md").exists()
    assert not (target / ".claude" / "rules" / "aide-retired-by-test.md").exists()


def test_a_dropped_file_the_consumer_already_deleted_is_not_an_event(
        tmp_path: Path, monkeypatch, capsys):
    target = _installed_from_an_older_adapter(tmp_path, monkeypatch)
    for rel in DROPPED:
        (target / rel).unlink()
    capsys.readouterr()

    assert install.main(["--into", str(target), "--check"]) == 0
    assert install.main(["--into", str(target), "--update"]) == 0
    out = capsys.readouterr().out
    assert "no longer ships" not in out
    for rel in DROPPED:
        assert rel not in _manifest_lines(target)


# --------------------------------------------------------------------------- #
# --check — reports, exits non-zero, writes nothing
# --------------------------------------------------------------------------- #
def _snapshot(target: Path) -> list:
    return sorted((p.relative_to(target).as_posix(),
                   p.read_bytes() if p.is_file() else None)
                  for p in target.rglob("*"))


def test_check_names_a_dropped_file_exits_nonzero_and_writes_nothing(
        tmp_path: Path, monkeypatch, capsys):
    target = _installed_from_an_older_adapter(tmp_path, monkeypatch)
    before = _snapshot(target)
    capsys.readouterr()

    rc = install.main(["--into", str(target), "--check"])

    assert rc == 1, "a pending deletion is something to act on before updating"
    out = capsys.readouterr().out
    for rel in DROPPED:
        assert Path(rel).name in out, f"{rel} not named by --check"
    assert "--update" in out
    assert "installed from the adapter" in out
    assert "part of the engine" not in out, (
        "the per-file line says adapter; the closing line must not say engine")
    assert _snapshot(target) == before, "--check wrote something"


def test_check_is_clean_once_the_update_has_run(tmp_path: Path, monkeypatch, capsys):
    target = _installed_from_an_older_adapter(tmp_path, monkeypatch)
    assert install.main(["--into", str(target), "--update"]) == 0
    capsys.readouterr()

    assert install.main(["--into", str(target), "--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_the_preview_equals_the_act(tmp_path: Path, monkeypatch):
    """What `--check` lists is what `--update` removes, one function each."""
    target = _installed_from_an_older_adapter(tmp_path, monkeypatch)
    candidates = install.read_adapter_manifest(target / ".aide")

    preview = install.stale_adapter_files(REAL_ADAPTER, target, candidates)
    assert preview, "nothing stale — the setup proves nothing"
    removed = install.retire_adapter_files(REAL_ADAPTER, target, candidates, [])

    assert removed == preview


# --------------------------------------------------------------------------- #
# the bootstrap list — pre-manifest consumers
# --------------------------------------------------------------------------- #
def test_the_bootstrap_list_retires_a_file_when_there_is_no_manifest(
        tmp_path: Path, monkeypatch, capsys):
    """A consumer installed before the manifest existed has nothing to read,
    so a release that retires a file must name it in `RETIRED_ADAPTER_PATHS`
    or every such consumer keeps it forever."""
    target = tmp_path / "consumer"
    _install(target)
    _manifest(target).unlink()                    # what a pre-manifest consumer looks like
    old = target / ".claude" / "rules" / "aide-retired-before-manifests.md"
    old.write_text("# shipped by an earlier release\n", encoding="utf-8")
    monkeypatch.setitem(install.RETIRED_ADAPTER_PATHS, "claude",
                        (".claude/rules/aide-retired-before-manifests.md",))
    capsys.readouterr()

    assert install.main(["--into", str(target), "--check"]) == 1
    assert old.name in capsys.readouterr().out
    assert old.is_file(), "--check must never write"

    assert install.main(["--into", str(target), "--update"]) == 0
    assert not old.exists()
    assert _manifest(target).is_file(), "the update leaves the consumer with a manifest"
    assert old.relative_to(target).as_posix() not in _manifest_lines(target)


def test_the_bootstrap_list_is_harmless_where_the_adapter_still_ships_the_file(
        tmp_path: Path, monkeypatch):
    """Consulted in addition to the manifest, so an entry that is wrong — or
    merely early — must not delete a file the adapter still delivers."""
    target = tmp_path / "consumer"
    _install(target)
    kept = target / ".claude" / "rules" / "aide-command-hygiene.md"
    assert kept.is_file()
    monkeypatch.setitem(install.RETIRED_ADAPTER_PATHS, "claude",
                        (".claude/rules/aide-command-hygiene.md",))

    assert install.main(["--into", str(target), "--check"]) == 0
    assert install.main(["--into", str(target), "--update"]) == 0
    assert kept.is_file()


def test_every_bootstrap_entry_is_a_control_path_the_adapter_no_longer_ships():
    """A populated entry must be one the retirement can act on and one the
    adapter has really dropped — an entry naming a live file is a deletion of
    something the same update just installed."""
    for adapter, entries in install.RETIRED_ADAPTER_PATHS.items():
        adapter_dir = FRAMEWORK_ROOT / "adapters" / adapter
        assert adapter_dir.is_dir(), adapter
        for rel in entries:
            posix = install._adapter_control_path(rel)
            assert posix is not None, f"{adapter}: {rel!r} is not under .claude/<control dir>/"
            assert not adapter_dir.joinpath(*posix.parts[1:]).exists(), (
                f"{adapter}: {rel} is still shipped; it cannot be retired")


# --------------------------------------------------------------------------- #
# a control directory retired whole — still retired, file by file
# --------------------------------------------------------------------------- #
#: Every control directory name the installer has EVER shipped. Append-only
#: history, frozen here rather than derived: it grows only when a name is
#: retired, and never shrinks — a name deleted from `ADAPTER_CONTROL` without
#: entering the retired half of `HISTORIC_CONTROL_DIRS` is caught by it,
#: where `set(ADAPTER_CONTROL) <= set(HISTORIC_CONTROL_DIRS)` alone would
#: stay true (the historic set is built from the live tuple).
EVER_SHIPPED_CONTROL_DIRS = frozenset(
    {"agents", "commands", "hooks", "rules", "scripts", "skills"})


def test_the_historic_control_set_holds_every_name_ever_shipped():
    """A name that leaves `ADAPTER_CONTROL` without entering the historic
    set makes every recorded path under it unparseable — see the tests below
    for what that costs. The literal is what makes this fail: it is the one
    record of the names that does not move when the tuple does."""
    assert set(install.HISTORIC_CONTROL_DIRS) >= EVER_SHIPPED_CONTROL_DIRS
    assert set(install.ADAPTER_CONTROL) <= set(install.HISTORIC_CONTROL_DIRS)


def _release_that_dropped_rules_whole(tmp_path: Path, monkeypatch) -> None:
    """Point `install` at a tree where `rules/` is gone — from the adapter
    directory AND from `ADAPTER_CONTROL`, the way a release retiring the whole
    channel would do it — with the name kept in the historic set."""
    root = _framework_that_also_ships(tmp_path, monkeypatch, {})
    shutil.rmtree(root / "adapters" / "claude" / "rules")
    shrunk = tuple(n for n in install.ADAPTER_CONTROL if n != "rules")
    monkeypatch.setattr(install, "ADAPTER_CONTROL", shrunk)
    monkeypatch.setattr(install, "HISTORIC_CONTROL_DIRS", shrunk + ("rules",))


def test_a_control_directory_retired_whole_is_still_retired_file_by_file(
        tmp_path: Path, monkeypatch, capsys):
    """The reviewer's repro. Validating manifest lines against the CURRENT
    `ADAPTER_CONTROL` meant that once `rules/` left the tuple every line under
    it failed to parse: `--check` exited 0 "up to date" over three rules still
    armed in every session, `--update` left them in place, and the manifest
    rebuilt at step 8b no longer listed them — so re-adding the name later
    recovered nothing. The historic set is what keeps them parseable.

    "File by file" needs more than one file. Since 1.27.0 the adapter ships
    a single rule (the two scoped ones became section skills), so a second
    one is planted the way an earlier release would have left it: on disk
    and in the manifest."""
    target = tmp_path / "consumer"
    _install(target)                                   # this release ships rules/
    planted = target / ".claude" / "rules" / "aide-second-rule-by-test.md"
    planted.write_text("# a rule an earlier release shipped\n", encoding="utf-8")
    _manifest(target).write_bytes(_manifest(target).read_bytes()
                                  + b".claude/rules/aide-second-rule-by-test.md\n")
    rules = sorted((target / ".claude" / "rules").glob("*.md"))
    assert len(rules) >= 2, "nothing installed under rules/; the rest proves nothing"
    _release_that_dropped_rules_whole(tmp_path, monkeypatch)
    capsys.readouterr()

    assert install.main(["--into", str(target), "--check"]) == 1
    out = capsys.readouterr().out
    for rule in rules:
        assert rule.name in out, f"{rule.name}: --check said nothing"
        assert rule.is_file(), "--check must never write"

    assert install.main(["--into", str(target), "--update"]) == 0

    for rule in rules:
        assert not rule.exists(), f"{rule.name} survived the retirement of rules/"
    assert not (target / ".claude" / "rules").exists(), (
        "emptied, and the adapter ships no rules/ — the directory goes too")
    assert not any(line.startswith(".claude/rules/") for line in _manifest_lines(target))
    assert install.main(["--into", str(target), "--check"]) == 0


def test_a_retired_directorys_files_stay_recorded_until_they_are_gone(
        tmp_path: Path, monkeypatch, capsys):
    """The manifest must carry a path under a retired directory for as long
    as the file exists — a removal that failed included — or the next
    `--update` has nothing to retry and `--check` nothing to name."""
    target = tmp_path / "consumer"
    _install(target)
    stuck = target / ".claude" / "rules" / "aide-command-hygiene.md"
    assert stuck.is_file()
    _release_that_dropped_rules_whole(tmp_path, monkeypatch)
    real_unlink = Path.unlink

    def refuse_one(self, *args, **kwargs):
        if self.name == stuck.name:
            raise PermissionError(13, "Permission denied")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", refuse_one)
    capsys.readouterr()

    assert install.main(["--into", str(target), "--update"]) == 0

    assert stuck.is_file(), "injection did not take"
    assert "could not be removed" in capsys.readouterr().out
    assert ".claude/rules/aide-command-hygiene.md" in _manifest_lines(target)
    assert (target / ".claude" / "rules").is_dir()   # not empty, so not removed
    monkeypatch.setattr(Path, "unlink", real_unlink)
    assert install.main(["--into", str(target), "--check"]) == 1
    assert install.main(["--into", str(target), "--update"]) == 0
    assert not stuck.exists()
    assert ".claude/rules/aide-command-hygiene.md" not in _manifest_lines(target)


def test_a_directory_gone_from_the_tuple_but_not_the_source_is_still_retired(
        tmp_path: Path, monkeypatch, capsys):
    """Half-retired: the name left `ADAPTER_CONTROL` while
    `adapters/claude/rules/` still sat in the source tree. Asking the source
    alone — "does the adapter still hold this path?" — said yes to every
    file, so `--check` exited 0, `--update` kept the files, and the manifest
    lines were dropped while the files existed. Copied by nothing is retired,
    whatever the source tree still holds."""
    target = tmp_path / "consumer"
    _install(target)
    rules = sorted((target / ".claude" / "rules").glob("*.md"))
    assert len(rules) >= 2, "nothing installed under rules/; the rest proves nothing"
    root = _framework_that_also_ships(tmp_path, monkeypatch, {})
    assert (root / "adapters" / "claude" / "rules").is_dir()   # left behind
    shrunk = tuple(n for n in install.ADAPTER_CONTROL if n != "rules")
    monkeypatch.setattr(install, "ADAPTER_CONTROL", shrunk)
    monkeypatch.setattr(install, "HISTORIC_CONTROL_DIRS", shrunk + ("rules",))
    capsys.readouterr()

    assert install.main(["--into", str(target), "--check"]) == 1
    out = capsys.readouterr().out
    for rule in rules:
        assert rule.name in out, f"{rule.name}: --check said nothing"
        assert rule.is_file(), "--check must never write"

    assert install.main(["--into", str(target), "--update"]) == 0

    for rule in rules:
        assert not rule.exists(), f"{rule.name} survived a half-retired rules/"
    assert not any(line.startswith(".claude/rules/") for line in _manifest_lines(target))
    assert install.main(["--into", str(target), "--check"]) == 0


def test_a_bootstrap_entry_under_a_retired_directory_is_accepted():
    """The escape hatch for pre-manifest consumers has to open for a retired
    directory too, or the guard that refuses everything else refuses it."""
    assert install._adapter_control_path(".claude/rules/x.md") is not None
    for name in install.HISTORIC_CONTROL_DIRS:
        assert install._adapter_control_path(f".claude/{name}/x.md") is not None, name


# --------------------------------------------------------------------------- #
# a control directory the adapter still ships survives being emptied
# --------------------------------------------------------------------------- #
def test_a_control_directory_the_adapter_ships_empty_survives_the_same_run(
        tmp_path: Path, monkeypatch):
    """The guard in `retire_adapter_files` — do not remove a directory the
    adapter still ships — was untested: `.claude/rules/` always held shipped
    rules, so the emptiness check broke the loop before the guard was asked.
    Here the old release shipped `commands/only-in-the-old-release.md` and the
    new one ships `commands/` EMPTY: step 2 creates `.claude/commands/`, step
    8a empties it, and without the guard the same run would then delete the
    directory it had just installed."""
    _framework_that_also_ships(tmp_path / "old", monkeypatch, {
        ".claude/commands/only-in-the-old-release.md": "# gone next release\n"})
    target = tmp_path / "consumer"
    _install(target)
    commands = target / ".claude" / "commands"
    assert (commands / "only-in-the-old-release.md").is_file()

    new = _framework_that_also_ships(tmp_path / "new", monkeypatch, {})
    for path in (new / "adapters" / "claude" / "commands").iterdir():
        path.unlink()                                   # ships the directory, empty
    assert install.main(["--into", str(target), "--update"]) == 0

    assert not (commands / "only-in-the-old-release.md").exists()
    assert not any(commands.iterdir()), "every command retired: the directory is empty"
    assert commands.is_dir(), (
        "the adapter still ships commands/; the update must not delete what "
        "its own step 2 created")


# --------------------------------------------------------------------------- #
# safety — the retirement never leaves the control directories
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("rel", [
    ".claude/settings.json",
    ".claude/settings.overlay.json",
    ".claude/rules",
    ".claude/rules/",
    ".aide/VERSION",
    "aide.toml",
    ".claude/rules/../settings.json",
    ".claude/../aide.toml",
    "../.claude/rules/x.md",
    "/etc/passwd",
    "C:/Windows/x.md",
    ".claude/notes/x.md",
])
def test_a_path_outside_the_control_directories_is_never_a_candidate(rel: str):
    assert install._adapter_control_path(rel) is None


@pytest.mark.parametrize("rel", [
    ".claude/rules/x.md",
    ".claude/skills/aide-x/SKILL.md",
    ".claude\\agents\\x.md",          # a Windows writer's separators
    ".claude/./rules/x.md",           # `.` normalises away; still inside
])
def test_a_path_inside_a_control_directory_is_a_candidate(rel: str):
    assert install._adapter_control_path(rel) is not None


def test_a_hostile_manifest_cannot_reach_settings_json(tmp_path: Path):
    """The manifest is a file in someone else's repo. Whatever it says, only a
    file inside `.claude/<control dir>/` can be removed."""
    target = tmp_path / "consumer"
    _install(target)
    settings = target / ".claude" / "settings.json"
    toml = target / "aide.toml"
    (target / ".aide" / install.ADAPTER_MANIFEST).write_bytes(
        b"# tampered\n.claude/settings.json\n.claude/rules/../settings.json\n"
        b"../aide.toml\n.aide/VERSION\n")

    assert install.main(["--into", str(target), "--update"]) == 0

    assert settings.is_file() and toml.is_file()
    assert (target / ".aide" / "VERSION").is_file()


def test_a_removal_that_fails_is_logged_and_kept_in_the_manifest(
        tmp_path: Path, monkeypatch, capsys):
    """Same tolerance as the prune: one unremovable file (Windows, held open)
    must not abort the update. It stays recorded so the next `--update`
    tries again and `--check` keeps naming it, rather than being forgotten."""
    target = _installed_from_an_older_adapter(tmp_path, monkeypatch)
    real_unlink = Path.unlink

    def refuse_one(self, *args, **kwargs):
        if self.name == "aide-retired-by-test.md":
            raise PermissionError(13, "Permission denied")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", refuse_one)
    capsys.readouterr()

    assert install.main(["--into", str(target), "--update"]) == 0

    stuck = target / ".claude" / "rules" / "aide-retired-by-test.md"
    assert stuck.is_file(), "injection did not take"
    out = capsys.readouterr().out
    assert "could not be removed" in out
    assert ".claude/rules/aide-retired-by-test.md" in _manifest_lines(target)
    assert not (target / ".claude" / "skills" / "aide-retired-by-test").exists(), (
        "the retirement stopped early")
    monkeypatch.setattr(Path, "unlink", real_unlink)
    assert install.main(["--into", str(target), "--check"]) == 1
