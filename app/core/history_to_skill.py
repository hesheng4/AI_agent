"""昇腾历史记录搜索与 Skill 生成模块

遵循 ascend-history-to-skill skill 规范：
1. 明确目标模型和范围
2. 搜索历史记录 (Codex / Claude Code / OpenCode / Cursor)
3. 只保留高价值证据
4. 整理成 skill 素材
5. 生成模型 skill
6. 生成后验证
"""

import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("ascend_history_to_skill")

# SQL 标识符白名单：仅允许字母、数字、下划线，且必须以字母或下划线开头
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _is_safe_identifier(name: str, max_len: int = 64) -> bool:
    """检查名称是否可作为安全的 SQL 标识符"""
    if not name or len(name) > max_len:
        return False
    return bool(_SAFE_IDENTIFIER_RE.match(name))


# ========== 枚举与数据结构 ==========


class HistorySource(Enum):
    """历史记录来源"""

    CODEX = "codex"
    CLAUDE_CODE = "claude-code"
    OPENCODE = "opencode"
    CURSOR = "cursor"
    UNKNOWN = "unknown"


class SkillStage(Enum):
    """Skill 阶段"""

    ADAPT = "adapt"
    OPTIMIZE = "optimize"


class EvidenceLevel(Enum):
    """证据等级"""

    VERIFIED = "verified"  # 已验证，有运行输出
    LIKELY = "likely"  # 有代码修改，无明确输出
    DISCUSSION = "discussion"  # 仅讨论
    UNVERIFIED = "unverified"  # 未验证


@dataclass
class HistoryHit:
    """历史记录命中项"""

    source: HistorySource = HistorySource.UNKNOWN
    file_path: str = ""
    timestamp: str = ""
    model_name: str = ""
    stage: str = ""  # adapt / optimize / both
    content: str = ""
    evidence_level: EvidenceLevel = EvidenceLevel.DISCUSSION
    keywords: list[str] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "file_path": self.file_path,
            "timestamp": self.timestamp,
            "model_name": self.model_name,
            "stage": self.stage,
            "evidence_level": self.evidence_level.value,
            "keywords": self.keywords,
            "score": self.score,
            "content_length": len(self.content),
        }


@dataclass
class SkillMaterial:
    """Skill 素材（从历史中提炼）"""

    model_name: str = ""
    repo_path: str = ""
    entry_scripts: list[str] = field(default_factory=list)
    weight_names: list[str] = field(default_factory=list)

    # 环境要求
    python_version: str = ""
    torch_version: str = ""
    torch_npu_version: str = ""
    cann_version: str = ""
    conda_env_name: str = ""
    pip_packages: list[str] = field(default_factory=list)

    # 适配步骤
    adapt_steps: list[dict[str, str]] = field(default_factory=list)
    cuda_replacements: list[dict[str, str]] = field(default_factory=list)
    third_party_fixes: list[dict[str, str]] = field(default_factory=list)
    distributed_constraints: list[str] = field(default_factory=list)

    # 优化步骤
    optimize_steps: list[dict[str, str]] = field(default_factory=list)
    runtime_env_vars: dict[str, str] = field(default_factory=dict)
    benchmark_results: list[dict[str, Any]] = field(default_factory=list)

    # 验证步骤
    verify_commands: list[str] = field(default_factory=list)
    accuracy_references: list[dict[str, Any]] = field(default_factory=list)

    # 常见问题
    common_issues: list[dict[str, str]] = field(default_factory=list)

    # 原始命中
    hits: list[HistoryHit] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "repo_path": self.repo_path,
            "entry_scripts": self.entry_scripts,
            "weight_names": self.weight_names,
            "python_version": self.python_version,
            "torch_version": self.torch_version,
            "torch_npu_version": self.torch_npu_version,
            "cann_version": self.cann_version,
            "conda_env_name": self.conda_env_name,
            "pip_packages": self.pip_packages,
            "adapt_steps": self.adapt_steps,
            "cuda_replacements": self.cuda_replacements,
            "third_party_fixes": self.third_party_fixes,
            "distributed_constraints": self.distributed_constraints,
            "optimize_steps": self.optimize_steps,
            "runtime_env_vars": self.runtime_env_vars,
            "benchmark_results": self.benchmark_results,
            "verify_commands": self.verify_commands,
            "accuracy_references": self.accuracy_references,
            "common_issues": self.common_issues,
            "hit_count": len(self.hits),
            "hit_sources": list(set(h.source.value for h in self.hits)),
        }


