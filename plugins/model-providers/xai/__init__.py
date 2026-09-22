from hermes_cli import __version__ as _HERMES_VERSION
from hermes_cli.config import get_env_value, load_config
from providers import register_provider
from providers.base import ProviderProfile


def _extra_params(operation: str) -> dict:
    """Return proxy-only body fields without overwriting Hermes fields."""
    try:
        cfg = load_config() or {}
    except Exception:
        cfg = {}
    common = ((cfg.get("xai_proxy") or {}).get("extra_params") or {}).get(operation, {})
    model_cfg = cfg.get("model") or {}
    local_cfg = model_cfg.get("extra_params") or ((model_cfg.get("xai") or {}).get("extra_params") or {})
    local = local_cfg.get(operation, {}) if isinstance(local_cfg, dict) else {}
    out = dict(common) if isinstance(common, dict) else {}
    if isinstance(local, dict):
        out.update(local)
    return out


class XAIProxyProviderProfile(ProviderProfile):
    def build_extra_body(self, *, session_id=None, **context):
        operation = "responses" if self.api_mode == "codex_responses" else "chat"
        return _extra_params(operation)

_base_url = (get_env_value("XAI_PROXY_BASE_URL") or "").strip().rstrip("/")
# Keep discovery/import safe when the optional proxy is not configured.
if not _base_url:
    _base_url = ""

xai = XAIProxyProviderProfile(
    name="xai",
    aliases=("grok", "x-ai", "x.ai"),
    api_mode="codex_responses",
    env_vars=("XAI_PROXY_API_KEY",),
    base_url=_base_url,
    auth_type="api_key",
    default_headers={"User-Agent": f"Hermes-Agent/{_HERMES_VERSION} xai-proxy"},
)

register_provider(xai)
