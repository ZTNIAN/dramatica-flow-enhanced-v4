"""
/ai-actions AI 生成/提取
"""
from __future__ import annotations

import json
import logging
import re

from fastapi import APIRouter, HTTPException

from ..deps import (
    sm, load_env, create_llm, run_sync, dc_to_dict, DF_MAP,
    AiGenerateSetupReq, ExtractFromNovelReq, AiGenerateOutlineReq,
    AiContinueOutlineReq, DetailedOutlineReq, ChapterContentReq,
    ExtractStoryStateReq,
)

router = APIRouter(prefix="/api/books", tags=["ai-actions"])


@router.post("/{{book_id}}/ai-generate/setup")
async def ai_generate_setup(book_id: str, req: AiGenerateSetupReq):
    """AI 自动生成世界观设定"""
    load_env()
    s = sm(book_id)
    llm = create_llm()
    from core.llm import LLMMessage
    prompt = f"""你是一位专业的小说世界观构建师。请为以下小说生成完整的角色、世界和事件设定。

题材：{req.genre}
书名：{req.book_title}
{f'核心想法：{req.idea}' if req.idea else ''}

请返回 JSON 格式，包含：
1. characters: 角色数组（每个包含 id, name, role, personality, backstory, goals, relationships）
2. locations: 地点数组（每个包含 id, name, description, significance）
3. events: 种子事件数组（每个包含 id, description, chapter_hint, impact）

风格：{req.style}
返回纯 JSON，不要 markdown 代码块。"""
    try:
        resp = await run_sync(llm.chat, [LLMMessage(role="user", content=prompt)])
        from core.llm import parse_llm_json
        data = parse_llm_json(resp.content)
        setup_dir = s.book_dir / "setup"
        setup_dir.mkdir(parents=True, exist_ok=True)
        if "characters" in data:
            chars = {{"characters": data["characters"]}}
            (setup_dir / "characters.json").write_text(json.dumps(chars, ensure_ascii=False, indent=2), encoding="utf-8")
        if "locations" in data:
            world = {{"locations": data["locations"], "power_system": data.get("power_system", "")}}
            (setup_dir / "world.json").write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
        if "events" in data:
            evts = {{"events": data["events"]}}
            (setup_dir / "events.json").write_text(json.dumps(evts, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "data": data}
    except Exception as e:
        raise HTTPException(500, f"AI 生成设定失败：{e}")


@router.post("/{{book_id}}/extract-from-novel")
async def extract_from_novel(book_id: str, req: ExtractFromNovelReq):
    """从已有小说文本中提取角色和世界观设定"""
    load_env()
    s = sm(book_id)
    llm = create_llm()
    from core.llm import LLMMessage
    text_preview = req.text[:8000]
    prompt = f"""你是一位专业的小说分析师。请从以下小说文本中提取角色和世界观设定。

题材：{req.genre}

小说文本（节选）：
{text_preview}

请返回 JSON 格式：
1. characters: 提取的角色（每个包含 id, name, role, personality, relationships）
2. locations: 提取的地点
3. world_rules: 发现的世界规则/设定
4. plot_summary: 情节概述

返回纯 JSON。"""
    try:
        resp = await run_sync(llm.chat, [LLMMessage(role="user", content=prompt)])
        from core.llm import parse_llm_json
        data = parse_llm_json(resp.content)
        return {"ok": True, "extracted": data}
    except Exception as e:
        raise HTTPException(500, f"提取失败：{e}")


@router.post("/{{book_id}}/extract-story-state")
async def extract_story_state(book_id: str, req: ExtractStoryStateReq):
    """从小说文本中提取完整故事状态（角色位置/情感/因果链等）"""
    load_env()
    s = sm(book_id)
    llm = create_llm()
    from core.llm import LLMMessage
    text_preview = req.text[:12000]
    prompt = f"""你是一位资深小说分析师。请从小说文本中提取完整的故事状态信息。

小说文本：
{text_preview}

请返回 JSON 格式：
1. characters: 角色详细信息（含当前位置、情感状态、关系变化）
2. plot_progression: 情节推进节点
3. causal_chain: 因果链（事件A导致事件B）
4. emotional_states: 角色情感变化轨迹
5. pending_hooks: 未回收的伏笔
6. world_state: 当前世界观状态

返回纯 JSON。"""
    try:
        resp = await run_sync(llm.chat, [LLMMessage(role="user", content=prompt)])
        from core.llm import parse_llm_json
        data = parse_llm_json(resp.content)
        return {"ok": True, "state": data}
    except Exception as e:
        raise HTTPException(500, f"提取故事状态失败：{e}")


@router.post("/{{book_id}}/extract-story-state/batch")
async def extract_story_state_batch(book_id: str):
    """批量提取故事状态（从所有已写章节）"""
    load_env()
    s = sm(book_id)
    chapters = []
    for f in sorted(s.chapter_dir.glob("ch*_final.md")):
        content = f.read_text(encoding="utf-8")
        chapters.append(content)
    if not chapters:
        raise HTTPException(404, "没有已写章节")

    llm = create_llm()
    from core.llm import LLMMessage
    all_states = []
    for i, ch_content in enumerate(chapters):
        try:
            prompt = f"""从第{i+1}章文本中提取关键信息：
- 出场角色及其状态
- 关键事件和因果关系
- 情感变化
- 伏笔

文本：{ch_content[:5000]}
返回 JSON。"""
            resp = await run_sync(llm.chat, [LLMMessage(role="user", content=prompt)])
            from core.llm import parse_llm_json
            state = parse_llm_json(resp.content)
            state["chapter"] = i + 1
            all_states.append(state)
        except Exception as e:
            logging.warning(f"提取第{i+1}章状态失败: {e}")
            continue
    return {"ok": True, "chapters_processed": len(all_states), "states": all_states}


@router.post("/{{book_id}}/ai-generate/outline")
async def ai_generate_outline(book_id: str, req: AiGenerateOutlineReq):
    """AI 生成故事大纲"""
    load_env()
    s = sm(book_id)
    try:
        cfg = s.read_config()
        genre = cfg.get("genre", "玄幻")
        title = cfg.get("title", "")
        target_ch = cfg.get("target_chapters", 90)
    except Exception:
        genre, title, target_ch = "玄幻", "", 90

    llm = create_llm()
    from core.llm import LLMMessage
    idea_text = f"用户想法：{req.idea}\n" if req.idea else ""
    prompt = f"""你是一位专业的小说大纲规划师。请为以下小说生成完整的故事大纲。

题材：{genre}
书名：{title}
目标章数：{target_ch}
{idea_text}

请生成包含 6-10 个序列（sequence）的大纲，每个序列包含：
- id: 序列标识
- title: 序列标题
- dramatic_function: setup/inciting/turning/midpoint/crisis/climax/reveal/decision/consequence/transition
- summary: 序列概述
- narrative_goal: 叙事目标
- estimated_scenes: 预估场景数（整数）
- key_events: 关键事件列表

返回 JSON：{{"sequences": [...]}}"""
    try:
        resp = await run_sync(llm.chat, [LLMMessage(role="user", content=prompt)])
        from core.llm import parse_llm_json
        data = parse_llm_json(resp.content)
        if "sequences" in data:
            from ..deps import normalize_outline
            data = normalize_outline(data, s)
        return {"ok": True, "outline": data}
    except Exception as e:
        raise HTTPException(500, f"AI 生成大纲失败：{e}")


@router.post("/{{book_id}}/ai-continue/outline")
async def ai_continue_outline(book_id: str, req: AiContinueOutlineReq):
    """AI 续写大纲（追加序列）"""
    load_env()
    s = sm(book_id)
    outline_path = s.state_dir / "outline.json"
    if not outline_path.exists():
        raise HTTPException(404, "大纲不存在，请先生成")
    existing = json.loads(outline_path.read_text(encoding="utf-8"))
    existing_seqs = existing.get("sequences", [])
    last_summary = existing_seqs[-1].get("summary", "") if existing_seqs else ""

    llm = create_llm()
    from core.llm import LLMMessage
    prompt = f"""续写故事大纲。已有 {len(existing_seqs)} 个序列，最后序列：{last_summary}
请追加 {req.extra_sequences} 个新序列。
{f'想法：{req.idea}' if req.idea else ''}
返回 JSON：{{"sequences": [...]}}"""
    try:
        resp = await run_sync(llm.chat, [LLMMessage(role="user", content=prompt)])
        from core.llm import parse_llm_json
        new_seqs = parse_llm_json(resp.content)
        if "sequences" in new_seqs:
            existing["sequences"].extend(new_seqs["sequences"])
        else:
            existing["sequences"].extend(new_seqs if isinstance(new_seqs, list) else [])
        from ..deps import normalize_outline
        existing = normalize_outline(existing, s)
        return {"ok": True, "outline": existing, "added": req.extra_sequences}
    except Exception as e:
        raise HTTPException(500, f"续写大纲失败：{e}")


@router.post("/{{book_id}}/ai-generate/chapter-outlines")
async def ai_generate_chapter_outlines(book_id: str):
    """AI 根据大纲生成章纲"""
    load_env()
    s = sm(book_id)
    outline_path = s.state_dir / "outline.json"
    if not outline_path.exists():
        raise HTTPException(404, "大纲不存在")
    outline = json.loads(outline_path.read_text(encoding="utf-8"))

    llm = create_llm()
    from core.llm import LLMMessage
    prompt = f"""根据以下故事大纲，生成详细的章纲。

大纲：{json.dumps(outline, ensure_ascii=False)[:4000]}

每个章纲包含：
- chapter_number: 章号
- title: 章标题
- summary: 章节概述
- beats: 情节节拍数组（每个含 id, description, dramatic_function）
- emotional_arc: {{"start": "起始情绪", "end": "结束情绪"}}
- target_words: 目标字数

返回 JSON 数组。"""
    try:
        resp = await run_sync(llm.chat, [LLMMessage(role="user", content=prompt)])
        from core.llm import parse_llm_json
        data = parse_llm_json(resp.content)
        outlines = data if isinstance(data, list) else data.get("outlines", data.get("chapters", []))
        co_path = s.state_dir / "chapter_outlines.json"
        co_path.write_text(json.dumps(outlines, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "outlines": outlines, "count": len(outlines)}
    except Exception as e:
        raise HTTPException(500, f"生成章纲失败：{e}")


@router.post("/{{book_id}}/ai-generate/detailed-outline")
async def ai_generate_detailed_outline(book_id: str, req: DetailedOutlineReq):
    """AI 生成某章的详细大纲"""
    load_env()
    s = sm(book_id)
    try:
        cfg = s.read_config()
        genre = cfg.get("genre", "玄幻")
    except Exception:
        genre = "玄幻"
    llm = create_llm()
    from core.llm import LLMMessage
    prompt = f"""为第 {req.chapter} 章生成详细大纲。

题材：{genre}
{f'上下文：{req.context}' if req.context else ''}
风格：{req.style}

返回 JSON：{{"title": "...", "scenes": [...], "beats": [...], "emotional_arc": {{...}}, "target_words": 4000}}"""
    try:
        resp = await run_sync(llm.chat, [LLMMessage(role="user", content=prompt)])
        from core.llm import parse_llm_json
        data = parse_llm_json(resp.content)
        data["chapter"] = req.chapter
        out_dir = s.state_dir / "detailed_outlines"
        out_dir.mkdir(exist_ok=True)
        (out_dir / f"ch{req.chapter:04d}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "outline": data}
    except Exception as e:
        raise HTTPException(500, f"生成详细大纲失败：{e}")


@router.get("/{{book_id}}/detailed-outline/{{chapter}}")
def get_detailed_outline(book_id: str, chapter: int):
    s = sm(book_id)
    path = s.state_dir / "detailed_outlines" / f"ch{chapter:04d}.json"
    if not path.exists():
        raise HTTPException(404, f"第 {chapter} 章详细大纲不存在")
    return json.loads(path.read_text(encoding="utf-8"))


@router.put("/{{book_id}}/detailed-outline/{{chapter}}")
def save_detailed_outline(book_id: str, chapter: int, data: dict):
    s = sm(book_id)
    out_dir = s.state_dir / "detailed_outlines"
    out_dir.mkdir(exist_ok=True)
    (out_dir / f"ch{chapter:04d}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


@router.post("/{{book_id}}/ai-generate/chapter-content")
async def ai_generate_chapter_content(book_id: str, req: ChapterContentReq):
    """AI 生成某章内容"""
    load_env()
    s = sm(book_id)
    try:
        cfg = s.read_config()
        genre = cfg.get("genre", "玄幻")
        target_words = cfg.get("target_words_per_chapter", 4000)
        style_guide = cfg.get("style_guide", "")
        forbidden = cfg.get("custom_forbidden_words", [])
    except Exception:
        genre, target_words, style_guide, forbidden = "玄幻", 4000, "", []

    # 读取章纲
    outline_text = ""
    if req.outline:
        outline_text = json.dumps(req.outline, ensure_ascii=False)
    else:
        co_path = s.state_dir / "chapter_outlines.json"
        if co_path.exists():
            outlines = json.loads(co_path.read_text(encoding="utf-8"))
            for co in outlines:
                if co.get("chapter_number") == req.chapter:
                    outline_text = json.dumps(co, ensure_ascii=False)
                    break

    # 读取前文摘要
    prev_summary = req.previous_summary
    if not prev_summary:
        summary_path = s.state_dir / "chapter_summaries.md"
        if summary_path.exists():
            prev_summary = summary_path.read_text(encoding="utf-8")[-2000:]

    from core.agents import WriterAgent
    llm = create_llm()
    writer = WriterAgent(llm, style_guide=style_guide, genre=genre)

    try:
        from core.narrative import ChapterOutlineSchema
        chapter_outline = None
        if req.outline:
            try:
                chapter_outline = ChapterOutlineSchema.model_validate(req.outline)
            except Exception:
                pass
        result = await run_sync(writer.write_chapter, chapter_outline, None,
                                target_words=target_words, forbidden_words=forbidden,
                                previous_summary=prev_summary)
        s.save_draft(req.chapter, result.content)
        return {"ok": True, "content": result.content, "chars": len(result.content),
                "settlement": dc_to_dict(result.settlement) if result.settlement else None}
    except Exception as e:
        raise HTTPException(500, f"生成章节内容失败：{e}")
