import sys
import unittest
from pathlib import Path
from urllib.parse import unquote_plus

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent import router as intent_router
from intent.normalizer import (
    build_ai_assisted_browser_intent,
    build_last_resort_intent,
    detect_intent,
    normalize_command,
)


class IntentNormalizerTests(unittest.TestCase):
    def test_normalize_command_strips_korean_particle_from_url(self):
        command = "https://newsstand.naver.com/?list&pcode=020을 크롤링해줘"
        normalized = normalize_command(command)
        self.assertEqual(
            normalized,
            "https://newsstand.naver.com/?list&pcode=020 크롤링해줘",
        )

    def test_detect_search_intent_for_google_korean_phrase(self):
        intent = detect_intent("구글에서 나무위키 검색해줘")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "search")
        self.assertIn("google.com/search?q=", intent.params["url"])
        self.assertIn("나무위키", unquote_plus(intent.params["url"]))

    def test_detect_news_search_intent_for_recent_articles(self):
        intent = detect_intent("토스 상장 관련 내용 일주일 간 뉴스 기사 검색해줄래")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "search")
        self.assertIn("news.google.com/rss/search", intent.params["url"])
        decoded_url = unquote_plus(intent.params["url"])
        self.assertIn("토스 상장", decoded_url)
        self.assertIn("when:7d", decoded_url)
        self.assertNotIn("검색해줄래", decoded_url)

    def test_detect_crawl_intent_from_url_phrase(self):
        intent = detect_intent("https://example.com 읽어와")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "crawl")
        self.assertEqual(intent.params["url"], "https://example.com")

    def test_detect_file_read_intent(self):
        intent = detect_intent("/tmp/test.txt 파일 읽어줘")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "file_read")
        self.assertEqual(intent.params["path"], "/tmp/test.txt")

    def test_detect_file_write_intent(self):
        intent = detect_intent("/tmp/test.txt 파일에 hello world 써줘")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "file_write")
        self.assertEqual(intent.params["path"], "/tmp/test.txt")
        self.assertEqual(intent.params["content"], "hello world")

    def test_detect_file_copy_intent(self):
        intent = detect_intent("/tmp/a.txt 를 /tmp/b.txt 로 복사해줘")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "file_copy")
        self.assertEqual(intent.params["src"], "/tmp/a.txt")
        self.assertEqual(intent.params["dst"], "/tmp/b.txt")

    def test_detect_file_delete_intent(self):
        intent = detect_intent("/tmp/a.txt 파일 삭제해줘")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "file_delete")
        self.assertEqual(intent.params["path"], "/tmp/a.txt")

    def test_detect_list_path_intent(self):
        intent = detect_intent("/tmp 폴더 목록 보여줘")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "shell_ls_path")
        self.assertEqual(intent.params["command"], "ls /tmp")

    def test_detect_open_site_intent(self):
        intent = detect_intent("네이버 열어줘")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "open_url")
        self.assertEqual(intent.params["url"], "https://www.naver.com")

    def test_detect_shopping_intent(self):
        intent = detect_intent("네이버에서 드럼 스틱 사줘")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "shopping_search")
        decoded_url = unquote_plus(intent.params["url"])
        self.assertIn("search.shopping.naver.com", decoded_url)
        self.assertIn("드럼 스틱", decoded_url)
        self.assertIn("네이버 쇼핑", intent.params["title"])

    def test_detect_shopping_intent_for_lowest_price_purchase_phrase(self):
        intent = detect_intent("네이버에서 최저가 드럼스틱 찾아서 바로 살 수 있게 세팅해줘")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "shopping_search")
        decoded_url = unquote_plus(intent.params["url"])
        self.assertIn("search.shopping.naver.com", decoded_url)
        self.assertIn("드럼스틱", decoded_url)
        self.assertIn("sort=price_asc", decoded_url)

    def test_detect_email_send_intent(self):
        intent = detect_intent("mogiyoon@gmail.com으로 메일 보내줘")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "open_url")
        self.assertEqual(intent.params["url"], "mailto:mogiyoon@gmail.com")
        self.assertIn("메일 보내기", intent.params["title"])

    def test_detect_youtube_service_search_intent(self):
        intent = detect_intent("유튜브에서 드럼 연습 영상 찾아줘")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "open_url")
        decoded_url = unquote_plus(intent.params["url"])
        self.assertIn("youtube.com/results", decoded_url)
        self.assertIn("드럼 연습 영상", decoded_url)

    def test_detect_place_search_intent(self):
        intent = detect_intent("성수 카페 추천해줘")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "open_url")
        decoded_url = unquote_plus(intent.params["url"])
        self.assertIn("google.com/maps/search", decoded_url)
        self.assertIn("성수 카페", decoded_url)

    def test_detect_naver_map_search_intent(self):
        intent = detect_intent("네이버 지도에서 강남 맛집 찾아줘")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "open_url")
        decoded_url = unquote_plus(intent.params["url"])
        self.assertIn("map.naver.com/p/search", decoded_url)
        self.assertIn("강남 맛집", decoded_url)

    def test_build_last_resort_intent_returns_search_page(self):
        intent = build_last_resort_intent("토스 상장 관련 내용 알려줘")
        self.assertIsNone(intent)

    def test_build_last_resort_intent_keeps_simple_search(self):
        intent = build_last_resort_intent("토스 상장 관련 내용 검색")
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "open_url")
        decoded_url = unquote_plus(intent.params["url"])
        self.assertIn("google.com/search", decoded_url)
        self.assertIn("토스 상장 관련 내용", decoded_url)

    def test_build_ai_assisted_browser_intent_for_shopping(self):
        intent = build_ai_assisted_browser_intent(
            {
                "intent_type": "shopping_search",
                "platform": "naver",
                "query": "드럼스틱",
                "prefer_lowest_price": True,
            },
            "네이버에서 최저가 드럼스틱 찾아줘",
        )
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.category, "shopping_search")
        decoded_url = unquote_plus(intent.params["url"])
        self.assertIn("search.shopping.naver.com", decoded_url)
        self.assertIn("드럼스틱", decoded_url)
        self.assertIn("sort=price_asc", decoded_url)


class IntentRouterFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_route_shopping_request_creates_browser_step(self):
        task = await intent_router.route("네이버에서 드럼 스틱 사줘")
        self.assertEqual(len(task.steps), 1)
        self.assertEqual(task.steps[0].tool, "shopping_helper")
        self.assertEqual(task.steps[0].params["platform"], "naver")
        self.assertEqual(task.steps[0].params["query"], "드럼 스틱")
        self.assertTrue(task.steps[0].params["purchase_intent"])

    async def test_route_lowest_price_shopping_request_creates_browser_step(self):
        task = await intent_router.route("네이버에서 최저가 드럼스틱 찾아서 바로 살 수 있게 세팅해줘")
        self.assertEqual(len(task.steps), 1)
        self.assertEqual(task.steps[0].tool, "shopping_helper")
        self.assertEqual(task.steps[0].params["platform"], "naver")
        self.assertEqual(task.steps[0].params["query"], "드럼스틱")
        self.assertTrue(task.steps[0].params["prefer_lowest_price"])

    async def test_route_place_search_request_creates_browser_step(self):
        task = await intent_router.route("성수 카페 추천해줘")
        self.assertEqual(len(task.steps), 1)
        self.assertEqual(task.steps[0].tool, "browser")
        decoded_url = unquote_plus(task.steps[0].params["url"])
        self.assertIn("google.com/maps/search", decoded_url)
        self.assertIn("성수 카페", decoded_url)

    async def test_route_email_send_request_creates_browser_step(self):
        task = await intent_router.route("mogiyoon@gmail.com으로 메일 보내줘")
        self.assertEqual(len(task.steps), 1)
        self.assertEqual(task.steps[0].tool, "browser")
        self.assertEqual(task.steps[0].params["url"], "mailto:mogiyoon@gmail.com")

    async def test_route_weather_alert_request_creates_schedule_helper_step(self):
        task = await intent_router.route("아침 8시에 기상청에서 스크롤한 거 바탕으로 날씨 알림 보내줘")
        self.assertEqual(len(task.steps), 1)
        self.assertEqual(task.steps[0].tool, "weather_alert_helper")


if __name__ == "__main__":
    unittest.main()
