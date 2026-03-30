import re
from dataclasses import dataclass
from urllib.parse import quote_plus


SEARCH_KEYWORDS = ("검색", "search", "찾아", "찾아줘", "알아봐", "보여줘")
NEWS_KEYWORDS = ("뉴스", "기사", "헤드라인", "보도")
CRAWL_KEYWORDS = ("크롤링", "읽어", "가져와", "수집", "fetch", "scrape")
AUTOMATION_KEYWORDS = (
    "알림",
    "보내줘",
    "보내 줄래",
    "알려줘",
    "알려 줄래",
    "매일",
    "매주",
    "스케줄",
    "예약",
    "오전",
    "오후",
    "아침",
    "저녁",
    "밤",
)
SHOPPING_KEYWORDS = (
    "사줘",
    "사 줘",
    "구매해줘",
    "구매해 줘",
    "구매해줄래",
    "구매해 줄래",
    "주문해줘",
    "주문해 줘",
    "주문해줄래",
    "주문해 줄래",
    "결제해줘",
    "결제해 줘",
)
SHOPPING_DISCOVERY_KEYWORDS = (
    "최저가",
    "가장 싼",
    "제일 싼",
    "쇼핑",
    "구매 링크",
    "구매페이지",
    "구매 페이지",
    "바로 살 수 있게",
    "바로 구매",
    "살 수 있게",
    "주문할 수 있게",
    "결제할 수 있게",
    "장바구니",
    "상품 페이지",
)
EMAIL_SEND_KEYWORDS = (
    "메일 보내줘",
    "메일 보내 줘",
    "이메일 보내줘",
    "이메일 보내 줘",
    "메일 보내줄래",
    "메일 보내 줄래",
    "이메일 보내줄래",
    "이메일 보내 줄래",
    "메일 보내",
    "이메일 보내",
    "메일 전송",
    "이메일 전송",
    "보내달라",
    "보내 달라",
    "보내달라고",
    "보내 달라고",
)
TIME_KEYWORDS = ("지금 몇 시", "현재 시간", "what time is it", "current time")
DATE_KEYWORDS = ("오늘 날짜", "현재 날짜", "date today", "today's date")
SYSTEM_KEYWORDS = ("시스템 정보", "system info", "현재 시스템")
PWD_KEYWORDS = ("현재 경로", "현재 위치", "working directory")
LS_KEYWORDS = (
    "현재 폴더 목록",
    "파일 목록 보여줘",
    "디렉터리 목록",
    "list files",
    "폴더 목록",
    "폴더 보여줘",
    "디렉터리 보여줘",
)
OPEN_KEYWORDS = ("열어줘", "열어 줘", "열어", "접속해줘", "접속해 줘", "이동해줘", "이동해 줘", "open")
SITE_ALIASES = {
    "네이버": "https://www.naver.com",
    "구글": "https://www.google.com",
    "유튜브": "https://www.youtube.com",
    "깃허브": "https://github.com",
    "github": "https://github.com",
    "나무위키": "https://namu.wiki",
}
SHOPPING_SITE_ALIASES = {
    "네이버": ("네이버 쇼핑", "https://search.shopping.naver.com/search/all?query={query}"),
    "naver": ("네이버 쇼핑", "https://search.shopping.naver.com/search/all?query={query}"),
    "쿠팡": ("쿠팡", "https://www.coupang.com/np/search?q={query}"),
    "coupang": ("쿠팡", "https://www.coupang.com/np/search?q={query}"),
    "11번가": ("11번가", "https://search.11st.co.kr/Search.tmall?kwd={query}"),
    "11st": ("11번가", "https://search.11st.co.kr/Search.tmall?kwd={query}"),
    "g마켓": ("G마켓", "https://browse.gmarket.co.kr/search?keyword={query}"),
    "gmarket": ("G마켓", "https://browse.gmarket.co.kr/search?keyword={query}"),
}
SHOPPING_PLATFORM_IDS = {
    "네이버": "naver",
    "naver": "naver",
    "쿠팡": "coupang",
    "coupang": "coupang",
    "11번가": "11st",
    "11st": "11st",
    "g마켓": "gmarket",
    "gmarket": "gmarket",
}
SERVICE_SEARCH_ALIASES = {
    "유튜브": ("유튜브", "https://www.youtube.com/results?search_query={query}"),
    "youtube": ("유튜브", "https://www.youtube.com/results?search_query={query}"),
    "깃허브": ("깃허브", "https://github.com/search?q={query}&type=repositories"),
    "github": ("깃허브", "https://github.com/search?q={query}&type=repositories"),
    "나무위키": ("나무위키", "https://namu.wiki/Search?q={query}"),
    "네이버": ("네이버", "https://search.naver.com/search.naver?query={query}"),
    "naver": ("네이버", "https://search.naver.com/search.naver?query={query}"),
}
PLACE_HINT_KEYWORDS = (
    "맛집",
    "식당",
    "카페",
    "병원",
    "약국",
    "호텔",
    "숙소",
    "펜션",
    "미용실",
    "헬스장",
    "주유소",
    "편의점",
    "근처",
)


