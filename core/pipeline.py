"""
写作管线
修复：
- AuditIssue 构造不再传 excerpt 到 location
- 章后调用 update_current_state_md
- 集成 SummaryAgent，写完生成摘要注入 chapter_summaries.md
- WriterAgent 获得前情摘要上下文
- _apply_settlement 完整处理位置/情感/关系变化
多线叙事扩展：
- 多线程调度：根据章纲的 thread_id 解析视角角色和线程上下文
- 跨线程感知：建筑师/写手/审计员均获得其他线程状态
- 时间轴记录：写完章节后自动添加 TimelineEvent
- 线程权重管理：根据线程的 weight 调整字数分配
- 支线掉线预警：章后更新 thread_status.md
"""
from __future__ import annotations

import os
import logging
import traceback
import uuid
from dataclasses import dataclass, field

from .agents import (
    ArchitectAgent, ArchitectBlueprint,
    WriterAgent, WriterOutput,
    PatrolAgent, PatrolReport,
    AuditorAgent, AuditReport, AuditIssue,
    ReviserAgent, ReviseResult,
    SummaryAgent,
    # V4: 增强 Agent
    DialogueExpert, DialogueReviewResult,
    EmotionCurveDesigner, EmotionCurveResult,
    CharacterGrowthExpert, CharacterGrowthResult,
    FeedbackExpert, FeedbackResult,
    StyleConsistencyChecker, StyleConsistencyResult,
    SceneArchitect, SceneAuditResult,
    PsychologicalPortrayalExpert, PsychologicalAuditResult,
    MiroFishReader, MiroFishResult,
)
from .narrative import NarrativeEngine, ChapterOutlineSchema
from .state import StateManager
from .types.narrative import Character, NarrativeThread, TimelineEvent
from .types.state import (
    TruthFileKey, EmotionalSnapshot, CausalLink, AffectedDecision,
    Hook, HookType, HookStatus,
)
from .validators import PostWriteValidator
from .quality_dashboard import QualityDashboard, ChapterStats
from .dynamic_planner import DynamicPlanner
from .kb_incentive import KBIncentiveTracker


@dataclass
class PipelineConfig:
    """管线可配置参数（优先读环境变量，否则用默认值）"""
    max_revise_rounds: int = 3          # 最大修订轮数
    mirofish_interval: int = 5          # MiroFish 每N章触发
    mirofish_sample_chars: int = 3000   # MiroFish 每章采样字数
    recent_summaries_n: int = 3         # 前情摘要取最近N章
    dormancy_threshold: int = 5         # 支线掉线预警阈值（章）
    review_score_floor: int = 75        # 审查Agent问题汇入阈值
    style_score_floor: int = 80         # 风格一致性修正阈值
    audit_tension_floor: int = 90       # 审计分低于此值调整张力曲线
    audit_dimension_floor: int = 85     # 单项维度最低分要求
    audit_pass_total: int = 95          # 审计通过加权总分要求
    # V5: 选择性审查模式
    review_mode: str = "all"            # all | light | minimal | adaptive
    review_full_interval: int = 5       # adaptive 模式下每N章强制全量
    review_force_score: int = 70        # 低于此分强制全量审查

    @classmethod
    def from_env(cls) -> PipelineConfig:
        """从环境变量读取配置，未设置则用默认值"""
        def _int(key: str, default: int) -> int:
            try:
                return int(os.environ.get(key, default))
            except (ValueError, TypeError):
                return default
        def _str(key: str, default: str) -> str:
            return os.environ.get(key, default) or default
        return cls(
            max_revise_rounds=_int("PIPELINE_MAX_REVISE_ROUNDS", 3),
            mirofish_interval=_int("PIPELINE_MIROFISH_INTERVAL", 5),
            mirofish_sample_chars=_int("PIPELINE_MIROFISH_SAMPLE_CHARS", 3000),
            recent_summaries_n=_int("PIPELINE_RECENT_SUMMARIES_N", 3),
            dormancy_threshold=_int("PIPELINE_DORMANCY_THRESHOLD", 5),
            review_score_floor=_int("PIPELINE_REVIEW_SCORE_FLOOR", 75),
            style_score_floor=_int("PIPELINE_STYLE_SCORE_FLOOR", 80),
            audit_tension_floor=_int("PIPELINE_AUDIT_TENSION_FLOOR", 90),
            audit_dimension_floor=_int("PIPELINE_AUDIT_DIMENSION_FLOOR", 85),
            audit_pass_total=_int("PIPELINE_AUDIT_PASS_TOTAL", 95),
            review_mode=_str("PIPELINE_REVIEW_MODE", "all"),
            review_full_interval=_int("PIPELINE_REVIEW_FULL_INTERVAL", 5),
            review_force_score=_int("PIPELINE_REVIEW_FORCE_SCORE", 70),
        )


@dataclass
class PipelineResult:
    chapter_number: int
    content: str
    audit_report: AuditReport
    validation_passed: bool
    revision_rounds: int
    causal_links: int
    word_count: int
    # 多线叙事扩展
    thread_id: str = ""
    pov_character_id: str = ""
    dormancy_warnings: list[str] = field(default_factory=list)
    # 增强：巡查报告 + 返工监控
    patrol_report: PatrolReport | None = None
    patrol_rejected: bool = False
    total_rework_count: int = 0  # 总返工次数（含巡查+审计）


