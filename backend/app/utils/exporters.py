"""Convert ProseMirror JSON documents to DOCX and PDF byte streams.

Both exporters walk the same node tree as ``app.utils.content`` and reuse its
safety rules: links are filtered through ``safe_link_url`` and heading levels
through ``_heading_level``. Unknown node types degrade to their rendered text
rather than failing the export. ``data:`` image URIs are embedded when the
payload decodes; remote ``http(s)`` image URLs are never fetched — they render
as a captioned link instead.
"""
import base64
import io
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import unquote_to_bytes
from xml.sax.saxutils import escape as xml_escape
from xml.sax.saxutils import quoteattr

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    XPreformatted,
)

from app.utils.content import _heading_level, _prosemirror_children, safe_link_url

_LINK_COLOR = "0563C1"
_HEX_COLOR = re.compile(r"^#?[0-9a-fA-F]{3,8}$")
_LIST_TYPES = ("bulletList", "orderedList", "taskList")


def _hex_or_none(value: Any) -> str | None:
    if isinstance(value, str) and _HEX_COLOR.match(value.strip()):
        return value.strip().lstrip("#")
    return None


def _data_uri_bytes(src: Any) -> bytes | None:
    """Decode a ``data:`` URI payload, returning None for anything else."""
    if not isinstance(src, str) or not src.startswith("data:"):
        return None
    try:
        header, _, payload = src.partition(",")
        if ";base64" in header:
            return base64.b64decode(payload)
        return unquote_to_bytes(payload)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# DOCX (python-docx)
# ---------------------------------------------------------------------------

_DOCX_ALIGN = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def _docx_shade(run_or_para_pr, hex_fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hex_fill)
    run_or_para_pr.append(shd)


def _docx_apply_marks(run: Any, marks: Sequence[dict[str, Any]]) -> None:
    for mark in marks:
        mark_type = mark.get("type")
        attrs = mark.get("attrs", {})
        if mark_type == "bold":
            run.bold = True
        elif mark_type == "italic":
            run.italic = True
        elif mark_type == "underline":
            run.underline = True
        elif mark_type == "strike":
            run.font.strike = True
        elif mark_type == "code":
            run.font.name = "Courier New"
        elif mark_type == "subscript":
            run.font.subscript = True
        elif mark_type == "superscript":
            run.font.superscript = True
        elif mark_type == "textStyle":
            color = _hex_or_none(attrs.get("color"))
            if color:
                run.font.color.rgb = RGBColor.from_string(color)
        elif mark_type == "highlight":
            color = _hex_or_none(attrs.get("color"))
            if color:
                _docx_shade(run._r.get_or_add_rPr(), color)


def _docx_add_hyperlink(paragraph: Any, url: str, text: str, marks: Sequence[dict[str, Any]]) -> None:
    """Append a clickable external hyperlink; python-docx has no public API for it."""
    run = paragraph.add_run(text)
    _docx_apply_marks(run, [m for m in marks if m.get("type") != "link"])
    run.font.color.rgb = RGBColor.from_string(_LINK_COLOR)
    run.underline = True
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True))
    hyperlink.append(run._r)
    paragraph._p.append(hyperlink)


def _docx_inline(paragraph: Any, nodes: Sequence[dict[str, Any]]) -> None:
    for node in nodes:
        node_type = node.get("type")
        if node_type == "hardBreak":
            paragraph.add_run().add_break()
            continue
        if node_type != "text":
            alt = node.get("attrs", {}).get("alt")
            if alt:
                paragraph.add_run(str(alt))
            continue
        marks = node.get("marks", [])
        link = next((m for m in marks if m.get("type") == "link"), None)
        href = safe_link_url(link.get("attrs", {}).get("href", "")) if link else None
        if href:
            _docx_add_hyperlink(paragraph, href, node.get("text", ""), marks)
        else:
            run = paragraph.add_run(node.get("text", ""))
            _docx_apply_marks(run, marks)


