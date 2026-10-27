"""Class configuration and owner-private tutor resources."""
import json

from flask import Blueprint, current_app, g, jsonify, request, Response, stream_with_context
from sqlalchemy.exc import IntegrityError

from .api_docs import api_doc, obj, array, ref, STRING, INTEGER, BOOLEAN, SCHEMAS
from .auth import json_error, require_auth
from .authorization import is_teacher_member, subject_scope
from .extensions import db
from .models import Conversation, Material, Message, Skill, TutorAgent, TutorAgentMaterial, TutorAgentSkill, utc_now
from .tutor_skills import parse_skill, SkillInputError
from .tutor_context import prepare_turn
from .tutor_stream import CitationFilter, GenerationLock, stream_tutor
from .providers import ProviderUnavailable
from .retrieval import ReindexRequired, RetrievalInputError
from .mcp_bindings import prepare_bindings, replace_bindings, binding_payload
from .models import SkillMCPBinding
from .tutor_tools import ToolPhase, selected_refs, recovered_snapshot

tutors_bp = Blueprint("tutors", __name__)
NOT_FOUND = "resource not found"
AGENT_INPUT = obj({"name": {"type": "string", "minLength": 1, "maxLength": 64}, "prompt": {"type": "string", "maxLength": 2000}, "enabled": BOOLEAN,
                   "skill_ids": array(INTEGER), "material_ids": array({"type": "string", "format": "uuid"})}, ["name"])
SKILL_INPUT = obj({"source_text": {"type": "string", "maxLength": 8000}, "tool_confirmations": {"type": "object", "additionalProperties": STRING}}, ["source_text"])
SKILL_FILE = obj({"file": {"type": "string", "format": "binary"}, "tool_confirmations": {"type": "string", "description": "JSON object mapping reviewed ref to declaration_hash"}}, ["file"])
SCHEMAS.update({
    "Skill": obj({"id": INTEGER, "class_id": INTEGER, "name": STRING, "trigger_text": STRING, "description": STRING,
                  "source_text": STRING, "subject_text": STRING, "tools": array(STRING), "enabled": BOOLEAN, "mcp_bindings": array(obj({"ref": STRING, "declaration_hash": STRING, "status": STRING})),
                  "created_by": {"type": "integer", "nullable": True}, "updated_by": {"type": "integer", "nullable": True}, "updated_at": STRING}),
    "Agent": obj({"id": INTEGER, "class_id": INTEGER, "name": STRING, "prompt": STRING, "enabled": BOOLEAN,
                  "skill_ids": array(INTEGER), "material_ids": array(STRING), "hidden_material_count": INTEGER,
                  "created_by": {"type": "integer", "nullable": True}, "updated_by": {"type": "integer", "nullable": True}, "updated_at": STRING}),
    "Conversation": obj({"id": INTEGER, "class_id": INTEGER, "user_id": INTEGER, "agent_id": INTEGER, "title": STRING, "created_at": STRING, "updated_at": STRING}),
    "Message": obj({"id": INTEGER, "role": {"type": "string", "enum": ["user", "assistant"]}, "content": STRING,
                    "citations": array(ref("CitationSnapshot")), "skill_name": {"type": "string", "nullable": True},
                    "tool_calls": array(obj({"call_id": STRING, "ref": STRING, "round": INTEGER, "status": {"type": "string", "enum": ["ok", "error", "denied"]}, "reason_code": {**STRING, "nullable": True}, "text": STRING})),
                    "completion_state": {"type": "string", "enum": ["complete", "interrupted"]}, "created_at": STRING}),
})


def scope_or_error(write=False):
    scope = subject_scope(g.current_user)
    if not scope or (write and not is_teacher_member(g.current_user, scope.class_id)):
        return None, json_error(403, "teacher role required" if write else "class access denied")
    return scope, None


def body_object():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValueError("request must be a JSON object")
    return body


def skill_payload(skill):
    return {"id": skill.id, "class_id": skill.class_id, "name": skill.name, "trigger_text": skill.trigger_text,
            "description": skill.description, "source_text": skill.source_text, "subject_text": skill.subject_text,
            "tools": skill.tools_json, "enabled": skill.enabled, "created_by": skill.created_by,
            "updated_by": skill.updated_by, "updated_at": skill.updated_at.isoformat(), "mcp_bindings": binding_payload(skill)}


