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
