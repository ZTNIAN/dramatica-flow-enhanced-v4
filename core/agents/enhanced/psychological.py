"""PsychologicalPortrayalExpert — 心理真实性审核"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ...llm import LLMProvider, LLMMessage, parse_llm_json, with_retry

from ..kb import KB_PSYCHOLOGICAL, track_kb_query

_KB_PSYCHOLOGICAL = KB_PSYCHOLOGICAL

@dataclass
class PsychologicalDimension:
    """心理审核维度"""
    dimension: str
    score: int
    issues: list[str]
    suggestions: list[str]




@dataclass
class PsychologicalAuditResult:
    """心理审核结果"""
    dimensions: list[PsychologicalDimension]
    overall_score: int
    passed: bool
    summary: str




class _PsychDimensionSchema(BaseModel):
    dimension: str
    score: int = 80
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)




class _PsychAuditSchema(BaseModel):
    dimensions: list[_PsychDimensionSchema] = Field(default_factory=list)
    overall_score: int = 80
    passed: bool = True
    summary: str = ""




class PsychologicalPortrayalExpert:
    """心理刻画专家：审核角色心理的真实性和层次感"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def audit_psychology(
        self,
        chapter_content: str,
        chapter_number: int,
        characters: list[str],
    ) -> PsychologicalAuditResult:
        kb_section = ""
        if _KB_PSYCHOLOGICAL:
            kb_section = f"\n## 心理刻画方法论\n{_KB_PSYCHOLOGICAL[:3000]}\n"

        content = chapter_content[:5000]
        if len(chapter_content) > 5000:
            content += "\n...(截断)"

        prompt = f"""你是心理刻画专家，请审核第 {chapter_number} 章角色心理描写质量。

## 章节正文
{content}

## 登场角色
{', '.join(characters)}
{kb_section}
## 四维审核要求

### 1. 心理真实性（权重 30%）
- 性格一致性
- 情境合理性
- 人性普遍性
- 是否脸谱化

### 2. 心理层次（权重 25%）
- 情绪层次（表面 vs 真实）
- 意识层次
- 心理防御
- 认知失调

### 3. 心理留白（权重 25%）
- 是否给读者留了思考空间
- 暗示技巧运用
- 反差艺术
- 沉默的力量

### 4. 心理与行为一致性（权重 20%）
- 行为是否有心理动机
- 情感驱动是否合理
- 认知驱动是否合理

## 输出格式（JSON）
{{"dimensions": [
  {{"dimension": "心理真实性", "score": 88, "issues": ["问题1"], "suggestions": ["建议1"]}},
  {{"dimension": "心理层次", "score": 85, "issues": [], "suggestions": []}},
  {{"dimension": "心理留白", "score": 90, "issues": [], "suggestions": []}},
  {{"dimension": "心理与行为一致性", "score": 87, "issues": [], "suggestions": []}}
], "overall_score": 88, "passed": true, "summary": "整体评价"}}

overall_score >= 85 为通过
只输出 JSON。"""

        def _call() -> PsychologicalAuditResult:
            resp = self.llm.complete([
                LLMMessage("system", "你是心理刻画专家，专注于角色心理质量审核。只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _PsychAuditSchema, "audit_psychology")
            dimensions = [
                PsychologicalDimension(
                    dimension=d.dimension,
                    score=d.score,
                    issues=d.issues,
                    suggestions=d.suggestions,
                )
                for d in parsed.dimensions
            ]
            return PsychologicalAuditResult(
                dimensions=dimensions,
                overall_score=parsed.overall_score,
                passed=parsed.overall_score >= 85,
                summary=parsed.summary,
            )

        return with_retry(_call)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. MiroFishReader — 模拟1000名读者测试 + 收集反馈
# ═══════════════════════════════════════════════════════════════════════════════


