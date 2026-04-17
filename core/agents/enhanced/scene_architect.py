"""SceneArchitect — 场景空间感审核"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ...llm import LLMProvider, LLMMessage, parse_llm_json, with_retry

from ..kb import KB_SCENE_ARCHITECT, track_kb_query

_KB_SCENE_ARCHITECT = KB_SCENE_ARCHITECT

@dataclass
class SceneDimension:
    """场景审核维度"""
    dimension: str
    score: int
    issues: list[str]
    suggestions: list[str]




@dataclass
class SceneAuditResult:
    """场景审核结果"""
    dimensions: list[SceneDimension]
    overall_score: int
    passed: bool
    summary: str




class _SceneDimensionSchema(BaseModel):
    dimension: str
    score: int = 80
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)




class _SceneAuditSchema(BaseModel):
    dimensions: list[_SceneDimensionSchema] = Field(default_factory=list)
    overall_score: int = 80
    passed: bool = True
    summary: str = ""




class SceneArchitect:
    """场景建筑师：审核场景的空间感/五感/氛围/转场质量"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def audit_scene(
        self,
        chapter_content: str,
        chapter_number: int,
    ) -> SceneAuditResult:
        kb_section = ""
        if _KB_SCENE_ARCHITECT:
            kb_section = f"\n## 场景构建方法论\n{_KB_SCENE_ARCHITECT[:3000]}\n"

        content = chapter_content[:5000]
        if len(chapter_content) > 5000:
            content += "\n...(截断)"

        prompt = f"""你是场景建筑师，请审核第 {chapter_number} 章的场景质量。

## 章节正文
{content}
{kb_section}
## 四维审核要求

### 1. 空间感（权重 25%）
- 三维空间描述是否清晰
- 角色定位是否明确
- 空间转换是否自然

### 2. 感官细节（权重 30%）
- 五感运用是否充分（至少3种）
- 感官描写是否有层次
- 感官是否服务于情绪
- 是否有留白

### 3. 氛围营造（权重 25%）
- 氛围是否与情绪一致
- 意象运用是否恰当
- 氛围变化是否自然

### 4. 转场质量（权重 20%）
- 场景切换是否自然
- 时空转换是否清晰
- 转场手法是否恰当

## 输出格式（JSON）
{{"dimensions": [
  {{"dimension": "空间感", "score": 85, "issues": ["问题1"], "suggestions": ["建议1"]}},
  {{"dimension": "感官细节", "score": 90, "issues": [], "suggestions": []}},
  {{"dimension": "氛围营造", "score": 88, "issues": [], "suggestions": []}},
  {{"dimension": "转场质量", "score": 82, "issues": [], "suggestions": []}}
], "overall_score": 87, "passed": true, "summary": "整体评价"}}

加权总分 = 空间感×0.25 + 感官细节×0.30 + 氛围营造×0.25 + 转场质量×0.20
overall_score >= 85 为通过
只输出 JSON。"""

        def _call() -> SceneAuditResult:
            resp = self.llm.complete([
                LLMMessage("system", "你是场景建筑师，专注于场景质量审核。只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _SceneAuditSchema, "audit_scene")
            dimensions = [
                SceneDimension(
                    dimension=d.dimension,
                    score=d.score,
                    issues=d.issues,
                    suggestions=d.suggestions,
                )
                for d in parsed.dimensions
            ]
            return SceneAuditResult(
                dimensions=dimensions,
                overall_score=parsed.overall_score,
                passed=parsed.overall_score >= 85,
                summary=parsed.summary,
            )

        return with_retry(_call)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. PsychologicalPortrayalExpert — 心理真实性/层次/留白/行为一致性审核
# ═══════════════════════════════════════════════════════════════════════════════


