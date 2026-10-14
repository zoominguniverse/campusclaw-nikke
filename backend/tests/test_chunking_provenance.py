import pytest

from app.chunking import chunk_text, preprocess_with_mapping, normalize_options, ChunkingError, _find_boundary


@pytest.mark.parametrize("strategy", ["auto", "custom", "hierarchy"])
@pytest.mark.parametrize("source", ["前言。\n\n# 章节\n" + "正文。😀" * 600, "无标题内容。" * 500, "短段落。\n\n下一段。", "  😀A\r\nB。  \r\n"])
def test_nonwhitespace_coverage_trim_and_working_slice(strategy, source):
    chunks, options = chunk_text(source, {"strategy": strategy})
    covered = {i for c in chunks for i in range(c.start_offset, c.end_offset)}
    assert all(i in covered for i, char in enumerate(source) if not char.isspace())
    assert all(source[c.start_offset:c.end_offset] == c.text for c in chunks)
    assert options["overlap_percent"] == 10 and options["max_length"] == 800
    assert all(c.source_spans == [{"start": c.start_offset, "end": c.end_offset}] for c in chunks)


def test_paragraph_before_line_before_sentence():
    source = "段落。\n\n后一段。\n再一句。余下"
    assert _find_boundary(source, 0, len(source), ["sentence", "line", "blank_line"]) == 5
    assert _find_boundary(source, 0, len(source), ["sentence", "line"]) == 10


@pytest.mark.parametrize("preprocess", [{"remove_urls": True}, {"remove_emails": True}, {"collapse_whitespace": True}, {"remove_urls": True, "remove_emails": True, "collapse_whitespace": True}])
def test_removal_collapse_emoji_crlf_mapping(preprocess):
    source = "  😀甲\r\n\r\n乙 https://example.com/" + "u" * 300 + "。 a@example.com\t\t丙。\n"
    chunks, options = chunk_text(source, {"strategy": "custom", "max_length": 100, "preprocess": preprocess})
    working, mapping = preprocess_with_mapping(source, options)
    for c in chunks:
        assert working[c.start_offset:c.end_offset] == c.text
        previous = -1
        for segment in c.source_mapping:
            start, end = segment["source_start"], segment["source_end"]
            assert 0 <= start < end <= len(source) and start >= previous
            previous = end
            value = working[segment["working_start"]:segment["working_end"]]
            assert value == source[start:end] if segment["operation"] == "keep" else value == " " and source[start:end].isspace()
        if preprocess.get("remove_urls"):
            assert all("https://" not in source[s["start"]:s["end"]] for s in c.source_spans)


@pytest.mark.parametrize("options", [[], {"strategy": []}, {"strategy": "custom", "max_length": True}, {"strategy": "custom", "overlap_percent": True}, {"preprocess": {"remove_urls": "false"}}, {"strategy": "custom", "separators": ["line", "line"]}])
def test_invalid_options_raise_chunking_error(options):
    with pytest.raises(ChunkingError):
        normalize_options(options)
