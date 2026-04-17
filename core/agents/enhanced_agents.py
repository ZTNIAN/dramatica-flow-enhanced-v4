"""
OpenMOSS 增强 Agent 集成（V3→V4）
包含 10 个新 Agent，从 OpenMOSS 项目引入，增强写作质量。

P1（4个）：
  1. CharacterGrowthExpert  — 角色详细设定 + 成长弧线规划
  2. DialogueExpert         — 对话质量审核 + 角色语言特征设计
  3. EmotionCurveDesigner   — 整书情绪曲线 + 每章情绪类型规划
  4. FeedbackExpert         — 读者反馈分类 → 转发对应 Agent → 跟踪闭环

P2（3个）：
  5. HookDesigner           — 7种章末钩子类型设计（方法论注入 ArchitectAgent）
  6. OpeningEndingDesigner  — 黄金三章 + 全书结尾（方法论注入 ArchitectAgent）
  7. StyleConsistencyChecker — 五维一致性检查

P3（3个）：
  8. SceneArchitect         — 场景空间感/五感层次/氛围/转场质量审核
  9. PsychologicalPortrayalExpert — 心理真实性/层次/留白/行为一致性审核
  10. MiroFishReader        — 模拟1000名读者测试 + 收集反馈
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..llm import LLMProvider, LLMMessage, parse_llm_json, with_retry


# ── V5: 知识库从公共模块导入（消除重复）────────────────────────────────────────
from .kb import (
    KB_HOOK_DESIGNER, KB_OPENING_ENDING, KB_EMOTION_CURVE,
    KB_DIALOGUE, KB_CHAR_GROWTH, KB_STYLE_CONSISTENCY,
    KB_SCENE_ARCHITECT, KB_PSYCHOLOGICAL,
    track_kb_query,
)

# 向后兼容别名
_KB_HOOK_DESIGNER = KB_HOOK_DESIGNER
_KB_OPENING_ENDING = KB_OPENING_ENDING
_KB_EMOTION_CURVE = KB_EMOTION_CURVE
_KB_DIALOGUE = KB_DIALOGUE
_KB_CHAR_GROWTH = KB_CHAR_GROWTH
_KB_STYLE_CONSISTENCY = KB_STYLE_CONSISTENCY
_KB_SCENE_ARCHITECT = KB_SCENE_ARCHITECT
_KB_PSYCHOLOGICAL = KB_PSYCHOLOGICAL


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CharacterGrowthExpert — 角色详细设定 + 成长弧线规划
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CharacterGrowthProfile:
    """单个角色的成长档案"""
    character_id: str
    name: str
    basic_setting: dict[str, str] = field(default_factory=dict)       # 基础设定
    personality: dict[str, str] = field(default_factory=dict)          # 性格设定
    backstory: dict[str, str] = field(default_factory=dict)            # 家世与经历
    preferences: list[str] = field(default_factory=list)               # 喜好与习惯
    abilities: dict[str, str] = field(default_factory=dict)            # 能力设定
    growth_trajectory: dict[str, str] = field(default_factory=dict)    # 成长轨迹
    turning_points: list[dict[str, str]] = field(default_factory=list) # 关键转折点
    relationship_matrix: dict[str, str] = field(default_factory=dict)  # 人物关系矩阵


@dataclass
class CharacterGrowthResult:
    """角色成长规划结果"""
    profiles: list[CharacterGrowthProfile]
    overall_note: str


class _GrowthProfileSchema(BaseModel):
    character_id: str
    name: str
    basic_setting: dict[str, str] = Field(default_factory=dict)
    personality: dict[str, str] = Field(default_factory=dict)
    backstory: dict[str, str] = Field(default_factory=dict)
    preferences: list[str] = Field(default_factory=list)
    abilities: dict[str, str] = Field(default_factory=dict)
    growth_trajectory: dict[str, str] = Field(default_factory=dict)
    turning_points: list[dict[str, str]] = Field(default_factory=list)
    relationship_matrix: dict[str, str] = Field(default_factory=dict)


class _GrowthResultSchema(BaseModel):
    profiles: list[_GrowthProfileSchema] = Field(default_factory=list)
    overall_note: str = ""


class CharacterGrowthExpert:
    """角色成长专家：为每个主要角色生成详细的成长档案"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def plan_character_growth(
        self,
        world_context: str,
        characters_json: str,
    ) -> CharacterGrowthResult:
        kb_section = ""
        if _KB_CHAR_GROWTH:
            kb_section = f"\n## 角色成长方法论\n{_KB_CHAR_GROWTH[:3000]}\n"

        prompt = f"""你是资深的角色设计师，精通角色塑造和成长弧线规划。
请为以下世界观中的每个主要角色生成详细的成长档案。

## 世界观
{world_context[:3000]}

## 角色列表
{characters_json[:3000]}
{kb_section}
## 输出要求（JSON）
{{"profiles": [
  {{
    "character_id": "角色ID",
    "name": "角色名",
    "basic_setting": {{
      "name_full": "全名（含字号/绰号）",
      "appearance": "外貌描述",
      "age": "年龄",
      "identity": "身份/职业"
    }},
    "personality": {{
      "core": "核心性格（1-3个关键词）",
      "cause": "性格成因",
      "flaw": "性格缺陷",
      "contrast": "性格反差",
      "behavior_lock": "绝对不做的事"
    }},
    "backstory": {{
      "family": "家庭背景",
      "growth": "成长经历关键节点",
      "turning": "人生转折点",
      "relationships": "重要人际关系"
    }},
    "preferences": ["喜好/习惯列表"],
    "abilities": {{
      "combat": "战斗技能",
      "special": "非战斗特长",
      "growth_space": "能力成长空间",
      "limit": "能力上限和代价"
    }},
    "growth_trajectory": {{
      "early": "初期状态（1-30%）",
      "mid": "中期状态（30-60%）",
      "late": "后期状态（60-90%）",
      "final": "终局状态（90-100%）"
    }},
    "turning_points": [
      {{"type": "认知/能力/情感/价值观", "chapter_range": "预期章节范围", "description": "转折描述"}}
    ],
    "relationship_matrix": {{
      "角色A": "关系类型 + 发展预期",
      "角色B": "关系类型 + 发展预期"
    }}
  }}
], "overall_note": "整体角色关系格局一句话总结"}}

要求：
- 每个主要角色（protagonist/antagonist/impact/guardian/sidekick）都要有档案
- 每个角色至少3个关键转折点
- 成长轨迹要体现从弱到强/从迷茫到清晰的变化
只输出 JSON。"""

        def _call() -> CharacterGrowthResult:
            resp = self.llm.complete([
                LLMMessage("system", "你是角色设计专家，只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _GrowthResultSchema, "plan_character_growth")
            profiles = [
                CharacterGrowthProfile(
                    character_id=p.character_id,
                    name=p.name,
                    basic_setting=p.basic_setting,
                    personality=p.personality,
                    backstory=p.backstory,
                    preferences=p.preferences,
                    abilities=p.abilities,
                    growth_trajectory=p.growth_trajectory,
                    turning_points=p.turning_points,
                    relationship_matrix=p.relationship_matrix,
                )
                for p in parsed.profiles
            ]
            return CharacterGrowthResult(
                profiles=profiles,
                overall_note=parsed.overall_note,
            )

        return with_retry(_call)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DialogueExpert — 对话质量审核 + 角色语言特征设计
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class LanguageFingerprint:
    """角色语言指纹（六维度）"""
    character_name: str
    vocabulary: str = ""          # 词汇偏好
    sentence_structure: str = ""  # 句式结构
    interjections: str = ""       # 语气词
    speaking_speed: str = ""      # 说话速度
    expression_habit: str = ""    # 表达习惯
    knowledge_scope: str = ""     # 知识范围


@dataclass
class DialogueReviewResult:
    """对话审查结果"""
    language_fingerprints: list[LanguageFingerprint]
    issues: list[dict[str, str]]
    rhythm_analysis: str
    era_check: str
    overall_score: int
    suggestions: list[str]


class _LanguageFingerprintSchema(BaseModel):
    character_name: str
    vocabulary: str = ""
    sentence_structure: str = ""
    interjections: str = ""
    speaking_speed: str = ""
    expression_habit: str = ""
    knowledge_scope: str = ""


class _DialogueReviewSchema(BaseModel):
    language_fingerprints: list[_LanguageFingerprintSchema] = Field(default_factory=list)
    issues: list[dict[str, str]] = Field(default_factory=list)
    rhythm_analysis: str = ""
    era_check: str = ""
    overall_score: int = 80
    suggestions: list[str] = Field(default_factory=list)


class DialogueExpert:
    """对话专家：审核对话质量 + 设计角色语言指纹"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def review_dialogue(
        self,
        chapter_content: str,
        chapter_number: int,
        characters: list[str],
        era: str = "古代",
    ) -> DialogueReviewResult:
        kb_section = ""
        if _KB_DIALOGUE:
            kb_section = f"\n## 对话专家方法论\n{_KB_DIALOGUE[:3000]}\n"

        # 截断正文
        content = chapter_content[:5000]
        if len(chapter_content) > 5000:
            content += "\n...(截断)"

        prompt = f"""你是对话质量专家，请审核第 {chapter_number} 章的对话质量。

## 章节正文
{content}

## 登场角色
{', '.join(characters)}

## 时代背景
{era}
{kb_section}
## 审核要求

### 语言特征六维度（为每个有对话的角色设计语言指纹）
1. 词汇偏好
2. 句式结构
3. 语气词
4. 说话速度
5. 表达习惯
6. 知识范围

### 潜台词分析
- 每段重要对话是否有言外之意
- 是否有说教/直白的问题

### 对话节奏
- 密度和长度是否合理
- 是否有张弛交替

### 时代语言审核
- 是否有不符合时代背景的用语

## 输出格式（JSON）
{{"language_fingerprints": [
  {{"character_name": "角色名", "vocabulary": "词汇偏好描述", "sentence_structure": "句式结构描述",
    "interjections": "常用语气词", "speaking_speed": "说话速度", "expression_habit": "表达习惯", "knowledge_scope": "知识范围"}}
], "issues": [
  {{"character": "角色名", "type": "问题类型", "description": "具体问题", "suggestion": "修改建议"}}
], "rhythm_analysis": "对话节奏分析（100字）", "era_check": "时代语言审核结果（100字）",
"overall_score": 85, "suggestions": ["建议1", "建议2"]}}

只输出 JSON。"""

        def _call() -> DialogueReviewResult:
            resp = self.llm.complete([
                LLMMessage("system", "你是对话质量专家，擅长分析角色语言特征。只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _DialogueReviewSchema, "review_dialogue")
            fingerprints = [
                LanguageFingerprint(
                    character_name=fp.character_name,
                    vocabulary=fp.vocabulary,
                    sentence_structure=fp.sentence_structure,
                    interjections=fp.interjections,
                    speaking_speed=fp.speaking_speed,
                    expression_habit=fp.expression_habit,
                    knowledge_scope=fp.knowledge_scope,
                )
                for fp in parsed.language_fingerprints
            ]
            return DialogueReviewResult(
                language_fingerprints=fingerprints,
                issues=parsed.issues,
                rhythm_analysis=parsed.rhythm_analysis,
                era_check=parsed.era_check,
                overall_score=parsed.overall_score,
                suggestions=parsed.suggestions,
            )

        return with_retry(_call)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. EmotionCurveDesigner — 整书情绪曲线 + 每章情绪类型规划
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ChapterEmotion:
    """单章情绪规划"""
    chapter_number: int
    emotion_type: str       # 压抑/紧张/恐惧/爽/感动/幽默/温暖/愤怒/悲伤/满足
    intensity: int          # 1-10
    note: str = ""


@dataclass
class EmotionCurveResult:
    """情绪曲线设计结果"""
    curve: list[ChapterEmotion]
    overall_trend: str
    climax_chapters: list[int]
    design_notes: str


class _ChapterEmotionSchema(BaseModel):
    chapter_number: int
    emotion_type: str
    intensity: int
    note: str = ""


class _EmotionCurveSchema(BaseModel):
    curve: list[_ChapterEmotionSchema] = Field(default_factory=list)
    overall_trend: str = ""
    climax_chapters: list[int] = Field(default_factory=list)
    design_notes: str = ""


class EmotionCurveDesigner:
    """情绪曲线设计师：为整本书规划情绪曲线"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def design_emotion_curve(
        self,
        chapter_outlines: list[dict],
        total_chapters: int,
        genre: str = "玄幻",
    ) -> EmotionCurveResult:
        kb_section = ""
        if _KB_EMOTION_CURVE:
            kb_section = f"\n## 情绪曲线方法论\n{_KB_EMOTION_CURVE[:3000]}\n"

        # 提取章纲摘要
        outline_summary = "\n".join(
            f"- 第{co.get('chapter_number', i+1)}章《{co.get('title', '')}》：{co.get('summary', '')[:80]}"
            for i, co in enumerate(chapter_outlines[:total_chapters])
        )

        prompt = f"""你是情绪曲线设计师，请为以下小说规划每章的情绪类型和强度。

## 小说信息
- 题材：{genre}
- 总章数：{total_chapters}

## 章纲摘要
{outline_summary[:3000]}
{kb_section}
## 情绪类型
压抑/紧张/恐惧/爽/感动/幽默/温暖/愤怒/悲伤/满足

## 设计原则
1. 整体趋势：波动上升
2. 不能超过3章平淡（强度<5）
3. 高潮前要压抑（先抑后扬）
4. 爽点后要期待
5. 情绪类型要多样（不能连续3章同类型）

## 输出格式（JSON）
{{"curve": [
  {{"chapter_number": 1, "emotion_type": "紧张", "intensity": 6, "note": "开篇紧张感"}}
], "overall_trend": "波动上升，三次大高潮", "climax_chapters": [25, 50, 85],
"design_notes": "整体设计说明（100字）"}}

请为所有 {total_chapters} 章设计情绪曲线。
只输出 JSON。"""

        def _call() -> EmotionCurveResult:
            resp = self.llm.complete([
                LLMMessage("system", "你是情绪曲线设计师，精通读者心理学。只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _EmotionCurveSchema, "design_emotion_curve")
            curve = [
                ChapterEmotion(
                    chapter_number=ce.chapter_number,
                    emotion_type=ce.emotion_type,
                    intensity=ce.intensity,
                    note=ce.note,
                )
                for ce in parsed.curve
            ]
            return EmotionCurveResult(
                curve=curve,
                overall_trend=parsed.overall_trend,
                climax_chapters=parsed.climax_chapters,
                design_notes=parsed.design_notes,
            )

        return with_retry(_call)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. FeedbackExpert — 读者反馈分类 → 转发对应 Agent → 跟踪闭环
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class FeedbackItem:
    """单条反馈分类结果"""
    category: str           # 世界观/人物/数值/文笔/剧情/细节/结构
    description: str        # 反馈内容摘要
    target_agent: str       # 应转发的 Agent
    priority: str           # high/medium/low
    action_suggestion: str  # 行动建议


@dataclass
class FeedbackResult:
    """反馈分类结果"""
    items: list[FeedbackItem]
    summary: str


class _FeedbackItemSchema(BaseModel):
    category: str
    description: str
    target_agent: str
    priority: str = "medium"
    action_suggestion: str = ""


class _FeedbackResultSchema(BaseModel):
    items: list[_FeedbackItemSchema] = Field(default_factory=list)
    summary: str = ""


_FEEDBACK_ROUTING = {
    "世界观": "WorldBuilderAgent（规划师）",
    "人物": "CharacterGrowthExpert（人物成长专家）",
    "数值": "数值专家",
    "文笔": "WriterAgent（作家）",
    "剧情": "OutlinePlannerAgent（规划师）+ WriterAgent（作家）",
    "细节": "WriterAgent（作家）",
    "结构": "OutlinePlannerAgent（规划师）",
}


class FeedbackExpert:
    """反馈专家：分类读者反馈并路由到对应 Agent"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def categorize_feedback(
        self,
        feedback_text: str,
        chapter_range: str = "",
    ) -> FeedbackResult:
        routing_str = "\n".join(f"- {k}问题 → {v}" for k, v in _FEEDBACK_ROUTING.items())

        prompt = f"""你是读者反馈分析专家。请对以下读者反馈进行分类和路由。

## 读者反馈
{feedback_text[:3000]}

## 反馈涉及章节
{chapter_range or '未指定'}

## 反馈分类路由规则
{routing_str}

## 输出格式（JSON）
{{"items": [
  {{"category": "人物", "description": "反馈内容摘要", "target_agent": "CharacterGrowthExpert", "priority": "high",
    "action_suggestion": "建议重新审视角色成长弧线"}}
], "summary": "整体反馈趋势分析（50字）"}}

要求：
- 每条反馈必须分类到以上7个类别之一
- target_agent 使用路由规则中的名称
- priority 根据问题严重程度判断
只输出 JSON。"""

        def _call() -> FeedbackResult:
            resp = self.llm.complete([
                LLMMessage("system", "你是反馈分析专家，擅长分类和路由。只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _FeedbackResultSchema, "categorize_feedback")
            items = [
                FeedbackItem(
                    category=fi.category,
                    description=fi.description,
                    target_agent=fi.target_agent,
                    priority=fi.priority,
                    action_suggestion=fi.action_suggestion,
                )
                for fi in parsed.items
            ]
            return FeedbackResult(items=items, summary=parsed.summary)

        return with_retry(_call)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. HookDesigner — 方法论注入（不作为独立 Agent）
# ═══════════════════════════════════════════════════════════════════════════════

def get_hook_designer_prompt_injection() -> str:
    """返回钩子设计方法论，注入到 ArchitectAgent 的 prompt 中"""
    if not _KB_HOOK_DESIGNER:
        return ""
    return f"""
## 章末钩子设计参考（HookDesigner 方法论）
{_KB_HOOK_DESIGNER[:3000]}

> 请在 chapter_end_hook 中运用以上7种钩子类型之一，确保章末有强驱动力。
"""


# ═══════════════════════════════════════════════════════════════════════════════
# 6. OpeningEndingDesigner — 方法论注入（不作为独立 Agent）
# ═══════════════════════════════════════════════════════════════════════════════

def get_opening_ending_prompt_injection(chapter_number: int, total_chapters: int = 90) -> str:
    """返回开篇/结尾设计方法论，根据章节位置注入到 ArchitectAgent 的 prompt 中"""
    if not _KB_OPENING_ENDING:
        return ""

    sections = []

    if chapter_number <= 3:
        sections.append(f"""
## 黄金三章设计参考（OpeningEndingDesigner 方法论 — 开篇阶段）
{_KB_OPENING_ENDING[:2000]}

> 第 {chapter_number} 章属于黄金三章范围，请特别注意开篇钩子的强度。
> {'第一章：需要最强的开篇钩子' if chapter_number == 1 else '第二章：需要深化人物引入' if chapter_number == 2 else '第三章：需要自然引入世界观 + 埋下伏笔'}
""")

    if chapter_number >= total_chapters - 3:
        sections.append(f"""
## 全书结尾设计参考（OpeningEndingDesigner 方法论 — 结尾阶段）
{_KB_OPENING_ENDING[2000:] if len(_KB_OPENING_ENDING) > 2000 else ''}

> 第 {chapter_number} 章接近全书结尾，注意高潮对决/主题升华/情感落点。
""")

    return "\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. StyleConsistencyChecker — 五维一致性检查
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class StyleDimension:
    """单个风格维度检查结果"""
    dimension: str
    score: int              # 0-100
    deviation: str          # 偏差程度：轻微/中度/严重
    details: str            # 具体表现
    suggestion: str = ""    # 修改建议


@dataclass
class StyleConsistencyResult:
    """风格一致性检查结果"""
    dimensions: list[StyleDimension]
    overall_score: int
    passed: bool
    summary: str


class _StyleDimensionSchema(BaseModel):
    dimension: str
    score: int = 80
    deviation: str = "无"
    details: str = ""
    suggestion: str = ""


class _StyleConsistencySchema(BaseModel):
    dimensions: list[_StyleDimensionSchema] = Field(default_factory=list)
    overall_score: int = 80
    passed: bool = True
    summary: str = ""


class StyleConsistencyChecker:
    """风格一致性检查器：跨章节检查五维一致性"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def check_consistency(
        self,
        chapters: list[dict[str, str]],  # [{"number": 1, "content": "..."}]
        sample_count: int = 5,
    ) -> StyleConsistencyResult:
        kb_section = ""
        if _KB_STYLE_CONSISTENCY:
            kb_section = f"\n## 风格一致性检查方法论\n{_KB_STYLE_CONSISTENCY[:2000]}\n"

        # 随机采样章节
        import random
        if len(chapters) > sample_count:
            sampled = random.sample(chapters, sample_count)
        else:
            sampled = chapters

        chapters_text = "\n\n".join(
            f"### 第 {ch.get('number', '?')} 章（节选）\n{ch.get('content', '')[:1000]}"
            for ch in sampled
        )

        prompt = f"""你是风格一致性检查专家，请跨章节检查以下五维一致性。

## 采样章节
{chapters_text}
{kb_section}
## 五维检查要求
1. 文笔风格一致性（语言风格/描写密度/修辞使用/句式偏好）
2. 人物语气一致性（词汇习惯/句式/语气/口头禅）
3. 叙事节奏一致性
4. 时代背景一致性
5. 情感基调一致性

## 偏差等级
- 轻微：不影响阅读
- 中度：影响体验，建议修改
- 严重：严重影响体验，必须修改

## 输出格式（JSON）
{{"dimensions": [
  {{"dimension": "文笔风格", "score": 90, "deviation": "轻微", "details": "具体表现", "suggestion": "建议"}}
], "overall_score": 88, "passed": true, "summary": "整体评价（50字）"}}

评分标准：overall_score >= 85 为通过
只输出 JSON。"""

        def _call() -> StyleConsistencyResult:
            resp = self.llm.complete([
                LLMMessage("system", "你是风格一致性检查专家。只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _StyleConsistencySchema, "check_consistency")
            dimensions = [
                StyleDimension(
                    dimension=d.dimension,
                    score=d.score,
                    deviation=d.deviation,
                    details=d.details,
                    suggestion=d.suggestion,
                )
                for d in parsed.dimensions
            ]
            return StyleConsistencyResult(
                dimensions=dimensions,
                overall_score=parsed.overall_score,
                passed=parsed.overall_score >= 85,
                summary=parsed.summary,
            )

        return with_retry(_call)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. SceneArchitect — 场景空间感/五感层次/氛围/转场质量审核
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SceneDimension:
    """场景审核维度"""
    dimension: str
    score: int
    issues: list[str]
    suggestions: list[str]


@dataclass
class SceneAuditResult:
    """场景审核结果"""
    dimensions: list[SceneDimension]
    overall_score: int
    passed: bool
    summary: str


class _SceneDimensionSchema(BaseModel):
    dimension: str
    score: int = 80
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class _SceneAuditSchema(BaseModel):
    dimensions: list[_SceneDimensionSchema] = Field(default_factory=list)
    overall_score: int = 80
    passed: bool = True
    summary: str = ""


class SceneArchitect:
    """场景建筑师：审核场景的空间感/五感/氛围/转场质量"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def audit_scene(
        self,
        chapter_content: str,
        chapter_number: int,
    ) -> SceneAuditResult:
        kb_section = ""
        if _KB_SCENE_ARCHITECT:
            kb_section = f"\n## 场景构建方法论\n{_KB_SCENE_ARCHITECT[:3000]}\n"

        content = chapter_content[:5000]
        if len(chapter_content) > 5000:
            content += "\n...(截断)"

        prompt = f"""你是场景建筑师，请审核第 {chapter_number} 章的场景质量。

## 章节正文
{content}
{kb_section}
## 四维审核要求

### 1. 空间感（权重 25%）
- 三维空间描述是否清晰
- 角色定位是否明确
- 空间转换是否自然

### 2. 感官细节（权重 30%）
- 五感运用是否充分（至少3种）
- 感官描写是否有层次
- 感官是否服务于情绪
- 是否有留白

### 3. 氛围营造（权重 25%）
- 氛围是否与情绪一致
- 意象运用是否恰当
- 氛围变化是否自然

### 4. 转场质量（权重 20%）
- 场景切换是否自然
- 时空转换是否清晰
- 转场手法是否恰当

## 输出格式（JSON）
{{"dimensions": [
  {{"dimension": "空间感", "score": 85, "issues": ["问题1"], "suggestions": ["建议1"]}},
  {{"dimension": "感官细节", "score": 90, "issues": [], "suggestions": []}},
  {{"dimension": "氛围营造", "score": 88, "issues": [], "suggestions": []}},
  {{"dimension": "转场质量", "score": 82, "issues": [], "suggestions": []}}
], "overall_score": 87, "passed": true, "summary": "整体评价"}}

加权总分 = 空间感×0.25 + 感官细节×0.30 + 氛围营造×0.25 + 转场质量×0.20
overall_score >= 85 为通过
只输出 JSON。"""

        def _call() -> SceneAuditResult:
            resp = self.llm.complete([
                LLMMessage("system", "你是场景建筑师，专注于场景质量审核。只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _SceneAuditSchema, "audit_scene")
            dimensions = [
                SceneDimension(
                    dimension=d.dimension,
                    score=d.score,
                    issues=d.issues,
                    suggestions=d.suggestions,
                )
                for d in parsed.dimensions
            ]
            return SceneAuditResult(
                dimensions=dimensions,
                overall_score=parsed.overall_score,
                passed=parsed.overall_score >= 85,
                summary=parsed.summary,
            )

        return with_retry(_call)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. PsychologicalPortrayalExpert — 心理真实性/层次/留白/行为一致性审核
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class PsychologicalDimension:
    """心理审核维度"""
    dimension: str
    score: int
    issues: list[str]
    suggestions: list[str]


@dataclass
class PsychologicalAuditResult:
    """心理审核结果"""
    dimensions: list[PsychologicalDimension]
    overall_score: int
    passed: bool
    summary: str


class _PsychDimensionSchema(BaseModel):
    dimension: str
    score: int = 80
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class _PsychAuditSchema(BaseModel):
    dimensions: list[_PsychDimensionSchema] = Field(default_factory=list)
    overall_score: int = 80
    passed: bool = True
    summary: str = ""


class PsychologicalPortrayalExpert:
    """心理刻画专家：审核角色心理的真实性和层次感"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def audit_psychology(
        self,
        chapter_content: str,
        chapter_number: int,
        characters: list[str],
    ) -> PsychologicalAuditResult:
        kb_section = ""
        if _KB_PSYCHOLOGICAL:
            kb_section = f"\n## 心理刻画方法论\n{_KB_PSYCHOLOGICAL[:3000]}\n"

        content = chapter_content[:5000]
        if len(chapter_content) > 5000:
            content += "\n...(截断)"

        prompt = f"""你是心理刻画专家，请审核第 {chapter_number} 章角色心理描写质量。

## 章节正文
{content}

## 登场角色
{', '.join(characters)}
{kb_section}
## 四维审核要求

### 1. 心理真实性（权重 30%）
- 性格一致性
- 情境合理性
- 人性普遍性
- 是否脸谱化

### 2. 心理层次（权重 25%）
- 情绪层次（表面 vs 真实）
- 意识层次
- 心理防御
- 认知失调

### 3. 心理留白（权重 25%）
- 是否给读者留了思考空间
- 暗示技巧运用
- 反差艺术
- 沉默的力量

### 4. 心理与行为一致性（权重 20%）
- 行为是否有心理动机
- 情感驱动是否合理
- 认知驱动是否合理

## 输出格式（JSON）
{{"dimensions": [
  {{"dimension": "心理真实性", "score": 88, "issues": ["问题1"], "suggestions": ["建议1"]}},
  {{"dimension": "心理层次", "score": 85, "issues": [], "suggestions": []}},
  {{"dimension": "心理留白", "score": 90, "issues": [], "suggestions": []}},
  {{"dimension": "心理与行为一致性", "score": 87, "issues": [], "suggestions": []}}
], "overall_score": 88, "passed": true, "summary": "整体评价"}}

overall_score >= 85 为通过
只输出 JSON。"""

        def _call() -> PsychologicalAuditResult:
            resp = self.llm.complete([
                LLMMessage("system", "你是心理刻画专家，专注于角色心理质量审核。只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _PsychAuditSchema, "audit_psychology")
            dimensions = [
                PsychologicalDimension(
                    dimension=d.dimension,
                    score=d.score,
                    issues=d.issues,
                    suggestions=d.suggestions,
                )
                for d in parsed.dimensions
            ]
            return PsychologicalAuditResult(
                dimensions=dimensions,
                overall_score=parsed.overall_score,
                passed=parsed.overall_score >= 85,
                summary=parsed.summary,
            )

        return with_retry(_call)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. MiroFishReader — 模拟1000名读者测试 + 收集反馈
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ReaderSegment:
    """读者分层反馈"""
    segment_name: str       # 核心/普通/路人
    percentage: int         # 占比
    overall_score: int      # 整体评分（1-100）
    engagement: int         # 参与度（1-100）
    feedback: list[str]     # 具体反馈
    key_issues: list[str]   # 关键问题


@dataclass
class MiroFishResult:
    """MiroFish 模拟测试结果"""
    total_readers: int
    overall_score: int
    segments: list[ReaderSegment]
    top_issues: list[str]
    improvement_suggestions: list[str]


class _ReaderSegmentSchema(BaseModel):
    segment_name: str
    percentage: int = 0
    overall_score: int = 70
    engagement: int = 70
    feedback: list[str] = Field(default_factory=list)
    key_issues: list[str] = Field(default_factory=list)


class _MiroFishSchema(BaseModel):
    total_readers: int = 1000
    overall_score: int = 70
    segments: list[_ReaderSegmentSchema] = Field(default_factory=list)
    top_issues: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)


class MiroFishReader:
    """MiroFish 读者模拟器：模拟1000名读者测试并收集反馈"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def simulate_readers(
        self,
        chapter_content: str,
        chapter_number: int,
        genre: str = "玄幻",
    ) -> MiroFishResult:
        content = chapter_content[:5000]
        if len(chapter_content) > 5000:
            content += "\n...(截断)"

        prompt = f"""你是 MiroFish 读者模拟系统。请模拟 1000 名读者对第 {chapter_number} 章的阅读体验。

## 读者分层
- 核心读者 200 人（20%）：忠实粉丝，对该题材有深度理解，要求高
- 普通读者 500 人（50%）：常规读者，看个乐，要求中等
- 路人读者 300 人（30%）：随机读者，容易弃书，要求低

## 读者画像
- 性别分布：80% 男 / 20% 女
- 年龄分布：20-40 岁
- 文化水平：30% 高中 / 50% 专科 / 20% 本科
- 题材：{genre}

## 章节正文
{content}

## 收集维度（每类读者分别评估）
1. 整体满意度（1-100）
2. 代入感（1-100）
3. 紧迫感（想不想看下一章，1-100）
4. 文笔评价（1-100）
5. 人物评价（1-100）
6. 具体问题（文字反馈）
7. 弃书风险点

## 输出格式（JSON）
{{"total_readers": 1000, "overall_score": 82,
"segments": [
  {{"segment_name": "核心读者", "percentage": 20, "overall_score": 78, "engagement": 85,
    "feedback": ["对话不够精炼", "期待后续发展"], "key_issues": ["某些对话过于直白"]}},
  {{"segment_name": "普通读者", "percentage": 50, "overall_score": 85, "engagement": 88,
    "feedback": ["节奏不错", "打斗很爽"], "key_issues": []}},
  {{"segment_name": "路人读者", "percentage": 30, "overall_score": 80, "engagement": 75,
    "feedback": ["还行"], "key_issues": ["世界观不够清晰"]}}
], "top_issues": ["问题1", "问题2"],
"improvement_suggestions": ["建议1", "建议2"]}}

要求：
- 核心读者评分通常最低（要求最高）
- 路人读者最容易弃书（对世界设定容忍度低）
- overall_score = 各层加权平均（核心×0.2 + 普通×0.5 + 路人×0.3）
只输出 JSON。"""

        def _call() -> MiroFishResult:
            resp = self.llm.complete([
                LLMMessage("system", "你是 MiroFish 读者模拟系统，模拟真实读者反应。只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _MiroFishSchema, "simulate_readers")
            segments = [
                ReaderSegment(
                    segment_name=s.segment_name,
                    percentage=s.percentage,
                    overall_score=s.overall_score,
                    engagement=s.engagement,
                    feedback=s.feedback,
                    key_issues=s.key_issues,
                )
                for s in parsed.segments
            ]
            return MiroFishResult(
                total_readers=parsed.total_readers,
                overall_score=parsed.overall_score,
                segments=segments,
                top_issues=parsed.top_issues,
                improvement_suggestions=parsed.improvement_suggestions,
            )

        return with_retry(_call)