@dataclass
class SkillGenerationResult:
    """Skill 生成结果"""

    success: bool = False
    model_name: str = ""
    skill_dir: str = ""
    skill_md_path: str = ""
    hits_found: int = 0
    hits_used: int = 0
    stages: list[str] = field(default_factory=list)
    validation_passed: bool = False
    validation_errors: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "model_name": self.model_name,
            "skill_dir": self.skill_dir,
            "skill_md_path": self.skill_md_path,
            "hits_found": self.hits_found,
            "hits_used": self.hits_used,
            "stages": self.stages,
            "validation_passed": self.validation_passed,
            "validation_errors": self.validation_errors,
            "errors": self.errors,
        }


# ========== 默认历史记录路径 ==========

DEFAULT_HISTORY_PATHS = {
    HistorySource.CODEX: [
        os.path.expanduser("~/.codex/sessions"),
        os.path.expanduser("~/.codex/history"),
    ],
    HistorySource.CLAUDE_CODE: [
        os.path.expanduser("~/.claude/projects"),
        os.path.expanduser("~/.claude/sessions"),
    ],
    HistorySource.OPENCODE: [
        os.path.expanduser("~/.opencode/sessions"),
        os.path.expanduser("~/.local/share/opencode"),
    ],
    HistorySource.CURSOR: [
        os.path.expanduser("~/.cursor/sessions"),
        os.path.expanduser("~/Library/Application Support/Cursor/User/globalStorage"),
    ],
}

SKILL_OUTPUT_ROOT = Path.home() / ".codex" / "skills"
_ALLOWED_EXTRA_ROOTS = [
    Path.home() / ".codex",
    Path.home() / ".claude",
    Path.home() / ".opencode",
    Path.home() / ".cursor",
]


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _validate_extra_root(root: str) -> str:
    target = Path(root).expanduser().resolve()
    allowed_roots = [base.expanduser().resolve() for base in _ALLOWED_EXTRA_ROOTS]
    if not any(_is_relative_to(target, base) for base in allowed_roots):
        raise ValueError("extra_roots 只能指向允许的历史目录")
    return str(target)


def _safe_skill_output_dir(model_name: str, output_dir: str | None = None) -> Path:
    base = SKILL_OUTPUT_ROOT.expanduser().resolve()
    if output_dir:
        target = Path(output_dir).expanduser().resolve()
    else:
        target = (base / model_name.lower().replace(" ", "-")).resolve()
    if not _is_relative_to(target, base):
        raise ValueError(f"output_dir 必须位于 {base} 下")
    return target


# ========== Step 1: 明确目标模型和范围 ==========


def normalize_model_name(model_name: str) -> list[str]:
    """生成模型名的常见变体，用于扩大搜索范围"""
    variants = [model_name]

    # 连字符 ↔ 下划线
    if "-" in model_name:
        variants.append(model_name.replace("-", "_"))
    if "_" in model_name:
        variants.append(model_name.replace("_", "-"))

    # 小写
    lower = model_name.lower()
    if lower not in variants:
        variants.append(lower)

    # 去除版本后缀 (如 esm2_t33_650M_UR50D -> esm2)
    base = re.split(r"[_\-]", model_name)[0]
    if base not in variants:
        variants.append(base)

    # 仓库名后缀 (如 esm-main, esm2-main)
    for suffix in ["-main", "-master", "-repo", "_main", "_repo"]:
        candidate = model_name + suffix
        if candidate not in variants:
            variants.append(candidate)
        candidate = base + suffix
        if candidate not in variants:
            variants.append(candidate)

    return list(dict.fromkeys(variants))  # 去重保序


# ========== Step 2: 搜索历史记录 ==========


def discover_history_roots(
    sources: list[HistorySource] | None = None,
    extra_roots: list[str] | None = None,
) -> dict[HistorySource, list[str]]:
    """发现可用历史记录根目录"""
    roots: dict[HistorySource, list[str]] = {}
    search_sources = sources or list(HistorySource)

    for src in search_sources:
        if src == HistorySource.UNKNOWN:
            continue
        paths = DEFAULT_HISTORY_PATHS.get(src, [])
        existing = [p for p in paths if os.path.exists(p)]
        if existing:
            roots[src] = existing

    if extra_roots:
        for r in extra_roots:
            safe_root = _validate_extra_root(r)
            if os.path.exists(safe_root):
                if HistorySource.UNKNOWN not in roots:
                    roots[HistorySource.UNKNOWN] = []
                roots[HistorySource.UNKNOWN].append(safe_root)

    return roots


