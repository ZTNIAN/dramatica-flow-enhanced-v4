"""
/analysis 因果链/情感弧/钩子/关系
"""
from __future__ import annotations

import dataclasses
from fastapi import APIRouter, HTTPException

from ..deps import sm, dc_to_dict

router = APIRouter(prefix="/api/books", tags=["analysis"])


@router.get("/{{book_id}}/causal-chain")
def get_causal_chain(book_id: str):
    s = sm(book_id)
    ws = s.read_world_state()
    return dc_to_dict(ws.causal_chain)


@router.get("/{{book_id}}/emotional-arcs")
def get_emotional_arcs(book_id: str):
    s = sm(book_id)
    ws = s.read_world_state()
    arcs: dict[str, list] = {}
    for snap in ws.emotional_snapshots:
        arcs.setdefault(snap.character_id, []).append(dc_to_dict(snap))
    return arcs


@router.get("/{{book_id}}/hooks")
def get_hooks(book_id: str, status: str | None = None):
    s = sm(book_id)
    ws = s.read_world_state()
    hooks = dc_to_dict(ws.pending_hooks)
    if status:
        hooks = [h for h in hooks if h.get("status") == status]
    return hooks


@router.post("/{{book_id}}/hooks/{{hook_id}}/resolve")
def resolve_hook_api(book_id: str, hook_id: str, body: dict | None = None):
    s = sm(book_id)
    chapter = (body or {}).get("chapter")
    if not chapter:
        chapter = s.read_world_state().current_chapter or 0
    s.resolve_hook(hook_id, int(chapter))
    s.update_current_state_md()
    return {"ok": True, "hook_id": hook_id, "resolved_in_chapter": int(chapter)}


@router.post("/{{book_id}}/hooks/{{hook_id}}/reopen")
def reopen_hook_api(book_id: str, hook_id: str):
    from core.types.state import HookStatus
    s = sm(book_id)
    ws = s.read_world_state()
    for hook in ws.pending_hooks:
        if hook.id == hook_id:
            hook.status = HookStatus.OPEN
            hook.resolved_in_chapter = None
            break
    s.write_world_state(ws)
    s.update_current_state_md()
    return {"ok": True, "hook_id": hook_id}


@router.get("/{{book_id}}/relationships")
def get_relationships(book_id: str):
    s = sm(book_id)
    ws = s.read_world_state()
    return dc_to_dict(ws.relationships)


@router.get("/{{book_id}}/quality-dashboard")
def api_quality_dashboard(book_id: str):
    s = sm(book_id)
    from core.quality_dashboard import QualityDashboard
    dashboard = QualityDashboard(s)
    return dashboard.get_summary()


@router.get("/{{book_id}}/kb-queries")
def api_kb_queries(book_id: str):
    from core.agents import get_kb_queries
    queries = get_kb_queries()
    return {"queries": [{{"agent": q[0], "file": q[1], "context": q[2]}} for q in queries]}
