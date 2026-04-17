"""CharacterGrowthExpert — 角色成长弧线规划"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ...llm import LLMProvider, LLMMessage, parse_llm_json, with_retry

from ..kb import KB_CHAR_GROWTH, track_kb_query

_KB_CHAR_GROWTH = KB_CHAR_GROWTH

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


