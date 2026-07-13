from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
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
        allow_interactive: bool = True,
    ) -> GoogleClassroomClient:
        service = build_google_service(
            "classroom",
            "v1",
            scopes=scopes or default_classroom_read_scopes(),
            config=oauth_config,
            allow_interactive=allow_interactive,
        )
        return cls(service)

    def get_course(self, course_id: str) -> dict[str, Any]:
        return self._service.courses().get(id=course_id).execute()

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

    def list_topics(
        self,
        course_id: str,
        *,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        return self._collect_paginated(
            "topic",
            lambda page_token: self._service.courses()
            .topics()
            .list(courseId=course_id, pageSize=page_size, pageToken=page_token)
            .execute(),
        )

    def list_coursework_materials(
        self,
        course_id: str,
        *,
        page_size: int = 100,
        states: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return self._collect_paginated(
            "courseWorkMaterial",
            lambda page_token: self._service.courses()
            .courseWorkMaterials()
            .list(
                courseId=course_id,
                pageSize=page_size,
                pageToken=page_token,
                courseWorkMaterialStates=states,
            )
            .execute(),
        )

    def create_topic(self, course_id: str, name: str) -> dict[str, Any]:
        return (
            self._service.courses()
            .topics()
            .create(courseId=course_id, body={"name": name})
            .execute()
        )

    def create_coursework_material(
        self,
        course_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        return (
            self._service.courses()
            .courseWorkMaterials()
            .create(courseId=course_id, body=body)
            .execute()
        )

    def create_coursework(
        self,
        course_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        return (
            self._service.courses()
            .courseWork()
            .create(courseId=course_id, body=body)
            .execute()
        )

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


@dataclass(slots=True)
class ClassroomFetchFixture:
    course: dict[str, Any]
    course_work: dict[str, Any]
    students_pages: list[dict[str, Any]]
    student_submissions_pages: list[dict[str, Any]]

    @property
    def course_id(self) -> str:
        return _fixture_required_str(self.course, "id", "courseId")

    @property
    def course_work_id(self) -> str:
        return _fixture_required_str(self.course_work, "id", "courseWorkId")

    def build_client(self) -> GoogleClassroomClient:
        return GoogleClassroomClient(
            _FixtureClassroomService(
                course=self.course,
                course_work=self.course_work,
                students_pages=self.students_pages,
                student_submissions_pages=self.student_submissions_pages,
            )
        )


def load_classroom_fetch_fixture(path: str | Path) -> ClassroomFetchFixture:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Fixture payload must be a JSON object.")

    course = _fixture_required_dict(payload, "course")
    course_work = _fixture_required_dict(payload, "courseWork")
    students_pages = _fixture_required_page_list(payload, "studentsPages", item_key="students")
    student_submissions_pages = _fixture_required_page_list(
        payload,
        "studentSubmissionsPages",
        item_key="studentSubmissions",
    )
    return ClassroomFetchFixture(
        course=course,
        course_work=course_work,
        students_pages=students_pages,
        student_submissions_pages=student_submissions_pages,
    )


class _FixtureRequest:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def execute(self) -> dict[str, Any]:
        return dict(self._response)


class _FixtureStudentsResource:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self._page_lookup = _build_fixture_page_lookup(pages, item_key="students")

    def list(self, **kwargs: Any) -> _FixtureRequest:
        page_token = _normalize_fixture_page_token(kwargs.get("pageToken"))
        return _FixtureRequest(_fixture_page_response(self._page_lookup, page_token))


class _FixtureStudentSubmissionsResource:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self._page_lookup = _build_fixture_page_lookup(
            pages,
            item_key="studentSubmissions",
        )

    def list(self, **kwargs: Any) -> _FixtureRequest:
        page_token = _normalize_fixture_page_token(kwargs.get("pageToken"))
        return _FixtureRequest(_fixture_page_response(self._page_lookup, page_token))


class _FixtureCourseWorkResource:
    def __init__(
        self,
        *,
        course_work: dict[str, Any],
        student_submissions_pages: list[dict[str, Any]],
    ) -> None:
        self._course_work = course_work
        self._student_submissions_pages = student_submissions_pages

    def get(self, **kwargs: Any) -> _FixtureRequest:
        _assert_fixture_identifier(
            kwargs.get("courseId"),
            _fixture_required_str(self._course_work, "courseId"),
            field_name="courseId",
        )
        _assert_fixture_identifier(
            kwargs.get("id"),
            _fixture_required_str(self._course_work, "id", "courseWorkId"),
            field_name="courseWorkId",
        )
        return _FixtureRequest(self._course_work)

    def studentSubmissions(self) -> _FixtureStudentSubmissionsResource:
        return _FixtureStudentSubmissionsResource(self._student_submissions_pages)


class _FixtureCoursesResource:
    def __init__(
        self,
        *,
        course: dict[str, Any],
        course_work: dict[str, Any],
        students_pages: list[dict[str, Any]],
        student_submissions_pages: list[dict[str, Any]],
    ) -> None:
        self._course = course
        self._course_work = course_work
        self._students_pages = students_pages
        self._student_submissions_pages = student_submissions_pages

    def get(self, **kwargs: Any) -> _FixtureRequest:
        _assert_fixture_identifier(
            kwargs.get("id"),
            _fixture_required_str(self._course, "id", "courseId"),
            field_name="courseId",
        )
        return _FixtureRequest(self._course)

    def students(self) -> _FixtureStudentsResource:
        return _FixtureStudentsResource(self._students_pages)

    def courseWork(self) -> _FixtureCourseWorkResource:
        return _FixtureCourseWorkResource(
            course_work=self._course_work,
            student_submissions_pages=self._student_submissions_pages,
        )


class _FixtureClassroomService:
    def __init__(
        self,
        *,
        course: dict[str, Any],
        course_work: dict[str, Any],
        students_pages: list[dict[str, Any]],
        student_submissions_pages: list[dict[str, Any]],
    ) -> None:
        self._courses = _FixtureCoursesResource(
            course=course,
            course_work=course_work,
            students_pages=students_pages,
            student_submissions_pages=student_submissions_pages,
        )

    def courses(self) -> _FixtureCoursesResource:
        return self._courses


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
    allow_interactive: bool = True,
) -> GoogleClassroomClient:
    service = build_google_service(
        "classroom",
        "v1",
        scopes=default_classroom_post_scopes(),
        config=oauth_config,
        allow_interactive=allow_interactive,
    )
    return GoogleClassroomClient(service)


def _fixture_required_dict(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Fixture field {key} must be an object.")
    return value


def _fixture_required_page_list(
    raw: dict[str, Any],
    key: str,
    *,
    item_key: str,
) -> list[dict[str, Any]]:
    value = raw.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"Fixture field {key} must be a non-empty list.")

    pages: list[dict[str, Any]] = []
    for index, page in enumerate(value):
        if not isinstance(page, dict):
            raise ValueError(f"Fixture page {key}[{index}] must be an object.")
        items = page.get(item_key, [])
        if not isinstance(items, list):
            raise ValueError(f"Fixture page {key}[{index}].{item_key} must be a list.")
        next_page_token = page.get("nextPageToken")
        if next_page_token is not None and not isinstance(next_page_token, str):
            raise ValueError(
                f"Fixture page {key}[{index}].nextPageToken must be a string when present."
            )
        page_token = page.get("pageToken")
        if page_token is not None and not isinstance(page_token, str):
            raise ValueError(
                f"Fixture page {key}[{index}].pageToken must be a string when present."
            )
        pages.append(dict(page))
    return pages


def _fixture_required_str(raw: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    joined = ", ".join(keys)
    raise ValueError(f"Fixture is missing required string field: {joined}.")


def _build_fixture_page_lookup(
    pages: list[dict[str, Any]],
    *,
    item_key: str,
) -> dict[str | None, dict[str, Any]]:
    lookup: dict[str | None, dict[str, Any]] = {}
    for index, page in enumerate(pages):
        page_token = _normalize_fixture_page_token(page.get("pageToken"))
        if page_token in lookup:
            raise ValueError(f"Fixture page token is duplicated for {item_key}[{index}].")
        response = dict(page)
        response.pop("pageToken", None)
        lookup[page_token] = response

    if None not in lookup:
        raise ValueError(f"Fixture pages for {item_key} must include the first page.")

    for response in lookup.values():
        next_page_token = _normalize_fixture_page_token(response.get("nextPageToken"))
        if next_page_token is not None and next_page_token not in lookup:
            raise ValueError(
                f"Fixture nextPageToken {next_page_token} for {item_key} does not resolve."
            )
    return lookup


def _fixture_page_response(
    page_lookup: dict[str | None, dict[str, Any]],
    page_token: str | None,
) -> dict[str, Any]:
    response = page_lookup.get(page_token)
    if response is None:
        raise ValueError(f"Unknown fixture page token: {page_token}.")
    return response


def _normalize_fixture_page_token(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Fixture pageToken must be a string when present.")
    normalized = value.strip()
    return normalized or None


def _assert_fixture_identifier(value: Any, expected: str, *, field_name: str) -> None:
    if str(value or "").strip() != expected:
        raise ValueError(f"Fixture {field_name} mismatch: expected {expected}.")