def agent_payload(agent, scope):
    skill_ids = [row.skill_id for row in TutorAgentSkill.query.filter_by(agent_id=agent.id).order_by(TutorAgentSkill.skill_id)]
    all_bindings = [row.material_id for row in TutorAgentMaterial.query.filter_by(agent_id=agent.id)]
    material_ids = [m.id for m in Material.query.filter(Material.id.in_(all_bindings), Material.class_id == scope.class_id,
                                                      Material.subject_id.in_(scope.subject_ids)).order_by(Material.id)]
    return {"id": agent.id, "class_id": agent.class_id, "name": agent.name, "prompt": agent.prompt, "enabled": agent.enabled,
            "skill_ids": skill_ids, "material_ids": material_ids, "hidden_material_count": len(all_bindings) - len(material_ids),
            "created_by": agent.created_by, "updated_by": agent.updated_by, "updated_at": agent.updated_at.isoformat()}


def _skill_source():
    if request.mimetype == "multipart/form-data":
        upload = request.files.get("file")
        if not upload:
            raise SkillInputError("请选择UTF-8技能文件")
        try:
            return upload.stream.read(32001).decode("utf-8")
        except UnicodeDecodeError:
            raise SkillInputError("技能文件必须使用UTF-8编码") from None
    return body_object().get("source_text")


def _find_skill(scope, ident):
    return Skill.query.filter_by(id=ident, class_id=scope.class_id, legacy_placeholder=False).one_or_none()


@tutors_bp.get("/api/classes/<int:class_id>/skills")
@api_doc("skills_list", "列出本班技能", response=obj({"items": array(ref("Skill"))}))
@require_auth
def list_skills(class_id):
    scope, denied = scope_or_error()
    if denied:
        return denied
    return jsonify(items=[skill_payload(s) for s in Skill.query.filter_by(class_id=scope.class_id, legacy_placeholder=False).order_by(Skill.id)])


@tutors_bp.get("/api/classes/<int:class_id>/skills/<int:skill_id>")
@api_doc("skills_get", "读取本班技能原文", response=obj({"skill": ref("Skill")}), errors={404: NOT_FOUND})
@require_auth
def get_skill(class_id, skill_id):
    scope, denied = scope_or_error()
    if denied:
        return denied
    skill = _find_skill(scope, skill_id)
    return jsonify(skill=skill_payload(skill)) if skill else json_error(404, NOT_FOUND)


def _write_skill(skill=None):
    scope, denied = scope_or_error(write=True)
    if denied:
        return denied
    try:
        values = parse_skill(_skill_source())
        if request.mimetype == "multipart/form-data":
            try:
                confirmations = json.loads(request.form.get("tool_confirmations", "{}"))
            except ValueError:
                raise ValueError("invalid_tool_confirmations") from None
        else:
            confirmations = body_object().get("tool_confirmations", {})
        prepared = prepare_bindings(values["tools_json"], confirmations, scope.class_id, skill)
        if skill is None:
            skill = Skill(class_id=scope.class_id, created_by=g.current_user.id)
            db.session.add(skill)
        for key, value in values.items():
            setattr(skill, key, value)
        skill.updated_by, skill.updated_at = g.current_user.id, utc_now()
        db.session.flush()
        replace_bindings(skill, prepared)
        db.session.commit()
        return jsonify(skill=skill_payload(skill))
    except LookupError:
        db.session.rollback()
        return json_error(404, NOT_FOUND)
    except (ValueError, IntegrityError) as error:
        db.session.rollback()
        return json_error(400, "本班已有同名技能" if isinstance(error, IntegrityError) else str(error))


@tutors_bp.post("/api/classes/<int:class_id>/skills")
@api_doc("skills_create", "教师用文本文件创建技能", role="teacher", status=201, body=SKILL_INPUT, multipart=SKILL_FILE,
         response=obj({"skill": ref("Skill")}), errors={400: "Invalid skill definition, unreviewed tool or duplicate class name", 404: NOT_FOUND})
@require_auth
def create_skill(class_id):
    response = _write_skill()
    if response.status_code == 200:
        response.status_code = 201
    return response


