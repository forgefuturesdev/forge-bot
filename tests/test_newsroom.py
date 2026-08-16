from datetime import datetime, timezone
import os
import sys
from types import SimpleNamespace
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")

requests_stub = types.ModuleType("requests")
requests_stub.RequestException = Exception
requests_stub.get = lambda *args, **kwargs: None
requests_stub.post = lambda *args, **kwargs: None
sys.modules.setdefault("requests", requests_stub)

import newsroom


def response(status_code, payload=None):
    return SimpleNamespace(
        status_code=status_code,
        json=lambda: payload or {},
    )


class NewsroomTests(unittest.TestCase):
    def test_branding_travels_with_every_embed(self):
        embed = newsroom.brand_embed(
            {"title": "Market update"},
            timestamp=datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(embed["author"]["name"], "FORGE FUTURES · MARKET DESK")
        self.assertIn("Curated by Forge Futures", embed["footer"]["text"])
        self.assertIn("forge-futures.com", embed["footer"]["text"])
        self.assertEqual(embed["timestamp"], "2026-08-16T12:00:00+00:00")

    def test_shareable_post_is_crossposted(self):
        with patch.object(
            newsroom.requests,
            "post",
            side_effect=[response(200, {"id": "message-1"}), response(200, {})],
        ) as sender:
            result = newsroom.post_discord(
                "token",
                "channel",
                [{"title": "Briefing"}],
                publish=True,
            )

        self.assertTrue(result)
        self.assertTrue(result.published)
        self.assertEqual(sender.call_count, 2)
        payload = sender.call_args_list[0].kwargs["json"]
        self.assertEqual(payload["allowed_mentions"], {"parse": []})
        self.assertTrue(sender.call_args_list[1].args[0].endswith("/crosspost"))

    def test_crosspost_failure_is_a_real_job_failure(self):
        with patch.object(
            newsroom.requests,
            "post",
            side_effect=[response(200, {"id": "message-1"}), response(403, {})],
        ):
            result = newsroom.post_discord(
                "token",
                "channel",
                [{"title": "Briefing"}],
                publish=True,
            )

        self.assertFalse(result)
        self.assertEqual(result.message_id, "message-1")
        self.assertIn("403", result.error)

    def test_tracking_links_and_duplicate_headlines_are_removed(self):
        seen = {"https://example.com/story?id=1"}
        items = [
            {
                "title": "Same story",
                "url": "https://example.com/story?id=1&utm_source=test",
            },
            {
                "title": "Fresh story",
                "url": "https://example.com/fresh?utm_medium=social",
            },
            {
                "title": "Fresh story",
                "url": "https://another.example/fresh",
            },
        ]

        selected = newsroom.filter_unseen_news(items, seen, limit=5)

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["url"], "https://example.com/fresh")

    def test_calendar_times_handle_uk_and_us_daylight_saving(self):
        events = newsroom.select_calendar_events(
            [{
                "date": "2026-07-01T08:30:00-04:00",
                "impact": "High",
                "country": "USD",
                "title": "Example release",
            }],
            start=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
            hours=2,
        )

        rendered = newsroom.render_calendar_events(events)
        self.assertIn("13:30 UK", rendered)
        self.assertIn("08:30 ET", rendered)


if __name__ == "__main__":
    unittest.main()
