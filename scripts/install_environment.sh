#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo 'Uso: ./scripts/install_environment.sh /ruta/al/ejecutable/blender' >&2
  exit 2
fi

BLENDER="$1"
if [[ ! -x "$BLENDER" ]]; then
  echo "No se encontró un ejecutable de Blender en: $BLENDER" >&2
  exit 2
fi

"$BLENDER" --background --python "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install_environment.py"
echo 'Dependencias instaladas. Reinicia Blender antes de activar Analysis 3D.'
