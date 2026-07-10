"""Instala las dependencias en el Python incluido con Blender.

Uso recomendado:
    blender --background --python scripts/install_environment.py

No ejecuta instalaciones al activar el add-on: la modificación del entorno es
una acción explícita del desarrollador o usuario.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def bundled_python() -> Path:
    """Localiza el intérprete Python incluido en la instalación de Blender."""
    prefix = Path(sys.prefix)
    candidates = [
        prefix / "bin" / "python.exe",
        prefix / "bin" / "python3.exe",
        prefix / "bin" / "python3",
        prefix / "bin" / f"python{sys.version_info.major}.{sys.version_info.minor}",
        prefix / "python.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "No se encontró el Python interno de Blender bajo sys.prefix="
        f"{prefix}. Consulta docs/DEVELOPER_GUIDE.md para la instalación manual."
    )


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    requirements = repo_root / "requirements.txt"
    if not requirements.is_file():
        raise FileNotFoundError(f"No existe {requirements}")

    python = bundled_python()
    print(f"Python de Blender: {python}")
    print(f"Dependencias: {requirements}")

    env = os.environ.copy()
    subprocess.run([str(python), "-m", "ensurepip", "--upgrade"], check=True, env=env)
    subprocess.run(
        [str(python), "-m", "pip", "install", "--upgrade", "pip"],
        check=True,
        env=env,
    )
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(requirements)],
        check=True,
        env=env,
    )

    subprocess.run(
        [str(python), "-c", "import numpy, matplotlib; print('Entorno instalado correctamente')"],
        check=True,
        env=env,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
