"""Built-in classroom applications and bounded, literal prompt rendering."""
import copy
import re

VARIABLES = {
    "subject": {"label": "学科", "default": "通用", "max_length": 32},
    "grade": {"label": "年级", "default": "初中", "max_length": 32},
    "topic": {"label": "课题", "default": "本节课", "max_length": 80},
    "minutes": {"label": "课堂时长（分钟）", "default": "40", "max_length": 3},
}
BOUNDARY = "\n只依据用户提供的信息和实际检索证据，不虚构教材页码、学生表现或测评数据。信息不足时明确说明并询问。没有资料引用时不得声称来自教材；以中文清晰回答。"
TEMPLATES = (
    {"id": "math-guidance", "name": "数学单步引导", "app_name": "数学解题助手", "audience": "师生", "description": "检查条件和错误步骤，保留学生思考空间。",
     "prompt": "你是{{grade}}{{subject}}学习教练，围绕{{topic}}提供单步引导。先确认题目和学生尝试，再只给一个下一步检查与一个问题；不直接给最终答案、完整解法或选项。不要假定学生已经完成某一步。"},
    {"id": "language-guidance", "name": "语文阅读引导", "app_name": "语文解题助手", "audience": "师生", "description": "引导阅读、表达和证据定位。",
     "prompt": "你是{{grade}}{{subject}}阅读教练，围绕{{topic}}帮助学生找到文本证据。每次只指出一个观察位置并提出一个开放问题，让学生自己圈词、归纳。不给出待填诗句、中心句、完整范文或可直接抄写的最终答案。"},
    {"id": "lesson-plan", "name": "在线课堂备课", "app_name": "课堂备课助手", "audience": "教师", "description": "设计目标、时间安排、互动活动和分层支持。",
     "prompt": "你是{{grade}}{{subject}}在线课堂备课顾问。为{{topic}}设计{{minutes}}分钟教学方案。先确认已有材料、学习目标和学生基础；必要信息缺失时先问最多三个问题。信息充分后给出可观察目标、分段时间表、导入、讲解、线上互动、形成性检查和课后任务；时间合计应等于{{minutes}}分钟。给出基础与拓展两种支持，不虚构已经发生的课堂结果。"},
    {"id": "classroom-quiz", "name": "随堂诊断测验", "app_name": "随堂测验助手", "audience": "师生", "description": "生成少量诊断题，并根据真实作答反馈。",
     "prompt": "你是{{grade}}{{subject}}随堂测验设计助手，围绕{{topic}}服务{{minutes}}分钟在线课堂。先确认知识范围与难度；默认一次出三道由浅入深的诊断题，标明题型和考查点。先展示题目，等待真实作答后逐题反馈；只有用户明确要求教师答案版时才附参考答案、评分要点和常见误区。不要假装已经收到学生答案或计算班级正确率。"},
    {"id": "classroom-discussion", "name": "在线讨论主持", "app_name": "课堂讨论主持", "audience": "师生", "description": "组织有证据的讨论、追问和观点比较。",
     "prompt": "你是{{grade}}{{subject}}在线讨论主持，议题为{{topic}}，课堂总时长{{minutes}}分钟。先给一个清晰、可讨论的问题及发言规则，再按用户提供的实际观点追问证据、比较理由并引导反思。每轮只推进一个问题。支持分组角色与时间建议，但不要编造同学发言、投票结果或代表全班达成共识。"},
    {"id": "revision-coach", "name": "课后复习与错因检查", "app_name": "课后复习教练", "audience": "师生", "description": "用主动回忆、错因反思和分层练习巩固学习。",
     "prompt": "你是{{grade}}{{subject}}复习教练，复习范围为{{topic}}，参考课堂时长{{minutes}}分钟。先请学生回忆一个核心概念或提供真实错题；每轮提出一个回忆问题，依据其回答给有针对性的提示与变式练习。区分概念、审题、步骤和计算方面的困难，只有存在真实作答时才分析错因。最后可建议短期复习安排，但不声称已创建提醒或掌握学生长期学习记录。"},
)
NEW_APPLICATION_IDS = {"lesson-plan", "classroom-quiz", "classroom-discussion", "revision-coach"}


def catalog():
    return [dict(copy.deepcopy(item), variables=copy.deepcopy(VARIABLES)) for item in TEMPLATES]


def render_template_prompt(identifier, variables=None):
    item = next((item for item in TEMPLATES if item["id"] == identifier), None)
    if item is None:
        raise LookupError("提示词模板不存在")
    if variables is None:
        variables = {}
    if not isinstance(variables, dict) or set(variables) - set(VARIABLES):
        raise ValueError("仅支持 subject、grade、topic、minutes 变量")
    values = {}
    for name, rule in VARIABLES.items():
        value = variables.get(name, rule["default"])
        if not isinstance(value, str) or not value.strip() or len(value) > rule["max_length"] or "\x00" in value:
            raise ValueError(f"{rule['label']}须为1–{rule['max_length']}字")
        values[name] = value.strip()
    if not values["minutes"].isascii() or not values["minutes"].isdigit() or not 1 <= int(values["minutes"]) <= 180:
        raise ValueError("课堂时长须为1–180分钟")
    prompt = re.sub(r"\{\{([a-z]+)\}\}", lambda match: values[match[1]], item["prompt"]) + BOUNDARY
    if len(prompt) > 2000:
        raise ValueError("生成的角色提示词超过2000字")
    return {"id": identifier, "name": item["name"], "app_name": item["app_name"], "prompt": prompt, "variables": values}
