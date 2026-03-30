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


def validate_connection() -> tuple[bool, str | None]:
    client = get_client()
    if client is None:
        return False, "API key is not configured."

    try:
        client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
        return True, None
    except Exception as exc:
        return False, str(exc)
