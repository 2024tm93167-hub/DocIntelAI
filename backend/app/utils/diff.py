"""Text diff helpers for comparing document contents."""
from difflib import SequenceMatcher
import re
from typing import Any


def prosemirror_to_text(content: dict[str, Any]) -> str:
    """Convert a ProseMirror/TipTap JSON document to plain text.

    Paragraph and block boundaries are preserved as newlines where possible.
    """
    parts: list[str] = []
    _walk_node(content, parts)
    return "\n".join(parts).strip()


def _walk_node(node: dict[str, Any], parts: list[str]) -> None:
    node_type = node.get("type")
    content_nodes = node.get("content")

    if node_type == "text":
        text = node.get("text", "")
        marks = node.get("marks", [])
        if any(m.get("type") == "code" for m in marks):
            text = f"`{text}`"
        if any(m.get("type") == "link" for m in marks):
            href = next(
                (m.get("attrs", {}).get("href", "") for m in marks if m.get("type") == "link"),
                "",
            )
            text = f"{text} ({href})"
        parts.append(text)
        return

    if node_type in ("paragraph", "heading", "list_item", "blockquote"):
        block_parts: list[str] = []
        if content_nodes:
            for child in content_nodes:
                _walk_node(child, block_parts)
        parts.append("".join(block_parts))
        return

    if node_type in ("bullet_list", "ordered_list"):
        for child in content_nodes or []:
            _walk_node(child, parts)
        return

    if node_type in ("table", "table_row"):
        for child in content_nodes or []:
            _walk_node(child, parts)
        return

    if node_type == "table_cell" or node_type == "table_header":
        cell_parts: list[str] = []
        for child in content_nodes or []:
            _walk_node(child, cell_parts)
        parts.append(" | ".join(cell_parts))
        return

    if content_nodes:
        for child in content_nodes:
            _walk_node(child, parts)


def diff_texts(old_text: str, new_text: str) -> list[tuple[str, str, str]]:
    """Return a list of (op, old_chunk, new_chunk) tuples.

    Operations are: equal, insert, delete, replace.
    """
    old_tokens = re.findall(r"\w+|\s+|[^\w\s]", old_text)
    new_tokens = re.findall(r"\w+|\s+|[^\w\s]", new_text)
    sm = SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    results: list[tuple[str, str, str]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        old_chunk = "".join(old_tokens[i1:i2])
        new_chunk = "".join(new_tokens[j1:j2])
        if tag == "equal":
            results.append(("equal", old_chunk, new_chunk))
        elif tag == "replace":
            results.append(("replace", old_chunk, new_chunk))
        elif tag == "delete":
            results.append(("delete", old_chunk, ""))
        elif tag == "insert":
            results.append(("insert", "", new_chunk))
    return results
