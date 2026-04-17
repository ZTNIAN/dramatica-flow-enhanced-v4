"""Hook/Opening 设计方法论注入函数"""
from __future__ import annotations

from ..kb import KB_HOOK_DESIGNER, KB_OPENING_ENDING

_KB_HOOK_DESIGNER = KB_HOOK_DESIGNER
_KB_OPENING_ENDING = KB_OPENING_ENDING

def get_hook_designer_prompt_injection() -> str:
    """返回钩子设计方法论，注入到 ArchitectAgent 的 prompt 中"""
    if not _KB_HOOK_DESIGNER:
        return ""
    return f"""
## 章末钩子设计参考（HookDesigner 方法论）
{_KB_HOOK_DESIGNER[:3000]}

> 请在 chapter_end_hook 中运用以上7种钩子类型之一，确保章末有强驱动力。
"""


# ═══════════════════════════════════════════════════════════════════════════════
# 6. OpeningEndingDesigner — 方法论注入（不作为独立 Agent）
# ═══════════════════════════════════════════════════════════════════════════════



def get_opening_ending_prompt_injection(chapter_number: int, total_chapters: int = 90) -> str:
    """返回开篇/结尾设计方法论，根据章节位置注入到 ArchitectAgent 的 prompt 中"""
    if not _KB_OPENING_ENDING:
        return ""

    sections = []

    if chapter_number <= 3:
        sections.append(f"""
## 黄金三章设计参考（OpeningEndingDesigner 方法论 — 开篇阶段）
{_KB_OPENING_ENDING[:2000]}

> 第 {chapter_number} 章属于黄金三章范围，请特别注意开篇钩子的强度。
> {'第一章：需要最强的开篇钩子' if chapter_number == 1 else '第二章：需要深化人物引入' if chapter_number == 2 else '第三章：需要自然引入世界观 + 埋下伏笔'}
""")

    if chapter_number >= total_chapters - 3:
        sections.append(f"""
## 全书结尾设计参考（OpeningEndingDesigner 方法论 — 结尾阶段）
{_KB_OPENING_ENDING[2000:] if len(_KB_OPENING_ENDING) > 2000 else ''}

> 第 {chapter_number} 章接近全书结尾，注意高潮对决/主题升华/情感落点。
""")

    return "\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. StyleConsistencyChecker — 五维一致性检查
# ═══════════════════════════════════════════════════════════════════════════════


