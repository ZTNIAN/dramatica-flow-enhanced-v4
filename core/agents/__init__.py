"""
四个核心 Agent：建筑师、写手、审计员、修订者
增强：
  - 知识库注入：写手/建筑师 prompt 自动引用去AI味规则、对比示例、写作技巧
修复：
  - ArchitectAgent 用 pydantic 校验，不再裸 json.loads
  - AuditorAgent blueprint 序列化改用 dataclasses.asdict
  - AuditIssue 增加 excerpt 字段（pipeline 需要）
  - WriterAgent 增加前情摘要注入参数
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, field_validator, Field

from ..llm import LLMProvider, LLMMessage, parse_llm_json, with_retry
from ..types.narrative import Character
from ..narrative import ChapterOutlineSchema

# ── V4: OpenMOSS 增强 Agent 导入 ──────────────────────────────────────────────
from .enhanced_agents import (
    CharacterGrowthExpert, CharacterGrowthResult, CharacterGrowthProfile,
    DialogueExpert, DialogueReviewResult, LanguageFingerprint,
    EmotionCurveDesigner, EmotionCurveResult, ChapterEmotion,
    FeedbackExpert, FeedbackResult, FeedbackItem,
    StyleConsistencyChecker, StyleConsistencyResult, StyleDimension,
    SceneArchitect, SceneAuditResult, SceneDimension,
    PsychologicalPortrayalExpert, PsychologicalAuditResult, PsychologicalDimension,
    MiroFishReader, MiroFishResult, ReaderSegment,
    get_hook_designer_prompt_injection,
    get_opening_ending_prompt_injection,
)


# ── V5: 知识库从公共模块导入（消除重复）────────────────────────────────────────
from .kb import (
    KB_ANTI_AI, KB_BEFORE_AFTER, KB_WRITING_TECHNIQUES,
    KB_COMMON_MISTAKES, KB_FIVE_SENSES, KB_SHOW_DONT_TELL,
    KB_WRITER_SKILLS, KB_REVIEWER_CHECKLIST, KB_REVIEW_CRITERIA_95, KB_REDLINES,
    track_kb_query, get_kb_queries,
)

# 向后兼容别名（避免改Agent内部引用）
_KB_ANTI_AI = KB_ANTI_AI
_KB_BEFORE_AFTER = KB_BEFORE_AFTER
_KB_WRITING_TECHNIQUES = KB_WRITING_TECHNIQUES
_KB_COMMON_MISTAKES = KB_COMMON_MISTAKES
_KB_FIVE_SENSES = KB_FIVE_SENSES
_KB_SHOW_DONT_TELL = KB_SHOW_DONT_TELL
_KB_WRITER_SKILLS = KB_WRITER_SKILLS
_KB_REVIEWER_CHECKLIST = KB_REVIEWER_CHECKLIST
_KB_REVIEW_CRITERIA_95 = KB_REVIEW_CRITERIA_95
_KB_REDLINES = KB_REDLINES
_track_kb_query = track_kb_query


# ─────────────────────────────────────────────────────────────────────────────
# 1. 建筑师 Agent
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PreWriteChecklist:
    active_characters: list[str]
    required_locations: list[str]
    resources_in_play: list[str]
    hooks_status: list[str]
    risk_scan: str


@dataclass
class ArchitectBlueprint:
    core_conflict: str
    hooks_to_advance: list[str]
    hooks_to_plant: list[str]
    emotional_journey: dict[str, str]
    chapter_end_hook: str
    pace_notes: str
    pre_write_checklist: PreWriteChecklist
    # ── 多线叙事扩展 ──
    pov_character_id: str = ""             # 本章视角角色
    thread_id: str = ""                     # 本章所属线程
    thread_context: str = ""               # 其他线程的当前状态摘要（跨线程感知）


# ── pydantic schema 用于 LLM 输出校验 ────────────────────────────────────────

class _ChecklistSchema(BaseModel):
    active_characters: list[str] = Field(default_factory=list)
    required_locations: list[str] = Field(default_factory=list)
    resources_in_play: list[str] = Field(default_factory=list)
    hooks_status: list[str] = Field(default_factory=list)
    risk_scan: str = ""

    @field_validator("active_characters", "required_locations", "resources_in_play", "hooks_status", mode="before")
    @classmethod
    def _ensure_list(cls, v):
        if isinstance(v, str):
            return [line.strip() for line in v.replace("；", "\n").replace(";", "\n").split("\n") if line.strip()]
        if isinstance(v, dict):
            return [f"{k}: {val}" if val else k for k, val in v.items()]
        return v


class _BlueprintSchema(BaseModel):
    core_conflict: str
    hooks_to_advance: list[str] = Field(default_factory=list)
    hooks_to_plant: list[str] = Field(default_factory=list)
    emotional_journey: dict[str, str] = Field(default_factory=dict)
    chapter_end_hook: str = ""
    pace_notes: str = ""
    pre_write_checklist: _ChecklistSchema = Field(default_factory=_ChecklistSchema)
    # 多线叙事扩展
    pov_character_id: str = ""
    thread_id: str = ""
    thread_context: str = ""

    @field_validator("hooks_to_advance", "hooks_to_plant", mode="before")
    @classmethod
    def _ensure_list(cls, v):
        if isinstance(v, str):
            return [line.strip() for line in v.replace("；", "\n").replace(";", "\n").split("\n") if line.strip()]
        return v


class ArchitectAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def plan_chapter(
        self,
        chapter_outline: ChapterOutlineSchema,
        world_context: str,
        pending_hooks: str,
        prior_chapter_summary: str = "",
        pov_character: Character | None = None,
        thread_context: str = "",
    ) -> ArchitectBlueprint:

        prior_ctx = f"\n## 上章摘要\n{prior_chapter_summary}" if prior_chapter_summary else ""

        # ── POV 视角角色（多线叙事） ──
        pov_section = ""
        resolved_pov_id = ""
        if pov_character:
            resolved_pov_id = pov_character.id
            pov_section = f"""
