"""Configure the local main deployment; optionally run two authorized real turns.

Run from the repository root. Credentials remain in the ignored .env. This uses
normal authenticated HTTP APIs and never resets the database. --verify-real
creates two private acceptance conversations and calls the configured chat model.
"""
import argparse
import json
from pathlib import Path
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-real', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    env = {}
    for line in (root / '.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip().strip("'\"")
    accounts = json.loads(env['DEMO_ACCOUNT_PASSWORDS'])
    base = 'http://127.0.0.1:' + env.get('WEB_PORT', '5173')

    def request(method, path, body=None, token=None, stream=False):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body, ensure_ascii=False).encode(), headers=headers, method=method)
        try:
            response = urllib.request.urlopen(req, timeout=180)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'{method} {path}: HTTP {error.code}') from None
        if stream:
            events, name, data = [], None, []
            with response:
                for raw in response:
                    line = raw.decode('utf-8').rstrip('\r\n')
                    if line.startswith('event:'): name = line[6:].strip()
                    elif line.startswith('data:'): data.append(line[5:].strip())
                    elif not line and name and data:
                        events.append({'event': name, 'data': json.loads('\n'.join(data))})
                        name, data = None, []
            return events
        with response:
            return json.load(response)

    def login(username):
        return request('POST', '/api/auth/login', {'username': username, 'password': accounts[username]})

    report = {'date': '2026-10-27', 'environment': 'main-normal-runtime', 'servers': [], 'real_conversations': []}
    source = '名称：课堂工具解题引导\n适用条件：括号,公式,单位,换算,厘米,米\n工具：formula_hint@school,unit_convert@school\n启用：是\n\n需要检查去括号、公式或单位关系时，使用绑定的对应工具核对，再根据结果只给一个下一步检查和一个引导问题。不要给最终得数或完整解法，不要编造工具调用；工具不可用时说明情况。'
    for username in ('wangyuxin', 'hejiayi', 'taoyichen'):
        auth = login(username)
        token, class_id = auth['access_token'], auth['user']['class_id']
        class_base = f'/api/classes/{class_id}'
        servers = request('GET', class_base + '/mcp/servers', token=token)['items']
        server = next((row for row in servers if row['name'] == 'school'), None)
        if server is None:
            server = request('POST', class_base + '/mcp/servers', {'name': 'school', 'base_url': 'http://mcp-demo:8090', 'token': env['MCP_AUTH_TOKEN']}, token)['server']
        if server['base_url'] != 'http://mcp-demo:8090':
            raise RuntimeError('Existing school origin differs; preserve configuration')
        server = request('POST', class_base + f"/mcp/servers/{server['id']}/connect", {}, token)['server']
        tools = request('GET', class_base + f"/mcp/servers/{server['id']}/tools", token=token)['items']
        assert server['connected'] and {t['name'] for t in tools} == {'formula_hint', 'unit_convert'}
        assert all(t['permitted'] for t in tools)
        assert 'token' not in server and 'token_ciphertext' not in server
        confirmations = {tool['ref']: tool['declaration_hash'] for tool in tools}
        skills = request('GET', class_base + '/skills', token=token)['items']
        skill = next((row for row in skills if row['name'] == '课堂工具解题引导'), None)
        if skill and skill['source_text'] != source:
            raise RuntimeError('Existing classroom tool skill was edited; preserve it')
        skill = request('PUT' if skill else 'POST', class_base + '/skills' + (f"/{skill['id']}" if skill else ''), {'source_text': source, 'tool_confirmations': confirmations}, token)['skill']
        agents = request('GET', class_base + '/agents', token=token)['items']
        agent = next((row for row in agents if row['name'] == '课堂工具助手'), None)
        if agent is None:
            agent = request('POST', class_base + '/agents', {'name': '课堂工具助手', 'prompt': '你是课堂学习助手。需要公式或单位检查时依据绑定工具返回的提示进行单步引导，不给最终答案。不假装已经调用工具。', 'skill_ids': [skill['id']], 'material_ids': []}, token)['agent']
        assert not agent['material_ids'] and skill['id'] in agent['skill_ids']
        templates = request('GET', class_base + '/prompt-templates', token=token)['items']
        assert len(templates) == 6
        report['servers'].append({'class_id': class_id, 'server': server, 'tools': tools, 'skill_id': skill['id'], 'agent_id': agent['id'], 'agent_count': len(agents) + int(not any(row['id'] == agent['id'] for row in agents)), 'templates': len(templates)})
        print(f'Class {class_id}: server connected, two permitted declarations confirmed, tool agent ready.', flush=True)

    student = login('zhouchengxi')
    student_token, student_class = student['access_token'], student['user']['class_id']
    try:
        request('GET', f'/api/classes/{student_class}/mcp/servers', token=student_token)
        raise AssertionError('Student management access unexpectedly succeeded')
    except RuntimeError as error:
        assert 'HTTP 403' in str(error)
    report['student_management_denied'] = True

    if args.verify_real:
        agent_id = next(row['agent_id'] for row in report['servers'] if row['class_id'] == student_class)
        for kind, question, tool_name in [
            ('formula', '我把2-(3+x)写成2-3+x，请调用公式提示工具只检查去括号的符号，不要给出最终答案。', 'formula_hint'),
            ('unit', '5米换算厘米先看什么？请调用单位换算工具给一个提示，不要给出最终数值。', 'unit_convert'),
        ]:
            conversation = request('POST', '/api/conversations', {'agent_id': agent_id}, student_token)['conversation']
            events = request('POST', f"/api/conversations/{conversation['id']}/messages", {'question': question}, student_token, stream=True)
            text = ''.join(e['data']['text'] for e in events if e['event'] == 'delta')
            metas = [e['data'] for e in events if e['event'] == 'meta']
            outcomes = metas[-1].get('tool_calls', []) if metas else []
            history = request('GET', f"/api/conversations/{conversation['id']}", token=student_token)['messages']
            teacher = login('wangyuxin')
            audits = request('GET', f'/api/classes/{student_class}/mcp/tool-calls?limit=100', token=teacher['access_token'])['items']
            audits = [row for row in audits if row['conversation_id'] == conversation['id']]
            complete = bool(events and events[-1]['event'] == 'done')
            matched = [call for call in outcomes if call['status'] == 'ok' and call['ref'] == tool_name + '@school']
            stored = [row for row in history if row['role'] == 'assistant']
            passed = bool(complete and matched and stored and stored[-1]['content'] == text and stored[-1]['completion_state'] == 'complete' and {c['call_id'] for c in outcomes} == {a['call_id'] for a in audits} and all(not meta['citations'] for meta in metas))
            report['real_conversations'].append({'case': kind, 'conversation_id': conversation['id'], 'question': question, 'events': events, 'answer': text, 'history': history, 'audits': audits, 'passed': passed})
            print(f'{kind}: complete={complete}, successful_requested_tool={bool(matched)}, audit_and_history_match={passed}', flush=True)
    directory = root / 'docs/classroom-mcp-acceptance'
    directory.mkdir(exist_ok=True)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    for key in ('MCP_AUTH_TOKEN', 'MCP_TOKEN_ENCRYPTION_KEY', 'CHAT_API_KEY', 'EMBEDDING_API_KEY', 'AUTH_TOKEN_SECRET', 'SECRET_KEY'):
        if env.get(key):
            assert env[key] not in serialized, 'Private value would enter report'
    (directory / '2026-10-27.json').write_text(serialized + '\n', encoding='utf-8')
    if args.verify_real:
        assert len(report['real_conversations']) == 2 and all(row['passed'] for row in report['real_conversations']), 'See saved real-conversation failures'


if __name__ == '__main__':
    main()
