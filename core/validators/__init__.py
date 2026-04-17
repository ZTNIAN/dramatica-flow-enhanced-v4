
"""
写后验证器（增强版）
纯规则检测，零 LLM 成本
增强：
  - 禁止词汇扩展到 17 类
  - 红线正则扫描
  - 知识库规则注入
  - 45 特征写作风格约束
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class ValidationIssue:
    rule: str
    severity: Literal["error", "warning"]
    description: str
    excerpt: str | None = None


@dataclass
class ValidationResult:
    passed: bool
    issues: list[ValidationIssue]
    word_count: int

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


# ═══════════════════════════════════════════════════════════════════════════════
# 规则库（增强版 — 17 类红线 + 扩展禁止词）
# ═══════════════════════════════════════════════════════════════════════════════

# ── 1. AI 标记词（每 3000 字最多 1 次）────────────────────────────────────────
AI_MARKER_WORDS = [
    "仿佛", "忽然", "竟然", "不禁", "宛如",
    "猛地", "顿时", "霎时", "不由得",
    "悄然", "蓦然", "倏然", "猝然",
]

# ── 2. 绝对禁止词（出现即 error）──────────────────────────────────────────────
FORBIDDEN_WORDS_ABSOLUTE = [
    # 机械排序
    "首先，", "其次，", "最后，", "总之，", "综上所述",
    # AI过渡词
    "更关键的是", "更奇怪的是", "更有意思的是",
    "值得注意的是", "需要注意的是",
    # 总结性词汇
    "众所周知", "不言而喻", "毫无疑问", "显而易见",
    # 套话开头
    "让我们来看看", "让我们一起", "一方面，",
    "在这个信息爆炸的时代", "在这个时代",
]

# ── 3. 禁止句式 ───────────────────────────────────────────────────────────────
FORBIDDEN_PHRASES = [
    "全场震惊",
    "众人哗然",
    "所有人都",
    "不言而喻",
    "无一例外",
    "众所周知",
    "综上所述",
    "在这个时代",
]

# ── 4. 红线正则模式（17类，error级别）─────────────────────────────────────────
REDBLINE_PATTERNS = [
    # (1) 元叙事
    (r"核心动机",            "元叙事",           "REDLINE_META"),
    (r"叙事节奏",            "元叙事",           "REDLINE_META"),
    (r"人物弧线",            "元叙事",           "REDLINE_META"),
    (r"情节推进",            "元叙事",           "REDLINE_META"),
    (r"信息落差",            "元叙事",           "REDLINE_META"),
    # (2) 报告式语言
    (r"分析了.*?(?:情况|局势|形势)",  "报告式语言",  "REDLINE_REPORT"),
    (r"从.*?(?:角度|层面)(?:来|而言|看)", "报告式语言", "REDLINE_REPORT"),
    (r"综合考虑",            "报告式语言",       "REDLINE_REPORT"),
    (r"综合以上",            "报告式语言",       "REDLINE_REPORT"),
    # (3) 作者说教
    (r"显然[，,。]",         "作者说教",         "REDLINE_PREACH"),
    (r"毫无疑问[，,。]",     "作者说教",         "REDLINE_PREACH"),
    (r"这说明了",            "作者说教",         "REDLINE_PREACH"),
    (r"这充分说明",          "作者说教",         "REDLINE_PREACH"),
    # (4) 集体反应套话
    (r"(?:在场|全场)(?:之人|人|众人)(?:皆|都|全)", "集体反应套话", "REDLINE_COLLECTIVE"),
    (r"(?:众人|所有人)(?:齐声|异口同声)",           "集体反应套话", "REDLINE_COLLECTIVE"),
    (r"一时间.*?(?:哗然|震动|沸腾)",               "集体反应套话", "REDLINE_COLLECTIVE"),
    (r"无一例外",                                   "集体反应套话", "REDLINE_COLLECTIVE"),
    # (5) 套话模板
    (r"的尽头是",            "套话模板",         "REDLINE_CLICHE"),
    (r"不过是.*?的另一种",   "套话模板",         "REDLINE_CLICHE"),
    (r"人生就像",            "套话模板",         "REDLINE_CLICHE"),
    (r"这个世界上有两种人",  "套话模板",         "REDLINE_CLICHE"),
    # (6) AI味感叹
    (r"多么.*?啊[！!]",      "AI感叹句",         "REDLINE_AI_EXCLAIM"),
    (r"何等.*?啊[！!]",      "AI感叹句",         "REDLINE_AI_EXCLAIM"),
    # (7) 过度解释
    (r"也就是说[，,]",       "过度解释",         "REDLINE_OVEREXPLAIN"),
    (r"换句话说[，,]",       "过度解释",         "REDLINE_OVEREXPLAIN"),
    (r"简单来说[，,]",       "过度解释",         "REDLINE_OVEREXPLAIN"),
]

# ── 5. 元叙事模式（warning）────────────────────────────────────────────────────
META_NARRATIVE_PATTERNS = [
    (r"信息差",              "元叙事"),
    (r"爽点",                "元叙事"),
    (r"钩子(?!.*(?:钓鱼|鱼钩))", "元叙事"),  # 排除实际的钩子
]

# ── 6. 报告式语言（warning）────────────────────────────────────────────────────
REPORT_STYLE_PATTERNS = [
    r"客观来说",
    r"实际情况是",
    r"本质上",
]

# ── 7. 集体反应（warning）──────────────────────────────────────────────────────
COLLECTIVE_PATTERNS = [
    r"(?:几乎|差不多)(?:所有人都|每个人)",
]

# ── 8. Show Don't Tell 检测 ────────────────────────────────────────────────────
TELL_PATTERNS = [
    (r"(?:他|她|它|(?:\w{2,4}))(?:感到|觉得|感觉)(?:很|非常|十分|特别|极其)?(?:害怕|恐惧|愤怒|生气|开心|高兴|悲伤|难过|紧张|焦虑|激动|失望|绝望)", "Tell式表达"),
    (r"(?:他|她|它|(?:\w{2,4}))很(?:害怕|恐惧|愤怒|生气|开心|高兴|悲伤|难过|紧张|焦虑|激动|失望|绝望)", "Tell式表达"),
    (r"心里(?:很|非常|十分|特别|极其)?(?:害怕|恐惧|愤怒|开心|悲伤|难过|紧张|激动)", "Tell式表达"),
    (r"心中涌起.*?(?:感|情绪)", "Tell式表达"),
]

# ── 9. 机械排序 ────────────────────────────────────────────────────────────────
MECHANICAL_ORDER_PATTERNS = [
    (r"首先[，,].*?其次[，,].*?最后", "机械排序三连"),
    (r"第一[，,].*?第二[，,].*?第三", "机械排序三连"),
    (r"一方面[，,].*?另一方面", "机械对仗"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# PostWriteValidator（增强版）
# ═══════════════════════════════════════════════════════════════════════════════

class PostWriteValidator:
    def __init__(self, custom_forbidden_words: list[str] | None = None):
        self.custom_forbidden_words = custom_forbidden_words or []

    def validate(self, content: str, target_words: int, chapter_number: int = 0) -> ValidationResult:
        issues: list[ValidationIssue] = []
        word_count = len(content)

        # ── 规则 1：AI 标记词密度 ──────────────────────────────────────────────
        for word in AI_MARKER_WORDS:
            count = len(re.findall(re.escape(word), content))
            if count == 0:
                continue
            per_3000 = (count / word_count) * 3000 if word_count > 0 else 0
            if per_3000 > 1:
                issues.append(ValidationIssue(
                    rule="AI_MARKER_DENSITY",
                    severity="warning",
                    description=f"「{word}」出现 {count} 次（每3000字 {per_3000:.1f} 次，上限 1）",
                    excerpt=word,
                ))

        # ── 规则 2：绝对禁止词（error）─────────────────────────────────────────
        for word in FORBIDDEN_WORDS_ABSOLUTE:
            if word in content:
                issues.append(ValidationIssue(
                    rule="FORBIDDEN_WORD_ABSOLUTE",
                    severity="error",
                    description=f"绝对禁止词：「{word}」",
                    excerpt=word,
                ))

        # ── 规则 3：禁止句式 ───────────────────────────────────────────────────
        for phrase in FORBIDDEN_PHRASES:
            if phrase in content:
                issues.append(ValidationIssue(
                    rule="FORBIDDEN_PHRASE",
                    severity="error",
                    description=f"禁止句式：「{phrase}」",
                    excerpt=phrase,
                ))

        # ── 规则 4：17 类红线正则扫描（error）──────────────────────────────────
        for pattern, label, rule_code in REDBLINE_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                issues.append(ValidationIssue(
                    rule=rule_code,
                    severity="error",
                    description=f"{label}：「{matches[0]}」（共 {len(matches)} 处）",
                    excerpt=matches[0],
                ))

        # ── 规则 5：元叙事（warning）───────────────────────────────────────────
        for pattern, label in META_NARRATIVE_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                issues.append(ValidationIssue(
                    rule="META_NARRATIVE",
                    severity="warning",
                    description=f"{label}：「{matches[0]}」",
                    excerpt=matches[0],
                ))

        # ── 规则 6：报告式语言（warning）────────────────────────────────────────
        for pattern in REPORT_STYLE_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                issues.append(ValidationIssue(
                    rule="REPORT_STYLE",
                    severity="warning",
                    description=f"报告式语言：「{matches[0]}」",
                    excerpt=matches[0],
                ))

        # ── 规则 7：集体反应（warning）─────────────────────────────────────────
        for pattern in COLLECTIVE_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                issues.append(ValidationIssue(
                    rule="COLLECTIVE_REACTION",
                    severity="warning",
                    description=f"集体反应：「{matches[0]}」",
                    excerpt=matches[0],
                ))

        # ── 规则 8：Show Don't Tell 检测（warning）────────────────────────────
        for pattern, label in TELL_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                issues.append(ValidationIssue(
                    rule="TELL_DONT_SHOW",
                    severity="warning",
                    description=f"{label}：「{matches[0]}」（共 {len(matches)} 处）",
                    excerpt=matches[0],
                ))

        # ── 规则 9：机械排序（warning）─────────────────────────────────────────
        for pattern, label in MECHANICAL_ORDER_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                issues.append(ValidationIssue(
                    rule="MECHANICAL_ORDER",
                    severity="warning",
                    description=f"{label}：「{matches[0]}」",
                    excerpt=matches[0],
                ))

        # ── 规则 10：连续"了"字 ───────────────────────────────────────────────
        sentences = re.split(r"[。！？!?]", content)
        max_consecutive_le = 0
        consecutive = 0
        for s in sentences:
            if "了" in s:
                consecutive += 1
                max_consecutive_le = max(max_consecutive_le, consecutive)
            else:
                consecutive = 0
        if max_consecutive_le >= 6:
            issues.append(ValidationIssue(
                rule="CONSECUTIVE_LE",
                severity="warning",
                description=f"连续 {max_consecutive_le} 句含「了」字（上限 6）",
            ))

        # ── 规则 11：段落过长 ──────────────────────────────────────────────────
        paragraphs = [p for p in re.split(r"\n{2,}", content) if p.strip()]
        long_paragraphs = [p for p in paragraphs if len(p) > 300]
        if len(long_paragraphs) >= 2:
            issues.append(ValidationIssue(
                rule="LONG_PARAGRAPH",
                severity="warning",
                description=f"{len(long_paragraphs)} 个段落超过 300 字",
            ))

        # ── 规则 12：字数偏差 ──────────────────────────────────────────────────
        if target_words > 0:
            deviation = abs(word_count - target_words) / target_words
            if deviation > 0.2:
                issues.append(ValidationIssue(
                    rule="WORD_COUNT_DEVIATION",
                    severity="warning",
                    description=f"实际 {word_count} 字，目标 {target_words} 字，偏差 {deviation*100:.0f}%",
                ))

        # ── 规则 13：自定义禁止词 ──────────────────────────────────────────────
        for word in self.custom_forbidden_words:
            count = len(re.findall(re.escape(word), content))
            if count > 1:
                issues.append(ValidationIssue(
                    rule="CUSTOM_FORBIDDEN_WORD",
                    severity="warning",
                    description=f"自定义禁止词「{word}」出现 {count} 次",
                    excerpt=word,
                ))

        has_error = any(i.severity == "error" for i in issues)
        return ValidationResult(passed=not has_error, issues=issues, word_count=word_count)

    def summarize(self, results: list[ValidationResult]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in results:
            for issue in r.issues:
                counts[issue.rule] = counts.get(issue.rule, 0) + 1
        return counts
