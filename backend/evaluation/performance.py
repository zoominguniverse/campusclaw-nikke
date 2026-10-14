"""Provider-aware benchmark confined to a disposable PostgreSQL fixture."""
import argparse
import json
import os
from pathlib import Path
import platform
import time
from unittest.mock import patch
from sqlalchemy import event, text
from sqlalchemy.engine import make_url

def run_benchmark(app, output_path, *, reuse_fixture=False):
    url = make_url(app.config['SQLALCHEMY_DATABASE_URI'])
    if os.getenv('QUALITY_DISPOSABLE_DATABASE') != 'true' or url.get_backend_name() != 'postgresql' or not (url.database or '').startswith('quality_'):
        raise ValueError('benchmark requires a disposable quality_* PostgreSQL database')
    from app.database import db
    from app.indexing import index_entry
    from app.models import ClassSubject, SchoolClass, KnowledgeEntry, KnowledgeChunk, Material, User, Role
    from app.providers import embedding_client, chat_client
    from app.retrieval import retrieve, _vector_ranked
    from app.answers import answer_question
    from evaluation.report import percentile

    with app.app_context():
        owner = User.query.first(); scopes = []
        for number in range(20):
            if reuse_fixture:
                school_class = SchoolClass.query.filter_by(code=f'PERF-{number}').one()
                subject = ClassSubject.query.filter_by(class_id=school_class.id,subject_key='perf').one()
                entry = KnowledgeEntry.query.filter_by(class_id=school_class.id,subject_id=subject.id).one()
                expected = ''.join((f'范围{number}性能片{index}细胞结构功能单位' + '背景' * 60)[:98] + '。\n' for index in range(500))
                assert entry.body_text == expected
                assert KnowledgeChunk.query.filter_by(knowledge_entry_id=entry.id,searchable_active=True,index_status='ready').count()==500
                from app.retrieval import _ensure_compatible
                _ensure_compatible(school_class.id,{subject.id})
                scopes.append((school_class.id,subject.id,number))
                continue
            school_class = SchoolClass(code=f'PERF-{number}', name=f'performance-{number}')
            db.session.add(school_class); db.session.flush()
            if owner is None:
                if not db.session.get(Role, 'teacher'):
                    db.session.add(Role(name='teacher')); db.session.flush()
                owner = User(username='performance-fixture-owner', password_hash='disabled-fixture-login', role='teacher', class_id=school_class.id, is_active=False)
                db.session.add(owner); db.session.flush()
            subject = ClassSubject(class_id=school_class.id, subject_key='perf', name='performance', normalized_name='performance', status='active')
            db.session.add(subject); db.session.flush()
            material = Material(class_id=school_class.id, subject_id=subject.id, uploader_id=owner.id, title=f'performance-{number}', original_filename='performance.md', storage_path='seeded', content_type='text/plain')
            db.session.add(material); db.session.flush()
            # 500 paragraphs of exactly 99 code points + newline, one chunk each.
            body = ''.join((f'范围{number}性能片{index}细胞结构功能单位' + '背景' * 60)[:98] + '。\n' for index in range(500))
            entry = KnowledgeEntry(class_id=school_class.id, subject_id=subject.id, material_id=material.id, body_text=body)
            db.session.add(entry); db.session.commit()
            output = index_entry(entry, {'strategy': 'custom', 'max_length': 100, 'overlap_percent': 0})
            assert output['status'] == 'ready'
            assert KnowledgeChunk.query.filter_by(generation_id=output['generation_id'], searchable_active=True).count() == 500
            scopes.append((school_class.id, subject.id, number))
        assert KnowledgeChunk.query.filter(KnowledgeChunk.class_id.in_([s[0] for s in scopes]), KnowledgeChunk.searchable_active.is_(True)).count() == 10000
        db.session.execute(text('ANALYZE')); db.session.commit()
        elapsed = {'db': 0., 'embedding': 0., 'chat': 0.}; sql_samples = {}
        def before(conn, cursor, statement, parameters, context, many):
            context.quality_start = time.perf_counter()
            if '<=>' in statement and 'knowledge_embeddings' in statement and 'vector' not in sql_samples:
                sql_samples['vector'] = (statement, parameters)
            if '@@' in statement and 'keyword' not in sql_samples:
                sql_samples['keyword'] = (statement, parameters)
        def after(conn, cursor, statement, parameters, context, many):
            elapsed['db'] += (time.perf_counter() - context.quality_start) * 1000
        class TimedEmbedding:
            def __init__(self):
                self.client = embedding_client()
            def embed_batch(self, values):
                start = time.perf_counter()
                try:
                    result = self.client.embed_batch(values)
                    return result
                finally:
                    elapsed['embedding'] += (time.perf_counter() - start) * 1000
        class TimedChat:
            def __init__(self):
                self.client = chat_client()
            def answer(self, *args, **kwargs):
                start = time.perf_counter()
                try:
                    return self.client.answer(*args, **kwargs)
                finally:
                    elapsed['chat'] += (time.perf_counter() - start) * 1000
        timed_embedding, timed_chat = TimedEmbedding(), TimedChat()
        captured = {}
        def capture_vector(class_id, query, limit, subject_ids=None, vector=None):
            captured['vector'] = vector
            return _vector_ranked(class_id, query, limit, subject_ids, vector)
        event.listen(db.engine, 'before_cursor_execute', before); event.listen(db.engine, 'after_cursor_execute', after)
        measurements, comparisons = [], []
        try:
            with patch('app.retrieval.embedding_client', return_value=timed_embedding), patch('app.answers.chat_client', return_value=timed_chat), patch('app.retrieval._vector_ranked', side_effect=capture_vector):
                for mode in ['keyword', 'vector', 'hybrid', 'ask']:
                    for ordinal in range(120):
                        class_id, subject_id, number = scopes[ordinal % 20]
                        question = (f'范围{number}性能片{ordinal % 500}细胞结构功能单位' + '背景' * 60)[:98] + '。'
                        for stage in elapsed: elapsed[stage] = 0.
                        start = time.perf_counter()
                        result = answer_question(class_id=class_id, subject_ids={subject_id}, question=question) if mode == 'ask' else retrieve(class_id=class_id, subject_ids={subject_id}, query=question, mode=mode, limit=10)
                        total = (time.perf_counter() - start) * 1000
                        if ordinal >= 20:
                            measurements.append({'mode': mode, 'scope': number, 'latency_ms': {**elapsed, 'total': total}})
                        if mode == 'vector' and 20 <= ordinal < 70:
                            vector = captured['vector']
                            literal = '[' + ','.join(map(str, vector)) + ']'
                            from app.profiles import current_profile
                            cprofile = current_profile()
                            exact = list(db.session.execute(text('SELECT c.id FROM knowledge_chunks c JOIN knowledge_embeddings e ON e.chunk_id=c.id JOIN knowledge_index_generations g ON g.id=c.generation_id WHERE c.class_id=:class_id AND c.subject_id=:subject_id AND c.searchable_active AND g.is_current AND e.is_active AND e.state=\'ready\' AND e.profile_id=g.profile_id AND e.profile_id=:profile_id AND e.dimensions=:dimensions AND g.status=\'ready\' AND c.index_status=\'ready\' AND EXISTS (SELECT 1 FROM knowledge_chunk_sentences s JOIN knowledge_sentence_embeddings se ON se.sentence_id=s.id WHERE s.chunk_id=c.id AND s.generation_id=c.generation_id AND se.profile_id=e.profile_id AND se.dimensions=e.dimensions AND se.is_active AND se.state=\'ready\' AND 1-(se.embedding <=> CAST(:vector AS vector))>=:threshold) AND 1-(e.embedding <=> CAST(:vector AS vector))>=:threshold ORDER BY e.embedding <=> CAST(:vector AS vector), c.id LIMIT 10'), {'class_id': class_id, 'subject_id': subject_id, 'vector': literal, 'profile_id': cprofile.id, 'dimensions': app.config['EMBEDDING_DIMENSIONS'], 'threshold': app.config['VECTOR_THRESHOLD']}).scalars())
                            actual = [hit['chunk_id'] for hit in result['hits']]
                            assert len(exact) == 10
                            assert actual == exact
                            comparisons.append({'scope': number, 'query_number': ordinal, 'recall10': len(set(actual) & set(exact)) / len(exact)})
        finally:
            event.remove(db.engine, 'before_cursor_execute', before); event.remove(db.engine, 'after_cursor_execute', after)
        summaries = {}
        for mode in ['keyword', 'vector', 'hybrid', 'ask']:
            rows = [r for r in measurements if r['mode'] == mode]
            assert len(rows) == 100
            summaries[mode] = {stage: percentile([r['latency_ms'][stage] for r in rows], .95) for stage in elapsed | {'total': 0}}
            assert summaries[mode]['db'] <= 300
        assert len(comparisons) == 50
        plans = {}
        raw = db.engine.raw_connection()
        try:
            with raw.cursor() as cursor:
                for mode, (statement, parameters) in sql_samples.items():
                    cursor.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + statement, parameters)
                    plans[mode] = cursor.fetchone()[0]
        finally:
            raw.close()
        cpu = next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), platform.processor())
        from app.profiles import profile_identity, PROCESSING_VERSION
        from app.retrieval import RETRIEVAL_VERSION
        from app.providers import CHAT_PROMPT_VERSION
        report = {'profile_fingerprint': profile_identity()['fingerprint'], 'processing_version': PROCESSING_VERSION,
                  'retrieval_version': RETRIEVAL_VERSION, 'chat_prompt_version': CHAT_PROMPT_VERSION, 'reused_verified_fixture': reuse_fixture,
                  'active_chunks': 10000, 'scopes': 20, 'warmup_per_path': 20, 'measured_per_path': 100, 'exact_comparison_queries': 50, 'ann_enabled': False, 'recall10': 1.0,
                  'embedding_provider': app.config['EMBEDDING_PROVIDER'], 'embedding_model': app.config['EMBEDDING_MODEL'], 'embedding_revision': app.config['EMBEDDING_REVISION'], 'chat_provider': app.config['CHAT_PROVIDER'], 'chat_model': app.config['CHAT_MODEL'],
                  'dimensions': app.config['EMBEDDING_DIMENSIONS'], 'vector_threshold': app.config['VECTOR_THRESHOLD'],
                  'real_profile_gate': 'passed' if all(app.config[key] == 'openai-compatible' for key in ['EMBEDDING_PROVIDER', 'CHAT_PROVIDER']) else 'incomplete', 'semantic_release_passed': False,
                  'hardware': {'platform': platform.platform(), 'cpu': cpu, 'logical_cpus': os.cpu_count(), 'memory_bytes': os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')},
                  'extensions': dict(db.session.execute(text("SELECT extname,extversion FROM pg_extension WHERE extname IN ('vector','pg_trgm')")).all()), 'postgres': db.session.execute(text('SHOW server_version')).scalar(),
                  'stage_p95_ms': summaries, 'measurements': measurements, 'exact_comparisons': comparisons, 'plans': plans}
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-demo', action='store_true')
    parser.add_argument('--reuse-fixture', action='store_true', help='Verify and reuse this disposable benchmark dataset without re-embedding it')
    args = parser.parse_args()
    url = make_url(os.getenv('DATABASE_URL', 'sqlite://'))
    if os.getenv('QUALITY_DISPOSABLE_DATABASE') != 'true' or url.get_backend_name() != 'postgresql' or not (url.database or '').startswith('quality_'):
        parser.error('requires an explicitly disposable quality_* PostgreSQL database')
    from app import create_app
    from app.database import initialize_database
    from app.models import SchoolClass
    app = create_app({'INITIALIZE_DATABASE': False, 'SEED_DEMO_DATA': False})
    real = all(app.config[key] == 'openai-compatible' for key in ['EMBEDDING_PROVIDER', 'CHAT_PROVIDER'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not real and not args.allow_demo:
        args.output.write_text(json.dumps({'real_profile_gate': 'incomplete', 'reason': 'real_provider_required', 'semantic_release_passed': False}) + '\n', encoding='utf-8')
        return 2
    with app.app_context():
        initialize_database()
        if not args.reuse_fixture and SchoolClass.query.filter(SchoolClass.code.like('PERF-%')).first():
            parser.error('requires a fresh disposable performance database; use its dedicated Compose project')
        try:
            run_benchmark(app, args.output, reuse_fixture=args.reuse_fixture)
        except Exception as error:
            # Never expose provider payloads, SQL parameters or environment values.
            args.output.write_text(json.dumps({'real_profile_gate': 'incomplete', 'reason': 'benchmark_failed', 'error_type': type(error).__name__, 'semantic_release_passed': False}) + '\n', encoding='utf-8')
            return 2
    return 0 if real else 2


if __name__ == '__main__':
    raise SystemExit(main())
