"""
/threads 线程管理
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..deps import sm, dc_to_dict, CreateThreadReq, UpdateThreadReq

router = APIRouter(prefix="/api/books", tags=["threads"])


@router.get("/{{book_id}}/threads")
def get_threads(book_id: str):
    s = sm(book_id)
    ws = s.read_world_state()
    return dc_to_dict(ws.threads)


@router.post("/{{book_id}}/threads")
def create_thread_api(book_id: str, req: CreateThreadReq):
    from core.types.narrative import NarrativeThread, ThreadType
    s = sm(book_id)
    thread = NarrativeThread(
        id=req.id, name=req.name, type=ThreadType(req.type),
        pov_character_id=req.pov_character_id, character_ids=req.character_ids,
        goal=req.goal, growth_arc=req.growth_arc, start_chapter=req.start_chapter,
        weight=req.weight, merge_chapter=req.merge_chapter, end_hook=req.end_hook,
    )
    s.create_thread(thread)
    s.update_thread_status_md()
    return {"ok": True, "thread_id": req.id}


@router.put("/{{book_id}}/threads/{{thread_id}}")
def update_thread_api(book_id: str, thread_id: str, req: UpdateThreadReq):
    s = sm(book_id)
    kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
    if kwargs:
        s.update_thread(thread_id, **kwargs)
        s.update_thread_status_md()
    return {"ok": True}


@router.delete("/{{book_id}}/threads/{{thread_id}}")
def delete_thread_api(book_id: str, thread_id: str):
    s = sm(book_id)
    s.delete_thread(thread_id)
    s.update_thread_status_md()
    return {"ok": True}


@router.get("/{{book_id}}/threads/status")
def get_thread_status(book_id: str):
    s = sm(book_id)
    ws = s.read_world_state()
    return {
        "current_chapter": ws.current_chapter,
        "threads": dc_to_dict(ws.threads),
        "dormant": dc_to_dict(ws.dormant_threads(ws.current_chapter, threshold=5)),
        "timeline": dc_to_dict(ws.timeline[-30:]),
        "thread_chapter_map": ws.thread_chapter_map(),
        "cross_thread_causal_links": dc_to_dict(s.get_cross_thread_causal_links()),
    }


@router.get("/{{book_id}}/timeline")
def get_timeline(book_id: str, thread_id: str | None = None, character_id: str | None = None,
                 from_chapter: int | None = None, to_chapter: int | None = None):
    s = sm(book_id)
    if thread_id:
        events = s.get_thread_timeline(thread_id)
    elif character_id:
        events = s.get_character_timeline(character_id)
    else:
        ws = s.read_world_state()
        events = ws.timeline
    if from_chapter is not None:
        events = [e for e in events if (e.chapter if hasattr(e, 'chapter') else e.get('chapter', 0)) >= from_chapter]
    if to_chapter is not None:
        events = [e for e in events if (e.chapter if hasattr(e, 'chapter') else e.get('chapter', 0)) <= to_chapter]
    return dc_to_dict(events)
