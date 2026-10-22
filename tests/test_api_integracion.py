"""Pruebas de integración F06 + F08: autorización por tema, fuentes e historial por usuario.

El generador se sustituye por un doble de prueba; no se llama a Gemini.
"""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from api import database
from api.auth import hash_password
from api.main import create_app, get_generator
from oci_storage import OCIConfigurationError, OCIStorageManager
from schemas import DEFAULT_DETAIL, DEFAULT_NICHE
from tests.test_oci_storage import FakeOCIClient

PASSWORD = "clave-segura-123"
DOC_TEXT = "Python es un lenguaje interpretado. Las listas guardan elementos ordenados. " * 8


def educational_response(request, approved=True):
    score = 0.9 if approved else 0.5
    return {
        "status": "exito" if approved else "requiere_revision",
        "metadatos": {
            "tiempo_estimado_estudio_minutos": 10,
            "conceptos_clave": ["listas"],
            "prerrequisitos": [],
            "perfil_aplicado": request.perfil_destinatario,
            "formato_generado": "Resumen",
            "nicho_sector": request.nicho_sector,
            "nivel_detalle": request.nivel_detalle,
        },
        "contenido_adaptado": {
            "titulo": "Listas en Python",
            "introduccion_contextualizada": "Introducción breve.",
            "items": [{"subtitulo": "Qué son", "texto": "Colecciones ordenadas."}],
        },
        "evaluacion_calidad": {
            "anclaje_fuente_score": score,
            "calidad_pedagogica_score": 0.9,
            "cumplimiento_formato_score": 0.9,
            "claridad_pedagogica": "Alta",
            "observaciones": "Correcto.",
            "intentos_revision": 1,
        },
    }


class FakeGenerator:
    def __init__(self):
        self.approved = True
        self.calls = []

    def __call__(self, request, *, source_docs):
        self.calls.append((request, source_docs))
        return educational_response(request, self.approved), source_docs[:2]


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "integracion.sqlite3")
    app = create_app()
    generator = FakeGenerator()
    oci_client = FakeOCIClient()
    app.dependency_overrides[get_generator] = lambda: generator
    app.state.oci_storage = OCIStorageManager(
        client=oci_client,
        config={"tenancy": "ocid1.tenancy.oc1..test"},
    )
    with TestClient(app) as client:
        users = {name: create_user(name, rol) for name, rol in
                 (("admin", "admin"), ("ana", "estudiante"), ("beto", "estudiante"))}
        tokens = {name: login(client, name) for name in users}
        yield {"client": client, "generator": generator, "oci_client": oci_client, "users": users, "tokens": tokens}


