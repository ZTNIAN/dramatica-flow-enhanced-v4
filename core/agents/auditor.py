"""AuditorAgent — 审计员 Agent：三层质量审计"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, field_validator, Field

from ..llm import LLMProvider, LLMMessage, parse_llm_json, with_retry
from ..types.narrative import Character
from ..narrative import ChapterOutlineSchema

from .kb import KB_REVIEW_CRITERIA_95, KB_REDLINES, KB_ANTI_AI, track_kb_query

_KB_REVIEW_CRITERIA_95 = KB_REVIEW_CRITERIA_95
_KB_REDLINES = KB_REDLINES
_KB_ANTI_AI = KB_ANTI_AI

@dataclass
class AuditIssue:
    dimension: str
    severity: AuditSeverity
    description: str
    location: str | None = None   # 问题在原文的关键句引用
    suggestion: str | None = None
    excerpt: str | None = None    # 触发规则的文本片段（验证器用）




@dataclass
class AuditReport:
    chapter_number: int
    passed: bool
    issues: list[AuditIssue]
    overall_note: str
    # 增强：加权评分
    dimension_scores: dict[str, int] = field(default_factory=dict)  # 各维度得分
    weighted_total: int = 0    # 加权总分（满分100）
    redline_violations: list[str] = field(default_factory=list)  # 红线违规

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")




class _AuditIssueSchema(BaseModel):
    dimension: str
    severity: str  # "critical" | "warning" | "info"
    description: str
    location: str | None = None
    suggestion: str | None = None




class _AuditReportSchema(BaseModel):
    chapter_number: int
    passed: bool
    issues: list[_AuditIssueSchema] = Field(default_factory=list)
    overall_note: str = ""
    dimension_scores: dict[str, int] = Field(default_factory=dict)
    weighted_total: int = 0
    redline_violations: list[str] = Field(default_factory=list)


# 原版审计维度（保留）
AUDIT_DIMENSIONS = [
    "OOC（角色行为是否符合性格锁定，性格锁定的事绝对不能做）",
    "信息边界（角色是否知道了他不应知道的信息，信息获取是否有合理来源）",
    "因果一致性（每个事件的发生是否有前因，是否靠巧合推进）",
    "情感弧线（本章情感弧是否符合章纲目标，情绪变化是否有足够铺垫）",
    "大纲偏离（本章是否完成了所有 mandatory_tasks，核心冲突是否落地）",
    "节奏（快场景与慢场景的分配是否合理，是否有张弛）",
    "伏笔管理（新开伏笔是否有铺垫，已声明回收的伏笔是否在正文中落地）",
    "去AI味（AI标记词密度、套话、元叙事、报告式语言、集体反应）",
    "连续性（角色位置/道具/时间线/称谓/数值是否前后一致）",
    "冲突质量（每个场景的冲突是否源于角色目标与障碍的张力，不靠巧合）",
    "结尾钩子（章末钩子是否有效实现，是否能驱动读者继续读）",
    "跨线程一致性（多线叙事时，不同线程的角色位置/时间线/信息是否冲突）",
]

# ═══════════════════════════════════════════════════════════════════════════════
# 增强版：9 维度加权评分 + 17 条红线一票否决
# ═══════════════════════════════════════════════════════════════════════════════

# 加权维度定义：(名称, 权重, 检查要点)
AUDIT_DIMENSIONS_WEIGHTED = [
    ("逻辑自洽",   0.20, "因果链成立、反派不降智、战力不崩、信息边界"),
    ("文笔去AI化", 0.15, "无AI标记词、无套话、短句为主、口语化、有瑕疵"),
    ("场景构建",   0.15, "感官细节>=3种、画面感强、空间清晰、氛围到位"),
    ("心理刻画",   0.15, "Show don't tell、情感有层次、有留白、共鸣感"),
    ("对话质量",   0.10, "符合身份、有潜台词、有打断/省略/答非所问"),
    ("风格一致",   0.10, "文笔统一、节奏连贯、无其他题材腔调混入"),
    ("设定一致",   0.08, "世界观无矛盾、数值稳定、称谓一致、时间线正确"),
    ("结构合理",   0.05, "起承转合自然、节拍完成、节奏张弛有度"),
    ("人物OOC",    0.02, "性格连贯、行为有动机、非工具人"),
]

# 17条红线（一票否决）
REDBLINE_VIOLATIONS = [
    "角色严重OOC（做了性格锁定中绝对不做的事）",
    "战力数值10倍以上跳变",
    "重要伏笔丢失（声明回收但未落地）",
    "风格严重污染（混入其他题材腔调超3处）",
    "元叙事出现（核心动机/叙事节奏/人物弧线等）",
    "报告式语言出现（分析了形势/综合考虑等）",
    "集体反应套话出现（全场震惊/众人哗然等）",
    "套话模板出现（XX的尽头是XX/人生就像XX）",
    "AI感叹句出现（多么XX啊/何等XX啊）",
    "机械排序出现（首先其次最后三连）",
    "过度解释出现（也就是说/换句话说）",
    "角色同时出现在不同地点（跨线程矛盾）",
    "时间线前后矛盾",
    "因果靠巧合推进（无前因的关键转折）",
    "配角只剩震惊/附和/送人头三种功能",
    "信息越界（角色知道他没见过的事）",
    "数据通胀（资源收益无具体数值或暴涨）",
]

# 加权总分通过线
AUDIT_PASS_TOTAL = 95      # 总分 >= 95
AUDIT_PASS_MIN_DIM = 85    # 所有单项 >= 85




class AuditorAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm  # 应传入 temperature=0 的实例

    def audit_chapter(
        self,
        chapter_content: str,
        chapter_number: int,
        blueprint: ArchitectBlueprint,
        truth_context: str,
        settlement: PostWriteSettlement,
        cross_thread_context: str = "",
    ) -> AuditReport:

        # 安全序列化 blueprint（dataclass → dict，避免 json.dumps 崩溃）
        blueprint_dict = dataclasses.asdict(blueprint)
        blueprint_summary = f"""\
