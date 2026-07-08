"""Adapter/installer conformance for the Claude usage probe.

Two invariants live here rather than in the engine's ``core/scripts/tests/test_loop.py``,
because both are *consumer/adapter* facts, not engine facts:

1. **Probe conformance** — the shipped ``adapters/claude/usage_probe.py`` exposes the
   engine-facing ``get_usage(cfg) -> dict | None`` contract and degrades to ``None``
   (no network) when there is no OAuth token.
2. **Installer co-location** — after ``install.py`` materialises a consumer, the probe
   sits next to ``loop.py`` in ``.aide/loop/`` so the engine's ``_import_probe_module()``
   resolves it. The engine (``core/``) and the Claude probe (``adapters/claude/``) are
   deliberately *separate*; only ``install.py`` co-locates them, which is why this
   invariant is verified at the installer level.

Modules are loaded by path (they don't live on the package path). Stdlib + pytest only.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
ADAPTER_PROBE = FRAMEWORK_ROOT / "adapters" / "claude" / "usage_probe.py"
INSTALL_PY = FRAMEWORK_ROOT / "install.py"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# --------------------------------------------------------------------------- #
# 1. probe conformance (against the source adapter file, no install needed)
# --------------------------------------------------------------------------- #
def test_shipped_probe_exposes_get_usage():
    probe = _load(ADAPTER_PROBE, "adapter_usage_probe")
    assert callable(getattr(probe, "get_usage", None)), "probe must expose get_usage(cfg)"


def test_probe_degrades_to_none_without_token(tmp_path: Path):
    probe = _load(ADAPTER_PROBE, "adapter_usage_probe")
    # A credentials path that does not exist -> no token -> None, and crucially no
    # network call (the engine treats None as "run on time cadence").
    cfg = {"credentials_path": str(tmp_path / "no-such-credentials.json")}
    assert probe.get_usage(cfg) is None


# --------------------------------------------------------------------------- #
# 2. installer co-location (the consumer-only invariant)
# --------------------------------------------------------------------------- #
def test_installer_colocates_probe_next_to_loop(tmp_path: Path):
    install = _load(INSTALL_PY, "aide_install")
    target = tmp_path / "consumer"
    target.mkdir()

    rc = install.main(["--adapter", "claude", "--into", str(target), "--yes"])
    assert rc == 0

    loop_py = target / ".aide" / "loop" / "loop.py"
    probe_py = target / ".aide" / "loop" / "usage_probe.py"
    assert loop_py.is_file(), "install must drop the engine loop into .aide/loop/"
    assert probe_py.is_file(), "install must co-locate the Claude probe next to loop.py"

    # The consumer's engine resolves the co-located probe (not the degraded fallback):
    # _import_probe_module() finds the sibling usage_probe.py and it exposes get_usage.
    loop = _load(loop_py, "consumer_loop")
    module = loop._import_probe_module()
    assert module is not None, "engine failed to resolve the co-located probe"
    assert callable(getattr(module, "get_usage", None))

    # And load_probe("anthropic-oauth") yields a working callable that stays offline
    # (bogus credentials -> None) rather than crashing or hitting the network.
    probe = loop.load_probe({
        "usage_probe": "anthropic-oauth",
        "credentials_path": str(tmp_path / "no-such-credentials.json"),
    })
    assert probe() is None
