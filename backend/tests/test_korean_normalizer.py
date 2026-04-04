import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent.korean import extract_keywords, strip_particles_from_url
from intent.normalizer import normalize_command


class KoreanNormalizerTests(unittest.TestCase):
    def test_strip_particle_eseo_from_url(self):
        self.assertEqual(strip_particles_from_url("https://news.hada.io에서"), "https://news.hada.io")

    def test_strip_particle_euro_from_url(self):
        self.assertEqual(strip_particles_from_url("https://google.com으로"), "https://google.com")

    def test_strip_particle_eul_from_url(self):
        self.assertEqual(strip_particles_from_url("https://example.com을"), "https://example.com")

    def test_strip_particle_eseoui_from_url(self):
        self.assertEqual(strip_particles_from_url("https://news.hada.io에서의"), "https://news.hada.io")

    def test_url_without_particle_is_unchanged(self):
        self.assertEqual(strip_particles_from_url("https://example.com"), "https://example.com")

    def test_non_url_korean_text_is_unchanged(self):
        self.assertEqual(strip_particles_from_url("네이버에서 검색해줘"), "네이버에서 검색해줘")

    def test_fallback_regex_still_strips_common_particles(self):
        with patch("intent.korean._get_kiwi", return_value=None):
            self.assertEqual(strip_particles_from_url("https://example.com에서"), "https://example.com")
            self.assertEqual(strip_particles_from_url("https://example.com을"), "https://example.com")
            self.assertEqual(strip_particles_from_url("https://example.com를"), "https://example.com")

    def test_extract_keywords_returns_nouns_and_verbs(self):
        keywords = extract_keywords("뉴스 크롤링해줘")
        self.assertIn("뉴스", keywords)
        self.assertIn("크롤링", keywords)

    def test_strip_particles_from_url_handles_multiple_urls(self):
        command = "https://example.com을 열고 https://google.com으로 이동해줘"
        expected = "https://example.com 열고 https://google.com 이동해줘"
        self.assertEqual(strip_particles_from_url(command), expected)

    def test_normalize_command_applies_url_particle_stripping(self):
        command = "  https://news.hada.io에서의   크롤링해줘  "
        self.assertEqual(normalize_command(command), "https://news.hada.io 크롤링해줘")


if __name__ == "__main__":
    unittest.main()