- 核心冲突：{blueprint.core_conflict}
- 情感旅程：{blueprint.emotional_journey.get('start','')} → {blueprint.emotional_journey.get('end','')}
- 必须推进伏笔：{blueprint.hooks_to_advance}
- 计划埋下伏笔：{blueprint.hooks_to_plant}
- 结尾钩子：{blueprint.chapter_end_hook}
- 风险点：{blueprint.pre_write_checklist.risk_scan}
- 登场角色：{blueprint.pre_write_checklist.active_characters}"""

        settlement_summary = f"""\
- 资源变化：{settlement.resource_changes}
- 新开伏笔：{settlement.new_hooks}
- 回收伏笔：{settlement.resolved_hooks}
- 关系变化：{settlement.relationship_changes}
- 信息揭示：{settlement.info_revealed}
- 位置变化：{settlement.character_position_changes}
- 情感变化：{settlement.emotional_changes}"""

        # 原版维度（保留向后兼容）
        dimensions_str = "\n".join(f"{i+1}. {d}" for i, d in enumerate(AUDIT_DIMENSIONS))

        # 增强：加权维度
        weighted_dims_str = "\n".join(
            f"| {name} | {int(weight*100)}% | {desc} |"
            for name, weight, desc in AUDIT_DIMENSIONS_WEIGHTED
        )
        redline_str = "\n".join(f"{i+1}. {r}" for i, r in enumerate(REDBLINE_VIOLATIONS))

        # 正文截断（避免超 token）
        content_for_audit = chapter_content
        if len(chapter_content) > 6000:
            content_for_audit = chapter_content[:3000] + "\n\n...[中间省略]...\n\n" + chapter_content[-2000:]

        # ── 跨线程上下文注入（多线叙事） ──
        cross_thread_section = ""
        if cross_thread_context.strip():
            cross_thread_section = f"""
### 跨线程一致性参照
以下是其他线程最近的时间轴和因果链，用于检测跨线程冲突：
{cross_thread_context[:2000]}

> 请特别检查：
> - 同一角色是否同时出现在不同地点
> - 不同线程中的时间线是否矛盾
> - 一个线程的事件是否与另一个线程的已确立事实冲突
"""

        prompt = f"""\
## 叙事审计：第 {chapter_number} 章

### 审计维度（逐一检查，不可遗漏）
{dimensions_str}

### 章节正文
{content_for_audit}

### 写前蓝图（参照标准）
{blueprint_summary}
{cross_thread_section}
### 写后结算表（需与正文交叉验证）
{settlement_summary}

### 真相文件（连续性参照）
{truth_context[:3000] if len(truth_context) > 3000 else truth_context}