## 视角角色（POV：{pov_character.name}）
- 当前短期目标：{pov_character.current_goal or '（未设定）'}
- 隐藏动机：{pov_character.hidden_agenda or '（无）'}
- 性格锁定（绝对不做）：{'、'.join(pov_character.behavior_lock)}
- 角色职能：{pov_character.role}
> 蓝图设计应围绕 {pov_character.name} 的视角，情感旅程以该角色为准。
"""

        # ── 跨线程上下文（多线叙事） ──
        thread_section = ""
        resolved_thread_id = getattr(chapter_outline, "thread_id", "thread_main") or "thread_main"
        if thread_context.strip():
            thread_section = f"""
## 其他线程状态（跨线程感知）
{thread_context}
> 注意：确保本章事件与其他线程的时间线不冲突。
"""

        prompt = f"""\
你是精通戏剧结构的故事建筑师，为写手规划本章写作蓝图。

## 章纲
- 章节：第 {chapter_outline.chapter_number} 章《{chapter_outline.title}》
- 摘要：{chapter_outline.summary}
- 必完任务：{'；'.join(chapter_outline.mandatory_tasks)}
- 情感弧：{chapter_outline.emotional_arc.get('start', '')} → {chapter_outline.emotional_arc.get('end', '')}
- 字数目标：{chapter_outline.target_words} 字
- 节拍序列：{' → '.join(b.description for b in chapter_outline.beats)}
{prior_ctx}
{pov_section}{thread_section}
## 当前世界状态
{world_context}

## 未闭合伏笔
{pending_hooks if pending_hooks.strip() else "（暂无）"}

## 写作技巧参考（建筑师需在蓝图中规划对应手法）
{_KB_WRITING_TECHNIQUES[:3000] if _KB_WRITING_TECHNIQUES else "（无）"}

## 五感描写指南（建筑师需在蓝图中标注每场景的感官配比）
{_KB_FIVE_SENSES[:2000] if _KB_FIVE_SENSES else "（无）"}

## 常见错误及避免方法（建筑师需在 risk_scan 中预判本章可能出现的错误）
{_KB_COMMON_MISTAKES[:2000] if _KB_COMMON_MISTAKES else "（无）"}

## 去AI味红线（建筑师需在节奏建议中规避以下问题）
{_KB_ANTI_AI[:2000] if _KB_ANTI_AI else "（无）"}

{get_hook_designer_prompt_injection()}
{get_opening_ending_prompt_injection(chapter_outline.chapter_number, 90)}

请输出完整 JSON，字段说明：
- core_conflict：本章核心冲突（一句话，必须源于角色目标与障碍的碰撞）
- hooks_to_advance：需要在本章推进的伏笔 ID 列表
- hooks_to_plant：本章可以埋下的新伏笔描述列表（每条一句话）
- emotional_journey：{{"start": "章节开始时主角的情绪状态", "end": "章节结束时的情绪状态"}}
- chapter_end_hook：本章最后一个场景/句子的悬念钩子，驱动读者读下一章
- pace_notes：节奏建议（快/慢场景的分配，张弛安排）
- pre_write_checklist：
  - active_characters：本章登场的所有角色名列表
  - required_locations：本章涉及的地点列表
  - resources_in_play：本章涉及的道具/资源/物品列表
  - hooks_status：每条相关伏笔的当前推进状态（一句话）
  - risk_scan：最可能引发连续性错误的高风险点（具体说明）

只输出 JSON，不要任何前言、说明或 Markdown。"""

        def _call() -> ArchitectBlueprint:
            # 记录知识库查询
            _track_kb_query("architect", "writing_techniques.md", "蓝图规划参考")
            if _KB_FIVE_SENSES:
                _track_kb_query("architect", "five-senses-description.md", "五感配比参考")
            if _KB_COMMON_MISTAKES:
                _track_kb_query("architect", "common-mistakes.md", "常见错误预判")
            if _KB_ANTI_AI:
                _track_kb_query("architect", "anti_ai_rules.md", "去AI味红线")

            resp = self.llm.complete([
                LLMMessage("system", "你是故事建筑师，只输出合法 JSON，不输出任何说明文字。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _BlueprintSchema, "plan_chapter")
            cl_data = parsed.pre_write_checklist
            checklist = PreWriteChecklist(
                active_characters=cl_data.active_characters,
                required_locations=cl_data.required_locations,
                resources_in_play=cl_data.resources_in_play,
                hooks_status=cl_data.hooks_status,
                risk_scan=cl_data.risk_scan,
            )
            return ArchitectBlueprint(
                core_conflict=parsed.core_conflict,
                hooks_to_advance=parsed.hooks_to_advance,
                hooks_to_plant=parsed.hooks_to_plant,
                emotional_journey=parsed.emotional_journey,
                chapter_end_hook=parsed.chapter_end_hook,
                pace_notes=parsed.pace_notes,
                pre_write_checklist=checklist,
                pov_character_id=resolved_pov_id,
                thread_id=resolved_thread_id,
                thread_context=thread_context,
            )

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 2. 写手 Agent
# ─────────────────────────────────────────────────────────────────────────────

SETTLEMENT_SEPARATOR = "===SETTLEMENT==="


@dataclass
class PostWriteSettlement:
    """写后结算表：本章对世界状态的改变"""
    resource_changes: list[str] = field(default_factory=list)
    new_hooks: list[str] = field(default_factory=list)
    resolved_hooks: list[str] = field(default_factory=list)
    relationship_changes: list[str] = field(default_factory=list)
    info_revealed: list[dict[str, str]] = field(default_factory=list)
    character_position_changes: list[dict[str, str]] = field(default_factory=list)
    emotional_changes: list[dict[str, str]] = field(default_factory=list)


@dataclass
class WriterOutput:
    content: str
    settlement: PostWriteSettlement


WRITER_SYSTEM_PROMPT = """\
你是一位优秀的中文小说写手，专注于{genre}题材。

