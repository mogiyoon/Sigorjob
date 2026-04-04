from __future__ import annotations

import importlib.util
import sys

PLAYWRIGHT_PIP_INSTALL_COMMAND = "pip install playwright"
PLAYWRIGHT_BROWSER_INSTALL_COMMAND = f"{sys.executable} -m playwright install chromium"


def check_playwright_status() -> dict[str, object]:
    installed = importlib.util.find_spec("playwright") is not None
    return {
        "installed": installed,
        "browsers_installed": installed,
        "install_command": PLAYWRIGHT_PIP_INSTALL_COMMAND,
        "browser_install_command": PLAYWRIGHT_BROWSER_INSTALL_COMMAND,
    }


if __name__ == "__main__":
    from cli import main as cli_main

    check_playwright_status()
    raise SystemExit(cli_main())
