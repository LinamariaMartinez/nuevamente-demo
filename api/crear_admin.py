
import getpass
import sqlite3

from api.auth import hash_password
from api.database import get_connection, init_db


def main():
    init_db()

    print("=== Crear administrador NuevaMente ===")

    nombre = input("Nombre completo: ").strip()
    usuario = input("Nombre de usuario: ").strip()
    contrasena = getpass.getpass("Contraseña: ")
    confirmacion = getpass.getpass("Confirmar contraseña: ")

    if not nombre or not usuario:
        print("El nombre y el usuario son obligatorios.")
        return

    if len(contrasena) < 12:
        print("La contraseña debe tener al menos 12 caracteres.")
        return

    if contrasena != confirmacion:
        print("Las contraseñas no coinciden.")
        return

    try:
        with get_connection() as connection:
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
                VALUES (?, ?, ?, 'admin', 1, 0)
                """,
                (nombre, usuario, hash_password(contrasena)),
            )

        print("Administrador creado correctamente.")

    except sqlite3.IntegrityError:
        print("Ese nombre de usuario ya existe.")


if __name__ == "__main__":
    main()
