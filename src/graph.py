from langgraph.graph import StateGraph, END
from state import AgentState

# Importamos los nodos (agentes)
from agents.researcher import researcher_node
from agents.writer import writer_node
from agents.reviewer import reviewer_node

from review_policy import MAX_REVISION_ATTEMPTS

def check_score(state: AgentState) -> str:
    """
    Función de borde condicional.
    Decide si el borrador pasa la revisión o si necesita volver al redactor.
    """
    score = state.get("source_anchoring_score", 0.0)
    attempts = state.get("revision_attempts", 0)
    
    if state.get("review_status") in ("no_source_context", "empty_draft"):
        return "invalid_content"
    if state.get("approved", False):
        print(f"🏁 [Orquestador] ¡Borrador Aprobado! Puntaje: {score}")
        return "approved"
    elif attempts >= MAX_REVISION_ATTEMPTS:
        print(f"⚠️ [Orquestador] Límite de intentos alcanzado. Contenido no aprobado. Puntaje: {score}")
        return "max_attempts_reached"
    else:
        print(f"🔄 [Orquestador] Borrador Rechazado (Puntaje: {score}). Devolviendo al Redactor...")
        return "needs_revision"

def build_graph():
    """Construye y compila el LangGraph multi-agente."""
    # 1. Inicializamos el Grafo con nuestro TypedDict State
    builder = StateGraph(AgentState)
    
    # 2. Agregamos todos los nodos (agentes)
    builder.add_node("researcher", researcher_node)
    builder.add_node("writer", writer_node)
    builder.add_node("reviewer", reviewer_node)
    
    # 3. Definimos el flujo principal (conexiones)
    builder.set_entry_point("researcher")
    builder.add_edge("researcher", "writer")
    builder.add_edge("writer", "reviewer")
    
    # 4. Definimos el Borde Condicional (El Ciclo)
    # La salida de 'check_score' determina el siguiente paso.
    builder.add_conditional_edges(
        "reviewer",
        check_score,
        {
            "approved": END,               # Si es aprobado, termina el grafo
            "needs_revision": "writer",    # Si es rechazado, vuelve al redactor
            "invalid_content": END,
            "max_attempts_reached": END,    # Termina sin aprobar el borrador
        }
    )
    
    # 5. Compilamos y devolvemos
    return builder.compile()
