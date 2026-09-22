# hermes-xai-proxy

Route Hermes Agent's xAI/Grok surfaces through any xAI-compatible HTTP proxy.

## Supported surfaces

- LLM/model provider: `xai` (same-name override)
- Web search provider: `xai` (same-name override)
- Image generation provider: `xai` (same-name override)
- Video generation provider: `xai` (same-name override)
- `x_search`: tool override
- `xai_video_edit`: tool override
- `xai_video_extend`: tool override
- TTS provider: `xai-proxy`
- STT provider: `xai-proxy`

Hermes does not allow Python plugins to shadow built-in TTS/STT names, so those providers use `xai-proxy`.

## Configuration

Add the following to Hermes' `.env`:

```env
XAI_PROXY_BASE_URL=https://your-proxy.example.com/v1
XAI_PROXY_API_KEY=your-key
```

Optional settings:

```env
XAI_PROXY_SEARCH_MODEL=grok-4.6
XAI_PROXY_TTS_MODEL=grok-tts
XAI_PROXY_STT_MODEL=grok-voice-transcribe-2.0
XAI_PROXY_STT_TIMEOUT=180
```

Use HTTPS in production so the API key is not sent over plaintext HTTP.

## Install

Inside the Hermes container or host:

```bash
HERMES_HOME=/opt/data ./install.sh
```

The installer creates timestamped backups before replacing existing plugin directories.

Enable the plugins:

```bash
hermes plugins enable xai-proxy-model
hermes plugins enable xai-proxy-web
hermes plugins enable xai-proxy-image
hermes plugins enable xai-proxy-video
hermes plugins enable xai-proxy-tools --allow-tool-override
hermes plugins enable xai-proxy-tts
hermes plugins enable xai-proxy-stt
```

Merge `config.example.yaml` into Hermes' `config.yaml`, then restart Hermes.

## TTS

The TTS model can be selected through the environment:

```env
XAI_PROXY_TTS_MODEL=grok-tts
```

Or through `config.yaml`:

```yaml
tts:
  provider: xai-proxy
  xai-proxy:
    model: grok-tts
    voice_id: eve
    language: auto
    speed: 1.0
```

The provider calls `POST $XAI_PROXY_BASE_URL/tts`, supports voice listing through `GET /tts/voices`, and returns MP3/WAV output.

## STT

```yaml
stt:
  provider: xai-proxy
  xai-proxy:
    model: grok-voice-transcribe-2.0
```

The provider calls multipart `POST $XAI_PROXY_BASE_URL/stt`.

## Uninstall

```bash
HERMES_HOME=/opt/data ./uninstall.sh
```

The uninstall script moves plugin directories to timestamped backups. Configuration and environment entries are left untouched; disable the plugins manually after uninstalling.

## Validate

```bash
hermes plugins validate /opt/data/plugins/web/xai
hermes plugins validate /opt/data/plugins/image_gen/xai
hermes plugins validate /opt/data/plugins/video_gen/xai
hermes plugins capabilities xai-proxy-tools
```

## Design note

This repository is a compatibility/adapter layer. It does not embed or redistribute Hermes' bundled xAI image/video/web implementations; those modules are loaded from the user's installed Hermes package at runtime.
