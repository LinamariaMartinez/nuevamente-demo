"""Pruebas del contrato de F07 y de los ejemplos de app/mocks/. No necesitan API key."""

import json
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from pydantic import ValidationError

from contrato import FORMATOS, NICHOS, PERFILES, Paquete, SolicitudPaquete, items_validos

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
        datos = {"tema": "Redes VCN", "perfil": PERFILES[0], "formato": "Quiz", "nicho": "General"}
        datos.update(cambios)
        return datos

    def test_solicitud_valida_quita_espacios_y_documentos_va_vacio(self):
        solicitud = SolicitudPaquete(**self.base(tema="  Redes VCN  "))
        self.assertEqual(solicitud.tema, "Redes VCN")
        self.assertEqual(solicitud.documentos, [])

    def test_tema_vacio_falla(self):
        with self.assertRaises(ValidationError):
            SolicitudPaquete(**self.base(tema="   "))

    def test_tema_de_mas_de_300_caracteres_falla(self):
        with self.assertRaises(ValidationError):
            SolicitudPaquete(**self.base(tema="a" * 301))

    def test_valores_fuera_de_las_listas_fallan(self):
        for campo, valor in (("perfil", "Experto"), ("formato", "Podcast"), ("nicho", "Minería")):
            with self.subTest(campo=campo), self.assertRaises(ValidationError):
                SolicitudPaquete(**self.base(**{campo: valor}))


if __name__ == "__main__":
    unittest.main()
