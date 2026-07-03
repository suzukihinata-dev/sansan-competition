from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .analysis import analyze_submissions
from .models import SubmissionAnalysis
from .normalization import (
    normalize_course,
    normalize_coursework,
    normalize_submission_batch,
)
from .oauth import (
    GoogleOAuthConfig,
    build_google_service,
    default_classroom_post_scopes,
    default_classroom_read_scopes,
)


@dataclass(slots=True)
class ClassroomAnnouncementRequest:
    course_id: str
    body: dict[str, Any]


class GoogleClassroomClient:
    def __init__(self, service: Any) -> None:
        self._service = service

    @classmethod
    def from_oauth(
        cls,
        *,
        scopes: tuple[str, ...] | None = None,
        oauth_config: GoogleOAuthConfig | None = None,
    ) -> GoogleClassroomClient:
        service = build_google_service(
            "classroom",
            "v1",
            scopes=scopes or default_classroom_read_scopes(),
            config=oauth_config,
        )
        return cls(service)

    def get_course(self, course_id: str) -> dict[str, Any]:
        return self._service.courses().get(courseId=course_id).execute()

    def list_courses(
        self,
        *,
        page_size: int = 100,
        teacher_id: str = "me",
        course_states: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return self._collect_paginated(
            "courses",
            lambda page_token: self._service.courses()
            .list(
                teacherId=teacher_id,
                pageSize=page_size,
                pageToken=page_token,
                courseStates=course_states,
            )
            .execute(),
        )

    def get_coursework(self, course_id: str, course_work_id: str) -> dict[str, Any]:
        return (
            self._service.courses()
            .courseWork()
            .get(courseId=course_id, id=course_work_id)
            .execute()
        )

    def list_coursework(
        self,
        course_id: str,
        *,
        page_size: int = 100,
        course_work_states: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return self._collect_paginated(
            "courseWork",
            lambda page_token: self._service.courses()
            .courseWork()
            .list(
                courseId=course_id,
                pageSize=page_size,
                pageToken=page_token,
                courseWorkStates=course_work_states,
            )
            .execute(),
        )

    def list_students(
        self,
        course_id: str,
        *,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        return self._collect_paginated(
            "students",
            lambda page_token: self._service.courses()
            .students()
            .list(courseId=course_id, pageSize=page_size, pageToken=page_token)
            .execute(),
        )

    def list_student_submissions(
        self,
        course_id: str,
        course_work_id: str,
        *,
        page_size: int = 100,
        user_id: str | None = None,
        states: list[str] | None = None,
        late: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._collect_paginated(
            "studentSubmissions",
            lambda page_token: self._service.courses()
            .courseWork()
            .studentSubmissions()
            .list(
                courseId=course_id,
                courseWorkId=course_work_id,
                pageSize=page_size,
                pageToken=page_token,
                userId=user_id,
                states=states,
                late=late,
            )
            .execute(),
        )

    def create_announcement(self, request: ClassroomAnnouncementRequest) -> dict[str, Any]:
        return (
            self._service.courses()
            .announcements()
            .create(courseId=request.course_id, body=request.body)
            .execute()
        )

    def create_announcement_from_output(self, reminder_output: dict[str, Any]) -> dict[str, Any]:
        request = build_classroom_announcement_request(reminder_output)
        return self.create_announcement(request)

    @staticmethod
    def _collect_paginated(
        item_key: str,
        fetch_page: Any,
    ) -> list[dict[str, Any]]:
        page_token: str | None = None
        items: list[dict[str, Any]] = []
        while True:
            response = fetch_page(page_token)
            page_items = response.get(item_key, [])
            if isinstance(page_items, list):
                items.extend(item for item in page_items if isinstance(item, dict))
            page_token = response.get("nextPageToken")
            if not page_token:
                return items


def build_student_name_lookup(raw_students: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for student in raw_students:
        user_id = str(student.get("userId") or "").strip()
        profile = student.get("profile")
        profile_name = ""
        if isinstance(profile, dict):
            name = profile.get("name")
            if isinstance(name, dict):
                profile_name = str(name.get("fullName") or "").strip()
        if user_id:
            lookup[user_id] = profile_name
    return lookup


def build_classroom_announcement_request(
    reminder_output: dict[str, Any],
) -> ClassroomAnnouncementRequest:
    target = reminder_output.get("target")
    if not isinstance(target, dict):
        raise ValueError("classroomReminder.target must be an object.")

    course_id = str(target.get("courseId") or "").strip()
    if not course_id:
        raise ValueError("classroomReminder.target.courseId is required.")

    title = str(reminder_output.get("title") or "").strip()
    text = str(reminder_output.get("text") or "").strip()
    composed_text = _compose_announcement_text(title=title, text=text)
    if not composed_text:
        raise ValueError("Announcement title or text is required.")

    raw_materials = reminder_output.get("materials", [])
    materials = [item for item in raw_materials if isinstance(item, dict)]

    target_student_ids = [
        str(item).strip()
        for item in reminder_output.get("targetStudentIds", [])
        if str(item).strip()
    ]
    assignee_mode = str(reminder_output.get("assigneeMode") or "").strip() or (
        "INDIVIDUAL_STUDENTS" if target_student_ids else "ALL_STUDENTS"
    )

    body: dict[str, Any] = {
        "text": composed_text,
        "materials": materials,
        "assigneeMode": assignee_mode,
        "state": "PUBLISHED",
    }

    scheduled_time = reminder_output.get("scheduledTime")
    if isinstance(scheduled_time, str) and scheduled_time.strip():
        body["scheduledTime"] = scheduled_time.strip()

    if assignee_mode == "INDIVIDUAL_STUDENTS":
        if not target_student_ids:
            raise ValueError(
                "targetStudentIds is required when assigneeMode is INDIVIDUAL_STUDENTS."
            )
        body["individualStudentsOptions"] = {
            "studentIds": target_student_ids,
        }

    return ClassroomAnnouncementRequest(course_id=course_id, body=body)


def _compose_announcement_text(*, title: str, text: str) -> str:
    if title and text:
        return f"{title}\n\n{text}"
    return title or text


def fetch_submission_analysis(
    client: GoogleClassroomClient,
    *,
    course_id: str,
    course_work_id: str,
    now: datetime | None = None,
) -> SubmissionAnalysis:
    raw_course = client.get_course(course_id)
    raw_course_work = client.get_coursework(course_id, course_work_id)
    raw_students = client.list_students(course_id)
    raw_submissions = client.list_student_submissions(course_id, course_work_id)

    student_name_lookup = build_student_name_lookup(raw_students)
    course = normalize_course(raw_course)
    course_work = normalize_coursework(raw_course_work)
    submissions, issues = normalize_submission_batch(
        raw_submissions,
        student_names_by_id=student_name_lookup,
    )
    return analyze_submissions(
        course,
        course_work,
        submissions,
        now=now,
        normalization_issues=issues,
    )


def build_post_only_client(
    *,
    oauth_config: GoogleOAuthConfig | None = None,
) -> GoogleClassroomClient:
    service = build_google_service(
        "classroom",
        "v1",
        scopes=default_classroom_post_scopes(),
        config=oauth_config,
    )
    return GoogleClassroomClient(service)
