from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict

from hermes_cli.config import get_env_value, load_config


def _extra_params() -> Dict[str, Any]:
    try:
        cfg = load_config() or {}
    except Exception:
        cfg = {}
    common = ((cfg.get("xai_proxy") or {}).get("extra_params") or {}).get("web", {})
    local = (((cfg.get("web") or {}).get("xai") or {}).get("extra_params") or {})
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


def register(ctx) -> None:
    path = _bundled_file("plugins", "web", "xai", "provider.py")
    mod = _load_file("_hermes_builtin_web_xai_proxywrap", path)

    # Patch the bundled provider's credential seams.
    mod.resolve_xai_http_credentials = lambda *a, **kw: _proxy_credentials()
    mod.has_xai_credentials = _proxy_ready
    original_post = mod.XAIWebSearchProvider._post_responses

    class XAIProxyWebSearchProvider(mod.XAIWebSearchProvider):
        @staticmethod
        def _post_responses(base_url, payload, api_key, timeout, *, is_oauth_path):
            merged = dict(payload)
            merged.update(_extra_params())
            if _api_format() == "openai":
                merged.pop("include", None)
                merged["tools"] = [
                    {"type": "web_search_preview"}
                    if isinstance(tool, dict) and tool.get("type") == "web_search"
                    else tool
                    for tool in merged.get("tools", [])
                ]
            return original_post(base_url, merged, api_key, timeout, is_oauth_path=is_oauth_path)

    class XAIProxyWebProvider(XAIProxyWebSearchProvider):
        DISPLAY_NAME = "xAI Web Search (via proxy)"

        def get_setup_schema(self):
            return {
                "name": "xAI Web Search (Proxy)",
                "badge": "proxy",
                "tag": "Uses XAI_PROXY_BASE_URL and XAI_PROXY_API_KEY",
                "env_vars": [
                    {"key": "XAI_PROXY_BASE_URL", "prompt": "xAI-compatible proxy base URL"},
                    {"key": "XAI_PROXY_API_KEY", "prompt": "Proxy API key"},
                ],
            }

    ctx.register_web_search_provider(XAIProxyWebProvider())
