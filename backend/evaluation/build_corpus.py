"""Authoring tool. Frozen release labels must not be changed to fit model results."""
import json
from pathlib import Path

# fact, distributed terms, independent paraphrase, answer question
FACTS = [
 ("细胞是生物体结构和功能的基本单位。", "结构 功能 基本单位", "生物身体最基础的构成和运作单元是什么", "细胞在生物体中是什么单位？"),
 ("叶绿体是绿色植物进行光合作用的主要场所。", "绿色植物 光合作用 场所", "植物靠阳光制造养料主要在哪个细胞器完成", "光合作用主要在何处进行？"),
 ("线粒体为细胞的生命活动提供能量。", "线粒体 生命活动 能量", "细胞靠哪种细胞器获得活动所需动力", "线粒体有什么作用？"),
 ("细胞膜能控制物质进出细胞。", "细胞膜 控制 进出", "细胞边界上哪一层负责调节物质出入", "细胞膜的功能是什么？"),
 ("遗传信息主要储存在细胞核中。", "遗传信息 储存 细胞核", "细胞的遗传资料主要存放在哪个部位", "遗传信息主要存在哪里？"),
 ("蒸腾作用能促进植物对水分的吸收和运输。", "蒸腾作用 水分 运输", "植物散失水汽如何影响吸水和水在体内的移动", "蒸腾作用对水分有什么影响？"),
 ("光合作用把二氧化碳和水转化为有机物，并释放氧气。", "二氧化碳 有机物 氧气", "植物利用光时消耗哪些原料产出哪些物质", "光合作用会释放什么气体？"),
 ("呼吸作用分解有机物，释放能量。", "呼吸作用 有机物 能量", "生物通过哪种过程拆解养料获得动力", "呼吸作用如何获得能量？"),
 ("根尖的成熟区是根吸收水和无机盐的主要部位。", "根尖 吸收 无机盐", "植物根部哪个区域主要负责摄取水及矿质", "根吸收水和无机盐的主要部位在哪？"),
 ("导管负责在植物体内运输水和无机盐。", "导管 植物体 运输", "植物体内水和矿质经哪种管道输送", "导管运输哪些物质？"),
 ("同种电荷相互排斥，异种电荷相互吸引。", "同种电荷 排斥 异种电荷", "两个带相同电性的物体靠近后会怎样", "同种电荷之间有什么作用？"),
 ("电流方向规定为正电荷定向移动的方向。", "电流方向 正电荷 定向移动", "约定的电流朝向以哪种电荷的运动为准", "电流方向如何规定？"),
 ("串联电路中各处电流相等。", "串联电路 各处 电流", "串接元件的线路各位置流过的电流是否一样", "串联电路的电流有什么特点？"),
 ("并联电路中各支路两端的电压相等。", "并联电路 支路 电压", "并接的各分支两端电势差有何关系", "并联支路的电压有什么关系？"),
 ("物体受到的重力方向总是竖直向下。", "重力 方向 竖直", "地球对物体的吸引力朝哪个方向", "重力方向是什么？"),
 ("惯性是物体保持原来运动状态的性质。", "惯性 运动状态 性质", "物体维持原有静止或运动状态的特性叫什么", "什么是惯性？"),
 ("声音的传播需要介质，真空不能传声。", "声音 介质 真空", "没有任何物质的空间里能否听到传来的声音", "真空能否传播声音？"),
 ("光在均匀介质中沿直线传播。", "光 均匀介质 直线", "光线在性质一致的物质中走什么路径", "光在均匀介质中如何传播？"),
 ("凸透镜对光有会聚作用。", "凸透镜 光 会聚", "凸形镜片会使平行光束聚拢还是散开", "凸透镜对光有什么作用？"),
 ("物体的密度等于质量与体积之比。", "密度 质量 体积", "用质量除以所占空间得到什么物理量", "如何计算物体密度？"),
 ("酸溶液的pH小于7。", "酸溶液 pH 7", "酸性液体的酸碱度数值位于七的哪一侧", "酸溶液的pH有什么特点？"),
 ("碱溶液的pH大于7。", "碱溶液 pH 7", "碱性液体的酸碱度数值比七高还是低", "碱溶液的pH有什么特点？"),
 ("催化剂能改变反应速率，自身质量和化学性质在反应前后不变。", "催化剂 速率 质量", "促进或减慢化学过程但反应前后自身质量不变的物质叫什么", "催化剂的特点是什么？"),
 ("铁生锈需要同时接触氧气和水。", "铁 生锈 氧气 水", "铁发生锈蚀须具备哪两个共同条件", "铁生锈需要什么条件？"),
 ("质量守恒定律适用于化学反应。", "质量守恒 化学反应", "化学变化前后反应物与生成物总质量遵循什么规律", "质量守恒定律适用于什么过程？"),
 ("三角形内角和等于180度。", "三角形 内角 180", "三角形三个内部角加起来是多少", "三角形内角和是多少？"),
 ("平行四边形的对边平行且相等。", "平行四边形 对边 相等", "平行四边形相对的两条边有何位置和长度关系", "平行四边形的对边有什么特点？"),
 ("一次函数的图像是一条直线。", "一次函数 图像 直线", "一元一次函数画在坐标系里是什么形状", "一次函数的图像是什么？"),
 ("圆的周长等于直径乘以圆周率。", "圆 周长 直径 圆周率", "已知圆的直径应怎样求它边界的长度", "如何由直径计算圆周长？"),
 ("平均数等于数据总和除以数据个数。", "平均数 总和 个数", "把一组数加起来再按数量均分得到什么统计量", "平均数如何计算？"),
]
EXTRA_PARAPHRASES = ["活物结构和生命功能的最小基础是什么", "叶绿体与植物利用日光合成养分有何关系", "生命活动的动力由线粒体如何供给", "物质能否进入细胞由哪层结构管控", "遗传指令在细胞哪里集中保存", "植物把水分变成水汽散发对水的输送有何帮助", "植物造有机物时会把什么气体放出来", "把储存的有机养料分解来供能称为什么", "根上主要吸取矿质和水的地方叫什么", "水和矿质在植物内部的输送通路叫什么"]
UNRELATED = ["火星移民基地如何供暖", "股票明天会涨吗", "给我一份旅行行程", "贝多芬第九交响曲的指挥是谁", "云计算集群怎样自动扩容", "护照到期如何换发", "烤面包的配方有哪些", "区块链共识协议如何工作", "台风下周在哪里登陆", "给猫取一个名字", "编写快速排序程序", "电影票什么时候预售", "查询航班实时延误", "帮我设计咖啡店标志", "海底电缆是谁铺设的", "解释国际贸易关税", "推荐一款跑鞋", "今天的新闻头条", "书法作品怎样装裱", "量子纠缠实验如何搭建"]
ADVERSARIAL = ["遗传信息主要存在细胞膜吗", "线粒体主要用于光合作用吗", "同种电荷是否相互吸引", "异种电荷是否相互排斥", "真空能够传播声音吗", "重力总是水平向右吗", "酸溶液的pH大于7吗", "碱溶液的pH小于7吗", "三角形内角和是360度吗", "凸透镜会使光发散吗", "惯性会随速度改变吗", "只有氧气没有水铁必定生锈吗", "导管主要运输糖吗", "细胞核调节物质进出吗", "呼吸作用制造有机物吗", "串联电路各处电流不同吗", "并联支路电压总是不等吗", "密度是体积除以质量吗", "圆周长等于直径除以圆周率吗", "平均数等于总和乘以个数吗"]