def search_history(
    model_name: str,
    stages: list[str] | None = None,
    keywords: list[str] | None = None,
    sources: list[HistorySource] | None = None,
    extra_roots: list[str] | None = None,
    exclude_terms: list[str] | None = None,
    max_hits: int = 100,
) -> list[HistoryHit]:
    """搜索历史记录，返回命中项

    Args:
        model_name: 目标模型名
        stages: 阶段过滤 adapt/optimize
        keywords: 额外关键词
        sources: 限制搜索来源
        extra_roots: 额外搜索路径
        exclude_terms: 排除关键词
        max_hits: 最大命中数
    """
    variants = normalize_model_name(model_name)
    search_terms = variants[:]
    if keywords:
        search_terms.extend(keywords)

    roots = discover_history_roots(sources, extra_roots)
    if not roots:
        logger.warning("未找到任何历史记录根目录")
        return []

    hits: list[HistoryHit] = []

    for src, paths in roots.items():
        for root in paths:
            src_hits = _search_in_path(root, src, search_terms, exclude_terms, max_hits)
            hits.extend(src_hits)

    # 评分和排序
    for hit in hits:
        hit.score = _score_hit(hit, model_name, stages, keywords)
        hit.model_name = model_name
        if stages:
            hit.stage = _infer_stage(hit.content, stages)

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:max_hits]


def _rglob_with_depth(path: Path, pattern: str, max_depth: int):
    """带深度限制的 rglob，避免遍历巨大目录树"""
    base_depth = len(path.parts)
    for p in path.rglob(pattern):
        if len(p.parts) - base_depth <= max_depth:
            yield p


def _search_in_path(
    root: str,
    source: HistorySource,
    search_terms: list[str],
    exclude_terms: list[str] | None,
    max_hits: int,
) -> list[HistoryHit]:
    """在指定路径下搜索

    限制递归深度为 MAX_SEARCH_DEPTH，避免遍历巨大目录树（如用户主目录）。
    """
    # 搜索最大深度（层数），防止遍历巨大目录
    MAX_SEARCH_DEPTH = 8  # noqa: N806

    hits = []
    root_path = Path(root)

    if not root_path.exists():
        return hits

    # 尝试 SQLite 数据库
    for db_file in _rglob_with_depth(root_path, "*.db", MAX_SEARCH_DEPTH):
        if len(hits) >= max_hits:
            break
        db_hits = _search_sqlite(str(db_file), source, search_terms, exclude_terms)
        hits.extend(db_hits)

    # 搜索 JSON / JSONL 文件
    for json_file in _rglob_with_depth(root_path, "*.json*", MAX_SEARCH_DEPTH):
        if len(hits) >= max_hits:
            break
        file_hits = _search_text_file(
            str(json_file), source, search_terms, exclude_terms
        )
        hits.extend(file_hits)

    # 搜索 Markdown / 文本文件
    for ext in ["*.md", "*.txt", "*.log"]:
        for text_file in _rglob_with_depth(root_path, ext, MAX_SEARCH_DEPTH):
            if len(hits) >= max_hits:
                break
            file_hits = _search_text_file(
                str(text_file), source, search_terms, exclude_terms
            )
            hits.extend(file_hits)

    return hits


def _search_sqlite(
    db_path: str,
    source: HistorySource,
    search_terms: list[str],
    exclude_terms: list[str] | None,
) -> list[HistoryHit]:
    """搜索 SQLite 数据库"""
    hits = []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            if not _is_safe_identifier(table):
                logger.debug("跳过不安全表名: %s", table)
                continue
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]

                # 搜索文本列
                text_cols = [
                    c
                    for c in columns
                    if any(
                        kw in c.lower()
                        for kw in [
                            "content",
                            "text",
                            "message",
                            "body",
                            "value",
                            "prompt",
                            "output",
                        ]
                    )
                ]

                for col in text_cols:
                    if not _is_safe_identifier(col):
                        continue
                    for term in search_terms[:5]:  # 限制搜索词数量
                        try:
                            query = (
                                f"SELECT rowid, {col} FROM {table} "
                                f"WHERE {col} LIKE ? LIMIT 50"
                            )
                            cursor.execute(query, (f"%{term}%",))
                            for row in cursor.fetchall():
                                content = str(row[1])[:5000]
                                if exclude_terms and any(
                                    ex.lower() in content.lower()
                                    for ex in exclude_terms
                                ):
                                    continue
                                hits.append(
                                    HistoryHit(
                                        source=source,
                                        file_path=f"{db_path}::{table}::row{row[0]}",
                                        content=content,
                                        keywords=[term],
                                    )
                                )
                        except sqlite3.OperationalError:
                            continue
            except sqlite3.OperationalError:
                continue

        conn.close()
    except Exception as e:
        logger.debug(f"SQLite 搜索失败 {db_path}: {str(e)}")

    return hits