@tutors_bp.put("/api/classes/<int:class_id>/skills/<int:skill_id>")
@api_doc("skills_update", "教师改写技能文件", role="teacher", body=SKILL_INPUT, multipart=SKILL_FILE,
         response=obj({"skill": ref("Skill")}), errors={400: "Invalid or duplicate definition", 404: NOT_FOUND})
@require_auth
def update_skill(class_id, skill_id):
    scope, denied = scope_or_error(write=True)
    if denied:
        return denied
    skill = _find_skill(scope, skill_id)
    return _write_skill(skill) if skill else json_error(404, NOT_FOUND)


@tutors_bp.delete("/api/classes/<int:class_id>/skills/<int:skill_id>")
@api_doc("skills_delete", "教师删除技能并解绑", role="teacher", status=204, errors={404: NOT_FOUND})
@require_auth
def delete_skill(class_id, skill_id):
    scope, denied = scope_or_error(write=True)
    if denied:
        return denied
    skill = _find_skill(scope, skill_id)
    if not skill:
        return json_error(404, NOT_FOUND)
    TutorAgentSkill.query.filter_by(skill_id=skill.id).delete(synchronize_session=False)
    SkillMCPBinding.query.filter_by(skill_id=skill.id).delete(synchronize_session=False)
    db.session.delete(skill)
    db.session.commit()
    return "", 204


def _find_agent(scope, ident, selectable=False):
    query = TutorAgent.query.filter_by(id=ident, class_id=scope.class_id)
    if selectable or scope.role == "student":
        query = query.filter_by(enabled=True)
    return query.one_or_none()


@tutors_bp.get("/api/classes/<int:class_id>/agents")
@api_doc("agents_list", "列出本班智能体", response=obj({"items": array(ref("Agent"))}), description="学生只见启用的；教师可见停用的。绑定材料响应按当前学科权限过滤。")
@require_auth
def list_agents(class_id):
    scope, denied = scope_or_error()
    if denied:
        return denied
    query = TutorAgent.query.filter_by(class_id=scope.class_id)
    if scope.role == "student":
        query = query.filter_by(enabled=True)
    return jsonify(items=[agent_payload(agent, scope) for agent in query.order_by(TutorAgent.id)])


@tutors_bp.get("/api/classes/<int:class_id>/agents/<int:agent_id>")
@api_doc("agents_get", "读取智能体配置", response=obj({"agent": ref("Agent")}), errors={404: NOT_FOUND})
@require_auth
def get_agent(class_id, agent_id):
    scope, denied = scope_or_error()
    if denied:
        return denied
    agent = _find_agent(scope, agent_id)
    return jsonify(agent=agent_payload(agent, scope)) if agent else json_error(404, NOT_FOUND)


def _validate_agent(body, scope, agent):
    name = body.get("name", agent.name if agent else "")
    prompt = body.get("prompt", agent.prompt if agent else "")
    enabled = body.get("enabled", agent.enabled if agent else True)
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64 or "\x00" in name:
        raise ValueError("名称须为1–64字")
    if not isinstance(prompt, str) or len(prompt) > 2000 or "\x00" in prompt:
        raise ValueError("角色提示词最多2000字")
    if type(enabled) is not bool:
        raise ValueError("enabled must be a boolean")
    values = dict(name=name.strip(), prompt=prompt.strip(), enabled=enabled)
    for key, model, field in [("skill_ids", Skill, Skill.id), ("material_ids", Material, Material.id)]:
        if key not in body:
            continue
        identifiers = body[key]
        expected = int if key == "skill_ids" else str
        if not isinstance(identifiers, list) or len(identifiers) > 1000 or any(type(i) is not expected for i in identifiers):
            raise ValueError(f"{key} must be an array of {expected.__name__} IDs (at most 1000)")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError(f"{key} contains duplicate IDs")
        query = model.query.filter(field.in_(identifiers), model.class_id == scope.class_id)
        query = query.filter(Skill.legacy_placeholder.is_(False)) if model is Skill else query.filter(Material.subject_id.in_(scope.subject_ids))
        if query.count() != len(identifiers):
            raise LookupError(NOT_FOUND)
        values[key] = identifiers
    return values


