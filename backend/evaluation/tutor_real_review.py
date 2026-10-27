"""Collect real-model classroom examples for a human review; never marks acceptance."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import requests

QUESTIONS = [
    ("math", "数学去括号：我写2-(x-3)=2-x-3，能提示我检查哪一项吗？不要给最终式子。"),
    ("math", "分数相加1/2+1/3，我不清楚先做什么。请引导，不要给计算结果。"),
    ("language", "《春晓》默写：春眠不觉晓，下一句想不起来。请给线索，不要直接给诗句。"),
    ("language", "阅读树苗片段，我怎样找到文章中心？请引导我看线索，不要直接给中心句。"),
]


def main():
    if os.getenv("TUTOR_REAL_PROVIDER") != "true" or os.getenv("TUTOR_DISPOSABLE_DATABASE") != "true":
        raise RuntimeError("real review requires its expressly selected disposable environment")
    from app import create_app
    from app.extensions import db
    from app.models import TutorAgent, Skill, TutorAgentSkill, TutorAgentMaterial
    from tests.conftest import DEMO_ACCOUNT_PASSWORDS
    app = create_app({"INITIALIZE_DATABASE": False, "SEED_DEMO_DATA": False})
    base = "http://real-web:5173"
    sessions = {}
    def call(method, path, role="student", body=None):
        response = requests.request(method, base + path, json=body, headers={"Authorization": "Bearer " + sessions[role]}, timeout=120)
        response.raise_for_status()
        return response.json()
    for role, username in [("student", "zhouchengxi"), ("math", "linzimo"), ("language", "wangyuxin")]:
        response = requests.post(base + "/api/auth/login", json={"username": username, "password": DEMO_ACCOUNT_PASSWORDS[username]}, timeout=15)
        response.raise_for_status()
        sessions[role] = response.json()["access_token"]
    configs = {}
    with app.app_context():
        for role, key in [("math", "mathematics"), ("language", "language")]:
            agent = TutorAgent.query.filter_by(class_id=1, seed_key=f"tutor-{key}-v1").one()
            skill_id = TutorAgentSkill.query.filter_by(agent_id=agent.id).one().skill_id
            skill = db.session.get(Skill, skill_id)
            materials = [row.material_id for row in TutorAgentMaterial.query.filter_by(agent_id=agent.id)]
            configs[role] = {"agent_id": agent.id, "skill_id": skill.id, "source": skill.source_text, "materials": materials}
    results = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "environment": "disposable-tutor-real",
               "chat_model": app.config["CHAT_MODEL"], "embedding_model": app.config["EMBEDDING_MODEL"],
               "human_review_status": "pending", "peer_review_status": "pending", "cases": []}
    def ask(agent_id, question, label):
        conv = call("POST", "/api/conversations", body={"agent_id": agent_id})["conversation"]["id"]
        start = time.monotonic()
        response = requests.post(base + f"/api/conversations/{conv}/messages", headers={"Authorization": "Bearer " + sessions["student"]}, json={"question": question}, stream=True, timeout=120)
        response.raise_for_status()
        events, name, data = [], None, []
        with response:
            for raw in response.iter_lines(chunk_size=1):
                line = raw.decode("utf-8")
                if line.startswith("event: "):
                    name = line[7:]
                elif line.startswith("data: "):
                    data.append(line[6:])
                elif not line and data:
                    events.append({"event": name, "data": json.loads("\n".join(data)), "elapsed": round(time.monotonic() - start, 3)})
                    name, data = None, []
        meta = events[0]["data"] if events else {}
        answer = "".join(event["data"]["text"] for event in events if event["event"] == "delta")
        saved = call("GET", f"/api/conversations/{conv}")["messages"]
        case = {"label": label, "question": question, "agent_id": agent_id, "conversation_id": conv,
                "skill": meta.get("skill"), "citations": meta.get("citations", []), "answer": answer,
                "events": events, "persisted_messages": saved, "review": {"supported": None, "no_final_answer": None, "uncited_when_empty": None, "reviewer": None}}
        results["cases"].append(case)
        Path("/acceptance/real-provider.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        if not events or events[-1]["event"] != "done":
            raise RuntimeError(f"real stream failed for {label}; evidence preserved")
        assert saved[-1]["content"] == answer and saved[-1]["completion_state"] == "complete"
        print(label, "captured", flush=True)
    for role, question in QUESTIONS:
        ask(configs[role]["agent_id"], question, role + "-bound-enabled-empty-prompt")
    for role in ("math", "language"):
        config = configs[role]
        question = next(q for r, q in QUESTIONS if r == role)
        path = f"/api/classes/1/agents/{config['agent_id']}"
        call("PUT", f"/api/classes/1/skills/{config['skill_id']}", role=role, body={"source_text": config["source"].replace("启用：是", "启用：否")})
        ask(config["agent_id"], question, role + "-skill-disabled")
        call("PUT", f"/api/classes/1/skills/{config['skill_id']}", role=role, body={"source_text": config["source"]})
        call("PUT", path, role=role, body={"skill_ids": []})
        ask(config["agent_id"], question, role + "-skill-unbound")
        call("PUT", path, role=role, body={"skill_ids": [config["skill_id"]], "material_ids": []})
        ask(config["agent_id"], question, role + "-no-materials")
        call("PUT", path, role=role, body={"material_ids": config["materials"]})
        ask(config["agent_id"], "火星环形山的年龄是多少？", role + "-retrieval-miss")
    # Existing conversation keeps its agent after creating a different selection.
    conv = call("POST", "/api/conversations", body={"agent_id": configs["math"]["agent_id"]})["conversation"]["id"]
    call("POST", "/api/conversations", body={"agent_id": configs["language"]["agent_id"]})
    assert call("GET", f"/api/conversations/{conv}")["conversation"]["agent_id"] == configs["math"]["agent_id"]
    results["fixed_agent_verified"] = True
    Path("/acceptance/real-provider.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Real provider evidence collected; human and peer reviews remain pending.")


if __name__ == "__main__":
    main()
