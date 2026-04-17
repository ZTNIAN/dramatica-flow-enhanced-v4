"""
/setup 世界观配置
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..deps import (
    PROJECT_ROOT, TEMPLATES_DIR, safe_book_dir, sm, SaveSetupReq,
)

router = APIRouter(prefix="/api/books", tags=["setup"])


@router.get("/{{book_id}}/setup/status")
def setup_status(book_id: str):
    s = sm(book_id)
    setup_dir = s.book_dir / "setup"
    has_templates = setup_dir.exists() and any(setup_dir.glob("*.json"))
    has_setup_state = (s.state_dir / "setup_state.json").exists()
    has_outline = (s.state_dir / "outline.json").exists()
    files_status = {}
    for fname in ["characters.json", "world.json", "events.json"]:
        path = setup_dir / fname
        key = fname.replace(".json", "")
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                list_keys = {"characters": "characters", "world": "locations", "events": "events"}
                lk = list_keys.get(key, list(data.keys())[0] if data else "")
                items = data.get(lk, []) if lk else []
                files_status[key] = {"exists": True, "modified": True, "items": len(items) if isinstance(items, list) else 0}
            except Exception:
                files_status[key] = {"exists": True, "modified": False, "items": 0}
        else:
            files_status[key] = {"exists": False}
    return {"has_templates": has_templates, "has_setup_state": has_setup_state, "has_outline": has_outline, "files": files_status}


@router.post("/{{book_id}}/setup/init")
def setup_init_templates(book_id: str):
    from core.setup import SetupLoader
    loader = SetupLoader(PROJECT_ROOT, book_id)
    loader.init_templates()
    return {"ok": True}


@router.get("/{{book_id}}/setup/{{file_type}}")
def setup_read(book_id: str, file_type: str):
    s = sm(book_id)
    setup_dir = s.book_dir / "setup"
    filename_map = {"characters": "characters.json", "world": "world.json", "events": "events.json"}
    filename = filename_map.get(file_type)
    if not filename:
        raise HTTPException(400, "只支持 characters / world / events")
    path = setup_dir / filename
    if not path.exists():
        raise HTTPException(404, f"{filename} 不存在，请先初始化模板")
    tmpl_path = TEMPLATES_DIR / filename
    template_default = tmpl_path.read_text(encoding="utf-8") if tmpl_path.exists() else ""
    return {"content": path.read_text(encoding="utf-8"), "template": template_default}


@router.put("/{{book_id}}/setup/{{file_type}}")
def setup_save(book_id: str, file_type: str, req: SaveSetupReq):
    s = sm(book_id)
    setup_dir = s.book_dir / "setup"
    filename_map = {"characters": "characters.json", "world": "world.json", "events": "events.json"}
    filename = filename_map.get(file_type)
    if not filename:
        raise HTTPException(400, "只支持 characters / world / events")
    try:
        data = json.loads(req.content)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"JSON 格式错误：{e}")
    setup_dir.mkdir(parents=True, exist_ok=True)
    path = setup_dir / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "message": f"{filename} 已保存"}


@router.post("/{{book_id}}/setup/load")
def setup_load(book_id: str):
    from core.setup import SetupLoader
    try:
        loader = SetupLoader(PROJECT_ROOT, book_id)
        state = loader.load_all()
        return {
            "ok": True,
            "characters": list(state.characters.keys()),
            "locations": list(state.locations.keys()),
            "factions": list(state.factions.keys()),
            "events": len(state.seed_events),
        }
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"加载失败：{e}")
