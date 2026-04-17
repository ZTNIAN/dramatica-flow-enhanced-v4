"""MiroFishReader — 模拟读者测试"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ...llm import LLMProvider, LLMMessage, parse_llm_json, with_retry

from ..kb import track_kb_query

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