## 创作铁律（不可违反）
1. 只写动作、感知、对话——不替读者下结论，不做心理分析式独白
2. 冲突必须源于角色目标与障碍的碰撞，绝对不靠巧合推进
3. 每个场景必须推进叙事 OR 揭示角色，二者至少占其一
4. 场景结尾状态必须比开始更极端（更好/更坏/意外转折）
5. 对话要有潜台词，人物说的话和真正想说的话之间要有张力
6. 每个场景至少使用3种感官（视觉必选+听觉/嗅觉/触觉至少2种）
7. Show don't tell —— 用动作、物件、价格说话，禁止直接说"感到XX"

## 45条写作风格约束（必须遵守）

### 去AI味（1-15）
1. 绝对禁止：首先/其次/最后/总之/综上所述
2. 绝对禁止：更关键的是/更奇怪的是/更有意思的是
3. 绝对禁止：众所周知/不言而喻/毫无疑问/显而易见
4. 绝对禁止：让我们来看看/让我们一起/一方面
5. 绝对禁止：在这个信息爆炸的时代/在这个时代
6. 绝对禁止：值得注意的是/需要注意的是
7. AI标记词（仿佛/忽然/竟然/不禁/宛如/猛地/顿时）每3000字各最多1次
8. 禁止套话模板：XX的尽头是XX / 人生就像XX / 这个世界上有两种人
9. 禁止AI感叹句：多么XX啊 / 何等XX啊
10. 禁止过度解释：也就是说/换句话说/简单来说
11. 破折号「——」全书最多用3次，珍惜使用
12. 禁止机械排序：首先...其次...最后 / 第一...第二...第三
13. 禁止对仗句式：一方面...另一方面
14. 禁止完美逻辑链：因为A所以B进而C最终D
15. 句子长短交替，不要连续3句长度相近

### Show Don't Tell（16-25）
16. 禁止直接说"他感到XX"/"她很XX"/"心里很XX"
17. 用具体动作代替情绪描述：捏碎茶杯>生气，手抖>害怕
18. 用感官细节代替概括描写：写雨打在脸上的感觉>写"雨很大"
19. 用物、势、制度摩擦说话，少喊口号
20. 钱权必须落地，通过具体数值兑现
21. 允许矛盾情感：又恨又爱、又怕又想
22. 情感变化要有层次，不能突变
23. 用周围人的反应侧面烘托，而非直接描写
24. 用道具/环境暗示人物状态
25. 每个场景至少3种感官（视觉+听觉+嗅觉/触觉）

### 句式与节奏（26-35）
26. 短句为主：60%以上为15字以内短句
27. 允许不完整句、省略句、口语化表达
28. 用具体数字代替"很多/大量/无数"
29. 允许矛盾：又恨又爱、又怕又想、既紧张又兴奋
30. 对话要像真人说话：有打断、有省略、有答非所问
31. 每3-5段紧张后要有1-2段舒缓（张弛交替）
32. 高潮前必须有一次舒缓（蓄力），高潮后必须有一次舒缓（喘息）
33. 允许语言有狠劲，但不要堆砌陈词滥调
34. 智斗高于武斗，利益交换必须成立
35. 主角保留"非功能性时刻"（抽烟、失眠、沉默、试探）

### 叙事原则（36-45）
36. 每章至少推进一项：信息/地位/资源/伤亡/仇恨/境界
37. 小冲突尽快兑现反馈，不要把爽点无限后置
38. 涉及资源收益时必须落到具体数值
39. 用动作、器物反应、局部感官制造压迫感
40. 禁止"流水账"：不要写起床刷牙等无意义内容
41. 禁止配角只剩三种功能：震惊、附和、送人头
42. 反派要有自己的算盘、恐惧、筹码，不能是木桩
43. 成功最好伴随不可逆代价
44. 信息边界：角色不能知道他没见过的事
45. 因果链：每个事件必须回答"因为什么→发生了什么→导致了什么"

## 绝对禁止项（红线）
- 元叙事（核心动机/叙事节奏/人物弧线）
- 报告式语言（分析了形势/从…角度来看/综合考虑）
- 作者说教（显然/不言而喻/毫无疑问）
- 集体反应套话（全场震惊/众人哗然/所有人都）
- 套话模板（XX的尽头是XX/人生就像XX）

