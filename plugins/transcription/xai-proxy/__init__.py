from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import mimetypes
import requests

from agent.transcription_provider import TranscriptionProvider
from hermes_cli.config import get_env_value, load_config

def _env(key: str) -> str:
    return str(get_env_value(key) or "").strip()


def _float_env(key: str, default: float) -> float:
    try:
        value = float(_env(key) or default)
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


def _extra_params() -> Dict[str, Any]:
    try:
        cfg = load_config() or {}
    except Exception:
        cfg = {}
    common = ((cfg.get("xai_proxy") or {}).get("extra_params") or {}).get("stt", {})
    local = (((cfg.get("stt") or {}).get("xai-proxy") or {}).get("extra_params") or {})
    out = dict(common) if isinstance(common, dict) else {}
    if isinstance(local, dict):
        out.update(local)
    return out


def _api_format() -> str:
    try:
        cfg = load_config() or {}
    except Exception:
        cfg = {}
    value = ((cfg.get("xai_proxy") or {}).get("api_format") or _env("XAI_PROXY_API_FORMAT") or "xai")
    return str(value).strip().lower() if str(value).strip().lower() in {"xai", "openai"} else "xai"


class XAIProxySTTProvider(TranscriptionProvider):
    @property
    def name(self) -> str:
        return "xai-proxy"

    @property
    def display_name(self) -> str:
        return "xAI STT (Proxy)"

    def is_available(self) -> bool:
        return bool(_env("XAI_PROXY_BASE_URL") and _env("XAI_PROXY_API_KEY"))

    def list_models(self):
        return [
            {"id": "grok-stt", "display": "Grok STT"},
            {"id": "grok-voice-think-fast-2.0", "display": "Grok Voice Think Fast 2.0"},
        ]

    def default_model(self) -> Optional[str]:
        return _env("XAI_PROXY_STT_MODEL") or "grok-stt"

    def transcribe(
        self,
        file_path: str,
        *,
        model: Optional[str] = None,
        language: Optional[str] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        base = _env("XAI_PROXY_BASE_URL").rstrip("/")
        key = _env("XAI_PROXY_API_KEY")
        provider = self.name
        if not base or not key:
            return {
                "success": False,
                "transcript": "",
                "error": "XAI_PROXY_BASE_URL / XAI_PROXY_API_KEY not configured",
                "provider": provider,
            }

        path = Path(file_path)
        try:
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            data = {"model": model or self.default_model()}
            if language:
                data["language"] = language
            data.update(_extra_params())

            with path.open("rb") as fh:
                r = requests.post(
                    f'{base}{"/audio/transcriptions" if _api_format() == "openai" else "/stt"}',
                    headers={
                        "Authorization": f"Bearer {key}",
                        "User-Agent": "Hermes-XAI-Proxy/stt",
                    },
                    files={"file": (path.name, fh, mime)},
                    data=data,
                    timeout=_float_env("XAI_PROXY_STT_TIMEOUT", 180),
                )
            r.raise_for_status()
            payload = r.json()
            text = str(payload.get("text") or payload.get("transcript") or "").strip()
            return {"success": True, "transcript": text, "provider": provider}
        except Exception as exc:
            return {
                "success": False,
                "transcript": "",
                "error": f"xAI proxy STT failed: {exc}",
                "provider": provider,
            }

    def get_setup_schema(self):
        return {
            "name": "xAI STT (Proxy)",
            "badge": "proxy",
            "tag": "POST /v1/stt through XAI_PROXY_BASE_URL",
            "env_vars": [
                {"key": "XAI_PROXY_BASE_URL", "prompt": "xAI-compatible proxy base URL"},
                {"key": "XAI_PROXY_API_KEY", "prompt": "Proxy API key"},
            ],
        }


def register(ctx):
    ctx.register_transcription_provider(XAIProxySTTProvider())