def create_user(usuario, rol):
    with database.get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO usuarios (nombre, usuario, contrasena_hash, rol, activo, debe_cambiar_contrasena)
            VALUES (?, ?, ?, ?, 1, 0)""",
            (usuario.title(), usuario, hash_password(PASSWORD), rol),
        )
        return cursor.lastrowid


def login(client, usuario):
    response = client.post("/api/v1/sesion", json={"usuario": usuario, "contrasena": PASSWORD})
    assert response.status_code == 200
    return response.json()["token"]


def auth(ctx, name):
    return {"Authorization": f"Bearer {ctx['tokens'][name]}"}


def setup_topic(ctx, id_tema="t-python", nicho="Fintech", with_document=True, assign="ana"):
    client, admin = ctx["client"], auth(ctx, "admin")
    response = client.post("/api/v1/temas", headers=admin, json={
        "id_tema": id_tema, "nombre": "Python", "nicho_sector": nicho, "nivel_detalle": "Práctico",
    })
    assert response.status_code == 201
    if with_document:
        document = client.post("/api/v1/documentos/texto", headers=admin,
                               json={"documento_titulo": "Manual Python", "documento_contenido": DOC_TEXT})
        assert document.status_code == 201
        assert client.put(f"/api/v1/temas/{id_tema}/documentos/{document.json()['id']}", headers=admin).status_code == 204
    if assign:
        assert client.put(f"/api/v1/temas/{id_tema}/estudiantes/{ctx['users'][assign]}", headers=admin).status_code == 204


def generate(ctx, name, **overrides):
    body = {"tema": "Listas", "perfil_destinatario": "Principiante", "formato_salida": "Resumen", "id_tema": "t-python"}
    return ctx["client"].post("/api/v1/contenidos", headers=auth(ctx, name), json={**body, **overrides})


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json() == {"status": "error", "error": {"codigo": code, "mensaje": response.json()["error"]["mensaje"]}}


def test_rutas_privadas_requieren_token(ctx):
    client = ctx["client"]
    assert client.get("/health").status_code == 200
    for method, path in (("get", "/api/v1/catalogos"), ("get", "/api/v1/documentos"),
                         ("get", "/api/v1/contenidos"), ("post", "/api/v1/contenidos"), ("get", "/api/v1/temas/t-python")):
        assert_error(getattr(client, method)(path), 401, "AUTENTICACION_REQUERIDA")


def test_documentos_solo_admin(ctx):
    response = ctx["client"].post("/api/v1/documentos/texto", headers=auth(ctx, "ana"),
                                  json={"documento_titulo": "X", "documento_contenido": DOC_TEXT})
    assert_error(response, 403, "PERMISOS_INSUFICIENTES")
    assert_error(ctx["client"].get("/api/v1/documentos", headers=auth(ctx, "ana")), 403, "PERMISOS_INSUFICIENTES")


def test_estudiante_genera_por_tema_asignado_con_fuentes(ctx):
    setup_topic(ctx)
    response = generate(ctx, "ana")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] == response.headers["X-Contenido-ID"]
    assert body["creado_en"] and body["id_tema"] == "t-python"
    assert body["metadatos"]["nicho_sector"] == "Fintech"
    assert body["metadatos"]["nivel_detalle"] == "Práctico"
    assert body["fuentes"][0]["documento"] == "Manual Python"
    assert body["fuentes"][0]["fragmento"] == 1
    assert body["fuentes"][0]["extracto"].startswith("Python es un lenguaje")

    request, source_docs = ctx["generator"].calls[0]
    assert request.nicho_sector == "Fintech"
    assert all(doc.metadata["documento_titulo"] == "Manual Python" for doc in source_docs)

    detail = ctx["client"].get(f"/api/v1/contenidos/{body['id']}", headers=auth(ctx, "ana"))
    assert detail.status_code == 200
    assert detail.json()["fuentes"] == body["fuentes"]
    download = ctx["client"].get(f"/api/v1/contenidos/{body['id']}/descarga", headers=auth(ctx, "ana"))
    assert download.status_code == 200 and download.json()["id"] == body["id"]


def test_estudiante_no_genera_en_tema_no_asignado_o_inexistente(ctx):
    setup_topic(ctx, assign=None)
    assert_error(generate(ctx, "ana"), 403, "TEMA_NO_ASIGNADO")
    assert_error(generate(ctx, "ana", id_tema="t-otro"), 404, "TEMA_NO_ENCONTRADO")
    assert ctx["generator"].calls == []


def test_tema_sin_documentos(ctx):
    setup_topic(ctx, with_document=False)
    assert_error(generate(ctx, "ana"), 422, "SIN_DOCUMENTOS_ASOCIADOS")


def test_nicho_no_se_envia_con_id_tema_y_documento_id_solo_admin(ctx):
    setup_topic(ctx)
    assert_error(generate(ctx, "ana", nicho_sector="Salud"), 422, "ENTRADA_INVALIDA")
    document_id = ctx["client"].get("/api/v1/temas/t-python/documentos", headers=auth(ctx, "ana")).json()[0]["id"]
    assert_error(generate(ctx, "ana", id_tema=None, documento_id=document_id), 403, "PERMISOS_INSUFICIENTES")

    response = generate(ctx, "admin", id_tema=None, documento_id=document_id, nicho_sector="Salud")
    assert response.status_code == 201, response.text
    assert response.json()["metadatos"]["nicho_sector"] == "Salud"
    assert response.json()["id_tema"] is None


def test_material_en_revision_no_llega_al_estudiante(ctx):
    setup_topic(ctx)
    ctx["generator"].approved = False
    response = generate(ctx, "ana")
    assert response.status_code == 202
    pending = response.json()
    assert pending["status"] == "requiere_revision" and "contenido_adaptado" not in pending

    client = ctx["client"]
    assert_error(client.get(f"/api/v1/contenidos/{pending['id']}", headers=auth(ctx, "ana")), 404, "CONTENIDO_NO_ENCONTRADO")
    assert client.get("/api/v1/contenidos", headers=auth(ctx, "ana")).json()["total"] == 0
    assert client.get("/api/v1/contenidos?status=requiere_revision", headers=auth(ctx, "ana")).json()["total"] == 0

    admin_view = client.get(f"/api/v1/contenidos/{pending['id']}", headers=auth(ctx, "admin"))
    assert admin_view.status_code == 200 and admin_view.json()["status"] == "requiere_revision"
    listed = client.get("/api/v1/contenidos?status=requiere_revision", headers=auth(ctx, "admin")).json()
    assert listed["total"] == 1 and listed["items"][0]["id_usuario"] == ctx["users"]["ana"]


def test_historial_aislado_por_usuario(ctx):
    setup_topic(ctx)
    client = ctx["client"]
    assert client.put(f"/api/v1/temas/t-python/estudiantes/{ctx['users']['beto']}", headers=auth(ctx, "admin")).status_code == 204
    content_id = generate(ctx, "ana").json()["id"]

    assert client.get("/api/v1/contenidos", headers=auth(ctx, "ana")).json()["total"] == 1
    assert client.get("/api/v1/contenidos", headers=auth(ctx, "beto")).json()["total"] == 0
    assert client.get(f"/api/v1/contenidos?id_usuario={ctx['users']['ana']}", headers=auth(ctx, "beto")).json()["total"] == 0
    assert_error(client.get(f"/api/v1/contenidos/{content_id}", headers=auth(ctx, "beto")), 404, "CONTENIDO_NO_ENCONTRADO")
    assert client.get("/api/v1/contenidos?id_tema=t-python", headers=auth(ctx, "admin")).json()["total"] == 1


def test_gestion_de_tema_por_admin(ctx):
    setup_topic(ctx)
    client, admin = ctx["client"], auth(ctx, "admin")
    updated = client.patch("/api/v1/temas/t-python", headers=admin, json={"nicho_sector": "Educación"})
    assert updated.status_code == 200 and updated.json()["nicho_sector"] == "Educación"
    assert_error(client.patch("/api/v1/temas/t-python", headers=auth(ctx, "ana"), json={"nicho_sector": "X"}), 403, "PERMISOS_INSUFICIENTES")

    assert client.get("/api/v1/temas", headers=auth(ctx, "ana")).json()[0]["nicho_sector"] == "Educación"
    assert [s["usuario"] for s in client.get("/api/v1/temas/t-python/estudiantes", headers=admin).json()] == ["ana"]
    assert_error(client.put(f"/api/v1/temas/t-python/estudiantes/{ctx['users']['admin']}", headers=admin), 404, "ESTUDIANTE_NO_ENCONTRADO")
    assert client.delete(f"/api/v1/temas/t-python/estudiantes/{ctx['users']['ana']}", headers=admin).status_code == 204
    assert_error(client.get("/api/v1/temas/t-python", headers=auth(ctx, "ana")), 403, "TEMA_NO_ASIGNADO")

    document_id = client.get("/api/v1/temas/t-python/documentos", headers=admin).json()[0]["id"]
    assert client.delete(f"/api/v1/temas/t-python/documentos/{document_id}", headers=admin).status_code == 204
    assert client.get("/api/v1/temas/t-python/documentos", headers=admin).json() == []


def test_crear_tema_rechaza_valores_en_blanco_y_recorta(ctx):
    client, admin = ctx["client"], auth(ctx, "admin")
    for field in ("nombre", "nicho_sector", "nivel_detalle"):
        body = {"id_tema": "t-blanco", "nombre": "Python", field: "   "}
        assert_error(client.post("/api/v1/temas", headers=admin, json=body), 422, "ENTRADA_INVALIDA")
    created = client.post("/api/v1/temas", headers=admin, json={"id_tema": "t-ok", "nombre": "  Python  ", "nicho_sector": " Salud "})
    assert created.status_code == 201
    assert created.json()["nombre"] == "Python" and created.json()["nicho_sector"] == "Salud"
    assert client.get("/api/v1/temas/t-ok", headers=admin).json()["nicho_sector"] == "Salud"


def test_crear_tema_con_documentos_y_borrarlo(ctx):
    client, admin = ctx["client"], auth(ctx, "admin")
    document = client.post("/api/v1/documentos/texto", headers=admin,
                           json={"documento_titulo": "Manual", "documento_contenido": DOC_TEXT}).json()["id"]

    missing = client.post("/api/v1/temas", headers=admin,
                          json={"id_tema": "t-doc", "nombre": "Doc", "documentos": ["0" * 32]})
    assert_error(missing, 404, "DOCUMENTO_NO_ENCONTRADO")
    assert client.get("/api/v1/temas/t-doc", headers=admin).status_code == 404

    created = client.post("/api/v1/temas", headers=admin,
                          json={"id_tema": "t-doc", "nombre": "Doc", "documentos": [document, document]})
    assert created.status_code == 201 and created.json()["documentos"] == [document]
    assert [d["id"] for d in client.get("/api/v1/temas/t-doc/documentos", headers=admin).json()] == [document]

    assert client.delete("/api/v1/temas/t-doc", headers=auth(ctx, "ana")).status_code == 403
    assert client.delete("/api/v1/temas/t-doc", headers=admin).status_code == 204
    assert client.get("/api/v1/temas/t-doc", headers=admin).status_code == 404
    assert client.delete("/api/v1/temas/t-doc", headers=admin).status_code == 404
    assert client.get(f"/api/v1/documentos/{document}", headers=admin).status_code == 200


def test_borrar_tema_conserva_historial(ctx):
    setup_topic(ctx)
    assert generate(ctx, "ana").status_code == 201
    assert client_delete(ctx, "t-python").status_code == 204
    assert len(ctx["client"].get("/api/v1/contenidos", headers=auth(ctx, "admin")).json()["items"]) == 1


def client_delete(ctx, id_tema):
    return ctx["client"].delete(f"/api/v1/temas/{id_tema}", headers=auth(ctx, "admin"))


def test_listar_usuarios_solo_admin(ctx):
    setup_topic(ctx)
    client = ctx["client"]
    assert client.get("/api/v1/usuarios", headers=auth(ctx, "ana")).status_code == 403
    assert client.get("/api/v1/usuarios").status_code == 401
    users = {u["usuario"]: u for u in client.get("/api/v1/usuarios", headers=auth(ctx, "admin")).json()}
    assert set(users) == {"admin", "ana", "beto"}
    assert users["ana"]["temas"] == ["t-python"] and users["beto"]["temas"] == []
    assert users["admin"]["rol"] == "admin" and "contrasena_hash" not in users["ana"]


def test_generar_con_tema_vacio_equivale_a_omitirlo(ctx):
    setup_topic(ctx)
    response = ctx["client"].post("/api/v1/contenidos", headers=auth(ctx, "ana"), json={
        "tema": "  ", "perfil_destinatario": "Principiante", "formato_salida": "Resumen", "id_tema": "t-python",
    })
    assert response.status_code == 201
    assert ctx["generator"].calls[-1][0].tema == "Python"


def test_generar_sin_tema_usa_el_nombre_del_tema(ctx):
    setup_topic(ctx)
    response = ctx["client"].post("/api/v1/contenidos", headers=auth(ctx, "ana"), json={
        "perfil_destinatario": "Principiante", "formato_salida": "Resumen", "id_tema": "t-python",
    })
    assert response.status_code == 201
    assert ctx["generator"].calls[-1][0].tema == "Python"
    stored = ctx["client"].get("/api/v1/contenidos", headers=auth(ctx, "admin")).json()["items"][0]
    assert stored["tema"] == "Python"

    document = ctx["client"].get("/api/v1/temas/t-python/documentos", headers=auth(ctx, "admin")).json()[0]["id"]
    assert_error(ctx["client"].post("/api/v1/contenidos", headers=auth(ctx, "admin"), json={
        "perfil_destinatario": "Principiante", "formato_salida": "Resumen", "documento_id": document,
    }), 422, "ENTRADA_INVALIDA")


def test_catalogos_incluye_sectores(ctx):
    catalogs = ctx["client"].get("/api/v1/catalogos", headers=auth(ctx, "ana")).json()
    assert catalogs["sectores"] == ["Fintech", "Salud", "E-commerce", "General"]


def test_sesion_actual(ctx):
    setup_topic(ctx)
    client = ctx["client"]
    assert client.get("/api/v1/sesion").status_code == 401
    me = client.get("/api/v1/sesion", headers=auth(ctx, "ana")).json()
    assert me["usuario"] == "ana" and me["rol"] == "estudiante" and me["temas"] == ["t-python"]
    assert "contrasena_hash" not in me
    assert client.get("/api/v1/sesion", headers=auth(ctx, "admin")).json()["temas"] == ["t-python"]


def test_actualizar_estudiante(ctx):
    client, admin, ana = ctx["client"], auth(ctx, "admin"), ctx["users"]["ana"]
    url = f"/api/v1/usuarios/{ana}"
    assert client.put(url, headers=auth(ctx, "beto"), json={"nombre": "X"}).status_code == 403
    assert client.put(url, headers=admin, json={}).status_code == 422
    assert client.put(f"/api/v1/usuarios/{ctx['users']['admin']}", headers=admin, json={"activo": False}).status_code == 404
    assert client.put("/api/v1/usuarios/9999", headers=admin, json={"activo": False}).status_code == 404

    renamed = client.put(url, headers=admin, json={"nombre": "  Ana Paz  "})
    assert renamed.status_code == 200 and renamed.json()["nombre"] == "Ana Paz"

    disabled = client.put(url, headers=admin, json={"activo": False}).json()
    assert disabled["activo"] is False
    assert client.get("/api/v1/sesion", headers=auth(ctx, "ana")).status_code == 401
    login = client.post("/api/v1/sesion", json={"usuario": "ana", "contrasena": PASSWORD})
    assert login.status_code == 401

    client.put(url, headers=admin, json={"activo": True, "contrasena_temporal": "temporal-123456"})
    login = client.post("/api/v1/sesion", json={"usuario": "ana", "contrasena": "temporal-123456"})
    assert login.status_code == 200 and login.json()["usuario"]["debe_cambiar_contrasena"] is True


def test_migracion_desde_base_f06(tmp_path):
    path = tmp_path / "f06.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE documentos (id TEXT PRIMARY KEY, documento_titulo TEXT NOT NULL, nombre_archivo TEXT NOT NULL,
            tipo TEXT NOT NULL, tamano_bytes INTEGER NOT NULL, fragmentos_extraidos INTEGER NOT NULL,
            creado_en TEXT NOT NULL, original BLOB NOT NULL, paginas_json TEXT NOT NULL);
        CREATE TABLE contenidos (id TEXT PRIMARY KEY, documento_id TEXT NOT NULL REFERENCES documentos(id),
            titulo TEXT NOT NULL, tema TEXT NOT NULL, perfil_aplicado TEXT NOT NULL, formato_generado TEXT NOT NULL,
            status TEXT NOT NULL, anclaje_fuente_score REAL NOT NULL, creado_en TEXT NOT NULL,
            solicitud_json TEXT NOT NULL, respuesta_json TEXT NOT NULL);
        INSERT INTO documentos VALUES ('d1', 'Doc', 'a.txt', 'txt', 1, 1, 'x', X'00', '[]');
        INSERT INTO contenidos VALUES ('c1', 'd1', 'T', 'tema', 'Principiante', 'Resumen', 'exito', 0.9, 'x', '{}', '{}');
        PRAGMA user_version = 1;
    """)
    conn.close()

    database.init_db(path)
    with database.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
        row = conn.execute("SELECT documento_id, id_tema, fuentes_json FROM contenidos WHERE id = 'c1'").fetchone()
        assert tuple(row) == ("d1", None, "[]")
        assert "nicho_sector" in {r["name"] for r in conn.execute("PRAGMA table_info(temas)")}


