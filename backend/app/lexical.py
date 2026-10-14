"""Shared fixed tokenizer rules; changing these requires a new profile/rebuild."""
from functools import lru_cache
import hashlib
import logging
from pathlib import Path
import re

import jieba

from .profiles import TOKENIZER_VERSION

STOPWORDS = frozenset({"的", "了", "吗", "呢", "请", "什么", "如何", "是", "在", "有", "和", "与", "及"})
DOMAIN_TERMS = ("基本单位", "细胞膜", "细胞核", "叶绿体", "线粒体", "光合作用", "呼吸作用", "蒸腾作用", "无机盐", "正电荷", "异种电荷", "同种电荷", "串联电路", "并联电路", "质量守恒", "平均数", "平行四边形", "一次函数", "二氧化碳", "圆周率", "催化剂", "不能", "不等", "小于", "大于")


@lru_cache(maxsize=1)
def tokenizer():
    if jieba.__version__ != "0.42.1":
        raise RuntimeError("jieba dictionary/tokenizer version changed; rebuild required")
    expected = "7197c3211ddd98962b036cdf40324d1ea2bfaa12bd028e68faa70111a88e12a8"
    if hashlib.sha256(Path(jieba.__file__).with_name("dict.txt").read_bytes()).hexdigest() != expected:
        raise RuntimeError("jieba dictionary changed; rebuild required")
    jieba.setLogLevel(logging.WARNING)
    result = jieba.Tokenizer()
    cache = Path(__file__).parents[1] / ".tokenizer-cache"
    cache.mkdir(exist_ok=True)
    result.tmp_dir = str(cache)
    result.initialize()
    for term in DOMAIN_TERMS:
        result.add_word(term, freq=1000000)
    return result


def tokenize(text, *, query=False):
    value = text.casefold()
    # Spaces delimit pieces, but compound terms still use the source dictionary.
    # Keeping a query compound whole while splitting its source loses recall.
    pieces = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?|[\u3400-\u9fff]+", value)
    result = []
    engine = tokenizer()
    for piece in pieces:
        words = engine.lcut(piece, HMM=False)
        unknown = ""
        def flush_unknown():
            if len(unknown) >= 2:
                if len(unknown) <= 8:
                    result.append(unknown)
                result.extend(unknown[i:i + 2] for i in range(min(len(unknown) - 1, 8)))
        for word in words:
            if not word.strip() or word in STOPWORDS:
                flush_unknown()
                unknown = ""
                continue
            result.append(word)
            if len(word) == 1 and "\u3400" <= word <= "\u9fff" and word not in {"不", "无", "未"}:
                unknown += word
            else:
                flush_unknown()
                unknown = ""
        flush_unknown()
    return list(dict.fromkeys(result))


def lexical_text(text):
    return " ".join(tokenize(text))


def query_groups(text):
    """Retain explicit terms as coverage units, expanding with the source tokenizer.

    A compound must not outweigh a missing separate qualifier just because its
    dictionary segmentation produces more tokens. Continuous queries retain
    ordinary token coverage.
    """
    if len(text.strip().split()) > 1:
        groups = [tuple(tokenize(piece)) for piece in text.split()]
    else:
        groups = [(term,) for term in tokenize(text)]
    return list(dict.fromkeys(group for group in groups if group))
