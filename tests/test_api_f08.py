
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import database
from api.auth import hash_password
from api.main import app


@pytest.fixture
def client(monkeypatch):
    # Cada prueba utiliza su propia base de datos temporal.
    with tempfile.TemporaryDirectory() as temp_dir:
        test_db = Path(temp_dir) / "test_nuevamente.db"
        monkeypatch.setattr(database, "DB_PATH", test_db)

        with TestClient(app) as test_client:
            yield test_client


def crear_usuario(nombre, usuario, password, rol, cambiar=False):
    with database.get_connection() as connection:
        connection.execute(
            """
            INSERT INTO usuarios (
                nombre,
                usuario,
                contrasena_hash,
                rol,
                activo,
                debe_cambiar_contrasena
            )
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (
                nombre,
                usuario,
                hash_password(password),
                rol,
                int(cambiar),
            ),
        )


def iniciar_sesion(client, usuario, password):
    response = client.post(
        "/api/v1/sesion",
        json={
            "usuario": usuario,
            "contrasena": password,
        },
    )

    assert response.status_code == 200
    return response.json()["token"]


def test_salud(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_correcto(client):
    crear_usuario(
        "Admin Prueba",
        "admin_test",
        "ContrasenaSegura123!",
        "admin",
    )

    response = client.post(
        "/api/v1/sesion",
        json={
            "usuario": "admin_test",
            "contrasena": "ContrasenaSegura123!",
        },
    )

    assert response.status_code == 200
    assert response.json()["usuario"]["rol"] == "admin"
    assert "token" in response.json()


def test_login_incorrecto(client):
    crear_usuario(
        "Admin Prueba",
        "admin_test",
        "ContrasenaSegura123!",
        "admin",
    )

    response = client.post(
        "/api/v1/sesion",
        json={
            "usuario": "admin_test",
            "contrasena": "incorrecta",
        },
    )

    assert response.status_code == 401


def test_temas_sin_sesion(client):
    response = client.get("/api/v1/temas")

    assert response.status_code == 401


def test_admin_puede_crear_tema(client):
    crear_usuario(
        "Admin Prueba",
        "admin_test",
        "ContrasenaSegura123!",
        "admin",
    )

    token = iniciar_sesion(
        client,
        "admin_test",
        "ContrasenaSegura123!",
    )

    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/temas",
        headers=headers,
        json={
            "id_tema": "t-python",
            "nombre": "Python",
            "descripcion": "Introducción a Python",
        },
    )

    assert response.status_code == 201

    listado = client.get("/api/v1/temas", headers=headers)

    assert listado.status_code == 200
    assert len(listado.json()) == 1
    assert listado.json()[0]["id_tema"] == "t-python"


def test_estudiante_no_puede_crear_tema(client):
    crear_usuario(
        "Estudiante Prueba",
        "estudiante_test",
        "ContrasenaSegura123!",
        "estudiante",
    )

    token = iniciar_sesion(
        client,
        "estudiante_test",
        "ContrasenaSegura123!",
    )

    response = client.post(
        "/api/v1/temas",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "id_tema": "t-python",
            "nombre": "Python",
        },
    )

    assert response.status_code == 403


def test_contrasena_temporal_bloquea_temas(client):
    crear_usuario(
        "Estudiante Prueba",
        "estudiante_test",
        "ContrasenaSegura123!",
        "estudiante",
        cambiar=True,
    )

    token = iniciar_sesion(
        client,
        "estudiante_test",
        "ContrasenaSegura123!",
    )

    response = client.get(
        "/api/v1/temas",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_logout_revoca_token(client):
    crear_usuario(
        "Admin Prueba",
        "admin_test",
        "ContrasenaSegura123!",
        "admin",
    )

    token = iniciar_sesion(
        client,
        "admin_test",
        "ContrasenaSegura123!",
    )

    headers = {"Authorization": f"Bearer {token}"}

    logout = client.delete("/api/v1/sesion", headers=headers)

    assert logout.status_code == 200

    response = client.get("/api/v1/temas", headers=headers)

    assert response.status_code == 401

def test_estudiante_solo_ve_temas_asignados(client):
    crear_usuario(
        "Estudiante Prueba",
        "estudiante_test",
        "ContrasenaSegura123!",
        "estudiante",
    )

    with database.get_connection() as connection:
        connection.execute(
            """
            INSERT INTO temas (id_tema, nombre, descripcion)
            VALUES ('t-python', 'Python', ''),
                   ('t-ia', 'Inteligencia Artificial', '')
            """
        )

        id_usuario = connection.execute(
            "SELECT id_usuario FROM usuarios WHERE usuario = ?",
            ("estudiante_test",),
        ).fetchone()["id_usuario"]

        connection.execute(
            """
            INSERT INTO usuario_temas (id_usuario, id_tema)
            VALUES (?, ?)
            """,
            (id_usuario, "t-python"),
        )

    token = iniciar_sesion(
        client, "estudiante_test", "ContrasenaSegura123!"
    )

    response = client.get(
        "/api/v1/temas",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id_tema"] == "t-python"


def test_cambio_contrasena_revoca_sesiones(client):
    crear_usuario(
        "Estudiante Prueba",
        "estudiante_test",
        "ContrasenaSegura123!",
        "estudiante",
    )

    token1 = iniciar_sesion(
        client, "estudiante_test", "ContrasenaSegura123!"
    )
    token2 = iniciar_sesion(
        client, "estudiante_test", "ContrasenaSegura123!"
    )

    response = client.put(
        "/api/v1/sesion/contrasena",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "contrasena_actual": "ContrasenaSegura123!",
            "contrasena_nueva": "OtraContrasenaSegura456!",
        },
    )

    assert response.status_code == 200

    for token in (token1, token2):
        result = client.get(
            "/api/v1/temas",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert result.status_code == 401

    nuevo_token = iniciar_sesion(
        client, "estudiante_test", "OtraContrasenaSegura456!"
    )
    assert nuevo_token


def test_estudiante_no_puede_crear_usuarios(client):
    crear_usuario(
        "Estudiante Prueba",
        "estudiante_test",
        "ContrasenaSegura123!",
        "estudiante",
    )

    token = iniciar_sesion(
        client, "estudiante_test", "ContrasenaSegura123!"
    )

    response = client.post(
        "/api/v1/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre": "Otro Estudiante",
            "usuario": "otro_estudiante",
            "contrasena_temporal": "TemporalSegura123!",
            "temas": [],
        },
    )

    assert response.status_code == 403
