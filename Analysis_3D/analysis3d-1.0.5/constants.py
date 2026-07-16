# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender
# Copyright (C) 2026 María Molina Goyena
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

"""Configuración centralizada del add-on.

Evita magic numbers repartidos por el código y permite exponer los umbrales en UI.
"""

DEFAULT_BREAK_SPEED = 0.01
DEFAULT_MAX_REASONABLE_SPEED = 20.0
SPHERE_INSTANCING_THRESHOLD = 250
SELECTED_COLOR_PALETTE = "ibm_color_blind_safe"


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    """Convierte un color hexadecimal #RRGGBB a una tupla RGBA normalizada."""
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")

    r = int(value[0:2], 16) / 255.0
    g = int(value[2:4], 16) / 255.0
    b = int(value[4:6], 16) / 255.0
    return (r, g, b, alpha)


# IBM Color Blind Safe Palette.
# Buena opción por defecto para diferenciar series sin depender solo de rojo/verde.
IBM_COLOR_BLIND_SAFE = [
    _hex_to_rgba("#648FFF"),  # azul
    _hex_to_rgba("#785EF0"),  # violeta
    _hex_to_rgba("#DC267F"),  # magenta
    _hex_to_rgba("#FE6100"),  # naranja
    _hex_to_rgba("#FFB000"),  # amarillo
]


# Viridis: paleta perceptualmente uniforme.
# Útil para gradientes, progresiones e intensidades.
VIRIDIS = [
    _hex_to_rgba("#440154"),
    _hex_to_rgba("#482878"),
    _hex_to_rgba("#3E4989"),
    _hex_to_rgba("#31688E"),
    _hex_to_rgba("#26828E"),
    _hex_to_rgba("#1F9E89"),
    _hex_to_rgba("#35B779"),
    _hex_to_rgba("#6DCD59"),
    _hex_to_rgba("#B4DE2C"),
    _hex_to_rgba("#FDE725"),
]


# Inferno: paleta perceptualmente uniforme de alto contraste.
# Útil cuando se quiere más contraste visual entre valores bajos y altos.
INFERNO = [
    _hex_to_rgba("#000004"),
    _hex_to_rgba("#1B0C41"),
    _hex_to_rgba("#4A0C6B"),
    _hex_to_rgba("#781C6D"),
    _hex_to_rgba("#A52C60"),
    _hex_to_rgba("#CF4446"),
    _hex_to_rgba("#ED6925"),
    _hex_to_rgba("#FB9B06"),
    _hex_to_rgba("#F7D13D"),
    _hex_to_rgba("#FCFFA4"),
]


# Plasma: vivid purple-to-yellow gradient.
PLASMA = [
    _hex_to_rgba("#0D0887"), _hex_to_rgba("#46039F"),
    _hex_to_rgba("#7201A8"), _hex_to_rgba("#9C179E"),
    _hex_to_rgba("#BD3786"), _hex_to_rgba("#D8576B"),
    _hex_to_rgba("#ED7953"), _hex_to_rgba("#FB9F3A"),
    _hex_to_rgba("#FDCA26"), _hex_to_rgba("#F0F921"),
]

# Magma: dark purple-to-pale yellow gradient.
MAGMA = [
    _hex_to_rgba("#000004"), _hex_to_rgba("#180F3D"),
    _hex_to_rgba("#440F76"), _hex_to_rgba("#721F81"),
    _hex_to_rgba("#9E2F7F"), _hex_to_rgba("#CD4071"),
    _hex_to_rgba("#F1605D"), _hex_to_rgba("#FD9567"),
    _hex_to_rgba("#FECF92"), _hex_to_rgba("#FCFDBF"),
]

# Cividis: perceptually uniform and color-vision friendly.
CIVIDIS = [
    _hex_to_rgba("#00204C"), _hex_to_rgba("#123570"),
    _hex_to_rgba("#3B496C"), _hex_to_rgba("#575D6D"),
    _hex_to_rgba("#707173"), _hex_to_rgba("#898578"),
    _hex_to_rgba("#A59C74"), _hex_to_rgba("#C3B369"),
    _hex_to_rgba("#E1CC55"), _hex_to_rgba("#FFE945"),
]

