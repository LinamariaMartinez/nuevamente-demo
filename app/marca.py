"""Archivos de la marca NuevaMente (logo e ícono) y cuál usar según el tema."""

from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
LOGO_CLARO = ASSETS / "logo_nuevamente.svg"
LOGO_OSCURO = ASSETS / "logo_nuevamente_oscuro.svg"
ICONO = ASSETS / "icono_nuevamente.svg"


def logo_para(tipo_tema):
    """`tipo_tema` es st.context.theme.type ("light", "dark" o None si el navegador no lo informó)."""
    return LOGO_OSCURO if tipo_tema == "dark" else LOGO_CLARO
