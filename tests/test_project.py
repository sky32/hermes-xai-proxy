import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_plugin(relative_path, modules):
    saved = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        name = "test_plugin_" + relative_path.replace("/", "_").replace("-", "_")
        spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, old in saved.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


def hermes_stubs(values=None, config=None):
    values = values or {}
    config = config or {}
    hermes = types.ModuleType("hermes_cli")
    hermes_config = types.ModuleType("hermes_cli.config")
    hermes_config.get_env_value = lambda key: values.get(key, "")
    hermes_config.load_config = lambda: config
    hermes.config = hermes_config
    return {"hermes_cli": hermes, "hermes_cli.config": hermes_config}


class FakeTTSProvider:
    pass


class FakeSTTProvider:
    pass


class ProjectTests(unittest.TestCase):
    def test_manifests_and_config(self):
        config = yaml.safe_load((ROOT / "config.example.yaml").read_text())
        enabled = config["plugins"]["enabled"]
        plugin_dirs = [
            "plugins/model-providers/xai",
            "plugins/web/xai",
            "plugins/image_gen/xai",
            "plugins/video_gen/xai",
            "plugins/xai-proxy-tools",
            "plugins/xai-proxy-tts",
            "plugins/transcription/xai-proxy",
        ]
        self.assertEqual(len(enabled), len(plugin_dirs))
        for directory in plugin_dirs:
            path = ROOT / directory
            self.assertTrue((path / "plugin.yaml").is_file())
            self.assertTrue((path / "__init__.py").is_file())
            manifest = yaml.safe_load((path / "plugin.yaml").read_text())
            self.assertTrue(manifest.get("name"))
            self.assertTrue(manifest.get("version"))
            for requirement in manifest.get("requires_env", []):
                self.assertIsInstance(requirement, dict)
                self.assertIn("name", requirement)
                self.assertIn("secret", requirement)
            self.assertIn(manifest["name"], enabled)

        self.assertEqual(config["model"]["default"], "grok-4.7")
        self.assertEqual(config["tts"]["xai-proxy"]["model"], "grok-voice-think-fast-2.0")
        self.assertEqual(config["stt"]["xai-proxy"]["model"], "grok-stt")

    def test_stt_defaults_and_missing_config(self):
        modules = hermes_stubs()
        modules["agent"] = types.ModuleType("agent")
        transcription = types.ModuleType("agent.transcription_provider")
        transcription.TranscriptionProvider = FakeSTTProvider
        modules["agent.transcription_provider"] = transcription
        module = load_plugin("plugins/transcription/xai-proxy/__init__.py", modules)
        provider = module.XAIProxySTTProvider()
        self.assertEqual(provider.default_model(), "grok-stt")
        result = provider.transcribe("missing.wav")
        self.assertFalse(result["success"])
        self.assertIn("not configured", result["error"])

    def test_stt_invalid_timeout_uses_default(self):
        modules = hermes_stubs({"XAI_PROXY_STT_TIMEOUT": "not-a-number"})
        modules["agent"] = types.ModuleType("agent")
        transcription = types.ModuleType("agent.transcription_provider")
        transcription.TranscriptionProvider = FakeSTTProvider
        modules["agent.transcription_provider"] = transcription
        module = load_plugin("plugins/transcription/xai-proxy/__init__.py", modules)
        self.assertEqual(module._float_env("XAI_PROXY_STT_TIMEOUT", 180), 180)

    def test_tts_missing_config_and_network_error(self):
        modules = hermes_stubs()
        modules["agent"] = types.ModuleType("agent")
        tts = types.ModuleType("agent.tts_provider")
        tts.TTSProvider = FakeTTSProvider
        modules["agent.tts_provider"] = tts
        module = load_plugin("plugins/xai-proxy-tts/__init__.py", modules)
        provider = module.XAIProxyTTSProvider()
        with self.assertRaisesRegex(RuntimeError, "not configured"):
            provider.synthesize("hello", "out.mp3")

        values = {"XAI_PROXY_BASE_URL": "https://proxy.example/v1", "XAI_PROXY_API_KEY": "secret-key"}
        modules = hermes_stubs(values)
        modules["agent"] = types.ModuleType("agent")
        modules["agent.tts_provider"] = tts
        module = load_plugin("plugins/xai-proxy-tts/__init__.py", modules)
        provider = module.XAIProxyTTSProvider()
        with patch.object(module.requests, "post", side_effect=module.requests.RequestException("connection failed")):
            with self.assertRaisesRegex(RuntimeError, "request failed") as error:
                provider.synthesize("hello", "out.mp3")
        self.assertNotIn("secret-key", str(error.exception))

    def test_tools_return_safe_errors(self):
        modules = hermes_stubs()
        module = load_plugin("plugins/xai-proxy-tools/__init__.py", modules)
        result = json.loads(module._x_search({"query": "hello"}))
        self.assertFalse(result["success"])
        self.assertIn("not configured", result["error"])
        video = json.loads(module._video_edit({"prompt": "x", "video_url": "y"}))
        self.assertFalse(video["success"])

        values = {"XAI_PROXY_BASE_URL": "https://proxy.example/v1", "XAI_PROXY_API_KEY": "secret-key"}
        modules = hermes_stubs(values)
        module = load_plugin("plugins/xai-proxy-tools/__init__.py", modules)
        with patch.object(module.requests, "post", side_effect=module.requests.RequestException("secret-key connection failed")):
            result = json.loads(module._x_search({"query": "hello"}))
        self.assertFalse(result["success"])
        self.assertNotIn("secret-key", result["error"])

    def test_dynamic_loader_has_actionable_error(self):
        modules = hermes_stubs()
        module = load_plugin("plugins/web/xai/__init__.py", modules)
        with patch.dict(sys.modules, {"hermes_cli": None}):
            with self.assertRaisesRegex(RuntimeError, "installed Hermes package"):
                module._bundled_file("plugins", "web", "xai", "provider.py")

    def test_no_legacy_model_names_in_project(self):
        forbidden = ("grok-" + "4.6", "grok-" + "tts", "grok-voice-" + "transcribe-2.0")
        for path in ROOT.rglob("*"):
            if ".git" in path.parts or ".pi" in path.parts or not path.is_file():
                continue
            if path.suffix not in {".py", ".yaml", ".md", ".env"}:
                continue
            text = path.read_text(errors="ignore")
            for value in forbidden:
                self.assertNotIn(value, text, f"legacy model in {path}")


if __name__ == "__main__":
    unittest.main()