@dataclass
class NormalizedIntent:
    category: str
    command: str
    params: dict
    description: str


def normalize_command(command: str) -> str:
    normalized = re.sub(r"\s+", " ", command).strip()
    normalized = re.sub(r"(https?://[^\s가-힣]+)[을를이가은는]\b", r"\1", normalized)
    return normalized


def detect_intent(command: str) -> NormalizedIntent | None:
    normalized = normalize_command(command)
    lowered = normalized.lower()

    url = _extract_url(normalized)
    open_target = _extract_open_target_intent(normalized)
    if open_target:
        return NormalizedIntent(
            category="open_url",
            command=normalized,
            params=open_target,
            description="open_url",
        )

    if url and any(keyword in lowered for keyword in CRAWL_KEYWORDS):
        return NormalizedIntent(
            category="crawl",
            command=normalized,
            params={"url": url},
            description="crawl_url_flexible",
        )

    if normalized == "pwd" or any(keyword in normalized for keyword in PWD_KEYWORDS):
        return NormalizedIntent(
            category="shell_pwd",
            command=normalized,
            params={"command": "pwd"},
            description="shell_pwd",
        )

    if normalized == "ls" or any(keyword in normalized for keyword in LS_KEYWORDS):
        list_path = _extract_list_path_intent(normalized)
        return NormalizedIntent(
            category="shell_ls_path" if list_path else "shell_ls",
            command=normalized,
            params={"command": f"ls {list_path}" if list_path else "ls"},
            description="shell_ls_path" if list_path else "shell_ls",
        )

    file_read = _extract_file_read_intent(normalized)
    if file_read:
        return NormalizedIntent(
            category="file_read",
            command=normalized,
            params={"operation": "read", "path": file_read},
            description="file_read_flexible",
        )

    file_write = _extract_file_write_intent(normalized)
    if file_write:
        return NormalizedIntent(
            category="file_write",
            command=normalized,
            params={
                "operation": "write",
                "path": file_write["path"],
                "content": file_write["content"],
            },
            description="file_write_flexible",
        )

    file_copy = _extract_file_copy_move_intent(normalized, operation="copy")
    if file_copy:
        return NormalizedIntent(
            category="file_copy",
            command=normalized,
            params={"operation": "copy", "src": file_copy["src"], "dst": file_copy["dst"]},
            description="file_copy_flexible",
        )

    file_move = _extract_file_copy_move_intent(normalized, operation="move")
    if file_move:
        return NormalizedIntent(
            category="file_move",
            command=normalized,
            params={"operation": "move", "src": file_move["src"], "dst": file_move["dst"]},
            description="file_move_flexible",
        )

    file_delete = _extract_file_delete_intent(normalized)
    if file_delete:
        return NormalizedIntent(
            category="file_delete",
            command=normalized,
            params={"operation": "delete", "path": file_delete},
            description="file_delete_flexible",
        )

    if any(keyword in lowered for keyword in TIME_KEYWORDS):
        return NormalizedIntent(
            category="time",
            command=normalized,
            params={},
            description="current_time",
        )

    if any(keyword in lowered for keyword in DATE_KEYWORDS):
        return NormalizedIntent(
            category="time",
            command=normalized,
            params={},
            description="current_date",
        )

    if any(keyword in lowered for keyword in SYSTEM_KEYWORDS):
        return NormalizedIntent(
            category="system_info",
            command=normalized,
            params={},
            description="system_info",
        )

    email_action = _extract_email_send_intent(normalized)
    if email_action:
        return NormalizedIntent(
            category="open_url",
            command=normalized,
            params=email_action,
            description="email_send",
        )

    reminder_schedule = _extract_reminder_schedule_intent(normalized)
    if reminder_schedule:
        return NormalizedIntent(
            category="reminder_schedule",
            command=normalized,
            params=reminder_schedule,
            description="reminder_schedule",
        )

    shopping_query = _extract_shopping_query(normalized)
    if shopping_query:
        return NormalizedIntent(
            category="shopping_search",
            command=normalized,
            params=shopping_query,
            description="shopping_search",
        )

    place_query = _extract_place_search_intent(normalized)
    if place_query:
        return NormalizedIntent(
            category="open_url",
            command=normalized,
            params=place_query,
            description="place_search",
        )

    service_search = _extract_service_search_intent(normalized)
    if service_search:
        return NormalizedIntent(
            category="open_url",
            command=normalized,
            params=service_search,
            description="service_search",
        )

    news_query = _extract_news_query(normalized)
    if news_query:
        return NormalizedIntent(
            category="search",
            command=normalized,
            params={"url": _build_google_news_rss_url(news_query, normalized)},
            description="search_news",
        )

    search_query = _extract_search_query(normalized)
    if search_query:
        return NormalizedIntent(
            category="search",
            command=normalized,
            params={"url": f"https://www.google.com/search?q={quote_plus(search_query)}"},
            description="search_web",
        )

    return None