class WritingPipeline:
    """
    单章写作管线：

    快照备份
        ↓
    [建筑师] 规划蓝图（含前情摘要上下文）
        ↓
    [写手] 生成正文 + 写后结算表
        ↓
    [写后验证器] 零 LLM 硬规则检测
        ↓ error → spot-fix
    [审计员] 叙事质量审计（temperature=0）
        ↓ critical → 修订 → 再审（最多 MAX_REVISE_ROUNDS 轮）
    保存最终稿
        ↓
    [因果链提取] 从正文中提取因果关系
        ↓
    [摘要生成] 生成章节摘要 → chapter_summaries.md
        ↓
    [状态更新] 结算表 → world_state.json + current_state.md
    """

    # MAX_REVISE_ROUNDS 改由 self.config.max_revise_rounds 控制

    def __init__(
        self,
        state_manager: StateManager,
        architect: ArchitectAgent,
        writer: WriterAgent,
        auditor: AuditorAgent,
        reviser: ReviserAgent,
        narrative_engine: NarrativeEngine,
        summary_agent: SummaryAgent,
        validator: PostWriteValidator,
        protagonist: Character,
        all_characters: list[Character],
        patrol: PatrolAgent | None = None,  # 增强：巡查者（可选）
        dashboard: QualityDashboard | None = None,  # 增强：质量仪表盘（可选）
        dynamic_planner: DynamicPlanner | None = None,  # 增强：动态规划器（可选）
        kb_tracker: KBIncentiveTracker | None = None,  # V4：知识库查询激励追踪
        # V4: 增强 Agent（可选）
        dialogue_expert: DialogueExpert | None = None,
        emotion_curve_designer: EmotionCurveDesigner | None = None,
        character_growth_expert: CharacterGrowthExpert | None = None,
        feedback_expert: FeedbackExpert | None = None,
        style_checker: StyleConsistencyChecker | None = None,
        scene_architect: SceneArchitect | None = None,
        psychological_expert: PsychologicalPortrayalExpert | None = None,
        mirofish_reader: MiroFishReader | None = None,
        config: PipelineConfig | None = None,  # V5: 可配置参数
    ):
        self.config = config or PipelineConfig.from_env()
        self.sm = state_manager
        self.architect = architect
        self.writer = writer
        self.auditor = auditor
        self.reviser = reviser
        self.engine = narrative_engine
        self.summary_agent = summary_agent
        self.validator = validator
        self.protagonist = protagonist
        self.all_characters = all_characters
        self.patrol = patrol  # 增强：巡查者（可选）
        self.dashboard = dashboard  # 增强：质量仪表盘（可选）
        self.dynamic_planner = dynamic_planner  # 增强：动态规划器（可选）
        self.kb_tracker = kb_tracker or KBIncentiveTracker()  # V4：知识库查询激励
        # V4: 增强 Agent
        self.dialogue_expert = dialogue_expert
        self.emotion_curve_designer = emotion_curve_designer
        self.character_growth_expert = character_growth_expert
        self.feedback_expert = feedback_expert
        self.style_checker = style_checker
        self.scene_architect = scene_architect
        self.psychological_expert = psychological_expert
        self.mirofish_reader = mirofish_reader
        # V5: WebSocket 进度回调
        self._progress_callback: Callable[[dict], None] | None = None

    def set_progress_callback(self, cb: Callable[[dict], None] | None):
        """设置进度回调，用于 WebSocket 实时推送"""
        self._progress_callback = cb

    def _emit(self, step: str, detail: str = "", **extra):
        """发射进度事件"""
        if self._progress_callback:
            try:
                event = {"step": step, "detail": detail, **extra}
                self._progress_callback(event)
            except Exception:
                pass  # 回调失败不影响管线

    def _should_run_review(self, agent_name: str, chapter: int) -> bool:
        """V5: 根据审查模式决定是否运行某个审查 Agent"""
        mode = self.config.review_mode
        if mode == "all":
            return True
        if mode == "minimal":
            return False  # minimal 模式跳过所有专项审查，只跑审计
        if mode == "light":
            return agent_name in ("dialogue", "scene")  # light 只跑对话+场景
        if mode == "adaptive":
            # 每 N 章强制全量
            if chapter % self.config.review_full_interval == 0:
                return True
            return agent_name in ("dialogue", "scene")
        return True

    def run(
        self,
        chapter_outline: ChapterOutlineSchema,
        verbose: bool = False,
    ) -> PipelineResult:
        ch = chapter_outline.chapter_number
        title = chapter_outline.title

        def log(msg: str) -> None:
            if verbose:
                print(f"  [{ch}] {msg}")

        # ── 快照 ─────────────────────────────────────────────────────────────
        log("创建快照...")
        self.sm.create_snapshot(ch - 1)

        # ── 读取上下文 ────────────────────────────────────────────────────────
        world_context = self.sm.read_truth_bundle([
            TruthFileKey.CURRENT_STATE,
            TruthFileKey.CHARACTER_MATRIX,
        ])
        pending_hooks = self.sm.read_truth(TruthFileKey.PENDING_HOOKS)

        # 因果链 + 情感弧线（写手也需要看到）
        causal_chain = self.sm.read_truth(TruthFileKey.CAUSAL_CHAIN)
        emotional_arcs = self.sm.read_truth(TruthFileKey.EMOTIONAL_ARCS)

        # 前情摘要：取最近 3 章
        full_summaries = self.sm.read_truth(TruthFileKey.CHAPTER_SUMMARIES)
        prior_summaries = _extract_recent_summaries(full_summaries, n=self.config.recent_summaries_n)

        # ── 多线程上下文解析 ──────────────────────────────────────────────────
        ws = self.sm.read_world_state()
        thread_id = getattr(chapter_outline, "thread_id", "thread_main") or "thread_main"
        pov_char_id = getattr(chapter_outline, "pov_character_id", "") or ""

        # 解析视角角色
        pov_character: Character | None = None
        if pov_char_id:
            for c in self.all_characters:
                if c.id == pov_char_id:
                    pov_character = c
                    break
        # 回退到线程的 pov_character_id
        if not pov_character and thread_id:
            thread = ws.get_thread(thread_id)
            if thread and thread.pov_character_id:
                for c in self.all_characters:
                    if c.id == thread.pov_character_id:
                        pov_character = c
                        break

        # 构建跨线程上下文摘要
        thread_context = self._build_thread_context(ws, thread_id, ch)

        # 根据线程权重调整字数
        effective_thread = ws.get_thread(thread_id) if thread_id else None
        thread_weight = effective_thread.weight if effective_thread else 1.0
        adjusted_target_words = max(
            int(chapter_outline.target_words * thread_weight),
            int(chapter_outline.target_words * 0.5),
        )

        if verbose and effective_thread:
            log(f"线程：{effective_thread.name}（{thread_id}），权重={thread_weight}，调整字数={adjusted_target_words}")

        # ── 1. 建筑师规划 ─────────────────────────────────────────────────────
        log("建筑师规划...")
        self._emit("architect", f"规划第{ch}章蓝图")
        blueprint = self.architect.plan_chapter(
            chapter_outline=chapter_outline,
            world_context=world_context,
            pending_hooks=pending_hooks,
            prior_chapter_summary=prior_summaries,
            pov_character=pov_character,
            thread_context=thread_context,
        )
        # V4：记录建筑师的KB查询
        from .agents import get_kb_queries
        for role, fname, ctx in get_kb_queries():
            self.kb_tracker.record_query(role, fname, ctx)

        # ── 2. 写手写章 ───────────────────────────────────────────────────────
        log("写手写章...")
        self._emit("writer", f"撰写第{ch}章正文")
        scene_summaries = _format_beats(chapter_outline)
        writer_output = self.writer.write_chapter(
            scene_summaries=scene_summaries,
            blueprint=blueprint,
            protagonist=self.protagonist,
            world_context=world_context,
            chapter_number=ch,
            target_words=adjusted_target_words,
            prior_summaries=prior_summaries,
            chapter_title=title,
            pov_character=pov_character,
            thread_context=thread_context,
            pending_hooks=pending_hooks,
            causal_chain=causal_chain,
            emotional_arcs=emotional_arcs,
        )
        self.sm.save_draft(ch, writer_output.content)
        log(f"草稿 {len(writer_output.content)} 字")
        # V4：记录写手的KB查询
        for role, fname, ctx in get_kb_queries():
            self.kb_tracker.record_query(role, fname, ctx)

        # ═══════════════════════════════════════════════════════════════════════
        # V4：统一审查循环
        # 所有审查 Agent 的结果汇聚成 issues 列表，喂给修订者，形成闭环
        # ═══════════════════════════════════════════════════════════════════════

        current_content = writer_output.content
        total_rework = 0
        revision_rounds = 0
        patrol_report = None
        patrol_rejected = False
        dialogue_review = None
        scene_audit = None
        psych_audit = None
        style_check = None

        def _collect_review_issues() -> list[AuditIssue]:
            """从所有审查 Agent 收集问题，转为 AuditIssue 列表"""
            issues: list[AuditIssue] = []

            # 对话审查问题
            if dialogue_review and dialogue_review.issues:
                for di in dialogue_review.issues:
                    if di.get("type") != "positive":
                        issues.append(AuditIssue(
                            dimension="对话质量",
                            severity="warning" if dialogue_review.overall_score >= 80 else "critical",
                            description=f"[{di.get('character', '通用')}] {di.get('description', '')}",
                            suggestion=di.get("suggestion", ""),
                        ))

            # 场景审核问题
            if scene_audit and scene_audit.issues:
                for si in scene_audit.issues:
                    if si.get("score", 100) < self.config.review_score_floor:
                        issues.append(AuditIssue(
                            dimension="场景构建",
                            severity="warning" if si.get("score", 0) >= 60 else "critical",
                            description=f"[{si.get('dimension', '')}] {si.get('description', '')}",
                            suggestion=si.get("suggestion", ""),
                        ))

            # 心理审核问题
            if psych_audit and psych_audit.issues:
                for pi in psych_audit.issues:
                    if pi.get("score", 100) < self.config.review_score_floor:
                        issues.append(AuditIssue(
                            dimension="心理刻画",
                            severity="warning" if pi.get("score", 0) >= 60 else "critical",
                            description=f"[{pi.get('dimension', '')}] {pi.get('description', '')}",
                            suggestion=pi.get("suggestion", ""),
                        ))

            # 风格一致性问题
            if style_check and style_check.issues:
                for si in style_check.issues:
                    if si.get("severity", "info") in ("critical", "warning"):
                        issues.append(AuditIssue(
                            dimension="风格一致",
                            severity=si.get("severity", "warning"),
                            description=si.get("description", ""),
                            suggestion=si.get("suggestion", ""),
                        ))

            return issues

        # ── 2.5 对话专家审查（V5: 选择性触发）─────────────────────────────────
        if self.dialogue_expert and self._should_run_review("dialogue", ch):
            log("对话专家审查...")
            self._emit("review_dialogue", f"审查第{ch}章对话")
            try:
                char_names = [c.name for c in self.all_characters]
                dialogue_review = self.dialogue_expert.review_dialogue(
                    chapter_content=current_content,
                    chapter_number=ch,
                    characters=char_names,
                )
                log(f"  对话评分：{dialogue_review.overall_score}/100")
                if dialogue_review.overall_score < self.config.review_score_floor:
                    log(f"  ⚠ 对话质量偏低，问题将汇入修订循环")
            except Exception as e:
                log(f"  对话审查失败（不阻塞）：{type(e).__name__}: {e}")
                if not isinstance(e, (json.JSONDecodeError, KeyError, ValueError)):
                    log(f"  详细错误：{traceback.format_exc()[-500:]}")

        # ── 3. 写后验证（零 LLM） ────────────────────────────────────────────
        log("写后验证...")
        val_result = self.validator.validate(
            current_content,
            target_words=adjusted_target_words,
        )

        if not val_result.passed:
            error_issues = [
                AuditIssue(
                    dimension="写后验证",
                    severity="critical",
                    description=i.description,
                    location=i.excerpt,
                )
                for i in val_result.issues
                if i.severity == "error"
            ]
            log(f"验证未通过（{len(error_issues)} 个 error），spot-fix...")
            fix_result = self.reviser.revise(current_content, error_issues, mode="spot-fix")
            current_content = fix_result.content

        # ── 3.5 巡查者快速扫描 ───────────────────────────────────────────────
        if self.patrol:
            log("巡查者快速扫描...")
            patrol_report = self.patrol.quick_scan(
                chapter_content=current_content,
                chapter_number=ch,
                blueprint=blueprint,
                settlement=writer_output.settlement,
            )
            if not patrol_report.passed:
                patrol_rejected = True
                total_rework += 1
                log(f"  巡查打回：{patrol_report.conclusion}")
                failed_items = [i for i in patrol_report.issues if i.status == "fail"]
                if failed_items:
                    revise_result = self.reviser.revise(
                        original_content=current_content,
                        issues=[AuditIssue(
                            dimension="巡查打回",
                            severity="critical",
                            description=f"{i.check_item}: {i.description}",
                            suggestion="根据巡查意见修正",
                        ) for i in failed_items],
                        mode="spot-fix",
                    )
                    current_content = revise_result.content
            else:
                log("  巡查通过")

        # ── 3.7 场景审核 + 心理审核（V5: 选择性触发）───────────────────────────
        if self.scene_architect and self._should_run_review("scene", ch):
            log("场景审核...")
            self._emit("review_scene", f"审查第{ch}章场景")
            try:
                scene_audit = self.scene_architect.audit_scene(
                    chapter_content=current_content,
                    chapter_number=ch,
                )
                log(f"  场景评分：{scene_audit.overall_score}/100")
            except Exception as e:
                log(f"  场景审核失败（不阻塞）：{type(e).__name__}: {e}")
                if not isinstance(e, (json.JSONDecodeError, KeyError, ValueError)):
                    log(f"  详细错误：{traceback.format_exc()[-500:]}")

        if self.psychological_expert and self._should_run_review("psychology", ch):
            log("心理审核...")
            self._emit("review_psychology", f"审查第{ch}章心理描写")
            try:
                char_names = [c.name for c in self.all_characters]
                psych_audit = self.psychological_expert.audit_psychology(
                    chapter_content=current_content,
                    chapter_number=ch,
                    characters=char_names,
                )
                log(f"  心理评分：{psych_audit.overall_score}/100")
            except Exception as e:
                log(f"  心理审核失败（不阻塞）：{type(e).__name__}: {e}")
                if not isinstance(e, (json.JSONDecodeError, KeyError, ValueError)):
                    log(f"  详细错误：{traceback.format_exc()[-500:]}")

        # ── 4. 审计 → 修订闭环（合并所有审查 Agent 的问题）────────────────────
        log("审计员审计...")
        self._emit("audit", f"9维度审计第{ch}章")
        audit_truth_ctx = self.sm.read_truth_bundle([
            TruthFileKey.CURRENT_STATE,
            TruthFileKey.CHARACTER_MATRIX,
            TruthFileKey.PENDING_HOOKS,
            TruthFileKey.EMOTIONAL_ARCS,
            TruthFileKey.CAUSAL_CHAIN,
        ])
        cross_thread_audit_ctx = self._build_cross_thread_audit_context(ws, thread_id, ch)

        audit_report = self.auditor.audit_chapter(
            chapter_content=current_content,
            chapter_number=ch,
            blueprint=blueprint,
            truth_context=audit_truth_ctx,
            settlement=writer_output.settlement,
            cross_thread_context=cross_thread_audit_ctx,
        )
        for role, fname, ctx in get_kb_queries():
            self.kb_tracker.record_query(role, fname, ctx)

        # V4 关键改动：合并审查 Agent 的问题到审计 issues
        review_issues = _collect_review_issues()
        if review_issues:
            all_issues = list(audit_report.issues) + review_issues
            # 重新判定 passed：有 review critical 也不通过
            has_review_critical = any(i.severity == "critical" for i in review_issues)
            audit_report = AuditReport(
                chapter_number=audit_report.chapter_number,
                passed=audit_report.passed and not has_review_critical,
                issues=all_issues,
                overall_note=audit_report.overall_note,
                dimension_scores=audit_report.dimension_scores,
                weighted_total=audit_report.weighted_total,
                redline_violations=audit_report.redline_violations,
            )
            log(f"  合并审查问题：+{len(review_issues)} 条（对话/场景/心理/风格）")

        # 修订循环
        while not audit_report.passed and revision_rounds < self.config.max_revise_rounds:
            revision_rounds += 1
            total_rework += 1
            log(f"修订第 {revision_rounds} 轮（累计返工{total_rework}次，{audit_report.critical_count} critical）...")
            revise_result = self.reviser.revise(
                current_content,
                audit_report.issues,
                mode="spot-fix",
            )
            current_content = revise_result.content

            # 重审
            audit_report = self.auditor.audit_chapter(
                chapter_content=current_content,
                chapter_number=ch,
                blueprint=blueprint,
                truth_context=audit_truth_ctx,
                settlement=writer_output.settlement,
                cross_thread_context=cross_thread_audit_ctx,
            )

            # V4：修订后重新跑对话/场景/心理审查，问题再次合并
            review_issues = _collect_review_issues()
            if review_issues:
                all_issues = list(audit_report.issues) + review_issues
                has_review_critical = any(i.severity == "critical" for i in review_issues)
                audit_report = AuditReport(
                    chapter_number=audit_report.chapter_number,
                    passed=audit_report.passed and not has_review_critical,
                    issues=all_issues,
                    overall_note=audit_report.overall_note,
                    dimension_scores=audit_report.dimension_scores,
                    weighted_total=audit_report.weighted_total,
                    redline_violations=audit_report.redline_violations,
                )

        # ── 4.5 风格一致性检查（V5: 选择性触发）────────────────────────────────
        if self.style_checker and self._should_run_review("style", ch):
            log("风格一致性检查...")
            try:
                recent_chapters = []
                for prev_ch in range(max(1, ch - 4), ch):
                    prev_content = self.sm.read_final(prev_ch) or self.sm.read_draft(prev_ch)
                    if prev_content:
                        recent_chapters.append({"number": prev_ch, "content": prev_content})
                recent_chapters.append({"number": ch, "content": current_content})
                if len(recent_chapters) >= 2:
                    style_check = self.style_checker.check_consistency(recent_chapters)
                    log(f"  风格一致性评分：{style_check.overall_score}/100")
                    # V4：风格不通过且还有修订余量，做最后一轮修正
                    if style_check.overall_score < self.config.style_score_floor and revision_rounds < self.config.max_revise_rounds and style_check.issues:
                        style_issues = [
                            AuditIssue(
                                dimension="风格一致",
                                severity=si.get("severity", "warning"),
                                description=si.get("description", ""),
                                suggestion=si.get("suggestion", ""),
                            )
                            for si in style_check.issues
                            if si.get("severity", "info") in ("critical", "warning")
                        ]
                        if style_issues:
                            log(f"  风格不通过，最后一轮修正（{len(style_issues)} 条）...")
                            revision_rounds += 1
                            total_rework += 1
                            revise_result = self.reviser.revise(current_content, style_issues, mode="polish")
                            current_content = revise_result.content
            except Exception as e:
                log(f"  风格检查失败（不阻塞）：{type(e).__name__}: {e}")
                if not isinstance(e, (json.JSONDecodeError, KeyError, ValueError)):
                    log(f"  详细错误：{traceback.format_exc()[-500:]}")

        # ── 5. 保存最终稿 ─────────────────────────────────────────────────────
        self.sm.save_final(ch, current_content)
        log(f"最终稿保存（{len(current_content)} 字）")
        self._emit("save_final", f"第{ch}章保存", words=len(current_content))

        # ── 6. 因果链提取 ─────────────────────────────────────────────────────
        log("提取因果链...")
        self._emit("causal_chain", f"提取第{ch}章因果链")
        causal_schemas = self.engine.extract_causal_links(
            chapter_content=current_content,
            chapter_number=ch,
            characters=self.all_characters,
        )
        for link_schema in causal_schemas:
            cl = CausalLink(
                id=link_schema.id,
                chapter=link_schema.chapter,
                cause=link_schema.cause,
                event=link_schema.event,
                consequence=link_schema.consequence,
                affected_decisions=[
                    AffectedDecision(d.character_id, d.decision)
                    for d in link_schema.affected_decisions
                ],
                triggered_events=link_schema.triggered_events,
                thread_id=thread_id,
            )
            self.sm.add_causal_link(cl)
        log(f"因果链：{len(causal_schemas)} 条")

        # ── 7. 生成章节摘要 ───────────────────────────────────────────────────
        log("生成章节摘要...")
        self._emit("summary", f"生成第{ch}章摘要")
        try:
            summary = self.summary_agent.generate_summary(
                chapter_content=current_content,
                chapter_number=ch,
                chapter_title=title,
                settlement=writer_output.settlement,
            )
            summary_md = self.summary_agent.format_for_truth_file(summary)
            self.sm.append_truth(TruthFileKey.CHAPTER_SUMMARIES, summary_md)
        except Exception as e:
            log(f"摘要生成失败：{type(e).__name__}: {e}")
            fallback = (
                f"\n## 第 {ch} 章《{title}》\n"
                f"{chapter_outline.summary}\n"
                f"- 审计：{'通过' if audit_report.passed else '未通过'}"
                f"，修订 {revision_rounds} 轮\n---\n"
            )
            self.sm.append_truth(TruthFileKey.CHAPTER_SUMMARIES, fallback)
            log(f"摘要生成失败（{e}），使用 fallback")

        # ── 8. 应用结算表到世界状态 ───────────────────────────────────────────
        log("应用结算表...")
        self._apply_settlement(ch, writer_output, blueprint)

        # ── 9. 记录时间轴事件 + 更新线程状态 ─────────────────────────────────
        log("更新时间轴和线程状态...")
        self._record_timeline_events(ch, writer_output, blueprint, thread_id, ws)

        # ── 10. 更新 current_chapter + current_state.md ───────────────────────
        ws = self.sm.read_world_state()
        ws.current_chapter = ch
        self.sm.write_world_state(ws)
        self.sm.update_current_state_md()
        log("current_state.md 已更新")

        # ── 11. 更新线程状态 + 掉线预警 ───────────────────────────────────────
        dormancy_warnings: list[str] = []
        if ws.threads:
            self.sm.update_thread_status_md()
            dormant = ws.dormant_threads(ch, threshold=self.config.dormancy_threshold)
            for t in dormant:
                gap = ch - t.last_active_chapter
                dormancy_warnings.append(f"{t.name}（{t.id}）：已 {gap} 章未活跃")
            if dormancy_warnings and verbose:
                for w in dormancy_warnings:
                    print(f"  [预警] 支线掉线：{w}")

        # ── 12. 记录质量仪表盘统计（新增） ──────────────────────────────────────
        if self.dashboard:
            log("记录质量仪表盘...")
            stats = ChapterStats(
                chapter_number=ch,
                word_count=len(current_content),
                revision_rounds=revision_rounds,
                patrol_rejected=patrol_rejected,
                total_rework=total_rework,
                weighted_score=audit_report.weighted_total,
                dimension_scores=audit_report.dimension_scores,
                redline_violations=audit_report.redline_violations,
                validation_issues={
                    i.rule: 1 for i in val_result.issues
                } if hasattr(val_result, 'issues') else {},
                timestamp="",
            )
            self.dashboard.add_chapter(stats)
            # 自动保存仪表盘数据到书籍目录
            try:
                dash_path = self.sm.book_dir / "quality_dashboard.json"
                self.dashboard.save(dash_path)
                log(f"仪表盘已保存：{dash_path}")
            except Exception as e:
                log(f"仪表盘保存失败（不阻塞）：{type(e).__name__}: {e}")

        # ── 13. 更新动态规划器进度（V3 增强）─────────────────────────────────────
        if self.dynamic_planner:
            log("更新动态规划器...")
            try:
                self.dynamic_planner.update_progress(ch)

                # V3 新增：记录审计结果，用于动态调整张力曲线
                from .dynamic_planner import ChapterAuditRecord
                audit_record = ChapterAuditRecord(
                    chapter=ch,
                    weighted_total=audit_report.weighted_total,
                    dimension_scores=audit_report.dimension_scores,
                    redline_violations=audit_report.redline_violations,
                    revision_rounds=revision_rounds,
                )
                self.dynamic_planner.record_chapter_audit(audit_record)

                # V3 新增：根据审计分数动态调整后续张力曲线
                self.dynamic_planner.adjust_tension_based_on_audit(ch)

                # 检查是否需要调整战役规划
                campaign = self.dynamic_planner.get_current_campaign(ch)
                if campaign:
                    if audit_report.weighted_total > 0 and audit_report.weighted_total < self.config.audit_tension_floor:
                        log(f"  注意：本章加权分 {audit_report.weighted_total} < {self.config.audit_tension_floor}，"
                            f"战役「{campaign.name}」已自动调整后续张力曲线")
                    if audit_report.redline_violations:
                        log(f"  ⚠ 红线触发：{audit_report.redline_violations}，后续5章张力已下调")
                    # 保存规划器状态
                    planner_path = self.sm.book_dir / "dynamic_planner.json"
                    self.dynamic_planner.save(planner_path)
            except Exception as e:
                log(f"动态规划器更新失败（不阻塞）：{type(e).__name__}: {e}")
                if not isinstance(e, (OSError, IOError)):
                    log(f"  详细错误：{traceback.format_exc()[-300:]}")

        # ── 14. 保存知识库查询统计（V4 新增）────────────────────────────────────
        if self.kb_tracker and self.kb_tracker.queries:
            log("保存知识库查询统计...")
            try:
                kb_path = self.sm.book_dir / "kb_queries.json"
                existing = []
                if kb_path.exists():
                    existing = json.loads(kb_path.read_text(encoding="utf-8"))
                existing.append({
                    "chapter": ch,
                    "queries": [
                        {"role": q.agent_role, "file": q.knowledge_file,
                         "time": q.query_time, "context": q.context}
                        for q in self.kb_tracker.queries
                    ],
                })
                kb_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
                log(f"KB查询：本章 {len(self.kb_tracker.queries)} 次")
            except Exception as e:
                log(f"KB统计保存失败（不阻塞）：{type(e).__name__}: {e}")

        # ── 15. V4：记录 Agent 能力画像 ──────────────────────────────────────
        self._record_agent_performance(
            ch=ch,
            revision_rounds=revision_rounds,
            total_rework=total_rework,
            patrol_rejected=patrol_rejected,
            audit_report=audit_report,
            dialogue_review=dialogue_review,
            scene_audit=scene_audit,
            psych_audit=psych_audit,
            style_check=style_check,
        )

        # ── 16. V4：MiroFish 读者测试（每 MIROFISH_INTERVAL 章触发）──────────
        MIROFISH_INTERVAL = self.config.mirofish_interval
        if self.mirofish_reader and self.feedback_expert and ch % MIROFISH_INTERVAL == 0:
            log(f"MiroFish 读者测试（第 {ch} 章，每{self.config.mirofish_interval}章触发）...")
            try:
                # 收集最近 N 章的内容
                test_chapters = []
                for prev_ch in range(max(1, ch - MIROFISH_INTERVAL + 1), ch + 1):
                    c = self.sm.read_final(prev_ch) or self.sm.read_draft(prev_ch)
                    if c:
                        test_chapters.append({"number": prev_ch, "content": c[:self.config.mirofish_sample_chars]})

                if test_chapters:
                    # 模拟读者测试
                    reader_report = self.mirofish_reader.simulate_reading(
                        chapters=test_chapters,
                        genre=self.writer.genre if hasattr(self.writer, 'genre') else "玄幻",
                    )
                    log(f"  MiroFish 总分：{reader_report.overall_score}/100")
                    log(f"  读者反馈：{len(reader_report.feedback_items)} 条")

                    # 路由反馈到对应 Agent
                    routed = self.feedback_expert.classify_and_route(reader_report)
                    log(f"  反馈路由：{len(routed.routed_tasks)} 个任务")

                    # 保存 MiroFish 报告
                    mirofish_path = self.sm.book_dir / f"mirofish_report_ch{ch}.json"
                    mirofish_data = {
                        "chapter": ch,
                        "overall_score": reader_report.overall_score,
                        "reader_scores": {
                            "core": reader_report.core_reader_score,
                            "normal": reader_report.normal_reader_score,
                            "casual": reader_report.casual_reader_score,
                        },
                        "feedback_count": len(reader_report.feedback_items),
                        "routed_tasks": [
                            {"target_agent": t.target_agent, "category": t.category,
                             "priority": t.priority, "description": t.description}
                            for t in routed.routed_tasks
                        ],
                    }
                    mirofish_path.write_text(
                        json.dumps(mirofish_data, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    log(f"  报告已保存：{mirofish_path}")
            except Exception as e:
                log(f"  MiroFish 测试失败（不阻塞）：{type(e).__name__}: {e}")

        return PipelineResult(
            chapter_number=ch,
            content=current_content,
            audit_report=audit_report,
            patrol_report=patrol_report,
            validation_passed=val_result.passed,
            revision_rounds=revision_rounds,
            causal_links=len(causal_schemas),
            word_count=len(current_content),
            thread_id=thread_id,
            pov_character_id=pov_character.id if pov_character else "",
            dormancy_warnings=dormancy_warnings,
            patrol_rejected=patrol_rejected,
            total_rework_count=total_rework,
        )

    def _record_agent_performance(
        self, ch, revision_rounds, total_rework, patrol_rejected,
        audit_report, dialogue_review=None, scene_audit=None,
        psych_audit=None, style_check=None,
    ):
        """V4：记录每个 Agent 的本章表现，用于能力画像"""
        try:
            perf_path = self.sm.book_dir / "agent_performance.json"
            existing = []
            if perf_path.exists():
                existing = json.loads(perf_path.read_text(encoding="utf-8"))

            record = {
                "chapter": ch,
                "revision_rounds": revision_rounds,
                "total_rework": total_rework,
                "patrol_rejected": patrol_rejected,
                "audit_passed": audit_report.passed,
                "audit_weighted_total": audit_report.weighted_total,
                "redline_violations": len(audit_report.redline_violations),
                "agent_scores": {},
            }

            if dialogue_review:
                record["agent_scores"]["dialogue_expert"] = dialogue_review.overall_score
            if scene_audit:
                record["agent_scores"]["scene_architect"] = scene_audit.overall_score
            if psych_audit:
                record["agent_scores"]["psychological_expert"] = psych_audit.overall_score
            if style_check:
                record["agent_scores"]["style_consistency"] = style_check.overall_score

            existing.append(record)
            perf_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logging.getLogger("pipeline").debug(f"Agent画像记录失败：{e}")

    # ── 多线程辅助方法 ────────────────────────────────────────────────────────

    def _build_thread_context(
        self, ws, current_thread_id: str, chapter: int,
    ) -> str:
        """构建跨线程感知上下文（供建筑师和写手使用）"""
        if not ws.threads:
            return ""

        lines = []
        for t in ws.get_active_threads():
            if t.id == current_thread_id:
                continue
            # 线程基本信息
            lines.append(
                f"- {t.name}（{t.id}）：上次活跃 Ch.{t.last_active_chapter}，"
                f"期待感 {t.hook_score}/100"
            )
            if t.end_hook:
                lines.append(f"  当前悬念：{t.end_hook}")
            if t.goal:
                lines.append(f"  目标：{t.goal}")

        if not lines:
            return ""
        return "\n".join(lines)

    def _build_cross_thread_audit_context(
        self, ws, current_thread_id: str, chapter: int,
    ) -> str:
        """构建跨线程审计上下文（供审计员检测跨线程冲突）"""
        parts = []

        # 其他线程的近期时间轴
        for t in ws.threads:
            if t.id == current_thread_id:
                continue
            thread_events = [e for e in ws.timeline if e.thread_id == t.id and e.chapter <= chapter]
            if thread_events:
                parts.append(f"### {t.name}（{t.id}）近期事件\n")
                for te in thread_events[-5:]:
                    parts.append(
                        f"- Ch.{te.chapter} {te.physical_time}：{te.character_id} 在 {te.location_id} "
                        f"做了 {te.action[:40]}"
                    )
                parts.append("")

        # 跨线程因果链
        cross_links = [cl for cl in ws.causal_chain
                       if cl.source_thread_id and cl.source_thread_id != cl.thread_id
                       and cl.thread_id == current_thread_id]
        if cross_links:
            parts.append("### 受其他线程影响的因果链\n")
            for cl in cross_links[-5:]:
                parts.append(f"- Ch.{cl.chapter}：{cl.event}（因：来自 {cl.source_thread_id} 的 {cl.cause}）")
            parts.append("")

        return "\n".join(parts)

    def _record_timeline_events(
        self,
        chapter: int,
        writer_output: WriterOutput,
        blueprint: ArchitectBlueprint,
        thread_id: str,
        ws,
    ) -> None:
        """根据结算表和蓝图记录时间轴事件"""
        time_order = float(chapter)
        counter = 0

        def _next_order():
            nonlocal counter
            counter += 1
            return time_order + counter * 0.1

        # 从角色位置变化中提取时间轴事件
        for change in writer_output.settlement.character_position_changes:
            char_id = change.get("character_id", "")
            loc_id = change.get("location_id", "")
            if char_id and loc_id:
                event = TimelineEvent(
                    id=f"te_{uuid.uuid4().hex[:8]}",
                    chapter=chapter,
                    physical_time="",
                    time_order=_next_order(),
                    character_id=char_id,
                    location_id=loc_id,
                    action=f"移动到 {loc_id}",
                    thread_id=thread_id,
                )
                self.sm.add_timeline_event(event)

        # 从情感变化中提取关键情感转折事件（仅高强度的）
        for ec in writer_output.settlement.emotional_changes:
            char_id = ec.get("character_id", "")
            intensity = int(ec.get("intensity", 0))
            emotion = ec.get("emotion", "")
            trigger = ec.get("trigger", "")
            if char_id and intensity >= 7:
                event = TimelineEvent(
                    id=f"te_{uuid.uuid4().hex[:8]}",
                    chapter=chapter,
                    physical_time="",
                    time_order=_next_order(),
                    character_id=char_id,
                    action=f"情感转折：{emotion}（强度{intensity}/10），触发：{trigger[:30]}",
                    thread_id=thread_id,
                )
                self.sm.add_timeline_event(event)

        # 从信息揭示中提取事件
        for info in writer_output.settlement.info_revealed:
            char_id = info.get("character_id", "")
            info_key = info.get("info_key", "")
            if char_id and info_key:
                event = TimelineEvent(
                    id=f"te_{uuid.uuid4().hex[:8]}",
                    chapter=chapter,
                    physical_time="",
                    time_order=_next_order(),
                    character_id=char_id,
                    action=f"得知：{info_key}",
                    thread_id=thread_id,
                )
                self.sm.add_timeline_event(event)

        # 从核心冲突中提取主线事件
        if blueprint.core_conflict:
            pov_id = blueprint.pov_character_id or self.protagonist.id
            event = TimelineEvent(
                id=f"te_{uuid.uuid4().hex[:8]}",
                chapter=chapter,
                physical_time="",
                time_order=_next_order(),
                character_id=pov_id,
                action=blueprint.core_conflict[:60],
                thread_id=thread_id,
            )
            self.sm.add_timeline_event(event)

    # ── 结算表应用 ────────────────────────────────────────────────────────────

    def _apply_settlement(
        self,
        chapter: int,
        writer_output: WriterOutput,
        blueprint: ArchitectBlueprint,
    ) -> None:
        s = writer_output.settlement

        # 角色位置变化
        for change in s.character_position_changes:
            char_id = change.get("character_id", "")
            loc_id  = change.get("location_id", "")
            if char_id and loc_id:
                self.sm.move_character(char_id, loc_id)

        # 情感变化
        for ec in s.emotional_changes:
            char_id = ec.get("character_id", "")
            if not char_id:
                continue
            snap = EmotionalSnapshot(
                character_id=char_id,
                emotion=ec.get("emotion", "未知"),
                intensity=int(ec.get("intensity", 5)),
                chapter=chapter,
                trigger=ec.get("trigger", ""),
            )
            self.sm.record_emotion(snap)
            # 更新 emotional_arcs.md
            self.sm.append_truth(
                TruthFileKey.EMOTIONAL_ARCS,
                f"- Ch.{chapter} [{char_id}] {snap.emotion}（{snap.intensity}/10）：{snap.trigger}\n",
            )

        # 关系变化（格式：「角色A-角色B：delta，原因」）
        for rel_str in s.relationship_changes:
            try:
                # 解析 "林尘-慕雪：+20，慕雪开始动摇"
                parts = rel_str.split("：", 1)
                if len(parts) == 2:
                    chars_part = parts[0].strip()
                    detail = parts[1].strip()
                    chars = chars_part.split("-", 1)
                    if len(chars) == 2:
                        char_a = chars[0].strip()
                        char_b_detail = chars[1].strip()
                        # 从 detail 提取 delta
                        import re
                        m = re.search(r'([+-]\d+)', detail)
                        delta = int(m.group(1)) if m else 0
                        reason = re.sub(r'[+-]\d+[，,]?\s*', '', detail).strip()
                        self.sm.update_relationship(char_a, char_b_detail, delta, chapter, reason)
            except Exception as e:
                logging.getLogger("pipeline").debug(f"关系变化解析跳过：{e}")

        # 新开伏笔
        for hook_desc in s.new_hooks:
            hook = Hook(
                id=f"hook_{uuid.uuid4().hex[:8]}",
                type=HookType.FORESHADOW,
                description=hook_desc,
                planted_in_chapter=chapter,
                expected_resolution_range=(chapter + 3, chapter + 25),
                status=HookStatus.OPEN,
            )
            self.sm.open_hook(hook)

        # 建筑师计划埋下的伏笔（blueprint.hooks_to_plant）
        for hook_desc in blueprint.hooks_to_plant:
            if hook_desc and hook_desc not in s.new_hooks:
                hook = Hook(
                    id=f"hook_{uuid.uuid4().hex[:8]}",
                    type=HookType.FORESHADOW,
                    description=hook_desc,
                    planted_in_chapter=chapter,
                    expected_resolution_range=(chapter + 5, chapter + 30),
                    status=HookStatus.OPEN,
                )
                self.sm.open_hook(hook)

        # 回收伏笔
        for hook_id in s.resolved_hooks:
            self.sm.resolve_hook(hook_id, chapter)

        # 信息揭示
        for info in s.info_revealed:
            char_id  = info.get("character_id", "")
            info_key = info.get("info_key", "")
            content  = info.get("content", "")
            if char_id and info_key:
                self.sm.learn_info(char_id, info_key, content, chapter, "witnessed")
                # 更新 character_matrix.md
                self.sm.append_truth(
                    TruthFileKey.CHARACTER_MATRIX,
                    f"\n- Ch.{chapter} [{char_id}] 得知：{info_key} — {content}\n",
                )

        # 资源变化写入 current_state（附加记录）
        if s.resource_changes:
            changes_str = "；".join(s.resource_changes)
            self.sm.append_truth(
                TruthFileKey.CURRENT_STATE,
                f"\n### Ch.{chapter} 资源变化\n{changes_str}\n",
            )


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _format_beats(chapter_outline: ChapterOutlineSchema) -> str:
    """将章纲节拍格式化为写手可读的场景序列"""
    lines = []
    for i, b in enumerate(chapter_outline.beats):
        fn_label = f"【{b.dramatic_function.value}】"
        line = f"节拍{i+1}{fn_label}：{b.description}"
        if b.emotional_target:
            line += f"（情感目标：{b.emotional_target}）"
        if b.target_words:
            line += f"（约 {b.target_words} 字）"
        lines.append(line)
    return "\n".join(lines) if lines else "（无节拍信息，根据章节摘要自由发挥）"


def _extract_recent_summaries(full_summaries: str, n: int = 3) -> str:
    """从 chapter_summaries.md 中提取最近 n 章的摘要"""
    if not full_summaries.strip():
        return ""
    # 按 "## 第X章" 分割
    import re
    sections = re.split(r'\n(?=## 第\d+章)', full_summaries)
    recent = [s for s in sections if s.strip().startswith("## 第")]
    if not recent:
        return ""
    return "\n".join(recent[-n:])
