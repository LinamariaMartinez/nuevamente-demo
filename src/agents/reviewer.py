import os
import sys

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field, SecretStr

# Permite importar módulos ubicados directamente dentro de src/
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from state import AgentState
from the_keys import GEMINI_API_KEY
from the_models import GEMINI_LIGERO
from agents.retry import invoke_with_retry
from review_policy import MAX_REVISION_ATTEMPTS


class ReviewResult(BaseModel):
    """
    Estructura de salida del Agente Revisor.

    El revisor evalúa tres dimensiones independientes:
    1. Fidelidad al contexto recuperado por RAG.
    2. Calidad pedagógica.
    3. Cumplimiento del formato solicitado.
    """

    source_anchoring_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Score from 0.0 to 1.0 measuring how faithfully "
            "the draft is supported by the retrieved source context."
        ),
    )

    pedagogical_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Score from 0.0 to 1.0 evaluating clarity, organization, "
            "and suitability for the target user profile."
        ),
    )

    format_compliance_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Score from 0.0 to 1.0 evaluating whether the requested "
            "output format was correctly followed."
        ),
    )

    approved: bool = Field(
        description=(
            "True only if the draft is sufficiently faithful to "
            "the sources and meets the pedagogical and formatting "
            "requirements."
        ),
    )

    feedback: str = Field(
        description=(
            "Specific feedback for the Writer Agent. Explain "
            "unsupported claims, omissions, pedagogical problems, "
            "or formatting errors."
        ),
    )


def reviewer_node(state: AgentState) -> dict:
    """
    Revisa el borrador generado por el Writer Agent.

    Responsabilidades:
    - Comparar el contenido generado contra las fuentes recuperadas.
    - Detectar afirmaciones no respaldadas o posibles alucinaciones.
    - Evaluar claridad y adecuación pedagógica.
    - Validar que se respete el formato solicitado.
    - Generar feedback para una posible nueva iteración del Writer.
    """

    print(
        "[Reviewer Agent] Evaluating source fidelity, "
        "pedagogical quality and format..."
    )

    # 1. Extraer la información necesaria del estado.
    query = state.get("query", "")
    user_profile = state.get(
        "user_profile",
        "General Audience",
    )
    output_format = state.get(
        "output_format",
        "Summary",
    )
    current_draft = state.get(
        "current_draft",
        "",
    )
    retrieved_docs = state.get(
        "retrieved_docs",
        [],
    )
    revision_attempts = state.get(
        "revision_attempts",
        0,
    )

    # 2. Validar que exista contexto recuperado.
    # Sin contexto RAG no podemos comprobar fidelidad.
    if not retrieved_docs:
        return {
            "source_anchoring_score": 0.0,
            "pedagogical_score": 0.0,
            "format_compliance_score": 0.0,
            "approved": False,
            "review_status": "no_source_context",
            "review_feedback": (
                "No retrieved source context was available. "
                "The content cannot be validated."
            ),
            "revision_attempts": revision_attempts + 1,
            "final_content": "",
            "requires_admin_review": True,
        }

    # 3. Validar que Writer haya producido contenido.
    if not current_draft.strip():
        return {
            "source_anchoring_score": 0.0,
            "pedagogical_score": 0.0,
            "format_compliance_score": 0.0,
            "approved": False,
            "review_status": "empty_draft",
            "review_feedback": (
                "The Writer Agent returned an empty draft."
            ),
            "revision_attempts": revision_attempts + 1,
            "final_content": "",
            "requires_admin_review": True,
        }

    # 4. Unir los documentos recuperados para construir
    # el contexto que utilizará el Reviewer.
    context = "\n\n".join(
        doc.page_content for doc in retrieved_docs
    )

    # 5. Usar el modelo ligero compatible con la configuración de F02.
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_LIGERO,
        api_key=(
            SecretStr(GEMINI_API_KEY)
            if GEMINI_API_KEY
            else None
        ),
    )

    # Structured Output permite recibir una estructura validada
    # en lugar de depender de parsing manual.
    structured_llm = llm.with_structured_output(
        ReviewResult
    )

    # 6. Prompt del Agente Revisor.
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are the Reviewer Agent of a multi-agent educational
content system.

Your task is to evaluate a draft generated from retrieved
technical documentation.

You MUST evaluate three independent dimensions:

1. SOURCE FIDELITY

Determine whether every technical claim in the draft is
supported by the provided source context.

Penalize:

- hallucinated facts
- unsupported numbers
- invented features
- claims that contradict the source
- important technical distortions

2. PEDAGOGICAL QUALITY

Determine whether the explanation is clear and appropriate
for the requested user profile.

Evaluate:

- clarity
- vocabulary
- organization
- complexity
- usefulness for the specified audience

3. FORMAT COMPLIANCE

Determine whether the draft follows the requested output
format.

IMPORTANT RULES:

- Use ONLY the supplied source context.
- Do NOT use outside knowledge.
- Do NOT correct the draft yourself.
- Instead, provide precise feedback that the Writer Agent
  can use in the next revision.
- Be strict about unsupported technical claims.

Approval criteria:

- source_anchoring_score >= 0.80
- pedagogical_score >= 0.75
- format_compliance_score >= 0.75

The draft should only be approved when ALL three conditions
are met.

SOURCE CONTEXT:

{context}
""",
            ),
            (
                "human",
                """
Topic:

{query}

Target user profile:

{user_profile}

Requested output format:

{output_format}

Target niche:

{niche}

DRAFT TO REVIEW:

{draft}
""",
            ),
        ]
    )

    # 7. Construir la cadena.
    chain = prompt | structured_llm

    result = invoke_with_retry(chain, {
        "context": context,
        "query": query,
        "user_profile": user_profile,
        "output_format": output_format,
        "niche": state.get("niche", "General"),
        "draft": current_draft,
    })

    # Validación defensiva.
    if result is None:
        raise RuntimeError(
            "Reviewer Agent could not obtain a response "
            "from the LLM."
        )

    # 8. Calcular la aprobación en código.
    #
    # Aunque el modelo devuelve el campo "approved",
    # la decisión final no depende únicamente del LLM.
    # Aplicamos umbrales objetivos y reproducibles.
    approved = (
        result.source_anchoring_score >= 0.80
        and result.pedagogical_score >= 0.75
        and result.format_compliance_score >= 0.75
    )

    review_status = ("approved" if approved else
                     "max_attempts_reached" if revision_attempts + 1 >= MAX_REVISION_ATTEMPTS
                     else "needs_revision")

    print(
        "[Reviewer Agent] Evaluation complete.\n"
        f"Source anchoring: "
        f"{result.source_anchoring_score:.2f}\n"
        f"Pedagogical quality: "
        f"{result.pedagogical_score:.2f}\n"
        f"Format compliance: "
        f"{result.format_compliance_score:.2f}\n"
        f"Approved: {approved}"
    )

    # 9. Actualizar el estado compartido de LangGraph.
    state_update = {
        "source_anchoring_score": (
            result.source_anchoring_score
        ),
        "pedagogical_score": (
            result.pedagogical_score
        ),
        "format_compliance_score": (
            result.format_compliance_score
        ),
        "approved": approved,
        "requires_admin_review": not approved,
        "final_content": current_draft if approved else "",
        "review_status": review_status,
        "review_feedback": result.feedback,
        "revision_attempts": revision_attempts + 1,
    }

    # Solo existe contenido final cuando realmente
    # fue aprobado por los criterios del Reviewer.
    if approved:
        state_update["final_content"] = current_draft

    return state_update
