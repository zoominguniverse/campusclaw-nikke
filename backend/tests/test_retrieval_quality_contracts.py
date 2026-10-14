import math
from unittest.mock import patch

import pytest

from app.database import db
from app.indexing import index_entry
from app.lexical import tokenize, query_groups
from app.models import KnowledgeChunk, KnowledgeIndexGeneration, KnowledgeEmbedding, KnowledgeChunkSentence, KnowledgeSentenceEmbedding
from app.providers import OpenAICompatibleEmbeddingClient, ProviderUnavailable, embed_validated, validate_vector
from app.retrieval import retrieve, _vector_ranked

from .conftest import login
from .test_retrieval_quality_regressions import add_entry


def test_fixed_shared_tokenizer_mixed_numeric_negation_explicit_unknown():
    query = tokenize("结构 功能 基本单位", query=True)
    assert query == ["结构", "功能", "基本单位"]
    assert set(query) <= set(tokenize("细胞是生物体结构和功能的基本单位。"))
    assert set(tokenize("不 不能 180 pH ATP", query=True)) == {"不", "不能", "180", "ph", "atp"}
    assert "鹭霁" in tokenize("珞珈鹭霁")
    assert tokenize("的 了 吗", query=True) == []


@pytest.mark.parametrize('query,source', [
    ('气体压强 实验观察', '通过实验观察气体压强的变化。'),
    ('图书馆管理员 查询', '可以查询图书馆管理员的排班信息。'),
    ('电流方向 正电荷 定向移动', '电流方向规定为正电荷定向移动的方向。'),
    ('光 均匀介质 直线', '光在均匀介质中沿直线传播。'),
])
def test_space_delimited_compounds_share_source_segmentation(app, query, source):
    groups, words = query_groups(query), set(tokenize(source))
    assert sum(set(group) <= words for group in groups) >= max(2, math.ceil(.6 * len(groups)))
    with app.app_context():
        entry = add_entry(source)
        index_entry(entry)
        with patch('app.retrieval.embedding_client') as provider:
            hits = retrieve(class_id=1, query=query, mode='keyword')['hits']
        assert hits and hits[0]['material_id'] == entry.material_id
        provider.assert_not_called()


def test_explicit_term_coverage_retains_missing_qualifier(app):
    assert query_groups('B 班示例材料内容') == [('b',), ('班', '示例', '材料', '内容')]
    with app.app_context():
        entry = add_entry('A 班示例材料内容。')
        index_entry(entry)
        assert not retrieve(class_id=1, query='B 班示例材料内容', mode='keyword')['hits']
        assert retrieve(class_id=1, query='A 班示例材料内容', mode='keyword')['hits']


@pytest.mark.parametrize("vector", [[], [0., 0.], [1.], [math.nan, 1.], [math.inf, 1.], [True, 1.], ["1", 0.], [1.7e308, 1.7e308]])
def test_provider_rejects_wrong_nonfinite_nonnumeric_zero_vectors(vector):
    with pytest.raises(ProviderUnavailable):
        validate_vector(vector, 2)


def test_provider_bounded_batch_order_and_missing_duplicate_indices(app):
    with app.app_context():
        app.config.update(EMBEDDING_API_URL="https://embedding.example/v1", EMBEDDING_API_KEY="server-secret", EMBEDDING_MODEL="fixture", EMBEDDING_DIMENSIONS=2, EMBEDDING_BATCH_SIZE=2)
        with patch("app.providers.requests.post") as post:
            post.return_value.json.side_effect = [{"data": [{"index": 1, "embedding": [0., 2.]}, {"index": 0, "embedding": [3., 0.]}]}, {"data": [{"index": 0, "embedding": [1., 1.]}]}]
            vectors = embed_validated(OpenAICompatibleEmbeddingClient(), ["一", "二", "三"])
        assert vectors[:2] == [[1., 0.], [0., 1.]] and len(vectors) == 3
        assert [call.kwargs["json"]["input"] for call in post.call_args_list] == [["一", "二"], ["三"]]
        for response in ({"data": []}, {"data": [{"index": 0, "embedding": [1, 0]}, {"index": 0, "embedding": [1, 0]}]}, {"data": [{"embedding": [1, 0]}]}):
            with patch("app.providers.requests.post") as post, pytest.raises(ProviderUnavailable):
                post.return_value.json.return_value = response
                OpenAICompatibleEmbeddingClient().embed_batch(["一", "二"])


