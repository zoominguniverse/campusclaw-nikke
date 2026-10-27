"""The course's text skill format and deterministic, bound-only routing."""
import re

SEPARATORS = r"[,，、;；|]"
KEYS = {"名称", "适用条件", "资料", "工具", "启用"}


class SkillInputError(ValueError):
    pass


def split_words(value):
    return [part.strip() for part in re.split(SEPARATORS, value) if part.strip()]


def parse_skill(source):
    if not isinstance(source, str) or not source.strip() or len(source) > 8000 or "\x00" in source:
        raise SkillInputError("技能文件须为非空 UTF-8 文本，最多8000字")
    lines = source.lstrip("\ufeff").splitlines()
    metadata, body = {}, None
    for index, line in enumerate(lines):
        value = line.strip()
        if not value:
            if metadata:
                body = "\n".join(lines[index + 1:]).strip()
                break
            continue
        if value.startswith("#"):
            continue
        pair = re.split(r"[:：]", value, maxsplit=1)
        if len(pair) != 2 or pair[0].strip() not in KEYS:
            raise SkillInputError(f"第{index + 1}行包含未定义字段")
        key, value = (part.strip() for part in pair)
        if key in metadata:
            raise SkillInputError(f"字段重复：{key}")
        metadata[key] = value
    for key in ("名称", "适用条件", "启用"):
        if not metadata.get(key):
            raise SkillInputError(f"缺少必填字段：{key}")
    if not body:
        raise SkillInputError("元数据之后须有空行和非空技能说明")
    for key, maximum in [("名称", 32), ("适用条件", 120), ("资料", 32)]:
        if len(metadata.get(key, "")) > maximum:
            raise SkillInputError(f"{key}最多{maximum}字")
    if len(body) > 2000:
        raise SkillInputError("技能说明最多2000字")
    if not split_words(metadata["适用条件"]):
        raise SkillInputError("适用条件须包含至少一个关键词")
    if metadata["启用"] not in {"是", "否"}:
        raise SkillInputError("启用必须为是或否")
    tools = split_words(metadata.get("工具", ""))
    from .mcp_policy import TOOL_REF
    if len(tools) > 32 or any(tool != "knowledge_search" and not TOOL_REF.fullmatch(tool) for tool in tools):
        raise SkillInputError("工具须为 knowledge_search 或 tool_name@server-name（最多32项）")
    return dict(name=metadata["名称"], trigger_text=metadata["适用条件"],
                subject_text=metadata.get("资料", ""), tools_json=list(dict.fromkeys(tools)),
                description=body, source_text=source, enabled=metadata["启用"] == "是", legacy_placeholder=False)


def select_skill(question, candidates):
    selected, best = None, 0
    question = question.casefold()
    for skill in sorted(candidates, key=lambda item: item.id):
        if not skill.enabled or skill.legacy_placeholder:
            continue
        score = sum(word.casefold() in question for word in split_words(skill.trigger_text))
        if score > best:
            selected, best = skill, score
    return selected