def _search_text_file(
    file_path: str,
    source: HistorySource,
    search_terms: list[str],
    exclude_terms: list[str] | None,
) -> list[HistoryHit]:
    """搜索文本文件 (JSON, JSONL, MD, TXT)"""
    hits = []
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read(100000)  # 限制读取量

        if not any(term.lower() in content.lower() for term in search_terms):
            return hits

        if exclude_terms and any(ex.lower() in content.lower() for ex in exclude_terms):
            return hits

        # 提取相关片段
        matched_terms = [t for t in search_terms if t.lower() in content.lower()]

        # 对于 JSONL 文件，按行搜索
        if file_path.endswith(".jsonl"):
            for i, line in enumerate(content.splitlines()):
                if any(t.lower() in line.lower() for t in search_terms):
                    hits.append(
                        HistoryHit(
                            source=source,
                            file_path=f"{file_path}::L{i}",
                            content=line[:5000],
                            keywords=matched_terms,
                        )
                    )
        else:
            hits.append(
                HistoryHit(
                    source=source,
                    file_path=file_path,
                    content=content[:10000],
                    keywords=matched_terms,
                )
            )

    except Exception as e:
        logger.debug(f"文件搜索失败 {file_path}: {str(e)}")

    return hits


def _score_hit(
    hit: HistoryHit,
    model_name: str,
    stages: list[str] | None,
    keywords: list[str] | None,
) -> float:
    """对命中项评分"""
    score = 0.0
    content = hit.content.lower()

    # 模型名精确匹配
    if model_name.lower() in content:
        score += 10.0

    # 关键词匹配
    if keywords:
        for kw in keywords:
            if kw.lower() in content:
                score += 3.0

    # 昇腾相关关键词
    ascend_terms = [
        "torch_npu",
        "npu",
        "ascend",
        "cann",
        "vllm-ascend",
        "cuda",
        "hccl",
        "npu-smi",
        "task_queue_enable",
        "pytorch_npu_alloc_conf",
        "cpu_affinity_conf",
    ]
    for term in ascend_terms:
        if term.lower() in content:
            score += 1.5

    # 证据等级加分
    if "error" in content and "fix" in content:
        score += 2.0
        hit.evidence_level = EvidenceLevel.LIKELY
    if any(
        kw in content
        for kw in ["passed", "success", "ok", "accuracy", "qps", "throughput"]
    ):
        score += 3.0
        hit.evidence_level = EvidenceLevel.VERIFIED

    # 阶段匹配
    if stages:
        for stage in stages:
            if stage == "adapt" and any(
                kw in content
                for kw in ["adapt", "migrate", "replace", "cuda_to_npu", "patch"]
            ):
                score += 2.0
            if stage == "optimize" and any(
                kw in content
                for kw in ["optimize", "perf", "benchmark", "tuning", "tcmalloc"]
            ):
                score += 2.0

    # 代码相关加分
    if any(
        kw in content for kw in ["import ", "def ", "class ", "pip install", "conda "]
    ):
        score += 1.0

    return score


def _infer_stage(content: str, stages: list[str]) -> str:
    """推断记录所属阶段"""
    content_lower = content.lower()
    adapt_kw = ["adapt", "migrate", "replace", "cuda", "patch", "fix import"]
    optimize_kw = [
        "optimize",
        "perf",
        "benchmark",
        "tuning",
        "tcmalloc",
        "cpu_affinity",
    ]

    is_adapt = any(kw in content_lower for kw in adapt_kw)
    is_optimize = any(kw in content_lower for kw in optimize_kw)

    if is_adapt and is_optimize:
        return "both"
    elif is_optimize:
        return "optimize"
    elif is_adapt:
        return "adapt"
    else:
        return stages[0] if stages else "unknown"


# ========== Step 3: 只保留高价值证据 ==========


def filter_high_value_hits(hits: list[HistoryHit]) -> list[HistoryHit]:
    """过滤高价值证据

    优先保留：已验证命令、代码修改、benchmark 结果、报错修复
    降权/丢弃：纯讨论、无关记录、被推翻的旧方案
    """
    filtered = []

    for hit in hits:
        # 丢弃纯讨论（无任何代码或命令）
        has_code = any(
            kw in hit.content
            for kw in [
                "import ",
                "def ",
                "class ",
                "pip ",
                "conda ",
                "python ",
                "bash ",
                "export ",
                "npu-smi",
                "vllm ",
                "torch_npu",
            ]
        )
        has_result = any(
            kw in hit.content.lower()
            for kw in [
                "passed",
                "success",
                "ok",
                "accuracy",
                "qps",
                "throughput",
                "tokens/s",
                "error:",
                "traceback",
                "fixed",
                "resolved",
            ]
        )

        if not has_code and not has_result:
            hit.evidence_level = EvidenceLevel.DISCUSSION
            # 仍然保留，但排在后面
            hit.score *= 0.3

        if hit.evidence_level == EvidenceLevel.DISCUSSION and hit.score < 2.0:
            continue  # 丢弃低分讨论

        filtered.append(hit)

    return filtered


# ========== Step 4: 整理成 Skill 素材 ==========