def _write_agent(agent=None):
    scope, denied = scope_or_error(write=True)
    if denied:
        return denied
    try:
        values = _validate_agent(body_object(), scope, agent)
        if agent is None:
            agent = TutorAgent(class_id=scope.class_id, created_by=g.current_user.id)
            db.session.add(agent)
        for key in ("name", "prompt", "enabled"):
            setattr(agent, key, values[key])
        agent.updated_by, agent.updated_at = g.current_user.id, utc_now()
        db.session.flush()
        for key, model, field in [("skill_ids", TutorAgentSkill, "skill_id"), ("material_ids", TutorAgentMaterial, "material_id")]:
            if key in values:
                model.query.filter_by(agent_id=agent.id).delete(synchronize_session=False)
                db.session.add_all([model(agent_id=agent.id, **{field: ident}) for ident in values[key]])
        db.session.commit()
        return jsonify(agent=agent_payload(agent, scope))
    except LookupError:
        db.session.rollback()
        return json_error(404, NOT_FOUND)
    except (ValueError, IntegrityError) as error:
        db.session.rollback()
        return json_error(400, "本班已有同名智能体" if isinstance(error, IntegrityError) else str(error))


@tutors_bp.post("/api/classes/<int:class_id>/agents")
@api_doc("agents_create", "教师创建智能体及绑定", role="teacher", status=201, body=AGENT_INPUT, response=obj({"agent": ref("Agent")}), errors={400: "Invalid fields or duplicate name", 404: "A binding resource is unavailable"})
@require_auth
def create_agent(class_id):
    response = _write_agent()
    if response.status_code == 200:
        response.status_code = 201
    return response


@tutors_bp.put("/api/classes/<int:class_id>/agents/<int:agent_id>")
@api_doc("agents_update", "教师修改智能体及绑定", role="teacher", body={**AGENT_INPUT, "required": []}, response=obj({"agent": ref("Agent")}), errors={400: "Invalid fields or duplicate name", 404: NOT_FOUND}, description="省略绑定数组保持原关系；提交数组完整替换，空数组清空。配置下一轮生效；停用只阻止新选用。")
@require_auth
def update_agent(class_id, agent_id):
    scope, denied = scope_or_error(write=True)
    if denied:
        return denied
    agent = _find_agent(scope, agent_id)
    return _write_agent(agent) if agent else json_error(404, NOT_FOUND)


def conversation_payload(conversation):
    return {key: getattr(conversation, key) for key in ("id", "class_id", "user_id", "agent_id", "title")} | {
        "created_at": conversation.created_at.isoformat(), "updated_at": conversation.updated_at.isoformat()}


def own_conversation(scope, ident):
    return Conversation.query.filter_by(id=ident, user_id=g.current_user.id, class_id=scope.class_id).one_or_none()


def message_payload(message, scope):
    citations = []
    for citation in message.citations_json:
        source = Material.query.filter_by(id=citation.get("material_id"), class_id=scope.class_id).one_or_none()
        if source and source.subject_id in scope.subject_ids:
            citations.append(citation)
        else:
            citations.append({key: citation[key] for key in ("material_id", "material_title", "chunk_id", "chunk_index", "generation_id") if key in citation} | {"unavailable": True})
    return {"id": message.id, "role": message.role, "content": message.content, "citations": citations,
            "skill_name": message.skill_name, "completion_state": message.completion_state, "created_at": message.created_at.isoformat(), "tool_calls": recovered_snapshot(message)}


@tutors_bp.get("/api/conversations")
@api_doc("conversations_list", "列出本人最近会话", response=obj({"items": array(ref("Conversation"))}))
@require_auth
def list_conversations():
    scope, denied = scope_or_error()
    if denied:
        return denied
    rows = Conversation.query.filter_by(user_id=g.current_user.id, class_id=scope.class_id).order_by(Conversation.updated_at.desc(), Conversation.id.desc())
    return jsonify(items=[conversation_payload(row) for row in rows])


@tutors_bp.post("/api/conversations")
@api_doc("conversations_create", "选定智能体创建私有会话", status=201, body=obj({"agent_id": INTEGER}), response=obj({"conversation": ref("Conversation")}), errors={400: "Missing selection or no available agent", 404: NOT_FOUND})
@require_auth
def create_conversation():
    scope, denied = scope_or_error()
    if denied:
        return denied
    try:
        body = body_object()
        ident = body.get("agent_id")
        if ident is None:
            return json_error(400, "请选择智能体" if TutorAgent.query.filter_by(class_id=scope.class_id, enabled=True).first() else "本班暂无可用的智能体")
        agent = _find_agent(scope, ident, selectable=True) if type(ident) is int else None
        if not agent:
            return json_error(404, NOT_FOUND)
        row = Conversation(class_id=scope.class_id, user_id=g.current_user.id, agent_id=agent.id)
        db.session.add(row)
        db.session.commit()
        return jsonify(conversation=conversation_payload(row)), 201
    except ValueError as error:
        return json_error(400, str(error))


