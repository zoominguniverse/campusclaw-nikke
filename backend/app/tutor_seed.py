"""Idempotent demo configuration; never rewrites an existing teacher configuration."""
from .extensions import db
from .models import ClassMembership, ClassSubject, Material, SchoolClass, Skill, TeacherSubjectAssignment, TutorAgent, TutorAgentMaterial, TutorAgentSkill
from .tutor_skills import parse_skill
from .tutor_catalog import TEMPLATES, NEW_APPLICATION_IDS, render_template_prompt

SAMPLES = {
    "mathematics": "名称：数学解题引导\n适用条件：方程,去括号,分数,通分,面积,应用题,未知数,行程\n资料：数学\n工具：knowledge_search\n启用：是\n\n先看懂学生卡在哪一步，只指出下一步该检查什么。去括号时检查每一项是否都乘到了系数，分母不同先检查是否通分。不要算出最终得数，不要给完整过程。依据本班数学资料，说明错在哪一项。",
    "language": "名称：语文解题引导\n适用条件：春晓,默写,阅读,中心,作文,开头,古诗,词语\n资料：语文\n工具：knowledge_search\n启用：是\n\n先接住学生已经写出的内容，引导他看哪一句或找哪类线索。不要直接给诗的下一句、选项、中心句或改好的段落。依据本班语文资料说明下一步。",
}


def seed_tutor_data():
    for subject in ClassSubject.query.filter(ClassSubject.subject_key.in_(SAMPLES), ClassSubject.status == "active"):
        assignment = TeacherSubjectAssignment.query.filter_by(subject_id=subject.id, is_active=True).order_by(TeacherSubjectAssignment.id).first()
        if not assignment:
            continue
        key = f"tutor-{subject.subject_key}-v1"
        skill = Skill.query.filter_by(class_id=subject.class_id, seed_key=key).one_or_none()
        if not skill:
            values = parse_skill(SAMPLES[subject.subject_key])
            # Respect class-local names already created by teachers.
            skill = Skill.query.filter_by(class_id=subject.class_id, name=values["name"]).one_or_none()
            if not skill:
                skill = Skill(class_id=subject.class_id, seed_key=key, created_by=assignment.teacher_id, updated_by=assignment.teacher_id, **values)
                db.session.add(skill)
                db.session.flush()
        agent = TutorAgent.query.filter_by(class_id=subject.class_id, seed_key=key).one_or_none()
        if agent or TutorAgent.query.filter_by(class_id=subject.class_id, name=f"{subject.name}解题助手").first():
            continue
        agent = TutorAgent(class_id=subject.class_id, name=f"{subject.name}解题助手", seed_key=key,
                           created_by=assignment.teacher_id, updated_by=assignment.teacher_id)
        db.session.add(agent)
        db.session.flush()
        if skill and not skill.legacy_placeholder:
            db.session.add(TutorAgentSkill(agent_id=agent.id, skill_id=skill.id))
        for material in Material.query.filter_by(class_id=subject.class_id, subject_id=subject.id):
            db.session.add(TutorAgentMaterial(agent_id=agent.id, material_id=material.id))
    for school_class in SchoolClass.query.order_by(SchoolClass.id):
        teacher = ClassMembership.query.filter_by(class_id=school_class.id, is_teacher=True).order_by(ClassMembership.id).first()
        if not teacher:
            continue
        for template in TEMPLATES:
            if template["id"] not in NEW_APPLICATION_IDS:
                continue
            seed_key = f"classroom-{template['id']}-v1"
            existing = TutorAgent.query.filter_by(class_id=school_class.id, seed_key=seed_key).first()
            if existing or TutorAgent.query.filter_by(class_id=school_class.id, name=template["app_name"]).first():
                continue
            rendered = render_template_prompt(template["id"])
            db.session.add(TutorAgent(class_id=school_class.id, seed_key=seed_key, name=template["app_name"],
                                     prompt=rendered["prompt"], created_by=teacher.user_id, updated_by=teacher.user_id))
    db.session.commit()
