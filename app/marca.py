"""Archivos de la marca NuevaMente (logo e ícono)."""

from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
LOGO = ASSETS / "logo_nuevamente.svg"  # fondo claro (desde la v2.4 ninguna pantalla lo usa)
LOGO_MENU = ASSETS / "logo_nuevamente_menu.svg"  # fondos oscuros: menú lateral y panel de Iniciar sesión
ICONO = ASSETS / "icono_nuevamente.svg"
# Favicon en PNG: Safari y otros navegadores no muestran favicons SVG
FAVICON = ASSETS / "icono_nuevamente.png"

