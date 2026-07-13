"""Google Workspace source aggregation and teacher-approved publication."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .classroom import GoogleClassroomClient
from .lesson import (
    LessonBundle,
    LessonBundleValidationError,
    build_ai_lesson_payload,
    build_lesson_bundle,
    build_publication_plan,
)
from .oauth import (
    GoogleOAuthConfig,
    build_google_service,
    default_lesson_publish_scopes,
    default_lesson_read_scopes,
)


class GoogleCalendarClient:
    def __init__(self, service: Any) -> None:
        self._service = service

    @classmethod
    def from_oauth(
        cls,
        *,
        oauth_config: GoogleOAuthConfig | None = None,
        allow_interactive: bool = False,
        scopes: tuple[str, ...] | None = None,
    ) -> GoogleCalendarClient:
        return cls(
            build_google_service(
                "calendar",
                "v3",
                scopes=scopes or default_lesson_read_scopes(),
                config=oauth_config,
                allow_interactive=allow_interactive,
            )
        )

    def list_events(
        self,
        *,
        calendar_id: str = "primary",
        time_min: str | None = None,
        time_max: str | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        def fetch(page_token: str | None) -> dict[str, Any]:
            params: dict[str, Any] = {
                "calendarId": calendar_id,
                "singleEvents": True,
                "orderBy": "startTime",
                "pageToken": page_token,
            }
            if time_min:
                params["timeMin"] = time_min
            if time_max:
                params["timeMax"] = time_max
            if query:
                params["q"] = query
            return self._service.events().list(**params).execute()

        return _collect_pages(fetch, "items")

    def get_event(
        self,
        event_id: str,
        *,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        return (
            self._service.events()
            .get(calendarId=calendar_id, eventId=event_id)
            .execute()
        )


class GoogleDriveClient:
    def __init__(self, service: Any) -> None:
        self._service = service

    @classmethod
    def from_oauth(
        cls,
        *,
        oauth_config: GoogleOAuthConfig | None = None,
        allow_interactive: bool = False,
        scopes: tuple[str, ...] | None = None,
    ) -> GoogleDriveClient:
        return cls(
            build_google_service(
                "drive",
                "v3",
                scopes=scopes or default_lesson_read_scopes(),
                config=oauth_config,
                allow_interactive=allow_interactive,
            )
        )

    def list_files(
        self,
        *,
        query: str = "trashed = false",
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        def fetch(page_token: str | None) -> dict[str, Any]:
            return (
                self._service.files()
                .list(
                    q=query,
                    pageSize=page_size,
                    pageToken=page_token,
                    spaces="drive",
                    orderBy="modifiedTime desc",
                    fields=(
                        "nextPageToken,files(id,name,mimeType,webViewLink,"
                        "createdTime,modifiedTime,description,parents,size)"
                    ),
                )
                .execute()
            )

        return _collect_pages(fetch, "files")

    def read_text(self, file_id: str, *, mime_type: str = "") -> str:
        if mime_type == "application/vnd.google-apps.document":
            data = self._service.files().export(
                fileId=file_id,
                mimeType="text/plain",
            ).execute()
        else:
            data = self._service.files().get(fileId=file_id, alt="media").execute()
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data)


class GoogleWorkspaceLessonClient:
    """Build a lesson bundle from live Workspace APIs and publish it safely."""

    def __init__(
        self,
        calendar: GoogleCalendarClient,
        drive: GoogleDriveClient,
        classroom: GoogleClassroomClient,
    ) -> None:
        self.calendar = calendar
        self.drive = drive
        self.classroom = classroom

    @classmethod
    def from_oauth(
        cls,
        *,
        oauth_config: GoogleOAuthConfig | None = None,
        allow_interactive: bool = False,
        publish: bool = False,
    ) -> GoogleWorkspaceLessonClient:
        scopes = default_lesson_publish_scopes() if publish else default_lesson_read_scopes()
        return cls(
            GoogleCalendarClient.from_oauth(
                oauth_config=oauth_config,
                allow_interactive=allow_interactive,
                scopes=scopes,
            ),
            GoogleDriveClient.from_oauth(
                oauth_config=oauth_config,
                allow_interactive=allow_interactive,
                scopes=scopes,
            ),
            GoogleClassroomClient.from_oauth(
                scopes=scopes,
                oauth_config=oauth_config,
                allow_interactive=allow_interactive,
            ),
        )

    def assemble_bundle(
        self,
        *,
        course_id: str,
        calendar_event_id: str,
        calendar_id: str = "primary",
        drive_query: str = "trashed = false",
        include_transcripts: bool = False,
    ) -> tuple[LessonBundle, dict[str, Any]]:
        course = self.classroom.get_course(course_id)
        event = self.calendar.get_event(calendar_event_id, calendar_id=calendar_id)
        drive_files = self.drive.list_files(query=drive_query)
        coursework = self.classroom.list_coursework(
            course_id,
            course_work_states=["PUBLISHED"],
        )
        coursework_materials = self.classroom.list_coursework_materials(
            course_id,
            states=["PUBLISHED"],
        )
        bundle = build_lesson_bundle(
            course_id=course_id,
            course_name=str(course.get("name") or course_id),
            calendar_event=event,
            drive_files=drive_files,
            coursework=coursework,
            coursework_materials=coursework_materials,
        )
        transcript_texts: dict[str, str] = {}
        if include_transcripts:
            for source in bundle.drive_sources:
                if source.kind == "transcript":
                    transcript_texts[source.source_id] = self.drive.read_text(
                        source.source_id,
                        mime_type=source.mime_type,
                    )
        return bundle, build_ai_lesson_payload(bundle, transcript_texts=transcript_texts)

    def publish(
        self,
        *,
        bundle: LessonBundle,
        items: list[dict[str, Any]],
        approved: bool,
    ) -> dict[str, Any]:
        if not approved:
            raise LessonBundleValidationError(
                "教師承認がないためClassroomへの公開を実行しません。"
            )
        plan = build_publication_plan(bundle, items)
        topics = self.classroom.list_topics(bundle.course_id)
        topic = next(
            (item for item in topics if item.get("name") == bundle.topic_name),
            None,
        )
        if topic is None:
            topic = self.classroom.create_topic(bundle.course_id, bundle.topic_name)
        topic_id = str(topic.get("topicId") or topic.get("id") or "")
        if not topic_id:
            raise LessonBundleValidationError("Classroom Topic IDが返されませんでした。")

        existing_coursework = self.classroom.list_coursework(
            bundle.course_id,
            course_work_states=["PUBLISHED", "DRAFT"],
        )
        existing_materials = self.classroom.list_coursework_materials(
            bundle.course_id,
            states=["PUBLISHED", "DRAFT"],
        )
        source_map = {source.source_id: source for source in bundle.drive_sources}
        created: list[dict[str, Any]] = []
        for item in plan["items"]:
            existing = _find_existing_item(
                item,
                topic_id=topic_id,
                coursework=existing_coursework,
                materials=existing_materials,
            )
            if existing is not None:
                created.append(
                    {
                        "kind": item["kind"],
                        "status": "already_present",
                        "id": existing.get("id"),
                        "title": existing.get("title"),
                    }
                )
                continue
            body = _build_classroom_item_body(item, topic_id=topic_id, source_map=source_map)
            if item["kind"] == "assignment":
                response = self.classroom.create_coursework(bundle.course_id, body)
            else:
                response = self.classroom.create_coursework_material(bundle.course_id, body)
            created.append(
                {
                    "kind": item["kind"],
                    "status": "created",
                    "id": response.get("id"),
                    "title": response.get("title") or item["title"],
                    "alternateLink": response.get("alternateLink"),
                }
            )
        return {
            "lessonId": bundle.lesson_id,
            "courseId": bundle.course_id,
            "topicId": topic_id,
            "topicName": bundle.topic_name,
            "items": created,
            "status": "success",
        }


def _build_classroom_item_body(
    item: dict[str, Any],
    *,
    topic_id: str,
    source_map: dict[str, Any],
) -> dict[str, Any]:
    materials = []
    for source_id in item["sourceIds"]:
        source = source_map[source_id]
        materials.append(
            {
                "driveFile": {
                    "driveFile": {
                        "id": source.source_id,
                        "title": source.title,
                    },
                    "shareMode": "VIEW",
                }
            }
        )
    body: dict[str, Any] = {
        "title": item["title"],
        "description": item["description"],
        "materials": materials,
        "topicId": topic_id,
        "state": "PUBLISHED",
    }
    if item["kind"] == "assignment":
        body["workType"] = "ASSIGNMENT"
        due_date = _classroom_due_date(item.get("dueDate"))
        due_time = _classroom_due_time(item.get("dueTime"))
        if due_date:
            body["dueDate"] = due_date
        if due_time:
            body["dueTime"] = due_time
    return body


def _find_existing_item(
    item: dict[str, Any],
    *,
    topic_id: str,
    coursework: list[dict[str, Any]],
    materials: list[dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = coursework if item["kind"] == "assignment" else materials
    return next(
        (
            candidate
            for candidate in candidates
            if candidate.get("title") == item["title"]
            and str(candidate.get("topicId") or "") == topic_id
        ),
        None,
    )


def _classroom_due_date(value: str | None) -> dict[str, int] | None:
    if not value:
        return None
    try:
        date = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    return {"year": date.year, "month": date.month, "day": date.day}


def _classroom_due_time(value: str | None) -> dict[str, int] | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError:
        return None
    return {"hours": parsed.hour, "minutes": parsed.minute, "seconds": 0, "nanos": 0}


def _collect_pages(fetch: Any, item_key: str) -> list[dict[str, Any]]:
    page_token: str | None = None
    items: list[dict[str, Any]] = []
    while True:
        response = fetch(page_token)
        page_items = response.get(item_key, [])
        if isinstance(page_items, list):
            items.extend(item for item in page_items if isinstance(item, dict))
        page_token = response.get("nextPageToken")
        if not page_token:
            return items
