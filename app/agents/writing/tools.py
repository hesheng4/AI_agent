import re
from typing import Any

from app.utils.exceptions import ToolException
from app.utils.logger import get_logger

logger = get_logger("tools.writing")


class WritingTools:
    """Nature-skills 驱动的学术写作工具集"""

    # 论文类型分类（源自 paper-type-taxonomy.md）
    PAPER_TYPES = {
        "research": {
            "label": "研究论文",
            "definition": "报告通过观察或实验发现的现象、机制或结果",
            "reader_question": "发现了什么？这意味着什么？",
            "core_chain": "现象→量化→机制→意义",
            "drafting_order": [
                "results",
                "methods",
                "introduction",
                "discussion",
                "conclusion",
            ],
        },
        "methods": {
            "label": "方法论文",
            "definition": "提出新方法、协议或测量手段，并证明其优势",
            "reader_question": "它管用吗？更好吗？可复现吗？",
            "core_chain": "问题→方法→验证→优势",
            "drafting_order": [
                "methods_description",
                "validation",
                "introduction",
                "discussion",
            ],
        },
        "hypothesis": {
            "label": "假说论文",
            "definition": "通过针对性证据建立或排除因果解释",
            "reader_question": "所提机制是正确的吗？",
            "core_chain": "假设→预测→检验→证据→判断",
            "drafting_order": [
                "hypothesis_statement",
                "predictions",
                "evidence",
                "introduction",
                "discussion",
            ],
        },
        "algorithmic": {
            "label": "算法论文",
            "definition": "提出算法、模型、系统或设备，展示其可靠性和优势",
            "reader_question": "在公平对比下性能如何？哪里会失败？",
            "core_chain": "问题→算法→理论保证→实证验证→失败分析",
            "drafting_order": [
                "algorithm",
                "experiments",
                "introduction",
                "theory",
                "discussion",
            ],
        },
        "review": {
            "label": "综述论文",
            "definition": "综合领域现状，按论点而非论文组织文献",
            "reader_question": "已知什么？分歧在哪？什么是开放的？",
            "core_chain": "领域图景→分论点→证据综合→开放问题",
            "drafting_order": [
                "framework",
                "evidence_synthesis",
                "introduction",
                "open_questions",
            ],
        },
    }

    # 学术写作常见问题
    COMMON_ISSUES = {
        r"\b(very|really|basically|actually|literally)\b": "口语化词汇，建议删除或替换",
        r"\b(a lot of|lots of)\b": "口语化表达，建议用 many/much 替换",
        r"\b(stuff|things)\b": "模糊词汇，建议用具体名词",
        r"\b(get|got)\b": "口语化动词，建议用 obtain/acquire/receive 替换",
        r"\b(gonna|wanna|gotta)\b": "非正式缩写，学术写作中不应使用",
        r"!!!+": "过多感叹号，学术写作中应谨慎使用",
        r"\.\.\.": "省略号，学术写作中应避免使用",
    }

    # 裸论断检测模式（没有证据支撑的断言）
    NAKED_CLAIM_PATTERNS = {
        r"\b(significant|notable|remarkable|substantial)\b(?!ly)": (
            "定性断言缺少定量证据"
        ),
        r"\b(obviously|clearly|evidently|it is well known)\b": (
            "无根据断言，需提供证据或引用"
        ),
        r"\b(proves? that|confirms? that|demonstrates? that)\b": (
            "强因果断言，需确认证据充分性"
        ),
        r"\b(the best|the most|superior)\b(?!ity)": "最高级断言，需公平对比证据",
    }

    # 学术连接词
    ACADEMIC_TRANSITIONS = {
        "addition": ["Furthermore", "Moreover", "In addition", "Additionally"],
        "contrast": ["However", "Nevertheless", "On the other hand", "Conversely"],
        "cause": ["Therefore", "Consequently", "As a result", "Thus"],
        "example": ["For instance", "For example", "Specifically", "In particular"],
        "conclusion": ["In conclusion", "To summarize", "Overall", "In summary"],
        "sequence": ["First", "Second", "Third", "Finally"],
    }

    # ─────────────────────────────────────────────
    # 论文类型大纲模板（Nature-skills 驱动）
    # ─────────────────────────────────────────────

    # 各类型标准章节模板
    TYPE_TEMPLATES = {
        "research": [
            {
                "title": "引言",
                "purpose": "建立相关性，从广泛背景收窄到具体问题，最后一段明确陈述发现",
                "key_points": [
                    "研究背景与领域定位",
                    "现有知识空白",
                    "本研究发现（Novelty）",
                    "论文结构概述",
                ],
                "subsections": ["研究背景", "知识空白", "研究目的与发现", "论文结构"],
            },
            {
                "title": "结果",
                "purpose": (
                    "核心章节，按逻辑而非时间顺序组织，每个子结果推进论证链的一步"
                ),
                "key_points": [
                    "主要发现（量化呈现）",
                    "次级发现",
                    "验证性结果",
                    "意外结果",
                ],
                "subsections": ["主要发现", "定量分析", "验证实验", "补充结果"],
            },
            {
                "title": "方法",
                "purpose": "服务Trust，足够复现即可，不堆砌",
                "key_points": ["实验设计", "数据采集", "分析方法", "可复现性细节"],
                "subsections": ["实验设计", "数据收集", "统计分析", "代码与数据可用性"],
            },
            {
                "title": "讨论",
                "purpose": "回答Meaning，解释结果、对比、暴露局限性、未来方向",
                "key_points": [
                    "结果解释",
                    "与已有工作对比",
                    "局限性（暴露边界）",
                    "未来方向",
                ],
                "subsections": ["结果解释", "文献对比", "研究局限", "未来方向"],
            },
            {
                "title": "结论",
                "purpose": "简洁重申核心发现和最广意义，不引入新论点",
                "key_points": ["核心发现", "最广意义"],
                "subsections": ["核心结论", "更广意义"],
            },
            {
                "title": "数据与代码可用性",
                "purpose": "服务Reuse，声明数据/代码/材料的可获取性与获取方式",
                "key_points": [
                    "数据可获取性",
                    "代码仓库",
                    "材料可获取性",
                    "可复现性声明",
                ],
                "subsections": ["数据可用性", "代码可用性", "材料与试剂"],
            },
        ],
        "methods": [
            {
                "title": "引言",
                "purpose": "明确现有方法的不足，建立Relevance和Novelty",
                "key_points": ["领域需求", "现有方法局限", "本方法创新"],
                "subsections": ["方法学需求", "现有方法不足", "本研究方法"],
            },
            {
                "title": "方法描述",
                "purpose": "核心章节，逐步协议，关键参数完整，复现性第一",
                "key_points": ["方法原理", "逐步协议", "关键参数", "质控措施"],
                "subsections": ["方法原理", "详细协议", "关键参数", "质量控制"],
            },
            {
                "title": "验证",
                "purpose": "与现有方法对比，报告灵敏度、特异性、鲁棒性",
                "key_points": ["对比基线", "灵敏度分析", "特异性评估", "鲁棒性测试"],
                "subsections": ["对比实验", "灵敏度", "特异性", "鲁棒性"],
            },
            {
                "title": "讨论",
                "purpose": "何时用此方法？何时不适用？暴露边界",
                "key_points": ["方法优势", "适用范围", "局限性", "与金标准比较"],
                "subsections": ["方法优势", "适用场景", "不适用场景", "与金标准对比"],
            },
        ],
        "hypothesis": [
            {
                "title": "引言",
                "purpose": "清晰陈述假设，解释重要性",
                "key_points": ["研究背景", "待检验假设", "假设的重要性"],
                "subsections": ["背景", "核心假设", "假设意义"],
            },
            {
                "title": "假设陈述",
                "purpose": "核心章节，假设必须可证伪，明确因果主张",
                "key_points": ["假设的形式化陈述", "可证伪性说明", "因果主张"],
                "subsections": ["假设定义", "可证伪条件", "因果链"],
            },
            {
                "title": "预测与检验",
                "purpose": "从假设推导可检验预测，逐一检验",
                "key_points": ["可检验预测", "实验设计", "每条预测的检验"],
                "subsections": ["预测推导", "实验设计", "检验结果"],
            },
            {
                "title": "证据评估",
                "purpose": "报告支持和不支持的证据",
                "key_points": ["支持性证据", "不支持证据", "证据质量"],
                "subsections": ["支持证据", "反对证据", "证据评估"],
            },
            {
                "title": "讨论",
                "purpose": "综合判断，证据链完整性，替代解释",
                "key_points": ["支持/排除判断", "证据链完整性", "替代解释"],
                "subsections": ["综合判断", "证据链分析", "替代解释"],
            },
        ],
        "algorithmic": [
            {
                "title": "引言",
                "purpose": "明确问题定义和基线，说明核心创新",
                "key_points": ["问题定义", "基线方法", "核心创新"],
                "subsections": ["问题定义", "现有方法", "本文贡献"],
            },
            {
                "title": "算法",
                "purpose": "核心章节，形式化描述+直觉解释",
                "key_points": ["形式化描述", "直觉解释", "伪代码/流程图"],
                "subsections": ["问题形式化", "算法描述", "伪代码"],
            },
            {
                "title": "理论分析",
                "purpose": "理论保证，没有则诚实说明",
                "key_points": ["复杂度分析", "收敛性", "理论保证或无保证声明"],
                "subsections": ["复杂度", "收敛性", "理论性质"],
            },
            {
                "title": "实验",
                "purpose": "公平对比，同一硬件/数据/划分，报告失败案例",
                "key_points": ["实验设置", "公平对比", "统计显著性", "失败案例"],
                "subsections": ["实验设置", "主实验", "消融实验", "失败分析"],
            },
            {
                "title": "讨论",
                "purpose": "适用范围和局限，何时优/劣于基线",
                "key_points": ["适用范围", "局限性", "计算成本"],
                "subsections": ["适用场景", "局限性", "计算成本"],
            },
        ],
        "review": [
            {
                "title": "引言",
                "purpose": "定义综述范围和读者群体，说明按论点组织",
                "key_points": ["综述范围", "目标读者", "组织方式"],
                "subsections": ["综述范围", "读者定位", "组织原则"],
            },
            {
                "title": "概念框架",
                "purpose": "核心章节，提出组织领域的框架，按论点分节",
                "key_points": ["领域图景", "核心分论点", "论点间关系"],
                "subsections": ["领域全景", "核心论点", "论点关系"],
            },
            {
                "title": "证据综合",
                "purpose": "综合多篇文献，指出共识、分歧、证据质量",
                "key_points": ["共识", "分歧", "证据质量", "方法论差异"],
                "subsections": ["领域共识", "核心分歧", "证据评估"],
            },
            {
                "title": "开放问题",
                "purpose": "暴露知识空白，提出具体未来方向",
                "key_points": ["知识空白", "方法论局限", "未来方向"],
                "subsections": ["知识空白", "方法局限", "未来方向"],
            },
        ],
    }

    # Nature Communications 字数预算
    NATCOMMS_WORD_BUDGET = {
        "research": {
            "total": 5000,
            "introduction": 800,
            "results": 1500,
            "methods": 1200,
            "discussion": 1200,
            "conclusion": 300,
        },
        "methods": {
            "total": 5000,
            "introduction": 600,
            "methods_description": 1800,
            "validation": 1200,
            "discussion": 1400,
        },
        "hypothesis": {
            "total": 5000,
            "introduction": 600,
            "hypothesis_statement": 800,
            "predictions": 800,
            "evidence": 1200,
            "discussion": 1600,
        },
        "algorithmic": {
            "total": 5000,
            "introduction": 600,
            "algorithm": 1000,
            "theory": 800,
            "experiments": 1400,
            "discussion": 1200,
        },
        "review": {
            "total": 6000,
            "introduction": 600,
            "framework": 1800,
            "evidence_synthesis": 2400,
            "open_questions": 1200,
        },
    }

    @staticmethod
    def create_outline_template(
        topic: str,
        paper_type: str = "research",
        journal: str = "standard",
        sections: int | None = None,
    ) -> dict[str, Any]:
        """根据论文类型创建结构化大纲模板（Nature-skills 驱动）

        Args:
            topic: 论文主题
            paper_type: 论文类型（research/methods/hypothesis/algorithmic/review）
            journal: 期刊风格（standard / nat-comms）
            sections: 指定章节数量；为 None 时使用类型默认全部章节，
                      为正整数时按顺序截取前 N 节
        """
        logger.info(
            f"创建大纲: {topic}, 类型={paper_type}, 期刊={journal}, sections={sections}"
        )

        # 验证论文类型
        if paper_type not in WritingTools.PAPER_TYPES:
            paper_type = "research"

        type_info = WritingTools.PAPER_TYPES[paper_type]
        all_sections = WritingTools.TYPE_TEMPLATES.get(
            paper_type, WritingTools.TYPE_TEMPLATES["research"]
        )

        # 按需截取章节数量
        if sections is not None:
            if not isinstance(sections, int) or sections <= 0:
                raise ToolException(
                    "sections 必须为正整数", tool_name="create_outline_template"
                )
            used_sections = all_sections[:sections]
        else:
            used_sections = all_sections

        # 字数预算
        word_budget = WritingTools.NATCOMMS_WORD_BUDGET.get(
            paper_type, WritingTools.NATCOMMS_WORD_BUDGET["research"]
        )
        if journal != "nat-comms":
            # 通用学术格式，稍宽松
            word_budget = {k: int(v * 1.3) for k, v in word_budget.items()}

        total_words = word_budget.get("total", 5000)
        # 按每页约 500 词估算页数
        estimated_pages = max(1, round(total_words / 500))
        # 字数浮动范围 ±10%
        word_count_range = [int(total_words * 0.9), int(total_words * 1.1)]

        return {
            "title": topic,
            "paper_type": paper_type,
            "paper_type_label": type_info["label"],
            "core_chain": type_info["core_chain"],
            "reader_question": type_info["reader_question"],
            "drafting_order": type_info["drafting_order"],
            "sections": used_sections,
            "word_budget": word_budget,
            "estimated_pages": estimated_pages,
            "word_count_range": word_count_range,
            "reader_workflow": {
                "1_relevance": "引言前两段",
                "2_novelty": "引言末段 + 结果首段",
                "3_trust": "方法 + 统计细节",
                "4_reuse": "方法可复现性 + 数据/代码可用性",
                "5_meaning": "讨论 + 局限性",
            },
            "journal": journal,
        }

    @staticmethod
    def detect_paper_type(content: str) -> dict[str, Any]:
        """从文本内容推断论文类型"""
        logger.info(f"推断论文类型，文本长度: {len(content)}")

        content_lower = content.lower()

        # 检测信号
        signals = {
            "hypothesis": [
                r"\b(hypothes[ie]s|假设|mechanism|causal|因果关系)\b",
                r"\b(predict|prediction|可证伪|falsif)\b",
            ],
            "algorithmic": [
                r"\b(algorithm|model|neural network|deep learning|算法|模型)\b",
                r"\b(perform|accuracy|baseline|ablation|性能|对比)\b",
                r"\b(complexity|收敛|convergence)\b",
            ],
            "methods": [
                r"\b(method|protocol|protocol|assay|方法|协议)\b",
                r"\b(sensitivity|specificity|reproducibility|灵敏度|特异性)\b",
                r"\b(validat|验证|benchmark)\b",
            ],
            "review": [
                r"\b(review|survey|综述|overview|systematic review)\b",
                r"\b(state.of.the.art|recent advances|文献)\b",
            ],
        }

        scores = {}
        for ptype, patterns in signals.items():
            score = 0
            for pattern in patterns:
                matches = re.findall(pattern, content_lower)
                score += len(matches)
            scores[ptype] = score

        # 默认 research
        best_type = (
            max(scores, key=scores.get) if max(scores.values()) > 0 else "research"
        )

        return {
            "detected_type": best_type,
            "scores": scores,
            "confidence": scores[best_type] / max(sum(scores.values()), 1),
            "type_info": WritingTools.PAPER_TYPES[best_type],
        }

    @staticmethod
    def check_grammar(text: str) -> list[dict[str, str]]:
        """检查语法和写作问题"""
        logger.info(f"检查语法，文本长度: {len(text)}")

        issues = []

        # 检查常见问题
        for pattern, message in WritingTools.COMMON_ISSUES.items():
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end]

                issues.append(
                    {
                        "type": "style",
                        "word": match.group(),
                        "message": message,
                        "position": match.start(),
                        "context": f"...{context}...",
                    }
                )

        # 检查裸论断
        for pattern, message in WritingTools.NAKED_CLAIM_PATTERNS.items():
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end]

                issues.append(
                    {
                        "type": "evidence",
                        "word": match.group(),
                        "message": message,
                        "position": match.start(),
                        "context": f"...{context}...",
                    }
                )

        # 检查句子长度
        sentences = re.split(r"[.!?]+", text)
        for i, sentence in enumerate(sentences):
            words = sentence.split()
            if len(words) > 40:
                issues.append(
                    {
                        "type": "readability",
                        "word": sentence[:50] + "...",
                        "message": f"句子过长({len(words)}词)，建议拆分",
                        "position": 0,
                        "context": sentence[:100] + "...",
                    }
                )

        # 检查重复词
        words = re.findall(r"\b\w+\b", text.lower())
        word_freq = {}
        for word in words:
            if len(word) > 4:
                word_freq[word] = word_freq.get(word, 0) + 1

        for word, count in word_freq.items():
            if count > 5:
                issues.append(
                    {
                        "type": "repetition",
                        "word": word,
                        "message": f"词汇 '{word}' 重复 {count} 次，建议使用同义词",
                        "position": 0,
                        "context": "",
                    }
                )

        # 检查被动语态过度使用
        passive_patterns = [
            r"\b(is|are|was|were|be|been|being)\s+\w+ed\b",
            r"\b(is|are|was|were|be|been|being)\s+\w+en\b",
        ]
        passive_count = 0
        for pattern in passive_patterns:
            passive_count += len(re.findall(pattern, text, re.IGNORECASE))

        if passive_count > 5:
            issues.append(
                {
                    "type": "style",
                    "word": "",
                    "message": f"被动语态使用过多({passive_count}处)，建议增加主动语态",
                    "position": 0,
                    "context": "",
                }
            )

        logger.info(f"发现 {len(issues)} 个问题")
        return issues

    @staticmethod
    def analyze_structure(content: str, paper_type: str = None) -> dict[str, Any]:
        """分析论文的论证结构（Nature-skills 读者工作流驱动）"""
        logger.info(f"分析论证结构，文本长度: {len(content)}")

        # 如果未指定类型，自动检测
        if not paper_type:
            detection = WritingTools.detect_paper_type(content)
            paper_type = detection["detected_type"]

        type_info = WritingTools.PAPER_TYPES[paper_type]
        core_chain = type_info["core_chain"]

        # 识别章节
        sections = WritingTools._extract_sections(content)

        # 读者问题覆盖分析
        reader_questions = WritingTools._analyze_reader_questions(content, sections)

        # 论证链完整性分析
        chain_analysis = WritingTools._analyze_chain(content, core_chain)

        # 术语一致性检查
        terminology_issues = WritingTools._check_terminology_consistency(content)

        # 结构问题汇总
        structure_issues = []
        if not reader_questions.get("relevance_covered"):
            structure_issues.append(
                {
                    "section": "introduction",
                    "issue": "相关性(Relevance)未在引言开头建立",
                    "severity": "high",
                    "suggestion": "在引言前两段明确说明研究对谁重要、解决什么问题",
                }
            )
        if not reader_questions.get("novelty_covered"):
            structure_issues.append(
                {
                    "section": "introduction",
                    "issue": "新颖性(Novelty)未在引言末段突出",
                    "severity": "high",
                    "suggestion": "在引言最后一段明确陈述本研究的新发现",
                }
            )
        if not reader_questions.get("boundaries_covered"):
            structure_issues.append(
                {
                    "section": "discussion",
                    "issue": "边界与局限性(Meaning)未在讨论中暴露",
                    "severity": "medium",
                    "suggestion": "在讨论中增加局限性小节，主动暴露研究的适用边界",
                }
            )

        # 计算总分
        score = 10
        score -= len([i for i in structure_issues if i["severity"] == "high"]) * 2
        score -= len([i for i in structure_issues if i["severity"] == "medium"]) * 1
        score -= min(len(terminology_issues), 3) * 1
        score -= min(len(chain_analysis.get("gaps", [])), 3) * 1
        score = max(1, score)

        return {
            "paper_type": paper_type,
            "paper_type_label": type_info["label"],
            "core_chain": core_chain,
            "chain_analysis": chain_analysis,
            "reader_questions": reader_questions,
            "structure_issues": structure_issues,
            "terminology_issues": terminology_issues,
            "sections": sections,
            "overall_score": score,
        }

    @staticmethod
    def _extract_sections(content: str) -> list[dict[str, str]]:
        """从文本中提取章节"""
        sections = []
        # 匹配 Markdown 标题
        pattern = r"^(#{1,3})\s+(.+)$"
        lines = content.split("\n")

        current_section = None
        current_content = []

        for line in lines:
            match = re.match(pattern, line)
            if match:
                if current_section:
                    current_section["content"] = "\n".join(current_content).strip()
                    sections.append(current_section)
                current_section = {
                    "title": match.group(2).strip(),
                    "level": len(match.group(1)),
                }
                current_content = []
            else:
                current_content.append(line)

        if current_section:
            current_section["content"] = "\n".join(current_content).strip()
            sections.append(current_section)

        return sections

    @staticmethod
    def _analyze_reader_questions(content: str, sections: list[dict]) -> dict[str, Any]:
        """分析5个读者问题的覆盖情况"""
        content_lower = content.lower()
        {s["title"].lower(): s.get("content", "") for s in sections}

        # 简单的关键词启发式检测
        relevance_keywords = [
            "important",
            "significant",
            "critical",
            "essential",
            "重要",
            "关键",
            "意义",
        ]
        novelty_keywords = [
            "novel",
            "new",
            "first",
            "for the first time",
            "首次",
            "新",
            "创新",
        ]
        trust_keywords = [
            "p <",
            "p<",
            "significant",
            "confidence",
            "statistical",
            "显著",
            "统计",
        ]
        reuse_keywords = [
            "available",
            "repository",
            "github",
            "zenodo",
            "supplementary",
            "可用",
            "代码",
            "数据集",
        ]
        boundary_keywords = [
            "limitation",
            "future work",
            "caveat",
            "boundary",
            "局限",
            "不足",
            "未来",
        ]

        result = {
            "relevance_covered": any(kw in content_lower for kw in relevance_keywords),
            "novelty_covered": any(kw in content_lower for kw in novelty_keywords),
            "trust_covered": any(kw in content_lower for kw in trust_keywords),
            "reuse_covered": any(kw in content_lower for kw in reuse_keywords),
            "boundaries_covered": any(kw in content_lower for kw in boundary_keywords),
            "details": {},
        }

        # 定位各问题在哪个章节被回答
        for s in sections:
            s_lower = s.get("content", "").lower()
            s_title = s["title"]
            if (
                any(kw in s_lower for kw in relevance_keywords)
                and "relevance_section" not in result["details"]
            ):
                result["details"]["relevance_section"] = s_title
            if (
                any(kw in s_lower for kw in novelty_keywords)
                and "novelty_section" not in result["details"]
            ):
                result["details"]["novelty_section"] = s_title
            if (
                any(kw in s_lower for kw in trust_keywords)
                and "trust_section" not in result["details"]
            ):
                result["details"]["trust_section"] = s_title
            if (
                any(kw in s_lower for kw in reuse_keywords)
                and "reuse_section" not in result["details"]
            ):
                result["details"]["reuse_section"] = s_title
            if (
                any(kw in s_lower for kw in boundary_keywords)
                and "boundaries_section" not in result["details"]
            ):
                result["details"]["boundaries_section"] = s_title

        return result

    @staticmethod
    def _analyze_chain(content: str, core_chain: str) -> dict[str, Any]:
        """分析论证链完整性"""
        chain_steps = [step.strip() for step in core_chain.split("→")]
        content_lower = content.lower()

        covered = []
        gaps = []

        # 简单启发式检查每个链步是否有对应内容
        chain_keywords = {
            "现象": ["phenomenon", "observation", "observed", "现象", "观察"],
            "量化": ["quantif", "measured", "数值", "量化", "统计"],
            "机制": ["mechanism", "underlying", "pathway", "机制", "通路"],
            "意义": ["implication", "significance", "meaning", "意义", "启示"],
            "问题": ["problem", "challenge", "issue", "问题", "挑战"],
            "方法": ["method", "approach", "protocol", "方法", "方案"],
            "验证": ["validat", "verified", "confirmed", "验证", "确认"],
            "优势": ["advantage", "superior", "outperform", "优势", "优于"],
            "假设": ["hypothes", "假设", "postulat"],
            "预测": ["predict", "forecast", "预测"],
            "检验": ["test", "examin", "检验", "测试"],
            "证据": ["evidence", "support", "证据", "支持"],
            "判断": ["conclud", "judg", "判断", "结论"],
            "算法": ["algorithm", "model", "procedure", "算法", "模型"],
            "理论保证": ["theorem", "guarantee", "convergence", "理论", "保证"],
            "实证验证": ["experiment", "empirical", "实验", "实证"],
            "失败分析": ["failure", "error", "limitation", "失败", "错误"],
            "领域图景": ["landscape", "overview", "领域", "全景"],
            "分论点": ["argument", "perspective", "论点", "视角"],
            "证据综合": ["synthesis", "consensus", "综合", "共识"],
            "开放问题": ["open", "future", "gap", "开放", "空白"],
        }

        for step in chain_steps:
            step_covered = False
            for kw in chain_keywords.get(step, [step.lower()]):
                if kw in content_lower:
                    step_covered = True
                    break
            if step_covered:
                covered.append(step)
            else:
                gaps.append(step)

        return {
            "chain": core_chain,
            "steps": chain_steps,
            "covered_steps": covered,
            "gaps": gaps,
            "completeness": len(covered) / max(len(chain_steps), 1),
        }

    @staticmethod
    def _check_terminology_consistency(content: str) -> list[dict[str, Any]]:
        """检查术语一致性（Nature-skills 术语账本规则）"""
        issues = []

        # 检测常见的术语不一致模式
        inconsistency_patterns = [
            (
                r"\b(deep learning|Deep Learning|Deep-learning|deep-learning)\b",
                "deep learning",
                "大小写/连字符不一致",
            ),
            (
                r"\b(machine learning|Machine Learning|Machine-learning)\b",
                "machine learning",
                "大小写/连字符不一致",
            ),
            (
                r"\b(neural network|Neural Network|neural-network)\b",
                "neural network",
                "大小写/连字符不一致",
            ),
            (r"\b(data set|dataset|data-set)\b", "dataset", "拼写不一致"),
            (r"\b(pre-train|pretrain|pre train)\b", "pretrain", "拼写不一致"),
            (r"\b(fine-tun|finetun|fine tun)\b", "fine-tun", "拼写不一致"),
        ]

        for pattern, canonical, issue_type in inconsistency_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            unique_forms = set(m.lower() for m in matches)
            if len(unique_forms) > 1:
                issues.append(
                    {
                        "type": "terminology_inconsistency",
                        "canonical": canonical,
                        "variants": list(unique_forms),
                        "message": (
                            f"术语 '{canonical}' 有多种形式: "
                            f"{', '.join(unique_forms)}，"
                            f"建议统一为 '{canonical}'"
                        ),
                    }
                )

        return issues

    @staticmethod
    def format_academic_text(text: str, style: str = "standard") -> str:
        """格式化学术文本"""
        logger.info(f"格式化文本，风格: {style}")

        # 基础格式化
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\s+([,.])", r"\1", text)
        text = re.sub(r"\.+", ".", text)
        text = re.sub(r",+", ",", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        text = text.replace("\u2018", "'").replace("\u2019", "'")

        return text.strip()

    @staticmethod
    def suggest_transitions(paragraph: str, context: str = "") -> list[str]:
        """建议学术过渡词"""
        if not context:
            context = paragraph

        transition_type = "addition"
        if any(
            word in context.lower()
            for word in ["however", "but", "although", "然而", "但是"]
        ):
            transition_type = "contrast"
        elif any(
            word in context.lower()
            for word in ["therefore", "thus", "so", "因此", "所以"]
        ):
            transition_type = "cause"
        elif any(word in context.lower() for word in ["example", "instance", "例如"]):
            transition_type = "example"
        else:
            transition_type = "addition"

        suggestions = WritingTools.ACADEMIC_TRANSITIONS.get(transition_type, [])
        return suggestions

    @staticmethod
    def count_words(text: str) -> dict[str, Any]:
        """字数统计"""
        chinese_chars = len(re.findall(r"[一-鿿]", text))
        english_words = len(re.findall(r"\b[a-zA-Z]+\b", text))
        total_chars = len(text)
        paragraphs = len([p for p in text.split("\n\n") if p.strip()])
        sentences = len(re.split(r"[.!?。！？]+", text))

        return {
            "chinese_characters": chinese_chars,
            "english_words": english_words,
            "total_characters": total_chars,
            "paragraphs": paragraphs,
            "sentences": sentences,
            "estimated_reading_time": (
                f"{(chinese_chars / 300 + english_words / 200):.1f} 分钟"
            ),
        }

    @staticmethod
    def generate_references_section(papers: list[dict], style: str = "apa") -> str:
        """生成参考文献列表"""
        from app.agents.literature.tools import LiteratureTools

        references = []
        for i, paper in enumerate(papers, 1):
            citation = LiteratureTools.format_citation(paper, style)
            references.append(f"[{i}] {citation}")

        return "## 参考文献\n\n" + "\n".join(references)

    @staticmethod
    def polish_sentence(sentence: str) -> dict[str, Any]:
        """润色句子建议"""
        suggestions = []

        first_word = sentence.split()[0] if sentence.split() else ""
        if first_word.lower() in ["the", "a", "an"]:
            suggestions.append("考虑用更有力的开头词")

        words = sentence.lower().split()
        if len(set(words)) < len(words) * 0.6:
            suggestions.append("词汇重复较多，建议使用同义词")

        if len(words) > 30:
            suggestions.append("句子较长，建议拆分为两个句子")
        elif len(words) < 5:
            suggestions.append("句子较短，考虑是否需要扩展")

        return {
            "original": sentence,
            "suggestions": suggestions,
            "word_count": len(words),
        }

    @staticmethod
    def build_terminology_ledger(content: str) -> dict[str, Any]:
        """构建术语账本（Nature-skills 核心概念）"""
        logger.info(f"构建术语账本，文本长度: {len(content)}")

        ledger = {}

        # 提取缩写定义模式
        # 英文: "full term (ABBREVIATION)" or "full term (ABBR.)"
        abbr_pattern = r"([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)\s*\(([A-Z]{2,}[.]?)\)"
        for match in re.finditer(abbr_pattern, content):
            full_term = match.group(1).strip()
            abbreviation = match.group(2).strip().rstrip(".")
            ledger[abbreviation] = {
                "canonical": abbreviation,
                "full_form": full_term,
                "variants_seen": [],
                "decision": (
                    f"首次定义: {full_term} ({abbreviation})，"
                    f"之后统一使用 {abbreviation}"
                ),
            }

        # 中文: "全称（简称）"
        cn_abbr_pattern = r"([\u4e00-\u9fff]+[^\(]*)（([\u4e00-\u9fffA-Z]+)）"
        for match in re.finditer(cn_abbr_pattern, content):
            full_term = match.group(1).strip()
            abbreviation = match.group(2).strip()
            ledger[abbreviation] = {
                "canonical": abbreviation,
                "full_form": full_term,
                "variants_seen": [],
                "decision": (
                    f"首次定义: {full_term}（{abbreviation}），"
                    f"之后统一使用 {abbreviation}"
                ),
            }

        # 提取反复出现的专业术语（出现3次以上的长词）
        words = re.findall(r"\b[A-Z][a-z]{4,}(?:\s+[A-Z][a-z]{3,})*\b", content)
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1

        for word, count in sorted(word_freq.items(), key=lambda x: -x[1]):
            if count >= 3 and word not in ledger:
                ledger[word] = {
                    "canonical": word,
                    "full_form": "",
                    "variants_seen": [],
                    "decision": f"高频术语({count}次)，确认是否需要统一定义",
                }

        return {
            "ledger": ledger,
            "total_terms": len(ledger),
            "rules": [
                "每个缩写在首次使用时定义一次，之后用短形式",
                "单位、符号和记法在每个章节中完全相同",
                "术语一致性优先于词汇多样性",
                "不要为同一概念引入同义词以增加表达多样性",
            ],
        }

    # ─────────────────────────────────────────────
    # 引用管理与统一导出
    # ─────────────────────────────────────────────

    # 由 insert_citations 维护，供 build_reference_list 复用
    _last_citation_order: list[str] = []

    @staticmethod
    def insert_citations(text: str, citations: list[dict]) -> str:
        """将文本中的引用占位符替换为编号标记 [1]/[2]...

        支持占位符：[CITE:key] 与 {{key}}。按首次出现顺序编号，
        同时维护 WritingTools._last_citation_order（key 顺序列表）。

        Args:
            text: 含占位符的文本
            citations: 引用元数据列表，每项含 {key, title, authors, year, journal, url}

        Returns:
            替换后的文本
        """
        if not isinstance(text, str):
            raise ToolException("text 必须为字符串", tool_name="insert_citations")
        if not isinstance(citations, list):
            raise ToolException("citations 必须为列表", tool_name="insert_citations")

        logger.info(f"插入引用，文本长度={len(text)}, 引用数={len(citations)}")

        WritingTools._last_citation_order = []
        key_to_index: dict[str, int] = {}
        pattern = re.compile(r"\[CITE:([^\]]+)\]|\{\{([^}]+)\}\}")

        def _replace(m: "re.Match[str]") -> str:
            key = (m.group(1) or m.group(2) or "").strip()
            if not key:
                return m.group(0)
            if key not in key_to_index:
                key_to_index[key] = len(WritingTools._last_citation_order) + 1
                WritingTools._last_citation_order.append(key)
            return f"[{key_to_index[key]}]"

        return pattern.sub(_replace, text)

    @staticmethod
    def build_reference_list(citations: list[dict], style: str = "apa") -> str:
        """按引用顺序生成参考文献列表

        Args:
            citations: 引用元数据列表
            style: apa / numbered / vancouver

        Returns:
            参考文献列表文本；style 不支持时返回 {"error": ...}
        """
        if not isinstance(citations, list):
            raise ToolException(
                "citations 必须为列表", tool_name="build_reference_list"
            )
        if not isinstance(style, str):
            raise ToolException("style 必须为字符串", tool_name="build_reference_list")

        supported = ("apa", "numbered", "vancouver")
        if style not in supported:
            return {"error": f"不支持的格式: {style}"}  # type: ignore[return-value]

        logger.info(f"生成参考文献，style={style}, 引用数={len(citations)}")

        order = WritingTools._last_citation_order
        key_to_citation = {
            c.get("key", ""): c for c in citations if isinstance(c, dict)
        }

        ordered: list[dict] = []
        seen = set()
        for k in order:
            if k in key_to_citation and k not in seen:
                ordered.append(key_to_citation[k])
                seen.add(k)
        for c in citations:
            k = c.get("key", "") if isinstance(c, dict) else ""
            if k and k not in seen:
                ordered.append(c)
                seen.add(k)

        lines = []
        for i, cite in enumerate(ordered, 1):
            lines.append(WritingTools._format_citation(cite, style, i))
        return "\n".join(lines)

    @staticmethod
    def _format_citation(citation: dict, style: str, index: int) -> str:
        """格式化单条引用（内部辅助）"""
        authors = citation.get("authors", []) or []
        year = citation.get("year", "")
        title = citation.get("title", "")
        journal = citation.get("journal", "")
        url = citation.get("url", "")

        if style == "apa":
            if authors:
                auth_str = (
                    authors[0]
                    if len(authors) == 1
                    else ", ".join(authors[:-1]) + ", & " + authors[-1]
                )
            else:
                auth_str = ""
            parts = []
            if auth_str:
                parts.append(auth_str)
            if year:
                parts.append(f"({year}).")
            if title:
                parts.append(f"{title}.")
            if journal:
                parts.append(f"{journal}.")
            return " ".join(parts)

        # numbered / vancouver
        auth_str = ", ".join(authors) if authors else ""
        parts = []
        if auth_str:
            parts.append(auth_str + ".")
        if title:
            parts.append(f"{title}.")
        if journal:
            parts.append(f"{journal}.")
        if year:
            parts.append(f"{year}.")
        if url and style == "vancouver":
            parts.append(f"Available at: {url}")
        return f"[{index}] " + " ".join(parts)

    @staticmethod
    def export_manuscript(manuscript: dict, format: str) -> str:
        """导出手稿为指定格式

        Args:
            manuscript: 含 {title, sections:[{title, content}], citations:[...]}
            format: markdown / bibtex / ris / latex

        Returns:
            导出内容；format 不支持时返回 {"error": ...}
        """
        if not isinstance(manuscript, dict):
            raise ToolException("manuscript 必须为字典", tool_name="export_manuscript")
        if not isinstance(format, str):
            raise ToolException("format 必须为字符串", tool_name="export_manuscript")

        supported = ("markdown", "bibtex", "ris", "latex")
        if format not in supported:
            return {"error": f"不支持的格式: {format}"}  # type: ignore[return-value]

        from app.utils.export import DataExporter

        title = manuscript.get("title", "")
        sections = manuscript.get("sections", []) or []
        citations = manuscript.get("citations", []) or []

        logger.info(f"导出手稿，format={format}")

        if format == "markdown":
            lines = [f"# {title}", ""]
            for sec in sections:
                if not isinstance(sec, dict):
                    continue
                lines.append(f"## {sec.get('title', '')}")
                lines.append("")
                lines.append(sec.get("content", ""))
                lines.append("")
            return "\n".join(lines).strip()

        if format == "bibtex":
            return DataExporter.papers_to_bibtex(citations)

        if format == "ris":
            return DataExporter.papers_to_ris(citations)

        # latex: \section 拼接 + \bibitem 列表
        skeleton = DataExporter.to_latex(manuscript)
        bib_items = []
        for i, c in enumerate(citations, 1):
            if not isinstance(c, dict):
                continue
            key = c.get("key", f"ref{i}")
            entry = WritingTools._format_citation(c, "numbered", i)
            bib_items.append(f"\\bibitem{{{key}}} {entry}")
        if bib_items:
            bib_block = (
                "\\begin{thebibliography}{99}\n"
                + "\n".join(bib_items)
                + "\n\\end{thebibliography}"
            )
            skeleton = skeleton.replace(
                "\\end{document}",
                bib_block + "\n\\end{document}",
            )
        return skeleton

    @staticmethod
    def export_papers(papers: list[dict], format: str) -> str:
        """导出文献列表为指定格式

        Args:
            papers: 文献列表
            format: bibtex / ris / markdown / csv / json

        Returns:
            导出内容；format 不支持时返回 {"error": ...}
        """
        if not isinstance(papers, list):
            raise ToolException("papers 必须为列表", tool_name="export_papers")
        if not isinstance(format, str):
            raise ToolException("format 必须为字符串", tool_name="export_papers")

        supported = ("bibtex", "ris", "markdown", "csv", "json")
        if format not in supported:
            return {"error": f"不支持的格式: {format}"}  # type: ignore[return-value]

        from app.utils.export import DataExporter

        logger.info(f"导出文献，format={format}, 数量={len(papers)}")

        if format == "bibtex":
            return DataExporter.papers_to_bibtex(papers)
        if format == "ris":
            return DataExporter.papers_to_ris(papers)
        if format == "markdown":
            return DataExporter.to_markdown_table(papers)
        if format == "csv":
            return DataExporter.to_csv(papers).decode("utf-8-sig")
        # json
        return DataExporter.to_json(papers).decode("utf-8")
