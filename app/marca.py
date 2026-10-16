"""Archivos de la marca NuevaMente (logo e ícono)."""

from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
LOGO = ASSETS / "logo_nuevamente.svg"  # fondo claro: pantalla de Iniciar sesión
LOGO_MENU = ASSETS / "logo_nuevamente_menu.svg"  # menú lateral, que es oscuro en los dos modos
ICONO = ASSETS / "icono_nuevamente.svg"
# Favicon en PNG: Safari y otros navegadores no muestran favicons SVG
FAVICON = ASSETS / "icono_nuevamente.png"
