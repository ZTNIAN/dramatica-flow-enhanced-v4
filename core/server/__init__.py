"""
Dramatica-Flow API — 模块化后端
启动：uvicorn core.server:app --reload --port 8766
"""
from __future__ import annotations

import logging
import sys
import os

# ── 依赖检查 ───────────────────────────────────────────────────────────────────
_MISSING = []
try:
    from pydantic import BaseModel
except ImportError:
    _MISSING.append("pydantic")
try:
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
except ImportError:
    _MISSING.append("fastapi")
try:
    import python_multipart  # noqa: F401
except ImportError:
    _MISSING.append("python-multipart")
try:
    import uvicorn  # noqa: F401
except ImportError:
    _MISSING.append("uvicorn")

if _MISSING:
    print("=" * 60)
    print("  [ERROR] Missing dependencies:")
    for m in _MISSING:
        print(f"    - {m}")
    print(f"  Run: pip install {' '.join(_MISSING)}")
    print("=" * 60)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', stream=sys.stdout)

# ── App 实例 ───────────────────────────────────────────────────────────────────

app = FastAPI(title="Dramatica-Flow API", version="0.5.0")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logging.info(f"--> {request.method} {request.url.path}")
    response = await call_next(request)
    logging.info(f"<-- {request.method} {request.url.path} {response.status_code}")
    return response

# ── CORS ───────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:8766,http://127.0.0.1:8766").split(","),
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

# ── 静态文件服务 ───────────────────────────────────────────────────────────────

from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_WEB_UI_PATH = _PROJECT_ROOT / "dramatica_flow_web_ui.html"
_TIMELINE_UI_PATH = _PROJECT_ROOT / "dramatica_flow_timeline.html"
_TEMPLATES_DIR = _PROJECT_ROOT / "templates"

@app.get("/")
def serve_index():
    return FileResponse(str(_WEB_UI_PATH))

@app.get("/timeline")
def serve_timeline():
    return FileResponse(str(_TIMELINE_UI_PATH))

@app.get("/templates/{filename}")
def serve_template(filename: str):
    from fastapi import HTTPException
    allowed = {"novel_extract_prompt.md", "outline_import_template.md"}
    filepath = _TEMPLATES_DIR / filename
    if filename not in allowed or not filepath.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(str(filepath), media_type="text/markdown; charset=utf-8")

# ── WebSocket 进度推送（V5 新增）─────────────────────────────────────────────

class WSProgressManager:
    """管理 WebSocket 连接，按 book_id 分组推送进度"""
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, book_id: str, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(book_id, []).append(ws)

    def disconnect(self, book_id: str, ws: WebSocket):
        conns = self._connections.get(book_id)
        if conns and ws in conns:
            conns.remove(ws)

    async def broadcast(self, book_id: str, data: dict):
        conns = self._connections.get(book_id, [])
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            conns.remove(ws)

ws_manager = WSProgressManager()

@app.websocket("/ws/progress/{book_id}")
async def ws_progress(websocket: WebSocket, book_id: str):
    await ws_manager.connect(book_id, websocket)
    try:
        while True:
            # 保持连接，接收心跳
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(book_id, websocket)

# ── 注册 Routers ──────────────────────────────────────────────────────────────

from .routers import (
    books, setup, chapters, outline, writing,
    ai_actions, threads, analysis, enhanced,
    settings, export,
)

app.include_router(books.router)
app.include_router(setup.router)
app.include_router(chapters.router)
app.include_router(outline.router)
app.include_router(writing.router)
app.include_router(ai_actions.router)
app.include_router(threads.router)
app.include_router(analysis.router)
app.include_router(enhanced.router)
app.include_router(settings.router)
app.include_router(export.router)
