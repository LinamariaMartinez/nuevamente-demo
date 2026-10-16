"""Archivos de la marca NuevaMente (logo e ícono)."""

from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
LOGO = ASSETS / "logo_nuevamente.svg"  # fondo claro: pantalla de Iniciar sesión
LOGO_MENU = ASSETS / "logo_nuevamente_menu.svg"  # menú lateral, que es oscuro en los dos modos
ICONO = ASSETS / "icono_nuevamente.svg"
# Favicon en PNG: Safari y otros navegadores no muestran favicons SVG
FAVICON = ASSETS / "icono_nuevamente.png"


def logo_principal(tipo_tema):
    """Logo grande de la landing y de Iniciar sesión. `tipo_tema` es st.context.theme.type ("light", "dark" o None).

    En oscuro va la versión clara: el texto verde #205E58 no se leería. Si se cambia el tema en Settings, el logo
    se actualiza en el siguiente clic (Streamlit no vuelve a correr la página al cambiar el tema).
    """
    return LOGO_MENU if tipo_tema == "dark" else LOGO
