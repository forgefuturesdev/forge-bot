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


def response(status_code, payload=None, content=b""):
    return SimpleNamespace(
        status_code=status_code,
        json=lambda: payload or {},
        content=content,
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

    def test_invalid_embed_is_rejected_before_discord(self):
        with patch.object(newsroom.requests, "post") as sender:
            result = newsroom.post_discord(
                "token",
                "channel",
                [{"fields": [{"name": "Too long", "value": "x" * 1025}]}],
            )

        self.assertFalse(result)
        self.assertIn("rejected locally", result.error)
        sender.assert_not_called()

    def test_long_headlines_are_split_across_valid_fields(self):
        items = [
            {
                "title": f"Market headline {index} " + ("x" * 120),
                "url": f"https://example.com/story/{index}?detail=" + ("y" * 240),
                "source": "Example source",
            }
            for index in range(5)
        ]

        fields = newsroom.headline_fields(items, title="WHAT'S MOVING", limit=5)

        self.assertGreater(len(fields), 1)
        self.assertTrue(all(len(field["value"]) <= 1024 for field in fields))
        self.assertEqual(
            sum(field["value"].count("Market headline") for field in fields),
            5,
        )

    def test_calendar_xml_is_used_when_json_is_unavailable(self):
        xml = b"""<?xml version='1.0'?>
        <weeklyevents><event><title>CPI</title><country>USD</country>
        <date>08-19-2026</date><time>08:30am</time><impact>High</impact>
        <forecast>2.9%</forecast><previous>3.0%</previous></event></weeklyevents>"""
        with patch.object(
            newsroom.requests,
            "get",
            side_effect=[response(503), response(503), response(200, content=xml)],
        ):
            events = newsroom.fetch_economic_calendar()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["title"], "CPI")
        self.assertEqual(events[0]["date"], "2026-08-19T08:30:00")

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
