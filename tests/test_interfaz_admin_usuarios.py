"""Pruebas de Usuarios (admin): crear estudiantes, contraseña temporal, temas, activar y desbloquear."""

import unittest

from apoyo_interfaz import abrir_pagina, columnas_principales, textos

from cliente_api import ClienteMock

USUARIOS = "paginas.admin.usuarios:mostrar"


def abrir(cliente=None, usuario="admin"):
    return abrir_pagina(USUARIOS, usuario=usuario, cliente=cliente)


def crear(at, nombre="Ana Pérez", usuario="ana", contrasena="Temporal-2026", temas=("t-redes",)):
    at.text_input(key="nuevo_usuario_nombre").input(nombre)
    at.text_input(key="nuevo_usuario_usuario").input(usuario)
    at.text_input(key="nuevo_usuario_contrasena").input(contrasena)
    at.multiselect(key="nuevo_usuario_temas").set_value(list(temas))
    return at.button(key="crear_usuario").click().run()


class CrearEstudiante(unittest.TestCase):
    def test_crear_estudiante_muestra_la_contrasena_para_copiarla(self):
        cliente = ClienteMock()
        at = crear(abrir(cliente))
        self.assertIn("Estudiante creado: Ana Pérez", textos(at.success))
        self.assertEqual(at.code[0].value, "Temporal-2026")  # st.code trae el botón de copiar
        self.assertIn("Pásasela al estudiante. Al entrar, la app le pedirá cambiarla.", textos(at.caption))
        self.assertIn("**Ana Pérez**", textos(at.markdown))
        ana = next(u for u in cliente.listar_usuarios() if u.usuario == "ana")
        self.assertEqual(ana.temas, ["t-redes"])

    def test_la_contrasena_se_guarda_sin_espacios_al_borde(self):
        # Revisión final: un espacio pegado al final dejaba al estudiante sin poder entrar
        cliente = ClienteMock()
        at = crear(abrir(cliente), contrasena="  Temporal-2026 ")
        self.assertEqual(at.code[0].value, "Temporal-2026")
        self.assertTrue(cliente.iniciar_sesion("ana", "Temporal-2026").usuario.debe_cambiar_contrasena)

    def test_la_contrasena_no_reaparece_al_volver_de_otra_pagina(self):
        aviso = {"texto": "Estudiante creado: Ana", "contrasena": "Temporal-2026"}
        at = abrir_pagina(USUARIOS, usuario="admin", estado={"aviso_usuarios": aviso, "pagina_anterior": "temas"})
        self.assertEqual(len(at.code), 0)
        at = abrir_pagina(USUARIOS, usuario="admin", estado={"aviso_usuarios": aviso, "pagina_anterior": "usuarios"})
        self.assertEqual(at.code[0].value, "Temporal-2026")  # seguir en la página no la borra

    def test_generar_una_llena_el_campo(self):
        at = abrir().button(key="generar_nueva").click().run()
        self.assertEqual(len(at.text_input(key="nuevo_usuario_contrasena").value), 14)

    def test_contrasena_corta_avisa_y_no_crea(self):
        cliente = ClienteMock()
        at = crear(abrir(cliente), contrasena="corta")
        self.assertIn("La contraseña temporal debe tener al menos 12 caracteres.", textos(at.warning))
        self.assertNotIn("ana", [u.usuario for u in cliente.listar_usuarios()])

    def test_sin_nombre_avisa(self):
        at = crear(abrir(), nombre="  ")
        self.assertIn("Escribe el nombre y el usuario.", textos(at.warning))

    def test_usuario_repetido_avisa_y_conserva_lo_escrito(self):
        at = crear(abrir(), usuario="laura")
        self.assertIn("Ya existe un usuario con ese nombre de usuario.", textos(at.error))
        self.assertEqual(at.text_input(key="nuevo_usuario_usuario").value, "laura")


class AccionesPorEstudiante(unittest.TestCase):
    def test_lista_con_estado_rol_y_temas(self):
        at = abrir()
        markdown = textos(at.markdown)
        for nombre in ("**Laura Gómez**", "**Mateo Díaz**", "**Andrea Ruiz**"):
            self.assertIn(nombre, markdown)
        self.assertIn("laura · Estudiante · Temas: Redes en OCI, Seguridad en la nube", textos(at.caption))
        self.assertIn("admin · Administración", textos(at.caption))

    def test_la_tarjeta_del_admin_no_tiene_botones(self):
        claves = [b.key for b in abrir().button]
        self.assertFalse(any(clave.endswith("_3") for clave in claves))
        self.assertIn("restablecer_1", claves)

    def test_restablecer_muestra_la_nueva(self):
        cliente = ClienteMock()
        at = abrir(cliente).button(key="restablecer_1").click().run()
        at = at.button(key="generar_1").click().run()
        at = at.button(key="guardar_contrasena_1").click().run()
        self.assertIn("Contraseña restablecida: Laura Gómez", textos(at.success))
        nueva = at.code[0].value
        self.assertEqual(len(nueva), 14)
        self.assertTrue(cliente.iniciar_sesion("laura", nueva).usuario.debe_cambiar_contrasena)

    def test_restablecer_con_contrasena_corta_avisa(self):
        at = abrir().button(key="restablecer_1").click().run()
        at.text_input(key="restablecer_1_contrasena").input("corta")
        at = at.button(key="guardar_contrasena_1").click().run()
        self.assertIn("La contraseña temporal debe tener al menos 12 caracteres.", textos(at.warning))

    def test_cambiar_temas(self):
        cliente = ClienteMock()
        at = abrir(cliente).button(key="temas_1").click().run()
        at.multiselect(key="temas_1_valor").set_value(["t-datos"])
        at = at.button(key="guardar_temas_1").click().run()
        self.assertIn("Temas guardados: Laura Gómez", textos(at.success))
        self.assertEqual(next(u for u in cliente.listar_usuarios() if u.id_usuario == 1).temas, ["t-datos"])

    def test_desactivar_pide_confirmacion_y_activar_no(self):
        cliente = ClienteMock()
        at = abrir(cliente).button(key="desactivar_1").click().run()
        self.assertIn("¿Desactivar a «Laura Gómez»? No podrá iniciar sesión hasta que la actives de nuevo.",
                      textos(at.warning))
        self.assertTrue(next(u for u in cliente.listar_usuarios() if u.id_usuario == 1).activo)
        at = at.button(key="confirmar_desactivar_1").click().run()
        self.assertIn("Cuenta desactivada: Laura Gómez", textos(at.success))
        self.assertIn(":red-badge[Inactiva]", textos(at.markdown))
        at = at.button(key="activar_1").click().run()
        self.assertIn("Cuenta activada: Laura Gómez", textos(at.success))

    def test_desbloquear(self):
        at = abrir().button(key="desbloquear_1").click().run()
        self.assertIn("Cuenta desbloqueada: Laura Gómez", textos(at.success))


class Pagina(unittest.TestCase):
    def test_crear_a_la_izquierda_y_lista_a_la_derecha(self):
        izquierda, derecha = columnas_principales(abrir())
        self.assertIn("crear_usuario", [b.key for b in izquierda.button])
        self.assertIn("**Laura Gómez**", [m.value for m in derecha.markdown])

    def test_solo_para_admin(self):
        self.assertIn("No tienes permiso para ver esta página.", textos(abrir(usuario="laura").error))


if __name__ == "__main__":
    unittest.main()
