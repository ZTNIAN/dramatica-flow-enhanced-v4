"""WriterAgent — 写手 Agent：创作章节内容"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, field_validator, Field

from ..llm import LLMProvider, LLMMessage, parse_llm_json, with_retry
from ..types.narrative import Character
from ..narrative import ChapterOutlineSchema

from .kb import KB_ANTI_AI, KB_BEFORE_AFTER, KB_WRITING_TECHNIQUES, KB_COMMON_MISTAKES, KB_FIVE_SENSES, KB_SHOW_DONT_TELL, KB_WRITER_SKILLS, KB_REVIEWER_CHECKLIST, KB_REVIEW_CRITERIA_95, KB_REDLINES, track_kb_query

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