def _docx_styled_paragraph(doc: Any, style: str | None) -> Any:
    try:
        return doc.add_paragraph(style=style)
    except KeyError:
        # "List Bullet 3" etc. may be absent in some templates — fall back to
        # the base style by dropping a trailing depth number.
        return doc.add_paragraph(style=re.sub(r" \d+$", "", style) if style else None)


def _docx_block_attrs(paragraph: Any, node: dict[str, Any]) -> None:
    attrs = node.get("attrs", {})
    align = _DOCX_ALIGN.get(attrs.get("textAlign"))
    if align is not None:
        paragraph.alignment = align
    indent = attrs.get("indent")
    if isinstance(indent, int) and 0 < indent <= 8:
        paragraph.paragraph_format.left_indent = Pt(indent * 18)


def _docx_add_list_item(doc: Any, item: dict[str, Any], style: str | None, prefix: str, depth: int) -> None:
    for child in item.get("content", []):
        if child.get("type") in _LIST_TYPES:
            _docx_add_list(doc, child, depth + 1)
            continue
        paragraph = _docx_styled_paragraph(doc, style)
        if prefix:
            paragraph.add_run(prefix)
        if child.get("type") in ("paragraph", "heading"):
            _docx_block_attrs(paragraph, child)
        _docx_inline(paragraph, child.get("content", []))


def _docx_add_list(doc: Any, node: dict[str, Any], depth: int) -> None:
    kind = node.get("type")
    if kind == "taskList":
        base = "List Paragraph"
    else:
        base = "List Bullet" if kind == "bulletList" else "List Number"
    style = base if depth == 0 else f"{base} {min(depth + 1, 3)}"
    for item in node.get("content", []):
        prefix = ""
        if kind == "taskList":
            prefix = "☑ " if item.get("attrs", {}).get("checked") else "☐ "
        _docx_add_list_item(doc, item, style, prefix, depth)


def _docx_add_table(doc: Any, node: dict[str, Any]) -> None:
    rows = node.get("content", [])
    col_count = max((len(row.get("content", [])) for row in rows), default=0)
    if not rows or not col_count:
        return
    table = doc.add_table(rows=len(rows), cols=col_count)
    table.style = "Table Grid"
    for row_index, row in enumerate(rows):
        for col_index, cell in enumerate(row.get("content", [])[:col_count]):
            cell_obj = table.cell(row_index, col_index)
            paragraph = cell_obj.paragraphs[0]
            added_extra = False
            for child in cell.get("content", []):
                if child.get("type") == "paragraph":
                    _docx_inline(paragraph, child.get("content", []))
                    paragraph = cell_obj.add_paragraph()
                    added_extra = True
            # Drop the trailing empty paragraph left by the last add_paragraph().
            if added_extra:
                last = cell_obj.paragraphs[-1]
                last._p.getparent().remove(last._p)
            if cell.get("type") == "tableHeader":
                for cell_paragraph in cell_obj.paragraphs:
                    for run in cell_paragraph.runs:
                        run.bold = True


def _docx_add_horizontal_rule(doc: Any) -> None:
    paragraph = doc.add_paragraph()
    p_pr = paragraph._p.get_or_add_pPr()
    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:color"), "c3cada")
    border.append(bottom)
    p_pr.append(border)


def _docx_add_image(doc: Any, node: dict[str, Any]) -> None:
    attrs = node.get("attrs", {})
    data = _data_uri_bytes(attrs.get("src"))
    if data:
        try:
            from PIL import Image as PILImage

            stream = io.BytesIO(data)
            width = None
            try:
                with PILImage.open(io.BytesIO(data)) as probe:
                    if probe.width > 576:
                        width = Inches(6)
            except Exception:
                pass
            doc.add_picture(stream, width=width)
            return
        except Exception:
            pass
    paragraph = doc.add_paragraph()
    paragraph.add_run("[Image] ")
    href = safe_link_url(attrs.get("src"))
    label = attrs.get("alt") or attrs.get("src") or ""
    if href:
        _docx_add_hyperlink(paragraph, href, str(label) or href, [])
    elif label:
        paragraph.add_run(str(label))


