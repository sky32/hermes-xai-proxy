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
    common = ((cfg.get("xai_proxy") or {}).get("extra_params") or {}).get("images", {})
    image_cfg = cfg.get("image_gen") or {}
    local = image_cfg.get("extra_params") or ((image_cfg.get("xai") or {}).get("extra_params") or {})
    out = dict(common) if isinstance(common, dict) else {}
    if isinstance(local, dict):
        out.update(local)
    return out


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
    path = _bundled_file("plugins", "image_gen", "xai", "__init__.py")
    mod = _load_file("_hermes_builtin_image_xai_proxywrap", path)

    mod.resolve_xai_http_credentials = lambda *a, **kw: _proxy_credentials()
    original_post_json = mod.post_json

    def post_json_with_extras(endpoint_url, *args, **kwargs):
        payload = kwargs.get("payload")
        if isinstance(payload, dict):
            kwargs["payload"] = {**payload, **_extra_params()}
        return original_post_json(endpoint_url, *args, **kwargs)

    mod.post_json = post_json_with_extras

    class XAIProxyImageGenProvider(mod.XAIImageGenProvider):
        label = "xAI (via proxy)"

        def get_setup_schema(self):
            return {
                "name": "xAI Grok Imagine (Proxy)",
                "badge": "proxy",
                "tag": "Official Hermes xAI image backend routed through XAI_PROXY_BASE_URL",
                "env_vars": [
                    {"key": "XAI_PROXY_BASE_URL", "prompt": "xAI-compatible proxy base URL"},
                    {"key": "XAI_PROXY_API_KEY", "prompt": "Proxy API key"},
                ],
            }

    ctx.register_image_gen_provider(XAIProxyImageGenProvider())