def extract_skill_material(
    model_name: str,
    hits: list[HistoryHit],
) -> SkillMaterial:
    """从命中记录中提炼 Skill 素材"""
    material = SkillMaterial(model_name=model_name, hits=hits)

    for hit in hits:
        content = hit.content

        # 提取环境信息
        _extract_env_info(material, content)

        # 提取适配步骤
        _extract_adapt_steps(material, content)

        # 提取优化步骤
        _extract_optimize_steps(material, content)

        # 提取验证命令
        _extract_verify_commands(material, content)

        # 提取常见问题
        _extract_common_issues(material, content)

    return material


def _extract_env_info(material: SkillMaterial, content: str):
    """提取环境信息"""
    # Python 版本
    py_match = re.search(r"python[=><!~]+(\d+\.\d+[\.\d]*)", content, re.IGNORECASE)
    if py_match and not material.python_version:
        material.python_version = py_match.group(1)

    # torch 版本
    torch_match = re.search(r"torch[=><!~]+(\d+\.\d+[\.\d]*)", content, re.IGNORECASE)
    if torch_match and not material.torch_version:
        material.torch_version = torch_match.group(1)

    # torch_npu 版本
    npu_match = re.search(r"torch.npu[=><!~]+(\d+\.\d+[\.\d]*)", content, re.IGNORECASE)
    if npu_match and not material.torch_npu_version:
        material.torch_npu_version = npu_match.group(1)

    # CANN 版本
    cann_match = re.search(r"CANN[=><!~\s]+(\d+\.\d+[\.\d]*)", content, re.IGNORECASE)
    if cann_match and not material.cann_version:
        material.cann_version = cann_match.group(1)

    # conda 环境
    conda_match = re.search(r"conda\s+(?:activate|create).*?(\w+)", content)
    if conda_match and not material.conda_env_name:
        material.conda_env_name = conda_match.group(1)

    # pip 包
    pip_matches = re.findall(r"pip\s+install\s+([\w\-\.\[\]]+)", content)
    for pkg in pip_matches:
        if pkg not in material.pip_packages:
            material.pip_packages.append(pkg)

    # 仓库名
    repo_match = re.search(r"(?:clone|cd)\s+([\w\-\.]+/[\w\-\.]+|[\w\-]+)", content)
    if repo_match and not material.repo_path:
        material.repo_path = repo_match.group(1)

    # 入口脚本
    entry_matches = re.findall(r"python\s+([\w/\-]+\.py)", content)
    for script in entry_matches:
        if script not in material.entry_scripts:
            material.entry_scripts.append(script)


def _extract_adapt_steps(material: SkillMaterial, content: str):
    """提取适配步骤"""
    # CUDA 替换
    cuda_patterns = [
        (r"\.cuda\(\)", ".to('npu')"),
        (r"torch\.cuda", "torch_npu"),
        (r"CUDA_VISIBLE_DEVICES", "ASCEND_RT_VISIBLE_DEVICES"),
        (r"device.*cuda", "device='npu'"),
    ]

    for pattern, replacement in cuda_patterns:
        if pattern.replace("\\", "") in content:
            existing = [
                r for r in material.cuda_replacements if r["pattern"] == pattern
            ]
            if not existing:
                material.cuda_replacements.append(
                    {
                        "pattern": pattern,
                        "replacement": replacement,
                    }
                )

    # 第三方库修复
    third_party_kw = ["deepspeed", "accelerate", "flash_attn", "xformers", "apex"]
    for kw in third_party_kw:
        if kw in content.lower():
            existing = [f for f in material.third_party_fixes if f["library"] == kw]
            if not existing:
                material.third_party_fixes.append(
                    {
                        "library": kw,
                        "note": "需要昇腾适配版本或替代方案",
                    }
                )


def _extract_optimize_steps(material: SkillMaterial, content: str):
    """提取优化步骤"""
    # 运行时环境变量
    env_var_patterns = [
        ("TASK_QUEUE_ENABLE", r"TASK_QUEUE_ENABLE[=\s]+(\d)"),
        ("PYTORCH_NPU_ALLOC_CONF", r"PYTORCH_NPU_ALLOC_CONF[=\s]+(\S+)"),
        ("CPU_AFFINITY_CONF", r"CPU_AFFINITY_CONF[=\s]+(\S+)"),
        ("HCCL_BUFFSIZE", r"HCCL_BUFFSIZE[=\s]+(\S+)"),
        ("OMP_PROC_BIND", r"OMP_PROC_BIND[=\s]+(\S+)"),
        ("ASCEND_RT_VISIBLE_DEVICES", r"ASCEND_RT_VISIBLE_DEVICES[=\s]+(\S+)"),
    ]

    for var_name, pattern in env_var_patterns:
        match = re.search(pattern, content)
        if match and var_name not in material.runtime_env_vars:
            material.runtime_env_vars[var_name] = match.group(1)

    # Benchmark 结果
    bench_patterns = [
        (r"(?:qps|throughput|tokens/s)[\s:]+(\d+\.?\d*)", "qps"),
        (r"(?:accuracy|acc)[\s:]+(\d+\.?\d*)", "accuracy"),
        (r"(?:latency|ttft|tpot)[\s:]+(\d+\.?\d*)\s*ms", "latency_ms"),
    ]

    for pattern, metric_name in bench_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            material.benchmark_results.append(
                {
                    "metric": metric_name,
                    "value": match.group(1),
                    "source": "history",
                }
            )


