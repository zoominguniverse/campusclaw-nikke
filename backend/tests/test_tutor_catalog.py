import pytest
from app.extensions import db
from app.models import TutorAgent, TutorAgentMaterial, TutorAgentSkill
from app.tutor_catalog import TEMPLATES, NEW_APPLICATION_IDS, render_template_prompt
from app.tutor_seed import seed_tutor_data
from .conftest import login


def test_catalog_teacher_only_and_render_does_not_save(client, app):
    base = '/api/classes/1/prompt-templates'
    assert client.get(base).status_code == 401
    login(client, 'student_a1', 'student-a-password')
    assert client.get(base).status_code == 403
    assert client.post(base+'/lesson-plan/render', json={}).status_code == 403
    login(client, 'teacher_a', 'teacher-password')
    assert len(client.get(base).json['items']) == 6
    with app.app_context():
        before = TutorAgent.query.count()
    response = client.post(base+'/lesson-plan/render', json={'variables': {'subject': '数学', 'topic': '分数', 'minutes': '35'}})
    assert response.status_code == 200
    assert '分数' in response.json['template']['prompt'] and '35分钟' in response.json['template']['prompt']
    assert client.post(base+'/missing/render', json={}).status_code == 404
    for variables in [None, [], {'unknown': 'x'}, {'topic': 'x'*81}, {'subject': ''}, {'minutes': '0'}, {'minutes': '181'}, {'minutes': True}, {'topic': '\x00'}]:
        assert client.post(base+'/lesson-plan/render', json={'variables': variables}).status_code == 400
    with app.app_context():
        assert TutorAgent.query.count() == before


def test_templates_are_bounded_and_substitution_is_literal():
    for item in TEMPLATES:
        rendered = render_template_prompt(item['id'])
        assert 0 < len(rendered['prompt']) <= 2000
        assert '{{' not in rendered['prompt']
    prompt = render_template_prompt('lesson-plan', {'topic': '{{minutes}}<script>'})['prompt']
    assert '{{minutes}}<script>' in prompt
    with pytest.raises(ValueError):
        render_template_prompt('lesson-plan', [])


def test_new_classroom_agents_are_idempotent_and_preserve_edits(app):
    with app.app_context():
        seed_tutor_data()
        rows = TutorAgent.query.filter(TutorAgent.seed_key.like('classroom-%')).all()
        assert len(rows) == 3*len(NEW_APPLICATION_IDS)
        for row in rows:
            assert row.prompt and not TutorAgentMaterial.query.filter_by(agent_id=row.id).first()
            assert not TutorAgentSkill.query.filter_by(agent_id=row.id).first()
        rows[0].prompt, rows[0].enabled = '教师自己维护的提示词', False
        db.session.commit()
        ident = rows[0].id
        count = TutorAgent.query.count()
        seed_tutor_data()
        assert TutorAgent.query.count() == count
        assert db.session.get(TutorAgent, ident).prompt == '教师自己维护的提示词'
        assert not db.session.get(TutorAgent, ident).enabled
