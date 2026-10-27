"""Explicit teacher review binds a skill to a declaration and configuration."""
from .extensions import db
from .models import MCPServer, MCPTool, SkillMCPBinding
from .mcp_policy import MCPError, permitted

def resolve_binding(binding, class_id):
    server = MCPServer.query.filter_by(id=binding.server_id, class_id=class_id).one_or_none() if binding.server_id else None
    if not server:
        return None, None, "server_unavailable"
    if binding.configuration_revision != server.configuration_revision:
        return server, None, "binding_review_required"
    if not server.connected:
        return server, None, "server_unavailable"
    tool = MCPTool.query.filter_by(server_id=server.id, name=binding.tool_ref.split("@", 1)[0]).one_or_none()
    if not tool or tool.declaration_hash != binding.declaration_hash or binding.tool_ref != f"{tool.name}@{server.name}":
        return server, tool, "binding_review_required"
    if not permitted(server.base_url, tool.name):
        return server, tool, "tool_not_permitted"
    return server, tool, None

def prepare_bindings(refs, confirmations, class_id, skill=None):
    if not isinstance(confirmations, dict) or any(not isinstance(k, str) or not isinstance(v, str) or len(v) != 64 for k, v in confirmations.items()):
        raise MCPError("invalid_tool_confirmations")
    old = {b.tool_ref: b for b in SkillMCPBinding.query.filter_by(skill_id=skill.id)} if skill else {}
    prepared = []
    for tool_ref in (r for r in refs if r != "knowledge_search"):
        tool_name, server_name = tool_ref.split("@")
        server = MCPServer.query.filter_by(class_id=class_id, name=server_name).one_or_none()
        if not server:
            raise LookupError("resource not found")
        if not server.connected:
            raise MCPError("server_unavailable")
        tool = MCPTool.query.filter_by(server_id=server.id, name=tool_name).one_or_none()
        if not tool or not permitted(server.base_url, tool_name):
            raise MCPError("tool_not_permitted")
        previous = old.get(tool_ref)
        still_confirmed = previous and previous.server_id == server.id and previous.configuration_revision == server.configuration_revision and previous.declaration_hash == tool.declaration_hash
        if confirmations.get(tool_ref) != tool.declaration_hash and (tool_ref in confirmations or not still_confirmed):
            raise MCPError("binding_review_required")
        prepared.append(dict(tool_ref=tool_ref, server_id=server.id, configuration_revision=server.configuration_revision, declaration_hash=tool.declaration_hash))
    return prepared

def replace_bindings(skill, prepared):
    SkillMCPBinding.query.filter_by(skill_id=skill.id).delete(synchronize_session=False)
    db.session.add_all(SkillMCPBinding(skill_id=skill.id, **item) for item in prepared)

def binding_payload(skill):
    result = []
    for binding in SkillMCPBinding.query.filter_by(skill_id=skill.id).order_by(SkillMCPBinding.id):
        _, _, reason = resolve_binding(binding, skill.class_id)
        result.append({"ref": binding.tool_ref, "declaration_hash": binding.declaration_hash, "status": reason or "ready"})
    return result
