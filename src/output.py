"""Salida F06: conserva la política de revisión de la rama del equipo."""

from schemas import DRAFT_SCHEMAS, EducationalResponse, Metadata, QualityEvaluation
from review_policy import meets_quality_thresholds
from state import AgentState


def finalize_node(state: AgentState) -> dict:
    draft = DRAFT_SCHEMAS[state["output_format"]].model_validate(state["structured_draft"])
    source = state["source_anchoring_score"]
    pedagogy = state["pedagogical_score"]
    format_score = state["format_compliance_score"]
    approved = meets_quality_thresholds(source, pedagogy, format_score)
    clarity = "Alta" if pedagogy >= 0.75 else "Media" if pedagogy >= 0.5 else "Baja"
    response = EducationalResponse(
        status="exito" if approved else "requiere_revision",
        metadatos=Metadata(
            perfil_aplicado=state["user_profile"], formato_generado=state["output_format"],
            nicho_sector=state.get("niche", "General"),
            nivel_detalle=state.get("detail_level", "Didáctico"),
            tiempo_estimado_estudio_minutos=draft.tiempo_estimado_estudio_minutos,
            conceptos_clave=draft.conceptos_clave, prerrequisitos=draft.prerrequisitos,
        ),
        contenido_adaptado=draft.contenido_adaptado,
        evaluacion_calidad=QualityEvaluation(
            anclaje_fuente_score=source, calidad_pedagogica_score=pedagogy,
            cumplimiento_formato_score=format_score, claridad_pedagogica=clarity,
            observaciones=state["review_feedback"],
            intentos_revision=state["revision_attempts"],
        ),
    )
    # final_content conserva el contrato Hito 3: solo existe cuando se aprobó.
    return {"final_response": response.model_dump(mode="json"),
            "final_json": response.model_dump_json(indent=2)}
