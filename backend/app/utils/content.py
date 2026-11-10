"""Utilities for converting ProseMirror JSON to text, Markdown, HTML and
computing basic document analytics / readability metrics."""
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit


def safe_link_url(value: Any) -> str | None:
    if not isinstance(value, str) or any(ord(char) < 32 for char in value) or "\\" in value:
        return None
    value = value.strip()
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme.lower() in ("http", "https") and parsed.netloc:
        return value
    if parsed.scheme.lower() in ("mailto", "tel") and parsed.path:
        return value
    if value.startswith("#") or (value.startswith("/") and not value.startswith("//")):
        return value
    return None


def _heading_level(node: dict[str, Any]) -> int:
    level = node.get("attrs", {}).get("level", 1)
    return level if type(level) is int and 1 <= level <= 6 else 1


def _inline_to_text(node: dict[str, Any]) -> str:
    text = node.get("text", "")
    return text


def _inline_to_markdown(node: dict[str, Any]) -> str:
    text = node.get("text", "")
    marks = node.get("marks", [])
    for mark in reversed(marks):
        mark_type = mark.get("type")
        if mark_type == "bold":
            text = f"**{text}**"
        elif mark_type == "italic":
            text = f"*{text}*"
        elif mark_type == "code":
            text = f"`{text}`"
        elif mark_type == "link":
            href = mark.get("attrs", {}).get("href", "")
            text = f"[{text}]({href})"
    return text


def _inline_to_html(node: dict[str, Any]) -> str:
    text = escape_html(node.get("text", ""))
    marks = node.get("marks", [])
    for mark in reversed(marks):
        mark_type = mark.get("type")
        if mark_type == "bold":
            text = f"<strong>{text}</strong>"
        elif mark_type == "italic":
            text = f"<em>{text}</em>"
        elif mark_type == "code":
            text = f"<code>{text}</code>"
        elif mark_type == "link":
            href = safe_link_url(mark.get("attrs", {}).get("href", ""))
            if href:
                text = f'<a href="{escape_html(href)}">{text}</a>'
    return text


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _children_to_text(children: Sequence[dict[str, Any]]) -> str:
    return "".join(_node_to_text(child) for child in children)


def _children_to_markdown(children: Sequence[dict[str, Any]]) -> str:
    return "".join(_node_to_markdown(child) for child in children)


def _children_to_html(children: Sequence[dict[str, Any]]) -> str:
    return "".join(_node_to_html(child) for child in children)


def _node_to_text(node: dict[str, Any]) -> str:
    node_type = node.get("type")
    if node_type == "text":
        return _inline_to_text(node)

    children = node.get("content", [])
    if node_type == "hardBreak":
        return "\n"
    if node_type == "paragraph":
        return _children_to_text(children) + "\n"
    if node_type in ("heading", "blockquote"):
        return _children_to_text(children) + "\n"
    if node_type in ("bulletList", "orderedList"):
        return _children_to_text(children)
    if node_type == "listItem":
        return _children_to_text(children) + "\n"
    if node_type == "table":
        return "\n" + _children_to_text(children) + "\n"
    if node_type == "tableRow":
        return _children_to_text(children) + "\n"
    if node_type == "tableCell" or node_type == "tableHeader":
        return _children_to_text(children) + "\t"
    if node_type == "codeBlock":
        return _children_to_text(children) + "\n"
    if children:
        return _children_to_text(children)
    return ""


def _node_to_markdown(node: dict[str, Any]) -> str:
    node_type = node.get("type")
    if node_type == "text":
        return _inline_to_markdown(node)
    if node_type == "hardBreak":
        return "\n"

    children = node.get("content", [])
    content = _children_to_markdown(children)

    if node_type == "paragraph":
        return f"{content.strip()}\n\n"
    if node_type == "heading":
        level = _heading_level(node)
        prefix = "#" * level
        return f"{prefix} {content.strip()}\n\n"
    if node_type == "blockquote":
        lines = content.strip().splitlines()
        quoted = "\n".join(f"> {line}" for line in lines)
        return f"{quoted}\n\n"
    if node_type == "bulletList":
        items = "".join(_node_to_markdown(child) for child in children)
        return f"{items}\n"
    if node_type == "orderedList":
        items = "".join(_node_to_markdown(child) for child in children)
        return f"{items}\n"
    if node_type == "listItem":
        text = _children_to_markdown(children).strip()
        return f"- {text}\n"
    if node_type == "codeBlock":
        language = node.get("attrs", {}).get("language", "")
        return f"```{language}\n{content.strip()}\n```\n\n"
    if node_type == "horizontalRule":
        return "---\n\n"
    if node_type == "table":
        return _table_to_markdown(children)
    if children:
        return content
    return ""


