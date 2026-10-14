"""Small provider contract checks; no source/database changes or quality claim."""
import argparse
import json
from pathlib import Path
import platform
import time
from urllib.parse import urlsplit

from flask import current_app


def check_providers():
    from app.answers import _validate_output, AnswerValidationError
    from app.providers import embedding_client, chat_client, embed_validated, ProviderUnavailable
    from app.profiles import profile_identity, PROCESSING_VERSION
    config = current_app.config
    metadata = {**profile_identity(), 'processing_version': PROCESSING_VERSION,
                'chat_provider': config['CHAT_PROVIDER'], 'chat_model': config['CHAT_MODEL'],
                'hardware': platform.platform(),
                'embedding_endpoint_host': urlsplit(config['EMBEDDING_API_URL']).hostname,
                'chat_endpoint_host': urlsplit(config['CHAT_API_URL']).hostname}
    checks = {}
    for prefix in ['EMBEDDING', 'CHAT']:
        stage = prefix.lower()
        if config[prefix + '_PROVIDER'] != 'openai-compatible':
            checks[stage] = {'status': 'incomplete', 'reason': 'real_provider_required'}
            continue
        started = time.perf_counter()
        try:
            if prefix == 'EMBEDDING':
                vectors = embed_validated(embedding_client(), ['细胞是生物体结构和功能的基本单位。', '光在均匀介质中沿直线传播。'])
                # Use the same query contract as retrieval; never store vectors.
                query = embed_validated(embedding_client(), ['生物体由什么基本单位构成？'])
                checks[stage] = {'status': 'passed', 'batch_items': len(vectors), 'query_items': len(query),
                                 'dimensions': config['EMBEDDING_DIMENSIONS']}
            else:
                quote = '细胞是生物体结构和功能的基本单位。'
                evidence = [{'evidence_index': 1, 'subject_name': '生物', 'material_title': '公开构造的连通性样本',
                             'excerpt': quote, 'source_segments': [{'start': 0, 'end': len(quote), 'text': quote}]}]
                value = _validate_output(chat_client().answer('生物体结构和功能的基本单位是什么？', evidence, []), evidence)
                checks[stage] = {'status': 'passed' if value['status'] == 'answered' else 'failed',
                                 'answer_status': value['status'], 'claims': value['claims'], 'human_review': 'pending'}
        except (ProviderUnavailable, AnswerValidationError):
            checks[stage] = {'status': 'failed', 'reason': 'provider_or_response_unavailable'}
        checks[stage]['latency_ms'] = (time.perf_counter() - started) * 1000
    return {'metadata': metadata, 'checks': checks,
            'provider_contract_passed': all(item['status'] == 'passed' for item in checks.values()),
            'semantic_release_passed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from app import create_app
    try:
        app = create_app({'INITIALIZE_DATABASE': False, 'SEED_DEMO_DATA': False})
        with app.app_context():
            result = check_providers()
    except (RuntimeError, ValueError):
        result = {'provider_contract_passed': False, 'reason': 'configuration_incomplete', 'semantic_release_passed': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Provider contract:', 'passed' if result['provider_contract_passed'] else 'incomplete or failed')
    return 0 if result['provider_contract_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