def _extract_verify_commands(material: SkillMaterial, content: str):
    """提取验证命令"""
    # 查找 python / bash 验证命令
    verify_matches = re.findall(
        r"(?:python|bash)\s+([\w/\-\.]+\s*(?:--?\w+\s*\S*){0,5})",
        content,
    )
    for cmd in verify_matches:
        # 过滤掉非验证命令
        if any(
            kw in cmd.lower()
            for kw in ["test", "eval", "verify", "benchmark", "infer", "run"]
        ):
            clean_cmd = (
                "python " + cmd.strip()
                if cmd.strip() not in material.verify_commands
                else ""
            )
            if clean_cmd and clean_cmd not in material.verify_commands:
                material.verify_commands.append(clean_cmd)


def _extract_common_issues(material: SkillMaterial, content: str):
    """提取常见问题"""
    # 查找错误和修复
    error_matches = re.findall(
        r"(?:Error|Exception|FAILED|error):\s*(.{20,200})",
        content,
    )
    for error_msg in error_matches[:5]:  # 限制数量
        existing = [i for i in material.common_issues if i["error"] == error_msg[:100]]
        if not existing:
            material.common_issues.append(
                {
                    "error": error_msg[:200],
                    "fix": "(待从历史中提取修复方案)",
                }
            )


# ========== Step 5: 生成模型 Skill ==========

SKILL_MD_TEMPLATE = """# {model_name} 昇腾适配 Skill

## 触发场景

- 用户提到在昇腾 NPU 上运行/适配/优化 {model_name}
- 用户提到 {model_name} 的 CUDA 迁移或昇腾部署
- 搜索关键词：{keywords}

## 模型信息

| 项目 | 值 |
|------|-----|
| 模型名 | {model_name} |
| 仓库 | {repo_path} |
| 入口脚本 | {entry_scripts} |
| 权重 | {weight_names} |

## 环境要求

| 依赖 | 版本 |
|------|------|
| Python | {python_version} |
| PyTorch | {torch_version} |
| torch_npu | {torch_npu_version} |
| CANN | {cann_version} |
| Conda 环境 | {conda_env_name} |

### 安装依赖

```bash
pip install {pip_install_line}
```

{env_setup_section}

## 适配步骤

{adapt_steps_section}

### CUDA API 替换

{cuda_replacements_section}

### 第三方库处理

{third_party_fixes_section}

{distributed_section}

## 优化步骤

{optimize_steps_section}

### 运行时环境变量

{runtime_env_vars_section}

### 性能基准

{benchmark_section}

## 验证步骤

{verify_commands_section}

{accuracy_section}

## 常见问题

{common_issues_section}

---

*此 Skill 由 ascend-history-to-skill 从历史记录自动生成，生成时间: {timestamp}*
*数据来源: {sources}*
*命中记录: {hit_count} 条*
"""

DEFAULT_ENV_SETUP = """```bash
# 昇腾基础环境变量
export ASCEND_HOME_PATH=/usr/local/Ascend/ascend-toolkit/latest
source $ASCEND_HOME_PATH/bin/set_env.bash
```"""


