"""PatrolAgent — 巡查者 Agent：快速质量扫描"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, field_validator, Field

from ..llm import LLMProvider, LLMMessage, parse_llm_json, with_retry
from ..types.narrative import Character
from ..narrative import ChapterOutlineSchema

from .kb import KB_REVIEW_CRITERIA_95, KB_REDLINES, track_kb_query

_KB_REVIEW_CRITERIA_95 = KB_REVIEW_CRITERIA_95
_KB_REDLINES = KB_REDLINES

@dataclass
class PatrolIssue:
    check_item: str
    severity: PatrolSeverity
    status: str           # "pass" | "fail"
    description: str
    risk: str = ""




@dataclass
class PatrolReport:
    chapter_number: int
    passed: bool
    issues: list[PatrolIssue]
    conclusion: str




class _PatrolIssueSchema(BaseModel):
    check_item: str
    severity: str
    status: str
    description: str = ""
    risk: str = ""




class _PatrolReportSchema(BaseModel):
    chapter_number: int
    passed: bool
    issues: list[_PatrolIssueSchema] = Field(default_factory=list)
    conclusion: str = ""




class PatrolAgent:
    """巡查者：在写手和审计之间做快速扫描，P0问题直接打回"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def quick_scan(
        self,
        chapter_content: str,
        chapter_number: int,
        blueprint: ArchitectBlueprint,
        settlement: PostWriteSettlement,
    ) -> PatrolReport:
        content_for_scan = chapter_content
        if len(chapter_content) > 4000:
            content_for_scan = chapter_content[:2000] + "\n...[省略]...\n" + chapter_content[-1500:]

        prompt = f"""\
## 巡查任务：第 {chapter_number} 章快速扫描

### P0 - 必须检查（有任何 fail 则打回）
1. 状态卡一致：正文中的时间/地点/角色是否与蓝图一致
   登场角色：{blueprint.pre_write_checklist.active_characters}
   地点：{blueprint.pre_write_checklist.required_locations}
2. 人物OOC：角色行为是否符合性格锁定

### P1 - 重点检查（>=2项 fail 则打回）
3. 伏笔管理：待回收伏笔是否有下落
   伏笔：{blueprint.pre_write_checklist.hooks_status}
4. 战力稳定：数值是否合理（无10倍+跳变）
5. 风格纯度：有无其他题材腔调混入

### P2 - 有时间再看
6. 节奏健康：是否流水账
7. 配角质量：是否工具人化
8. 设定冲突：是否与前文矛盾

### 正文（节选）
{content_for_scan}

### 写后结算表
资源变化：{settlement.resource_changes}
新开伏笔：{settlement.new_hooks}
回收伏笔：{settlement.resolved_hooks}

## 输出 JSON
{{
  "chapter_number": {chapter_number},
  "passed": true,
  "issues": [
    {{"check_item": "状态卡一致", "severity": "P0", "status": "pass", "description": "", "risk": "P0"}}
  ],
  "conclusion": "通过 / 需修正"
}}
规则：P0 fail 或 P1 fail>=2 → passed=false
只输出 JSON。"""

        def _call() -> PatrolReport:
            resp = self.llm.complete([
                LLMMessage("system", "你是质量守门人，快速扫描找关键问题，不制造假阳性。只输出 JSON。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _PatrolReportSchema, "quick_scan")
            issues = [
                PatrolIssue(
                    check_item=i.check_item,
                    severity=i.severity,
                    status=i.status,
                    description=i.description,
                    risk=i.risk,
                )
                for i in parsed.issues
            ]
            return PatrolReport(
                chapter_number=parsed.chapter_number,
                passed=parsed.passed,
                issues=issues,
                conclusion=parsed.conclusion,
            )

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 7. 世界观建筑师 Agent（新增 — 从一句话设定生成完整世界观）
# ─────────────────────────────────────────────────────────────────────────────