def test_errores_de_asociacion_y_ruta_inexistente(ctx):
    setup_topic(ctx, assign=None)
    client, admin = ctx["client"], auth(ctx, "admin")
    assert_error(client.delete(f"/api/v1/temas/t-python/estudiantes/{ctx['users']['ana']}", headers=admin),
                 404, "ASIGNACION_NO_ENCONTRADA")
    assert_error(client.delete(f"/api/v1/temas/t-python/documentos/{'0' * 32}", headers=admin), 404, "ASOCIACION_NO_ENCONTRADA")
    assert_error(client.put(f"/api/v1/temas/t-python/documentos/{'0' * 32}", headers=admin), 404, "DOCUMENTO_NO_ENCONTRADO")
    missing = client.get("/ruta-inexistente")
    assert_error(missing, 404, "RECURSO_NO_ENCONTRADO")
    assert missing.json()["error"]["mensaje"] == "La ruta o el recurso solicitado no existe."


def test_generador_sin_configuracion_responde_503(ctx):
    from errors import ConfigurationError

    def unconfigured(request, *, source_docs):
        raise ConfigurationError("sin clave")

    setup_topic(ctx)
    ctx["client"].app.dependency_overrides[get_generator] = lambda: unconfigured
    assert_error(generate(ctx, "ana"), 503, "CONFIGURACION_INCOMPLETA")


