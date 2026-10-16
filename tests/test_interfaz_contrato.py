"""Pruebas del contrato de F07 y de los ejemplos de app/mocks/. No necesitan API key."""

import json
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from pydantic import ValidationError

from contrato import (FORMATOS, NICHOS, PERFILES, Configuracion, DatosTema, Paquete, Sesion, SolicitudPaquete,
                      Tema, Usuario, items_validos)

MOCKS = RAIZ / "app" / "mocks"


def cargar(nombre):
    return json.loads((MOCKS / nombre).read_text(encoding="utf-8"))


class MocksCumplenContrato(unittest.TestCase):
    def test_hay_un_mock_por_formato_y_uno_de_error(self):
        nombres = {ruta.name for ruta in MOCKS.glob("*.json")}
        self.assertEqual(nombres, {"flashcards.json", "quiz.json", "tutorial.json",
                                   "resumen.json", "guion.json", "error_sin_contexto.json"})

    def test_cada_mock_es_un_paquete_valido(self):
        for ruta in MOCKS.glob("*.json"):
            with self.subTest(mock=ruta.name):
                Paquete.model_validate(cargar(ruta.name))

    def test_items_de_cada_mock_de_exito_cumplen_su_formato(self):
        for ruta in MOCKS.glob("*.json"):
            paquete = Paquete.model_validate(cargar(ruta.name))
            if paquete.status == "exito":
                with self.subTest(mock=ruta.name):
                    self.assertGreater(len(items_validos(paquete)), 0)

    def test_valores_de_los_mocks_estan_en_las_listas_fijas(self):
        for ruta in MOCKS.glob("*.json"):
            paquete = Paquete.model_validate(cargar(ruta.name))
            if paquete.status == "exito":
                with self.subTest(mock=ruta.name):
                    self.assertIn(paquete.metadatos.perfil_aplicado, PERFILES)
                    self.assertIn(paquete.metadatos.formato_generado, FORMATOS)
                    self.assertIn(paquete.metadatos.nicho_sector, NICHOS)


class ReglasDelPaquete(unittest.TestCase):
    def test_exito_sin_contenido_no_es_valido(self):
        datos = cargar("quiz.json")
        datos["contenido_adaptado"] = None
        with self.assertRaises(ValidationError):
            Paquete.model_validate(datos)

    def test_error_sin_codigo_no_es_valido(self):
        datos = cargar("error_sin_contexto.json")
        datos["codigo_error"] = None
        with self.assertRaises(ValidationError):
            Paquete.model_validate(datos)

    def test_codigo_error_desconocido_no_es_valido(self):
        datos = cargar("error_sin_contexto.json")
        datos["codigo_error"] = "otro_codigo"
        with self.assertRaises(ValidationError):
            Paquete.model_validate(datos)

    def test_puntaje_fuera_de_0_a_1_no_es_valido(self):
        datos = cargar("quiz.json")
        datos["evaluacion_calidad"]["anclaje_fuente_score"] = 1.5
        with self.assertRaises(ValidationError):
            Paquete.model_validate(datos)

    def test_quiz_con_respuesta_fuera_de_rango_falla_solo_en_los_items(self):
        datos = cargar("quiz.json")
        datos["contenido_adaptado"]["items"][0]["respuesta_correcta"] = 9
        paquete = Paquete.model_validate(datos)  # el paquete sigue siendo válido
        with self.assertRaises(ValidationError):
            items_validos(paquete)

    def test_quiz_con_opciones_repetidas_falla_en_los_items(self):
        datos = cargar("quiz.json")
        datos["contenido_adaptado"]["items"][0]["opciones"] = ["A", "A", "B"]
        with self.assertRaises(ValidationError):
            items_validos(Paquete.model_validate(datos))


class ListasFijas(unittest.TestCase):
    def test_perfiles_son_los_tres_niveles_del_redactor(self):
        # Acordado en la weekly del 13-oct: los mismos niveles que usa el Redactor (writer_examples.py)
        self.assertEqual(PERFILES, ("Principiante", "Intermedio", "Avanzado"))