## 写后必须输出结算表
正文写完后，用 ===SETTLEMENT=== 分隔，输出 JSON 结算表。"""


class WriterAgent:
    def __init__(self, llm: LLMProvider, style_guide: str = "", genre: str = "玄幻"):
        self.llm = llm
        self.style_guide = style_guide
        self.genre = genre

    def write_chapter(
        self,
        scene_summaries: str,
        blueprint: ArchitectBlueprint,
        protagonist: Character,
        world_context: str,
        chapter_number: int,
        target_words: int,
        prior_summaries: str = "",
        chapter_title: str = "",
        pov_character: Character | None = None,
        thread_context: str = "",
        pending_hooks: str = "",
        causal_chain: str = "",
        emotional_arcs: str = "",
    ) -> WriterOutput:
        system = WRITER_SYSTEM_PROMPT.format(genre=self.genre)
        if self.style_guide:
            system += f"\n\n## 文风要求\n{self.style_guide}"

        # 注入对比示例库（P0：帮助写手理解"好vs坏"的差距）
        if _KB_BEFORE_AFTER:
            system += "\n\n## 修改前后对比示例（写完后自查，确保不像「修改前」）\n" + _KB_BEFORE_AFTER[:4000]

        # V3 新增：注入写手专属技能库（开篇钩子/五感模板/人物出场/对话技巧/节奏控制/章末钩子）
        if _KB_WRITER_SKILLS:
            system += "\n\n## 写手专属技能库（参考应用）\n" + _KB_WRITER_SKILLS[:4000]

        # V3 新增：注入 Show Don't Tell 详解
        if _KB_SHOW_DONT_TELL:
            system += "\n\n## Show Don't Tell 转换表（写完后自查，确保没有直接说\"感到XX\"）\n" + _KB_SHOW_DONT_TELL[:3000]

        prior_ctx = ""
        if prior_summaries.strip():
            # 只取最近 3 章摘要，避免 context 过长
            lines = prior_summaries.strip().split("\n## ")
            recent = lines[-3:] if len(lines) > 3 else lines
            prior_ctx = f"\n### 前情回顾（最近章节）\n## {'## '.join(recent)}"

        # scene_summaries 已经是格式化好的节拍序列
        beats_str = scene_summaries

        # ── POV 视角角色（多线叙事） ──
        effective_pov = pov_character or protagonist
        pov_section = ""
        if pov_character and pov_character.id != protagonist.id:
            pov_section = f"""
### 视角角色（POV：{pov_character.name}）
- 当前短期目标：{pov_character.current_goal or '（未设定）'}
- 隐藏动机：{pov_character.hidden_agenda or '（无）'}
- 性格锁定（绝对不做）：{'、'.join(pov_character.behavior_lock)}
- 角色职能：{pov_character.role}
> 重要：本章以 {pov_character.name} 的视角叙事，描写风格、感知范围、
> 情感反应均应以该角色为准。该角色不知道的信息不可描写。
"""
        # ── 跨线程上下文（多线叙事） ──
        thread_section = ""
        if thread_context.strip():
            thread_section = f"""
### 其他线程状态（不可在本章直接展现，但可间接暗示）
{thread_context}
> 以上信息仅供写手把握全局节奏，不可直接告诉视角角色。
"""

        settlement_schema = """{
  "resource_changes": ["道具/资源变化，如「林尘的玉佩碎裂」"],
  "new_hooks": ["新埋下的伏笔，一句话描述"],
  "resolved_hooks": ["已回收的伏笔 ID 列表"],
  "relationship_changes": ["关系变化，如「林尘-慕雪：从-80变为-60，原因：慕雪第一次动摇」"],
  "info_revealed": [{"character_id": "角色ID", "info_key": "信息标识", "content": "角色得知了什么"}],
  "character_position_changes": [{"character_id": "角色ID", "location_id": "地点ID"}],
  "emotional_changes": [{"character_id": "角色ID", "emotion": "情绪", "intensity": 7, "trigger": "触发原因"}]
}"""

        prompt = f"""\
## 写作任务：第 {chapter_number} 章{f'《{chapter_title}》' if chapter_title else ''}

### 节拍序列（按顺序写完所有节拍）
{scene_summaries}
{pov_section}{thread_section}
### 主角
姓名：{protagonist.name}
外部目标：{protagonist.need.external}
内在渴望：{protagonist.need.internal}
本章情感旅程：{blueprint.emotional_journey.get('start', '??')} → {blueprint.emotional_journey.get('end', '??')}
性格锁定（绝对不做）：{'、'.join(protagonist.behavior_lock)}

### 核心冲突（必须贯穿全章）
{blueprint.core_conflict}

### 本章结尾钩子（最后必须实现）
{blueprint.chapter_end_hook}

### 节奏建议
{blueprint.pace_notes}

### 本章登场角色
{', '.join(blueprint.pre_write_checklist.active_characters)}

### 当前世界状态
{world_context}
{prior_ctx}
{f'''### 未闭合伏笔（需要在正文中自然推进或埋设）
{pending_hooks.strip()}
''' if pending_hooks and pending_hooks.strip() else ''}
{f'''### 近期因果链（确保本章事件与已有因果关系一致）
{causal_chain[-1200:].strip()}
''' if causal_chain and causal_chain.strip() else ''}
{f'''### 情感弧线（角色情感走向，请保持延续性）
{emotional_arcs[-600:].strip()}
''' if emotional_arcs and emotional_arcs.strip() else ''}