def test_migracion_desde_base_f08(tmp_path):
    path = tmp_path / "f08.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE temas (id_tema TEXT PRIMARY KEY, nombre TEXT NOT NULL, descripcion TEXT NOT NULL DEFAULT '');
        INSERT INTO temas VALUES ('t1', 'Tema', '');
    """)
    conn.close()

    database.init_db(path)
    database.init_db(path)
    with database.connect(path) as conn:
        row = conn.execute("SELECT nicho_sector, nivel_detalle FROM temas WHERE id_tema = 't1'").fetchone()
        assert tuple(row) == (DEFAULT_NICHE, DEFAULT_DETAIL)


def test_migracion_fallida_no_deja_la_base_a_medias(tmp_path):
    path = tmp_path / "f06_rota.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE documentos (id TEXT PRIMARY KEY, documento_titulo TEXT NOT NULL, nombre_archivo TEXT NOT NULL,
            tipo TEXT NOT NULL, tamano_bytes INTEGER NOT NULL, fragmentos_extraidos INTEGER NOT NULL,
            creado_en TEXT NOT NULL, original BLOB NOT NULL, paginas_json TEXT NOT NULL);
        CREATE TABLE contenidos (id TEXT PRIMARY KEY, documento_id TEXT NOT NULL, titulo TEXT NOT NULL,
            tema TEXT NOT NULL, perfil_aplicado TEXT NOT NULL, formato_generado TEXT NOT NULL, status TEXT NOT NULL,
            anclaje_fuente_score REAL NOT NULL, creado_en TEXT NOT NULL, solicitud_json TEXT NOT NULL,
            respuesta_json TEXT NOT NULL);
        INSERT INTO contenidos VALUES ('c1', 'inexistente', 'T', 'tema', 'Principiante', 'Resumen', 'exito', 0.9,
            'x', '{}', '{}');
    """)
    conn.close()

    with pytest.raises(sqlite3.IntegrityError):
        database.init_db(path)
    with database.connect(path) as conn:
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert "contenidos_v1" not in tables
        assert "id_tema" not in {row["name"] for row in conn.execute("PRAGMA table_info(contenidos)")}
        assert conn.execute("SELECT count(*) FROM contenidos").fetchone()[0] == 1


