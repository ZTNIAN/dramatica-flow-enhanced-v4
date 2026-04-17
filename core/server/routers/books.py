"""
/books CRUD + 上传/导入
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Form, UploadFile

from ..deps import (
    BOOKS_DIR, PROJECT_ROOT, TEMPLATES_DIR,
    safe_book_dir, sm, load_env, create_llm, dc_to_dict,
    CreateBookReq, ExtractFromNovelReq, UpdateBookConfigReq,
)

router = APIRouter(prefix="/api/books", tags=["books"])


@router.get("")
def list_books():
    if not BOOKS_DIR.exists():
        return []
    books = []
    for d in BOOKS_DIR.iterdir():
        if not d.is_dir():
            continue
        config_path = d / "state" / "config.json"
        if config_path.exists():
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            ws_path = d / "state" / "world_state.json"
            current_ch = 0
            if ws_path.exists():
                ws = json.loads(ws_path.read_text(encoding="utf-8"))
                current_ch = ws.get("current_chapter", 0)
            has_setup = (d / "state" / "setup_state.json").exists()
            has_outline = (d / "state" / "outline.json").exists()
            has_chapters = bool(list((d / "chapters").glob("*_final.md")))
            books.append({
                **cfg,
                "current_chapter": current_ch,
                "finals": len(list((d / "chapters").glob("*_final.md"))),
                "drafts": len(list((d / "chapters").glob("*_draft.md"))),
                "stage": 4 if has_chapters else 3 if has_outline else 2 if has_setup else 1,
            })
    return books


@router.post("")
def create_book(req: CreateBookReq):
    from core.state import StateManager
    from core.types.state import BookConfig
    book_id = req.title.replace(" ", "_").replace("/", "_")[:20]
    config = BookConfig(
        id=book_id, title=req.title, genre=req.genre,
        target_words_per_chapter=req.words, target_chapters=req.chapters,
        protagonist_id="", status="planning",
        created_at=datetime.now(timezone.utc).isoformat(),
        custom_forbidden_words=[w.strip() for w in req.forbidden.split(",") if w.strip()],
        style_guide=req.style_guide,
    )
    s = StateManager(PROJECT_ROOT, book_id)
    s.init(config)
    return {"ok": True, "book_id": book_id, "title": req.title}


@router.get("/{{book_id}}")
def get_book(book_id: str):
    s = sm(book_id)
    try:
        config = s.read_config()
        ws = s.read_world_state()
    except FileNotFoundError:
        raise HTTPException(404, f"书籍不存在：{book_id}")
    from core.types.state import TruthFileKey
    hooks_md = s.read_truth(TruthFileKey.PENDING_HOOKS)
    open_hooks = hooks_md.count("| open |")
    has_setup = (s.state_dir / "setup_state.json").exists()
    has_outline = (s.state_dir / "outline.json").exists()
    has_chapters = bool(list(s.chapter_dir.glob("*_final.md")))
    return {
        **config, "current_chapter": ws.current_chapter, "open_hooks": open_hooks,
        "character_positions": ws.character_positions,
        "finals": len(list(s.chapter_dir.glob("*_final.md"))),
        "drafts": len(list(s.chapter_dir.glob("*_draft.md"))),
        "stage": 4 if has_chapters else 3 if has_outline else 2 if has_setup else 1,
    }


@router.delete("/{{book_id}}")
def delete_book(book_id: str):
    book_dir = safe_book_dir(book_id)
    if not book_dir.exists():
        raise HTTPException(404, f"书籍不存在：{book_id}")
    shutil.rmtree(book_dir, ignore_errors=True)
    return {"ok": True}


@router.post("/{{book_id}}/upload-novel")
async def upload_novel(book_id: str, text: str = Form(...), genre: str = Form("玄幻")):
    """上传本地小说文件进行导入"""
    req = ExtractFromNovelReq(text=text, genre=genre)
    # 延迟导入避免循环
    from . import ai_actions
    return await ai_actions.extract_from_novel(book_id, req)


@router.post("/{{book_id}}/import-chapters")
async def import_chapters(book_id: str, text: str = Form(...), start_chapter: int = Form(1)):
    """将上传的小说文本按章节分割导入为已有章节"""
    s = sm(book_id)
    chapters = re.split(r'第[零一二三四五六七八九十百千万\\d]+[章节回]', text)
    chapter_titles = re.findall(r'(第[零一二三四五六七八九十百千万\\d]+[章节回].*?)[\\n\\r]', text)
    imported = 0
    ch_num = start_chapter
    for i, content in enumerate(chapters):
        content = content.strip()
        if not content or len(content) < 50:
            continue
        title = chapter_titles[i] if i < len(chapter_titles) else f"第{ch_num}章"
        s.save_draft(ch_num, content)
        draft_path = s.chapter_dir / f"ch{ch_num:04d}_draft.md"
        final_path = s.chapter_dir / f"ch{ch_num:04d}_final.md"
        if draft_path.exists():
            shutil.copy2(str(draft_path), str(final_path))
        imported += 1
        ch_num += 1
    try:
        cfg = s.read_config()
        if (cfg.get("current_chapter") or 0) < ch_num - 1:
            cfg["current_chapter"] = ch_num - 1
        if cfg.get("target_chapters", 0) < ch_num - 1:
            cfg["target_chapters"] = ch_num - 1
        s._write_json("config.json", cfg)
    except Exception:
        pass
    return {"ok": True, "imported": imported, "last_chapter": ch_num - 1}


@router.put("/{{book_id}}/config")
def update_book_config(book_id: str, req: UpdateBookConfigReq):
    s = sm(book_id)
    try:
        cfg = s.read_config()
    except FileNotFoundError:
        raise HTTPException(404, f"书籍不存在：{book_id}")
    if req.style_guide:
        cfg["style_guide"] = req.style_guide
    if req.forbidden:
        cfg["custom_forbidden_words"] = [w.strip() for w in req.forbidden.split(",") if w.strip()]
    if req.protagonist_id:
        cfg["protagonist_id"] = req.protagonist_id
    if req.target_chapters is not None:
        cfg["target_chapters"] = req.target_chapters
    if req.target_words_per_chapter is not None:
        cfg["target_words_per_chapter"] = req.target_words_per_chapter
    s._write_json("config.json", cfg)
    return {"ok": True}


@router.get("/{{book_id}}/config")
def get_book_config(book_id: str):
    s = sm(book_id)
    try:
        return s.read_config()
    except FileNotFoundError:
        raise HTTPException(404, f"书籍不存在：{book_id}")
