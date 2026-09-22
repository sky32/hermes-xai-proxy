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
XAI_PROXY_SEARCH_MODEL=grok-4.20-multi-agent-0309
XAI_PROXY_TTS_MODEL=grok-voice-think-fast-2.0
XAI_PROXY_STT_MODEL=grok-stt
XAI_PROXY_STT_TIMEOUT=180
```

生产环境请使用 HTTPS，避免 API Key 通过明文网络传输。

## 模型参考

以下模型与 `config.example.yaml` 保持一致：

| 功能 | 模型 |
|---|---|
| 默认模型 | `grok-4.7` |
| 网页搜索 | `grok-4.20-multi-agent-0309` |
| 图片生成 | `grok-imagine-image-2.0` |
| 视频生成 | `grok-imagine-video` |
| TTS | `grok-voice-think-fast-2.0` |
| STT | `grok-stt` |

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

### 从 GitHub 安装

Hermes 的 Git 安装器支持 `owner/repo/subdir`。本项目是多插件仓库，根目录没有单一 manifest，因此建议按插件子目录分别安装：

```text
sky32/hermes-xai-proxy/plugins/model-providers/xai
sky32/hermes-xai-proxy/plugins/web/xai
sky32/hermes-xai-proxy/plugins/image_gen/xai
sky32/hermes-xai-proxy/plugins/video_gen/xai
sky32/hermes-xai-proxy/plugins/xai-proxy-tools
sky32/hermes-xai-proxy/plugins/xai-proxy-tts
sky32/hermes-xai-proxy/plugins/transcription/xai-proxy
```

在 Hermes 的“从 GitHub / Git 地址安装”中逐个输入上述路径，勾选“安装后启用”。`xai-proxy-tools` 还需要允许 `tools.override`。

## TTS 配置

TTS 模型、语音和其他参数可以在 `config.yaml` 中设置：


```yaml
tts:
  provider: xai-proxy
  xai-proxy:
    model: grok-voice-think-fast-2.0
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
    model: grok-stt
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

## 运行时兼容性

网页、图片、视频和视频工具插件会复用当前 Hermes 安装中的内置 xAI 实现，不会复制上游代码。如果 Hermes 版本缺少预期的内置文件，插件会报告明确的版本/路径兼容性错误；请升级或使用匹配的 Hermes 版本。
## 英文文档

See [README.en.md](README.en.md).
