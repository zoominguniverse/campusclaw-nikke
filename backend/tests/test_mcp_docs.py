from pathlib import Path
import importlib.util
import pytest
from app.tutor_skills import parse_skill

def test_mcp_openapi_contract_and_sample(client):
    document = client.get('/openapi.json').json
    paths = document['paths']
    base = '/api/classes/{class_id}/mcp/servers'
    assert paths[base]['post']['requestBody']['content']['application/json']['schema']['properties']['token']['writeOnly']
    assert all('token' not in key for key in document['components']['schemas']['MCPServer']['properties'] if key != 'has_token')
    assert set(paths[base + '/{server_id}/connect']['post']['responses']) == {'200', '400', '401', '403', '404', '502'}
    meta = paths['/api/conversations/{conversation_id}/messages']['post']['x-sse-events']['meta']
    assert 'tool_calls' in meta['properties'] and 'tool_calls' not in meta['required']
    assert 'tool_calls' in document['components']['schemas']['Message']['properties']
    assert parse_skill((Path(__file__).parents[1] / 'tutor_samples/mcp-hints.txt').read_text(encoding='utf-8'))['tools_json'] == ['knowledge_search', 'formula_hint@school', 'unit_convert@school']

@pytest.mark.parametrize('base,database', [('http://localhost:5174','postgresql://mcp_readonly:p@localhost:5548/mcp_test'), ('http://localhost:5284','postgresql://mcp_test:p@mcp-postgres:5432/mcp_test'), ('http://localhost:5284','postgresql://mcp_readonly:p@postgres:5432/campusclaw')])
def test_runner_rejects_development_targets_before_http(monkeypatch, base, database):
    path = Path(__file__).parents[2] / 'apitest/helpers.py'
    if not path.exists(): pytest.skip('apitest source is not mounted')
    spec = importlib.util.spec_from_file_location('mcp_apitest_helpers', path)
    helpers = importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)
    monkeypatch.setenv('MCP_DISPOSABLE_DATABASE','true'); monkeypatch.setenv('TUTOR_DISPOSABLE_DATABASE','true')
    monkeypatch.setenv('TUTOR_TEST_BASE_URL',base); monkeypatch.setenv('TUTOR_TEST_DATABASE_URL',database)
    monkeypatch.setattr(helpers.requests, 'get', lambda *a, **kw: pytest.fail('preflight contacted forbidden target'))
    with pytest.raises(AssertionError): helpers.Context().preflight()
