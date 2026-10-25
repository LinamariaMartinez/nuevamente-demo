"""Cuentas reales para desarrollo: python -m scripts.crear_cuentas_demo --con-tema-demo.

Reutiliza el esquema y el hash del backend. Por defecto conserva las cuentas.
--claves-fijas sincroniza sus claves con la configuración, sin mostrarlas.
"""

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
from uuid import NAMESPACE_DNS, uuid5

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _id_documento(clave):
    # El contrato HTTP exige 32 caracteres hexadecimales para los documentos.
    return uuid5(NAMESPACE_DNS, f"demo.{clave}.nuevamente").hex


TEMA_DEMO = "demo-redes-oci"
DOCUMENTO_DEMO = _id_documento("redes-oci")
NOMBRE_TEMA = "Redes VCN en OCI"


@dataclass(frozen=True)
class TemaDemo:
    id_tema: str
    nombre: str
    descripcion: str
    nicho_sector: str
    documento_id: str
    documento_titulo: str
    archivo: str

    @property
    def fuente(self):
        return ROOT / "data" / self.archivo


# Un tema por sector del catálogo (src/schemas.py); el de redes va en General.
TEMAS_DEMO = (
    TemaDemo("demo-fintech", "Pagos inmediatos y fraude",
             "Manual operativo de pagos inmediatos y prevención de fraude.", "Fintech",
             _id_documento("fintech"), "Pagos inmediatos y prevención de fraude",
             "fintech_pagos_inmediatos_fraude.md"),
    TemaDemo("demo-salud", "Higiene de manos",
             "Protocolo de higiene de manos para el personal de la clínica.", "Salud",
             _id_documento("salud"), "Protocolo de higiene de manos",
             "salud_protocolo_higiene_manos.pdf"),
    TemaDemo("demo-ecommerce", "Devoluciones, retracto y garantías",
             "Manual de atención al cliente para devoluciones y garantías.", "E-commerce",
             _id_documento("ecommerce"), "Devoluciones, retracto, reversión del pago y garantías",
             "ecommerce_devoluciones_retracto_garantias.txt"),
    TemaDemo(TEMA_DEMO, NOMBRE_TEMA,
             "Guía de arquitectura de redes VCN en OCI.", "General",
             DOCUMENTO_DEMO, "Redes VCN en OCI",
             "tecnologia_redes_vcn_oci.md"),
)
IDS_TEMAS_DEMO = tuple(t.id_tema for t in TEMAS_DEMO)


@dataclass(frozen=True)
class CuentaDemo:
    usuario: str
    nombre: str
    rol: str
    temporal: bool
    variable: str


CUENTAS = (
    CuentaDemo("admin_demo", "Administración", "admin", False, "DEMO_ADMIN_PASSWORD"),
    CuentaDemo("estudiante_demo", "Estudiante", "estudiante", False, "DEMO_ESTUDIANTE_PASSWORD"),
    CuentaDemo("temporal_demo", "Estudiante con clave temporal", "estudiante", True, "DEMO_TEMPORAL_PASSWORD"),
)


def _preparar_documento(tema):
    from api.documents import extract_document

    raw = tema.fuente.read_bytes()
    filename, kind, pages = extract_document(tema.fuente.name, raw)
    return raw, filename, kind, pages


