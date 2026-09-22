from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict

from hermes_cli.config import get_env_value


def _proxy_credentials() -> Dict[str, Any]:
    key = str(get_env_value("XAI_PROXY_API_KEY") or "").strip()
    base_url = str(get_env_value("XAI_PROXY_BASE_URL") or "").strip().rstrip("/")
    return {
        "provider": "xai-proxy",
        "api_key": key,
        "base_url": base_url,
    }


def _proxy_ready() -> bool:
    c = _proxy_credentials()
    return bool(c["api_key"] and c["base_url"])


def _bundled_file(*parts: str) -> Path:
    try:
        import hermes_cli
    except ImportError as exc:
        raise RuntimeError(
            "Hermes xAI proxy requires the installed Hermes package; "
            "hermes_cli is unavailable while loading the bundled xAI implementation"
        ) from exc
    repo_root = Path(hermes_cli.__file__).resolve().parent.parent
    path = repo_root.joinpath(*parts)
    if not path.is_file():
        raise RuntimeError(
            "Hermes xAI proxy is incompatible with this Hermes version: "
            f"bundled file not found at {path}. Install a Hermes version containing "
            f"plugins/{parts[1]}/xai."
        )
    return path


def _load_file(alias: str, path: Path):
    if alias in sys.modules:
        return sys.modules[alias]
    spec = importlib.util.spec_from_file_location(alias, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load Hermes bundled module: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod

import json
import requests


X_SEARCH_SCHEMA = {
    "name": "x_search",
    "description": "Search X (Twitter) using the xAI Responses API x_search hosted tool through the configured proxy.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "allowed_x_handles": {"type": "array", "items": {"type": "string"}},
            "excluded_x_handles": {"type": "array", "items": {"type": "string"}},
            "from_date": {"type": "string"},
            "to_date": {"type": "string"},
            "enable_image_understanding": {"type": "boolean", "default": False},
            "enable_video_understanding": {"type": "boolean", "default": False},
        },
        "required": ["query"],
    },
}

VIDEO_EDIT_SCHEMA = {
    "name": "xai_video_edit",
    "description": "Edit a previously generated xAI video through the configured proxy.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "video_url": {"type": "string"},
            "model": {"type": "string"},
        },
        "required": ["prompt", "video_url"],
    },
}

VIDEO_EXTEND_SCHEMA = {
    "name": "xai_video_extend",
    "description": "Extend a previously generated xAI video through the configured proxy.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "video_url": {"type": "string"},
            "duration": {"type": "integer"},
            "model": {"type": "string"},
        },
        "required": ["prompt", "video_url"],
    },
}