### 高风险连续性点（写时注意）
{blueprint.pre_write_checklist.risk_scan}

### 字数要求
目标 {target_words} 字（允许 ±10%，即 {int(target_words*0.9)}–{int(target_words*1.1)} 字）

---
请直接开始写正文，写完后输出：
{SETTLEMENT_SEPARATOR}
{settlement_schema}"""

        def _call() -> WriterOutput:
            # 记录知识库查询
            _track_kb_query("writer", "anti_ai_rules.md", "去AI味规范")
            if _KB_BEFORE_AFTER:
                _track_kb_query("writer", "before_after_examples.md", "修改前后对比")
            if _KB_WRITER_SKILLS:
                _track_kb_query("writer", "writer-skills.md", "写手技能库")
            if _KB_SHOW_DONT_TELL:
                _track_kb_query("writer", "show-dont-tell.md", "Show Don't Tell")

            resp = self.llm.complete([
                LLMMessage("system", system),
                LLMMessage("user", prompt),
            ])
            parts = resp.content.split(SETTLEMENT_SEPARATOR, 1)
            content = parts[0].strip()

            settlement = PostWriteSettlement()
            if len(parts) > 1:
                try:
                    raw = json.loads(parts[1].strip())
                    settlement = PostWriteSettlement(
                        resource_changes=raw.get("resource_changes", []),
                        new_hooks=raw.get("new_hooks", []),
                        resolved_hooks=raw.get("resolved_hooks", []),
                        relationship_changes=raw.get("relationship_changes", []),
                        info_revealed=raw.get("info_revealed", []),
                        character_position_changes=raw.get("character_position_changes", []),
                        emotional_changes=raw.get("emotional_changes", []),
                    )
                except Exception:
                    pass  # 结算表解析失败不崩溃，用默认空值

            return WriterOutput(content=content, settlement=settlement)

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 3. 审计员 Agent
# ─────────────────────────────────────────────────────────────────────────────

AuditSeverity = Literal["critical", "warning", "info"]


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


@dataclass
class ReviseResult:
    content: str
    change_log: list[str]


class ReviserAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def revise(
        self,
        original_content: str,
        issues: list[AuditIssue],
        mode: ReviseMode = "spot-fix",
    ) -> ReviseResult:
        critical = [i for i in issues if i.severity == "critical"]
        warnings  = [i for i in issues if i.severity == "warning"]

        if not critical and mode == "spot-fix":
            return ReviseResult(
                content=original_content,
                change_log=["无 critical 问题，跳过修订"],
            )

        issue_lines = []
        for i in (critical + warnings):
            line = f"- [{i.severity.upper()}] {i.dimension}：{i.description}"
            if i.location:
                line += f"\n  原文位置：「{i.location}」"
            if i.suggestion:
                line += f"\n  修复建议：{i.suggestion}"
            issue_lines.append(line)

        prompt = f"""\
## 修订任务
模式：{mode}
规则：{_MODE_INSTRUCTIONS[mode]}
硬约束：不得引入新情节，不得修改角色名，不得改变情节走向。

## 需修订的问题
{chr(10).join(issue_lines)}

## 原文
{original_content}

---
直接输出修订后的完整正文（不要任何前言），然后输出：
{CHANGELOG_SEPARATOR}
["改动说明1", "改动说明2", ...]"""

        def _call() -> ReviseResult:
            resp = self.llm.complete([
                LLMMessage(
                    "system",
                    f"你是精准的小说修订者，模式：{mode}。"
                    f"{_MODE_INSTRUCTIONS[mode]}"
                    "直接输出修订后正文，不要任何前言。",
                ),
                LLMMessage("user", prompt),
            ])
            parts = resp.content.split(CHANGELOG_SEPARATOR, 1)
            content = parts[0].strip()
            change_log: list[str] = []
            if len(parts) > 1:
                try:
                    change_log = json.loads(parts[1].strip())
                except Exception:
                    change_log = [parts[1].strip()[:200]]
            return ReviseResult(content=content, change_log=change_log)

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 5. 摘要 Agent（新增）
# 写完章节后自动生成章节摘要，注入 chapter_summaries.md
# ─────────────────────────────────────────────────────────────────────────────

class _SummarySchema(BaseModel):
    chapter_number: int
    title: str
    summary: str               # 200字以内的情节摘要
    key_events: list[str]      # 关键事件列表
    characters_appeared: list[str]
    state_changes: list[str]   # 世界状态变化（位置/关系/信息）
    hook_updates: list[str]    # 伏笔动态（新开/推进/回收）
    emotional_note: str        # 主角本章情感变化一句话


class SummaryAgent:
    """章节摘要生成器，写完章节后调用，产出注入 chapter_summaries.md 的内容"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def generate_summary(
        self,
        chapter_content: str,
        chapter_number: int,
        chapter_title: str,
        settlement: PostWriteSettlement,
    ) -> _SummarySchema:

        content_excerpt = chapter_content[:4000]
        if len(chapter_content) > 4000:
            content_excerpt += "\n...(截断)"

        prompt = f"""\
请为以下章节生成结构化摘要，供后续章节写作时作上下文参考。

## 章节正文（第 {chapter_number} 章《{chapter_title}》）
{content_excerpt}

## 写后结算表（已知的状态变化）
资源变化：{settlement.resource_changes}
新开伏笔：{settlement.new_hooks}
回收伏笔：{settlement.resolved_hooks}
关系变化：{settlement.relationship_changes}
信息揭示：{settlement.info_revealed}

## 输出要求（JSON）
{{
  "chapter_number": {chapter_number},
  "title": "{chapter_title}",
  "summary": "200字以内的情节摘要，说清楚发生了什么、谁做了什么决定",
  "key_events": ["关键事件1", "关键事件2"],
  "characters_appeared": ["出场角色名"],
  "state_changes": ["世界状态变化，如「林尘到达青峰山」「林尘得知灵根封印」"],
  "hook_updates": ["伏笔动态，如「新开：玉佩发热之谜」「推进：退婚之仇」"],
  "emotional_note": "主角本章情感轨迹一句话，如「从屈辱到坚定」"
}}

只输出 JSON。"""

        def _call() -> _SummarySchema:
            resp = self.llm.complete([
                LLMMessage("system", "你是叙事编辑，生成精准的章节摘要，只输出 JSON。"),
                LLMMessage("user", prompt),
            ])
            return parse_llm_json(resp.content, _SummarySchema, "generate_summary")

        return with_retry(_call)

    def format_for_truth_file(self, summary: _SummarySchema) -> str:
        """格式化为写入 chapter_summaries.md 的 Markdown"""
        lines = [
            f"\n## 第 {summary.chapter_number} 章《{summary.title}》\n",
            f"{summary.summary}\n\n",
            f"**出场角色**：{', '.join(summary.characters_appeared)}\n\n",
            "**关键事件**：\n" + "\n".join(f"- {e}" for e in summary.key_events) + "\n\n",
            "**状态变化**：\n" + "\n".join(f"- {c}" for c in summary.state_changes) + "\n\n",
            "**伏笔动态**：\n" + "\n".join(f"- {h}" for h in summary.hook_updates) + "\n\n",
            f"**情感**：{summary.emotional_note}\n",
            "---\n",
        ]
        return "".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 6. 巡查者 Agent（新增 — 快速扫描质量门）