@tutors_bp.get("/api/conversations/<int:conversation_id>")
@api_doc("conversations_get", "读取本人会话和消息", response=obj({"conversation": ref("Conversation"), "agent": ref("Agent"), "messages": array(ref("Message"))}), errors={404: NOT_FOUND})
@require_auth
def get_conversation(conversation_id):
    scope, denied = scope_or_error()
    if denied:
        return denied
    row = own_conversation(scope, conversation_id)
    agent = TutorAgent.query.filter_by(id=row.agent_id, class_id=scope.class_id).one_or_none() if row else None
    if not row or not agent:
        return json_error(404, NOT_FOUND)
    return jsonify(conversation=conversation_payload(row), agent=agent_payload(agent, scope),
                   messages=[message_payload(m, scope) for m in Message.query.filter_by(conversation_id=row.id).order_by(Message.id)])


def _live_turn(user_id, class_id, citations):
    from .auth import _load_access_context
    from .models import KnowledgeEntry
    from .retrieval_schema import source_hash
    # Short, fresh reads detect membership, token, subject and source revocation.
    db.session.remove()
    context = _load_access_context()
    scope = subject_scope(context.user) if context and context.user.id == user_id else None
    if not scope or scope.class_id != class_id:
        raise PermissionError("conversation access revoked")
    for citation in citations:
        material = Material.query.filter_by(id=citation["material_id"], class_id=class_id).one_or_none()
        entry = KnowledgeEntry.query.filter_by(material_id=citation["material_id"], class_id=class_id).one_or_none()
        if not material or material.subject_id not in scope.subject_ids or not entry or source_hash(entry.body_text) != citation["source_hash"]:
            raise PermissionError("evidence access revoked or source changed")
    db.session.rollback()


def _save_assistant(conversation_id, content, citations, skill, state):
    user_message = Message.query.filter_by(conversation_id=conversation_id, role="user").order_by(Message.id.desc()).first()
    row = Message(conversation_id=conversation_id, role="assistant", content=content, citations_json=citations,
                  skill_name=skill["name"] if skill else None, completion_state=state, tool_calls_json=recovered_snapshot(user_message) if user_message else [])
    db.session.add(row)
    conversation = db.session.get(Conversation, conversation_id)
    conversation.updated_at = utc_now()
    db.session.commit()
    return row.id


def _event(name, value):
    return f"event: {name}\ndata: {json.dumps(value, ensure_ascii=False)}\n\n"


@tutors_bp.post("/api/conversations/<int:conversation_id>/messages")
@api_doc("messages_create", "提交问题并流式返回辅导正文", body=obj({"question": {"type": "string", "minLength": 2, "maxLength": 500}}),
         response=STRING, streaming=True, errors={400: "Invalid question", 404: NOT_FOUND, 409: "This conversation is generating", 503: "Provider or retrieval unavailable"},
         description="固定会话agent；忽略客户端agent_id/class_id/history。meta先于增量delta，assistant提交后才发done。meta后错误使用error帧；取消或EOF保留已发正文为interrupted。不得自动重放POST。无证据仍提供帮助但无数字引用。")