@pytest.mark.parametrize("payload", [{"query": 123}, {"query": []}, {"query": "资料", "limit": True}, {"query": "资料", "limit": 0}, {"query": "资料", "limit": 21}, {"query": "资料", "mode": []}, {"query": "资料", "subject_id": True}, {"query": "资料", "subject_id": "1"}, [1]])
def test_bad_retrieval_input_is_400_without_models(client, payload):
    login(client, "student_a1", "student-a-password")
    with patch("app.retrieval.embedding_client") as provider, patch("app.answers.chat_client") as chat:
        response = client.post("/api/classes/1/knowledge/retrieve", json=payload)
    assert response.status_code == 400
    provider.assert_not_called()
    chat.assert_not_called()


def test_keyword_like_literals_and_empty_terms_never_call_models(app):
    with app.app_context():
        entry = add_entry("标记 token_100%\\path 只出现一次。")
        index_entry(entry)
        with patch("app.retrieval.embedding_client") as provider:
            hit = retrieve(class_id=1, query="token_100%\\path", mode="keyword")["hits"][0]
            empty = retrieve(class_id=1, query="的 了 吗", mode="keyword")
        assert hit["material_id"] == entry.material_id
        assert empty["hits"] == []
        provider.assert_not_called()


def test_equal_dimension_other_model_requires_reindex_but_keyword_and_empty_scope_work(app, client):
    login(client, "student_a1", "student-a-password")
    app.config["EMBEDDING_MODEL"] = "different-same64"
    with patch("app.retrieval.embedding_client") as provider:
        response = client.post("/api/classes/1/knowledge/retrieve", json={"query": "数学", "mode": "vector"})
        denied = client.post("/api/classes/1/knowledge/retrieve", json={"query": "数学", "mode": "hybrid", "subject_id": 99999})
        keyword = client.post("/api/classes/1/knowledge/retrieve", json={"query": "1 班数学示例材料内容", "mode": "keyword"})
    assert response.status_code == 503 and response.get_json()["code"] == "reindex_required"
    assert denied.status_code == 200 and denied.get_json()["hits"] == []
    assert keyword.status_code == 200 and keyword.get_json()["hits"]
    provider.assert_not_called()


def test_overlapping_windows_dedup_sentence_keep_distinct_useful_sentences(app):
    with app.app_context():
        text = "背景" * 40 + "细胞是生物体结构和功能的基本单位。" + "背景" * 70 + "细胞膜控制物质进出细胞。" + "背景" * 60
        entry = add_entry(text)
        index_entry(entry, {"strategy": "custom", "max_length": 100, "overlap_percent": 50, "separators": []})
        hits = [h for h in retrieve(class_id=1, query="细胞", mode="keyword", limit=20)["hits"] if h["material_id"] == entry.material_id]
        assert len(hits) == 2
        assert len({tuple(h["evidence_key"]) for h in hits}) == 2
        for hit in hits:
            assert len(hit["excerpt"]) <= 160
            assert text[hit["excerpt_start_offset"]:hit["excerpt_end_offset"]] == hit["excerpt"]


def test_preprocessed_long_url_excerpt_is_original_tail_not_joined_text(app):
    with app.app_context():
        source = "前言。访问 https://example.com/" + "x" * 600 + " 细胞结构功能在此说明。"
        entry = add_entry(source)
        index_entry(entry, {"strategy": "custom", "max_length": 100, "preprocess": {"remove_urls": True, "collapse_whitespace": True}})
        hit = retrieve(class_id=1, query="结构功能", mode="keyword")["hits"][0]
        assert hit["material_id"] == entry.material_id
        assert source[hit["excerpt_start_offset"]:hit["excerpt_end_offset"]] == hit["excerpt"]
        assert "结构功能" in hit["excerpt"] and "https://" not in hit["excerpt"] and len(hit["excerpt"]) <= 160
        assert len(hit["source_spans"]) > 1


