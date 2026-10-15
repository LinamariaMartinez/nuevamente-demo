"""Contrato público del Hito 4 y esquemas que se envían a Gemini."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from review_policy import MAX_REVISION_ATTEMPTS, meets_quality_thresholds

MAX_REVISIONS = MAX_REVISION_ATTEMPTS
Text = Annotated[str, Field(min_length=1)]
OutputFormat = Literal["Flashcards", "Resumen", "Quiz", "Tutorial", "Guion"]
UserProfile = Literal["Principiante", "Intermedio", "Avanzado"]
PROFILE_GUIDANCE = {
    "Principiante": "Explica desde cero, define los términos y utiliza ejemplos sencillos.",
    "Intermedio": "Asume conocimientos básicos y explica relaciones y aplicaciones prácticas.",
    "Avanzado": "Profundiza en los detalles técnicos, decisiones y limitaciones presentes en la fuente.",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, str_strip_whitespace=True, allow_inf_nan=False
    )


class GenerationRequest(StrictModel):
    tema: Text = Field(max_length=2000)
    perfil_destinatario: UserProfile
    formato_salida: OutputFormat
    nicho_sector: Text = Field(default="General", max_length=200)
    nivel_detalle: Text = Field(default="Didáctico", max_length=200)


class Flashcard(StrictModel):
    frente: Text
    dorso: Text
    pista_didactica: Text


class SummaryItem(StrictModel):
    subtitulo: Text
    texto: Text


class QuizItem(StrictModel):
    pregunta: Text
    opciones: list[Text] = Field(min_length=2)
    respuesta_correcta: Text = Field(description="Texto exacto de una de las opciones.")
    justificacion: Text

    @model_validator(mode="after")
    def check_answer(self):
        if len(set(self.opciones)) != len(self.opciones):
            raise ValueError("Las opciones del quiz deben ser distintas.")
        if self.respuesta_correcta not in self.opciones:
            raise ValueError("La respuesta correcta debe pertenecer a las opciones.")
        return self


class TutorialStep(StrictModel):
    titulo: Text
    instrucciones: Text


class ScriptSection(StrictModel):
    titulo: Text
    narracion: Text


class ContentBase(StrictModel):
    titulo: Text
    introduccion_contextualizada: Text


class FlashcardsContent(ContentBase):
    items: list[Flashcard] = Field(min_length=1)


class SummaryContent(ContentBase):
    items: list[SummaryItem] = Field(min_length=1)


class QuizContent(ContentBase):
    items: list[QuizItem] = Field(min_length=1)


class TutorialContent(ContentBase):
    items: list[TutorialStep] = Field(min_length=1)


class ScriptContent(ContentBase):
    items: list[ScriptSection] = Field(min_length=1)


AdaptedContent = (
    FlashcardsContent | SummaryContent | QuizContent | TutorialContent | ScriptContent
)
CONTENT_SCHEMAS = {
    "Flashcards": FlashcardsContent,
    "Resumen": SummaryContent,
    "Quiz": QuizContent,
    "Tutorial": TutorialContent,
    "Guion": ScriptContent,
}


class LearningFields(StrictModel):
    tiempo_estimado_estudio_minutos: int = Field(
        ge=1, description="Estimación de minutos de estudio, no de ejecución del sistema."
    )
    conceptos_clave: list[Text] = Field(min_length=1)
    prerrequisitos: list[Text] = Field(
        description="Conocimientos previos necesarios. Lista vacía si no se requieren."
    )


class WriterResult(LearningFields):
    contenido_adaptado: AdaptedContent


class FlashcardsDraft(WriterResult):
    contenido_adaptado: FlashcardsContent


class SummaryDraft(WriterResult):
    contenido_adaptado: SummaryContent


class QuizDraft(WriterResult):
    contenido_adaptado: QuizContent


class TutorialDraft(WriterResult):
    contenido_adaptado: TutorialContent


class ScriptDraft(WriterResult):
    contenido_adaptado: ScriptContent


DRAFT_SCHEMAS = {
    "Flashcards": FlashcardsDraft,
    "Resumen": SummaryDraft,
    "Quiz": QuizDraft,
    "Tutorial": TutorialDraft,
    "Guion": ScriptDraft,
}


class ReviewResult(StrictModel):
    source_anchoring_score: float = Field(ge=0, le=1, description="Fidelidad a las fuentes.")
    pedagogical_score: float = Field(ge=0, le=1, description="Claridad y adecuación al perfil.")
    format_compliance_score: float = Field(ge=0, le=1, description="Cumplimiento del formato solicitado.")
    approved: bool = Field(description="Propuesta del modelo; la decisión se recalcula con los tres umbrales.")
    feedback: Text


class Metadata(LearningFields):
    perfil_aplicado: UserProfile
    formato_generado: OutputFormat
    nicho_sector: Text
    nivel_detalle: Text


class QualityEvaluation(StrictModel):
    anclaje_fuente_score: float = Field(ge=0, le=1)
    calidad_pedagogica_score: float = Field(ge=0, le=1)
    cumplimiento_formato_score: float = Field(ge=0, le=1)
    claridad_pedagogica: Literal["Alta", "Media", "Baja"]
    observaciones: Text
    intentos_revision: int = Field(ge=1, le=MAX_REVISIONS)


class EducationalResponse(StrictModel):
    status: Literal["exito", "requiere_revision"]
    metadatos: Metadata
    contenido_adaptado: AdaptedContent
    evaluacion_calidad: QualityEvaluation

    @model_validator(mode="after")
    def check_consistency(self):
        expected = CONTENT_SCHEMAS[self.metadatos.formato_generado]
        if not isinstance(self.contenido_adaptado, expected):
            raise ValueError("El contenido no corresponde al formato generado.")
        quality = self.evaluacion_calidad
        approved = meets_quality_thresholds(
            quality.anclaje_fuente_score, quality.calidad_pedagogica_score,
            quality.cumplimiento_formato_score,
        )
        expected_status = "exito" if approved else "requiere_revision"
        if self.status != expected_status:
            raise ValueError("El estado debe corresponder a la evaluación de calidad.")
        return self


class ErrorDetail(StrictModel):
    codigo: Text
    mensaje: Text


class ErrorResponse(StrictModel):
    status: Literal["error"] = "error"
    error: ErrorDetail
