from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import mimetypes
import requests

from agent.transcription_provider import TranscriptionProvider
from hermes_cli.config import get_env_value


def _env(key: str) -> str:
    return str(get_env_value(key) or "").strip()


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
            {"id": "grok-voice-transcribe-2.0", "display": "Grok Voice Transcribe 2.0"},
            {"id": "grok-voice-transcribe-1.0", "display": "Grok Voice Transcribe 1.0"},
            {"id": "grok-stt", "display": "Grok STT (legacy alias)"},
        ]

    def default_model(self) -> Optional[str]:
        return _env("XAI_PROXY_STT_MODEL") or "grok-voice-transcribe-2.0"

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

            with path.open("rb") as fh:
                r = requests.post(
                    f"{base}/stt",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "User-Agent": "Hermes-XAI-Proxy/stt",
                    },
                    files={"file": (path.name, fh, mime)},
                    data=data,
                    timeout=float(_env("XAI_PROXY_STT_TIMEOUT") or 180),
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
