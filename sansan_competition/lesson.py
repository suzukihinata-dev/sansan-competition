"""Calendar・Drive・Classroomを授業単位へ束ねるデータ契約。

外部APIのレスポンスをそのままAIへ渡さず、出典と公開状態を保持した
LessonBundleへ変換する。文字起こしエンジンは別実装から差し替えられる。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from typing import Any, Mapping


LESSON_BUNDLE_SCHEMA_VERSION = "1.0.0"
_WHITESPACE_RE = re.compile(r"\s+")
_RECORDING_RE = re.compile(r"録画|recording|lecture|講義|meeting", re.IGNORECASE)
_TRANSCRIPT_RE = re.compile(
    r"文字起こし|transcript|transcription|caption|字幕", re.IGNORECASE
)


class LessonBundleValidationError(ValueError):
    """Raised when a lesson cannot be safely linked."""


@dataclass(frozen=True, slots=True)
class LessonSource:
    source_id: str
    title: str
    kind: str
    mime_type: str = ""
    url: str = ""
    modified_time: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "sourceId": self.source_id,
            "title": self.title,
            "kind": self.kind,
            "mimeType": self.mime_type,
            "url": self.url,
            "modifiedTime": self.modified_time,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class LessonBundle:
    lesson_id: str
    course_id: str
    course_name: str
    calendar_event: dict[str, Any]
    drive_sources: tuple[LessonSource, ...] = ()
    classroom_items: tuple[dict[str, Any], ...] = ()
    topic_name: str = ""
    transcript_segments: tuple[dict[str, Any], ...] = ()
    publication_status: str = "draft"
    errors: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": LESSON_BUNDLE_SCHEMA_VERSION,
            "lessonId": self.lesson_id,
            "course": {
                "courseId": self.course_id,
                "name": self.course_name,
            },
            "calendarEvent": self.calendar_event,
            "driveSources": [source.to_dict() for source in self.drive_sources],
            "classroomItems": list(self.classroom_items),
            "topic": {"name": self.topic_name},
            "transcript": {
                "segmentCount": len(self.transcript_segments),
                "segments": list(self.transcript_segments),
            },
            "publication": {
                "status": self.publication_status,
                "requiresTeacherApproval": True,
            },
            "errors": list(self.errors),
        }


def normalize_calendar_event(raw_event: Mapping[str, Any]) -> dict[str, Any]:
    event_id = _required_text(raw_event, "id", "calendarEventId")
    summary = _clean_text(raw_event.get("summary")) or "無題の授業"
    start = _normalize_event_time(raw_event.get("start"))
    end = _normalize_event_time(raw_event.get("end"))
    return {
        "calendarEventId": event_id,
        "summary": summary,
        "description": _clean_text(raw_event.get("description")),
        "start": start,
        "end": end,
        "location": _clean_text(raw_event.get("location")),
        "htmlLink": _clean_text(raw_event.get("htmlLink")),
        "status": _clean_text(raw_event.get("status")) or "confirmed",
    }


def normalize_drive_sources(raw_files: list[Mapping[str, Any]]) -> list[LessonSource]:
    sources: list[LessonSource] = []
    for raw_file in raw_files:
        source_id = _clean_text(raw_file.get("id"))
        if not source_id:
            continue
        title = _clean_text(raw_file.get("name")) or source_id
        mime_type = _clean_text(raw_file.get("mimeType"))
        kind = classify_drive_source(title, mime_type)
        sources.append(
            LessonSource(
                source_id=source_id,
                title=title,
                kind=kind,
                mime_type=mime_type,
                url=_clean_text(raw_file.get("webViewLink"))
                or _clean_text(raw_file.get("url")),
                modified_time=_clean_text(raw_file.get("modifiedTime")),
                description=_clean_text(raw_file.get("description")),
            )
        )
    return sources


def classify_drive_source(title: str, mime_type: str = "") -> str:
    """Classify a source without sending its contents to an AI model."""
    if _RECORDING_RE.search(title) or mime_type.startswith(("video/", "audio/")):
        return "recording"
    if _TRANSCRIPT_RE.search(title) or mime_type in {
        "text/plain",
        "text/csv",
        "application/vnd.google-apps.document",
    }:
        return "transcript"
    return "supplement"


def normalize_classroom_items(
    coursework: list[Mapping[str, Any]],
    coursework_materials: list[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in coursework:
        normalized = _normalize_classroom_item(item, item_type="assignment")
        if normalized:
            items.append(normalized)
    for item in coursework_materials:
        normalized = _normalize_classroom_item(item, item_type="material")
        if normalized:
            items.append(normalized)
    return items


def build_lesson_bundle(
    *,
    course_id: str,
    course_name: str,
    calendar_event: Mapping[str, Any],
    drive_files: list[Mapping[str, Any]] = (),
    coursework: list[Mapping[str, Any]] = (),
    coursework_materials: list[Mapping[str, Any]] = (),
    transcript_segments: list[Mapping[str, Any]] = (),
) -> LessonBundle:
    course_id = _clean_text(course_id)
    course_name = _clean_text(course_name) or course_id
    if not course_id:
        raise LessonBundleValidationError("course_id is required")

    event = normalize_calendar_event(calendar_event)
    event_id = event["calendarEventId"]
    lesson_id = _stable_lesson_id(course_id, event_id)
    sources = tuple(normalize_drive_sources(drive_files))
    items = tuple(normalize_classroom_items(coursework, coursework_materials))
    segments = tuple(_normalize_transcript_segment(item, sources) for item in transcript_segments)
    errors: list[dict[str, Any]] = []
    if not sources:
        errors.append(
            {
                "code": "LESSON_SOURCES_NOT_FOUND",
                "message": "授業に紐付くDrive資料がまだありません。",
                "recoverable": True,
            }
        )
    if not event.get("start"):
        errors.append(
            {
                "code": "CALENDAR_EVENT_TIME_MISSING",
                "message": "Calendar予定の開始時刻がないため、授業日時を確定できません。",
                "recoverable": True,
            }
        )
    return LessonBundle(
        lesson_id=lesson_id,
        course_id=course_id,
        course_name=course_name,
        calendar_event=event,
        drive_sources=sources,
        classroom_items=items,
        topic_name=build_topic_name(event),
        transcript_segments=segments,
        publication_status="ready" if not errors else "partial",
        errors=tuple(errors),
    )


def build_topic_name(calendar_event: Mapping[str, Any]) -> str:
    summary = _clean_text(calendar_event.get("summary")) or "授業"
    start = calendar_event.get("start")
    date_label = ""
    if isinstance(start, Mapping):
        value = _clean_text(start.get("dateTime")) or _clean_text(start.get("date"))
        date_label = value[:10] if value else ""
    return _limit_text(f"{date_label} {summary}".strip(), 90)


def build_ai_lesson_payload(
    bundle: LessonBundle,
    *,
    transcript_texts: Mapping[str, str] | None = None,
    max_chunk_chars: int = 1200,
) -> dict[str, Any]:
    """Create citation-preserving, student-safe input for a future AI layer."""
    if max_chunk_chars < 200:
        raise ValueError("max_chunk_chars must be at least 200")
    transcript_texts = transcript_texts or {}
    chunks: list[dict[str, Any]] = []
    for source in bundle.drive_sources:
        text = _clean_text(transcript_texts.get(source.source_id))
        if not text:
            continue
        for index, chunk in enumerate(_chunk_text(text, max_chunk_chars)):
            chunks.append(
                {
                    "chunkId": f"{source.source_id}:{index}",
                    "sourceId": source.source_id,
                    "sourceTitle": source.title,
                    "sourceKind": source.kind,
                    "sourceUrl": source.url,
                    "startSeconds": None,
                    "endSeconds": None,
                    "text": chunk,
                }
            )
    for segment in bundle.transcript_segments:
        text = _clean_text(segment.get("text"))
        if not text:
            continue
        chunks.append(
            {
                "chunkId": str(segment["segmentId"]),
                "sourceId": str(segment["sourceId"]),
                "sourceTitle": str(segment.get("sourceTitle") or ""),
                "sourceKind": "transcript",
                "sourceUrl": str(segment.get("sourceUrl") or ""),
                "startSeconds": segment.get("startSeconds"),
                "endSeconds": segment.get("endSeconds"),
                "text": text,
            }
        )
    return {
        "schemaVersion": LESSON_BUNDLE_SCHEMA_VERSION,
        "lessonId": bundle.lesson_id,
        "courseId": bundle.course_id,
        "courseName": bundle.course_name,
        "calendarEvent": bundle.calendar_event,
        "topicName": bundle.topic_name,
        "sources": [source.to_dict() for source in bundle.drive_sources],
        "classroomItems": list(bundle.classroom_items),
        "chunks": chunks,
        "privacy": {
            "studentIdentifiersIncluded": False,
            "visibility": "teacher_approved",
            "answerMustCiteSource": True,
        },
    }


def build_publication_plan(
    bundle: LessonBundle,
    items: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate a teacher-editable plan before Classroom write operations."""
    if not items:
        raise LessonBundleValidationError("publication items must not be empty")
    known_source_ids = {source.source_id for source in bundle.drive_sources}
    normalized_items: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        kind = _clean_text(item.get("kind"))
        if kind not in {"assignment", "material"}:
            raise LessonBundleValidationError(
                f"publication item {index} kind must be assignment or material"
            )
        title = _required_text(item, "title", f"publicationItems[{index}].title")
        source_ids = item.get("sourceIds", [])
        if not isinstance(source_ids, list):
            raise LessonBundleValidationError(
                f"publication item {index} sourceIds must be a list"
            )
        unknown_ids = [str(source_id) for source_id in source_ids if str(source_id) not in known_source_ids]
        if unknown_ids:
            raise LessonBundleValidationError(
                f"publication item {index} references unknown sources: {', '.join(unknown_ids)}"
            )
        normalized_items.append(
            {
                "kind": kind,
                "title": title,
                "description": _clean_text(item.get("description")),
                "sourceIds": [str(source_id) for source_id in source_ids],
                "dueDate": _clean_text(item.get("dueDate")),
                "dueTime": _clean_text(item.get("dueTime")),
            }
        )
    return {
        "lessonId": bundle.lesson_id,
        "courseId": bundle.course_id,
        "topicName": bundle.topic_name,
        "items": normalized_items,
        "requiresTeacherApproval": True,
    }


