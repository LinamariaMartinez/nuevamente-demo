"""Cuentas sembradas contra SQLite y las rutas reales; Gemini/OCI no se invocan."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import database
from api.auth import verify_password
from api.main import create_app, get_generator
from scripts.crear_cuentas_demo import CUENTAS, DOCUMENTO_DEMO, ROOT, TEMA_DEMO, crear_cuentas, main


PASSWORDS = {c.usuario: f"Clave-prueba-{c.usuario}-123!" for c in CUENTAS}


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "cuentas.sqlite3"
    monkeypatch.setattr(database, "DB_PATH", path)
    return path


@pytest.fixture
def seeded(db_path):
    crear_cuentas(db_path, con_tema_demo=True, passwords=PASSWORDS)
    return db_path


def login(client, usuario, password=None):
    response = client.post("/api/v1/sesion", json={
        "usuario": usuario, "contrasena": password or PASSWORDS[usuario],
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}, response.json()["usuario"]


def test_crea_roles_hashes_y_documento_utilizable(seeded):
    with database.connect(seeded) as conn:
        rows = conn.execute("SELECT * FROM usuarios ORDER BY usuario").fetchall()
        assert len(rows) == 3
        assert {row["rol"] for row in rows} == {"admin", "estudiante"}
        for row in rows:
            assert row["contrasena_hash"].startswith("$argon2")
            assert verify_password(PASSWORDS[row["usuario"]], row["contrasena_hash"])
        assert conn.execute("SELECT count(*) FROM usuario_temas").fetchone()[0] == 2
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    pages = database.Store(seeded).topic_pages(TEMA_DEMO)
    assert pages and "VCN" in pages[0].page_content
    assert pages[0].metadata["documento_id"] == DOCUMENTO_DEMO


def test_repetir_preserva_claves_estados_sesiones_y_no_duplica(seeded):
    with database.connect(seeded) as conn:
        conn.execute("UPDATE usuarios SET activo = 0 WHERE usuario = 'estudiante_demo'")
        conn.execute("UPDATE usuarios SET debe_cambiar_contrasena = 0 WHERE usuario = 'temporal_demo'")
        before = [tuple(r) for r in conn.execute("SELECT * FROM usuarios ORDER BY id_usuario")]
        conn.execute("INSERT INTO sesiones VALUES ('token-prueba', ?, '2099-01-01')", (before[0][0],))
    result = crear_cuentas(seeded, con_tema_demo=True, passwords={"admin_demo": "Otra-clave-valida-123"})
    assert all(not r["creada"] and r["contrasena"] is None for r in result)
    with database.connect(seeded) as conn:
        assert [tuple(r) for r in conn.execute("SELECT * FROM usuarios ORDER BY id_usuario")] == before
        for table, count in (("documentos", 1), ("temas", 1), ("usuario_temas", 2), ("sesiones", 1)):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == count


def test_tema_inexistente_no_deja_cuentas_parciales(db_path):
    with pytest.raises(ValueError, match="No existe el tema"):
        crear_cuentas(db_path, con_tema_demo=True, temas=["inexistente"])
    with database.connect(db_path) as conn:
        assert conn.execute("SELECT count(*) FROM usuarios").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM documentos").fetchone()[0] == 0


def test_colision_de_rol_no_promueve_cuentas(seeded):
    with database.connect(seeded) as conn:
        conn.execute("UPDATE usuarios SET rol = 'estudiante' WHERE usuario = 'admin_demo'")
    with pytest.raises(ValueError, match="otro rol"):
        crear_cuentas(seeded, con_tema_demo=True)
    with database.connect(seeded) as conn:
        assert conn.execute("SELECT rol FROM usuarios WHERE usuario = 'admin_demo'").fetchone()[0] == "estudiante"


def test_fallo_durante_hash_revierte_toda_la_carga(db_path, monkeypatch):
    def fallar(_):
        raise RuntimeError("Hash no disponible")

    monkeypatch.setattr("api.auth.hash_password", fallar)
    with pytest.raises(RuntimeError, match="Hash no disponible"):
        crear_cuentas(db_path, con_tema_demo=True)
    with database.connect(db_path) as conn:
        for table in ("usuarios", "documentos", "temas", "usuario_temas", "tema_documentos"):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


@pytest.mark.parametrize("password", ["", "corta"])
def test_clave_invalida_se_rechaza_antes_de_crear_base(db_path, password):
    with pytest.raises(ValueError, match="12 caracteres"):
        crear_cuentas(db_path, passwords={"admin_demo": password})
    assert not db_path.exists()


def test_asigna_temas_existentes_sin_quitar_asignaciones(seeded):
    with database.connect(seeded) as conn:
        conn.execute("INSERT INTO temas (id_tema, nombre) VALUES ('otro', 'Otro tema')")
    crear_cuentas(seeded, temas=["otro", "otro"])
    with database.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM usuario_temas").fetchone()[0] == 4
        assert conn.execute("SELECT count(*) FROM usuario_temas ut JOIN usuarios u USING (id_usuario) WHERE u.rol = 'admin'").fetchone()[0] == 0


def test_cli_genera_claves_y_solo_las_muestra_al_crear(db_path, monkeypatch, capsys):
    for cuenta in CUENTAS:
        monkeypatch.delenv(cuenta.variable, raising=False)
    # No leer secretos locales durante la prueba.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: None)
    assert main(["--db", str(db_path)]) == 0
    output = capsys.readouterr().out
    claves = [line.split("Contraseña: ")[1] for line in output.splitlines() if "Contraseña: " in line]
    assert len(claves) == len(set(claves)) == 3
    assert all(len(clave) >= 12 for clave in claves)
    with database.connect(db_path) as conn:
        for cuenta, clave in zip(CUENTAS, claves):
            hashed = conn.execute("SELECT contrasena_hash FROM usuarios WHERE usuario = ?", (cuenta.usuario,)).fetchone()[0]
            assert verify_password(clave, hashed)
    assert main(["--db", str(db_path)]) == 0
    assert "Contraseña: " not in capsys.readouterr().out


def test_login_permisos_y_cambio_obligatorio(seeded):
    with TestClient(create_app()) as client:
        admin, usuario_admin = login(client, "admin_demo")
        estudiante, usuario_estudiante = login(client, "estudiante_demo")
        temporal, usuario_temporal = login(client, "temporal_demo")
        assert usuario_admin["rol"] == "admin"
        assert usuario_estudiante["rol"] == "estudiante"
        assert not usuario_estudiante["debe_cambiar_contrasena"]
        assert usuario_temporal["debe_cambiar_contrasena"]
        assert client.get("/api/v1/usuarios", headers=admin).status_code == 200
        assert client.get(f"/api/v1/documentos/{DOCUMENTO_DEMO}", headers=admin).status_code == 200
        assert client.get("/api/v1/usuarios", headers=estudiante).status_code == 403
        assert client.get("/api/v1/documentos", headers=estudiante).status_code == 403
        assert client.get("/api/v1/temas").status_code == 401
        assert client.get("/api/v1/temas", headers=temporal).status_code == 403
        temas = client.get("/api/v1/temas", headers=estudiante).json()
        assert [t["id_tema"] for t in temas] == [TEMA_DEMO]
        docs = client.get(f"/api/v1/temas/{TEMA_DEMO}/documentos", headers=estudiante).json()
        assert docs[0]["id"] == DOCUMENTO_DEMO
        nueva = "Clave-nueva-temporal-456!"
        response = client.put("/api/v1/sesion/contrasena", headers=temporal, json={
            "contrasena_actual": PASSWORDS["temporal_demo"], "contrasena_nueva": nueva,
        })
        assert response.status_code == 200
        assert client.get("/api/v1/temas", headers=temporal).status_code == 401
        temporal, usuario = login(client, "temporal_demo", nueva)
        assert not usuario["debe_cambiar_contrasena"]
        assert client.get("/api/v1/temas", headers=temporal).status_code == 200
        assert client.delete("/api/v1/sesion", headers=admin).status_code == 200
        assert client.get("/api/v1/usuarios", headers=admin).status_code == 401


def test_generacion_historial_y_revision_con_cuentas_sembradas(seeded):
    pendiente = False

    def generar(request, *, source_docs):
        assert source_docs and source_docs[0].metadata["documento_id"] == DOCUMENTO_DEMO
        body = json.loads((ROOT / "examples" / "respuesta_flashcards.json").read_text(encoding="utf-8"))
        body["metadatos"].update(perfil_aplicado=request.perfil_destinatario,
                                 nicho_sector=request.nicho_sector, nivel_detalle=request.nivel_detalle)
        if pendiente:
            body["status"] = "requiere_revision"
            body["evaluacion_calidad"].update(anclaje_fuente_score=0.5, intentos_revision=3)
        return body, source_docs

    app = create_app()
    app.dependency_overrides[get_generator] = lambda: generar
    app.state.oci_storage = SimpleNamespace(
        upload_educational_json=lambda *a, **kw: (None, SimpleNamespace(status_upload="omitido")),
    )
    with TestClient(app) as client:
        admin, _ = login(client, "admin_demo")
        estudiante, _ = login(client, "estudiante_demo")
        solicitud = {"id_tema": TEMA_DEMO, "perfil_destinatario": "Intermedio", "formato_salida": "Flashcards"}
        response = client.post("/api/v1/contenidos", headers=estudiante, json=solicitud)
        assert response.status_code == 201, response.text
        assert response.json()["fuentes"][0]["documento_id"] == DOCUMENTO_DEMO
        assert client.get("/api/v1/contenidos", headers=estudiante).json()["total"] == 1
        pendiente = True
        response = client.post("/api/v1/contenidos", headers=estudiante, json=solicitud)
        assert response.status_code == 202, response.text
        identifier = response.json()["id"]
        assert "contenido_adaptado" not in response.json()
        assert client.get(f"/api/v1/contenidos/{identifier}", headers=estudiante).status_code == 404
        assert client.get("/api/v1/contenidos?pendiente=true", headers=admin).json()["total"] == 1
        assert client.post(f"/api/v1/contenidos/{identifier}/aprobar", headers=estudiante).status_code == 403
        assert client.post(f"/api/v1/contenidos/{identifier}/aprobar", headers=admin).status_code == 200
        assert client.get("/api/v1/contenidos", headers=estudiante).json()["total"] == 2
