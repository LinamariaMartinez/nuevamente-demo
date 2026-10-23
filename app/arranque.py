"""Arranque para Streamlit Community Cloud.

Streamlit Cloud corre un solo proceso: el de Streamlit. Con ARRANCAR_BACKEND=1, este módulo prende el
backend FastAPI en un hilo de ese mismo proceso (127.0.0.1:PUERTO_BACKEND), una sola vez por proceso.
Antes pasa los secretos de Streamlit al entorno y deja la llave de OCI en un archivo, porque el backend
la lee desde OCI_KEY_FILE y en Streamlit Cloud los secretos son texto.

En local no cambia nada: sin ARRANCAR_BACKEND, la interfaz usa la API de URL_API como siempre.
"""

import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import urllib.request

import streamlit as st

ESPERA_MAXIMA_SEGUNDOS = 60


def _secretos_a_entorno():
    """Copia los secretos de primer nivel a os.environ sin pisar lo que ya exista."""
    try:
        for clave, valor in st.secrets.items():
            if isinstance(valor, str):
                os.environ.setdefault(clave, valor)
    except Exception:
        # En local puede no haber secrets.toml: se usa el .env.
        pass


def _llave_oci_a_archivo():
    """Si la llave llega como texto (OCI_KEY_CONTENT), la escribe en un archivo temporal."""
    contenido = os.getenv("OCI_KEY_CONTENT", "").strip()
    if not contenido or os.getenv("OCI_KEY_FILE"):
        return
    ruta = Path(tempfile.gettempdir()) / "nuevamente_oci_key.pem"
    ruta.write_text(contenido + "\n")
    ruta.chmod(0o600)
    os.environ["OCI_KEY_FILE"] = str(ruta)


def _puerto():
    return int(os.getenv("PUERTO_BACKEND", "8000"))


def _backend_responde():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{_puerto()}/health", timeout=2) as respuesta:
            return respuesta.status == 200
    except Exception:
        return False


def _puerto_libre():
    with socket.socket() as conexion:
        return conexion.connect_ex(("127.0.0.1", _puerto())) != 0


def _admin_demo():
    """Crea el admin de ADMIN_DEMO_USUARIO / ADMIN_DEMO_CONTRASENA si no existe.

    Temporal: lo reemplaza el script de datos de la demo de Backend.
    """
    usuario = os.getenv("ADMIN_DEMO_USUARIO", "").strip()
    contrasena = os.getenv("ADMIN_DEMO_CONTRASENA", "")
    if not usuario or not contrasena:
        return
    from api.auth import hash_password
    from api.database import get_connection, init_db

    init_db()
    with get_connection() as conexion:
        if conexion.execute("SELECT 1 FROM usuarios WHERE usuario = ?", (usuario,)).fetchone():
            return
        conexion.execute(
            "INSERT INTO usuarios (nombre, usuario, contrasena_hash, rol, activo, debe_cambiar_contrasena) "
            "VALUES (?, ?, ?, 'admin', 1, 0)",
            ("Administración demo", usuario, hash_password(contrasena)),
        )


@st.cache_resource(show_spinner="Iniciando NuevaMente…")
def iniciar_backend():
    """Prende el backend si ARRANCAR_BACKEND=1. Devuelve True si quedó respondiendo."""
    _secretos_a_entorno()
    if os.getenv("ARRANCAR_BACKEND") != "1":
        return False
    _llave_oci_a_archivo()
    if not _puerto_libre():
        # Ya hay algo en el puerto (p. ej. el backend corrido aparte en local).
        return _backend_responde()

    import uvicorn
    from api.main import app

    _admin_demo()
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=_puerto(), log_level="warning"))
    threading.Thread(target=servidor.run, name="backend-fastapi", daemon=True).start()
    limite = time.monotonic() + ESPERA_MAXIMA_SEGUNDOS
    while time.monotonic() < limite:
        if _backend_responde():
            return True
        time.sleep(0.5)
    return False
