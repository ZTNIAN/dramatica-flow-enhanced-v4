"""MarketAnalyzerAgent — 市场分析 Agent"""
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

class _MarketAnalysisSchema(BaseModel):
    target_audience: str = ""         # 目标读者画像
    reader_preferences: list[str] = Field(default_factory=list)  # 读者偏好
    genre_trends: list[str] = Field(default_factory=list)         # 题材趋势
    recommended_style: str = ""       # 推荐文风
    recommended_hooks: list[str] = Field(default_factory=list)    # 推荐的开篇钩子
    competitive_analysis: str = ""    # 竞品分析
    style_guide: str = ""             # 写作风格指南（可直接注入prompt）




class MarketAnalyzerAgent:
    """市场分析师：分析目标读者偏好，输出风格指南"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm
        # V4：预加载番茄市场数据
        self._tomato_data = ""
        tomato_files = [
            "fanqie-data/番茄小说及男性向网文市场数据报告_完整版.md",
            "fanqie-data/番茄小说男性向读者内容偏好研究报告_完整版.md",
            "fanqie-data/番茄读者画像深度分析报告_v1.0.md",
        ]
        for f in tomato_files:
            content = _load_kb(f)
            if content:
                self._tomato_data += f"\n### {f.split('/')[-1]}\n{content[:3000]}\n"

    def analyze(
        self,
        genre: str,
        premise: str,
        target_platform: str = "番茄小说",
    ) -> _MarketAnalysisSchema:

        # V4：注入番茄市场数据
        tomato_section = ""
        if self._tomato_data:
            tomato_section = f"""
## 番茄小说真实市场数据（V4引入，分析时必须参考）
{self._tomato_data[:6000]}
> 以上数据来自番茄小说平台的真实用户画像和市场调研，分析时请优先引用这些数据，
> 而非凭空想象。读者画像、偏好趋势应以上述数据为准。
"""

        prompt = f"""你是网文市场分析师，精通{target_platform}平台的读者偏好和题材趋势。

## 小说信息
- 题材：{genre}
- 设定：{premise}
- 目标平台：{target_platform}
{tomato_section}
## 输出要求（JSON）
{{
  "target_audience": "目标读者画像（年龄/性别/阅读习惯）",
  "reader_preferences": ["该题材读者最看重的3-5个元素"],
  "genre_trends": ["当前该题材的3-5个流行趋势"],
  "recommended_style": "推荐的文风方向（100字）",
  "recommended_hooks": ["推荐的3种开篇钩子类型"],
  "competitive_analysis": "同类热门作品的共同特点（100字）",
  "style_guide": "可直接注入写手prompt的风格指南（200字，具体可操作）"
}}

只输出 JSON。"""

        def _call() -> _MarketAnalysisSchema:
            resp = self.llm.complete([
                LLMMessage("system", "你是网文市场分析师，精通各大平台读者数据。只输出JSON。"),
                LLMMessage("user", prompt),
            ])
            return parse_llm_json(resp.content, _MarketAnalysisSchema, "analyze")

        return with_retry(_call)