def test_admin_aprueba_material_en_revision(ctx):
    setup_topic(ctx)
    ctx["generator"].approved = False
    content_id = generate(ctx, "ana").json()["id"]
    client, admin = ctx["client"], auth(ctx, "admin")

    assert [i["id"] for i in client.get("/api/v1/contenidos?pendiente=true", headers=admin).json()["items"]] == [content_id]
    assert_error(client.post(f"/api/v1/contenidos/{content_id}/aprobar", headers=auth(ctx, "ana")), 403, "PERMISOS_INSUFICIENTES")

    approved = client.post(f"/api/v1/contenidos/{content_id}/aprobar", headers=admin)
    assert approved.status_code == 200
    assert approved.json()["aprobado_en"] and approved.json()["status"] == "requiere_revision"
    assert client.get("/api/v1/contenidos?pendiente=true", headers=admin).json()["total"] == 0
    assert_error(client.post(f"/api/v1/contenidos/{content_id}/aprobar", headers=admin), 409, "CONTENIDO_NO_PENDIENTE")

    student_view = client.get(f"/api/v1/contenidos/{content_id}", headers=auth(ctx, "ana"))
    assert student_view.status_code == 200 and student_view.json()["aprobado_en"]
    listed = client.get("/api/v1/contenidos", headers=auth(ctx, "ana")).json()
    assert listed["total"] == 1 and listed["items"][0]["aprobado_en"]


