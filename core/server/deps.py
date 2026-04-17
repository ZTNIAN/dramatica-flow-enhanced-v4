"""
公共依赖 — 所有 router 导入的共享工具函数和请求模型
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Form, Request

# ── 路径常量 ───────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BOOKS_DIR = PROJECT_ROOT / "books"
ENV_PATH = PROJECT_ROOT / ".env"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

# ── dramatic_function 枚举映射 ─────────────────────────────────────────────────

DF_MAP = {
    "setup": "setup", "establish": "setup", "exposition": "setup", "introduction": "setup",
    "inciting": "inciting", "inciting_incident": "inciting", "inciting-incident": "inciting",
    "turning": "turning", "turning_point": "turning", "turning-point": "turning",
    "progressive complication": "turning", "complication": "turning",
    "midpoint": "midpoint", "mid_point": "midpoint", "mid-point": "midpoint",
    "crisis": "crisis", "dark night": "crisis", "all is lost": "crisis", "lowest point": "crisis",
    "climax": "climax", "climax_build": "climax", "showdown": "climax", "confrontation": "climax",
    "reveal": "reveal", "revelation": "reveal", "discovery": "reveal",
    "decision": "decision", "choice": "decision", "commitment": "decision",
    "consequence": "consequence", "resolution": "consequence", "ending": "consequence",
    "denouement": "consequence", "new_world": "consequence",
    "transition": "transition", "bridge": "transition", "interlude": "transition",
}


# ── 工具函数 ───────────────────────────────────────────────────────────────────

def safe_book_dir(book_id: str) -> Path:
    """安全解析书籍路径，防止路径遍历攻击"""
    if not re.match(r'^[\w\-\u4e00-\u9fff]+$', book_id):
        raise HTTPException(400, "无效的书籍ID（只允许字母/数字/下划线/中文）")
    book_dir = (BOOKS_DIR / book_id).resolve()
    if not str(book_dir).startswith(str(BOOKS_DIR.resolve())):
        raise HTTPException(400, "无效的书籍路径")
    return book_dir


def normalize_outline(raw: dict, sm) -> dict:
    """规范化大纲 JSON，补缺字段 + 修正枚举值"""
    if "id" not in raw:
        raw["id"] = sm.book_id + "_outline"
    if "genre" not in raw:
        try:
            cfg = sm.read_config()
            raw["genre"] = cfg.get("genre", "玄幻")
        except Exception:
            raw["genre"] = "玄幻"

    INT_FIELDS = {"number", "act", "estimated_scenes", "chapter_number", "target_words"}

    for i, seq in enumerate(raw.get("sequences", [])):
        if "id" not in seq:
            seq["id"] = f"seq_{str(i+1).zfill(3)}"
        df = seq.get("dramatic_function", "setup")
        seq["dramatic_function"] = DF_MAP.get(df, df)
        if "narrative_goal" not in seq:
            seq["narrative_goal"] = seq.get("summary", "")
        for key in INT_FIELDS:
            if key in seq and isinstance(seq[key], float):
                seq[key] = int(seq[key])
        if seq.get("estimated_scenes", 0) < 1:
            seq["estimated_scenes"] = 1

    outline_path = sm.state_dir / "outline.json"
    outline_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return raw


def dc_to_dict(obj):
    """递归将 dataclass 转为 dict，处理 enum 等"""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: dc_to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [dc_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: dc_to_dict(v) for k, v in obj.items()}
    if hasattr(obj, "value"):
        return obj.value
    return obj


def sm(book_id: str):
    from core.state import StateManager
    return StateManager(PROJECT_ROOT, book_id)


def load_env():
    """加载 .env 到 os.environ"""
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH, override=True)


def create_llm(temperature: float | None = None, model_env: str = "DEEPSEEK_MODEL", max_tokens: int = 16384):
    """创建 LLM 实例"""
    from core.llm import LLMConfig, create_provider
    provider = os.environ.get("LLM_PROVIDER", "deepseek").lower()
    temp = temperature if temperature is not None else float(os.environ.get("DEFAULT_TEMPERATURE", "0.7"))

    if provider == "ollama":
        cfg = LLMConfig(
            api_key="ollama",
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            model=os.environ.get("OLLAMA_MODEL", "llama3.1"),
            temperature=temp,
            max_tokens=max_tokens,
        )
        return create_provider(cfg)

    env_prefix = provider.upper() + "_"
    key = os.environ.get(f"{env_prefix}API_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        raise HTTPException(400, f"请先配置 {provider} 的 API Key")
    base_url = os.environ.get(f"{env_prefix}BASE_URL",
                               os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"))
    model = os.environ.get(model_env, os.environ.get(f"{env_prefix}MODEL", os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")))
    cfg = LLMConfig(api_key=key, base_url=base_url, model=model, temperature=temp, max_tokens=max_tokens)
    return create_provider(cfg)


async def run_sync(func, *args, **kwargs):
    """将同步函数包装为异步，避免阻塞事件循环"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


