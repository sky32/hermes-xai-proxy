# hermes-xai-proxy

将 Hermes Agent 的 xAI/Grok 能力转发到任意兼容 xAI API 的 HTTP 代理。

## 功能

支持以下能力：

- 模型供应商：`xai`
- 网页搜索供应商：`xai`
- 图片生成供应商：`xai`
- 视频生成供应商：`xai`
- `x_search` 工具
- `xai_video_edit` 和 `xai_video_extend` 工具
- TTS 供应商：`xai-proxy`
- STT 供应商：`xai-proxy`

Hermes 不允许 Python 插件覆盖内置 TTS/STT 名称，因此 TTS 和 STT 使用 `xai-proxy`。

## 配置

在 Hermes 的 `.env` 中设置：

```env
XAI_PROXY_BASE_URL=https://your-proxy.example.com/v1
XAI_PROXY_API_KEY=your-key
```

可选配置：

```env
XAI_PROXY_SEARCH_MODEL=grok-4.6
XAI_PROXY_TTS_MODEL=grok-tts
XAI_PROXY_STT_MODEL=grok-voice-transcribe-2.0
XAI_PROXY_STT_TIMEOUT=180
```

生产环境请使用 HTTPS，避免 API Key 通过明文网络传输。

## 安装

在 Hermes 容器或主机中执行：

```bash
HERMES_HOME=/opt/data ./install.sh
```

安装脚本会在覆盖已有插件前创建带时间戳的备份。

启用插件：

```bash
hermes plugins enable xai-proxy-model
hermes plugins enable xai-proxy-web
hermes plugins enable xai-proxy-image
hermes plugins enable xai-proxy-video
hermes plugins enable xai-proxy-tools --allow-tool-override
hermes plugins enable xai-proxy-tts
hermes plugins enable xai-proxy-stt
```

然后将 `config.example.yaml` 合并到 Hermes 的 `config.yaml`，重启 Hermes。

## TTS 配置

TTS 模型可以通过环境变量设置：

```env
XAI_PROXY_TTS_MODEL=grok-tts
```

也可以在 `config.yaml` 中设置：

```yaml
tts:
  provider: xai-proxy
  xai-proxy:
    model: grok-tts
    voice_id: eve
    language: auto
    speed: 1.0
```

TTS 请求发送到 `POST $XAI_PROXY_BASE_URL/tts`，语音列表从 `GET /tts/voices` 获取；如果接口不可用，插件会使用内置语音列表作为回退。

## STT 配置

```yaml
stt:
  provider: xai-proxy
  xai-proxy:
    model: grok-voice-transcribe-2.0
```

STT 请求以 multipart 形式发送到 `POST $XAI_PROXY_BASE_URL/stt`。

## 卸载

```bash
HERMES_HOME=/opt/data ./uninstall.sh
```

卸载脚本会将插件目录移动到带时间戳的备份目录，配置和环境变量不会自动删除。卸载后请手动禁用对应插件。

## 验证

```bash
hermes plugins validate /opt/data/plugins/web/xai
hermes plugins validate /opt/data/plugins/image_gen/xai
hermes plugins validate /opt/data/plugins/video_gen/xai
hermes plugins capabilities xai-proxy-tools
```

## 英文文档

See [README.en.md](README.en.md).