def _normalize_event_time(value: Any) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    result: dict[str, str] = {}
    for key in ("dateTime", "date", "timeZone"):
        text = _clean_text(value.get(key))
        if text:
            result[key] = text
    return result or None


def _normalize_classroom_item(
    item: Mapping[str, Any],
    *,
    item_type: str,
) -> dict[str, Any] | None:
    item_id = _clean_text(item.get("id"))
    title = _clean_text(item.get("title"))
    if not item_id or not title:
        return None
    return {
        "itemType": item_type,
        "itemId": item_id,
        "title": title,
        "description": _clean_text(item.get("description")),
        "topicId": _clean_text(item.get("topicId")),
        "state": _clean_text(item.get("state")) or "PUBLISHED",
        "alternateLink": _clean_text(item.get("alternateLink")),
        "materials": item.get("materials") if isinstance(item.get("materials"), list) else [],
    }


def _normalize_transcript_segment(
    segment: Mapping[str, Any],
    sources: tuple[LessonSource, ...],
) -> dict[str, Any]:
    source_id = _clean_text(segment.get("sourceId"))
    source = next((item for item in sources if item.source_id == source_id), None)
    if source is None:
        raise LessonBundleValidationError(
            f"transcript segment references unknown source: {source_id}"
        )
    text = _clean_text(segment.get("text"))
    if not text:
        raise LessonBundleValidationError("transcript segment text is required")
    return {
        "segmentId": _clean_text(segment.get("segmentId")) or f"{source_id}:segment",
        "sourceId": source_id,
        "sourceTitle": source.title,
        "sourceUrl": source.url,
        "startSeconds": _number_or_none(segment.get("startSeconds")),
        "endSeconds": _number_or_none(segment.get("endSeconds")),
        "text": text,
    }


def _chunk_text(text: str, max_chars: int) -> list[str]:
    return [text[index : index + max_chars] for index in range(0, len(text), max_chars)]


def _stable_lesson_id(course_id: str, event_id: str) -> str:
    digest = hashlib.sha256(f"{course_id}:{event_id}".encode("utf-8")).hexdigest()
    return f"lesson_{digest[:20]}"


def _required_text(payload: Mapping[str, Any], key: str, label: str | None = None) -> str:
    value = _clean_text(payload.get(key))
    if not value:
        raise LessonBundleValidationError(f"{label or key} is required")
    return value


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return _WHITESPACE_RE.sub(" ", str(value)).strip()


def _limit_text(value: str, max_length: int) -> str:
    return value if len(value) <= max_length else f"{value[: max_length - 3]}..."


def _number_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None
