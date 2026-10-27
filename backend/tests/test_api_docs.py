import pytest
from flask import Flask

from app.api_docs import api_doc, generate_document


def test_document_is_handler_generated_and_bearer_accurate(app, client):
    document = client.get('/openapi.json').get_json()
    paths = document['paths']
    assert '/api/auth/login' in paths and '/api/login' not in paths
    assert paths['/api/auth/login']['post']['security'] == []
    assert paths['/api/auth/me']['get']['security'] == [{'BearerAuth': []}]
    assert 'bearerFormat' not in document['components']['securitySchemes']['BearerAuth']
    assert paths['/api/classes/{class_id}/materials']['post']['x-role'] == 'teacher'
    assert paths['/api/classes/{class_id}/materials/{material_id}']['get']['parameters'][0]['schema']['type'] == 'integer'
    assert client.get('/swagger/').status_code == client.get('/swagger/index.html').status_code == 200
    generate_document(app, ['auth_login', 'knowledge_retrieve', 'knowledge_ask'])
    with pytest.raises(ValueError, match='missing API documentation'):
        generate_document(app, ['undocumented'])


def test_generator_rejects_duplicate_ids_and_invalid_schema():
    app = Flask('duplicate')
    app.add_url_rule('/one', 'one', api_doc('duplicate', 'one')(lambda: 'one'))
    app.add_url_rule('/two', 'two', api_doc('duplicate', 'two')(lambda: 'two'))
    with pytest.raises(ValueError, match='duplicate operationId'):
        generate_document(app)
    broken = Flask('schema')
    broken.add_url_rule('/bad', 'bad', api_doc('bad', 'bad', body={'type': 'array'})(lambda: 'bad'), methods=['POST'])
    with pytest.raises(ValueError, match='array schema needs items'):
        generate_document(broken)
