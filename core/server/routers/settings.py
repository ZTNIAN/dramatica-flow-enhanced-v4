"""
/settings 设置管理
"""
from __future__ import annotations

import os
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..deps import PROJECT_ROOT, ENV_PATH, SaveSettingsReq, load_env

router = APIRouter(tags=["settings"])


@router.get("/api/settings")
def get_settings():
    """读取当前配置"""
    load_env()
    return {
        "deepseek_api_key": os.environ.get("DEEPSEEK_API_KEY", "")[:8] + "..." if os.environ.get("DEEPSEEK_API_KEY") else "",
        "deepseek_base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "deepseek_model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "llm_provider": os.environ.get("LLM_PROVIDER", "deepseek"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "llama3.1"),
        "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "default_temperature": os.environ.get("DEFAULT_TEMPERATURE", "0.7"),
        "auditor_model": os.environ.get("AUDITOR_MODEL", ""),
        "custom_base_url": os.environ.get("CUSTOM_BASE_URL", ""),
        "custom_api_key": os.environ.get("CUSTOM_API_KEY", "")[:8] + "..." if os.environ.get("CUSTOM_API_KEY") else "",
        "custom_model": os.environ.get("CUSTOM_MODEL", ""),
        "has_env_file": ENV_PATH.exists(),
    }


@router.get("/api/settings/status")
def get_settings_status():
    """检查配置状态"""
    load_env()
    provider = os.environ.get("LLM_PROVIDER", "deepseek").lower()
    env_prefix = provider.upper() + "_"
    has_key = bool(os.environ.get(f"{env_prefix}API_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", ""))
    return {
        "provider": provider,
        "has_api_key": has_key,
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "has_env_file": ENV_PATH.exists(),
        "ready": has_key,
    }


@router.post("/api/settings")
def save_settings(req: SaveSettingsReq):
    """保存配置到 .env 文件"""
    lines = []
    if req.deepseek_api_key:
        lines.append(f"DEEPSEEK_API_KEY={req.deepseek_api_key}")
    lines.append(f"DEEPSEEK_BASE_URL={req.deepseek_base_url}")
    lines.append(f"DEEPSEEK_MODEL={req.deepseek_model}")
    lines.append(f"LLM_PROVIDER={req.llm_provider}")
    lines.append(f"OLLAMA_MODEL={req.ollama_model}")
    lines.append(f"OLLAMA_BASE_URL={req.ollama_base_url}")
    lines.append(f"DEFAULT_TEMPERATURE={req.default_temperature}")
    if req.auditor_model:
        lines.append(f"AUDITOR_MODEL={req.auditor_model}")
    if req.custom_base_url:
        lines.append(f"CUSTOM_BASE_URL={req.custom_base_url}")
    if req.custom_api_key:
        lines.append(f"CUSTOM_API_KEY={req.custom_api_key}")
    if req.custom_model:
        lines.append(f"CUSTOM_MODEL={req.custom_model}")

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    load_env()
    return {"ok": True, "message": "配置已保存，重启服务后生效"}
