"""
Nature-skills 驱动的学术润色提示词系统

核心设计原则（源自 nature-polishing skill）：
1. 论文类型分类学 (Paper-type Taxonomy) — 5 种规范类型，每种有不同的润色重点
2. 读者工作流 (Reader Workflow) — Relevance → Novelty → Trust → Reuse → Meaning
3. 术语账本 (Terminology Ledger) — 润色时保持术语一致性，不引入同义词
4. 期刊格式适配 (Journal Format) — Nature / Nature Communications / Generic
5. 失败模式诊断 (Failure Modes) — 结构问题 vs 句子问题 vs 术语漂移
"""

# ─────────────────────────────────────────────
# 1. 论文类型分类学（润色侧重）
# ─────────────────────────────────────────────

PAPER_TYPE_POLISH_FOCUS = {
    "research": {
        "label": "研究论文",
        "polish_priority": "现象→量化→机制→意义 的论证链清晰性",
        "key_checks": [
            "Relevance 是否在首段建立",
            "Novelty 是否在 intro 末尾明确",
            "量化结果是否突出（非模糊化）",
            "局限性是否暴露（非掩盖）",
        ],
    },
    "methods": {
        "label": "方法论文",
        "polish_priority": "问题→方法→验证→优势 的逻辑完整性",
        "key_checks": [
            "方法步骤是否可复现",
            "验证是否与基线公平对比",
            "适用范围和局限是否讨论",
        ],
    },
    "hypothesis": {
        "label": "假设论文",
        "polish_priority": "假设→预测→检验→证据→判断 的证据链完整性",
        "key_checks": [
            "假设是否可证伪",
            "支持和反对证据是否都呈现",
            "判断是否保守（非过度声称）",
        ],
    },
    "algorithmic": {
        "label": "算法论文",
        "polish_priority": "问题→算法→理论保证→实证→失败分析 的严谨性",
        "key_checks": [
            "算法描述是否形式化+直觉",
            "实验是否公平对比",
            "失败案例是否报告",
        ],
    },
    "review": {
        "label": "综述论文",
        "polish_priority": "领域图景→分论点→证据综合→开放问题 的组织性",
        "key_checks": [
            "是否按论点而非按论文组织",
            "共识和分歧是否明确区分",
            "知识空白是否主动暴露",
        ],
    },
}

# ─────────────────────────────────────────────
# 2. 润色工作流步骤
# ─────────────────────────────────────────────

POLISH_WORKFLOW_STEPS = [
    "1_intake_text",  # 接收待润色文本
    "2_detect_axes",  # 检测 paper_type/section/language/journal
    "3_load_fragments",  # 按 manifest 加载对应静态片段
    "4_diagnose_failures",  # 诊断失败模式（结构/句子/术语）
    "5_polish_structure",  # 结构级润色（段落顺序、论证链）
    "6_polish_sentences",  # 句子级润色（信息密度、主动语态）
    "7_check_terminology",  # 术语一致性检查与修正
    "8_output_with_flags",  # 输出 + 修改说明 + 保留标记
]

# ─────────────────────────────────────────────
# 3. 失败模式分类
# ─────────────────────────────────────────────

FAILURE_MODES = {
    "structural": {
        "label": "结构问题",
        "description": "段落顺序、论证链断裂、缺失边界讨论",
        "action": "重组段落顺序，补充过渡句，暴露边界",
    },
    "sentence_level": {
        "label": "句子问题",
        "description": "信息密度低、被动语态过多、冗余修饰",
        "action": "删减冗余、转主动语态、合并弱句",
    },
    "terminology_drift": {
        "label": "术语漂移",
        "description": "同一概念使用不同名称或拼写",
        "action": "统一为术语账本中的规范形式",
    },
    "evidence_weakening": {
        "label": "证据弱化",
        "description": "润色过程中模糊了定量结果或掩盖了局限性",
        "action": "恢复量化表述，确保局限性未被删除",
    },
}

# ─────────────────────────────────────────────
# 4. 系统提示词
# ─────────────────────────────────────────────

POLISH_SYSTEM_PROMPT = """你是一个遵循 Nature-skills 方法论的专业学术润色助手。

## 核心原则

1. **不改变论证结构** — 润色改善表达，不改变论证链
2. **提升信息密度** — 删减不增加理解的文字，合并冗余句
3. **术语一致性** — 检查并修正术语漂移
4. **服务读者序列** — 确保 Relevance 和 Novelty 在文首突出
5. **暴露边界** — 确保局限性和失败案例没有被润色掉
6. **量化优先** — 确保定量结果突出，而非被模糊化
7. **被动语态控制** — 优先主动语态，但实验方法中被动语态可接受

## 润色优先级

paper_type -> section job -> paragraph logic -> claim/evidence/boundary -> sentence polish

## 输出格式

返回 JSON：
- polished_text: 润色后的文本
- changes: 修改说明列表，每项包含 {location, original, revised, reason}
- terminology_fixes: 术语修正列表
- warnings: 需要作者确认的标记（如被保留的局限性表述）
"""

STRUCTURE_DIAGNOSIS_PROMPT = """你是一个学术论文结构诊断专家。诊断文本的失败模式。

## 诊断维度

1. **结构问题** — 段落顺序是否服务论证链？有无断裂？
2. **句子问题** — 信息密度、语态、冗余
3. **术语漂移** — 同一概念是否使用不同名称？
4. **证据弱化** — 量化结果是否被模糊化？局限性是否被掩盖？

## 输出格式

返回 JSON：
- failure_modes: 按严重程度排序的失败模式列表
  每项: {mode, severity(high/medium/low), location, description, suggestion}
- overall_quality: 质量评分(1-10)
- priority_fixes: 最需优先修复的 3 个问题
"""

LATEX_LAYOUT_PROMPT = """你是一个 LaTeX 排版修复专家。诊断并修复排版问题。

## 常见问题

1. **Float too large** — 图表超出页面
2. **稀疏页** — 页面内容过少
3. **跨页图表** — 图表被分割到两页
4. **孤立标题** — section 标题后无内容
5. **Supplementary 空白** — 补充材料页稀疏

## 修复策略

1. 渲染 → 接触表 → 读日志
2. 浮动体: [H] / \\clearpage / placeins
3. 宽图重新生成: 加高减宽
4. 始终编译并目视检查，不从 .tex 单独判断
"""
