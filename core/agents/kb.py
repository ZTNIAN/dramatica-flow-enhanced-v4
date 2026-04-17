"""
公共知识库模块（V5 优化）
消除 __init__.py 和 enhanced_agents.py 中的 _KB_DIR / _load_kb 重复。
所有 Agent 从这里导入 KB 内容和追踪函数。
"""
from __future__ import annotations

from pathlib import Path

_KB_DIR = Path(__file__).parent.parent / "knowledge_base"


def _load_kb(name: str) -> str:
    """从 knowledge_base 目录加载文件内容，不存在则返回空串"""
    p = _KB_DIR / name
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# 知识库预加载 — 原有 Agent（建筑师/写手/审计员）
# ═══════════════════════════════════════════════════════════════════════════════

KB_ANTI_AI = _load_kb("anti_ai_rules.md")
KB_BEFORE_AFTER = _load_kb("before_after_examples.md")
KB_WRITING_TECHNIQUES = _load_kb("writing_techniques.md")
KB_COMMON_MISTAKES = _load_kb("rules/common-mistakes.md")
KB_FIVE_SENSES = _load_kb("references/writing-techniques/five-senses-description.md")
KB_SHOW_DONT_TELL = _load_kb("references/writing-techniques/show-dont-tell.md")
KB_WRITER_SKILLS = _load_kb("agent-specific/writer-skills.md")
KB_REVIEWER_CHECKLIST = _load_kb("agent-specific/reviewer-checklist.md")
KB_REVIEW_CRITERIA_95 = _load_kb("rules/review-criteria-95.md")
KB_REDLINES = _load_kb("rules/redlines.md")

# ═══════════════════════════════════════════════════════════════════════════════
# 知识库预加载 — V4 增强 Agent
# ═══════════════════════════════════════════════════════════════════════════════

KB_HOOK_DESIGNER = _load_kb("agent-specific/hook-designer-guide.md")
KB_OPENING_ENDING = _load_kb("agent-specific/opening-ending-guide.md")
KB_EMOTION_CURVE = _load_kb("agent-specific/emotion-curve-guide.md")
KB_DIALOGUE = _load_kb("agent-specific/dialogue-expert-guide.md")
KB_CHAR_GROWTH = _load_kb("agent-specific/character-growth-guide.md")
KB_STYLE_CONSISTENCY = _load_kb("agent-specific/style-consistency-guide.md")
KB_SCENE_ARCHITECT = _load_kb("agent-specific/scene-architect-guide.md")
KB_PSYCHOLOGICAL = _load_kb("agent-specific/psychological-portrayal-guide.md")

# ═══════════════════════════════════════════════════════════════════════════════
# 知识库查询追踪
# ═══════════════════════════════════════════════════════════════════════════════

_KB_QUERIES: list[tuple[str, str, str]] = []  # (agent_role, file_name, context)


def track_kb_query(agent_role: str, file_name: str, context: str = ""):
    """记录一次知识库查询（供 KBIncentiveTracker 使用）"""
    _KB_QUERIES.append((agent_role, file_name, context))


def get_kb_queries() -> list[tuple[str, str, str]]:
    """获取并清空自上次调用以来的所有知识库查询记录"""
    queries = list(_KB_QUERIES)
    _KB_QUERIES.clear()
    return queries
