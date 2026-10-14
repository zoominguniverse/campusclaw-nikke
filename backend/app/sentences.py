import re


def sentence_ranges(text):
    for match in re.finditer(r"[^。！？!?\r\n]+(?:[。！？!?]+|(?=\r?\n)|$)|[。！？!?]+", text):
        raw = match.group()
        start = match.start() + len(raw) - len(raw.lstrip())
        end = match.end() - len(raw) + len(raw.rstrip())
        if start < end:
            yield start, end


def evidence_ranges(text):
    for start, end in sentence_ranges(text):
        while start < end:
            stop = min(start + 160, end)
            yield start, stop
            if stop == end:
                break
            start = stop - 40