# ── 请求模型 ───────────────────────────────────────────────────────────────────

class CreateBookReq(BaseModel):
    title: str
    genre: str = "玄幻"
    chapters: int = 90
    words: int = 4000
    forbidden: str = ""
    style_guide: str = ""

class SaveSettingsReq(BaseModel):
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    llm_provider: str = "deepseek"
    ollama_model: str = "llama3.1"
    ollama_base_url: str = "http://localhost:11434/v1"
    default_temperature: str = "0.7"
    auditor_model: str = ""
    custom_base_url: str = ""
    custom_api_key: str = ""
    custom_model: str = ""

class SaveSetupReq(BaseModel):
    file_type: str
    content: str

class AiGenerateSetupReq(BaseModel):
    genre: str
    book_title: str
    idea: str = ""
    style: str = "standard"

class SaveOutlineReq(BaseModel):
    outline: dict

class SaveChapterOutlinesReq(BaseModel):
    outlines: list

class UpdateBookConfigReq(BaseModel):
    style_guide: str = ""
    forbidden: str = ""
    protagonist_id: str = ""
    target_chapters: int | None = None
    target_words_per_chapter: int | None = None

class AiGenerateOutlineReq(BaseModel):
    idea: str = ""

class AiContinueOutlineReq(BaseModel):
    extra_sequences: int = 2
    idea: str = ""

class ThreeLayerAuditReq(BaseModel):
    chapter: int
    mode: Literal["language", "structure", "drama", "full"] = "full"

class ExtractFromNovelReq(BaseModel):
    text: str
    genre: str = "玄幻"

class ContinueWritingReq(BaseModel):
    count: int = 1
    thread_id: str | None = None
    hint: str = ""

class SegmentRewriteReq(BaseModel):
    chapter: int
    start_line: int
    end_line: int
    reason: str = "提升质量"

class CharacterGrowthReq(BaseModel):
    character_id: str | None = None
    start_chapter: int = 1
    end_chapter: int = 0

class DialogueReviewReq(BaseModel):
    chapter: int
    focus: str = ""

class EmotionCurveReq(BaseModel):
    total_chapters: int | None = None

class FeedbackReq(BaseModel):
    text: str
    source: str = "读者"

class MiroFishReq(BaseModel):
    sample_count: int = 1000
    start_chapter: int = 1
    end_chapter: int = 0

class CreateThreadReq(BaseModel):
    id: str
    name: str
    type: str = "subplot"
    pov_character_id: str = ""
    character_ids: list[str] = []
    goal: str = ""
    growth_arc: str = ""
    start_chapter: int = 1
    weight: float = 0.7
    merge_chapter: int | None = None
    end_hook: str = ""

class UpdateThreadReq(BaseModel):
    name: str | None = None
    pov_character_id: str | None = None
    character_ids: list[str] | None = None
    goal: str | None = None
    growth_arc: str | None = None
    weight: float | None = None
    status: str | None = None
    hook_score: int | None = None
    end_hook: str | None = None
    merge_target_thread: str | None = None
    merge_chapter: int | None = None

class ImportOutlineReq(BaseModel):
    outline: dict

class ImportChapterOutlinesReq(BaseModel):
    outlines: list
    merge: bool = False

class DetailedOutlineReq(BaseModel):
    chapter: int
    context: str = ""
    style: str = "standard"

class ChapterContentReq(BaseModel):
    chapter: int
    outline: dict | None = None
    style: str = "standard"
    previous_summary: str = ""

class ExtractStoryStateReq(BaseModel):
    text: str
    book_id: str = ""

class WorldbuildRequest(BaseModel):
    locations: list = []
    power_system: str = ""

class OutlineRequest(BaseModel):
    seed: str = ""
    sequences: int = 6

class MarketRequest(BaseModel):
    genre: str = "玄幻"
    sample_text: str = ""

class ExportRequest(BaseModel):
    book_id: str
    format: str = "txt"
    include_outline: bool = False
