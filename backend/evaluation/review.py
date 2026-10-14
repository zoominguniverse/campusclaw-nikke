"""Export human claim review; import decisions bound to the exact case output."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

DECISIONS = {'pending', 'supported', 'unsupported', 'ambiguous'}
ANNOTATIONS = {'human_review', 'unsupported_claims', 'claim_reviews', 'response_review', 'reviewer'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def export_review(data, corpus, split='release'):
    if split not in {'dev', 'release'}:
        raise ValueError('unsupported review split')
    records = {(row['case_id'], row['mode']): row for row in data['results']}
    if len(records) != len(data['results']):
        raise ValueError('duplicate result case/mode')
    items = []
    for case in corpus['cases']:
        if case['split'] != split or case['category'] not in {'answer', 'adversarial'}:
            continue
        row = records.get((case['id'], 'ask'), {})
        claims = row.get('claims', [])
        items.append({'case_id': case['id'], 'category': case['category'], 'question': case['query'],
                      'reference_fact': case['reference_fact'], 'expected_status': case['expected_status'],
                      'run_status': row.get('status', 'incomplete'), 'answer': row.get('answer', ''),
                      'citations': row.get('citations', []), 'claims': claims,
                      'result_hash': digest({key: value for key, value in row.items() if key not in ANNOTATIONS}),
                      'response_review': {'status': 'pending', 'note': ''},
                      'claim_reviews': [{'status': 'pending', 'note': ''} for _ in claims]})
    return {'corpus_hash': digest(corpus), 'profile_fingerprint': data['metadata'].get('profile_fingerprint'),
            'split': split, 'reviewer': '', 'items': items}


def apply_review(data, corpus, review):
    expected = export_review(data, corpus, review['split'])
    for field in ['corpus_hash', 'profile_fingerprint', 'split']:
        if review.get(field) != expected[field]:
            raise ValueError('review belongs to a different corpus/profile')
    if not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip():
        raise ValueError('human reviewer name is required')
    items = {item['case_id']: item for item in review['items']}
    if len(items) != len(review['items']) or set(items) != {item['case_id'] for item in expected['items']}:
        raise ValueError('missing or duplicate review cases')
    result = copy.deepcopy(data)
    records = {(row['case_id'], row['mode']): row for row in result['results']}
    for item in expected['items']:
        reviewed = items[item['case_id']]
        for field in set(item) - {'response_review', 'claim_reviews'}:
            if reviewed.get(field) != item[field]:
                raise ValueError('review case output changed; export a fresh review')
        decisions = [reviewed['response_review'], *reviewed['claim_reviews']]
        if len(reviewed['claim_reviews']) != len(item['claims']):
            raise ValueError('every claim needs its own review')
        for decision in decisions:
            if decision.get('status') not in DECISIONS or not isinstance(decision.get('note'), str):
                raise ValueError('invalid review decision')
            if decision['status'] != 'pending' and not decision['note'].strip():
                raise ValueError('completed reviews require an explanation')
        row = records.get((item['case_id'], 'ask'))
        if not row:
            continue
        complete = row.get('status') == 'ok' and row.get('demo_mode') is False and all(d['status'] == 'supported' for d in decisions)
        if row.get('answer_status') == 'answered' and not item['claims']:
            complete = False  # Older result files do not contain a claim breakdown.
        row.update(reviewer=review['reviewer'], response_review=reviewed['response_review'], claim_reviews=reviewed['claim_reviews'],
                   human_review='supported' if complete else 'pending',
                   unsupported_claims=sum(d['status'] == 'unsupported' for d in reviewed['claim_reviews']))
    return result


def review_complete(row):
    def supported(decision):
        return isinstance(decision, dict) and decision.get('status') == 'supported' and isinstance(decision.get('note'), str) and bool(decision['note'].strip())
    claims, reviews = row.get('claims', []), row.get('claim_reviews')
    return (isinstance(row.get('reviewer'), str) and bool(row['reviewer'].strip())
            and isinstance(claims, list) and isinstance(reviews, list) and len(claims) == len(reviews)
            and (row.get('answer_status') != 'answered' or bool(claims))
            and supported(row.get('response_review')) and all(supported(review) for review in reviews))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--corpus', type=Path, default=Path(__file__).with_name('corpus-v1.json'))
    parser.add_argument('--split', choices=['dev', 'release'], default='release')
    parser.add_argument('--reviews', type=Path, help='Import completed human decisions instead of exporting pending ones')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.results.read_text(encoding='utf-8'))
    corpus = json.loads(args.corpus.read_text(encoding='utf-8'))
    result = apply_review(data, corpus, json.loads(args.reviews.read_text(encoding='utf-8'))) if args.reviews else export_review(data, corpus, args.split)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