def _docx_add_code_block(doc: Any, node: dict[str, Any]) -> None:
    text = "".join(child.get("text", "") for child in node.get("content", []))
    paragraph = _docx_styled_paragraph(doc, "No Spacing")
    paragraph.paragraph_format.space_after = Pt(6)
    _docx_shade(paragraph._p.get_or_add_pPr(), "f1f3f6")
    for index, line in enumerate(text.split("\n")):
        if index:
            paragraph.add_run().add_break()
        run = paragraph.add_run(line)
        run.font.name = "Courier New"
        run.font.size = Pt(9.5)


def _docx_add_blocks(doc: Any, nodes: Sequence[dict[str, Any]], quote: bool = False) -> None:
    for node in nodes:
        node_type = node.get("type")
        children = node.get("content", [])
        if node_type == "paragraph":
            paragraph = _docx_styled_paragraph(doc, "Intense Quote" if quote else None)
            _docx_block_attrs(paragraph, node)
            _docx_inline(paragraph, children)
        elif node_type == "heading":
            paragraph = _docx_styled_paragraph(doc, f"Heading {_heading_level(node)}")
            _docx_block_attrs(paragraph, node)
            _docx_inline(paragraph, children)
        elif node_type == "blockquote":
            _docx_add_blocks(doc, children, quote=True)
        elif node_type in _LIST_TYPES:
            _docx_add_list(doc, node, 0)
        elif node_type == "codeBlock":
            _docx_add_code_block(doc, node)
        elif node_type == "horizontalRule":
            _docx_add_horizontal_rule(doc)
        elif node_type == "table":
            _docx_add_table(doc, node)
        elif node_type == "image":
            _docx_add_image(doc, node)
        elif children:
            _docx_add_blocks(doc, children, quote)


def prosemirror_to_docx(title: str | None, content: dict[str, Any]) -> bytes:
    doc = Document()
    doc.core_properties.title = title or "Untitled Document"
    doc.add_heading(title or "Untitled Document", level=0)
    _docx_add_blocks(doc, _prosemirror_children(content))
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# PDF (ReportLab)
# ---------------------------------------------------------------------------

_PDF_ALIGN = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT, "justify": TA_JUSTIFY}
_PAGE_WIDTH = A4[0] - 50 * mm


def _pdf_styles() -> dict[str, ParagraphStyle]:
    body = ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=11, leading=15.5, spaceAfter=6,
        textColor=colors.HexColor("#20242b"),
    )
    styles: dict[str, ParagraphStyle] = {
        "Title": ParagraphStyle(
            "DocTitle", parent=body, fontName="Helvetica-Bold", fontSize=20,
            leading=26, spaceAfter=16,
        ),
        "Body": body,
        "ListItem": ParagraphStyle("ListItem", parent=body, spaceAfter=3),
        "Quote": ParagraphStyle(
            "Quote", parent=body, fontName="Helvetica-Oblique", leftIndent=16,
            textColor=colors.HexColor("#535d70"),
        ),
        "Code": ParagraphStyle(
            "CodeBlock", parent=body, fontName="Courier", fontSize=9.5, leading=12.5,
            backColor=colors.HexColor("#f1f3f6"), borderPadding=5, spaceAfter=8,
        ),
        "Cell": ParagraphStyle("Cell", parent=body, fontSize=10, leading=13, spaceAfter=0),
        "CellHeader": ParagraphStyle(
            "CellHeader", parent=body, fontName="Helvetica-Bold", fontSize=10,
            leading=13, spaceAfter=0,
        ),
        "Caption": ParagraphStyle(
            "Caption", parent=body, fontName="Helvetica-Oblique", fontSize=9,
            textColor=colors.HexColor("#535d70"),
        ),
    }
    for level, size in ((1, 18), (2, 15.5), (3, 13.5), (4, 12), (5, 11.5), (6, 11)):
        styles[f"H{level}"] = ParagraphStyle(
            f"H{level}", parent=body, fontName="Helvetica-Bold", fontSize=size,
            leading=size * 1.25, spaceBefore=10, spaceAfter=6,
        )
    return styles