def _crear_tema_demo(conn, tema, documento):
    from api.database import utc_now

    raw, filename, kind, pages = documento
    existente = conn.execute("SELECT original FROM documentos WHERE id = ?", (tema.documento_id,)).fetchone()
    if existente is not None and existente["original"] != raw:
        raise ValueError(f"El documento {tema.documento_id} ya existe con otro contenido; no se sobrescribió.")
    fila = conn.execute("SELECT nombre FROM temas WHERE id_tema = ?", (tema.id_tema,)).fetchone()
    if fila is not None and fila["nombre"] != tema.nombre:
        raise ValueError(f"El tema {tema.id_tema} ya existe con otro nombre; no se sobrescribió.")
    if existente is None:
        conn.execute(
            """INSERT INTO documentos
            (id, documento_titulo, nombre_archivo, tipo, tamano_bytes, fragmentos_extraidos,
             creado_en, original, paginas_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tema.documento_id, tema.documento_titulo, filename, kind, len(raw), len(pages), utc_now(), raw,
             json.dumps([{"page_content": p.page_content, "metadata": p.metadata} for p in pages],
                        ensure_ascii=False)),
        )
    if fila is None:
        conn.execute(
            "INSERT INTO temas (id_tema, nombre, descripcion, nicho_sector) VALUES (?, ?, ?, ?)",
            (tema.id_tema, tema.nombre, tema.descripcion, tema.nicho_sector),
        )
    conn.execute(
        "INSERT OR IGNORE INTO tema_documentos (id_tema, documento_id, asociado_en) VALUES (?, ?, ?)",
        (tema.id_tema, tema.documento_id, utc_now()),
    )


def crear_cuentas(db_path=None, *, con_tema_demo=False, temas=(), passwords=None, claves_fijas=False):
    """Devuelve estado y clave de las cuentas nuevas; nunca recupera claves existentes.

    ``passwords`` mapea nombres de usuario a claves; si falta uno, se genera una
    clave aleatoria. Con ``claves_fijas`` se exigen las tres claves y se actualizan
    las distintas, revocando sus sesiones. No cambia roles, activación ni el
    estado de contraseña temporal. Toda la carga se confirma en una transacción,
    después de inicializar/migrar la base mediante el backend.
    """
    from api.auth import hash_password, verify_password
    from api.database import connect, init_db, resolve_db_path

    passwords = dict(passwords or {})
    permitidos = {c.usuario for c in CUENTAS}
    if passwords.keys() - permitidos:
        raise ValueError("Se recibieron contraseñas para cuentas desconocidas.")
    if claves_fijas:
        faltantes = [c.variable for c in CUENTAS if c.usuario not in passwords]
        if faltantes:
            raise ValueError("El modo de claves fijas requiere: " + ", ".join(faltantes))
    for usuario, password in passwords.items():
        if not isinstance(password, str) or len(password) < 12:
            raise ValueError(f"La contraseña de {usuario} debe tener al menos 12 caracteres.")
    temas = list(dict.fromkeys(temas))
    if any(not isinstance(t, str) or not t.strip() for t in temas):
        raise ValueError("Los identificadores de tema no pueden estar vacíos.")
    documentos = [(t, _preparar_documento(t)) for t in TEMAS_DEMO] if con_tema_demo else []
    path = resolve_db_path(db_path)
    init_db(path)
    resultados = []
    with connect(path) as conn:
        # Serializa ejecuciones simultáneas: comprobar e insertar es una sola operación.
        conn.execute("BEGIN IMMEDIATE")
        for id_tema in temas:
            if con_tema_demo and id_tema in IDS_TEMAS_DEMO:
                continue
            if conn.execute("SELECT 1 FROM temas WHERE id_tema = ?", (id_tema,)).fetchone() is None:
                raise ValueError(f"No existe el tema {id_tema}. No se crearon cuentas.")
        existentes = {}
        for cuenta in CUENTAS:
            row = conn.execute("SELECT * FROM usuarios WHERE usuario = ?", (cuenta.usuario,)).fetchone()
            if row is not None and row["rol"] != cuenta.rol:
                raise ValueError(f"{cuenta.usuario} ya existe con otro rol. No se modificaron cuentas.")
            existentes[cuenta.usuario] = row
        for tema, documento in documentos:
            _crear_tema_demo(conn, tema, documento)
        if con_tema_demo:
            temas = list(dict.fromkeys([*temas, *IDS_TEMAS_DEMO]))
        for cuenta in CUENTAS:
            row = existentes[cuenta.usuario]
            password = None
            actualizada = False
            if row is None:
                password = passwords.get(cuenta.usuario) or secrets.token_urlsafe(18)
                cursor = conn.execute(
                    """INSERT INTO usuarios
                    (nombre, usuario, contrasena_hash, rol, activo, debe_cambiar_contrasena)
                    VALUES (?, ?, ?, ?, 1, ?)""",
                    (cuenta.nombre, cuenta.usuario, hash_password(password), cuenta.rol, int(cuenta.temporal)),
                )
                id_usuario, activo, temporal = cursor.lastrowid, True, cuenta.temporal
            else:
                id_usuario = row["id_usuario"]
                activo, temporal = bool(row["activo"]), bool(row["debe_cambiar_contrasena"])
                if claves_fijas and not verify_password(passwords[cuenta.usuario], row["contrasena_hash"]):
                    conn.execute("UPDATE usuarios SET contrasena_hash = ? WHERE id_usuario = ?",
                                 (hash_password(passwords[cuenta.usuario]), id_usuario))
                    conn.execute("DELETE FROM sesiones WHERE id_usuario = ?", (id_usuario,))
                    actualizada = True
            if cuenta.rol == "estudiante":
                conn.executemany(
                    "INSERT OR IGNORE INTO usuario_temas (id_usuario, id_tema) VALUES (?, ?)",
                    [(id_usuario, t) for t in temas],
                )
            resultados.append({
                "usuario": cuenta.usuario, "rol": cuenta.rol, "creada": row is None,
                "activo": activo, "debe_cambiar_contrasena": temporal,
                "contrasena": None if claves_fijas else password, "clave_actualizada": actualizada,
            })
    return resultados


def main(argv=None):
    parser = argparse.ArgumentParser(description="Crea cuentas reales de prueba para los roles admin y estudiante.")
    parser.add_argument("--db", help="Ruta SQLite; por defecto NUEVAMENTE_DB_PATH de .env o storage/nuevamente.sqlite3.")
    parser.add_argument("--con-tema-demo", action="store_true", help="Carga los 4 documentos de demostración (uno por sector) y asigna sus temas a ambos estudiantes.")
    parser.add_argument("--tema", action="append", default=[], metavar="ID", help="Asigna un tema existente a ambos estudiantes; se puede repetir.")
    parser.add_argument("--claves-fijas", action="store_true",
                        help="Exige las tres DEMO_*_PASSWORD y sincroniza las claves demo existentes; no las imprime.")
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        from api.database import resolve_db_path

        passwords = {c.usuario: os.environ[c.variable] for c in CUENTAS if c.variable in os.environ}
        resultados = crear_cuentas(args.db, con_tema_demo=args.con_tema_demo, temas=args.tema,
                                   passwords=passwords, claves_fijas=args.claves_fijas)
    except ModuleNotFoundError as exc:
        print(f"Falta una dependencia ({exc.name}). Instala requirements.txt con el mismo Python.", file=sys.stderr)
        return 1
    except (ValueError, OSError, sqlite3.Error, RuntimeError) as exc:
        print(f"No se pudo completar la carga: {exc}", file=sys.stderr)
        return 1
    print(f"Base de datos: {resolve_db_path(args.db).resolve()}")
    for cuenta in resultados:
        estado = "CREADA" if cuenta["creada"] else "EXISTENTE (conservada)"
        if cuenta["clave_actualizada"]:
            estado = "CLAVE ACTUALIZADA (sesiones revocadas)"
        print(f"\n{cuenta['usuario']} | {cuenta['rol']} | {estado}")
        print(f"  Activa: {cuenta['activo']} | Cambio obligatorio: {cuenta['debe_cambiar_contrasena']}")
        if cuenta["creada"] and not args.claves_fijas:
            print(f"  Contraseña: {cuenta['contrasena']}")
    asignados = list(dict.fromkeys([*args.tema, *(IDS_TEMAS_DEMO if args.con_tema_demo else ())]))
    print("\nTemas asignados a ambos estudiantes: " + (", ".join(asignados) or "ninguno nuevo"))
    if args.claves_fijas:
        print("Claves sincronizadas con DEMO_*_PASSWORD; consulta su configuración, no los logs.")
    else:
        print("Guarda las claves nuevas: no se vuelven a mostrar. Las cuentas existentes conservan su contraseña.")
    print("Frontend: MODO_API=http y URL_API=http://127.0.0.1:8000; la API debe usar esta misma base.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
