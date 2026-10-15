"""Servicio de generación compartido por la API y el CLI."""

from schemas import EducationalResponse, GenerationRequest
from errors import ConfigurationError, NoContextError
from langchain_core.documents import Document


def generate_content(
    request: GenerationRequest, *, source_docs: list[Document] | None = None
) -> EducationalResponse:
    # La importación diferida permite consultar los esquemas sin configurar Gemini.
    from graph import build_graph
    from the_keys import GEMINI_API_KEY

    request = GenerationRequest.model_validate(request)
    if not GEMINI_API_KEY or GEMINI_API_KEY.lower() in {"tu_api_key_aqui", "tu_clave_aqui"}:
        raise ConfigurationError("Configura GEMINI_API_KEY en el archivo .env.")
    inputs = {
        "query": request.tema,
        "user_profile": request.perfil_destinatario,
        "output_format": request.formato_salida,
        "niche": request.nicho_sector,
        "detail_level": request.nivel_detalle,
        "revision_attempts": 0,
        "review_feedback": "",
    }
    if source_docs is not None:
        inputs["source_docs"] = source_docs
    state = build_graph().invoke(inputs)
    if state.get("review_status") in {"no_source_context", "empty_draft"}:
        raise NoContextError("La fuente o el borrador no contienen texto utilizable.")
    return EducationalResponse.model_validate(state["final_response"])
