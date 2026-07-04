from __future__ import annotations

from .models import AgentTaskType, ResponseStatus


SCHEMA_VERSION = "1.0.0"
ALLOWED_AGENT_TASK_TYPES = frozenset(member.value for member in AgentTaskType)
ALLOWED_STATUSES = frozenset(member.value for member in ResponseStatus)
COMMON_TOP_LEVEL_KEYS = frozenset(
    {
        "schemaVersion",
        "requestId",
        "generatedAt",
        "agentTaskType",
        "status",
        "course",
        "summary",
        "gui",
        "outputs",
        "approval",
        "errors",
    }
)
COMMON_GUI_KEYS = frozenset({"cards", "tables", "warnings", "editableFields"})
COMMON_OUTPUT_KEYS = frozenset(
    {"markdown", "pdf", "googleDocument", "classroomReminder"}
)
COMMON_APPROVAL_KEYS = frozenset({"required", "reason", "actions"})
