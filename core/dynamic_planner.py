'''
动态分层规划（V3 升级版）
基于 OpenMOSS 动态分层规划机制，支持 100-5000+ 章自适应

V3 升级内容：
- 引入 OpenMOSS 完整的动态计算公式（战役/战术范围随总章节数自动调整）
- 支持四层结构（超长篇1500章+自动启用：战略→卷→篇→战术）
- 支持中途调整总章节数（自动重算所有范围）
- 章后审计分数反馈到张力曲线调整
'''
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


# ═══════════════════════════════════════════════════════════════════════════════
# OpenMOSS 动态范围计算公式
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_campaign_range(total_chapters: int) -> int:
    """根据总章节数计算战役规划范围（每X章一个战役）"""
    if total_chapters <= 300:
        return min(20, max(10, total_chapters // 5))
    elif total_chapters <= 800:
        return min(30, max(20, total_chapters // 4))
    elif total_chapters <= 1500:
        return min(50, max(30, total_chapters // 3))
    elif total_chapters <= 3000:
        return min(80, max(50, int(total_chapters / 2.5)))
    else:
        return min(100, max(80, total_chapters // 2))


def calculate_tactical_range(total_chapters: int) -> int:
    """根据总章节数计算战术规划范围（每Y章一个战术单元）"""
    if total_chapters <= 300:
        return max(1, min(3, total_chapters // 100))
    elif total_chapters <= 800:
        return max(2, min(4, total_chapters // 200))
    elif total_chapters <= 1500:
        return max(3, min(5, total_chapters // 300))
    elif total_chapters <= 3000:
        return max(5, min(10, total_chapters // 300))
    else:
        return max(10, min(15, total_chapters // 300))


def get_planning_mode(total_chapters: int) -> str:
    """根据总章节数返回规划模式"""
    if total_chapters <= 300:
        return "轻规划"
    elif total_chapters <= 800:
        return "标准规划"
    elif total_chapters <= 1500:
        return "强化规划"
    elif total_chapters <= 3000:
        return "重度规划"
    else:
        return "四层结构"  # 1500章+启用卷→篇→战术


# ═══════════════════════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class StrategicGoal:
    '''战略层：全书级别的目标'''
    goal_id: str
    description: str
    target_chapters: int
    progress: float = 0.0
    sub_goals: list[str] = field(default_factory=list)
    status: Literal["active", "completed", "paused"] = "active"


@dataclass
class CampaignPlan:
    '''战役层：卷/弧级别的规划'''
    campaign_id: str
    name: str
    strategic_goal_id: str
    start_chapter: int
    end_chapter: int
    climax_chapter: int
    key_events: list[str] = field(default_factory=list)
    character_arcs: dict[str, str] = field(default_factory=dict)
    tension_curve: list[int] = field(default_factory=list)
    status: Literal["planning", "active", "completed"] = "planning"
    current_chapter: int = 0


@dataclass
class VolumePlan:
    '''卷规划（超长篇1500章+的第二层）'''
    volume_id: str
    name: str
    start_chapter: int
    end_chapter: int
    theme: str = ""
    sub_plans: list[str] = field(default_factory=list)  # 篇规划ID列表
    status: Literal["planning", "active", "completed"] = "planning"


@dataclass
class ArcPlan:
    '''篇规划（超长篇1500章+的第三层）'''
    arc_id: str
    name: str
    volume_id: str
    start_chapter: int
    end_chapter: int
    climax_chapter: int = 0
    tension_curve: list[int] = field(default_factory=list)
    status: Literal["planning", "active", "completed"] = "planning"


@dataclass
class TacticalBeat:
    '''战术层：章节级别的节拍'''
    chapter: int
    beats: list[str] = field(default_factory=list)
    target_words: int = 2000
    emotional_target: str = ""
    must_include: list[str] = field(default_factory=list)


@dataclass
class ChapterAuditRecord:
    '''章节审计记录（用于动态调整）'''
    chapter: int
    weighted_total: int
    dimension_scores: dict[str, int] = field(default_factory=dict)
    redline_violations: list[str] = field(default_factory=list)
    revision_rounds: int = 0


class DynamicPlanner:
    '''动态分层规划器（V3 升级版）'''

    def __init__(self, book_id: str, total_chapters: int = 0):
        self.book_id = book_id
        self.total_chapters = total_chapters

        # 动态参数（根据 total_chapters 自动计算）
        self.campaign_range = calculate_campaign_range(total_chapters) if total_chapters else 20
        self.tactical_range = calculate_tactical_range(total_chapters) if total_chapters else 3
        self.planning_mode = get_planning_mode(total_chapters) if total_chapters else "标准规划"

        # 四层数据
        self.strategic_goals: dict[str, StrategicGoal] = {}
        self.campaigns: dict[str, CampaignPlan] = {}
        self.volumes: dict[str, VolumePlan] = {}       # 超长篇第二层
        self.arcs: dict[str, ArcPlan] = {}              # 超长篇第三层
        self.tactical_beats: dict[int, TacticalBeat] = {}

        # 审计记录（用于动态调整）
        self.audit_records: list[ChapterAuditRecord] = []

    def set_total_chapters(self, total: int):
        """重新设置总章节数，自动重算所有动态参数"""
        self.total_chapters = total
        self.campaign_range = calculate_campaign_range(total)
        self.tactical_range = calculate_tactical_range(total)
        self.planning_mode = get_planning_mode(total)

    def auto_generate_campaigns(self, strategic_goal_id: str, campaign_names: list[str] | None = None):
        """根据动态范围自动生成战役规划"""
        if not self.total_chapters:
            raise ValueError("total_chapters 未设置，无法自动生成战役规划")

        range_size = self.campaign_range
        num_campaigns = (self.total_chapters + range_size - 1) // range_size

        self.campaigns.clear()
        for i in range(num_campaigns):
            start = i * range_size + 1
            end = min((i + 1) * range_size, self.total_chapters)
            name = campaign_names[i] if campaign_names and i < len(campaign_names) else f"第{i+1}战役"
            climax = start + (end - start) * 2 // 3  # 高潮在战役后2/3处

            campaign = CampaignPlan(
                campaign_id=f"campaign_{i+1:03d}",
                name=name,
                strategic_goal_id=strategic_goal_id,
                start_chapter=start,
                end_chapter=end,
                climax_chapter=climax,
                tension_curve=[5] * (end - start + 1),  # 默认中等张力
            )
            self.campaigns[campaign.campaign_id] = campaign

    def get_current_campaign(self, chapter: int) -> CampaignPlan | None:
        '''根据当前章节号找到所属战役'''
        for c in self.campaigns.values():
            if c.start_chapter <= chapter <= c.end_chapter:
                return c
        return None

    def get_tension_target(self, chapter: int) -> int:
        '''获取当前章节的目标张力值'''
        campaign = self.get_current_campaign(chapter)
        if campaign and campaign.tension_curve:
            idx = chapter - campaign.start_chapter
            if 0 <= idx < len(campaign.tension_curve):
                return campaign.tension_curve[idx]
        return 5

    def update_progress(self, chapter: int):
        '''更新进度'''
        campaign = self.get_current_campaign(chapter)
        if campaign:
            campaign.current_chapter = chapter
            total = campaign.end_chapter - campaign.start_chapter + 1
            done = chapter - campaign.start_chapter + 1
            goal = self.strategic_goals.get(campaign.strategic_goal_id)
            if goal:
                campaign_weight = total / goal.target_chapters if goal.target_chapters > 0 else 0
                campaign_progress = done / total if total > 0 else 0
                goal.progress = min(1.0, goal.progress + campaign_weight * campaign_progress * 0.01)

    def record_chapter_audit(self, record: ChapterAuditRecord):
        """记录章节审计结果，用于动态调整"""
        self.audit_records.append(record)

    def adjust_tension_based_on_audit(self, chapter: int):
        """根据审计分数动态调整后续章节张力曲线

        规则：
        - 审计分 < 85：后续3章张力降1（避免连续高压导致质量下降）
        - 审计分 >= 95：后续2章可适当升1（质量好，可以加速）
        - 有红线：后续5章张力降2（严重问题，必须减速）
        """
        if not self.audit_records:
            return

        # 找到当前章节的审计记录
        current_record = None
        for r in self.audit_records:
            if r.chapter == chapter:
                current_record = r
                break
        if not current_record:
            return

        campaign = self.get_current_campaign(chapter)
        if not campaign:
            return

        if current_record.redline_violations:
            # 红线问题：后续5章张力降2
            adjust_range = 5
            adjust_amount = -2
        elif current_record.weighted_total < 85:
            # 低分：后续3章张力降1
            adjust_range = 3
            adjust_amount = -1
        elif current_record.weighted_total >= 95:
            # 高分：后续2章张力升1
            adjust_range = 2
            adjust_amount = 1
        else:
            return

        # 应用调整
        for offset in range(1, adjust_range + 1):
            target_ch = chapter + offset
            if target_ch > campaign.end_chapter:
                break
            idx = target_ch - campaign.start_chapter
            if 0 <= idx < len(campaign.tension_curve):
                new_val = campaign.tension_curve[idx] + adjust_amount
                campaign.tension_curve[idx] = max(1, min(10, new_val))

    def adjust_campaign(self, campaign_id: str, reason: str, **kwargs):
        '''动态调整战役规划'''
        campaign = self.campaigns.get(campaign_id)
        if not campaign:
            return
        if "end_chapter" in kwargs:
            campaign.end_chapter = kwargs["end_chapter"]
        if "climax_chapter" in kwargs:
            campaign.climax_chapter = kwargs["climax_chapter"]
        if "tension_curve" in kwargs:
            campaign.tension_curve = kwargs["tension_curve"]

    def get_planning_summary(self) -> dict:
        """返回当前规划摘要（供 CLI/Web UI 展示）"""
        return {
            "book_id": self.book_id,
            "total_chapters": self.total_chapters,
            "planning_mode": self.planning_mode,
            "campaign_range": self.campaign_range,
            "tactical_range": self.tactical_range,
            "num_campaigns": len(self.campaigns),
            "num_volumes": len(self.volumes),
            "num_arcs": len(self.arcs),
            "audit_records": len(self.audit_records),
        }

    def save(self, path: str | Path):
        data = {
            "book_id": self.book_id,
            "total_chapters": self.total_chapters,
            "campaign_range": self.campaign_range,
            "tactical_range": self.tactical_range,
            "planning_mode": self.planning_mode,
            "strategic_goals": {k: vars(v) for k, v in self.strategic_goals.items()},
            "campaigns": {k: vars(v) for k, v in self.campaigns.items()},
            "volumes": {k: vars(v) for k, v in self.volumes.items()},
            "arcs": {k: vars(v) for k, v in self.arcs.items()},
            "tactical_beats": {str(k): vars(v) for k, v in self.tactical_beats.items()},
            "audit_records": [vars(r) for r in self.audit_records],
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> 'DynamicPlanner':
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        planner = cls(
            book_id=data.get("book_id", ""),
            total_chapters=data.get("total_chapters", 0),
        )
        planner.campaign_range = data.get("campaign_range", 20)
        planner.tactical_range = data.get("tactical_range", 3)
        planner.planning_mode = data.get("planning_mode", "标准规划")
        for k, v in data.get("strategic_goals", {}).items():
            planner.strategic_goals[k] = StrategicGoal(**v)
        for k, v in data.get("campaigns", {}).items():
            planner.campaigns[k] = CampaignPlan(**v)
        for k, v in data.get("volumes", {}).items():
            planner.volumes[k] = VolumePlan(**v)
        for k, v in data.get("arcs", {}).items():
            planner.arcs[k] = ArcPlan(**v)
        for k, v in data.get("tactical_beats", {}).items():
            planner.tactical_beats[int(k)] = TacticalBeat(**v)
        for r in data.get("audit_records", []):
            planner.audit_records.append(ChapterAuditRecord(**r))
        return planner