def test_admin_rechaza_material_en_revision(ctx):
    setup_topic(ctx)
    client, admin = ctx["client"], auth(ctx, "admin")
    approved_id = generate(ctx, "ana").json()["id"]
    assert_error(client.post(f"/api/v1/contenidos/{approved_id}/rechazar", headers=admin), 409, "CONTENIDO_NO_PENDIENTE")

    ctx["generator"].approved = False
    content_id = generate(ctx, "ana").json()["id"]
    assert_error(client.post(f"/api/v1/contenidos/{content_id}/rechazar", headers=auth(ctx, "ana")), 403, "PERMISOS_INSUFICIENTES")
    assert client.post(f"/api/v1/contenidos/{content_id}/rechazar", headers=admin).status_code == 204
    assert_error(client.get(f"/api/v1/contenidos/{content_id}", headers=admin), 404, "CONTENIDO_NO_ENCONTRADO")
    assert_error(client.post(f"/api/v1/contenidos/{content_id}/rechazar", headers=admin), 404, "CONTENIDO_NO_ENCONTRADO")


def test_migracion_desde_base_v2_agrega_aprobacion(tmp_path):
    path = tmp_path / "v2.sqlite3"
    database.init_db(path)
    with database.connect(path) as conn:
        conn.execute("ALTER TABLE contenidos DROP COLUMN aprobado_en")
        conn.execute("PRAGMA user_version = 2")
    database.init_db(path)
    with database.connect(path) as conn:
        assert "aprobado_en" in {r["name"] for r in conn.execute("PRAGMA table_info(contenidos)")}
        assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


