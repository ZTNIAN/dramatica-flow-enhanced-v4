"""
/chapters 章节管理
"""
from __future__ import annotations

import json
from fastapi import APIRouter, HTTPException

from ..deps import sm

router = APIRouter(prefix="/api/books", tags=["chapters"])


@router.get("/{{book_id}}/chapters")
def list_chapters(book_id: str):
    s = sm(book_id)
    chapters = []
    for f in sorted(s.chapter_dir.glob("ch*.md")):
        stem = f.stem
        parts = stem.split("_")
        num = int(parts[0].replace("ch", ""))
        kind = parts[1] if len(parts) > 1 else "draft"
        chapters.append({
            "number": num, "kind": kind,
            "chars": len(f.read_text(encoding="utf-8")),
            "filename": f.name,
        })
    return chapters


@router.post("/{{book_id}}/chapters/{{chapter}}/promote")
def promote_chapter(book_id: str, chapter: int):
    s = sm(book_id)
    draft = s.read_draft(chapter)
    if not draft:
        raise HTTPException(404, f"第 {chapter} 章草稿不存在")
    s.save_final(chapter, draft)
    try:
        cfg = s.read_config()
        if (cfg.get("current_chapter") or 0) < chapter:
            cfg["current_chapter"] = chapter
            s._write_json("config.json", cfg)
    except Exception:
        pass
    return {"ok": True, "message": f"第 {chapter} 章已升级为最终稿"}


@router.get("/{{book_id}}/chapters/{{chapter}}")
def get_chapter(book_id: str, chapter: int):
    s = sm(book_id)
    content = s.read_final(chapter) or s.read_draft(chapter)
    if not content:
        raise HTTPException(404, f"第 {chapter} 章不存在")
    kind = "final" if (s.chapter_dir / f"ch{chapter:04d}_final.md").exists() else "draft"
    return {"number": chapter, "kind": kind, "content": content, "chars": len(content)}


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


@router.get("/{{book_id}}/hook-designs")
def api_hook_designs(book_id: str):
    s = sm(book_id)
    outline_path = s.state_dir / "outline.json"
    if not outline_path.exists():
        return {"hooks": []}
    outline = json.loads(outline_path.read_text(encoding="utf-8"))
    hooks = []
    for seq in outline.get("sequences", []):
        for beat in seq.get("beats", []):
            if beat.get("hook_type"):
                hooks.append(beat)
    return {"hooks": hooks}
