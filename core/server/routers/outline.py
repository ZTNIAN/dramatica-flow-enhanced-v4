"""
/outline 大纲管理
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from ..deps import (
    sm, normalize_outline, DF_MAP,
    SaveOutlineReq, SaveChapterOutlinesReq, ImportOutlineReq, ImportChapterOutlinesReq,
)

router = APIRouter(prefix="/api/books", tags=["outline"])


@router.get("/{{book_id}}/outline")
def get_outline(book_id: str):
    s = sm(book_id)
    outline_path = s.state_dir / "outline.json"
    if not outline_path.exists():
        raise HTTPException(404, "大纲尚未生成")
    return json.loads(outline_path.read_text(encoding="utf-8"))


@router.get("/{{book_id}}/chapter-outlines")
def get_chapter_outlines(book_id: str):
    s = sm(book_id)
    path = s.state_dir / "chapter_outlines.json"
    if not path.exists():
        raise HTTPException(404, "章纲尚未生成")
    return json.loads(path.read_text(encoding="utf-8"))


@router.put("/{{book_id}}/outline")
def save_outline(book_id: str, req: SaveOutlineReq):
    s = sm(book_id)
    outline_path = s.state_dir / "outline.json"
    outline_path.write_text(json.dumps(req.outline, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "message": "大纲已保存"}


@router.put("/{{book_id}}/chapter-outlines")
def save_chapter_outlines(book_id: str, req: SaveChapterOutlinesReq):
    s = sm(book_id)
    path = s.state_dir / "chapter_outlines.json"
    path.write_text(json.dumps(req.outlines, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "message": f"已保存 {len(req.outlines)} 章章纲"}


@router.post("/{{book_id}}/import/outline")
def import_outline(book_id: str, req: ImportOutlineReq):
    s = sm(book_id)
    raw = req.outline
    if not raw.get("sequences"):
        raise HTTPException(400, "大纲缺少 sequences 数组")
    if not isinstance(raw["sequences"], list):
        raise HTTPException(400, "sequences 必须是数组")
    try:
        raw = normalize_outline(raw, s)
    except Exception as e:
        raise HTTPException(400, f"大纲规范化失败：{e}")
    try:
        from core.narrative import StoryOutlineSchema
        StoryOutlineSchema.model_validate_json(json.dumps(raw, ensure_ascii=False))
    except Exception as e:
        logging.warning(f"大纲 Pydantic 验证警告：{e}")
    outline_path = s.state_dir / "outline.json"
    outline_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        cfg = s.read_config()
        total = sum(x.get("estimated_scenes", 0) for x in raw.get("sequences", []))
        if total > 0:
            cfg["target_chapters"] = total
            s._write_json("config.json", cfg)
    except Exception:
        pass
    seq_count = len(raw.get("sequences", []))
    total_ch = sum(x.get("estimated_scenes", 0) for x in raw.get("sequences", []))
    return {"ok": True, "message": f"大纲导入成功：{seq_count} 个序列，共 {total_ch} 章",
            "sequences": seq_count, "total_chapters": total_ch}


@router.post("/{{book_id}}/import/chapter-outlines")
def import_chapter_outlines(book_id: str, req: ImportChapterOutlinesReq):
    s = sm(book_id)
    if not req.outlines or not isinstance(req.outlines, list):
        raise HTTPException(400, "章纲数据为空或格式错误")
    if len(req.outlines) > 500:
        raise HTTPException(400, f"单次导入上限 500 章，当前 {len(req.outlines)} 章，请分批导入")

    for i, co in enumerate(req.outlines):
        if not isinstance(co, dict):
            continue
        if "chapter_number" not in co and "chapter" in co:
            co["chapter_number"] = co.pop("chapter")
        if "chapter_number" not in co:
            co["chapter_number"] = i + 1
        co.setdefault("title", f"第{{co['chapter_number']}}章")
        co.setdefault("summary", "")
        co.setdefault("sequence_id", "")
        co.setdefault("beats", [])
        co.setdefault("emotional_arc", {{"start": "平静", "end": "紧张"}})
        co.setdefault("mandatory_tasks", [])
        co.setdefault("target_words", 4000)
        for key in ("chapter_number", "target_words"):
            if key in co and isinstance(co[key], float):
                co[key] = int(co[key])
        for bi, beat in enumerate(co.get("beats", [])):
            if not isinstance(beat, dict):
                continue
            if not beat.get("id"):
                beat["id"] = f"beat_{{co['chapter_number']}}_{{bi+1}}"
            df = beat.get("dramatic_function", "transition")
            beat["dramatic_function"] = DF_MAP.get(df, df)
        if not co.get("beats"):
            co["beats"] = [{{
                "id": f"beat_{{co['chapter_number']}}_1",
                "description": "情节推进",
                "dramatic_function": "transition",
            }}]

    co_path = s.state_dir / "chapter_outlines.json"
    if req.merge and co_path.exists():
        all_cos = json.loads(co_path.read_text(encoding="utf-8"))
        if not isinstance(all_cos, list):
            all_cos = []
        max_ch = max((c.get("chapter_number", 0) for c in all_cos), default=0)
        for ci, co in enumerate(req.outlines):
            co["chapter_number"] = max_ch + ci + 1
            for bi, beat in enumerate(co.get("beats", [])):
                beat["id"] = f"beat_{{co['chapter_number']}}_{{bi+1}}"
        all_cos.extend(req.outlines)
    else:
        all_cos = req.outlines
        for i, co in enumerate(all_cos):
            co["chapter_number"] = i + 1
            for bi, beat in enumerate(co.get("beats", [])):
                beat["id"] = f"beat_{{co['chapter_number']}}_{{bi+1}}"

    co_path.write_text(json.dumps(all_cos, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        cfg = s.read_config()
        if len(all_cos) > (cfg.get("target_chapters") or 0):
            cfg["target_chapters"] = len(all_cos)
            s._write_json("config.json", cfg)
    except Exception:
        pass
    return {"ok": True, "message": f"导入 {{len(all_cos)}} 章章纲", "total": len(all_cos)}
