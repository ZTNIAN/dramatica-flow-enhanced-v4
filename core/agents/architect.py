"""ArchitectAgent — 建筑师 Agent：规划章节蓝图"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, field_validator, Field

from ..llm import LLMProvider, LLMMessage, parse_llm_json, with_retry
from ..types.narrative import Character
from ..narrative import ChapterOutlineSchema

from .kb import KB_ANTI_AI, KB_BEFORE_AFTER, KB_WRITING_TECHNIQUES, KB_REDLINES, track_kb_query

_KB_ANTI_AI = KB_ANTI_AI
_KB_BEFORE_AFTER = KB_BEFORE_AFTER
_KB_WRITING_TECHNIQUES = KB_WRITING_TECHNIQUES
_KB_REDLINES = KB_REDLINES

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


