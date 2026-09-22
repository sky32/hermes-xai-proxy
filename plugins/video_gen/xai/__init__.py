from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict

from hermes_cli.config import get_env_value, load_config


def _extra_params(operation: str = "videos") -> Dict[str, Any]:
    try:
        cfg = load_config() or {}
    except Exception:
        cfg = {}
    common = ((cfg.get("xai_proxy") or {}).get("extra_params") or {}).get(operation, {})
    video_cfg = cfg.get("video_gen") or {}
    local = video_cfg.get("extra_params") or ((video_cfg.get("xai") or {}).get("extra_params") or {})
    out = dict(common) if isinstance(common, dict) else {}
    if isinstance(local, dict):
        out.update(local)
    return out


def _api_format() -> str:
    try:
        cfg = load_config() or {}
    except Exception:
        cfg = {}
    value = ((cfg.get("xai_proxy") or {}).get("api_format") or get_env_value("XAI_PROXY_API_FORMAT") or "xai")
    return str(value).strip().lower() if str(value).strip().lower() in {"xai", "openai"} else "xai"


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


def _load_video_module():
    path = _bundled_file("plugins", "video_gen", "xai", "__init__.py")
    mod = _load_file("_hermes_builtin_video_xai_proxywrap", path)
    mod._resolve_xai_credentials = lambda: (
        str(_proxy_credentials()["api_key"]),
        str(_proxy_credentials()["base_url"]),
    )
    original_submit = mod._submit_xai_video_payload

    async def submit_with_extras(api_key, base_url, endpoint, payload, **kwargs):
        merged = dict(payload)
        merged.update(_extra_params())
        if _api_format() == "openai":
            if endpoint != "generations":
                return mod._xai_error(
                    "OpenAI video format supports generation only; edit/extend requires xAI format",
                    "unsupported_operation", merged.get("prompt", ""), model=merged.get("model"),
                )
            return await _submit_openai_video(mod, api_key, base_url, merged, **kwargs)
        return await original_submit(api_key, base_url, endpoint, merged, **kwargs)

    mod._submit_xai_video_payload = submit_with_extras
    return mod


async def _submit_openai_video(mod, api_key: str, base_url: str, payload: Dict[str, Any], **kwargs):
    """Submit/poll the OpenAI Videos shape while preserving Hermes' result envelope."""
    import httpx

    prompt = str(payload.get("prompt") or "")
    model = str(payload.get("model") or "")
    openai_payload = {"model": model, "prompt": prompt}
    if payload.get("duration") is not None:
        openai_payload["seconds"] = str(payload["duration"])
    resolution = payload.get("resolution")
    aspect = payload.get("aspect_ratio")
    openai_payload["size"] = {"16:9": "1280x720", "9:16": "720x1280", "1:1": "1024x1024"}.get(
        str(aspect), "1280x720"
    ) if not resolution else ("720x1280" if str(aspect) == "9:16" else "1280x720")
    if payload.get("image"):
        openai_payload["input_reference"] = payload["image"]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{base_url}/videos", headers=headers, json=openai_payload, timeout=60)
        response.raise_for_status()
        body = response.json()
        request_id = body.get("id") or body.get("request_id")
        if not request_id:
            return mod._xai_error("OpenAI video response did not include id", "api_error", prompt, model=model)
        elapsed = 0.0
        while elapsed < mod.DEFAULT_TIMEOUT_SECONDS:
            response = await client.get(f"{base_url}/videos/{request_id}", headers=headers, timeout=30)
            response.raise_for_status()
            body = response.json()
            status = str(body.get("status") or "").lower()
            if status in {"completed", "succeeded", "failed", "error", "cancelled", "canceled"}:
                break
            await __import__("asyncio").sleep(mod.DEFAULT_POLL_INTERVAL_SECONDS)
            elapsed += mod.DEFAULT_POLL_INTERVAL_SECONDS
    if status not in {"completed", "succeeded"}:
        return mod._xai_error(body.get("error") or f"OpenAI video job ended with status {status!r}", "api_error", prompt, model=model)
    video = body.get("video") if isinstance(body.get("video"), dict) else body
    video_url = video.get("url") or body.get("url")
    if not video_url:
        return mod._xai_error("OpenAI video response did not include a URL", "empty_response", prompt, model=model)
    return mod.success_response(video=video_url, model=body.get("model") or model, prompt=prompt,
                                modality="text", aspect_ratio=aspect or "16:9",
                                duration=payload.get("duration") or 0, provider="xai-proxy")


def register(ctx) -> None:
    mod = _load_video_module()

    class XAIProxyVideoGenProvider(mod.XAIVideoGenProvider):
        display_name = "xAI (via proxy)"

        def get_setup_schema(self):
            return {
                "name": "xAI Grok Imagine Video (Proxy)",
                "badge": "proxy",
                "tag": "Official Hermes xAI video backend routed through XAI_PROXY_BASE_URL",
                "env_vars": [
                    {"key": "XAI_PROXY_BASE_URL", "prompt": "xAI-compatible proxy base URL"},
                    {"key": "XAI_PROXY_API_KEY", "prompt": "Proxy API key"},
                ],
            }

    ctx.register_video_gen_provider(XAIProxyVideoGenProvider())
