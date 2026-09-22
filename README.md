# hermes-xai-proxy

将 Hermes Agent 的模型和媒体能力转发到可配置协议的 HTTP 代理。

## 协议格式

通过 `xai_proxy.api_format` 选择代理请求格式：

```yaml
xai_proxy:
  api_format: openai  # openai 或 xai
```

`openai` 模式是推荐模式：对话使用 OpenAI Chat Completions，图片使用
OpenAI Images 字段，TTS 使用 `/audio/speech`，STT 使用
`/audio/transcriptions`，网页搜索使用 OpenAI Responses 的
`web_search_preview` 工具。

`xai` 模式保留旧行为：对话使用 Responses，图片/视频/TTS/STT 使用原有
xAI/Grok 字段和路径。未设置时默认为 `xai`，以兼容旧配置。

视频接口需要特别注意：OpenAI 标准视频接口与 Grok Imagine 的异步任务协议
并不完全一致。如果代理只实现 `/videos/generations`，视频插件应使用
`api_format: xai`；只有代理同时实现 OpenAI `/videos` 协议时，才适合使用
OpenAI 视频模式。

## 功能

支持以下能力：

- 模型、网页搜索、图片和视频代理插件
- `x_search` 工具
- `xai_video_edit` 和 `xai_video_extend` 工具
- OpenAI/xAI 可选协议的 TTS 和 STT 代理插件

Hermes 不允许 Python 插件覆盖内置 TTS/STT 名称，因此 TTS 和 STT 使用项目自己的代理 provider 名称。

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
XAI_PROXY_API_FORMAT=openai
```

### 自定义附加参数

所有代理插件都支持在请求体中追加代理或上游专用字段。通用配置放在
`xai_proxy.extra_params` 下，键名对应请求类型；插件自己的 `extra_params`
会覆盖同名通用字段：

```yaml
xai_proxy:
  extra_params:
    images:
      n: 1
      aspect_ratio: "16:9"
      resolution: 2k
      response_format: url
      stream: false
    chat:
      temperature: 0.7
    responses: {}
    messages: {}
    videos:
      duration: 8
      resolution: 720p
    tts:
      with_timestamps: false
    stt: {}
    web: {}
```

支持的类型包括 `images`、`chat`、`responses`、`messages`、`videos`、`tts`、
`stt` 和 `web`。附加字段会原样转发；如果与 Hermes 已生成的字段同名，
附加参数优先，因此请只覆盖确实需要交给代理处理的字段。图片/视频插件仍由
Hermes 负责结果解析，配置 SSE 或异步行为前请确认对应 Hermes 版本支持该返回格式。

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

OpenAI 模式的 TTS 请求发送到 `POST $XAI_PROXY_BASE_URL/audio/speech`；xAI 模式发送到
`POST $XAI_PROXY_BASE_URL/tts`。语音列表接口不可用时，插件会使用内置语音列表作为回退。

## STT 配置

```yaml
stt:
  provider: xai-proxy
  xai-proxy:
    model: grok-stt
```

STT 请求以 OpenAI 兼容的 multipart 形式发送到
`POST $XAI_PROXY_BASE_URL/audio/transcriptions`；xAI 模式使用 `/stt`。

## 卸载

```bash
HERMES_HOME=/opt/data ./uninstall.sh
```

卸载脚本会将插件目录移动到带时间戳的备份目录，配置和环境变量不会自动删除。卸载后请手动禁用对应插件。

## 验证

通过 Hermes Git 安装后，插件会按 manifest 名称安装到 `/opt/data/plugins`：

```bash
hermes plugins validate /opt/data/plugins/xai-proxy-model
hermes plugins validate /opt/data/plugins/xai-proxy-web
hermes plugins validate /opt/data/plugins/xai-proxy-image
hermes plugins validate /opt/data/plugins/xai-proxy-video
hermes plugins validate /opt/data/plugins/xai-proxy-tools
hermes plugins validate /opt/data/plugins/xai-proxy-tts
hermes plugins validate /opt/data/plugins/xai-proxy-stt
hermes plugins capabilities xai-proxy-tools
```

只有使用 `install.sh` 手动复制时，才使用 `/opt/data/plugins/web/xai`、`/opt/data/plugins/image_gen/xai` 等源码目录路径。


## 运行时兼容性

网页、图片、视频和视频工具插件会复用当前 Hermes 安装中的内置 xAI 实现，不会复制上游代码。如果 Hermes 版本缺少预期的内置文件，插件会报告明确的版本/路径兼容性错误；请升级或使用匹配的 Hermes 版本。
## 英文文档

See [README.en.md](README.en.md).