def build():
    materials, cases = [], []
    for i, (fact, terms, paraphrase, question) in enumerate(FACTS):
        ident = f"release-{i + 1:02d}"
        text = "学习资料。\n\n" + fact + "\n请结合实验观察理解以上知识。"
        subject = ["biology", "physics", "chemistry", "math"][0 if i < 10 else 1 if i < 20 else 2 if i < 25 else 3]
        material = {"id": ident, "class": "A", "subject": subject, "title": f"知识点{i + 1}", "text": text, "split": "release"}
        materials.append(material)
        label = {"material": ident, "start": text.index(fact), "end": text.index(fact) + len(fact), "quote": fact}
        for category, query in [("exact", fact), ("distributed", terms), ("paraphrase", paraphrase), ("answer", question)]:
            cases.append({"id": f"{category}-{i + 1:02d}", "split": "release", "category": category, "query": query, "scope": {"class": "A", "subjects": [subject]}, "labels": [label]})
        if i < 10:
            cases.append({"id": f"paraphrase-{i + 31:02d}", "split": "release", "category": "paraphrase", "query": EXTRA_PARAPHRASES[i], "scope": {"class": "A", "subjects": [subject]}, "labels": [label]})
    for category, queries in [("unrelated", UNRELATED), ("adversarial", ADVERSARIAL)]:
        for i, query in enumerate(queries):
            cases.append({"id": f"{category}-{i + 1:02d}", "split": "release", "category": category, "query": query, "scope": {"class": "A", "subjects": ["biology", "physics", "chemistry", "math"]}, "labels": [], "review_required": category == "adversarial"})
    supporting = [4, 2, 10, 10, 16, 14, 20, 21, 25, 18, None, 23, 9, 3, 7, 12, 13, 19, 28, 29]
    for i, fact_index in enumerate(supporting):
        case = next(c for c in cases if c["id"] == f"adversarial-{i + 1:02d}")
        if fact_index is not None:
            reference = next(c for c in cases if c["id"] == f"answer-{fact_index + 1:02d}")
            case["labels"] = reference["labels"]
            case["reference_fact"] = FACTS[fact_index][0]
        else:
            case["reference_fact"] = "资料只有惯性的定义，未说明惯性与速度的关系。"
        case["can_answer"] = fact_index is not None
        case["expected_status"] = "answered" if fact_index is not None else "insufficient"
    for i in range(20):
        material = materials[i]
        cases.append({"id": f"permission-{i + 1:02d}", "split": "release", "category": "permission", "query": FACTS[i][0], "scope": {"class": "B" if i < 10 else "A", "subjects": [material["subject"]] if i < 10 else ["math"]}, "actor_role": "student" if i < 10 else "teacher", "labels": [], "denied_materials": [material["id"]], "paths": ["keyword", "vector", "hybrid", "ask", "detail", "preview", "retry"]})
    dev = [("水沸腾时温度保持不变。", "水 沸腾 温度", "水烧开之后继续加热温度会怎样"), ("淀粉遇碘液变蓝。", "淀粉 碘液 蓝", "用碘检验淀粉应观察到什么颜色"), ("力可以改变物体的形状。", "力 物体 形状", "施力能否使物体变形"), ("种子萌发需要适宜的温度。", "种子 萌发 温度", "种子发芽对冷热有什么要求"), ("长方形的四个角都是直角。", "长方形 四个角 直角", "长方形的每个内角是多少度"), ("二氧化碳能使澄清石灰水变浑浊。", "二氧化碳 石灰水 浑浊", "通入二氧化碳如何改变澄清石灰水"), ("平面镜成等大的虚像。", "平面镜 等大 虚像", "人在平面镜中的像大小和性质如何"), ("骨骼肌收缩能牵动骨产生运动。", "骨骼肌 收缩 运动", "肌肉缩短如何带来骨的活动")]
    for i, (fact, terms, query) in enumerate(dev):
        ident = f"dev-{i + 1:02d}"
        materials.append({"id": ident, "class": "D", "subject": "science", "title": ident, "text": fact, "split": "dev"})
        for category, value in [("exact", fact), ("distributed", terms), ("paraphrase", query)]:
            cases.append({"id": f"dev-{category}-{i + 1:02d}", "category": category, "split": "dev", "query": value, "scope": {"class": "D", "subjects": ["science"]}, "labels": [{"material": ident, "start": 0, "end": len(fact), "quote": fact}]})
    for case in cases:
        case.setdefault("can_answer", bool(case["labels"]))
        case.setdefault("expected_status", "answered" if case["can_answer"] else "no_evidence")
        case.setdefault("reference_fact", "；".join(label["quote"] for label in case["labels"]))
    return {"version": "1.0.1", "offset_unit": "unicode_code_point", "materials": materials, "cases": cases}


if __name__ == "__main__":
    Path(__file__).with_name("corpus-v1.json").write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
