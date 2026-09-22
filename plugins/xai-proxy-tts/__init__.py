from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from agent.tts_provider import TTSProvider
from hermes_cli.config import get_env_value, load_config


def _env(key: str) -> str:
    return str(get_env_value(key) or "").strip()


def _cfg() -> Dict[str, Any]:
    try:
        return ((load_config() or {}).get("tts", {}) or {}).get("xai-proxy", {}) or {}
    except Exception:
        return {}


class XAIProxyTTSProvider(TTSProvider):
    @property
    def name(self) -> str:
        return "xai-proxy"

    @property
    def display_name(self) -> str:
        return "xAI TTS (Proxy)"

    @property
    def voice_compatible(self) -> bool:
        return True

    def is_available(self) -> bool:
        return bool(_env("XAI_PROXY_BASE_URL") and _env("XAI_PROXY_API_KEY"))

    def list_voices(self) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []
        try:
            r = requests.get(
                f'{_env("XAI_PROXY_BASE_URL").rstrip("/")}/tts/voices',
                headers={"Authorization": f'Bearer {_env("XAI_PROXY_API_KEY")}'},
                timeout=15,
            )
            r.raise_for_status()
            payload = r.json()
            out = []
            for v in payload.get("voices", []) or []:
                if not isinstance(v, dict):
                    continue
                vid = v.get("voice_id") or v.get("id")
                if vid:
                    out.append({
                        "id": str(vid),
                        "display": str(v.get("name") or vid),
                        "language": str(v.get("language") or ""),
                    })
            return out
        except Exception:
            return [
                {"id": "eve", "display": "Eve"},
                {"id": "ara", "display": "Ara"},
                {"id": "leo", "display": "Leo"},
                {"id": "rex", "display": "Rex"},
                {"id": "sal", "display": "Sal"},
            ]

    def default_voice(self) -> Optional[str]:
        return str(_cfg().get("voice_id") or "eve")

    def synthesize(
        self,
        text: str,
        output_path: str,
        *,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        speed: Optional[float] = None,
        format: str = "mp3",
        **extra: Any,
    ) -> str:
        base = _env("XAI_PROXY_BASE_URL").rstrip("/")
        key = _env("XAI_PROXY_API_KEY")
        if not base or not key:
            raise RuntimeError("XAI_PROXY_BASE_URL / XAI_PROXY_API_KEY not configured")

        cfg = _cfg()
        requested_format = (format or "mp3").lower()
        # xAI TTS does not provide native opus/ogg. Hermes can transcode because
        # voice_compatible=True; request MP3 unless WAV is explicitly requested.
        codec = "wav" if requested_format == "wav" else "mp3"

        language = str(extra.get("language") or cfg.get("language") or "auto")
        sample_rate = int(cfg.get("sample_rate") or 24000)
        bit_rate = int(cfg.get("bit_rate") or 128000)
        rate = float(speed if speed is not None else cfg.get("speed", 1.0) or 1.0)
        rate = max(0.7, min(1.5, rate))

        payload = {
            "model": model or _env("XAI_PROXY_TTS_MODEL") or cfg.get("model") or "grok-tts",
            "text": text,
            "voice_id": voice or cfg.get("voice_id") or "eve",
            "language": language,
            "speed": rate,
            "output_format": {
                "codec": codec,
                "sample_rate": sample_rate,
            },
        }
        if codec == "mp3":
            payload["output_format"]["bit_rate"] = bit_rate

        if "text_normalization" in cfg:
            payload["text_normalization"] = bool(cfg["text_normalization"])
        if "optimize_streaming_latency" in cfg:
            payload["optimize_streaming_latency"] = int(cfg["optimize_streaming_latency"])

        try:
            r = requests.post(
                f"{base}/tts",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Hermes-XAI-Proxy/tts",
                },
                json=payload,
                timeout=float(cfg.get("timeout") or 120),
            )
            r.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"xAI proxy TTS request failed: {exc}") from exc

        target = Path(output_path)
        if codec == "wav" and target.suffix.lower() != ".wav":
            target = target.with_suffix(".wav")
        elif codec == "mp3" and target.suffix.lower() not in (".mp3",):
            target = target.with_suffix(".mp3")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(r.content)
        return str(target)

    def get_setup_schema(self):
        return {
            "name": "xAI TTS (Proxy)",
            "badge": "proxy",
            "tag": "POST /v1/tts through XAI_PROXY_BASE_URL",
            "env_vars": [
                {"key": "XAI_PROXY_BASE_URL", "prompt": "xAI-compatible proxy base URL"},
                {"key": "XAI_PROXY_API_KEY", "prompt": "Proxy API key"},
            ],
        }


def register(ctx):
    ctx.register_tts_provider(XAIProxyTTSProvider())
