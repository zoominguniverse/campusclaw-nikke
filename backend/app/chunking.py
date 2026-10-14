from __future__ import annotations

import re
from dataclasses import dataclass, field

AUTO_MAX_LENGTH = 800
AUTO_OVERLAP = 80
SEPARATORS = ["blank_line", "line", "sentence"]


class ChunkingError(ValueError):
    pass


@dataclass(frozen=True)
class Chunk:
    text: str
    start_offset: int
    end_offset: int
    offset_basis: str
    heading_context: str = ""
    source_mapping: list[dict] = field(default_factory=list)
    source_spans: list[dict] = field(default_factory=list)


def normalize_options(options: dict | None) -> dict:
    if options is None:
        options = {}
    if not isinstance(options, dict) or set(options) - {"strategy", "max_length", "overlap_percent", "separators", "preprocess"}:
        raise ChunkingError("chunking options must contain supported fields")
    strategy = options.get("strategy", "auto")
    if not isinstance(strategy, str) or strategy not in {"auto", "custom", "hierarchy"}:
        raise ChunkingError("unsupported chunking strategy")
    length = options.get("max_length", AUTO_MAX_LENGTH) if strategy == "custom" else AUTO_MAX_LENGTH
    overlap = options.get("overlap_percent", 10) if strategy == "custom" else 10
    if type(length) is not int or not 100 <= length <= 2000:
        raise ChunkingError("custom max_length must be between 100 and 2000")
    if type(overlap) not in (int, float) or not 0 <= overlap <= 50:
        raise ChunkingError("custom overlap_percent must be between 0 and 50")
    separators = options.get("separators", SEPARATORS) if strategy == "custom" else SEPARATORS
    if not isinstance(separators, list) or any(not isinstance(s, str) or s not in SEPARATORS for s in separators) or len(set(separators)) != len(separators):
        raise ChunkingError("custom separators are invalid")
    preprocess = options.get("preprocess", {})
    if not isinstance(preprocess, dict) or set(preprocess) - {"remove_urls", "remove_emails", "collapse_whitespace"} or any(type(v) is not bool for v in preprocess.values()):
        raise ChunkingError("preprocessing options must be boolean")
    return {"strategy": strategy, "max_length": length, "overlap_percent": float(overlap), "separators": list(separators),
            "preprocess": {name: preprocess.get(name, False) for name in ("remove_urls", "remove_emails", "collapse_whitespace")}}


def _segment(wstart, wend, sstart, send, operation="keep"):
    return {"working_start": wstart, "working_end": wend, "source_start": sstart, "source_end": send, "operation": operation}


def slice_mapping(mapping, start, end):
    result = []
    for item in mapping:
        low, high = max(start, item["working_start"]), min(end, item["working_end"])
        if low >= high:
            continue
        if item["operation"] == "keep":
            source_start = item["source_start"] + low - item["working_start"]
            source_end = source_start + high - low
        else:
            source_start, source_end = item["source_start"], item["source_end"]
        result.append(_segment(low, high, source_start, source_end, item["operation"]))
    return result


def source_spans(mapping):
    spans = []
    for item in mapping:
        start, end = item["source_start"], item["source_end"]
        if spans and start == spans[-1]["end"]:
            spans[-1]["end"] = end
        else:
            spans.append({"start": start, "end": end})
    return spans


def preprocess_with_mapping(source, options):
    preprocess = options.get("preprocess", {})
    patterns = []
    if preprocess.get("remove_urls"):
        patterns.append(r"https?://[^\s<>。！？；，]+")
    if preprocess.get("remove_emails"):
        patterns.append(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
    parts, mapping, position, working_position = [], [], 0, 0
    removed = re.finditer("|".join(patterns), source) if patterns else []
    for match in removed:
        if match.start() > position:
            text = source[position:match.start()]
            parts.append(text)
            mapping.append(_segment(working_position, working_position + len(text), position, match.start()))
            working_position += len(text)
        position = match.end()
    if position < len(source):
        parts.append(source[position:])
        mapping.append(_segment(working_position, working_position + len(source) - position, position, len(source)))
    working = "".join(parts)
    if preprocess.get("collapse_whitespace"):
        parts, collapsed, position = [], [], 0
        for match in re.finditer(r"\s+|\S+", working):
            original_mapping = slice_mapping(mapping, match.start(), match.end())
            if match.group().isspace():
                parts.append(" ")
                # Retain a whitespace source representative; never span deleted
                # URL/email gaps when a whitespace run bridges a deletion.
                first = original_mapping[0]
                collapsed.append(_segment(position, position + 1, first["source_start"], first["source_end"], "collapse"))
                position += 1
            else:
                parts.append(match.group())
                for item in original_mapping:
                    delta = position - match.start()
                    collapsed.append({**item, "working_start": item["working_start"] + delta, "working_end": item["working_end"] + delta})
                position += len(match.group())
        working, mapping = "".join(parts), collapsed
    return working, mapping


def preprocess_text(source: str, options: dict) -> tuple[str, str]:
    working, _ = preprocess_with_mapping(source, options)
    return working, "source" if working == source else "preprocessed"


def _find_boundary(text, start, end, separators):
    segment = text[start:end]
    for separator in SEPARATORS:
        if separator not in separators:
            continue
        if separator == "blank_line":
            matches = list(re.finditer(r"\r?\n[ \t]*\r?\n", segment))
        elif separator == "line":
            matches = list(re.finditer(r"\r?\n", segment))
        else:
            matches = list(re.finditer(r"[。！？.!?](?:[\"'”’）)]*)", segment))
        if matches:
            return start + matches[-1].end()
    return end


def _window_ranges(text, start, end, length, overlap, separators):
    while start < end:
        stop = min(start + length, end)
        if stop < end:
            stop = _find_boundary(text, start, stop, separators)
        raw = text[start:stop]
        low = start + len(raw) - len(raw.lstrip())
        high = stop - len(raw) + len(raw.rstrip())
        if low < high:
            yield low, high
        if stop == end:
            break
        start = stop - overlap if stop - overlap > start else stop


def chunk_text(source: str, options: dict | None = None) -> tuple[list[Chunk], dict]:
    if not isinstance(source, str):
        raise ChunkingError("source text must be a string")
    normalized = normalize_options(options)
    working, mapping = preprocess_with_mapping(source, normalized)
    basis = "source" if working == source else "preprocessed"
    regions = [(0, len(working), "")]
    if normalized["strategy"] == "hierarchy":
        headings = list(re.finditer(r"(?m)^(#{1,3})\s+[^\r\n]*", working))
        if headings:
            regions, parents = [], []
            if headings[0].start() > 0:
                regions.append((0, headings[0].start(), ""))
            for i, heading in enumerate(headings):
                level = len(heading.group(1))
                parents = [(depth, value) for depth, value in parents if depth < level]
                parents.append((level, heading.group().strip()))
                regions.append((heading.start(), headings[i + 1].start() if i + 1 < len(headings) else len(working), "\n".join(value for _, value in parents)))
    chunks = []
    for start, end, context in regions:
        for low, high in _window_ranges(working, start, end, normalized["max_length"], int(normalized["max_length"] * normalized["overlap_percent"] / 100), normalized["separators"]):
            selected = slice_mapping(mapping, low, high)
            chunks.append(Chunk(working[low:high], low, high, basis, context, selected, source_spans(selected)))
    return chunks, normalized
