"""DialogueExpert — 对话质量审查"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ...llm import LLMProvider, LLMMessage, parse_llm_json, with_retry

from ..kb import KB_DIALOGUE, track_kb_query

_KB_DIALOGUE = KB_DIALOGUE

@dataclass
class LanguageFingerprint:
    """角色语言指纹（六维度）"""
    character_name: str
    vocabulary: str = ""          # 词汇偏好
    sentence_structure: str = ""  # 句式结构
    interjections: str = ""       # 语气词
    speaking_speed: str = ""      # 说话速度
    expression_habit: str = ""    # 表达习惯
    knowledge_scope: str = ""     # 知识范围




@dataclass
class DialogueReviewResult:
    """对话审查结果"""
    language_fingerprints: list[LanguageFingerprint]
    issues: list[dict[str, str]]
    rhythm_analysis: str
    era_check: str
    overall_score: int
    suggestions: list[str]




class _LanguageFingerprintSchema(BaseModel):
    character_name: str
    vocabulary: str = ""
    sentence_structure: str = ""
    interjections: str = ""
    speaking_speed: str = ""
    expression_habit: str = ""
    knowledge_scope: str = ""




class _DialogueReviewSchema(BaseModel):
    language_fingerprints: list[_LanguageFingerprintSchema] = Field(default_factory=list)
    issues: list[dict[str, str]] = Field(default_factory=list)
    rhythm_analysis: str = ""
    era_check: str = ""
    overall_score: int = 80
    suggestions: list[str] = Field(default_factory=list)




class DialogueExpert:
    """对话专家：审核对话质量 + 设计角色语言指纹"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def review_dialogue(
        self,
        chapter_content: str,
        chapter_number: int,
        characters: list[str],
        era: str = "古代",
    ) -> DialogueReviewResult:
        kb_section = ""
        if _KB_DIALOGUE:
            kb_section = f"\n## 对话专家方法论\n{_KB_DIALOGUE[:3000]}\n"

        # 截断正文
        content = chapter_content[:5000]
        if len(chapter_content) > 5000:
            content += "\n...(截断)"

        prompt = f"""你是对话质量专家，请审核第 {chapter_number} 章的对话质量。

## 章节正文
{content}

## 登场角色
{', '.join(characters)}

## 时代背景
{era}
{kb_section}
## 审核要求

### 语言特征六维度（为每个有对话的角色设计语言指纹）
1. 词汇偏好
2. 句式结构
3. 语气词
4. 说话速度
5. 表达习惯
6. 知识范围

### 潜台词分析
- 每段重要对话是否有言外之意
- 是否有说教/直白的问题

### 对话节奏
- 密度和长度是否合理
- 是否有张弛交替

### 时代语言审核
- 是否有不符合时代背景的用语

## 输出格式（JSON）
{{"language_fingerprints": [
  {{"character_name": "角色名", "vocabulary": "词汇偏好描述", "sentence_structure": "句式结构描述",
    "interjections": "常用语气词", "speaking_speed": "说话速度", "expression_habit": "表达习惯", "knowledge_scope": "知识范围"}}
], "issues": [
  {{"character": "角色名", "type": "问题类型", "description": "具体问题", "suggestion": "修改建议"}}
], "rhythm_analysis": "对话节奏分析（100字）", "era_check": "时代语言审核结果（100字）",
"overall_score": 85, "suggestions": ["建议1", "建议2"]}}

只输出 JSON。"""

        def _call() -> DialogueReviewResult:
            resp = self.llm.complete([
                LLMMessage("system", "你是对话质量专家，擅长分析角色语言特征。只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _DialogueReviewSchema, "review_dialogue")
            fingerprints = [
                LanguageFingerprint(
                    character_name=fp.character_name,
                    vocabulary=fp.vocabulary,
                    sentence_structure=fp.sentence_structure,
                    interjections=fp.interjections,
                    speaking_speed=fp.speaking_speed,
                    expression_habit=fp.expression_habit,
                    knowledge_scope=fp.knowledge_scope,
                )
                for fp in parsed.language_fingerprints
            ]
            return DialogueReviewResult(
                language_fingerprints=fingerprints,
                issues=parsed.issues,
                rhythm_analysis=parsed.rhythm_analysis,
                era_check=parsed.era_check,
                overall_score=parsed.overall_score,
                suggestions=parsed.suggestions,
            )

        return with_retry(_call)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. EmotionCurveDesigner — 整书情绪曲线 + 每章情绪类型规划
# ═══════════════════════════════════════════════════════════════════════════════