def bad_login(client, usuario="ana", password="incorrecta-123"):
    return client.post("/api/v1/sesion", json={"usuario": usuario, "contrasena": password})


def test_login_se_bloquea_tras_cinco_fallos_y_vuelve_con_el_tiempo(ctx):
    client = ctx["client"]
    client.app.state.clock = clock = Clock()
    assert [bad_login(client).status_code for _ in range(5)] == [401] * 5
    locked = bad_login(client)
    assert_error(locked, 429, "DEMASIADOS_INTENTOS")
    assert locked.headers["Retry-After"] == "60"
    # Con el bloqueo activo ni la clave correcta entra.
    assert bad_login(client, password=PASSWORD).status_code == 429
    clock.now += 61
    assert bad_login(client, password=PASSWORD).status_code == 200


def test_login_bloqueo_progresivo(ctx):
    client = ctx["client"]
    client.app.state.clock = clock = Clock()
    for expected in ("60", "300", "900", "900"):
        for _ in range(5):
            bad_login(client)
        assert bad_login(client).headers["Retry-After"] == expected
        clock.now += int(expected) + 1


def test_login_exitoso_reinicia_el_contador_de_la_cuenta(ctx):
    client = ctx["client"]
    client.app.state.clock = Clock()
    for _ in range(4):
        bad_login(client)
    assert bad_login(client, password=PASSWORD).status_code == 200
    assert [bad_login(client).status_code for _ in range(4)] == [401] * 4


def test_login_usuario_inexistente_se_comporta_igual(ctx):
    client = ctx["client"]
    client.app.state.clock = Clock()
    first = bad_login(client, usuario="fantasma")
    assert first.status_code == 401
    assert first.json() == bad_login(client, usuario="ana").json()
    for _ in range(4):
        bad_login(client, usuario="fantasma")
    assert bad_login(client, usuario="fantasma").status_code == 429


def test_login_bloqueo_de_cuenta_no_afecta_a_otra_ip(ctx):
    client = ctx["client"]
    client.app.state.clock = Clock()
    for _ in range(5):
        bad_login(client)
    assert bad_login(client).status_code == 429
    with TestClient(client.app, client=("10.0.0.9", 5000)) as other:
        assert bad_login(other, password=PASSWORD).status_code == 200


def test_login_limite_por_ip_frena_el_barrido_de_usuarios(ctx):
    client = ctx["client"]
    client.app.state.clock = Clock()
    codes = [bad_login(client, usuario=f"u{i}").status_code for i in range(21)]
    assert codes[:20] == [401] * 20 and codes[20] == 429


