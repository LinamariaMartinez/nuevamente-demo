import os
import sys

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

# Agregamos la carpeta src al path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from state import AgentState
from the_keys import GEMINI_API_KEY
from the_models import GEMINI_LIGERO
from agents.retry import invoke_with_retry
from agents.writer_examples import profile_examples


def writer_node(state: AgentState) -> dict:
    """Nodo responsable de redactar contenido pedagógico basado en el contexto recuperado."""
    print("✍️  [Agente Redactor] Redactando contenido basado en el perfil y formato...")
    
    # 1. Extraer los datos del estado
    query = state.get("query", "")
    user_profile = state.get("user_profile", "Audiencia General")
    output_format = state.get("output_format", "Resumen")
    retrieved_docs = state.get("retrieved_docs", [])
    if not retrieved_docs:
        return {"current_draft": ""}
    niche = state.get("niche", "General")
    review_feedback = state.get("review_feedback", "")
    
    # 2. Combinar los documentos recuperados en un solo bloque de contexto
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])
    
    # Incluir los comentarios del revisor si existen (para el ciclo de corrección)
    feedback_section = (
        f"\n\nCOMENTARIOS CRÍTICOS DEL REVISOR PARA CORREGIR EN ESTE NUEVO BORRADOR:\n{review_feedback}\n"
        if review_feedback
        else ""
    )
    
    # 3. Inicializar el LLM
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_LIGERO, # Usamos el modelo ligero para la revisión (originalmente va GEMINI_GENERACION, pero suele estar saturado)
        api_key=SecretStr(GEMINI_API_KEY) if GEMINI_API_KEY else None,
        # temperature=0.4,  # Deshabilitado temporalmente: flash-lite usa defaults fijos
    )
    
    # 4. Crear la plantilla del Prompt (Role Prompting en Español)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Eres un redactor pedagógico experto y comunicador técnico. 
Tu tarea es explicar conceptos técnicos complejos de una manera clara, atractiva y altamente precisa.

INSTRUCCIONES:
- Debes adaptar tu tono, vocabulario y profundidad para que coincida con el Perfil del Usuario objetivo: {user_profile}.
- Debes estructurar tu respuesta estrictamente en el Formato Solicitado: {output_format}.
- Adapta los ejemplos al nicho solicitado: {niche}, sin añadir hechos ajenos a las fuentes.
- CRÍTICO: Debes basar tu explicación EXCLUSIVAMENTE en el Contexto Técnico proporcionado. 
  No introduzcas datos externos ni inventes (alucines) características que no se mencionen en el contexto.

EJEMPLOS DE ESTILO:
- Los turnos de ejemplo son ficticios: ilustran la adaptación al perfil y cómo reconocer información ausente.
- No son fuentes de la consulta real. No copies sus nombres, hechos ni respuestas al contenido solicitado.
- Aunque los ejemplos usan Resumen, respeta el formato y el nicho de la petición real.
- Usa exclusivamente el contexto técnico de la última petición para los hechos de tu respuesta.
""",
            ),
            *profile_examples(user_profile),
            ("human", "PETICIÓN REAL\nCONTEXTO TÉCNICO:\n{context}\n\nTema a explicar: {query}{feedback_section}"),
        ]
    )
    
    # 5. Construir y ejecutar la cadena
    chain = prompt | llm
    response = invoke_with_retry(chain,
        {
            "user_profile": user_profile,
            "output_format": output_format,
            "context": context,
            "query": query,
            "feedback_section": feedback_section,
            "niche": niche,
        }
    )
    
    print("✅ [Agente Redactor] Borrador completado.")
    
    # 6. Extraer el texto limpio (flash-lite a veces devuelve una lista de bloques)
    content = response.content
    if isinstance(content, list):
        # Extraemos solo el texto de los bloques
        text_blocks = [block["text"] for block in content if isinstance(block, dict) and "text" in block]
        content = "\n".join(text_blocks) if text_blocks else str(content)
    
    # 7. Devolver el estado actualizado
    return {"current_draft": content}
