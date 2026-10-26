from typing import List, TypedDict

from langchain_core.documents import Document


class AgentState(TypedDict, total=False):
    # --- Input Parameters ---
    query: str
    user_profile: str
    output_format: str
    niche: str

    # --- Internal Graph State ---
    retrieved_docs: List[Document]
    current_draft: str
    review_feedback: str
    revision_attempts: int

    # --- Reviewer Metrics ---
    source_anchoring_score: float
    pedagogical_score: float
    format_compliance_score: float
    approved: bool
    review_status: str

    # --- Final Output ---
    final_content: str
    requires_admin_review: bool
    almacenamiento_oci: dict

    # --- Salida estructurada F06 y fuente aislada de la API ---
    detail_level: str
    source_docs: List[Document]
    structured_draft: dict
    final_response: dict
    final_json: str
