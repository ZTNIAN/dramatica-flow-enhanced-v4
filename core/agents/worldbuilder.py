"""WorldBuilderAgent — 世界观构建 Agent"""
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