@require_auth
def create_message(conversation_id):
    scope, denied = scope_or_error()
    if denied:
        return denied
    conversation = own_conversation(scope, conversation_id)
    if not conversation:
        return json_error(404, NOT_FOUND)
    try:
        question = body_object().get("question")
        if not isinstance(question, str) or not 2 <= len(question.strip()) <= 500 or "\x00" in question:
            raise ValueError("问题须为2–500字")
        question = question.strip()
    except ValueError as error:
        return json_error(400, str(error))
    user_id, class_id = g.current_user.id, scope.class_id
    lock, provider = GenerationLock(conversation_id), None
    try:
        if not lock.acquire():
            return json_error(409, "会话正在生成，请等待当前回答完成")
        agent = TutorAgent.query.filter_by(id=conversation.agent_id, class_id=class_id).one_or_none()
        if not agent:
            lock.close()
            return json_error(404, NOT_FOUND)
        first = not Message.query.filter_by(conversation_id=conversation_id, role="user").first()
        user_message = Message(conversation_id=conversation_id, role="user", content=question)
        db.session.add(user_message)
        if first:
            conversation.title = question[:24]
        conversation.updated_at = utc_now()
        db.session.commit()
        user_message_id = user_message.id
        messages, citations, skill = prepare_turn(conversation, agent, scope, question, user_message_id)
        mcp_refs = selected_refs(skill)
        _live_turn(user_id, class_id, citations)
        if not mcp_refs:
            provider = stream_tutor(messages)
    except Exception as error:
        db.session.rollback()
        if provider:
            provider.close()
        lock.close()
        if isinstance(error, ReindexRequired):
            return jsonify(error="authorized materials require reindexing", code="reindex_required"), 503
        if isinstance(error, RetrievalInputError):
            return json_error(400, str(error))
        if isinstance(error, PermissionError):
            return json_error(403, "会话或资料权限已变更")
        current_app.logger.warning("tutor preflight unavailable: %s", type(error).__name__)
        return json_error(503, "辅导服务暂不可用，问题已保留，请稍后继续")

    def generate():
        nonlocal provider
        output, saved, storage_failed = [], False, False
        filter_ = CitationFilter(len(citations))
        try:
            meta = {"status": "ok", "skill": skill, "citations": citations, "demo_mode": current_app.config["CHAT_PROVIDER"] == "deterministic"}
            yield _event("meta", meta)
            if mcp_refs:
                phase = ToolPhase(messages, skill, mcp_refs, user_id, class_id, conversation_id, user_message_id,
                                  lambda: _live_turn(user_id, class_id, citations))
                for tool_calls in phase:
                    yield _event("meta", {**meta, "tool_calls": tool_calls})
                if phase.warning:
                    yield _event("meta", {**meta, **({"tool_calls": phase.snapshot()} if phase.calls else {}), "tool_warning": phase.warning})
                _live_turn(user_id, class_id, citations)
                provider = stream_tutor(phase.final_messages)
            for raw in provider:
                _live_turn(user_id, class_id, citations)
                delta = filter_.feed(raw)
                if delta:
                    output.append(delta)
                    yield _event("delta", {"text": delta})
                    # Flush separate SSE comments so a closed downstream socket
                    # is observed before waiting for the next provider chunk.
                    yield ": keep-alive\n\n"
                    yield ": keep-alive\n\n"
            tail = filter_.finish()
            if tail:
                _live_turn(user_id, class_id, citations)
                output.append(tail)
                yield _event("delta", {"text": tail})
            if not output:
                raise ProviderUnavailable("provider returned no text")
            yield ": keep-alive\n\n"
            yield ": keep-alive\n\n"
            _live_turn(user_id, class_id, citations)
            try:
                message_id = _save_assistant(conversation_id, "".join(output), citations, skill, "complete")
                saved = True
            except Exception:
                storage_failed = True
                db.session.rollback()
                raise
            yield _event("done", {"message_id": message_id})
        except GeneratorExit:
            raise
        except Exception:
            current_app.logger.warning("tutor stream interrupted conversation_id=%s", conversation_id)
            if output and not storage_failed:
                try:
                    _save_assistant(conversation_id, "".join(output), citations, skill, "interrupted")
                    saved = True
                except Exception:
                    storage_failed = True
                    db.session.rollback()
            yield _event("error", {"error": "回答未保存，请重新打开历史确认后继续" if storage_failed else "回答已中断，请重新打开历史后继续"})
        finally:
            if output and not saved and not storage_failed:
                try:
                    _save_assistant(conversation_id, "".join(output), citations, skill, "interrupted")
                except Exception:
                    db.session.rollback()
                    current_app.logger.warning("interrupted tutor text could not be saved conversation_id=%s", conversation_id)
            if provider:
                provider.close()
            lock.close()
            db.session.remove()

    response = Response(stream_with_context(generate()), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
    # Covers a response closed before the generator is first advanced.
    response.call_on_close(lambda: provider.close() if provider else None)
    response.call_on_close(lock.close)
    return response
