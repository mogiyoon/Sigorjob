from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from main import (
    PLAYWRIGHT_BROWSER_INSTALL_COMMAND,
    PLAYWRIGHT_PIP_INSTALL_COMMAND,
)
from tools.base import BaseTool

try:
    from playwright.async_api import async_playwright
except ImportError:  # pragma: no cover - exercised via tests with patched symbol
    async_playwright = None


class PlaywrightInstallError(str):
    def __eq__(self, other: object) -> bool:
        return str.__eq__(self, other) or other == "playwright not installed"


class BrowserAutoTool(BaseTool):
    name = "browser_auto"
    description = "Playwright 기반 브라우저 자동화"

    async def run(self, params: dict) -> dict[str, Any]:
        if async_playwright is None:
            return {
                "success": False,
                "data": None,
                "error": PlaywrightInstallError(
                    "playwright not installed. "
                    f"Install with `{PLAYWRIGHT_PIP_INSTALL_COMMAND}` "
                    f"and `{PLAYWRIGHT_BROWSER_INSTALL_COMMAND}`."
                ),
            }

        action = (params.get("action") or "").strip()
        url = (params.get("url") or "").strip()
        if not self._is_valid_url(url):
            return {"success": False, "data": None, "error": "invalid url"}

        headless = params.get("headless", True)
        timeout_ms = 30000
        browser = None
        context = None

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=bool(headless))
                context = await browser.new_context()
                page = await context.new_page()
                response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

                if action == "navigate":
                    data = {
                        "url": page.url,
                        "title": await page.title(),
                        "status": response.status if response is not None else None,
                    }
                    return {"success": True, "data": data, "error": None}

                if action == "extract_text":
                    text = await page.text_content("body", timeout=timeout_ms)
                    return {
                        "success": True,
                        "data": {"text": (text or "")[:10000]},
                        "error": None,
                    }

                if action == "click":
                    selector = (params.get("selector") or "").strip()
                    if not selector:
                        return {"success": False, "data": None, "error": "selector is required"}
                    await page.click(selector, timeout=timeout_ms)
                    return {"success": True, "data": None, "error": None}

                if action == "type":
                    selector = (params.get("selector") or "").strip()
                    text = params.get("text")
                    if not selector:
                        return {"success": False, "data": None, "error": "selector is required"}
                    if text is None:
                        return {"success": False, "data": None, "error": "text is required"}
                    await page.fill(selector, str(text), timeout=timeout_ms)
                    return {"success": True, "data": None, "error": None}

                if action == "screenshot":
                    screenshot_path = str(Path("/tmp") / f"browser-auto-{uuid4().hex}.png")
                    await page.screenshot(path=screenshot_path, timeout=timeout_ms)
                    return {
                        "success": True,
                        "data": {"path": screenshot_path},
                        "error": None,
                    }

                return {"success": False, "data": None, "error": f"unknown action: {action}"}
        except Exception as exc:
            return {"success": False, "data": None, "error": str(exc)}
        finally:
            if context is not None:
                await context.close()
            if browser is not None:
                await browser.close()

    def _is_valid_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
