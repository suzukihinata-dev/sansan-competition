"""実出力レンダラ (REQUIREMENTS 8.7-8.9, 10.5-10.7)。

kimuの outputs.* 構造データを実ファイル/実ドキュメントへ変換する。
- markdown: content を .md へ保存
- pdf: sections(heading/body/table) を reportlab で実PDF化 (日本語CIDフォント)
- googleDocument: blocks を Docs API風リクエストへ変換 (MVPはモック)

reportlabは遅延importする。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .errors import AgentError, ErrorCode

# ---------------------------------------------------------------- Markdown


def render_markdown(payload: dict | None, out_dir: str | Path) -> dict:
    if not isinstance(payload, dict):
        raise AgentError(
            ErrorCode.INVALID_AGENT_OUTPUT, detail="markdown payload missing"
        )
    content = payload.get("content")
    if not content:
        raise AgentError(ErrorCode.INVALID_AGENT_OUTPUT, detail="markdown content empty")
    file_name = payload.get("fileName") or "output.md"
    out_path = Path(out_dir) / file_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return {
        "format": "markdown",
        "fileName": file_name,
        "path": str(out_path),
        "title": payload.get("title", ""),
        "bytes": out_path.stat().st_size,
    }


# --------------------------------------------------------------------- PDF

_FONT_NAME = "HeiseiKakuGo-W5"
_font_registered = False


def _ensure_font() -> None:
    global _font_registered
    if _font_registered:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont(_FONT_NAME))
    _font_registered = True


def render_pdf(payload: dict | None, out_dir: str | Path) -> dict:
    if not isinstance(payload, dict):
        raise AgentError(ErrorCode.PDF_EXPORT_FAILED, detail="pdf payload missing")
    file_name = payload.get("fileName") or "output.pdf"
    out_path = Path(out_dir) / file_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    title = payload.get("title", "")

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        _write_basic_pdf(out_path, _fallback_pdf_lines(payload), title=title or file_name)
        return {
            "format": "pdf",
            "fileName": file_name,
            "path": str(out_path),
            "title": title,
            "bytes": out_path.stat().st_size,
        }

    _ensure_font()

    base = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "JPTitle", parent=base["Title"], fontName=_FONT_NAME, fontSize=18
    )
    heading_style = ParagraphStyle(
        "JPHeading", parent=base["Heading2"], fontName=_FONT_NAME, fontSize=13
    )
    body_style = ParagraphStyle(
        "JPBody", parent=base["BodyText"], fontName=_FONT_NAME, fontSize=10.5, leading=16
    )

    story: list = []
    title = payload.get("title", "")
    if title:
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 6 * mm))

    for section in payload.get("sections", []):
        if not isinstance(section, dict):
            continue
        heading = section.get("heading")
        if heading:
            story.append(Paragraph(heading, heading_style))
            story.append(Spacer(1, 2 * mm))
        body = section.get("body")
        if body:
            story.append(Paragraph(str(body).replace("\n", "<br/>"), body_style))
            story.append(Spacer(1, 3 * mm))
        table = section.get("table")
        if isinstance(table, dict):
            story.append(
                _build_pdf_table(table, Paragraph, Table, TableStyle, colors, body_style)
            )
            story.append(Spacer(1, 4 * mm))

    try:
        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=A4,
            title=title or file_name,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )
        doc.build(story)
    except Exception as exc:
        raise AgentError(
            ErrorCode.PDF_EXPORT_FAILED, detail=f"pdf build failed: {exc}"
        ) from exc

    return {
        "format": "pdf",
        "fileName": file_name,
        "path": str(out_path),
        "title": title,
        "bytes": out_path.stat().st_size,
    }


def _build_pdf_table(table, Paragraph, Table, TableStyle, colors, cell_style):
    columns = table.get("columns", [])
    rows = table.get("rows", [])
    data = [[Paragraph(str(c), cell_style) for c in columns]]
    for row in rows:
        data.append([Paragraph(str(c), cell_style) for c in row])
    if len(data) == 1:
        # ヘッダのみ (該当行なし) の空表を避ける
        data.append([Paragraph("該当なし", cell_style) for _ in columns] or [Paragraph("該当なし", cell_style)])
    t = Table(data, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3367d6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f2f6fc")],
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _fallback_pdf_lines(payload: dict) -> list[str]:
    lines: list[str] = []
    title = payload.get("title")
    if title:
        lines.append(str(title))
    for section in payload.get("sections", []):
        if not isinstance(section, dict):
            continue
        heading = section.get("heading")
        if heading:
            lines.append(f"[{heading}]")
        body = section.get("body")
        if body:
            lines.extend(str(body).splitlines())
        table = section.get("table")
        if isinstance(table, dict):
            columns = table.get("columns", [])
            rows = table.get("rows", [])
            if columns:
                lines.append(" | ".join(str(column) for column in columns))
            for row in rows:
                if isinstance(row, list):
                    lines.append(" | ".join(str(cell) for cell in row))
    return lines or ["PDF export"]


def _write_basic_pdf(path: Path, lines: list[str], *, title: str) -> None:
    sanitized_lines = [_pdf_text(line) for line in lines if str(line).strip()]
    if not sanitized_lines:
        sanitized_lines = ["PDF export"]

    commands = ["BT", "/F1 10 Tf", "72 800 Td"]
    first = True
    for line in sanitized_lines[:60]:
        if not first:
            commands.append("T*")
        commands.append(f"({_pdf_escape(line)}) Tj")
        first = False
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Title ({_pdf_escape(_pdf_text(title or path.name))}) >>".encode("latin-1"),
    ]

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R /Info 6 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(bytes(pdf))


def _pdf_text(value: str) -> str:
    return str(value).encode("latin-1", "replace").decode("latin-1")


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


# --------------------------------------------------------- Google Document

_VALID_BLOCKS = {
    "heading1",
    "heading2",
    "heading3",
    "paragraph",
    "table",
    "bulletList",
}


@runtime_checkable
class GoogleDocsClient(Protocol):
    def create_document(self, title: str, blocks: list[dict]) -> dict: ...


class MockGoogleDocsClient:
    """Docs APIを叩かず、生成予定の構造とダミーURLを返すモック。"""

    def __init__(self) -> None:
        self._seq = 0

    def create_document(self, title: str, blocks: list[dict]) -> dict:
        self._seq += 1
        doc_id = f"mockdoc_{self._seq:03d}"
        requests = _blocks_to_requests(blocks)
        return {
            "documentId": doc_id,
            "title": title,
            "url": f"https://docs.google.com/document/d/{doc_id}/edit",
            "requestCount": len(requests),
            "requests": requests,
        }


def render_google_document(payload: dict | None, client: GoogleDocsClient) -> dict:
    if not isinstance(payload, dict):
        raise AgentError(
            ErrorCode.DOCUMENT_EXPORT_FAILED, detail="googleDocument payload missing"
        )
    title = payload.get("title")
    if not title:
        raise AgentError(ErrorCode.DOCUMENT_EXPORT_FAILED, detail="document title empty")
    blocks = payload.get("blocks", [])
    try:
        result = client.create_document(title, blocks)
    except AgentError:
        raise
    except Exception as exc:
        raise AgentError(
            ErrorCode.DOCUMENT_EXPORT_FAILED, detail=f"docs create failed: {exc}"
        ) from exc
    return {
        "format": "googleDocument",
        "title": title,
        "documentId": result.get("documentId"),
        "url": result.get("url"),
    }


def _blocks_to_requests(blocks: list[dict]) -> list[dict]:
    """blocksをGoogle Docs API batchUpdate風リクエストへ変換する。"""
    requests: list[dict] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype not in _VALID_BLOCKS:
            continue
        if btype == "table":
            columns = block.get("columns", [])
            rows = block.get("rows", [])
            requests.append(
                {
                    "insertTable": {
                        "rows": len(rows) + 1,
                        "columns": len(columns),
                        "header": columns,
                        "cells": rows,
                    }
                }
            )
        elif btype == "bulletList":
            for item in block.get("items", []):
                requests.append(
                    {
                        "insertText": {"text": str(item) + "\n"},
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        "bullet": {"listType": "BULLET_DISC_CIRCLE_SQUARE"},
                    }
                )
        else:
            style = "NORMAL_TEXT"
            if btype.startswith("heading"):
                style = f"HEADING_{btype[-1]}"
            requests.append(
                {
                    "insertText": {"text": block.get("text", "") + "\n"},
                    "paragraphStyle": {"namedStyleType": style},
                }
            )
    return requests
