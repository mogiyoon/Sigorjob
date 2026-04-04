import re
from functools import lru_cache

try:
    from kiwipiepy import Kiwi
except ImportError:  # pragma: no cover - exercised via fallback behavior
    Kiwi = None


URL_PATTERN = re.compile(r"https?://[^\s가-힣]+", re.IGNORECASE)
URL_PARTICLE_FALLBACK_PATTERN = re.compile(
    r"(https?://[^\s가-힣]+)(?:에서의|으로의|부터의|까지의|에게의|한테의|이랑의|이나의|처럼의|만큼의|조차의|마저의|밖에의|에서|으로|부터|까지|에게|한테|이랑|이나|처럼|만큼|조차|마저|밖에|[을를이가은는도에의로서])\b",
    re.IGNORECASE,
)
KEYWORD_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")
FALLBACK_PARTICLE_SUFFIXES = (
    "에서의",
    "으로의",
    "부터의",
    "까지의",
    "에게의",
    "한테의",
    "이랑의",
    "이나의",
    "처럼의",
    "만큼의",
    "조차의",
    "마저의",
    "밖에의",
    "에게",
    "한테",
    "이랑",
    "처럼",
    "만큼",
    "조차",
    "마저",
    "밖에",
    "에서",
    "으로",
    "부터",
    "까지",
    "이나",
    "을",
    "를",
    "이",
    "가",
    "은",
    "는",
    "도",
    "에",
    "의",
    "로",
    "서",
)
FALLBACK_VERB_SUFFIXES = (
    "해줄래",
    "해 주세요",
    "해주세요",
    "해 줘",
    "해줘",
    "해라",
    "해",
    "줘",
)


@lru_cache(maxsize=1)
def _get_kiwi():
    if Kiwi is None:
        return None
    try:
        return Kiwi()
    except Exception:
        return None


def strip_particles_from_url(text: str) -> str:
    kiwi = _get_kiwi()
    if kiwi is None:
        return _strip_particles_from_url_regex(text)
    return _strip_particles_from_url_with_kiwi(text, kiwi)


def extract_keywords(text: str) -> list[str]:
    kiwi = _get_kiwi()
    if kiwi is None:
        return _extract_keywords_fallback(text)
    return _extract_keywords_with_kiwi(text, kiwi)


def _strip_particles_from_url_with_kiwi(text: str, kiwi) -> str:
    urls = list(URL_PATTERN.finditer(text))
    if not urls:
        return text

    try:
        tokens = kiwi.tokenize(text)
    except Exception:
        return _strip_particles_from_url_regex(text)

    removals: list[tuple[int, int]] = []
    for match in urls:
        current_end = match.end()
        removal_end = current_end
        for token in tokens:
            token_start = getattr(token, "start", None)
            token_len = getattr(token, "len", None)
            token_tag = getattr(token, "tag", "")
            if token_start is None or token_len is None:
                continue
            if token_start < current_end:
                continue
            if token_start != removal_end:
                break
            if not str(token_tag).startswith("J"):
                break
            removal_end = token_start + token_len
        if removal_end > current_end:
            removals.append((current_end, removal_end))

    if not removals:
        return text

    pieces: list[str] = []
    cursor = 0
    for start, end in removals:
        pieces.append(text[cursor:start])
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def _strip_particles_from_url_regex(text: str) -> str:
    return URL_PARTICLE_FALLBACK_PATTERN.sub(r"\1", text)


def _extract_keywords_with_kiwi(text: str, kiwi) -> list[str]:
    try:
        tokens = kiwi.tokenize(text)
    except Exception:
        return _extract_keywords_fallback(text)

    keywords: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        form = getattr(token, "form", "").strip()
        tag = str(getattr(token, "tag", ""))
        if not form:
            continue
        if tag.startswith("N") or tag.startswith("V"):
            if form not in seen:
                seen.add(form)
                keywords.append(form)
    return keywords


def _extract_keywords_fallback(text: str) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    for token in KEYWORD_TOKEN_PATTERN.findall(text):
        candidates = [token]
        verb_stem = _strip_first_matching_suffix(token, FALLBACK_VERB_SUFFIXES)
        if verb_stem != token:
            candidates.append(verb_stem)
        stripped = _strip_first_matching_suffix(token, FALLBACK_PARTICLE_SUFFIXES)
        if stripped != token:
            candidates.append(stripped)
        for candidate in candidates:
            candidate = candidate.strip()
            if len(candidate) < 2 or candidate in seen:
                continue
            seen.add(candidate)
            keywords.append(candidate)
    return keywords


def _strip_first_matching_suffix(token: str, suffixes: tuple[str, ...]) -> str:
    for suffix in suffixes:
        if token.endswith(suffix) and len(token) > len(suffix):
            return token[: -len(suffix)]
    return token
