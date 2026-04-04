from __future__ import annotations


_OAUTH_SCOPES: dict[str, tuple[str, ...]] = {
    "gmail": (
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.readonly",
    ),
    "google_calendar": (
        "https://www.googleapis.com/auth/calendar",
    ),
}


def get_scopes_for_connection(connection_id: str) -> list[str] | None:
    scopes = _OAUTH_SCOPES.get(connection_id.strip())
    if not scopes:
        return None
    return list(scopes)