def build_last_resort_intent(command: str) -> NormalizedIntent | None:
    normalized = normalize_command(command)
    if not normalized:
        return None

    if _looks_like_automation_request(normalized):
        return None

    shopping_query = _extract_shopping_query(normalized)
    if shopping_query:
        return NormalizedIntent(
            category="shopping_search",
            command=normalized,
            params=shopping_query,
            description="shopping_search_fallback",
        )

    search_query = _sanitize_general_search_query(normalized)
    if not search_query:
        return None

    return NormalizedIntent(
        category="open_url",
        command=normalized,
        params={
            "url": f"https://www.google.com/search?q={quote_plus(search_query)}",
            "title": "검색 결과 열기",
        },
        description="generic_search_fallback",
    )


def _looks_like_automation_request(command: str) -> bool:
    lowered = command.lower()
    if any(keyword in command or keyword in lowered for keyword in AUTOMATION_KEYWORDS):
        if not any(keyword in command or keyword in lowered for keyword in SEARCH_KEYWORDS):
            return True
    return bool(re.search(r"(오전|오후|아침|저녁|밤)?\s*\d{1,2}시", command))


def _extract_url(command: str) -> str | None:
    match = re.search(r"https?://[^\s가-힣]+", command, re.IGNORECASE)
    if not match:
        return None
    return match.group(0).rstrip(".,)")


def _extract_open_target_intent(command: str) -> dict | None:
    lowered = command.lower()
    if not any(keyword in command or keyword in lowered for keyword in OPEN_KEYWORDS):
        return None

    url = _extract_url(command)
    if url:
        return {"url": url, "title": "링크 열기"}

    target = command
    target = re.sub(r"\s*(열어줘|열어 줘|열어|접속해줘|접속해 줘|이동해줘|이동해 줘|open)\s*$", "", target, flags=re.IGNORECASE)
    target = re.sub(r"\s*(사이트|페이지|홈페이지)\s*$", "", target, flags=re.IGNORECASE)
    target = target.strip(" \"'")

    if not target:
        return None

    for name, site_url in SITE_ALIASES.items():
        if target.lower() == name.lower():
            return {"url": site_url, "title": f"{name} 열기"}

    return None


