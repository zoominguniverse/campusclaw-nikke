from types import SimpleNamespace

import pytest
from app.tutor_seed import SAMPLES
from app.tutor_skills import SkillInputError, parse_skill, select_skill


def test_parse_utf8_bom_crlf_colons_comments_and_roundtrip():
    source = "\ufeff\r\n# comment\r\n" + SAMPLES["mathematics"].replace("：", ":").replace("\n", "\r\n")
    parsed = parse_skill(source)
    assert parsed["source_text"] == source
    assert parsed["enabled"] and parsed["tools_json"] == ["knowledge_search"]
    assert parsed["name"] == "数学解题引导"
    assert parse_skill(SAMPLES["language"])["subject_text"] == "语文"


@pytest.mark.parametrize("source", [
    "名称：test\n\nbody", SAMPLES["mathematics"].replace("启用：是", "启用：maybe"),
    SAMPLES["mathematics"].replace("工具：knowledge_search", "工具：shell"),
    SAMPLES["mathematics"].replace("名称：", "未知："),
    SAMPLES["mathematics"].replace("名称：", "名称：duplicate\n名称："),
    "名称：x\n适用条件：y\n启用：是\n\n", "x" * 8001,
    SAMPLES["mathematics"].replace("数学解题引导", "a" * 33),
    SAMPLES["mathematics"].replace("资料：数学", "资料：" + "x" * 33),
    "名称：x\n适用条件：" + "x" * 121 + "\n启用：是\n\nbody",
    "名称：x\n适用条件：y\n启用：是\n\n" + "x" * 2001,
])
def test_invalid_skill_rejected(source):
    with pytest.raises(SkillInputError):
        parse_skill(source)


def test_skill_length_bounds_and_optional_tools():
    parsed = parse_skill(f"名称：{'名' * 32}\n适用条件：{'词' * 120}\n资料：{'材' * 32}\n启用：否\n\n{'说' * 2000}")
    assert not parsed["enabled"] and parsed["tools_json"] == []


def test_route_tie_casefold_separators_zero_and_disabled():
    def skill(ident, words, enabled=True):
        return SimpleNamespace(id=ident, trigger_text=words, enabled=enabled, legacy_placeholder=False)
    smaller = skill(1, "Equation、去括号；通分|面积")
    larger = skill(2, "equation,去括号")
    disabled = skill(3, "equation,去括号,通分", False)
    assert select_skill("EQUATION去括号通分", [larger, smaller, disabled]) is smaller
    assert select_skill("equation", [larger, smaller]) is smaller
    assert select_skill("古诗", [larger, smaller]) is None


def test_delivered_upload_samples_match_parser():
    from pathlib import Path
    for key, expected in SAMPLES.items():
        source = (Path(__file__).parents[1] / "tutor_samples" / f"{key}.txt").read_text(encoding="utf-8")
        assert source == expected and parse_skill(source)["enabled"]