def test_semantic_window_uses_cached_sentence_vectors_without_extra_requests(app):
    with app.app_context():
        source = "这是前言。果实成熟后会被采摘。生物体由细胞构成。"
        entry = add_entry(source)
        result = index_entry(entry)
        chunk = KnowledgeChunk.query.filter_by(generation_id=result["generation_id"]).one()
        KnowledgeEmbedding.query.filter_by(chunk_id=chunk.id).one().embedding = [1.] + [0.] * 63
        for sentence in KnowledgeChunkSentence.query.filter_by(chunk_id=chunk.id):
            KnowledgeSentenceEmbedding.query.filter_by(sentence_id=sentence.id).one().embedding = ([1., 0.] if "采摘" in sentence.text else [0., 1.]) + [0.] * 62
        db.session.commit()
        class QueryClient:
            calls = []
            def embed_batch(self, texts):
                self.calls.append(texts)
                return [[1.] + [0.] * 63 for _ in texts]
        client = QueryClient()
        with patch("app.retrieval.embedding_client", return_value=client):
            hits = retrieve(class_id=1, query="植物什么时候收获", mode="vector")["hits"]
        hit = next(h for h in hits if h["material_id"] == entry.material_id)
        assert hit["excerpt"] == "果实成熟后会被采摘。"
        assert client.calls == [["植物什么时候收获"]]


def test_vector_threshold_and_one_path_filtering(app):
    with app.app_context():
        low, high = add_entry("测试低相似度。"), add_entry("测试高相似度。")
        first, second = index_entry(low), index_entry(high)
        for result, score in [(first, .34), (second, .36)]:
            chunk = KnowledgeChunk.query.filter_by(generation_id=result["generation_id"]).one()
            KnowledgeEmbedding.query.filter_by(chunk_id=chunk.id).one().embedding = [score, math.sqrt(1 - score * score)] + [0.] * 62
            for sentence in KnowledgeChunkSentence.query.filter_by(chunk_id=chunk.id):
                KnowledgeSentenceEmbedding.query.filter_by(sentence_id=sentence.id).one().embedding = [score, math.sqrt(1-score*score)] + [0.]*62
        db.session.commit()
        ranked = _vector_ranked(1, "query", 100, vector=[1.] + [0.] * 63)
        identifiers = {c.material_id for c, _ in ranked}
        assert high.material_id in identifiers and low.material_id not in identifiers


def test_chunk_similarity_without_relevant_sentence_does_not_fill_results(app):
    with app.app_context():
        entry = add_entry('细胞是生物体的基本单位。背景学习资料。')
        result = index_entry(entry)
        chunk = KnowledgeChunk.query.filter_by(generation_id=result['generation_id']).one()
        KnowledgeEmbedding.query.filter_by(chunk_id=chunk.id).one().embedding = [1.] + [0.]*63
        for sentence in KnowledgeChunkSentence.query.filter_by(chunk_id=chunk.id):
            KnowledgeSentenceEmbedding.query.filter_by(sentence_id=sentence.id).one().embedding = [0.,1.]+[0.]*62
        db.session.commit()
        class QueryClient:
            def embed_batch(self, texts):
                return [[1.]+[0.]*63 for _ in texts]
        with patch('app.retrieval.embedding_client',return_value=QueryClient()):
            assert entry.material_id not in {h['material_id'] for h in retrieve(class_id=1,query='遥远星球的新问题',mode='hybrid')['hits']}
            assert entry.material_id in {h['material_id'] for h in retrieve(class_id=1,query='细胞是生物体的基本单位',mode='hybrid')['hits']}
