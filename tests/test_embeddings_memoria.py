"""Pruebas de la memoria de embeddings (src/chunk_embeddings.py). No llaman a Gemini: usan un modelo falso."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import chunk_embeddings


class ModeloFalso(Embeddings):
    """Vectores deterministas y registro de cada texto que se pidió."""

    def __init__(self):
        self.documentos_pedidos = []
        self.consultas_pedidas = []

    @staticmethod
    def _vector(texto):
        return [len(texto) / 7.0, sum(map(ord, texto)) % 97 / 3.0, 0.123456789012345]

    def embed_documents(self, texts):
        self.documentos_pedidos.extend(texts)
        return [self._vector(t) for t in texts]

    def embed_query(self, text):
        self.consultas_pedidas.append(text)
        return self._vector(text)


DOCS = [
    Document(page_content="El fraude autorizado ocurre cuando el cliente paga engañado.", metadata={"source": "a.md"}),
    Document(page_content="Centinela retiene los pagos con puntaje de 70 a 100.", metadata={"source": "a.md"}),
]


class MemoriaDeEmbeddingsTest(unittest.TestCase):
    def setUp(self):
        chunk_embeddings._VECTORES.clear()
        self.falso = ModeloFalso()
        parche = patch.object(chunk_embeddings, "GoogleGenerativeAIEmbeddings", return_value=self.falso)
        parche.start()
        self.addCleanup(parche.stop)

    def test_la_segunda_vez_no_vuelve_a_pedir_los_mismos_fragmentos(self):
        chunk_embeddings.crear_vectorstore(DOCS)
        pedidos_primera = len(self.falso.documentos_pedidos)
        chunk_embeddings.crear_vectorstore(DOCS)
        self.assertEqual(pedidos_primera, 2)
        self.assertEqual(len(self.falso.documentos_pedidos), 2)

    def test_los_vectores_son_identicos_a_los_del_modelo(self):
        modelo = chunk_embeddings.crear_modelo_embeddings()
        textos = [d.page_content for d in DOCS]
        primera = modelo.embed_documents(textos)
        segunda = modelo.embed_documents(textos)
        esperado = [ModeloFalso._vector(t) for t in textos]
        self.assertEqual(primera, esperado)
        self.assertEqual(segunda, esperado)

    def test_solo_pide_los_fragmentos_nuevos_y_respeta_el_orden(self):
        modelo = chunk_embeddings.crear_modelo_embeddings()
        modelo.embed_documents(["uno", "dos"])
        resultado = modelo.embed_documents(["tres", "uno", "tres"])
        self.assertEqual(self.falso.documentos_pedidos, ["uno", "dos", "tres"])
        self.assertEqual(resultado, [ModeloFalso._vector(t) for t in ("tres", "uno", "tres")])

    def test_las_consultas_siempre_van_al_modelo(self):
        modelo = chunk_embeddings.crear_modelo_embeddings()
        modelo.embed_query("¿qué es una cuenta mula?")
        modelo.embed_query("¿qué es una cuenta mula?")
        self.assertEqual(len(self.falso.consultas_pedidas), 2)

    def test_la_busqueda_devuelve_lo_mismo_con_y_sin_memoria(self):
        consulta = "puntaje de Centinela"
        con_memoria = chunk_embeddings.crear_vectorstore(DOCS).similarity_search(consulta, k=2)
        chunk_embeddings._VECTORES.clear()
        sin_memoria = chunk_embeddings.crear_vectorstore(DOCS).similarity_search(consulta, k=2)
        self.assertEqual([d.page_content for d in con_memoria], [d.page_content for d in sin_memoria])

    def test_la_memoria_tiene_tope(self):
        modelo = chunk_embeddings.crear_modelo_embeddings()
        with patch.object(chunk_embeddings, "MAXIMO_VECTORES_EN_MEMORIA", 3):
            modelo.embed_documents(["a", "b", "c", "d"])
        self.assertEqual(len(chunk_embeddings._VECTORES), 3)


if __name__ == "__main__":
    unittest.main()