class ReglasDeLaSolicitud(unittest.TestCase):
    def base(self, **cambios):
        datos = {"id_tema": "t-redes", "tema": "", "perfil": PERFILES[0], "formato": "Quiz"}
        datos.update(cambios)
        return datos

    def test_pedido_vacio_es_valido_y_se_quitan_espacios(self):
        self.assertEqual(SolicitudPaquete(**self.base()).tema, "")
        self.assertEqual(SolicitudPaquete(**self.base(tema="  subredes  ")).tema, "subredes")

    def test_sin_id_tema_falla(self):
        with self.assertRaises(ValueError):
            SolicitudPaquete(**self.base(id_tema=""))

    def test_pedido_de_mas_de_300_caracteres_falla(self):
        with self.assertRaises(ValueError):
            SolicitudPaquete(**self.base(tema="a" * 301))

    def test_valores_fuera_de_las_listas_fallan(self):
        for campo, valor in (("perfil", "Experto"), ("formato", "Podcast")):
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                SolicitudPaquete(**self.base(**{campo: valor}))

    def test_la_solicitud_no_lleva_nicho_ni_documentos(self):
        # El sector lo define el admin; los documentos salen del tema
        self.assertNotIn("nicho", SolicitudPaquete.model_fields)
        self.assertNotIn("documentos", SolicitudPaquete.model_fields)


class ConfiguracionDeLaInstitucion(unittest.TestCase):
    def test_sector_por_defecto_es_general(self):
        self.assertEqual(Configuracion().sector, "General")

    def test_sector_valido(self):
        self.assertEqual(Configuracion(sector="Salud").sector, "Salud")

    def test_sector_fuera_de_la_lista_falla(self):
        with self.assertRaises(ValidationError):
            Configuracion(sector="Minería")


INSTITUCION = MOCKS / "institucion"


class CuentasYTemasDeDemostracion(unittest.TestCase):
    def setUp(self):
        self.cuentas = json.loads((INSTITUCION / "usuarios.json").read_text(encoding="utf-8"))
        self.temas = [Tema.model_validate(t) for t in
                      json.loads((INSTITUCION / "temas.json").read_text(encoding="utf-8"))]

    def test_hay_un_admin_un_estudiante_y_uno_con_contrasena_temporal(self):
        usuarios = [Usuario.model_validate(c["usuario"]) for c in self.cuentas]
        self.assertEqual(sorted(u.rol for u in usuarios), ["admin", "estudiante", "estudiante"])
        self.assertEqual([u.usuario for u in usuarios if u.debe_cambiar_contrasena], ["mateo"])
        self.assertTrue(all(c["contrasena"] for c in self.cuentas))

    def test_los_temas_asignados_existen(self):
        ids = {t.id_tema for t in self.temas}
        for cuenta in self.cuentas:
            with self.subTest(usuario=cuenta["usuario"]["usuario"]):
                self.assertLessEqual(set(cuenta["usuario"]["temas"]), ids)

    def test_cada_tema_tiene_documentos(self):
        for tema in self.temas:
            with self.subTest(tema=tema.id_tema):
                self.assertTrue(tema.documentos)


class ReglasDeCuentasYTemas(unittest.TestCase):
    def usuario(self, **cambios):
        datos = {"id_usuario": "u-1", "nombre": "Ana", "usuario": "ana", "rol": "estudiante"}
        datos.update(cambios)
        return Usuario(**datos)

    def test_usuario_por_defecto_activo_y_sin_cambio_pendiente(self):
        usuario = self.usuario()
        self.assertTrue(usuario.activo)
        self.assertFalse(usuario.debe_cambiar_contrasena)
        self.assertEqual(usuario.temas, [])

    def test_rol_desconocido_falla(self):
        with self.assertRaises(ValueError):
            self.usuario(rol="profesor")

    def test_sesion_lleva_token_y_usuario(self):
        sesion = Sesion(token="abc", usuario=self.usuario())
        self.assertEqual(sesion.usuario.nombre, "Ana")

    def test_datos_tema_validos_quitan_espacios_y_repetidos(self):
        datos = DatosTema(nombre="  Redes  ", descripcion=" VCN ", documentos=["a.pdf", "a.pdf", "b.md"])
        self.assertEqual((datos.nombre, datos.descripcion, datos.documentos), ("Redes", "VCN", ["a.pdf", "b.md"]))

    def test_datos_tema_sin_nombre_o_sin_documentos_fallan(self):
        for cambios in ({"nombre": "   "}, {"documentos": []}, {"nombre": "x" * 101}, {"descripcion": "x" * 501}):
            with self.subTest(cambios=cambios):
                datos = {"nombre": "Redes", "descripcion": "", "documentos": ["a.pdf"]}
                datos.update(cambios)
                with self.assertRaises(ValueError):
                    DatosTema(**datos)


if __name__ == "__main__":
    unittest.main()
