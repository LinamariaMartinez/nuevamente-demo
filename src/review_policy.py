"""Criterios compartidos por el Reviewer y el orquestador."""

MIN_SOURCE_ANCHORING_SCORE = 0.8
MAX_REVISION_ATTEMPTS = 3

MIN_PEDAGOGICAL_SCORE = 0.75
MIN_FORMAT_COMPLIANCE_SCORE = 0.75


def meets_quality_thresholds(source: float, pedagogy: float, format_score: float) -> bool:
    return (
        source >= MIN_SOURCE_ANCHORING_SCORE
        and pedagogy >= MIN_PEDAGOGICAL_SCORE
        and format_score >= MIN_FORMAT_COMPLIANCE_SCORE
    )
