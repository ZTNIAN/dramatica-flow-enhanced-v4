"""
Dramatica-Flow Agents — 模块化导出（V5 优化版）
每个 Agent 独立文件，__init__.py 只做 re-export。
"""
from __future__ import annotations

# ── 核心 Agent ────────────────────────────────────────────────────────────────
from .architect import (
    ArchitectAgent, ArchitectBlueprint, PreWriteChecklist,
    _ChecklistSchema, _BlueprintSchema,
)
from .writer import (
    WriterAgent, WriterOutput, PostWriteSettlement,
)
from .auditor import (
    AuditorAgent, AuditReport, AuditIssue,
    _AuditIssueSchema, _AuditReportSchema,
)
from .reviser import (
    ReviserAgent, ReviseResult,
)
from .summary import (
    SummaryAgent, _SummarySchema,
)
from .patrol import (
    PatrolAgent, PatrolReport, PatrolIssue,
    _PatrolIssueSchema, _PatrolReportSchema,
)
from .worldbuilder import (
    WorldBuilderAgent, _WorldBuilderSchema,
)
from .outline_planner import (
    OutlinePlannerAgent, _ChapterOutlineItemSchema, _OutlinePlanSchema,
)
from .market_analyzer import (
    MarketAnalyzerAgent, _MarketAnalysisSchema,
)

# ── V4: 增强 Agent ───────────────────────────────────────────────────────────
from .enhanced import (
    CharacterGrowthExpert, CharacterGrowthResult, CharacterGrowthProfile,
    DialogueExpert, DialogueReviewResult, LanguageFingerprint,
    EmotionCurveDesigner, EmotionCurveResult, ChapterEmotion,
    FeedbackExpert, FeedbackResult, FeedbackItem,
    StyleConsistencyChecker, StyleConsistencyResult, StyleDimension,
    SceneArchitect, SceneAuditResult, SceneDimension,
    PsychologicalPortrayalExpert, PsychologicalAuditResult, PsychologicalDimension,
    MiroFishReader, MiroFishResult, ReaderSegment,
    get_hook_designer_prompt_injection,
    get_opening_ending_prompt_injection,
)

# ── V5: 知识库 ───────────────────────────────────────────────────────────────
from .kb import (
    KB_ANTI_AI, KB_BEFORE_AFTER, KB_WRITING_TECHNIQUES,
    KB_COMMON_MISTAKES, KB_FIVE_SENSES, KB_SHOW_DONT_TELL,
    KB_WRITER_SKILLS, KB_REVIEWER_CHECKLIST, KB_REVIEW_CRITERIA_95, KB_REDLINES,
    track_kb_query, get_kb_queries,
)

# 向后兼容别名
_KB_ANTI_AI = KB_ANTI_AI
_KB_BEFORE_AFTER = KB_BEFORE_AFTER
_KB_WRITING_TECHNIQUES = KB_WRITING_TECHNIQUES
_KB_COMMON_MISTAKES = KB_COMMON_MISTAKES
_KB_FIVE_SENSES = KB_FIVE_SENSES
_KB_SHOW_DONT_TELL = KB_SHOW_DONT_TELL
_KB_WRITER_SKILLS = KB_WRITER_SKILLS
_KB_REVIEWER_CHECKLIST = KB_REVIEWER_CHECKLIST
_KB_REVIEW_CRITERIA_95 = KB_REVIEW_CRITERIA_95
_KB_REDLINES = KB_REDLINES
_track_kb_query = track_kb_query