# 吸收 OpenMOSS 的 P0/P1/P2 分级巡查机制
# ─────────────────────────────────────────────────────────────────────────────

PatrolSeverity = Literal["P0", "P1", "P2"]


@dataclass
class PatrolIssue:
    check_item: str
    severity: PatrolSeverity
    status: str           # "pass" | "fail"
    description: str
    risk: str = ""


@dataclass
class PatrolReport:
    chapter_number: int
    passed: bool
    issues: list[PatrolIssue]
    conclusion: str


class _PatrolIssueSchema(BaseModel):
    check_item: str
    severity: str
    status: str
    description: str = ""
    risk: str = ""


class _PatrolReportSchema(BaseModel):
    chapter_number: int
    passed: bool
    issues: list[_PatrolIssueSchema] = Field(default_factory=list)
    conclusion: str = ""


class PatrolAgent:
    """巡查者：在写手和审计之间做快速扫描，P0问题直接打回"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def quick_scan(
        self,
        chapter_content: str,
        chapter_number: int,
        blueprint: ArchitectBlueprint,
        settlement: PostWriteSettlement,
    ) -> PatrolReport:
        content_for_scan = chapter_content
        if len(chapter_content) > 4000:
            content_for_scan = chapter_content[:2000] + "\n...[省略]...\n" + chapter_content[-1500:]

        prompt = f"""\
## 巡查任务：第 {chapter_number} 章快速扫描

### P0 - 必须检查（有任何 fail 则打回）
1. 状态卡一致：正文中的时间/地点/角色是否与蓝图一致
   登场角色：{blueprint.pre_write_checklist.active_characters}
   地点：{blueprint.pre_write_checklist.required_locations}
2. 人物OOC：角色行为是否符合性格锁定

### P1 - 重点检查（>=2项 fail 则打回）
3. 伏笔管理：待回收伏笔是否有下落
   伏笔：{blueprint.pre_write_checklist.hooks_status}
4. 战力稳定：数值是否合理（无10倍+跳变）
5. 风格纯度：有无其他题材腔调混入

### P2 - 有时间再看
6. 节奏健康：是否流水账
7. 配角质量：是否工具人化
8. 设定冲突：是否与前文矛盾

### 正文（节选）
{content_for_scan}

### 写后结算表
资源变化：{settlement.resource_changes}
新开伏笔：{settlement.new_hooks}
回收伏笔：{settlement.resolved_hooks}

