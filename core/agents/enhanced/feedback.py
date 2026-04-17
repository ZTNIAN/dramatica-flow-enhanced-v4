"""FeedbackExpert — 读者反馈分类"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ...llm import LLMProvider, LLMMessage, parse_llm_json, with_retry

from ..kb import track_kb_query

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

