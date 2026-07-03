from __future__ import annotations

from .models import AgentTaskType

ALLOWED_AGENT_TASK_TYPES = {member.value for member in AgentTaskType}