def _x_search(args, **kwargs):
    c = _proxy_credentials()
    if not c["api_key"] or not c["base_url"]:
        return json.dumps({"success": False, "error": "XAI_PROXY_BASE_URL / XAI_PROXY_API_KEY not configured"}, ensure_ascii=False)

    query = str(args.get("query") or "").strip()
    if not query:
        return json.dumps({"success": False, "error": "query is required"}, ensure_ascii=False)

    tool = {"type": "x_search"}
    for key in (
        "allowed_x_handles",
        "excluded_x_handles",
        "from_date",
        "to_date",
        "enable_image_understanding",
        "enable_video_understanding",
    ):
        value = args.get(key)
        if value not in (None, "", [], False):
            tool[key] = value

    try:
        from hermes_cli.config import load_config
        cfg = (load_config() or {}).get("x_search", {}) or {}
    except Exception:
        cfg = {}

    model = str(cfg.get("model") or get_env_value("XAI_PROXY_SEARCH_MODEL") or "grok-4.20-multi-agent-0309")
    try:
        timeout = max(1, float(cfg.get("timeout_seconds", 180) or 180))
    except (TypeError, ValueError):
        timeout = 180

    payload = {
        "model": model,
        "input": [{"role": "user", "content": query}],
        "tools": [tool],
        "store": False,
    }

    try:
        resp = requests.post(
            f'{c["base_url"]}/responses',
            headers={
                "Authorization": f'Bearer {c["api_key"]}',
                "Content-Type": "application/json",
                "User-Agent": "Hermes-XAI-Proxy/x-search",
            },
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        safe_error = str(exc).replace(c["api_key"], "[redacted]")
        return json.dumps({"success": False, "error": f"Proxy request failed: {safe_error}", "provider": "xai-proxy"}, ensure_ascii=False)

    if not resp.ok:
        safe_text = resp.text[:500].replace(c["api_key"], "[redacted]")
        return json.dumps({
            "success": False,
            "error": f"HTTP {resp.status_code}: {safe_text}",
            "provider": "xai-proxy",
        }, ensure_ascii=False)

    try:
        data = resp.json()
    except Exception:
        return json.dumps({"success": False, "error": "Proxy returned non-JSON response"}, ensure_ascii=False)

    text_parts = []
    annotations = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content", []) or []:
            if not isinstance(part, dict):
                continue
            if part.get("type") in ("output_text", "text") and part.get("text"):
                text_parts.append(str(part["text"]))
            for ann in part.get("annotations", []) or []:
                if isinstance(ann, dict):
                    annotations.append(ann)

    return json.dumps({
        "success": True,
        "provider": "xai-proxy",
        "tool": "x_search",
        "model": model,
        "answer": data.get("output_text") or "\n\n".join(text_parts),
        "citations": data.get("citations") or [],
        "annotations": annotations,
    }, ensure_ascii=False)


def _video_module():
    path = _bundled_file("plugins", "video_gen", "xai", "__init__.py")
    mod = _load_file("_hermes_builtin_video_xai_proxywrap_tools", path)
    mod._resolve_xai_credentials = lambda: (
        str(_proxy_credentials()["api_key"]),
        str(_proxy_credentials()["base_url"]),
    )
    return mod


def _video_error(message: str) -> str:
    return json.dumps({"success": False, "provider": "xai-proxy", "error": message}, ensure_ascii=False)


def _video_edit(args, **kwargs):
    if not _proxy_ready():
        return _video_error("XAI_PROXY_BASE_URL / XAI_PROXY_API_KEY not configured")
    try:
        mod = _video_module()
        return mod.run_xai_video_edit(
            prompt=str(args.get("prompt") or ""),
            video_url=str(args.get("video_url") or ""),
            model=args.get("model"),
        )
    except Exception:
        return _video_error("xAI proxy video edit failed; check Hermes and proxy logs")


def _video_extend(args, **kwargs):
    if not _proxy_ready():
        return _video_error("XAI_PROXY_BASE_URL / XAI_PROXY_API_KEY not configured")
    try:
        mod = _video_module()
        return mod.run_xai_video_extend(
            prompt=str(args.get("prompt") or ""),
            video_url=str(args.get("video_url") or ""),
            duration=args.get("duration"),
            model=args.get("model"),
        )
    except Exception:
        return _video_error("xAI proxy video extend failed; check Hermes and proxy logs")


def register(ctx):
    # All three intentionally replace Hermes built-ins.
    ctx.register_tool(
        name="x_search",
        toolset="x_search",
        schema=X_SEARCH_SCHEMA,
        handler=_x_search,
        check_fn=_proxy_ready,
        description="X Search via xAI-compatible proxy",
        emoji="🐦",
        override=True,
    )

    ctx.register_tool(
        name="xai_video_edit",
        toolset="video_gen",
        schema=VIDEO_EDIT_SCHEMA,
        handler=_video_edit,
        check_fn=_proxy_ready,
        description="xAI video edit via proxy",
        emoji="🎬",
        override=True,
    )

    ctx.register_tool(
        name="xai_video_extend",
        toolset="video_gen",
        schema=VIDEO_EXTEND_SCHEMA,
        handler=_video_extend,
        check_fn=_proxy_ready,
        description="xAI video extend via proxy",
        emoji="🎬",
        override=True,
    )