def _pdf_block_style(base: ParagraphStyle, node: dict[str, Any]) -> ParagraphStyle:
    attrs = node.get("attrs", {})
    align = _PDF_ALIGN.get(attrs.get("textAlign"), TA_LEFT)
    indent = attrs.get("indent")
    left_indent = base.leftIndent + min(max(indent, 0), 8) * 18 if isinstance(indent, int) else base.leftIndent
    return ParagraphStyle(f"{base.name}-i{left_indent}a{align}", parent=base, alignment=align, leftIndent=left_indent)


def _pdf_inline(nodes: Sequence[dict[str, Any]]) -> str:
    parts: list[str] = []
    for node in nodes:
        node_type = node.get("type")
        if node_type == "hardBreak":
            parts.append("<br/>")
            continue
        if node_type != "text":
            alt = node.get("attrs", {}).get("alt")
            if alt:
                parts.append(xml_escape(str(alt)))
            continue
        text = xml_escape(node.get("text", ""))
        for mark in reversed(node.get("marks", [])):
            mark_type = mark.get("type")
            attrs = mark.get("attrs", {})
            if mark_type == "bold":
                text = f"<b>{text}</b>"
            elif mark_type == "italic":
                text = f"<i>{text}</i>"
            elif mark_type == "underline":
                text = f"<u>{text}</u>"
            elif mark_type == "strike":
                text = f"<strike>{text}</strike>"
            elif mark_type == "code":
                text = f'<font face="Courier" backColor="#f1f3f6">{text}</font>'
            elif mark_type == "subscript":
                text = f"<sub>{text}</sub>"
            elif mark_type == "superscript":
                text = f"<super>{text}</super>"
            elif mark_type == "textStyle":
                color = _hex_or_none(attrs.get("color"))
                if color:
                    text = f'<font color="#{color}">{text}</font>'
            elif mark_type == "highlight":
                color = _hex_or_none(attrs.get("color"))
                if color:
                    text = f'<font backColor="#{color}">{text}</font>'
            elif mark_type == "link":
                href = safe_link_url(attrs.get("href", ""))
                if href:
                    text = f'<link href={quoteattr(href)}><font color="#{_LINK_COLOR}"><u>{text}</u></font></link>'
        parts.append(text)
    return "".join(parts)


def _pdf_paragraph(markup: str, style: ParagraphStyle) -> Any:
    if not markup.strip():
        return Spacer(1, style.leading)
    return Paragraph(markup, style)


def _pdf_list(node: dict[str, Any], styles: dict[str, ParagraphStyle], depth: int = 0) -> Any:
    kind = node.get("type")
    items = []
    for item in node.get("content", []):
        flowables: list[Any] = []
        prefix = ""
        if kind == "taskList":
            prefix = "[x] " if item.get("attrs", {}).get("checked") else "[ ] "
        for child in item.get("content", []):
            child_type = child.get("type")
            if child_type in _LIST_TYPES:
                flowables.append(_pdf_list(child, styles, depth + 1))
            elif child_type == "paragraph":
                flowables.append(_pdf_paragraph(prefix + _pdf_inline(child.get("content", [])), styles["ListItem"]))
            else:
                flowables.extend(_pdf_blocks([child], styles))
        if flowables:
            items.append(ListItem(flowables, spaceBefore=1))
    if kind == "taskList":
        bullet = "bullet"
        start = None
    else:
        bullet = "bullet" if kind == "bulletList" else "1"
        start = node.get("attrs", {}).get("start")
        start = start if isinstance(start, int) and start > 1 else None
    kwargs = {"bulletType": bullet, "leftIndent": 16 + depth * 14}
    if start is not None:
        kwargs["start"] = start
    return ListFlowable(items, **kwargs)


