import os
import sys
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")

ddgs_stub = types.ModuleType("ddgs")
ddgs_stub.DDGS = object
sys.modules["ddgs"] = ddgs_stub

requests_stub = types.ModuleType("requests")
requests_stub.RequestException = Exception
requests_stub.get = lambda *args, **kwargs: None
requests_stub.post = lambda *args, **kwargs: None
sys.modules["requests"] = requests_stub

feedparser_stub = types.ModuleType("feedparser")
feedparser_stub.parse = lambda *args, **kwargs: types.SimpleNamespace(entries=[])
sys.modules["feedparser"] = feedparser_stub

import discord_briefing
import market_feed


class MarketSafetyTests(unittest.TestCase):
    def assert_embed_limits(self, embed):
        self.assertLessEqual(len(embed.get("title", "")), 256)
        self.assertLessEqual(len(embed.get("description", "")), 4096)
        self.assertLessEqual(len(embed.get("footer", {}).get("text", "")), 2048)
        for field in embed.get("fields", []):
            self.assertLessEqual(len(field.get("name", "")), 256)
            self.assertLessEqual(len(field.get("value", "")), 1024)

    def test_market_news_splits_long_headlines_before_delivery(self):
        news = [
            {
                "title": f"Market headline {index} " + ("x" * 120),
                "url": f"https://example.com/story/{index}?detail=" + ("y" * 240),
                "source": "Example source",
                "category": "Markets",
            }
            for index in range(5)
        ]
        captured = []

        def capture_post(channel, embeds, *, publish=False):
            captured.extend(embeds)
            return True

        with patch.object(market_feed, "get_market_news", return_value=news), patch.object(
            market_feed,
            "recent_channel_links",
            return_value=set(),
        ), patch.object(market_feed, "post_discord", side_effect=capture_post):
            posted = market_feed.post_market_news()

        self.assertTrue(posted)
        moving_fields = [
            field
            for field in captured[0]["fields"]
            if field["name"].startswith("WHAT'S MOVING")
        ]
        self.assertGreater(len(moving_fields), 1)
        self.assert_embed_limits(captured[0])

    def test_us_briefing_does_not_invent_support_or_resistance(self):
        with patch.object(
            discord_briefing,
            "get_quote",
            return_value={"price": 100.0, "prev": 99.0, "timestamp": 1782907200},
        ), patch.object(
            discord_briefing,
            "get_news",
            return_value=[],
        ), patch.object(
            discord_briefing,
            "get_calendar_feed",
            return_value=[],
        ), patch.object(
            discord_briefing,
            "recent_channel_links",
            return_value=set(),
        ):
            briefing = discord_briefing.build_us_briefing()

        rendered = "\n".join(field["value"] for field in briefing["fields"]).lower()
        self.assertNotIn("support:", rendered)
        self.assertNotIn("resistance:", rendered)
        self.assert_embed_limits(briefing)

    def test_missing_calendar_feed_never_declares_clear_to_trade(self):
        captured = []

        def capture_post(channel, embeds, *, publish=False):
            captured.extend(embeds)
            return True

        with patch.object(
            market_feed,
            "get_economic_calendar",
            return_value=[{"impact": "Low", "country": "USD"}],
        ), patch.object(
            market_feed,
            "post_discord",
            side_effect=capture_post,
        ):
            posted = market_feed.post_weekly_ahead()

        self.assertTrue(posted)
        rendered = str(captured[0])
        self.assertNotIn("Clear to trade", rendered)
        self.assertIn("official economic calendar", rendered)
        self.assertIn("delayed or incomplete", rendered)
        self.assert_embed_limits(captured[0])

    def test_session_briefing_is_published_for_channel_followers(self):
        with patch.object(discord_briefing, "post_discord", return_value=True) as sender:
            posted = discord_briefing.post_embed({"title": "Test"})

        self.assertTrue(posted)
        sender.assert_called_once_with(
            discord_briefing.TOKEN,
            discord_briefing.CHANNEL,
            [{"title": "Test"}],
            publish=True,
        )

    def test_weekly_calendar_is_split_within_discord_field_limits(self):
        events = [
            {
                "date": f"2026-08-{17 + index // 4:02d}T{8 + index % 4:02d}:30:00-04:00",
                "impact": "High",
                "country": "USD",
                "title": "Very important scheduled economic release " + ("x" * 80),
                "forecast": "123.45",
                "previous": "120.00",
            }
            for index in range(12)
        ]
        captured = []

        def capture_post(channel, embeds, *, publish=False):
            captured.extend(embeds)
            return True

        with patch.object(
            market_feed,
            "get_economic_calendar",
            return_value=events,
        ), patch.object(
            market_feed,
            "post_discord",
            side_effect=capture_post,
        ), patch.object(
            market_feed,
            "datetime",
        ) as mocked_datetime:
            mocked_datetime.now.return_value = discord_briefing.datetime(
                2026, 8, 16, 17, 0, tzinfo=discord_briefing.timezone.utc
            )
            posted = market_feed.post_weekly_ahead()

        self.assertTrue(posted)
        self.assert_embed_limits(captured[0])

    def test_failed_cron_action_exits_nonzero(self):
        with patch.object(sys, "argv", ["market_feed.py", "news"]), patch.object(
            market_feed,
            "post_market_news",
            return_value=False,
        ):
            with self.assertRaises(SystemExit) as raised:
                market_feed.main()

        self.assertEqual(raised.exception.code, 1)

    def test_session_guards_follow_local_daylight_saving(self):
        cases = [
            ("uk", discord_briefing.datetime(2026, 7, 1, 6, 30, tzinfo=discord_briefing.timezone.utc)),
            ("uk", discord_briefing.datetime(2026, 1, 5, 7, 30, tzinfo=discord_briefing.timezone.utc)),
            ("us", discord_briefing.datetime(2026, 7, 1, 13, 0, tzinfo=discord_briefing.timezone.utc)),
            ("us", discord_briefing.datetime(2026, 1, 5, 14, 0, tzinfo=discord_briefing.timezone.utc)),
            ("asia", discord_briefing.datetime(2026, 7, 1, 22, 30, tzinfo=discord_briefing.timezone.utc)),
            ("asia", discord_briefing.datetime(2026, 1, 5, 23, 30, tzinfo=discord_briefing.timezone.utc)),
        ]

        for session, timestamp in cases:
            with self.subTest(session=session, timestamp=timestamp):
                self.assertTrue(discord_briefing.should_run_session(session, timestamp))


if __name__ == "__main__":
    unittest.main()
