"""
/writing 写作+审计+修订
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from ..deps import (
    sm, load_env, create_llm, run_sync, dc_to_dict,
    ContinueWritingReq, SegmentRewriteReq, ThreeLayerAuditReq,
)

router = APIRouter(prefix="/api/books", tags=["writing"])


@router.post("/{{book_id}}/continue-writing")
async def continue_writing(book_id: str, req: ContinueWritingReq):
    """续写指定数量的章节"""
    load_env()
    s = sm(book_id)
    try:
        cfg = s.read_config()
    except FileNotFoundError:
        raise HTTPException(404, f"书籍不存在：{book_id}")

    from core.pipeline import Pipeline, PipelineConfig
    llm = create_llm()
    pipeline = Pipeline(llm, book_id, PROJECT_ROOT=str((sm.__module__ and __import__('pathlib').Path(__file__).resolve().parent.parent.parent) or ""))
    # Use PROJECT_ROOT directly
    from pathlib import Path as _P
    pipeline = Pipeline(llm, book_id, PROJECT_ROOT=str(_P(__file__).resolve().parent.parent.parent))
    config = PipelineConfig(
        style_guide=cfg.get("style_guide", ""),
        genre=cfg.get("genre", "玄幻"),
        forbidden_words=cfg.get("custom_forbidden_words", []),
        max_revise_rounds=3,
    )

    results = []
    for i in range(req.count):
        try:
            ws = s.read_world_state()
            ch = (ws.current_chapter or 0) + 1
        except Exception:
            ch = 1
        try:
            result = await run_sync(pipeline.write_chapter, ch, config)
            results.append(dc_to_dict(result) if hasattr(result, '__dataclass_fields__') else result)
        except Exception as e:
            logging.error(f"续写第 {ch} 章失败: {e}", exc_info=True)
            results.append({"chapter": ch, "error": str(e)})

    return {"ok": True, "results": results}


@router.post("/{{book_id}}/three-layer-audit")
async def three_layer_audit(book_id: str, req: ThreeLayerAuditReq):
    """三层审计"""
    load_env()
    s = sm(book_id)
    from core.agents import AuditorAgent, ArchitectBlueprint, PreWriteChecklist, PostWriteSettlement
    llm = create_llm()
    auditor = AuditorAgent(llm)
    content = s.read_final(req.chapter) or s.read_draft(req.chapter)
    if not content:
        raise HTTPException(404, f"第 {{req.chapter}} 章不存在")

    try:
        cfg = s.read_config()
        genre = cfg.get("genre", "玄幻")
    except Exception:
        genre = "玄幻"

    from core.narrative import ChapterOutlineSchema
    outline_path = s.state_dir / "chapter_outlines.json"
    chapter_outline = None
    if outline_path.exists():
        outlines = json.loads(outline_path.read_text(encoding="utf-8"))
        for co in outlines:
            if co.get("chapter_number") == req.chapter:
                try:
                    chapter_outline = ChapterOutlineSchema.model_validate(co)
                except Exception:
                    pass
                break

    try:
        report = await run_sync(auditor.audit_chapter, content, chapter_outline, genre, req.mode)
        return {"ok": True, "report": dc_to_dict(report), "chapter": req.chapter}
    except Exception as e:
        raise HTTPException(500, f"审计失败：{e}")


@router.post("/api/action/revise")
def action_revise(book_id: str, chapter: int, mode: str = "spot-fix"):
    """手动触发修订"""
    load_env()
    s = sm(book_id)
    from core.agents import ReviserAgent
    llm = create_llm()
    reviser = ReviserAgent(llm)
    content = s.read_final(chapter) or s.read_draft(chapter)
    if not content:
        raise HTTPException(404, f"第 {chapter} 章不存在")
    try:
        result = reviser.revise(content, [], genre="玄幻")
        s.save_draft(chapter, result.content)
        return {"ok": True, "changes": result.changes_summary}
    except Exception as e:
        raise HTTPException(500, f"修订失败：{e}")


@router.get("/{{book_id}}/audit-results/{{chapter}}")
def get_audit_result(book_id: str, chapter: int):
    s = sm(book_id)
    path = s.state_dir / "audits" / f"audit_ch{chapter:04d}.json"
    if not path.exists():
        raise HTTPException(404, f"第 {chapter} 章审计结果不存在")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/{{book_id}}/audit-results")
def list_audit_results(book_id: str):
    s = sm(book_id)
    audit_dir = s.state_dir / "audits"
    if not audit_dir.exists():
        return []
    results = []
    for f in sorted(audit_dir.glob("audit_ch*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append(data)
        except Exception:
            pass
    return results


@router.post("/{{book_id}}/ai-rewrite-segment")
async def ai_rewrite_segment(book_id: str, req: SegmentRewriteReq):
    """AI 重写指定段落"""
    load_env()
    s = sm(book_id)
    content = s.read_final(req.chapter) or s.read_draft(req.chapter)
    if not content:
        raise HTTPException(404, f"第 {req.chapter} 章不存在")

    lines = content.split("\n")
    start = max(0, req.start_line - 1)
    end = min(len(lines), req.end_line)
    segment = "\n".join(lines[start:end])
    if not segment.strip():
        raise HTTPException(400, "选中段落为空")

    from core.agents import ReviserAgent
    llm = create_llm()
    reviser = ReviserAgent(llm)
    try:
        result = await run_sync(reviser.revise, segment, [], genre="玄幻")
        new_lines = lines[:start] + result.content.split("\n") + lines[end:]
        new_content = "\n".join(new_lines)
        s.save_draft(req.chapter, new_content)
        return {"ok": True, "old_segment": segment, "new_segment": result.content, "changes": result.changes_summary}
    except Exception as e:
        raise HTTPException(500, f"重写失败：{e}")


@router.put("/{{book_id}}/chapters/{{chapter}}/content")
def update_chapter_content(book_id: str, chapter: int, req: dict):
    content = req.get("content", "")
    kind = req.get("kind", "draft")
    if not content:
        raise HTTPException(400, "内容不能为空")
    s = sm(book_id)
    s.save_draft(chapter, content)
    if kind == "final":
        s.save_final(chapter, content)
    return {"ok": True, "chars": len(content)}


@router.post("/api/action/write")
async def action_write(book_id: str, count: int = 1):
    """CLI 兼容：触发写作（异步，不阻塞事件循环）"""
    import asyncio
    load_env()
    s = sm(book_id)
    from core.pipeline import Pipeline
    from pathlib import Path as _P
    llm = create_llm()
    pipeline = Pipeline(llm, book_id, PROJECT_ROOT=str(_P(__file__).resolve().parent.parent.parent))

    def _write_sync():
        results = []
        for i in range(count):
            try:
                ws = s.read_world_state()
                ch = (ws.current_chapter or 0) + 1
            except Exception:
                ch = 1
            try:
                result = pipeline.write_chapter(ch)
                results.append({"chapter": ch, "ok": True})
            except Exception as e:
                results.append({"chapter": ch, "error": str(e)})
        return results

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, _write_sync)
    return {"ok": True, "results": results}


@router.post("/api/action/audit")
async def action_audit(book_id: str, chapter: int):
    """CLI 兼容：触发审计（异步，不阻塞事件循环）"""
    import asyncio
    load_env()
    s = sm(book_id)
    from core.agents import AuditorAgent
    llm = create_llm()
    auditor = AuditorAgent(llm)
    content = s.read_final(chapter) or s.read_draft(chapter)
    if not content:
        raise HTTPException(404, f"第 {chapter} 章不存在")

    def _audit_sync():
        return auditor.audit_chapter(content, None, "玄幻", "full")

    try:
        loop = asyncio.get_event_loop()
        report = await loop.run_in_executor(None, _audit_sync)
        return {"ok": True, "issues": len(report.issues), "score": report.score}
    except Exception as e:
        raise HTTPException(500, f"审计失败：{e}")
