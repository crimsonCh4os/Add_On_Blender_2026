# Tools for monitoring and analysing 3D modelling processes in Blender
# Copyright (C) 2026 María Molina Goyena
# SPDX-License-Identifier: GPL-3.0-or-later

"""Private dependency management for Analysis 3D.

The add-on starts in a lightweight bootstrap mode until NumPy and Matplotlib
can be imported successfully. Dependency checks run in a separate Python
process so a broken NumPy installation cannot contaminate Blender's process or
prevent the repair panel from loading.
"""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Iterable

ADDON_DIR = Path(__file__).resolve().parent
SITE_PACKAGES_DIR = ADDON_DIR / "site-packages"
REQUIREMENTS_FILE = ADDON_DIR / "requirements.txt"
REQUIRED_MODULES = ("numpy", "matplotlib")


def _python_executable() -> Path:
    """Return Blender's bundled Python executable instead of blender.exe.

    Inside Blender, ``sys.executable`` can point to the Blender application.
    ``sys.prefix`` points to the bundled Python runtime, whose executable is
    required for ``python -m pip`` and isolated dependency probes.
    """
    names = ("python.exe",) if os.name == "nt" else ("python3", "python")
    prefixes = (Path(sys.prefix), Path(getattr(sys, "base_prefix", sys.prefix)))
    candidates: list[Path] = []
    for prefix in prefixes:
        candidates.extend(prefix / "bin" / name for name in names)
    candidates.append(Path(sys.executable))

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError("Could not locate Blender's bundled Python executable.")


def add_local_site_packages(addon_dir: str | os.PathLike[str] | None = None) -> None:
    """Prepend only the current add-on private dependency directory."""
    base = Path(addon_dir).resolve() if addon_dir else ADDON_DIR
    private_dir = base / "site-packages"
    path = str(private_dir)
    # Remove stale private dependency paths from older Analysis3D folders.
    cleaned = []
    for entry in list(sys.path):
        try:
            normalized = os.path.normcase(os.path.abspath(entry))
        except Exception:
            cleaned.append(entry)
            continue
        lowered = normalized.lower().replace("\\", "/")
        if lowered.endswith("/site-packages") and "analysis3d" in lowered and normalized != os.path.normcase(os.path.abspath(path)):
            continue
        cleaned.append(entry)
    sys.path[:] = cleaned
    if private_dir.is_dir() and path not in sys.path:
        sys.path.insert(0, path)


def _probe_module(module: str) -> tuple[bool, str]:
    """Import one dependency in a clean child process.

    Testing in a child process is essential on Windows: a failed NumPy import
    can leave extension modules or DLLs loaded in Blender, making the old
    installation impossible to delete during repair.
    """
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(SITE_PACKAGES_DIR)!r}); "
        f"import {module}; "
        f"print(getattr({module}, '__version__', 'unknown'))"
    )
    try:
        result = subprocess.run(
            [str(_python_executable()), "-I", "-c", code],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONNOUSERSITE": "1"},
            timeout=90,
            check=False,
        )
    except Exception as exc:
        return False, f"Could not start dependency check: {exc}"

    if result.returncode == 0:
        return True, (result.stdout or "").strip()

    detail = (result.stderr or result.stdout or "Import failed").strip()
    return False, detail[-1200:]


@lru_cache(maxsize=8)
def _cached_dependency_diagnostics(modules: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    """Probe dependencies once and cache the result for UI redraws."""
    diagnostics: list[tuple[str, str]] = []
    for module in modules:
        ok, detail = _probe_module(module)
        if not ok:
            diagnostics.append((module, detail))
    return tuple(diagnostics)


def invalidate_dependency_cache() -> None:
    """Force the next dependency status request to run new probes."""
    _cached_dependency_diagnostics.cache_clear()


def dependency_diagnostics(
    modules: Iterable[str] = REQUIRED_MODULES, *, force: bool = False
) -> dict[str, str]:
    """Return import errors for missing or broken dependencies.

    Results are cached because Blender may redraw a panel many times per
    second. Without caching, every redraw starts two external Python processes.
    """
    normalized = tuple(str(module) for module in modules)
    if force:
        invalidate_dependency_cache()
    return dict(_cached_dependency_diagnostics(normalized))


def missing_dependencies(
    modules: Iterable[str] = REQUIRED_MODULES, *, force: bool = False
) -> list[str]:
    """Return dependencies that are absent *or cannot be imported*."""
    return list(dependency_diagnostics(modules, force=force).keys())


def dependencies_available(*, force: bool = False) -> bool:
    return not missing_dependencies(force=force)


def ensure_modules(modules: Iterable[str], *, install: bool = False) -> list[str]:
    """Compatibility wrapper retained for older add-on code."""
    missing = missing_dependencies(modules)
    if install and missing:
        install_dependencies()
        return missing_dependencies(modules)
    return missing


def _run_python_module(module: str, args: list[str]) -> None:
    command = [str(_python_executable()), "-m", module, *args]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "Command failed").strip()
        raise RuntimeError(detail[-4000:])


def _ensure_pip() -> None:
    check = subprocess.run(
        [str(_python_executable()), "-m", "pip", "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    if check.returncode == 0:
        return
    _run_python_module("ensurepip", ["--upgrade"])


def _remove_private_dependencies() -> None:
    """Remove every previous private installation before reinstalling."""
    if not SITE_PACKAGES_DIR.exists():
        return
    try:
        shutil.rmtree(SITE_PACKAGES_DIR)
    except Exception as exc:
        raise RuntimeError(
            "Could not remove the previous dependency folder. Close every Blender "
            "window, delete the add-on's site-packages folder manually, reopen "
            f"Blender and try again. Original error: {exc}"
        ) from exc


def install_dependencies() -> None:
    """Perform a clean, explicit installation into the add-on folder."""
    if not REQUIREMENTS_FILE.is_file():
        raise FileNotFoundError(f"requirements.txt not found: {REQUIREMENTS_FILE}")

    _remove_private_dependencies()
    SITE_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_pip()

    _run_python_module(
        "pip",
        [
            "install",
            "--upgrade",
            "--force-reinstall",
            "--no-cache-dir",
            "--disable-pip-version-check",
            "--target",
            str(SITE_PACKAGES_DIR),
            "--requirement",
            str(REQUIREMENTS_FILE),
        ],
    )

    importlib.invalidate_caches()
    invalidate_dependency_cache()
    diagnostics = dependency_diagnostics(force=True)
    if diagnostics:
        details = "\n\n".join(f"{name}: {error}" for name, error in diagnostics.items())
        raise RuntimeError("Dependency verification failed:\n" + details)
