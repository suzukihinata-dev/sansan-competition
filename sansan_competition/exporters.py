from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from .oauth import DRIVE_FILE_SCOPE, GoogleOAuthConfig, build_google_service

GOOGLE_DOCUMENT_MIME_TYPE = "application/vnd.google-apps.document"


@dataclass(frozen=True, slots=True)
class MarkdownExportResult:
    path: Path

    def to_dict(self) -> dict[str, str]:
        return {"path": str(self.path)}


@dataclass(frozen=True, slots=True)
class GoogleDocumentExportResult:
    document_id: str
    title: str
    url: str
    shared_with: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "documentId": self.document_id,
            "title": self.title,
            "url": self.url,
            "sharedWith": list(self.shared_with),
        }


def extract_output_payload(payload: dict[str, Any], output_name: str) -> dict[str, Any]:
    outputs = payload.get("outputs")
    if isinstance(outputs, dict) and isinstance(outputs.get(output_name), dict):
        return outputs[output_name]
    if isinstance(payload, dict):
        return payload
    raise ValueError("Input payload must be an object.")


def save_markdown_output(
    markdown_output: dict[str, Any],
    *,
    output_dir: str | Path = ".",
) -> MarkdownExportResult:
    file_name = _required_string(markdown_output, "fileName")
    content = _required_string(markdown_output, "content")
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / Path(file_name).name
    target_path.write_text(content, encoding="utf-8")
    return MarkdownExportResult(path=target_path.resolve())


def create_google_document_from_output(
    document_output: dict[str, Any],
    *,
    oauth_config: GoogleOAuthConfig | None = None,
    share_emails: list[str] | None = None,
    share_role: str = "writer",
    drive_service: Any | None = None,
) -> GoogleDocumentExportResult:
    title = _required_string(document_output, "title")
    html = render_google_document_html(document_output).encode("utf-8")
    media_upload = _build_media_upload(html)

    service = drive_service or build_google_service(
        "drive",
        "v3",
        scopes=(DRIVE_FILE_SCOPE,),
        config=oauth_config,
    )
    created = (
        service.files()
        .create(
            body={
                "name": title,
                "mimeType": GOOGLE_DOCUMENT_MIME_TYPE,
            },
            media_body=media_upload,
            fields="id,name,webViewLink",
        )
        .execute()
    )

    document_id = _required_string(created, "id")
    url = str(created.get("webViewLink") or f"https://docs.google.com/document/d/{document_id}/edit")
    shared_with: list[str] = []
    for email in share_emails or []:
        normalized = email.strip()
        if not normalized:
            continue
        (
            service.permissions()
            .create(
                fileId=document_id,
                body={
                    "type": "user",
                    "role": share_role,
                    "emailAddress": normalized,
                },
                sendNotificationEmail=False,
                fields="id",
            )
            .execute()
        )
        shared_with.append(normalized)

    return GoogleDocumentExportResult(
        document_id=document_id,
        title=title,
        url=url,
        shared_with=shared_with,
    )


def render_google_document_html(document_output: dict[str, Any]) -> str:
    title = _required_string(document_output, "title")
    blocks = document_output.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("googleDocument.blocks must be a list.")

    rendered_blocks = [_render_google_block(block) for block in blocks]
    body = "\n".join(rendered_blocks)
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"ja\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        f"  <title>{escape(title)}</title>\n"
        "  <style>\n"
        "    body { font-family: sans-serif; line-height: 1.6; }\n"
        "    table { border-collapse: collapse; width: 100%; }\n"
        "    th, td { border: 1px solid #888; padding: 6px 8px; text-align: left; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def _render_google_block(block: Any) -> str:
    if not isinstance(block, dict):
        raise ValueError("Each googleDocument block must be an object.")

    block_type = _required_string(block, "type")
    if block_type == "heading1":
        return f"<h1>{escape(_required_string(block, 'text'))}</h1>"
    if block_type == "heading2":
        return f"<h2>{escape(_required_string(block, 'text'))}</h2>"
    if block_type == "paragraph":
        return f"<p>{_html_with_line_breaks(_required_string(block, 'text'))}</p>"
    if block_type == "bulletList":
        items = block.get("items")
        if not isinstance(items, list):
            raise ValueError("bulletList.items must be a list.")
        rendered_items = "".join(
            f"<li>{_html_with_line_breaks(str(item))}</li>"
            for item in items
            if str(item).strip()
        )
        return f"<ul>{rendered_items}</ul>"
    if block_type == "table":
        columns = block.get("columns")
        rows = block.get("rows")
        if not isinstance(columns, list):
            raise ValueError("table.columns must be a list.")
        if not isinstance(rows, list):
            raise ValueError("table.rows must be a list.")
        header_html = "".join(f"<th>{escape(str(column))}</th>" for column in columns)
        rows_html = "".join(_render_table_row(row) for row in rows)
        return f"<table><thead><tr>{header_html}</tr></thead><tbody>{rows_html}</tbody></table>"
    raise ValueError(f"Unsupported googleDocument block type: {block_type}")


def _render_table_row(row: Any) -> str:
    if not isinstance(row, list):
        raise ValueError("table.rows entries must be lists.")
    cells = "".join(f"<td>{_html_with_line_breaks(str(cell))}</td>" for cell in row)
    return f"<tr>{cells}</tr>"


def _html_with_line_breaks(text: str) -> str:
    return "<br />".join(escape(part) for part in text.splitlines()) or ""


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(f"{key} must be a non-empty string.")


def _build_media_upload(data: bytes) -> Any:
    try:
        from googleapiclient.http import MediaInMemoryUpload
    except ImportError:
        return _FallbackMediaUpload(data=data, mimetype="text/html")
    return MediaInMemoryUpload(data, mimetype="text/html", resumable=False)


@dataclass(frozen=True, slots=True)
class _FallbackMediaUpload:
    data: bytes
    mimetype: str
