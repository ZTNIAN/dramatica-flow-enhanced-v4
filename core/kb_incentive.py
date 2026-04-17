"""
知识库查询激励（新增模块）
记录各Agent查询知识库的次数，用于统计和激励
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime


@dataclass
class KBQueryRecord:
    agent_role: str           # architect/writer/auditor/patrol/reviser
    knowledge_file: str       # 查询的知识库文件名
    query_time: str = ""
    context: str = ""         # 查询上下文摘要


@dataclass
class KBIncentiveTracker:
    """知识库查询激励追踪器"""
    queries: list[KBQueryRecord] = field(default_factory=list)

    def record_query(self, agent_role: str, knowledge_file: str, context: str = ""):
        self.queries.append(KBQueryRecord(
            agent_role=agent_role,
            knowledge_file=knowledge_file,
            query_time=datetime.now().isoformat(),
            context=context[:200],
        ))

    def get_stats(self) -> dict:
        role_counts: dict[str, int] = {}
        file_counts: dict[str, int] = {}
        for q in self.queries:
            role_counts[q.agent_role] = role_counts.get(q.agent_role, 0) + 1
            file_counts[q.knowledge_file] = file_counts.get(q.knowledge_file, 0) + 1
        return {
            "total_queries": len(self.queries),
            "by_role": role_counts,
            "by_file": file_counts,
            "most_queried_file": max(file_counts, key=file_counts.get) if file_counts else "",
        }

    def format_report(self) -> str:
        stats = self.get_stats()
        lines = [
            f"知识库查询统计：共 {stats['total_queries']} 次",
            "按角色：",
        ]
        for role, count in stats["by_role"].items():
            lines.append(f"  {role}: {count} 次")
        lines.append("按文件：")
        for f, count in stats["by_file"].items():
            lines.append(f"  {f}: {count} 次")
        return "\n".join(lines)