def test_admin_desbloquea_a_un_estudiante(ctx):
    client = ctx["client"]
    client.app.state.clock = Clock()
    for _ in range(5):
        bad_login(client)
    assert bad_login(client, password=PASSWORD).status_code == 429
    url = f"/api/v1/usuarios/{ctx['users']['ana']}/desbloqueo"
    assert_error(client.post(url, headers=auth(ctx, "ana")), 403, "PERMISOS_INSUFICIENTES")
    assert client.post(url, headers=auth(ctx, "admin")).status_code == 204
    assert bad_login(client, password=PASSWORD).status_code == 200
    assert client.post(f"/api/v1/usuarios/{ctx['users']['admin']}/desbloqueo", headers=auth(ctx, "admin")).status_code == 404


def test_respaldo_oci_en_documentos_y_contenidos_aprobados(ctx):
    client, admin, oci_client = ctx["client"], auth(ctx, "admin"), ctx["oci_client"]
    setup_topic(ctx)
    assert "documentos/manual-python.txt" in oci_client.uploaded_objects

    upload = client.post(
        "/api/v1/documentos",
        headers=admin,
        files={"archivo": ("guia_redes_vcn.md", DOC_TEXT.encode("utf-8"), "text/markdown")},
    )
    assert upload.status_code == 201
    assert "documentos/guia-redes-vcn.md" in oci_client.uploaded_objects

    # Generación con éxito se respalda inmediatamente en OCI
    ok_resp = generate(ctx, "ana", tema="Listas")
    assert ok_resp.status_code == 201
    ok_id = ok_resp.json()["id"]
    content_obj = f"contenido-listas-principiante-resumen-{ok_id}.json"
    assert content_obj in oci_client.uploaded_objects
    stored_json = json.loads(oci_client.uploaded_objects[content_obj]["content"].decode("utf-8"))
    assert stored_json["id"] == ok_id
    assert stored_json["almacenamiento_oci"]["status_upload"] == "completado"

    # Material en revisión NO se sube a OCI hasta que un admin lo apruebe
    oci_client.uploaded_objects.clear()
    ctx["generator"].approved = False
    pending_resp = generate(ctx, "ana", tema="Tuplas")
    assert pending_resp.status_code == 202
    pending_id = pending_resp.json()["id"]
    assert oci_client.uploaded_objects == {}

    approved_resp = client.post(f"/api/v1/contenidos/{pending_id}/aprobar", headers=admin)
    assert approved_resp.status_code == 200
    approved_obj = f"contenido-tuplas-principiante-resumen-{pending_id}.json"
    assert approved_obj in oci_client.uploaded_objects
    approved_json = json.loads(oci_client.uploaded_objects[approved_obj]["content"].decode("utf-8"))
    assert approved_json["id"] == pending_id
    assert approved_json["aprobado_en"] is not None
    assert approved_json["almacenamiento_oci"]["status_upload"] == "completado"


def test_respaldo_oci_no_pisa_contenidos_con_mismos_parametros(ctx):
    oci_client = ctx["oci_client"]
    setup_topic(ctx)
    oci_client.uploaded_objects.clear()

    first = generate(ctx, "ana", tema="Listas", perfil_destinatario="Principiante", formato_salida="Resumen")
    second = generate(ctx, "ana", tema="Listas", perfil_destinatario="Principiante", formato_salida="Resumen")
    assert first.status_code == 201 and second.status_code == 201

    first_id, second_id = first.json()["id"], second.json()["id"]
    assert first_id != second_id

    first_obj = f"contenido-listas-principiante-resumen-{first_id}.json"
    second_obj = f"contenido-listas-principiante-resumen-{second_id}.json"
    assert first_obj in oci_client.uploaded_objects
    assert second_obj in oci_client.uploaded_objects

    first_stored = json.loads(oci_client.uploaded_objects[first_obj]["content"].decode("utf-8"))
    second_stored = json.loads(oci_client.uploaded_objects[second_obj]["content"].decode("utf-8"))
    assert first_stored["id"] == first_id
    assert second_stored["id"] == second_id


def test_api_opera_sin_credenciales_oci(ctx, monkeypatch):
    import oci_storage

    def sin_credenciales(*args, **kwargs):
        raise OCIConfigurationError("Sin credenciales OCI en entorno local")

    monkeypatch.setattr(oci_storage, "load_oci_config", sin_credenciales)
    ctx["client"].app.state.oci_storage = OCIStorageManager()

    setup_topic(ctx)
    response = generate(ctx, "ana")
    assert response.status_code == 201
