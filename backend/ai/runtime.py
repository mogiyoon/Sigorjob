import anthropic

from config.settings import settings
from config.secret_store import secret_store


def get_api_key() -> str:
    return (secret_store.get("anthropic_api_key") or settings.anthropic_api_key or "").strip()


def has_api_key() -> bool:
    return bool(get_api_key())


def get_client() -> anthropic.Anthropic | None:
    api_key = get_api_key()
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)
