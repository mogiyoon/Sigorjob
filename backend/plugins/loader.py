import importlib.util
import json
from pathlib import Path
from typing import Any

import yaml

from logger.logger import get_logger
from tools import registry

logger = get_logger(__name__)

_loaded = False
_plugin_rules: list[dict] = []
_ai_instructions: list[str] = []
_plugin_info: list[dict[str, Any]] = []


def plugins_root() -> Path:
    return Path(__file__).resolve().parent


def discover_plugin_dirs() -> list[Path]:
    root = plugins_root()
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith("_") and path.name != "__pycache__"
    )


def load_plugins() -> None:
    global _loaded, _plugin_rules, _ai_instructions, _plugin_info
    if _loaded:
        return

    _plugin_rules = []
    _ai_instructions = []
    _plugin_info = []

    for plugin_dir in discover_plugin_dirs():
        manifest = _load_manifest(plugin_dir)
        plugin_name = manifest.get("name") or plugin_dir.name
        plugin_description = manifest.get("description") or ""
        loaded_parts: list[str] = []

        plugin_file = plugin_dir / "plugin.py"
        if plugin_file.exists():
            _load_python_plugin(plugin_name, plugin_file)
            loaded_parts.append("tool")

        rules_file = plugin_dir / "rules.yaml"
        if rules_file.exists():
            rules = _load_rules_file(rules_file)
            if rules:
                _plugin_rules.extend(rules)
                loaded_parts.append("rules")

        ai_file = plugin_dir / "ai_instructions.md"
        if ai_file.exists():
            text = ai_file.read_text(encoding="utf-8").strip()
            if text:
                _ai_instructions.append(f"[{plugin_name}]\n{text}")
                loaded_parts.append("ai")

        if loaded_parts:
            logger.info(f"loaded plugin '{plugin_name}' ({', '.join(loaded_parts)})")

        _plugin_info.append(
            {
                "name": plugin_name,
                "description": plugin_description,
                "path": str(plugin_dir),
                "capabilities": loaded_parts,
                "permissions": manifest.get("permissions", []),
            }
        )

    _loaded = True


def load_plugin_rules() -> list[dict]:
    load_plugins()
    return list(_plugin_rules)


def get_ai_instructions() -> str:
    load_plugins()
    return "\n\n".join(part for part in _ai_instructions if part).strip()


def describe_plugins() -> list[dict[str, Any]]:
    load_plugins()
    return list(_plugin_info)


def scaffold_plugin(name: str, *, plugin_type: str = "hybrid") -> Path:
    safe_name = _sanitize_plugin_name(name)
    plugin_dir = plugins_root() / safe_name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    manifest = plugin_dir / "plugin.json"
    if not manifest.exists():
        manifest.write_text(
            json.dumps(
                {
                    "name": safe_name,
                    "description": "Custom Sigorjob plugin",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    readme = plugin_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Plugin\n\n"
            "Add your non-AI rules, custom tools, or AI instructions here.\n"
            "- `plugin.py`: optional Python tool registration\n"
            "- `rules.yaml`: optional non-AI intent rules\n"
            "- `ai_instructions.md`: optional extra AI planning guidance\n",
            encoding="utf-8",
        )

    if plugin_type in {"tool", "hybrid"}:
        plugin_py = plugin_dir / "plugin.py"
        if not plugin_py.exists():
            plugin_py.write_text(
                "from tools.base import BaseTool\n\n\n"
                "class ExampleTool(BaseTool):\n"
                "    name = \"example_" + safe_name + "\"\n"
                "    description = \"Example custom plugin tool\"\n\n"
                "    async def run(self, params: dict) -> dict:\n"
                "        text = (params.get(\"text\") or \"\").strip()\n"
                "        return {\n"
                "            \"success\": True,\n"
                "            \"data\": {\n"
                "                \"message\": text or \"plugin tool executed\",\n"
                "            },\n"
                "            \"error\": None,\n"
                "        }\n\n\n"
                "def register_tools(register):\n"
                "    register(ExampleTool())\n",
                encoding="utf-8",
            )

    if plugin_type in {"rules", "hybrid"}:
        rules_yaml = plugin_dir / "rules.yaml"
        if not rules_yaml.exists():
            rules_yaml.write_text(
                "rules:\n"
                "  - name: example_" + safe_name + "_rule\n"
                "    pattern: \"example " + safe_name + " (.+)\"\n"
                "    tool: \"example_" + safe_name + "\"\n"
                "    params:\n"
                "      text: \"{match_1}\"\n",
                encoding="utf-8",
            )

    ai_md = plugin_dir / "ai_instructions.md"
    if not ai_md.exists():
        ai_md.write_text(
            "# AI Instructions\n\n"
            "Describe when the AI planner should prefer your plugin tool or rules.\n",
            encoding="utf-8",
        )

    return plugin_dir


def _load_manifest(plugin_dir: Path) -> dict[str, Any]:
    manifest = plugin_dir / "plugin.json"
    if not manifest.exists():
        return {}
    try:
        return json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"failed to read plugin manifest for {plugin_dir.name}: {exc}")
        return {}


def _load_python_plugin(plugin_name: str, plugin_file: Path) -> None:
    module_name = f"sigorjob_plugin_{plugin_name}"
    spec = importlib.util.spec_from_file_location(module_name, plugin_file)
    if spec is None or spec.loader is None:
        logger.warning(f"failed to create plugin spec for {plugin_name}")
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    register_tools = getattr(module, "register_tools", None)
    if callable(register_tools):
        register_tools(registry.register)
    else:
        logger.warning(f"plugin '{plugin_name}' does not expose register_tools(register)")


def _load_rules_file(rules_file: Path) -> list[dict]:
    try:
        data = yaml.safe_load(rules_file.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning(f"failed to load plugin rules from {rules_file}: {exc}")
        return []
    if isinstance(data, dict):
        return list(data.get("rules", []))
    if isinstance(data, list):
        return list(data)
    return []


def _sanitize_plugin_name(name: str) -> str:
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in name.strip().lower())
    sanitized = sanitized.strip("._-")
    return sanitized or "custom_plugin"
