from __future__ import annotations

import re
from dataclasses import dataclass


AUTO_MAX_LENGTH = 800
AUTO_OVERLAP = 80


class ChunkingError(ValueError):
    pass


@dataclass(frozen=True)
class Chunk:
    text: str
    start_offset: int
    end_offset: int
    offset_basis: str


def normalize_options(options: dict | None) -> dict:
    options = options or {}
    strategy = options.get("strategy") or "auto"
    if strategy not in {"auto", "custom", "hierarchy"}:
        raise ChunkingError("unsupported chunking strategy")
    normalized = {"strategy": strategy}
    if strategy == "custom":
        max_length = options.get("max_length", AUTO_MAX_LENGTH)
        overlap_percent = options.get("overlap_percent", 10)
        if not isinstance(max_length, int) or not 100 <= max_length <= 2000:
            raise ChunkingError("custom max_length must be between 100 and 2000")
        if not isinstance(overlap_percent, (int, float)) or not 0 <= overlap_percent <= 50:
            raise ChunkingError("custom overlap_percent must be between 0 and 50")
        separators = options.get("separators") or ["blank_line", "line", "sentence"]
        if not isinstance(separators, list) or not set(separators) <= {"blank_line", "line", "sentence"}:
            raise ChunkingError("custom separators are invalid")
        preprocess = options.get("preprocess") or {}
        if not isinstance(preprocess, dict) or not set(preprocess) <= {"remove_urls", "remove_emails", "collapse_whitespace"}:
            raise ChunkingError("custom preprocessing is invalid")
        normalized.update(
            max_length=max_length,
            overlap_percent=float(overlap_percent),
            separators=separators,
            preprocess={name: bool(value) for name, value in preprocess.items()},
        )
    return normalized


def preprocess_text(source: str, options: dict) -> tuple[str, str]:
    preprocess = options.get("preprocess") or {}
    text = source
    changed = False
    if preprocess.get("remove_urls"):
        text = re.sub(r"https?://\S+", "", text)
        changed = True
    if preprocess.get("remove_emails"):
        text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "", text)
        changed = True
    if preprocess.get("collapse_whitespace"):
        text = re.sub(r"\s+", " ", text).strip()
        changed = True
    return text, "preprocessed" if changed else "source"


def chunk_text(source: str, options: dict | None = None) -> tuple[list[Chunk], dict]:
    normalized = normalize_options(options)
    working, basis = preprocess_text(source, normalized)
    if not working:
        return [], normalized
    strategy = normalized["strategy"]
    if strategy == "hierarchy":
        chunks = _hierarchy_chunks(working, basis)
    else:
        max_length = normalized.get("max_length", AUTO_MAX_LENGTH)
        overlap = int(max_length * normalized.get("overlap_percent", AUTO_OVERLAP / AUTO_MAX_LENGTH))
        separators = normalized.get("separators", ["blank_line", "line", "sentence"])
        chunks = _window_chunks(working, max_length, overlap, separators, basis)
    return chunks, normalized


def _window_chunks(text: str, max_length: int, overlap: int, separators: list[str], basis: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    start = 0
    size = len(text)
    while start < size:
        end = min(start + max_length, size)
        if end < size:
            boundary = _find_boundary(text, start, end, separators)
            if boundary > start:
                end = boundary
        segment = text[start:end].strip()
        if segment:
            leading = len(text[start:end]) - len(text[start:end].lstrip())
            chunks.append(Chunk(segment, start + leading, end, basis))
        if end >= size:
            break
        next_start = end - overlap
        start = next_start if next_start > start else end
    return chunks


def _find_boundary(text: str, start: int, end: int, separators: list[str]) -> int:
    candidates: list[int] = []
    segment = text[start:end]
    if "blank_line" in separators:
        candidates.append(segment.rfind("\n\n"))
    if "line" in separators:
        candidates.append(segment.rfind("\n"))
    if "sentence" in separators:
        candidates.extend(segment.rfind(mark) for mark in ("。", "！", "？", ".", "!", "?"))
    offset = max(candidates, default=-1)
    return start + offset + 1 if offset >= max(1, max(len(segment) // 3, 1)) else end


def _hierarchy_chunks(text: str, basis: str) -> list[Chunk]:
    headings = list(re.finditer(r"(?m)^#{1,3}\s+.*$", text))
    if not headings:
        return _window_chunks(text, AUTO_MAX_LENGTH, AUTO_OVERLAP, ["blank_line", "line", "sentence"], basis)
    chunks: list[Chunk] = []
    for position, heading in enumerate(headings):
        start = heading.start()
        end = headings[position + 1].start() if position + 1 < len(headings) else len(text)
        chapter = text[start:end]
        if len(chapter) <= AUTO_MAX_LENGTH:
            chunks.append(Chunk(chapter.strip(), start, end, basis))
            continue
        heading_text = heading.group(0).strip()
        for child in _window_chunks(chapter, AUTO_MAX_LENGTH, AUTO_OVERLAP, ["blank_line", "line", "sentence"], basis):
            child_text = child.text if child.text.startswith(heading_text) else f"{heading_text}\n{child.text}"
            chunks.append(Chunk(child_text, start + child.start_offset, start + child.end_offset, basis))
    return chunks