def _extract_search_query(command: str) -> str | None:
    lowered = command.lower()
    if not any(keyword in command or keyword in lowered for keyword in SEARCH_KEYWORDS):
        return None

    query = command.strip()
    query = re.sub(r"^구글에서\s*", "", query, flags=re.IGNORECASE)
    query = re.sub(r"^google(?:에서)?\s*", "", query, flags=re.IGNORECASE)
    query = re.sub(r"\s*(검색해줄래|검색해 줄래|검색해줘|검색해 줘|검색해|검색)\s*$", "", query, flags=re.IGNORECASE)
    query = re.sub(
        r"\s*(찾아줄래|찾아 줄래|찾아줘|찾아 줘|찾아|알아봐줄래|알아봐 줄래|알아봐줘|알아봐 줘|알아봐|보여줄래|보여 줄래|보여줘|보여 줘)\s*$",
        "",
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(r"\s*(search for|search)\s*$", "", query, flags=re.IGNORECASE)
    query = query.strip(" \"'")

    if len(query) < 2:
        return None
    return query


def _extract_email_send_intent(command: str) -> dict | None:
    lowered = command.lower()
    if not any(keyword in command or keyword in lowered for keyword in EMAIL_SEND_KEYWORDS):
        return None

    match = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", command)
    if not match:
        return None

    recipient = match.group(1)
    body = ""
    body_match = re.search(
        r"(?:메일|이메일)\s*(?:보내줘|보내 줘|보내줄래|보내 줄래)\s*[:：]?\s*(.+)$",
        command,
        re.IGNORECASE,
    )
    if body_match:
        body = body_match.group(1).strip().strip("\"'")
        if recipient in body:
            body = ""

    mailto = f"mailto:{recipient}"
    if body:
        mailto = f"{mailto}?body={quote_plus(body)}"

    return {
        "url": mailto,
        "title": f"{recipient}에 메일 보내기",
    }


def _extract_reminder_schedule_intent(command: str) -> dict | None:
    lowered = command.lower()
    if not re.search(r"(오전|오후|아침|저녁|밤)?\s*\d{1,2}시(?:\s*\d{1,2}분)?", command):
        return None
    if not any(
        keyword in command or keyword in lowered
        for keyword in (
            "알람",
            "알림",
            "리마인드",
            "알려줘",
            "보내줘",
            "보내 줄래",
        )
    ):
        return None
    if any(keyword in command for keyword in ("날씨", "기상청")):
        return None
    return {"text": command}


def _extract_shopping_query(command: str) -> dict | None:
    lowered = command.lower()
    if not _looks_like_shopping_request(command):
        return None

    platform_key, platform_name, url_template = _detect_shopping_platform(command)
    query = command.strip()
    query = re.sub(r"^(네이버|naver|쿠팡|coupang|11번가|11st|g마켓|gmarket)에서\s*", "", query, flags=re.IGNORECASE)
    lowest_price = bool(re.search(r"(최저가|가장\s*싼|제일\s*싼)", query, re.IGNORECASE))
    query = re.sub(r"\s*(최저가|가장\s*싼|제일\s*싼)\s*", " ", query, flags=re.IGNORECASE)
    query = re.sub(
        r"\s*(찾아서|찾아서 바로|찾아서 곧바로|찾아줘|찾아 줘|찾아줄래|찾아 줄래|찾아)\s*",
        " ",
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(
        r"\s*(바로\s*)?(살 수 있게|구매할 수 있게|구매할수 있게|주문할 수 있게|결제할 수 있게)\s*",
        " ",
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(
        r"\s*(바로\s*)?(살 수 있게|구매할 수 있게|구매할수 있게|주문할 수 있게|결제할 수 있게|사기 쉽게|세팅해줘|세팅해 줘|세팅해줄래|세팅해 줄래|준비해줘|준비해 줘|준비해줄래|준비해 줄래|링크 줘|링크 보여줘|링크 보여 줘|페이지 열어줘|페이지 열어 줘)\s*$",
        "",
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(
        r"\s*(사줘|사 줘|구매해줘|구매해 줘|구매해줄래|구매해 줄래|주문해줘|주문해 줘|주문해줄래|주문해 줄래|결제해줘|결제해 줘)\s*$",
        "",
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(r"\s*(상품|물건)\s*", " ", query)
    query = re.sub(r"\s+", " ", query).strip(" \"'")
    if len(query) < 2:
        return None

    url = url_template.format(query=quote_plus(query))
    if lowest_price and platform_key == "naver":
        url = f"{url}&sort=price_asc"

    return {
        "platform": platform_key,
        "query": query,
        "prefer_lowest_price": lowest_price,
        "purchase_intent": True,
        "url": url,
        "title": f"{platform_name}에서 {query}{' 최저가' if lowest_price else ''} 찾기",
    }


def _extract_service_search_intent(command: str) -> dict | None:
    lowered = command.lower()
    if not any(keyword in command or keyword in lowered for keyword in SEARCH_KEYWORDS):
        return None

    for alias, (service_name, url_template) in SERVICE_SEARCH_ALIASES.items():
        if not re.match(rf"^\s*{re.escape(alias)}(?:에서)?\s+", command, re.IGNORECASE):
            continue
        query = command.strip()
        query = re.sub(
            rf"^{re.escape(alias)}(?:에서)?\s*",
            "",
            query,
            flags=re.IGNORECASE,
        )
        query = re.sub(r"\s*(검색해줄래|검색해 줄래|검색해줘|검색해 줘|검색해|검색)\s*$", "", query, flags=re.IGNORECASE)
        query = re.sub(
            r"\s*(찾아줄래|찾아 줄래|찾아줘|찾아 줘|찾아|알아봐줄래|알아봐 줄래|알아봐줘|알아봐 줘|알아봐|보여줄래|보여 줄래|보여줘|보여 줘)\s*$",
            "",
            query,
            flags=re.IGNORECASE,
        )
        query = re.sub(r"\s+", " ", query).strip(" \"'")
        if len(query) < 2:
            return None
        return {
            "url": url_template.format(query=quote_plus(query)),
            "title": f"{service_name}에서 {query} 찾기",
        }
    return None


def _extract_place_search_intent(command: str) -> dict | None:
    lowered = command.lower()
    if not (
        any(keyword in command or keyword in lowered for keyword in SEARCH_KEYWORDS)
        or "추천" in command
        or "근처" in command
    ):
        return None
    if not any(keyword in command for keyword in PLACE_HINT_KEYWORDS):
        return None

    query = command.strip()
    query = re.sub(r"^(네이버 지도|네이버지도|구글 지도|구글지도|google maps|google map)\s*(에서)?\s*", "", query, flags=re.IGNORECASE)
    query = re.sub(r"\s*(검색해줄래|검색해 줄래|검색해줘|검색해 줘|검색해|검색)\s*$", "", query, flags=re.IGNORECASE)
    query = re.sub(
        r"\s*(찾아줄래|찾아 줄래|찾아줘|찾아 줘|찾아|알아봐줄래|알아봐 줄래|알아봐줘|알아봐 줘|알아봐|보여줄래|보여 줄래|보여줘|보여 줘|추천해줄래|추천해 줄래|추천해줘|추천해 줘|추천해)\s*$",
        "",
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(r"\s+", " ", query).strip(" \"'")
    if len(query) < 2:
        return None

    if any(marker in lowered for marker in ("네이버 지도", "네이버지도")):
        return {
            "url": f"https://map.naver.com/p/search/{quote_plus(query)}",
            "title": f"네이버 지도에서 {query} 찾기",
        }

    return {
        "url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}",
        "title": f"지도에서 {query} 찾기",
    }


def _extract_news_query(command: str) -> str | None:
    lowered = command.lower()
    if not any(keyword in command or keyword in lowered for keyword in SEARCH_KEYWORDS):
        return None
    if not any(keyword in command for keyword in NEWS_KEYWORDS):
        return None

    query = _extract_search_query(command)
    if not query:
        return None

    query = re.sub(r"\s*(뉴스|기사|헤드라인|보도)\s*", " ", query)
    query = re.sub(r"\s*(일주일 간|일주일간|1주일 간|1주일간|최근 일주일|7일 간|7일간|최근 한달|한달 간|한달간|1달 간|1달간)\s*", " ", query)
    query = re.sub(r"\s*(관련 내용|관련)\s*", " ", query)
    query = re.sub(r"\s+", " ", query).strip(" \"'")
    if len(query) < 2:
        return None
    return query


def _build_google_news_rss_url(query: str, command: str) -> str:
    filters: list[str] = []
    if any(keyword in command for keyword in ("일주일", "1주일", "7일", "최근 일주일")):
        filters.append("when:7d")
    elif any(keyword in command for keyword in ("한달", "1달", "1개월", "최근 한달")):
        filters.append("when:30d")
    elif any(keyword in command for keyword in ("오늘", "금일")):
        filters.append("when:1d")

    full_query = query
    if filters:
        full_query = f"{query} {' '.join(filters)}"

    return (
        "https://news.google.com/rss/search"
        f"?q={quote_plus(full_query)}&hl=ko&gl=KR&ceid=KR:ko"
    )


def _looks_like_shopping_request(command: str) -> bool:
    lowered = command.lower()
    has_shopping_word = any(keyword in command or keyword in lowered for keyword in SHOPPING_KEYWORDS)
    has_discovery_word = any(keyword in command or keyword in lowered for keyword in SHOPPING_DISCOVERY_KEYWORDS)
    has_shop_platform = any(keyword.lower() in lowered for keyword in SHOPPING_SITE_ALIASES)
    has_finding_verb = bool(re.search(r"(찾아|보여|추천|골라|비교)", command, re.IGNORECASE))
    return has_shopping_word or (has_discovery_word and (has_shop_platform or has_finding_verb))


def _detect_shopping_platform(command: str) -> tuple[str, str, str]:
    lowered = command.lower()
    for keyword, info in SHOPPING_SITE_ALIASES.items():
        if keyword.lower() in lowered:
            return SHOPPING_PLATFORM_IDS[keyword], info[0], info[1]
    default = SHOPPING_SITE_ALIASES["네이버"]
    return "naver", default[0], default[1]


def build_ai_assisted_browser_intent(classification: dict, original_command: str) -> NormalizedIntent | None:
    intent_type = str(classification.get("intent_type") or "").strip()
    query = str(classification.get("query") or "").strip()
    platform = str(classification.get("platform") or "").strip().lower()
    if not intent_type:
        return None

    if intent_type == "shopping_search":
        platform_name, url_template = SHOPPING_SITE_ALIASES.get(platform, SHOPPING_SITE_ALIASES["네이버"])
        if not query:
            query = _sanitize_general_search_query(original_command) or original_command
        url = url_template.format(query=quote_plus(query))
        if classification.get("prefer_lowest_price") and platform in {"naver", "네이버"}:
            url = f"{url}&sort=price_asc"
        return NormalizedIntent(
            category="shopping_search",
            command=original_command,
            params={
                "platform": platform,
                "query": query,
                "prefer_lowest_price": bool(classification.get("prefer_lowest_price")),
                "purchase_intent": True,
                "url": url,
                "title": f"{platform_name}에서 {query} 찾기",
            },
            description="ai_browser_shopping_fallback",
        )

    if intent_type == "place_search":
        if not query:
            query = _sanitize_general_search_query(original_command) or original_command
        if platform in {"naver_map", "naver"}:
            return NormalizedIntent(
                category="open_url",
                command=original_command,
                params={
                    "url": f"https://map.naver.com/p/search/{quote_plus(query)}",
                    "title": f"네이버 지도에서 {query} 찾기",
                },
                description="ai_browser_place_fallback",
            )
        return NormalizedIntent(
            category="open_url",
            command=original_command,
            params={
                "url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}",
                "title": f"지도에서 {query} 찾기",
            },
            description="ai_browser_place_fallback",
        )

    if intent_type == "service_search":
        if not query:
            return None
        service = SERVICE_SEARCH_ALIASES.get(platform)
        if not service:
            return None
        service_name, url_template = service
        return NormalizedIntent(
            category="open_url",
            command=original_command,
            params={
                "url": url_template.format(query=quote_plus(query)),
                "title": f"{service_name}에서 {query} 찾기",
            },
            description="ai_browser_service_fallback",
        )

    if intent_type == "search":
        if not query:
            query = _sanitize_general_search_query(original_command) or original_command
        return NormalizedIntent(
            category="open_url",
            command=original_command,
            params={
                "url": f"https://www.google.com/search?q={quote_plus(query)}",
                "title": "검색 결과 열기",
            },
            description="ai_browser_search_fallback",
        )

    return None


def _sanitize_general_search_query(command: str) -> str | None:
    query = command.strip()
    query = re.sub(
        r"\s*(해줘|해 줘|해줄래|해 줄래|보여줘|보여 줘|알아봐줘|알아봐 줘|찾아줘|찾아 줘|부탁해|please)\s*$",
        "",
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(r"\s+", " ", query).strip(" \"'")
    if len(query) < 2:
        return None
    return query


def _extract_file_read_intent(command: str) -> str | None:
    patterns = [
        r"(.+?)\s*파일(?:을|를)?\s*(읽어줘|읽어 줘|읽어|열어줘|열어 줘|보여줘|보여 줘)$",
        r"(.+?)\s*(읽어줘|읽어 줘|읽어|열어줘|열어 줘)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, command, re.IGNORECASE)
        if match:
            path = match.group(1).strip()
            if _looks_like_path(path):
                return path
    return None


def _extract_file_write_intent(command: str) -> dict | None:
    patterns = [
        r"(.+?)\s*파일(?:에)?\s*(.+?)\s*(써줘|써 줘|저장해줘|저장해 줘|기록해줘|기록해 줘)$",
        r"(.+?)\s*에\s*(.+?)\s*(써줘|써 줘|저장해줘|저장해 줘)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, command, re.IGNORECASE)
        if match:
            path = match.group(1).strip()
            content = match.group(2).strip().strip("\"'")
            if _looks_like_path(path) and content:
                return {"path": path, "content": content}
    return None


def _extract_file_copy_move_intent(command: str, *, operation: str) -> dict | None:
    verbs = {
        "copy": r"(복사해줘|복사해 줘|복사|copy)",
        "move": r"(옮겨줘|옮겨 줘|이동해줘|이동해 줘|이동|move)",
    }[operation]
    path_pattern = r"([~./\\\w\- ]+\.\w+|/[^\s]+|~/[^\s]+)"
    patterns = [
        rf"{path_pattern}\s*(?:을|를)?\s*{path_pattern}\s*(?:로|으로)\s*{verbs}$",
        rf"{path_pattern}\s*->\s*{path_pattern}\s*{verbs}$",
    ]
    for pattern in patterns:
        match = re.search(pattern, command, re.IGNORECASE)
        if match:
            src = match.group(1).strip()
            dst = match.group(2).strip()
            if _looks_like_path(src) and _looks_like_path(dst):
                return {"src": src, "dst": dst}
    return None


def _extract_file_delete_intent(command: str) -> str | None:
    patterns = [
        r"(.+?)\s*파일(?:을|를)?\s*(삭제해줘|삭제해 줘|지워줘|지워 줘|삭제|지워)$",
        r"(.+?)\s*(삭제해줘|삭제해 줘|지워줘|지워 줘|삭제|지워)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, command, re.IGNORECASE)
        if match:
            path = match.group(1).strip()
            if _looks_like_path(path):
                return path
    return None


def _extract_list_path_intent(command: str) -> str | None:
    patterns = [
        r"(.+?)\s*(폴더|디렉터리)\s*(목록 보여줘|목록|보여줘|열어줘|열어 줘)$",
        r"(.+?)\s*(안의|내)\s*파일\s*목록\s*보여줘$",
    ]
    for pattern in patterns:
        match = re.search(pattern, command, re.IGNORECASE)
        if match:
            path = match.group(1).strip()
            if _looks_like_path(path) or path.startswith("~") or path.startswith("/"):
                return path
    return None


def _looks_like_path(value: str) -> bool:
    return (
        "/" in value
        or "\\" in value
        or value.startswith("~")
        or "." in value
        or value.startswith("/tmp")
    )
