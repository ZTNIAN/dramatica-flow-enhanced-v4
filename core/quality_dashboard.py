"""
质量统计仪表盘（新增模块）
统计各章节的审计评分、巡查结果、返工次数、禁止词触发频率
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from typing import Any


@dataclass
class ChapterStats:
    chapter_number: int
    word_count: int = 0
    revision_rounds: int = 0
    patrol_rejected: bool = False
    total_rework: int = 0
    weighted_score: int = 0
    dimension_scores: dict[str, int] = field(default_factory=dict)
    redline_violations: list[str] = field(default_factory=list)
    validation_issues: dict[str, int] = field(default_factory=dict)  # rule -> count
    timestamp: str = ""


@dataclass
class QualityDashboard:
    """质量仪表盘：汇总所有章节的统计数据"""
    book_id: str
    chapters: list[ChapterStats] = field(default_factory=list)

    def add_chapter(self, stats: ChapterStats):
        self.chapters.append(stats)

    def summary(self) -> dict[str, Any]:
        if not self.chapters:
            return {"total_chapters": 0}

        scores = [c.weighted_score for c in self.chapters if c.weighted_score > 0]
        avg_score = sum(scores) / len(scores) if scores else 0

        total_rework = sum(c.total_rework for c in self.chapters)
        patrol_rejections = sum(1 for c in self.chapters if c.patrol_rejected)

        # 各维度平均分
        all_dims: dict[str, list[int]] = {}
        for c in self.chapters:
            for dim, score in c.dimension_scores.items():
                all_dims.setdefault(dim, []).append(score)
        dim_avg = {d: sum(s)/len(s) for d, s in all_dims.items()}

        # 禁止词触发频率
        rule_freq: dict[str, int] = {}
        for c in self.chapters:
            for rule, count in c.validation_issues.items():
                rule_freq[rule] = rule_freq.get(rule, 0) + count

        # 红线触发统计
        redline_count = sum(len(c.redline_violations) for c in self.chapters)

        return {
            "total_chapters": len(self.chapters),
            "avg_weighted_score": round(avg_score, 1),
            "total_rework_count": total_rework,
            "patrol_rejections": patrol_rejections,
            "redline_violations_total": redline_count,
            "dimension_averages": {d: round(s, 1) for d, s in dim_avg.items()},
            "top_validation_issues": sorted(rule_freq.items(), key=lambda x: -x[1])[:10],
            "score_trend": [c.weighted_score for c in self.chapters],
        }

    def format_report(self) -> str:
        s = self.summary()
        lines = [
            f"# 质量仪表盘 — {self.book_id}",
            f"章节总数: {s['total_chapters']}",
            f"平均加权分: {s['avg_weighted_score']}/100",
            f"总返工次数: {s['total_rework_count']}",
            f"巡查打回: {s['patrol_rejections']} 次",
            f"红线触发: {s['redline_violations_total']} 次",
            "",
            "## 各维度平均分",
        ]
        for dim, avg in s.get("dimension_averages", {}).items():
            bar = "#" * int(avg / 5)
            lines.append(f"  {dim}: {avg} {bar}")
        lines.append("")
        lines.append("## 禁止词触发 Top10")
        for rule, count in s.get("top_validation_issues", []):
            lines.append(f"  {rule}: {count} 次")
        lines.append("")
        lines.append("## 评分趋势")
        trend = s.get("score_trend", [])
        if trend:
            lines.append("  " + " → ".join(str(x) for x in trend))
        return "\n".join(lines)

    def save(self, path: str | Path):
        data = {
            "book_id": self.book_id,
            "chapters": [
                {
                    "chapter_number": c.chapter_number,
                    "word_count": c.word_count,
                    "revision_rounds": c.revision_rounds,
                    "patrol_rejected": c.patrol_rejected,
                    "total_rework": c.total_rework,
                    "weighted_score": c.weighted_score,
                    "dimension_scores": c.dimension_scores,
                    "redline_violations": c.redline_violations,
                    "validation_issues": c.validation_issues,
                    "timestamp": c.timestamp,
                }
                for c in self.chapters
            ],
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path, book_id: str = "") -> "QualityDashboard":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        dash = cls(book_id=data.get("book_id", book_id))
        for c in data.get("chapters", []):
            dash.chapters.append(ChapterStats(**c))
        return dash