def _table_to_markdown(rows: Sequence[dict[str, Any]]) -> str:
    if not rows:
        return ""

    parsed_rows: list[list[str]] = []
    for row in rows:
        cells = []
        for cell in row.get("content", []):
            cell_text = _children_to_markdown(cell.get("content", [])).strip().replace("|", "\\|")
            cells.append(cell_text)
        parsed_rows.append(cells)

    if not parsed_rows:
        return ""

    col_count = max(len(row) for row in parsed_rows)
    lines: list[str] = []
    for idx, row in enumerate(parsed_rows):
        padded = row + [""] * (col_count - len(row))
        lines.append("| " + " | ".join(padded) + " |")
        if idx == 0:
            lines.append("|" + "|".join([" --- " for _ in range(col_count)]) + "|")

    return "\n" + "\n".join(lines) + "\n\n"


def _node_to_html(node: dict[str, Any]) -> str:
    node_type = node.get("type")
    if node_type == "text":
        return _inline_to_html(node)
    if node_type == "hardBreak":
        return "<br>"

    children = node.get("content", [])
    content = _children_to_html(children)

    if node_type == "paragraph":
        return f"<p>{content}</p>\n"
    if node_type == "heading":
        level = _heading_level(node)
        return f"<h{level}>{content}</h{level}>\n"
    if node_type == "blockquote":
        return f"<blockquote>\n{content}</blockquote>\n"
    if node_type == "bulletList":
        return f"<ul>\n{content}</ul>\n"
    if node_type == "orderedList":
        return f"<ol>\n{content}</ol>\n"
    if node_type == "listItem":
        return f"<li>{content}</li>\n"
    if node_type == "codeBlock":
        return f"<pre><code>{content}</code></pre>\n"
    if node_type == "horizontalRule":
        return "<hr>\n"
    if node_type == "table":
        return f"<table>\n{content}</table>\n"
    if node_type == "tableRow":
        return f"<tr>\n{content}</tr>\n"
    if node_type == "tableHeader":
        return f"<th>{content}</th>\n"
    if node_type == "tableCell":
        return f"<td>{content}</td>\n"
    if children:
        return content
    return ""


def _prosemirror_children(content: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(content, dict):
        return content.get("content", [])
    if isinstance(content, list):
        return content
    return []


def prosemirror_to_text(content: dict[str, Any]) -> str:
    return _children_to_text(_prosemirror_children(content)).strip()


def prosemirror_to_markdown(content: dict[str, Any]) -> str:
    return _children_to_markdown(_prosemirror_children(content)).strip()


def prosemirror_to_html(content: dict[str, Any]) -> str:
    children = _prosemirror_children(content)
    return "".join(_node_to_html(child) for child in children)


def _syllable_count(word: str) -> int:
    word = word.lower().strip(".,!?;:'\"-")
    if not word:
        return 0
    vowels = re.findall(r"[aeiouy]+", word)
    return max(1, len(vowels))


def compute_stats(text: str) -> dict[str, Any]:
    words = re.findall(r"\b\w+\b", text) if text else []
    word_count = len(words)
    char_count = len(text)
    sentences = re.split(r"[.!?]+", text) if text else []
    sentence_count = len([s for s in sentences if s.strip()])
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    paragraph_count = len(paragraphs)

    syllable_count = sum(_syllable_count(w) for w in words)
    reading_time_minutes = word_count / 200.0

    flesch_reading_ease = 0.0
    flesch_kincaid_grade = 0.0
    if word_count > 0 and sentence_count > 0:
        avg_sentence_length = word_count / sentence_count
        avg_syllables_per_word = syllable_count / word_count
        flesch_reading_ease = (
            206.835 - 1.015 * avg_sentence_length - 84.6 * avg_syllables_per_word
        )
        flesch_kincaid_grade = (
            0.39 * avg_sentence_length + 11.8 * avg_syllables_per_word - 15.59
        )

    return {
        "word_count": word_count,
        "char_count": char_count,
        "sentence_count": sentence_count,
        "paragraph_count": paragraph_count,
        "syllable_count": syllable_count,
        "estimated_reading_time_minutes": round(reading_time_minutes, 2),
        "flesch_reading_ease": round(flesch_reading_ease, 2),
        "flesch_kincaid_grade": round(flesch_kincaid_grade, 2),
    }


def readability_suggestions(metrics: dict[str, Any]) -> list[str]:
    suggestions: list[str] = []
    if metrics["word_count"] == 0:
        return suggestions
    ease = metrics["flesch_reading_ease"]
    grade = metrics["flesch_kincaid_grade"]
    if ease < 30:
        suggestions.append("Very difficult to read. Consider shorter sentences and simpler words.")
    elif ease < 60:
        suggestions.append("Fairly difficult. Try simplifying some sentences.")
    elif ease > 90:
        suggestions.append("Easy to read. Great for broad audiences.")
    if grade > 12:
        suggestions.append("Education level is high; consider simplifying for a general audience.")
    return suggestions
