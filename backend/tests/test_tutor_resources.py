from io import BytesIO

import pytest
from app.extensions import db
from app.models import ClassMembership, Conversation, Material, Skill, TutorAgent, TutorAgentMaterial, TutorAgentSkill, User
from app.tutor_seed import SAMPLES
from .conftest import login


@pytest.fixture
def teacher(client):
    login(client, "teacher_a", "teacher-password")
    return client


def test_skill_crud_file_validation_unique_and_delete_binding(app, teacher):
    base = '/api/classes/1/skills'
    source = SAMPLES['mathematics'].replace('数学解题引导', '测试解题引导')
    response = teacher.post(base, data={'file': (BytesIO(source.encode()), 'skill.txt')})
    assert response.status_code == 201
    skill = response.get_json()['skill']
    assert teacher.get(f"{base}/{skill['id']}").get_json()['skill']['source_text'] == source
    assert teacher.post(base, json={'source_text': source}).status_code == 400
    assert teacher.put(f"{base}/{skill['id']}", json={'source_text': source.replace('启用：是', '启用：否')}).get_json()['skill']['enabled'] is False
    with app.app_context():
        agent = TutorAgent.query.filter_by(class_id=1).first()
        db.session.add(TutorAgentSkill(agent_id=agent.id, skill_id=skill['id']))
        db.session.commit()
    assert teacher.delete(f"{base}/{skill['id']}").status_code == 204
    with app.app_context():
        assert not db.session.get(Skill, skill['id']) and not TutorAgentSkill.query.filter_by(skill_id=skill['id']).first()
        before = Skill.query.count()
    assert teacher.post(base, json={'source_text': 'invalid'}).status_code == 400
    with app.app_context():
        assert Skill.query.count() == before


@pytest.mark.parametrize('username,password', [('student_a1','student-a-password'), ('super_admin','super-admin-password'), ('class_admin_a','class-admin-a-password')])
def test_no_teacher_privilege_is_inherited(client, username, password):
    login(client, username, password)
    assert client.post('/api/classes/1/agents', json={'name':'forbidden'}).status_code == 403
    assert client.post('/api/classes/1/skills', json={'source_text':SAMPLES['mathematics']}).status_code == 403


def test_agent_binding_validation_is_atomic_and_scope_filtered(app, teacher):
    with app.app_context():
        allowed = Material.query.filter_by(title='1 班数学示例材料').one().id
        foreign = Material.query.filter_by(title='2 班语文示例材料').one().id
        skill_id = Skill.query.filter_by(class_id=1, legacy_placeholder=False).first().id
    response = teacher.post('/api/classes/1/agents', json={'name':'atomic', 'prompt':'', 'skill_ids':[skill_id], 'material_ids':[allowed]})
    assert response.status_code == 201
    agent = response.get_json()['agent']
    base = f"/api/classes/1/agents/{agent['id']}"
    rejected = teacher.put(base, json={'name':'should-not-save','material_ids':[allowed,foreign]})
    assert rejected.status_code == 404
    assert teacher.get(base).get_json()['agent'] == agent
    assert teacher.put(base, json={'prompt':'new prompt'}).get_json()['agent']['material_ids'] == [allowed]
    assert teacher.put(base, json={'material_ids':[]}).get_json()['agent']['material_ids'] == []
    assert teacher.post('/api/classes/1/agents', json={'name':'atomic'}).status_code == 400
    for values in [{'name':''}, {'name':'a'*65}, {'prompt':'a'*2001}, {'enabled':'yes'}, {'skill_ids':[True]}]:
        assert teacher.put(base, json=values).status_code == 400
    with app.app_context():
        # Another teacher's source is not in linzimo's subjects.
        other = User.query.filter_by(username='wangyuxin').one()
        from app.models import ClassSubject, TeacherSubjectAssignment
        language = ClassSubject.query.filter_by(class_id=1, subject_key='language').one()
        material = Material(class_id=1, subject_id=language.id, uploader_id=other.id, title='private-language', original_filename='x.txt',storage_path='seeded',content_type='text/plain')
        db.session.add(material)
        db.session.commit()
        material_id = material.id
        db.session.add(TutorAgentMaterial(agent_id=agent['id'], material_id=material_id))
        db.session.commit()
    filtered = teacher.get(base).get_json()['agent']
    assert filtered['material_ids'] == [] and filtered['hidden_material_count'] == 1
    assert teacher.put(base, json={'material_ids':[material_id]}).status_code == 404
    with app.app_context():
        from app.models import TeacherSubjectAssignment
        TeacherSubjectAssignment.query.filter_by(teacher_id=agent['created_by']).update({'is_active':False})
        db.session.add(TutorAgentMaterial(agent_id=agent['id'],material_id=allowed))
        db.session.commit()
    assert teacher.get(base).get_json()['agent']['material_ids'] == []


def test_foreign_and_disabled_resources_have_same_404(app, client):
    login(client, 'student_a1', 'student-a-password')
    with app.app_context():
        foreign = TutorAgent.query.filter_by(class_id=2).first().id
        disabled = TutorAgent(class_id=1,name='disabled',enabled=False)
        db.session.add(disabled)
        db.session.commit()
        disabled_id = disabled.id
        foreign_skill = Skill.query.filter_by(class_id=2,legacy_placeholder=False).first().id
    missing = client.get('/api/classes/1/agents/999999')
    for ident in [foreign,disabled_id]:
        response = client.get(f'/api/classes/1/agents/{ident}')
        assert response.status_code == missing.status_code == 404 and response.data == missing.data
        created = client.post('/api/conversations', json={'agent_id':ident})
        assert created.status_code == 404 and created.data == missing.data
    assert client.get(f'/api/classes/1/skills/{foreign_skill}').data == client.get('/api/classes/1/skills/999999').data
    assert all(a['enabled'] for a in client.get('/api/classes/1/agents').get_json()['items'])


def test_conversation_private_owner_and_disabled_existing(app, client):
    login(client, 'student_a1', 'student-a-password')
    agent = client.get('/api/classes/1/agents').get_json()['items'][0]
    assert client.post('/api/conversations',json={}).status_code == 400
    row = client.post('/api/conversations',json={'agent_id':agent['id'], 'class_id':2, 'user_id':777}).get_json()['conversation']
    with app.app_context():
        db.session.get(TutorAgent,agent['id']).enabled = False
        source_user = User.query.filter_by(username='zhouchengxi').one()
        other = User(username='tutor-classmate',password_hash=source_user.password_hash,role='student',class_id=1)
        db.session.add(other)
        db.session.flush()
        db.session.add(ClassMembership(user_id=other.id,class_id=1))
        db.session.commit()
        assert row['user_id'] == source_user.id and row['class_id'] == 1
    assert client.get(f"/api/conversations/{row['id']}").status_code == 200
    login(client,'tutor-classmate','student-a-password')
    missing = client.get('/api/conversations/999999')
    assert client.get(f"/api/conversations/{row['id']}").data == missing.data
    assert client.get('/api/conversations').get_json()['items'] == []
    login(client,'student_b1','student-b-password')
    assert client.get(f"/api/conversations/{row['id']}").data == missing.data


def test_agent_no_selection_and_no_enabled_agents(app, client):
    login(client,'student_a1','student-a-password')
    with app.app_context():
        TutorAgent.query.filter_by(class_id=1).update({'enabled':False})
        db.session.commit()
    assert client.post('/api/conversations',json={}).get_json()['error'] == '本班暂无可用的智能体'
