"""A malformed ``aide.toml`` must fail loudly, identically, on every Python.

``aide.toml`` states the project's facts — where source lives, the git mode, the
test command. If it cannot be parsed, continuing on defaults means scoping the
builder at the wrong directory and reporting success, so ``load_config`` refuses.

Before this, the two parser paths disagreed on the same file: 3.11's ``tomllib``
raised an uncaught ``TOMLDecodeError`` (a traceback that never named the file),
while the 3.9 fallback *silently accepted* ``name = "unterminated`` and handed
back the truncated text as the value. These tests pin both to one behaviour.

Stdlib + pytest only.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
AIDE_PY = SCRIPTS_DIR / "aide.py"
sys.path.insert(0, str(SCRIPTS_DIR))
import aide  # noqa: E402  (path shim above)

GOOD = """\
[project]
name = "Demo"
source_dir = "src/pkg"

[git]
mode = "pr"
"""

UNTERMINATED = """\
[project]
name = "unterminated
source_dir = "src/pkg"
"""


def _repo(tmp_path: Path, text: str) -> Path:
    (tmp_path / "aide.toml").write_text(text, encoding="utf-8")
    return tmp_path


# --------------------------------------------------------------------------- #
# the happy paths still work
# --------------------------------------------------------------------------- #
def test_valid_config_still_loads(tmp_path):
    config = aide.load_config(_repo(tmp_path, GOOD))
    assert config["project"]["source_dir"] == "src/pkg"
    assert config["git"]["mode"] == "pr"


def test_missing_config_is_not_an_error(tmp_path):
    """Absent means 'unconfigured' — defaults are the right answer."""
    config = aide.load_config(tmp_path)
    assert config["project"]["source_dir"] == aide.DEFAULT_CONFIG["project"]["source_dir"]


def test_empty_config_is_not_an_error(tmp_path):
    config = aide.load_config(_repo(tmp_path, ""))
    assert config["project"]["source_dir"] == aide.DEFAULT_CONFIG["project"]["source_dir"]


def test_comments_and_blank_lines_are_not_an_error(tmp_path):
    text = "# leading comment\n\n[project]\n\n# another\nname = \"Demo\"  # trailing\n"
    assert aide.load_config(_repo(tmp_path, text))["project"]["name"] == "Demo"


def test_quoted_value_containing_a_hash_is_not_truncated(tmp_path):
    text = '[python]\ntest_command = "pytest -k \'a#b\'"\n'
    assert "#" in aide.load_config(_repo(tmp_path, text))["python"]["test_command"]


# --------------------------------------------------------------------------- #
# malformed -> ConfigError, never a silent default
# --------------------------------------------------------------------------- #
def test_unterminated_string_raises_rather_than_guessing(tmp_path):
    with pytest.raises(aide.ConfigError) as excinfo:
        aide.load_config(_repo(tmp_path, UNTERMINATED))

    message = str(excinfo.value)
    assert "aide.toml" in message          # names the file to go fix
    assert "malformed" in message


def test_the_error_names_the_offending_path(tmp_path):
    root = _repo(tmp_path, UNTERMINATED)
    with pytest.raises(aide.ConfigError) as excinfo:
        aide.load_config(root)

    assert str(root / "aide.toml") in str(excinfo.value)


def test_malformed_config_never_returns_defaults(tmp_path):
    """The regression: a wrong-but-plausible config is worse than a refusal."""
    with pytest.raises(aide.ConfigError):
        aide.load_config(_repo(tmp_path, UNTERMINATED))


def test_fallback_parser_rejects_what_it_used_to_misread():
    """`_parse_toml` is the 3.9 path that silently produced 'unterminated'."""
    with pytest.raises(aide.ConfigError):
        aide._parse_toml(UNTERMINATED)

    assert aide._parse_toml(GOOD)["project"]["name"] == "Demo"


@pytest.mark.parametrize("value", [
    'name = "closed"',
    "name = 'single closed'",
    "queue_cap = 10",
    "clarify = assume",
    "flag = true",
    'path = "C:/has/slashes"',
    'msg = "he said \'hi\'"',
])
def test_well_formed_values_are_not_rejected(value):
    """The strictness must not fire on anything legitimate."""
    assert aide._parse_toml(f"[loop]\n{value}\n")


@pytest.mark.parametrize("value", [
    'name = "open',
    "name = 'open",
])
def test_unterminated_variants_are_rejected(value):
    with pytest.raises(aide.ConfigError):
        aide._parse_toml(f"[project]\n{value}\n")


def test_error_reports_the_line_number():
    with pytest.raises(aide.ConfigError) as excinfo:
        aide._parse_toml('[project]\nname = "Demo"\nsource_dir = "open\n')

    assert "line 3" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# what the user actually sees at the CLI
# --------------------------------------------------------------------------- #
def test_cli_reports_cleanly_without_a_traceback(tmp_path):
    _repo(tmp_path, UNTERMINATED)

    res = subprocess.run([sys.executable, str(AIDE_PY), "--repo", str(tmp_path), "check"],
                         capture_output=True, text=True, encoding="utf-8")

    assert res.returncode == 2
    assert "Traceback" not in (res.stderr or "")
    assert "error:" in (res.stderr or "")
    assert "aide.toml" in (res.stderr or "")


def test_cli_does_not_refuse_a_valid_config(tmp_path):
    """Guard against the refusal firing on a good file.

    `check` still fails here — the scaffold has no progress.md — but it must fail
    on *that*, having read the config fine, rather than on the config itself.
    """
    _repo(tmp_path, GOOD)
    (tmp_path / "docs" / "aide").mkdir(parents=True)

    res = subprocess.run([sys.executable, str(AIDE_PY), "--repo", str(tmp_path), "check"],
                         capture_output=True, text=True, encoding="utf-8")

    combined = (res.stdout or "") + (res.stderr or "")
    assert "malformed" not in combined
    assert "progress.md" in combined      # got past config, into the real work