def _pdf_table(node: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Any:
    rows = node.get("content", [])
    data: list[list[Any]] = []
    has_header = False
    for row in rows:
        rendered = []
        for cell in row.get("content", []):
            style = styles["CellHeader"] if cell.get("type") == "tableHeader" else styles["Cell"]
            if cell.get("type") == "tableHeader":
                has_header = True
            markup = "<br/>".join(
                _pdf_inline(child.get("content", []))
                for child in cell.get("content", [])
                if child.get("type") == "paragraph"
            )
            rendered.append(Paragraph(markup or " ", style))
        data.append(rendered)
    if not data:
        return Spacer(0, 0)
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dfe2e7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if has_header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f6f8")))
    return Table(data, style=TableStyle(commands), hAlign="LEFT")


def _pdf_image(node: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Any:
    attrs = node.get("attrs", {})
    data = _data_uri_bytes(attrs.get("src"))
    if data:
        try:
            from PIL import Image as PILImage

            stream = io.BytesIO(data)
            with PILImage.open(io.BytesIO(data)) as probe:
                width_px, height_px = probe.size
            width_pt, height_pt = width_px * 0.75, height_px * 0.75
            scale = min(1.0, _PAGE_WIDTH / width_pt) if width_pt else 1.0
            return RLImage(stream, width=width_pt * scale, height=height_pt * scale)
        except Exception:
            pass
    label = attrs.get("alt") or attrs.get("src") or "image"
    href = safe_link_url(attrs.get("src"))
    markup = f'[Image] <link href={quoteattr(href)}><font color="#{_LINK_COLOR}"><u>{xml_escape(str(label))}</u></font></link>' if href else f"[Image] {xml_escape(str(label))}"
    return Paragraph(markup, styles["Caption"])


def _pdf_blocks(nodes: Sequence[dict[str, Any]], styles: dict[str, ParagraphStyle], quote: bool = False) -> list[Any]:
    flowables: list[Any] = []
    for node in nodes:
        node_type = node.get("type")
        children = node.get("content", [])
        if node_type == "paragraph":
            base = styles["Quote"] if quote else styles["Body"]
            flowables.append(_pdf_paragraph(_pdf_inline(children), _pdf_block_style(base, node)))
        elif node_type == "heading":
            base = styles[f"H{_heading_level(node)}"]
            flowables.append(Paragraph(_pdf_inline(children) or " ", _pdf_block_style(base, node)))
        elif node_type == "blockquote":
            flowables.extend(_pdf_blocks(children, styles, quote=True))
        elif node_type in _LIST_TYPES:
            flowables.append(_pdf_list(node, styles))
        elif node_type == "codeBlock":
            text = "".join(child.get("text", "") for child in children)
            flowables.append(XPreformatted(text or " ", styles["Code"]))
        elif node_type == "horizontalRule":
            flowables.append(HRFlowable(
                width="100%", thickness=0.8, color=colors.HexColor("#c3cada"),
                spaceBefore=6, spaceAfter=6,
            ))
        elif node_type == "table":
            flowables.append(_pdf_table(node, styles))
        elif node_type == "image":
            flowables.append(_pdf_image(node, styles))
        elif children:
            flowables.extend(_pdf_blocks(children, styles, quote))
    return flowables


def prosemirror_to_pdf(title: str | None, content: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    styles = _pdf_styles()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=title or "Untitled Document",
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
    )
    story: list[Any] = [Paragraph(xml_escape(title or "Untitled Document"), styles["Title"])]
    story.extend(_pdf_blocks(_prosemirror_children(content), styles))
    document.build(story)
    return buffer.getvalue()
