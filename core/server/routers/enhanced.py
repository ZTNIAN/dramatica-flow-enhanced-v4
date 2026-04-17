"""
/enhanced V4 增强功能（角色成长/对话/情绪/MiroFish等）
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from ..deps import (
    sm, load_env, create_llm, run_sync, dc_to_dict,
    CharacterGrowthReq, DialogueReviewReq, EmotionCurveReq,
    FeedbackReq, MiroFishReq,
)

router = APIRouter(prefix="/api/books", tags=["enhanced"])


@router.post("/{{book_id}}/character-growth")
async def api_character_growth(book_id: str, req: CharacterGrowthReq | None = None):
    """角色成长弧线规划"""
    load_env()
    s = sm(book_id)
    from core.agents import CharacterGrowthExpert
    llm = create_llm()
    expert = CharacterGrowthExpert(llm)

    # 读取角色信息
    setup_dir = s.book_dir / "setup"
    characters = []
    if (setup_dir / "characters.json").exists():
        try:
            data = json.loads((setup_dir / "characters.json").read_text(encoding="utf-8"))
            characters = data.get("characters", [])
        except Exception:
            pass

    if not characters:
        raise HTTPException(400, "请先设置角色")

    try:
        if req and req.character_id:
            chars = [c for c in characters if c.get("id") == req.character_id]
            if not chars:
                raise HTTPException(404, f"角色 {req.character_id} 不存在")
            result = await run_sync(expert.plan_character_growth, chars[0],
                                     start_chapter=req.start_chapter,
                                     end_chapter=req.end_chapter or 0)
        else:
            result = await run_sync(expert.plan_character_growth, characters[0],
                                     start_chapter=1, end_chapter=0)
        return {"ok": True, "result": dc_to_dict(result)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"角色成长规划失败：{e}")


@router.post("/{{book_id}}/dialogue-review")
async def api_dialogue_review(book_id: str, req: DialogueReviewReq):
    """对话质量审查"""
    load_env()
    s = sm(book_id)
    content = s.read_final(req.chapter) or s.read_draft(req.chapter)
    if not content:
        raise HTTPException(404, f"第 {req.chapter} 章不存在")
    from core.agents import DialogueExpert
    llm = create_llm()
    expert = DialogueExpert(llm)
    try:
        result = await run_sync(expert.review_dialogue, content, focus=req.focus)
        return {"ok": True, "result": dc_to_dict(result), "chapter": req.chapter}
    except Exception as e:
        raise HTTPException(500, f"对话审查失败：{e}")


@router.post("/{{book_id}}/emotion-curve")
async def api_emotion_curve(book_id: str, req: EmotionCurveReq | None = None):
    """情绪曲线设计"""
    load_env()
    s = sm(book_id)
    from core.agents import EmotionCurveDesigner
    llm = create_llm()
    designer = EmotionCurveDesigner(llm)
    try:
        cfg = s.read_config()
        total = req.total_chapters if req and req.total_chapters else cfg.get("target_chapters", 90)
    except Exception:
        total = 90
    try:
        result = await run_sync(designer.design_emotion_curve, total)
        return {"ok": True, "result": dc_to_dict(result)}
    except Exception as e:
        raise HTTPException(500, f"情绪曲线设计失败：{e}")


@router.post("/{{book_id}}/feedback")
async def api_feedback(book_id: str, req: FeedbackReq):
    """读者反馈分类处理"""
    load_env()
    from core.agents import FeedbackExpert
    llm = create_llm()
    expert = FeedbackExpert(llm)
    try:
        result = await run_sync(expert.categorize_feedback, req.text, source=req.source)
        return {"ok": True, "result": dc_to_dict(result)}
    except Exception as e:
        raise HTTPException(500, f"反馈处理失败：{e}")


@router.post("/{{book_id}}/mirofish-test")
async def api_mirofish_test(book_id: str, req: MiroFishReq):
    """MiroFish 模拟读者测试"""
    load_env()
    s = sm(book_id)
    from core.agents import MiroFishReader
    llm = create_llm()
    reader = MiroFishReader(llm)

    # 收集指定范围的章节
    chapters = []
    end = req.end_chapter or 9999
    for ch_num in range(req.start_chapter, end + 1):
        content = s.read_final(ch_num) or s.read_draft(ch_num)
        if content:
            chapters.append({"number": ch_num, "content": content[:req.sample_count]})
    if not chapters:
        raise HTTPException(400, "没有找到可用章节")
    try:
        result = await run_sync(reader.simulate_readers, chapters, sample_count=req.sample_count)
        return {"ok": True, "result": dc_to_dict(result)}
    except Exception as e:
        raise HTTPException(500, f"MiroFish 测试失败：{e}")


# ── V5 新增：Agent 能力画像 ──────────────────────────────────────────────────

@router.get("/{{book_id}}/agent-performance")
def api_agent_performance(book_id: str):
    """获取 Agent 能力画像数据（用于 Web UI 可视化）"""
    s = sm(book_id)
    perf_path = s.book_dir / "agent_performance.json"
    if not perf_path.exists():
        return {"ok": True, "chapters": [], "agents": {}}

    try:
        data = json.loads(perf_path.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": True, "chapters": [], "agents": {}}

    # 按 agent 维度聚合，方便前端做趋势图
    agents: dict[str, list[dict]] = {}
    for record in data:
        for agent_name, score in record.get("agent_scores", {}).items():
            agents.setdefault(agent_name, []).append({
                "chapter": record["chapter"],
                "score": score,
            })

    # 汇总统计
    summary = {}
    for agent_name, points in agents.items():
        scores = [p["score"] for p in points]
        summary[agent_name] = {
            "latest": scores[-1] if scores else None,
            "average": round(sum(scores) / len(scores), 1) if scores else None,
            "min": min(scores) if scores else None,
            "max": max(scores) if scores else None,
            "trend": _calc_trend(scores),
            "count": len(scores),
        }

    return {
        "ok": True,
        "chapters": data,
        "agents": agents,
        "summary": summary,
    }


def _calc_trend(scores: list) -> str:
    """计算趋势：up / down / stable"""
    if len(scores) < 3:
        return "stable"
    recent = scores[-5:] if len(scores) >= 5 else scores
    early = scores[:len(recent)]
    avg_recent = sum(recent) / len(recent)
    avg_early = sum(early) / len(early)
    diff = avg_recent - avg_early
    if diff > 3:
        return "up"
    if diff < -3:
        return "down"
    return "stable"


@router.get("/{{book_id}}/review-stats")
def api_review_stats(book_id: str):
    """获取审查统计（V5: 选择性审查模式下的实际触发次数）"""
    s = sm(book_id)
    perf_path = s.book_dir / "agent_performance.json"
    if not perf_path.exists():
        return {"ok": True, "stats": {}}

    try:
        data = json.loads(perf_path.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": True, "stats": {}}

    total_chapters = len(data)
    agent_counts: dict[str, int] = {}
    for record in data:
        for agent_name in record.get("agent_scores", {}):
            agent_counts[agent_name] = agent_counts.get(agent_name, 0) + 1

    stats = {
        "total_chapters": total_chapters,
        "agent_triggered": agent_counts,
        "agent_trigger_rate": {
            name: round(count / total_chapters * 100, 1) if total_chapters else 0
            for name, count in agent_counts.items()
        },
    }
    return {"ok": True, "stats": stats}