## 评判标准
- critical：叙事逻辑断裂、明显 OOC、重大连续性错误、mandatory_task 完全未完成、跨线程时间线矛盾
- warning：轻微节奏问题、AI 痕迹、伏笔处理不当、情感弧线偏差
- info：可选优化建议

## 增强评分维度（逐一打分 0-100）
| 维度 | 权重 | 检查要点 |
{weighted_dims_str}

## 17条红线（一票否决，任一触发则 passed=false）
{redline_str}
{_KB_REDLINES[:2000] if _KB_REDLINES else ""}

## 审查者详细检查清单（V3新增，逐条核对）
{_KB_REVIEWER_CHECKLIST[:3000] if _KB_REVIEWER_CHECKLIST else ""}

## 输出格式（严格 JSON）
{{
  "chapter_number": {chapter_number},
  "passed": true,
  "issues": [
    {{
      "dimension": "维度名称",
      "severity": "critical",
      "description": "具体问题描述，指出原文哪里出了问题",
      "location": "原文关键句引用（30字以内）",
      "suggestion": "具体修复建议"
    }}
  ],
  "overall_note": "整体评价（1-2句话）",
  "dimension_scores": {{
    "逻辑自洽": 90,
    "文笔去AI化": 88,
    "场景构建": 92,
    "心理刻画": 87,
    "对话质量": 90,
    "风格一致": 91,
    "设定一致": 93,
    "结构合理": 89,
    "人物OOC": 95
  }},
  "weighted_total": 90,
  "redline_violations": []
}}

评判规则：
- 若 redline_violations 非空 → passed=false
- 若 weighted_total < {AUDIT_PASS_TOTAL} → passed=false
- 若任一 dimension_scores < {AUDIT_PASS_MIN_DIM} → passed=false

只输出 JSON，不要任何说明。"""

        def _call() -> AuditReport:
            # 记录知识库查询
            if _KB_REVIEWER_CHECKLIST:
                _track_kb_query("auditor", "reviewer-checklist.md", "审查者检查清单")
            if _KB_REDLINES:
                _track_kb_query("auditor", "redlines.md", "红线检查")
            if _KB_REVIEW_CRITERIA_95:
                _track_kb_query("auditor", "review-criteria-95.md", "95分标准")

            resp = self.llm.complete([
                LLMMessage(
                    "system",
                    "你是严格的叙事审计员，专注叙事质量，"
                    "对 critical 问题零容忍但不制造假阳性。"
                    "只输出合法 JSON，不输出任何说明文字。",
                ),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _AuditReportSchema, "audit_chapter")
            issues = [
                AuditIssue(
                    dimension=i.dimension,
                    severity=i.severity,  # type: ignore
                    description=i.description,
                    location=i.location,
                    suggestion=i.suggestion,
                )
                for i in parsed.issues
            ]
            # 原版判定：有 critical 则不通过
            has_critical = any(i.severity == "critical" for i in issues)
            # 增强判定：红线 + 加权分数
            has_redline = len(parsed.redline_violations) > 0
            low_total = parsed.weighted_total < AUDIT_PASS_TOTAL if parsed.weighted_total > 0 else False
            low_dim = any(s < AUDIT_PASS_MIN_DIM for s in parsed.dimension_scores.values()) if parsed.dimension_scores else False
            passed = not (has_critical or has_redline or low_total or low_dim)
            return AuditReport(
                chapter_number=parsed.chapter_number,
                passed=passed,
                issues=issues,
                overall_note=parsed.overall_note,
                dimension_scores=parsed.dimension_scores,
                weighted_total=parsed.weighted_total,
                redline_violations=parsed.redline_violations,
            )

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 4. 修订者 Agent
# ─────────────────────────────────────────────────────────────────────────────

ReviseMode = Literal["spot-fix", "rewrite-section", "polish"]

CHANGELOG_SEPARATOR = "===CHANGELOG==="

_MODE_INSTRUCTIONS: dict[str, str] = {
    "spot-fix":
        "只修改有问题的句子/段落，其余正文一字不动。"
        "保持原段落结构，只替换问题文本。",
    "rewrite-section":
        "重写包含问题的段落（前后各保留一段作为锚点），"
        "保持整体情节不变。",
    "polish":
        "在不改变情节的前提下提升文笔流畅度，"
        "禁止增删段落、修改角色名、加入新情节。",
}