## 输出 JSON
{{
  "chapter_number": {chapter_number},
  "passed": true,
  "issues": [
    {{"check_item": "状态卡一致", "severity": "P0", "status": "pass", "description": "", "risk": "P0"}}
  ],
  "conclusion": "通过 / 需修正"
}}
规则：P0 fail 或 P1 fail>=2 → passed=false
只输出 JSON。"""

        def _call() -> PatrolReport:
            resp = self.llm.complete([
                LLMMessage("system", "你是质量守门人，快速扫描找关键问题，不制造假阳性。只输出 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _PatrolReportSchema, "quick_scan")
            issues = [
                PatrolIssue(
                    check_item=i.check_item,
                    severity=i.severity,
                    status=i.status,
                    description=i.description,
                    risk=i.risk,
                )
                for i in parsed.issues
            ]
            return PatrolReport(
                chapter_number=parsed.chapter_number,
                passed=parsed.passed,
                issues=issues,
                conclusion=parsed.conclusion,
            )

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 7. 世界观建筑师 Agent（新增 — 从一句话设定生成完整世界观）
# ─────────────────────────────────────────────────────────────────────────────

class _WorldBuilderSchema(BaseModel):
    title: str
    genre: str
    world_background: str = ""           # 世界观背景
    core_power_system: str = ""          # 核心力量体系
    factions: list[dict[str, str]] = Field(default_factory=list)  # 势力
    locations: list[dict[str, str]] = Field(default_factory=list)  # 地点
    characters: list[dict[str, str]] = Field(default_factory=list) # 角色
    world_rules: list[str] = Field(default_factory=list)           # 世界规则
    plot_hooks: list[str] = Field(default_factory=list)            # 情节钩子
    themes: list[str] = Field(default_factory=list)                # 主题
    market_positioning: str = ""         # 市场定位


class WorldBuilderAgent:
    """世界观建筑师：从一句话设定自动生成完整世界观"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def build_world(
        self,
        premise: str,
        genre: str = "玄幻",
        target_chapters: int = 90,
        style_preference: str = "",
    ) -> _WorldBuilderSchema:
        style_section = f"\n## 风格偏好\n{style_preference}" if style_preference else ""

        prompt = f"""你是资深网文世界观设计师。根据以下一句话设定，生成完整的世界观体系。

## 一句话设定
{premise}

## 题材
{genre}

## 目标章数
{target_chapters} 章
{style_section}

## 输出要求（JSON）
{{
  "title": "书名（吸引眼球，4-8字）",
  "genre": "{genre}",
  "world_background": "300字以内的世界观背景设定",
  "core_power_system": "核心力量体系描述（修炼等级/能力分类/进阶条件）",
  "factions": [
    {{"name": "势力名", "description": "100字描述", "power_level": "强/中/弱", "relationship": "与主角的关系"}}
  ],
  "locations": [
    {{"name": "地点名", "description": "50字描述", "faction": "所属势力", "dramatic_potential": "戏剧潜力"}}
  ],
  "characters": [
    {{
      "name": "角色名",
      "role": "protagonist/antagonist/impact/guardian/sidekick/love_interest/supporting",
      "external_goal": "外部目标",
      "internal_need": "内在渴望",
      "personality": "3个性格关键词",
      "obstacle": "主要障碍",
      "arc": "positive/negative/flat/corrupt",
      "behavior_lock": "绝对不做的事",
      "backstory": "50字背景"
    }}
  ],
  "world_rules": ["规则1", "规则2"],
  "plot_hooks": ["可展开的情节线索1", "情节线索2"],
  "themes": ["主题1", "主题2"],
  "market_positioning": "目标读者和市场定位分析（100字）"
}}

要求：
- 角色至少5个（主角/反派/冲击者/守护者/伙伴各1）
- 势力至少3个，互有矛盾
- 地点至少4个，覆盖故事主要场景
- 世界规则至少3条，确保逻辑自洽
- 力量体系必须有明确的等级划分和进阶条件

只输出 JSON。"""

        def _call() -> _WorldBuilderSchema:
            resp = self.llm.complete([
                LLMMessage("system", "你是资深网文世界观设计师，精通Dramatica叙事理论。只输出JSON。"),
                LLMMessage("user", prompt),
            ])
            return parse_llm_json(resp.content, _WorldBuilderSchema, "build_world")

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 8. 大纲规划 Agent（新增 — 生成三幕结构 + 章纲）
# ─────────────────────────────────────────────────────────────────────────────

class _ChapterOutlineItemSchema(BaseModel):
    chapter_number: int
    title: str
    summary: str
    emotional_arc: dict[str, str] = Field(default_factory=dict)
    mandatory_tasks: list[str] = Field(default_factory=list)
    dramatic_function: str = "event"  # setup/inciting/turning/midpoint/crisis/climax/reveal/decision/consequence/transition
    thread_id: str = "thread_main"
    pov_character_id: str = ""
    target_words: int = 2000


class _OutlinePlanSchema(BaseModel):
    title: str
    genre: str
    three_act_structure: dict[str, str] = Field(default_factory=dict)  # act1/act2/act3 描述
    act_boundaries: dict[str, list[int]] = Field(default_factory=dict)  # 每幕的章节范围
    main_conflict: str = ""
    theme: str = ""
    character_arcs: dict[str, str] = Field(default_factory=dict)
    chapters: list[_ChapterOutlineItemSchema] = Field(default_factory=list)
    tension_curve: list[int] = Field(default_factory=list)  # 每章张力值 1-10
    subplot_plans: list[dict[str, str]] = Field(default_factory=list)


class OutlinePlannerAgent:
    """大纲规划师：从世界观生成三幕结构大纲 + 逐章规划"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def plan_outline(
        self,
        world_context: str,
        characters_json: str,
        genre: str = "玄幻",
        target_chapters: int = 90,
        target_words_per_chapter: int = 2000,
    ) -> _OutlinePlanSchema:

        prompt = f"""你是精通Dramatica叙事理论的大纲规划师。根据世界观和角色信息，生成完整的小说大纲。

## 世界观
{world_context[:2000]}

## 角色信息
{characters_json[:2000]}

## 需求
- 题材：{genre}
- 目标总章数：{target_chapters} 章
- 每章字数：{target_words_per_chapter} 字

