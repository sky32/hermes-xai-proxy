from hermes_cli import __version__ as _HERMES_VERSION
from hermes_cli.config import get_env_value
from providers import register_provider
from providers.base import ProviderProfile

_base_url = (get_env_value("XAI_PROXY_BASE_URL") or "").strip().rstrip("/")
if not _base_url:
    raise RuntimeError("XAI_PROXY_BASE_URL is required for the xai-proxy model provider")

xai = ProviderProfile(
    name="xai",
    aliases=("grok", "x-ai", "x.ai"),
    api_mode="codex_responses",
    env_vars=("XAI_PROXY_API_KEY",),
    base_url=_base_url,
    auth_type="api_key",
    default_headers={"User-Agent": f"Hermes-Agent/{_HERMES_VERSION} xai-proxy"},
)

register_provider(xai)
