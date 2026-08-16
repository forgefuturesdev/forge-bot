import os
import sys
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")

ddgs_stub = types.ModuleType("ddgs")
ddgs_stub.DDGS = object
sys.modules["ddgs"] = ddgs_stub

import discord_briefing
import market_feed


class MarketSafetyTests(unittest.TestCase):
    def test_us_briefing_does_not_invent_support_or_resistance(self):
        with patch.object(
            discord_briefing,
            "get_quote",
            return_value={"price": 100.0, "prev": 99.0},
        ), patch.object(discord_briefing, "get_news", return_value=[]):
            briefing = discord_briefing.build_us_briefing()

        rendered = "\n".join(field["value"] for field in briefing["fields"]).lower()
        self.assertNotIn("support:", rendered)
        self.assertNotIn("resistance:", rendered)

    def test_missing_calendar_feed_never_declares_clear_to_trade(self):
        captured = []

        def capture_post(channel, embeds):
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
        description = captured[0]["description"]
        self.assertNotIn("Clear to trade", description)
        self.assertIn("official economic calendar", description)
        self.assertIn("delayed or incomplete", description)


if __name__ == "__main__":
    unittest.main()
