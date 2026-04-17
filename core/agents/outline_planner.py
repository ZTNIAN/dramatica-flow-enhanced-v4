"""OutlinePlannerAgent — 大纲规划 Agent"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, field_validator, Field

from ..llm import LLMProvider, LLMMessage, parse_llm_json, with_retry
from ..types.narrative import Character
from ..narrative import ChapterOutlineSchema

from .kb import track_kb_query

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