def generate_skill(
    model_name: str,
    material: SkillMaterial,
    output_dir: str | None = None,
) -> SkillGenerationResult:
    """生成模型 Skill

    Args:
        model_name: 模型名
        material: 从历史提炼的素材
        output_dir: 输出目录，默认 ~/.codex/skills/<model-skill-name>/
    """
    result = SkillGenerationResult(model_name=model_name)

    # 确定输出目录
    skill_dir = _safe_skill_output_dir(model_name, output_dir)
    skill_dir.mkdir(parents=True, exist_ok=True)
    result.skill_dir = str(skill_dir)

    # 确定阶段
    stages = []
    if material.adapt_steps or material.cuda_replacements:
        stages.append("adapt")
    if material.optimize_steps or material.runtime_env_vars:
        stages.append("optimize")
    if not stages:
        stages = ["adapt"]
    result.stages = stages

    # 生成 SKILL.md
    skill_content = _render_skill_md(model_name, material, stages)
    skill_md_path = skill_dir / "SKILL.md"

    with open(skill_md_path, "w", encoding="utf-8") as f:
        f.write(skill_content)

    result.skill_md_path = str(skill_md_path)

    # 生成参考脚本目录
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)

    # 生成验证脚本
    if material.verify_commands:
        verify_script = scripts_dir / "verify.sh"
        with open(verify_script, "w", encoding="utf-8") as f:
            f.write(f"#!/bin/bash\n# {model_name} 昇腾验证脚本\nset -e\n\n")
            for cmd in material.verify_commands[:10]:
                f.write(f"# {cmd}\n")
                f.write(f"# {cmd} 2>/dev/null || echo '验证跳过'\n\n")

    # 生成环境变量脚本
    if material.runtime_env_vars:
        env_script = scripts_dir / "setup_env.sh"
        with open(env_script, "w", encoding="utf-8") as f:
            f.write(f"#!/bin/bash\n# {model_name} 昇腾运行时环境变量\n\n")
            for var, val in material.runtime_env_vars.items():
                f.write(f"export {var}={val}\n")

    # 生成 references 目录
    refs_dir = skill_dir / "references"
    refs_dir.mkdir(exist_ok=True)

    # 保存原始命中摘要
    hits_summary = refs_dir / "hits_summary.json"
    with open(hits_summary, "w", encoding="utf-8") as f:
        json.dump(
            [h.to_dict() for h in material.hits[:50]],
            f,
            indent=2,
            ensure_ascii=False,
        )

    result.hits_found = len(material.hits)
    result.hits_used = len(
        [
            h
            for h in material.hits
            if h.evidence_level in (EvidenceLevel.VERIFIED, EvidenceLevel.LIKELY)
        ]
    )
    result.success = True

    return result


def _render_skill_md(
    model_name: str,
    material: SkillMaterial,
    stages: list[str],
) -> str:
    """渲染 SKILL.md 内容"""

    # 关键词
    variants = normalize_model_name(model_name)
    keywords = ", ".join(variants[:5])

    # 适配步骤
    adapt_section = ""
    if material.adapt_steps:
        adapt_section = "\n".join(
            "{}. {}\n   - {}".format(i + 1, s.get("title", ""), s.get("detail", ""))
            for i, s in enumerate(material.adapt_steps)
        )
    else:
        adapt_section = "（从历史记录中未提取到明确适配步骤，需手动补充）"

    # CUDA 替换表
    if material.cuda_replacements:
        cuda_section = "| 原始 | 替换 |\n|------|------|\n"
        for r in material.cuda_replacements:
            cuda_section += "| `{}` | `{}` |\n".format(r["pattern"], r["replacement"])
    else:
        cuda_section = "（未发现 CUDA 替换记录）"

    # 第三方库
    if material.third_party_fixes:
        tp_section = "| 库 | 说明 |\n|-----|------|\n"
        for f in material.third_party_fixes:
            tp_section += "| {} | {} |\n".format(f["library"], f["note"])
    else:
        tp_section = "（未发现第三方库修复记录）"

    # 分布式约束
    dist_section = ""
    if material.distributed_constraints:
        dist_section = "### 分布式约束\n\n"
        for c in material.distributed_constraints:
            dist_section += f"- {c}\n"

    # 优化步骤
    if material.optimize_steps:
        opt_section = "\n".join(
            "{}. {}\n   - {}".format(i + 1, s.get("title", ""), s.get("detail", ""))
            for i, s in enumerate(material.optimize_steps)
        )
    else:
        opt_section = "（从历史记录中未提取到明确优化步骤）"

    # 运行时环境变量
    if material.runtime_env_vars:
        env_section = "```bash\n"
        for var, val in material.runtime_env_vars.items():
            env_section += f"export {var}={val}\n"
        env_section += "```\n"
    else:
        env_section = "（未发现运行时环境变量记录）"

    # 性能基准
    if material.benchmark_results:
        bench_section = "| 指标 | 值 | 来源 |\n|------|-----|------|\n"
        for b in material.benchmark_results:
            bench_section += "| {} | {} | {} |\n".format(
                b.get("metric", ""), b.get("value", ""), b.get("source", "")
            )
    else:
        bench_section = "（未发现性能基准记录）"

    # 验证命令
    if material.verify_commands:
        verify_section = "\n".join(
            f"```bash\n{cmd}\n```" for cmd in material.verify_commands[:10]
        )
    else:
        verify_section = "（未发现验证命令记录）"

    # 精度参考
    acc_section = ""
    if material.accuracy_references:
        acc_section = "### 精度参考\n\n"
        for ref in material.accuracy_references:
            acc_section += "- {}: {} (参考值: {})\n".format(
                ref.get("dataset", ""),
                ref.get("value", ""),
                ref.get("reference", "N/A"),
            )

    # 常见问题
    if material.common_issues:
        issues_section = ""
        for i, issue in enumerate(material.common_issues[:10]):
            issues_section += "### 问题 {}: {}\n\n**修复**: {}\n\n".format(
                i + 1,
                issue.get("error", "")[:80],
                issue.get("fix", "待补充"),
            )
    else:
        issues_section = "（未发现常见问题记录）"

    return SKILL_MD_TEMPLATE.format(
        model_name=model_name,
        keywords=keywords,
        repo_path=material.repo_path or "(待确认)",
        entry_scripts=", ".join(material.entry_scripts) or "(待确认)",
        weight_names=", ".join(material.weight_names) or "(待确认)",
        python_version=material.python_version or "(待确认)",
        torch_version=material.torch_version or "(待确认)",
        torch_npu_version=material.torch_npu_version or "(待确认)",
        cann_version=material.cann_version or "(待确认)",
        conda_env_name=material.conda_env_name or "(待确认)",
        pip_install_line=" ".join(material.pip_packages[:10]) or "(待确认)",
        env_setup_section=DEFAULT_ENV_SETUP,
        adapt_steps_section=adapt_section,
        cuda_replacements_section=cuda_section,
        third_party_fixes_section=tp_section,
        distributed_section=dist_section,
        optimize_steps_section=opt_section,
        runtime_env_vars_section=env_section,
        benchmark_section=bench_section,
        verify_commands_section=verify_section,
        accuracy_section=acc_section,
        common_issues_section=issues_section,
        timestamp=datetime.now().isoformat(),
        sources=", ".join(set(h.source.value for h in material.hits)) or "unknown",
        hit_count=len(material.hits),
    )


