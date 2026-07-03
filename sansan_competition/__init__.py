"""Sansan competition package."""

from .analysis import analyze_submissions, build_ai_task_input
from .contract import (
    SCHEMA_VERSION,
    build_error_response,
    build_reminder_generation_response,
    build_submission_analysis_response,
    validate_agent_output,
)
from .normalization import (
    normalize_course,
    normalize_coursework,
    normalize_submission,
    normalize_submission_batch,
)

__all__ = [
    "SCHEMA_VERSION",
    "analyze_submissions",
    "build_ai_task_input",
    "build_error_response",
    "build_reminder_generation_response",
    "build_submission_analysis_response",
    "normalize_course",
    "normalize_coursework",
    "normalize_submission",
    "normalize_submission_batch",
    "validate_agent_output",
]
