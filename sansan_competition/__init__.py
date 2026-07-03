"""Sansan competition package."""

from .analysis import analyze_submissions, build_ai_task_input
from .classroom import (
    GoogleClassroomClient,
    build_classroom_announcement_request,
    build_post_only_client,
    build_student_name_lookup,
    fetch_submission_analysis,
)
from .contract import (
    SCHEMA_VERSION,
    build_agent_output,
    build_error_response,
    build_reminder_generation_response,
    build_submission_analysis_response,
    validate_agent_output,
    validate_agent_output_dict,
)
from .contracts import ALLOWED_AGENT_TASK_TYPES, ALLOWED_STATUSES
from .exporters import (
    GoogleDocumentExportResult,
    MarkdownExportResult,
    create_google_document_from_output,
    extract_output_payload,
    render_google_document_html,
    save_markdown_output,
)
from .models import AgentTaskType, Course, CourseWork, StudentSubmission
from .normalization import (
    normalize_course,
    normalize_coursework,
    normalize_submission,
    normalize_submission_batch,
)
from .oauth import (
    CLASSROOM_ANNOUNCEMENTS_SCOPE,
    CLASSROOM_COURSES_READONLY_SCOPE,
    CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE,
    CLASSROOM_ROSTERS_READONLY_SCOPE,
    DOCUMENTS_SCOPE,
    DRIVE_FILE_SCOPE,
    GoogleOAuthConfig,
    build_google_service,
    default_classroom_post_scopes,
    default_classroom_read_scopes,
    load_google_user_credentials,
)

__all__ = [
    "SCHEMA_VERSION",
    "ALLOWED_AGENT_TASK_TYPES",
    "ALLOWED_STATUSES",
    "AgentTaskType",
    "GoogleClassroomClient",
    "GoogleOAuthConfig",
    "Course",
    "CourseWork",
    "StudentSubmission",
    "GoogleDocumentExportResult",
    "MarkdownExportResult",
    "CLASSROOM_ANNOUNCEMENTS_SCOPE",
    "CLASSROOM_COURSES_READONLY_SCOPE",
    "CLASSROOM_COURSEWORK_STUDENTS_READONLY_SCOPE",
    "CLASSROOM_ROSTERS_READONLY_SCOPE",
    "DOCUMENTS_SCOPE",
    "DRIVE_FILE_SCOPE",
    "analyze_submissions",
    "build_agent_output",
    "build_ai_task_input",
    "build_classroom_announcement_request",
    "build_error_response",
    "build_google_service",
    "build_post_only_client",
    "build_reminder_generation_response",
    "build_submission_analysis_response",
    "build_student_name_lookup",
    "default_classroom_post_scopes",
    "default_classroom_read_scopes",
    "create_google_document_from_output",
    "extract_output_payload",
    "fetch_submission_analysis",
    "load_google_user_credentials",
    "normalize_course",
    "normalize_coursework",
    "normalize_submission",
    "normalize_submission_batch",
    "render_google_document_html",
    "save_markdown_output",
    "validate_agent_output",
    "validate_agent_output_dict",
]
