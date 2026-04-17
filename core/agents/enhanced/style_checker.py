"""StyleConsistencyChecker — 五维一致性检查"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ...llm import LLMProvider, LLMMessage, parse_llm_json, with_retry

from ..kb import KB_STYLE_CONSISTENCY, track_kb_query

_KB_STYLE_CONSISTENCY = KB_STYLE_CONSISTENCY

@dataclass
class StyleDimension:
    """单个风格维度检查结果"""
    dimension: str
    score: int              # 0-100
    deviation: str          # 偏差程度：轻微/中度/严重
    details: str            # 具体表现
    suggestion: str = ""    # 修改建议




@dataclass
class StyleConsistencyResult:
    """风格一致性检查结果"""
    dimensions: list[StyleDimension]
    overall_score: int
    passed: bool
    summary: str




class _StyleDimensionSchema(BaseModel):
    dimension: str
    score: int = 80
    deviation: str = "无"
    details: str = ""
    suggestion: str = ""




class _StyleConsistencySchema(BaseModel):
    dimensions: list[_StyleDimensionSchema] = Field(default_factory=list)
    overall_score: int = 80
    passed: bool = True
    summary: str = ""




class StyleConsistencyChecker:
    """风格一致性检查器：跨章节检查五维一致性"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def check_consistency(
        self,
        chapters: list[dict[str, str]],  # [{"number": 1, "content": "..."}]
        sample_count: int = 5,
    ) -> StyleConsistencyResult:
        kb_section = ""
        if _KB_STYLE_CONSISTENCY:
            kb_section = f"\n## 风格一致性检查方法论\n{_KB_STYLE_CONSISTENCY[:2000]}\n"

        # 随机采样章节
        import random
        if len(chapters) > sample_count:
            sampled = random.sample(chapters, sample_count)
        else:
            sampled = chapters

        chapters_text = "\n\n".join(
            f"### 第 {ch.get('number', '?')} 章（节选）\n{ch.get('content', '')[:1000]}"
            for ch in sampled
        )

        prompt = f"""你是风格一致性检查专家，请跨章节检查以下五维一致性。

## 采样章节
{chapters_text}
{kb_section}
## 五维检查要求
1. 文笔风格一致性（语言风格/描写密度/修辞使用/句式偏好）
2. 人物语气一致性（词汇习惯/句式/语气/口头禅）
3. 叙事节奏一致性
4. 时代背景一致性
5. 情感基调一致性

## 偏差等级
- 轻微：不影响阅读
- 中度：影响体验，建议修改
- 严重：严重影响体验，必须修改

## 输出格式（JSON）
{{"dimensions": [
  {{"dimension": "文笔风格", "score": 90, "deviation": "轻微", "details": "具体表现", "suggestion": "建议"}}
], "overall_score": 88, "passed": true, "summary": "整体评价（50字）"}}

评分标准：overall_score >= 85 为通过
只输出 JSON。"""

        def _call() -> StyleConsistencyResult:
            resp = self.llm.complete([
                LLMMessage("system", "你是风格一致性检查专家。只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _StyleConsistencySchema, "check_consistency")
            dimensions = [
                StyleDimension(
                    dimension=d.dimension,
                    score=d.score,
                    deviation=d.deviation,
                    details=d.details,
                    suggestion=d.suggestion,
                )
                for d in parsed.dimensions
            ]
            return StyleConsistencyResult(
                dimensions=dimensions,
                overall_score=parsed.overall_score,
                passed=parsed.overall_score >= 85,
                summary=parsed.summary,
            )

        return with_retry(_call)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. SceneArchitect — 场景空间感/五感层次/氛围/转场质量审核
# ═══════════════════════════════════════════════════════════════════════════════


