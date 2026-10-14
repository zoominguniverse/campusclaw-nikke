"""All 20 frozen permission scenarios through seven authenticated HTTP paths."""
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest

from app.database import db
from app.models import ClassMembership, ClassSubject, KnowledgeChunk, Material, TeacherSubjectAssignment, User
from app.providers import DeterministicChatClient
from evaluation.run import load_fixture
from .conftest import BearerClient, _test_hash_password, login
from .test_postgres_integration import postgres_app


@pytest.mark.skipif(not os.getenv('POSTGRES_INTEGRATION_URL'), reason='isolated PostgreSQL is required')
def test_twenty_permission_cases_all_seven_paths(postgres_app):
    corpus = json.loads((Path(__file__).parents[1] / 'evaluation/corpus-v1.json').read_text(encoding='utf-8'))
    postgres_app.test_client_class = BearerClient
    results = []
    with postgres_app.app_context():
        classes, subjects = load_fixture(corpus)
        for case in (c for c in corpus['cases'] if c['category'] == 'permission'):
            class_id, role = classes[case['scope']['class']], case['actor_role']
            authorized = []
            for key in case['scope']['subjects']:
                if (case['scope']['class'], key) not in subjects:
                    subject = ClassSubject(class_id=class_id, subject_key=key, name=key, normalized_name=key, status='active')
                    db.session.add(subject); db.session.flush()
                    subjects[(case['scope']['class'], key)] = subject.id
                authorized.append(subjects[(case['scope']['class'], key)])
            actor = User(username=f"quality-{case['id']}", password_hash=_test_hash_password('isolated-only-password'), role=role, class_id=class_id, is_active=True)
            db.session.add(actor); db.session.flush()
            db.session.add(ClassMembership(user_id=actor.id, class_id=class_id, is_teacher=role == 'teacher'))
            if role == 'teacher':
                for subject in authorized:
                    db.session.add(TeacherSubjectAssignment(teacher_id=actor.id, subject_id=subject, is_active=True))
            db.session.commit()
            client = postgres_app.test_client(); login(client, actor.username, 'isolated-only-password')
            denied_id = case['denied_materials'][0]
            denied = db.session.get(Material, denied_id)
            chunk = KnowledgeChunk.query.filter_by(material_id=denied_id, searchable_active=True).first()
            # Request the denied class and subject directly to test server-derived scope.
            for mode in ['keyword', 'vector', 'hybrid']:
                with patch('app.retrieval.embedding_client') as provider:
                    response = client.post(f'/api/classes/{denied.class_id}/knowledge/retrieve', json={'query': case['query'], 'mode': mode, 'subject_id': denied.subject_id})
                assert response.status_code == 200 and response.get_json()['hits'] == []
                assert response.get_json()['message'] == '资料中未找到相关内容'
                provider.assert_not_called()
                assert 'code' not in response.get_json()
                results.append({'case_id': case['id'], 'mode': mode, 'status': 'ok', 'leak_count': 0, 'http_status': response.status_code})
            with patch('app.answers.chat_client') as provider:
                response = client.post(f'/api/classes/{denied.class_id}/knowledge/ask', json={'question': case['query'], 'subject_id': denied.subject_id})
            assert response.status_code == 200 and response.get_json()['status'] == 'no_evidence' and response.get_json()['citations'] == []
            provider.assert_not_called()
            results.append({'case_id': case['id'], 'mode': 'ask', 'status': 'ok', 'leak_count': 0, 'http_status': 200})
            paths = {'detail': (f'/knowledge/chunks/{chunk.id}', 'GET', None), 'preview': (f'/materials/{denied_id}/chunk-preview', 'POST', {}), 'retry': (f'/materials/{denied_id}/reindex', 'POST', {})}
            for mode, (path, method, payload) in paths.items():
                with patch('app.indexing.embedding_client') as provider:
                    response = client.open(f'/api/classes/{denied.class_id}{path}', method=method, json=payload)
                assert response.status_code in {403, 404}
                assert set(response.get_json()) == {'error'}
                assert denied_id not in response.get_data(as_text=True) and case['query'] not in response.get_data(as_text=True)
                provider.assert_not_called()
                results.append({'case_id': case['id'], 'mode': mode, 'status': 'ok', 'leak_count': 0, 'http_status': response.status_code})
    assert len(results) == 140
    target = Path('/quality-results')
    if target.is_dir():
        (target / 'permission-results.json').write_text(json.dumps({'cases': 20, 'paths': 140, 'leaks': 0, 'provider': 'structural-demo-only', 'results': results}, indent=2) + '\n', encoding='utf-8')


def test_permission_revoked_during_chat_does_not_return_citations(app, client):
    from .test_structured_answers import fixture_hits, claim
    login(client, 'teacher_a', 'teacher-password')
    with app.app_context():
        _, hits = fixture_hits()
        actor_id = User.query.filter_by(username='linzimo').one().id
    def revoke(question, evidence, history):
        TeacherSubjectAssignment.query.filter_by(teacher_id=actor_id, subject_id=hits[0]['subject_id']).update({'is_active': False})
        db.session.commit()
        return {'status': 'answered', 'claims': [claim(hits)]}
    with patch('app.answers.retrieve', return_value={'hits': hits}), patch('app.answers.chat_client') as factory:
        factory.return_value.answer.side_effect = revoke
        response = client.post('/api/classes/1/knowledge/ask', json={'question': '基本单位'})
    assert response.status_code == 403
    assert set(response.get_json()) == {'error'}
