import os
import sys

# Add src folder to path so it can import the graph
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from graph import build_graph
from state import AgentState
from review_policy import MIN_SOURCE_ANCHORING_SCORE


def main():
    print("🚀 Inicializando el Sistema Multi-Agente (LangGraph)...\n")

    # Compilar el grafo
    graph = build_graph()

    # Definir los parámetros de prueba iniciales
    inputs: AgentState = {
        "query": "¿Qué es una VCN y cuáles son sus componentes principales?",
        "user_profile": "Estudiante de secundaria sin conocimientos técnicos previos",
        "output_format": "Explicación sencilla con una analogía cotidiana y 3 flashcards finales",
        "retrieved_docs": [],
        "current_draft": "",
        "review_feedback": "",
        "revision_attempts": 0,
        "source_anchoring_score": 0.0,
        "final_content": "",
        "approved": False,
        "review_status": "pending",
        "niche": "Educación secundaria",
    }

    print("-" * 50)
    print(f"Pregunta: {inputs['query']}")
    print(f"Perfil: {inputs['user_profile']}")
    print(f"Formato: {inputs['output_format']}")
    print("-" * 50 + "\n")

    # Ejecutar el grafo de principio a fin
    # graph.invoke() maneja automáticamente el paso del estado de nodo a nodo
    final_state = graph.invoke(inputs)

    if not final_state.get("approved", False):
        print("CONTENIDO NO APROBADO")
        print(final_state.get("review_feedback", ""))
        raise AssertionError(
            f"El flujo terminó sin aprobación: {final_state.get('review_status')}; "
            f"score={final_state.get('source_anchoring_score')}"
        )
    assert final_state["source_anchoring_score"] >= MIN_SOURCE_ANCHORING_SCORE
    assert final_state["review_status"] == "approved"
    assert final_state["final_content"] == final_state["current_draft"]
    assert final_state["final_content"].strip(), "El contenido aprobado está vacío"

    print("\n" + "=" * 50)
    print("🎉 CONTENIDO FINAL APROBADO")
    print("=" * 50)
    print(final_state["final_content"])
    print("\n" + "=" * 50)
    print(f"Score de Fidelidad: {final_state['source_anchoring_score']}")
    print(f"Calidad pedagógica: {final_state['pedagogical_score']}")
    print(f"Cumplimiento de formato: {final_state['format_compliance_score']}")
    print(f"Intentos de Revisión: {final_state['revision_attempts']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
