"""EmotionCurveDesigner — 情绪曲线设计"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ...llm import LLMProvider, LLMMessage, parse_llm_json, with_retry

from ..kb import KB_EMOTION_CURVE, track_kb_query

_KB_EMOTION_CURVE = KB_EMOTION_CURVE

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


