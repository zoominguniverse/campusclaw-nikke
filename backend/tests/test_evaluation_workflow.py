"""Contract/report tooling tests; simulated providers never certify quality."""
import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from evaluation.preflight import check_providers
from evaluation.review import export_review, apply_review, review_complete
from evaluation.report import summarize
from app.providers import ProviderUnavailable


def test_preflight_demo_never_calls_providers(app):
    with app.app_context(), patch('app.providers.embedding_client') as embedding, patch('app.providers.chat_client') as chat:
        result = check_providers()
    assert not result['provider_contract_passed'] and not result['semantic_release_passed']
    assert all(item['status'] == 'incomplete' for item in result['checks'].values())
    embedding.assert_not_called(); chat.assert_not_called()


def test_preflight_simulated_contract_and_error_redaction(app):
    app.config.update(EMBEDDING_PROVIDER='openai-compatible', EMBEDDING_DIMENSIONS=2, EMBEDDING_API_URL='https://embedding.example/v1', EMBEDDING_API_KEY='never-print-embedding-key', CHAT_PROVIDER='openai-compatible', CHAT_API_URL='https://chat.example/v1', CHAT_API_KEY='never-print-chat-key')
    def answer(question, evidence, history):
        return {'status': 'answered', 'claims': [{'text': '细胞是基本单位。', 'evidence': [{'index': 1, 'quote': evidence[0]['excerpt']}]}]}
    with app.app_context(), patch('app.providers.embedding_client') as embedding, patch('app.providers.chat_client') as chat:
        embedding.return_value.embed_batch.side_effect = lambda texts: [[1., 0.] for _ in texts]
        chat.return_value.answer.side_effect = answer
        result = check_providers()
        assert result['provider_contract_passed'] and not result['semantic_release_passed']
        assert [len(call.args[0]) for call in embedding.return_value.embed_batch.call_args_list] == [2, 1]
        assert result['checks']['chat']['human_review'] == 'pending'
        embedding.return_value.embed_batch.side_effect = ProviderUnavailable('never-print-embedding-key')
        chat.return_value.answer.side_effect = lambda *args: {'status': 'answered', 'claims': []}
        failed = check_providers()
    assert all(item['status'] == 'failed' for item in failed['checks'].values())
    for report in [result, failed]:
        encoded = json.dumps(report)
        assert 'never-print-embedding-key' not in encoded and 'never-print-chat-key' not in encoded


def review_fixture():
    corpus = json.loads((Path(__file__).parents[1] / 'evaluation/corpus-v1.json').read_text(encoding='utf-8'))
    case = next(case for case in corpus['cases'] if case['category'] == 'answer' and case['split'] == 'release')
    row = {'case_id': case['id'], 'mode': 'ask', 'status': 'ok', 'demo_mode': False, 'answer_status': 'answered',
           'answer': '有依据[1]\n另一事实[1]', 'citations': [{'quotes': [{'text': '原文', 'source_span': {'start': 0, 'end': 2}}]}],
           'claims': [{'text': '有依据', 'evidence': [{'index': 1, 'quote': '原文'}]}, {'text': '另一事实', 'evidence': [{'index': 1, 'quote': '原文'}]}]}
    data = {'metadata': {'profile_fingerprint': 'synthetic-test-only'}, 'results': [row]}
    return corpus, data


def test_each_claim_review_is_required_and_bound_to_unchanged_output():
    corpus, data = review_fixture()
    review = export_review(data, corpus)
    review['reviewer'] = '测试审阅记录（仅测试工具逻辑）'
    item = next(item for item in review['items'] if item['run_status'] == 'ok')
    item['response_review'] = {'status': 'supported', 'note': '工具测试说明'}
    item['claim_reviews'][0] = {'status': 'supported', 'note': '工具测试说明'}
    partial = apply_review(data, corpus, review)['results'][0]
    assert partial['human_review'] == 'pending' and not review_complete(partial)
    item['claim_reviews'][1] = {'status': 'supported', 'note': '工具测试说明'}
    complete = apply_review(data, corpus, review)['results'][0]
    assert complete['human_review'] == 'supported' and review_complete(complete)
    for field in ['answer', 'claims', 'citations']:
        changed = copy.deepcopy(data); changed['results'][0][field] = [] if field != 'answer' else '改写的回答'
        with pytest.raises(ValueError, match='changed'):
            apply_review(changed, corpus, review)
    review['profile_fingerprint'] = 'other-model'
    with pytest.raises(ValueError, match='different'):
        apply_review(data, corpus, review)
    assert data['results'][0].get('human_review') is None


def test_demo_and_missing_case_cannot_be_certified_by_review():
    corpus, data = review_fixture()
    data['results'][0]['demo_mode'] = True
    review = export_review(data, corpus); review['reviewer'] = '测试审阅人'
    for item in review['items']:
        item['response_review'] = {'status': 'supported', 'note': '工具测试'}
        for decision in item['claim_reviews']:
            decision.update(status='supported', note='工具测试')
    assert apply_review(data, corpus, review)['results'][0]['human_review'] == 'pending'
    missing = {'metadata': data['metadata'], 'results': []}
    empty_review = export_review(missing, corpus); empty_review['reviewer'] = '测试审阅人'
    assert apply_review(missing, corpus, empty_review)['results'] == []
    forged = copy.deepcopy(data); forged['results'][0].update(human_review='supported', unsupported_claims=0, demo_mode=False)
    report = summarize(corpus, forged['results'], forged['metadata'])
    assert {'case_id': data['results'][0]['case_id'], 'mode': 'ask'} in report['required_reviews_incomplete']