# Turbo: broad high-contrast rainbow palette.
TURBO = [
    _hex_to_rgba("#30123B"), _hex_to_rgba("#4145AB"),
    _hex_to_rgba("#4675ED"), _hex_to_rgba("#39A2FC"),
    _hex_to_rgba("#1BCFD4"), _hex_to_rgba("#24EFA5"),
    _hex_to_rgba("#61FC6C"), _hex_to_rgba("#A4FC3C"),
    _hex_to_rgba("#E1DD37"), _hex_to_rgba("#F9A31B"),
    _hex_to_rgba("#F45B0C"), _hex_to_rgba("#B51F09"),
]

# Coolwarm: diverging blue-to-red palette with a neutral centre.
COOLWARM = [
    _hex_to_rgba("#3B4CC0"), _hex_to_rgba("#5977E3"),
    _hex_to_rgba("#7B9FF9"), _hex_to_rgba("#A3C2FE"),
    _hex_to_rgba("#C9D7F0"), _hex_to_rgba("#E6D7CF"),
    _hex_to_rgba("#F3B79B"), _hex_to_rgba("#EE8468"),
    _hex_to_rgba("#D65244"), _hex_to_rgba("#B40426"),
]


PALETTES = {
    "ibm_color_blind_safe": IBM_COLOR_BLIND_SAFE,
    "viridis": VIRIDIS,
    "inferno": INFERNO,
    "plasma": PLASMA,
    "magma": MAGMA,
    "cividis": CIVIDIS,
    "turbo": TURBO,
    "coolwarm": COOLWARM,
}


def _extremes_to_center(
    palette: list[tuple[float, float, float, float]],
) -> list[tuple[float, float, float, float]]:
    """Order colors from opposite extremes towards the centre.

    Example indices for six colors: 0, 5, 1, 4, 2, 3.
    """
    ordered = []
    left = 0
    right = len(palette) - 1
    while left <= right:
        ordered.append(palette[left])
        if left != right:
            ordered.append(palette[right])
        left += 1
        right -= 1
    return ordered


def _build_color_families(
    palette: list[tuple[float, float, float, float]],
    family_size: int = 4,
) -> list[list[tuple[float, float, float, float]]]:
    """Agrupa una paleta plana en familias de color.

    Cada CSV recibe una familia y sus métricas usan colores de esa familia.
    Si la última familia queda incompleta, se completa reutilizando colores
    desde el inicio de la paleta.
    """
    if not palette:
        return [[(1.0, 1.0, 1.0, 1.0)]]

    families = []
    for i in range(0, len(palette), family_size):
        family = list(palette[i:i + family_size])

        while len(family) < family_size:
            family.append(palette[len(family) % len(palette)])

        families.append(family)

    return families


ACTIVE_PALETTE = _extremes_to_center(PALETTES.get(SELECTED_COLOR_PALETTE, IBM_COLOR_BLIND_SAFE))

# Familias cromáticas: cada CSV recibe una familia y las métricas de ese CSV
# usan variantes de la misma familia para conservar asociación visual.
COLOR_FAMILIES = _build_color_families(ACTIVE_PALETTE, family_size=4)

# Paleta plana de compatibilidad para usos antiguos.
COLORBLIND_SAFE_PALETTE = [color for family in COLOR_FAMILIES for color in family]


def get_palette(name: str | None = None) -> list[tuple[float, float, float, float]]:
    """Return a palette ordered from its extremes towards its centre."""
    palette = PALETTES.get(
        name or SELECTED_COLOR_PALETTE,
        IBM_COLOR_BLIND_SAFE,
    )
    return _extremes_to_center(list(palette))


def get_color_families(name: str | None = None, family_size: int = 4) -> list[list[tuple[float, float, float, float]]]:
    """Devuelve familias cromáticas para la paleta solicitada."""
    return _build_color_families(get_palette(name), family_size=family_size)
