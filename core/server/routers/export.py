"""
/export 导出
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..deps import sm, ExportRequest

router = APIRouter(tags=["export"])


@router.post("/api/action/export")
def action_export(req: ExportRequest):
    """导出完整小说"""
    s = sm(req.book_id)
    try:
        s.read_config()
    except FileNotFoundError:
        raise HTTPException(404, f"书籍不存在：{req.book_id}")

    chapters = []
    for f in sorted(s.chapter_dir.glob("ch*_final.md")):
        content = f.read_text(encoding="utf-8")
        chapters.append(content)

    if not chapters:
        # 尝试草稿
        for f in sorted(s.chapter_dir.glob("ch*_draft.md")):
            content = f.read_text(encoding="utf-8")
            chapters.append(content)

    if not chapters:
        raise HTTPException(400, "没有可导出的章节")

    if req.format == "txt":
        content = "\n\n".join(chapters)
        if req.include_outline:
            outline_path = s.state_dir / "outline.json"
            if outline_path.exists():
                outline = outline_path.read_text(encoding="utf-8")
                content = f"# 大纲\n\n{{outline}}\n\n---\n\n{{content}}"
        return {"content": content, "chapters": len(chapters), "chars": len(content)}
    elif req.format == "json":
        return {
            "chapters": [{"number": i+1, "content": c} for i, c in enumerate(chapters)],
            "total": len(chapters),
        }
    else:
        raise HTTPException(400, f"不支持的格式：{req.format}，支持 txt/json")
