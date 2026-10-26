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


def _datos_demo():
    """Carga las cuentas y los temas de la demo con el script de Backend (scripts/crear_cuentas_demo.py).

    Usa claves fijas (DEMO_ADMIN_PASSWORD, DEMO_ESTUDIANTE_PASSWORD, DEMO_TEMPORAL_PASSWORD): así las cuentas
    que muestra la landing coinciden con la base. Streamlit Cloud borra el disco al reiniciar, y el script es
    idempotente, por eso corre en cada arranque. Si falla, el backend arranca igual y queda en el registro.
    """
    from api import database
    from scripts.crear_cuentas_demo import CUENTAS, TEMAS_DEMO, crear_cuentas

    faltan = [c.variable for c in CUENTAS if not os.getenv(c.variable)]
    if faltan:
        print(f"[arranque] Sin datos de la demo: faltan {', '.join(faltan)}", flush=True)
        return
    try:
        resultados = crear_cuentas(
            database.DB_PATH,  # la misma base que usa la API
            con_tema_demo=True,
            passwords={c.usuario: os.environ[c.variable] for c in CUENTAS},
            claves_fijas=True,
        )
    except Exception as exc:
        print(f"[arranque] No se cargaron los datos de la demo: {type(exc).__name__}: {str(exc)[:300]}", flush=True)
        return
    creadas = sum(r["creada"] for r in resultados)
    print(f"[arranque] Datos de la demo listos: {creadas} cuentas nuevas, {len(TEMAS_DEMO)} temas por sector", flush=True)


def _diagnostico_oci():
    """Deja en el registro si OCI quedó listo o por qué no (sin mostrar claves)."""
    faltan = [v for v in ("OCI_USER_OCID", "OCI_TENANCY_OCID", "OCI_FINGERPRINT", "OCI_KEY_FILE") if not os.getenv(v)]
    if faltan:
        print(f"[arranque] OCI sin configurar: faltan {', '.join(faltan)}", flush=True)
        return
    llave = Path(os.environ["OCI_KEY_FILE"])
    lineas = llave.read_text().splitlines() if llave.is_file() else []
    print(f"[arranque] Llave OCI: {len(lineas)} líneas, primera: {lineas[0][:31] if lineas else '(vacía)'}", flush=True)
    # Largos y prefijos (no son secretos) para detectar valores cortados, con espacios o cruzados
    for variable in ("OCI_USER_OCID", "OCI_TENANCY_OCID", "OCI_FINGERPRINT", "OCI_REGION"):
        valor = os.getenv(variable, "")
        print(f"[arranque] {variable}: {len(valor)} caracteres, empieza con {valor[:14]!r}", flush=True)
    try:
        import hashlib

        from cryptography.hazmat.primitives import serialization

        privada = serialization.load_pem_private_key(llave.read_bytes(), password=None)
        publica = privada.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        huella = ":".join(f"{b:02x}" for b in hashlib.md5(publica).digest())
        coincide = huella == os.getenv("OCI_FINGERPRINT", "").strip()
        print(f"[arranque] El fingerprint {'SÍ' if coincide else 'NO'} corresponde a la llave", flush=True)
    except Exception as exc:
        print(f"[arranque] No se pudo calcular el fingerprint de la llave: {type(exc).__name__}", flush=True)
    try:
        from oci_storage import OCIStorageManager

        OCIStorageManager().ensure_bucket_exists()
        print("[arranque] OCI listo: bucket verificado", flush=True)
    except Exception as exc:
        print(f"[arranque] OCI no disponible: {type(exc).__name__}: {str(exc)[:300]}", flush=True)


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

    _datos_demo()
    _diagnostico_oci()
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=_puerto(), log_level="warning"))
    threading.Thread(target=servidor.run, name="backend-fastapi", daemon=True).start()
    limite = time.monotonic() + ESPERA_MAXIMA_SEGUNDOS
    while time.monotonic() < limite:
        if _backend_responde():
            return True
        time.sleep(0.5)
    return False