# ========== Step 6: 生成后验证 ==========


def validate_skill(skill_dir: str) -> tuple[bool, list[str]]:
    """验证生成的 Skill

    1. 结构验证: 检查必要文件是否存在
    2. 内容验证: 检查引用路径、环境名是否存在
    """
    errors = []
    skill_path = Path(skill_dir)

    # 结构验证
    if not (skill_path / "SKILL.md").exists():
        errors.append("SKILL.md 不存在")

    # 内容验证 - 读取 SKILL.md 检查引用
    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        with open(skill_md, encoding="utf-8") as f:
            content = f.read()

        # 检查是否包含占位符
        placeholders = re.findall(r"\(待\w+\)", content)
        if len(placeholders) > 10:
            errors.append(f"SKILL.md 包含过多占位符 ({len(placeholders)})，信息不足")

        # 检查引用路径是否存在
        path_refs = re.findall(r"`(/[\w/\-\.]+)`", content)
        for ref_path in path_refs[:20]:
            if not os.path.exists(ref_path):
                errors.append(f"引用路径不存在: {ref_path}")

    # 检查脚本文件
    scripts_dir = skill_path / "scripts"
    if scripts_dir.exists():
        for script in scripts_dir.glob("*.sh"):
            with open(script, encoding="utf-8") as f:
                script_content = f.read()
            # 检查脚本是否引用不存在的命令
            cmd_refs = re.findall(r"(?:python|bash)\s+([\w/\-\.]+)", script_content)
            for cmd in cmd_refs:
                if cmd.startswith("/") and not os.path.exists(cmd):
                    errors.append(f"脚本引用不存在的路径: {cmd} (in {script.name})")

    return len(errors) == 0, errors


# ========== 一键执行 ==========


def history_to_skill(
    model_name: str,
    stages: list[str] | None = None,
    keywords: list[str] | None = None,
    sources: list[HistorySource] | None = None,
    extra_roots: list[str] | None = None,
    exclude_terms: list[str] | None = None,
    output_dir: str | None = None,
    max_hits: int = 100,
) -> SkillGenerationResult:
    """一键执行 ascend-history-to-skill 完整流程

    1. 明确目标模型和范围
    2. 搜索历史记录
    3. 只保留高价值证据
    4. 整理成 skill 素材
    5. 生成模型 skill
    6. 生成后验证
    """
    logger.info(f"Step 1: 明确目标 - model={model_name}, stages={stages}")

    # Step 2: 搜索历史
    logger.info("Step 2: 搜索历史记录...")
    hits = search_history(
        model_name=model_name,
        stages=stages,
        keywords=keywords,
        sources=sources,
        extra_roots=extra_roots,
        exclude_terms=exclude_terms,
        max_hits=max_hits,
    )
    logger.info(f"搜索完成: {len(hits)} 条命中")

    # Step 3: 过滤高价值证据
    logger.info("Step 3: 过滤高价值证据...")
    hits = filter_high_value_hits(hits)
    logger.info(f"过滤后: {len(hits)} 条高价值记录")

    # Step 4: 整理素材
    logger.info("Step 4: 整理 Skill 素材...")
    material = extract_skill_material(model_name, hits)

    # Step 5: 生成 Skill
    logger.info("Step 5: 生成模型 Skill...")
    result = generate_skill(model_name, material, output_dir)

    # Step 6: 验证
    logger.info("Step 6: 生成后验证...")
    valid, errors = validate_skill(result.skill_dir)
    result.validation_passed = valid
    result.validation_errors = errors

    return result
