"""Ayudas compartidas por las pruebas de las páginas de la interfaz."""

from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
for ruta in (RAIZ / "src", RAIZ / "app"):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

from streamlit.testing.v1 import AppTest

from cliente_api import ClienteMock

APP_PAGINA = str(RAIZ / "tests" / "apps_interfaz" / "pagina_app.py")
CUENTAS = {"laura": "demo-estudiante", "mateo": "temporal-123", "admin": "demo-admin"}


def abrir_pagina(pagina, usuario="laura", cliente=None, estado=None):
    """Abre `pagina` ("modulo:funcion") con la sesión de `usuario` ya iniciada (None: sin sesión)."""
    cliente = cliente or ClienteMock()
    at = AppTest.from_file(APP_PAGINA, default_timeout=10)
    at.session_state["pagina"] = pagina
    at.session_state["cliente"] = cliente
    if usuario is not None:
        at.session_state["sesion"] = cliente.iniciar_sesion(usuario, CUENTAS[usuario])
    for clave, valor in (estado or {}).items():
        at.session_state[clave] = valor
    return at.run()


def textos(elementos):
    return [elemento.value for elemento in elementos]


def columnas_principales(at):
    """(izquierda, derecha) del diseño en dos columnas st.columns([1, 2])."""
    columnas = list(at.columns)
    j = next(i for i, c in enumerate(columnas) if abs(c.weight - 2 / 3) < 0.01)
    izquierda = next(c for c in reversed(columnas[:j]) if abs(c.weight - 1 / 3) < 0.01)
    return izquierda, columnas[j]
