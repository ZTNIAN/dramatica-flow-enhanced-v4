"""SummaryAgent — 摘要 Agent：生成章节摘要"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, field_validator, Field

from ..llm import LLMProvider, LLMMessage, parse_llm_json, with_retry
from ..types.narrative import Character
from ..narrative import ChapterOutlineSchema

from .kb import track_kb_query, get_kb_queries

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


