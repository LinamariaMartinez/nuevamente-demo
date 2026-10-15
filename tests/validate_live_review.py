"""Validación manual con Gemini real; requiere .env e índice FAISS generado."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import graph
from chunk_embeddings import cargar_vectorstore
from agents.reviewer import reviewer_node


def main():
    vectorstore = cargar_vectorstore()
    for query, expected in [
        ('¿Qué permite salir a internet sin recibir conexiones entrantes?', 'arquitectura_redes_vcn_oci.md'),
        ('¿Cuál es el límite por noche para alojamiento en hoteles?', 'politica_reembolsos_viajes_gastos.pdf'),
    ]:
        docs = vectorstore.similarity_search(query, k=1)
        assert docs and Path(docs[0].metadata['source']).name == expected
        print('PASS recuperación:', expected, flush=True)

    evaluations = []
    actual_writer = graph.writer_node

    def writer(state):
        if state.get('revision_attempts', 0) == 0:
            return {'current_draft': 'Oracle VCN incluye obligatoriamente una conexión Starlink gratuita de 100 Gbps y cobertura satelital ilimitada.'}
        return actual_writer(state)

    def reviewer(state):
        update = reviewer_node(state)
        evaluations.append(update['source_anchoring_score'])
        return update

    with patch.object(graph, 'writer_node', writer), patch.object(graph, 'reviewer_node', reviewer):
        result = graph.build_graph().invoke({
            'query': '¿Qué es una VCN y cuáles son sus componentes principales?',
            'user_profile': 'Principiante', 'output_format': 'Resumen breve',
            'review_feedback': '', 'revision_attempts': 0, 'final_content': '',
        })
    assert evaluations[0] < 0.8, 'Reviewer no rechazó el borrador falso'
    assert result['revision_attempts'] <= 3
    assert result['approved'], f"No se logró autocorregir: {result['review_status']}"
    assert result['final_content'] == result['current_draft']
    print('PASS rechazo y autocorrección real. Scores:', evaluations, flush=True)
    print(result['final_content'], flush=True)


if __name__ == '__main__':
    main()
