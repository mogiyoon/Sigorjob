from tools.base import BaseTool

_registry: dict[str, BaseTool] = {}


def register(tool: BaseTool):
    _registry[tool.name] = tool


def get(name: str) -> BaseTool | None:
    return _registry.get(name)


def list_tools() -> list[dict]:
    return [t.schema() for t in _registry.values()]


def load_default_tools():
    from tools.file.tool import FileTool
    from tools.shell.tool import ShellTool
    from tools.crawler.tool import CrawlerTool
    from tools.time.tool import TimeTool
    from tools.system_info.tool import SystemInfoTool
    from tools.browser.tool import BrowserTool
    from tools.browser_auto.tool import BrowserAutoTool

    register(FileTool())
    register(ShellTool())
    register(CrawlerTool())
    register(TimeTool())
    register(SystemInfoTool())
    register(BrowserTool())
    register(BrowserAutoTool())
