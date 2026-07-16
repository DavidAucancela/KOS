"""Etapa 3 — Chunking por encabezados (estrategia default, doc 05 §3).

Los offsets de cada chunk son reales sobre `body`: `body[start:end] == chunk.text`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from kos_core.schemas import Chunk, ChunkPosition, ParsedDocument

MAX_CHUNK_CHARS = 1500

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^(```|~~~)")
_PARAGRAPH_SEPARATOR_RE = re.compile(r"\n[ \t]*\n+")


@dataclass(frozen=True)
class _Heading:
    line_start: int
    line_end: int
    level: int
    text: str


@dataclass(frozen=True)
class _Section:
    heading: str | None
    level: int | None
    start: int
    end: int


def _find_headings(body: str) -> list[_Heading]:
    """Encabezados de nivel 1 a 3 fuera de bloques de código cercados."""
    headings: list[_Heading] = []
    in_fence = False
    offset = 0
    for line in body.split("\n"):
        if _FENCE_RE.match(line.lstrip()):
            in_fence = not in_fence
        elif not in_fence:
            match = _HEADING_RE.match(line)
            if match:
                headings.append(
                    _Heading(
                        line_start=offset,
                        line_end=offset + len(line),
                        level=len(match.group(1)),
                        text=match.group(2).strip(),
                    )
                )
        offset += len(line) + 1
    return headings


def _sections(body: str) -> list[_Section]:
    headings = _find_headings(body)
    first_heading_start = headings[0].line_start if headings else len(body)
    sections = [_Section(heading=None, level=None, start=0, end=first_heading_start)]
    for index, heading in enumerate(headings):
        content_start = min(heading.line_end + 1, len(body))
        content_end = headings[index + 1].line_start if index + 1 < len(headings) else len(body)
        sections.append(
            _Section(
                heading=heading.text,
                level=heading.level,
                start=content_start,
                end=max(content_start, content_end),
            )
        )
    return sections


def _trimmed_span(body: str, start: int, end: int) -> tuple[int, int]:
    segment = body[start:end]
    leading = len(segment) - len(segment.lstrip())
    trailing = len(segment) - len(segment.rstrip())
    return start + leading, end - trailing


def _paragraph_spans(body: str, start: int, end: int) -> list[tuple[int, int]]:
    segment = body[start:end]
    boundaries: list[tuple[int, int]] = []
    position = 0
    for separator in _PARAGRAPH_SEPARATOR_RE.finditer(segment):
        boundaries.append((position, separator.start()))
        position = separator.end()
    boundaries.append((position, len(segment)))

    spans: list[tuple[int, int]] = []
    for rel_start, rel_end in boundaries:
        span = _trimmed_span(body, start + rel_start, start + rel_end)
        if span[1] > span[0]:
            spans.append(span)
    return spans


def _group_spans(spans: list[tuple[int, int]], max_chars: int) -> list[tuple[int, int]]:
    """Agrupa párrafos consecutivos sin exceder max_chars; parte los gigantes."""
    groups: list[tuple[int, int]] = []
    current: list[tuple[int, int]] = []

    def flush() -> None:
        if current:
            groups.append((current[0][0], current[-1][1]))
            current.clear()

    for start, end in spans:
        if end - start > max_chars:
            flush()
            position = start
            while position < end:
                groups.append((position, min(position + max_chars, end)))
                position += max_chars
            continue
        if current and end - current[0][0] > max_chars:
            flush()
        current.append((start, end))
    flush()
    return groups


def chunk_by_headings(doc: ParsedDocument) -> ParsedDocument:
    """Divide el body en chunks por encabezados; subdivide secciones largas."""
    body = doc.body or ""
    if not body.strip():
        return doc.model_copy(update={"chunks": []})

    chunks: list[Chunk] = []
    order = 0
    for section in _sections(body):
        start, end = _trimmed_span(body, section.start, section.end)
        if end <= start:
            continue
        if end - start <= MAX_CHUNK_CHARS:
            spans = [(start, end)]
        else:
            spans = _group_spans(_paragraph_spans(body, start, end), MAX_CHUNK_CHARS)
        for span_start, span_end in spans:
            span_start, span_end = _trimmed_span(body, span_start, span_end)
            if span_end <= span_start:
                continue
            chunks.append(
                Chunk(
                    doc_id=doc.doc_id,
                    text=body[span_start:span_end],
                    position=ChunkPosition(order=order, start=span_start, end=span_end),
                    metadata={"heading": section.heading, "level": section.level},
                )
            )
            order += 1
    return doc.model_copy(update={"chunks": chunks})