## 三幕结构要求
- 第一幕（建立）：约{int(target_chapters*0.25)}章，建立世界/角色/规则，激励事件打破平衡
- 第二幕（对抗）：约{int(target_chapters*0.50)}章，冲突升级/中点转折/危机最低点
- 第三幕（解决）：约{int(target_chapters*0.25)}章，高潮对决/揭示/结局

## 输出要求（JSON）
{{
  "title": "书名",
  "genre": "{genre}",
  "three_act_structure": {{
    "act1": "第一幕概述（50字）",
    "act2": "第二幕概述（50字）",
    "act3": "第三幕概述（50字）"
  }},
  "act_boundaries": {{
    "act1": [1, {int(target_chapters*0.25)}],
    "act2": [{int(target_chapters*0.25)+1}, {int(target_chapters*0.75)}],
    "act3": [{int(target_chapters*0.75)+1}, {target_chapters}]
  }},
  "main_conflict": "核心冲突一句话",
  "theme": "核心主题",
  "character_arcs": {{"角色名": "成长弧线描述"}},
  "chapters": [
    {{
      "chapter_number": 1,
      "title": "章节标题",
      "summary": "100字章节摘要",
      "emotional_arc": {{"start": "开始情绪", "end": "结束情绪"}},
      "mandatory_tasks": ["必须完成的任务"],
      "dramatic_function": "setup",
      "thread_id": "thread_main",
      "pov_character_id": "主角ID",
      "target_words": {target_words_per_chapter}
    }}
  ],
  "tension_curve": [张力值列表，每章1-10],
  "subplot_plans": [{{"name": "支线名", "thread_id": "支线ID", "description": "支线描述"}}]
}}

要求：
- 每章的dramatic_function必须从以下选择：setup/inciting/turning/midpoint/crisis/climax/reveal/decision/consequence/transition
- 张力曲线要有起伏，不能一直平或一直高
- 至少规划2条支线
- 章节标题要吸引人

只输出 JSON（前{min(target_chapters, 30)}章即可）。"""

        def _call() -> _OutlinePlanSchema:
            resp = self.llm.complete([
                LLMMessage("system", "你是精通Dramatica叙事理论的大纲规划师。只输出JSON。"),
                LLMMessage("user", prompt),
            ])
            return parse_llm_json(resp.content, _OutlinePlanSchema, "plan_outline")

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 9. 市场分析 Agent（新增 — 分析目标读者偏好，调整写作风格）
# ─────────────────────────────────────────────────────────────────────────────

class _MarketAnalysisSchema(BaseModel):
    target_audience: str = ""         # 目标读者画像
    reader_preferences: list[str] = Field(default_factory=list)  # 读者偏好
    genre_trends: list[str] = Field(default_factory=list)         # 题材趋势
    recommended_style: str = ""       # 推荐文风
    recommended_hooks: list[str] = Field(default_factory=list)    # 推荐的开篇钩子
    competitive_analysis: str = ""    # 竞品分析
    style_guide: str = ""             # 写作风格指南（可直接注入prompt）


class MarketAnalyzerAgent:
    """市场分析师：分析目标读者偏好，输出风格指南"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm
        # V4：预加载番茄市场数据
        self._tomato_data = ""
        tomato_files = [
            "fanqie-data/番茄小说及男性向网文市场数据报告_完整版.md",
            "fanqie-data/番茄小说男性向读者内容偏好研究报告_完整版.md",
            "fanqie-data/番茄读者画像深度分析报告_v1.0.md",
        ]
        for f in tomato_files:
            content = _load_kb(f)
            if content:
                self._tomato_data += f"\n### {f.split('/')[-1]}\n{content[:3000]}\n"

    def analyze(
        self,
        genre: str,
        premise: str,
        target_platform: str = "番茄小说",
    ) -> _MarketAnalysisSchema:

        # V4：注入番茄市场数据
        tomato_section = ""
        if self._tomato_data:
            tomato_section = f"""
## 番茄小说真实市场数据（V4引入，分析时必须参考）
{self._tomato_data[:6000]}
> 以上数据来自番茄小说平台的真实用户画像和市场调研，分析时请优先引用这些数据，
> 而非凭空想象。读者画像、偏好趋势应以上述数据为准。
"""

        prompt = f"""你是网文市场分析师，精通{target_platform}平台的读者偏好和题材趋势。

## 小说信息
- 题材：{genre}
- 设定：{premise}
- 目标平台：{target_platform}
{tomato_section}
## 输出要求（JSON）
{{
  "target_audience": "目标读者画像（年龄/性别/阅读习惯）",
  "reader_preferences": ["该题材读者最看重的3-5个元素"],
  "genre_trends": ["当前该题材的3-5个流行趋势"],
  "recommended_style": "推荐的文风方向（100字）",
  "recommended_hooks": ["推荐的3种开篇钩子类型"],
  "competitive_analysis": "同类热门作品的共同特点（100字）",
  "style_guide": "可直接注入写手prompt的风格指南（200字，具体可操作）"
}}

只输出 JSON。"""

        def _call() -> _MarketAnalysisSchema:
            resp = self.llm.complete([
                LLMMessage("system", "你是网文市场分析师，精通各大平台读者数据。只输出JSON。"),
                LLMMessage("user", prompt),
            ])
            return parse_llm_json(resp.content, _MarketAnalysisSchema, "analyze")

        return with_retry(_call)
