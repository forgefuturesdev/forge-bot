import os
from pathlib import Path
import sys
from types import SimpleNamespace
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
os.environ.setdefault("DISCORD_GUILD_ID", "forge-guild")
os.environ.setdefault("DISCORD_BOT_ID", "forge-bot")
os.environ.setdefault("DISCORD_EDUCATION_CATEGORY_ID", "education-category")

requests_stub = types.ModuleType("requests")
requests_stub.RequestException = Exception
requests_stub.Response = SimpleNamespace
requests_stub.request = lambda *args, **kwargs: None
sys.modules.setdefault("requests", requests_stub)

import channel_refresh
import education_upgrade


class EducationUpgradeTests(unittest.TestCase):
    def test_trading_guides_are_complete_and_plainly_named(self):
        guides = education_upgrade.build_trading_guides()

        self.assertEqual(
            [guide["name"] for guide in guides],
            [
                "Chart Patterns",
                "Candlestick Basics",
                "Market Structure",
                "Support & Resistance",
                "Risk Management & Position Sizing",
                "Trading Psychology",
                "Trading Sessions & Economic News",
                "Trading Plans & Journaling",
            ],
        )
        for guide in guides:
            rendered = str(guide["embeds"])
            self.assertNotIn("--", rendered)
            self.assertNotIn(" -> ", rendered)
            self.assertFalse(guide["name"][:1].isdigit())
            channel_refresh.validate_embeds(guide["embeds"])
            self.assertTrue(
                (education_upgrade.TRADING_ASSET_DIR / guide["asset"]).is_file()
            )

    def test_trading_copy_does_not_claim_certainty_or_live_signals(self):
        rendered = str(education_upgrade.build_trading_guides()).casefold()

        for forbidden in (
            "guaranteed profit",
            "winning setup",
            "sure thing",
            "live signal",
            "must move",
        ):
            self.assertNotIn(forbidden, rendered)
        self.assertIn("do not predict what must happen next", rendered)
        self.assertIn("a good decision can lose", rendered)
        self.assertIn("leave room for slippage", rendered)

    def test_trading_forum_is_information_only(self):
        payload = education_upgrade.desired_trading_forum_payload()
        everyone = next(
            overwrite
            for overwrite in payload["permission_overwrites"]
            if overwrite["id"] == channel_refresh.GUILD_ID
        )
        allow = int(everyone["allow"])
        deny = int(everyone["deny"])

        self.assertTrue(allow & channel_refresh.VIEW_CHANNEL)
        self.assertTrue(allow & channel_refresh.READ_MESSAGE_HISTORY)
        self.assertTrue(deny & channel_refresh.SEND_MESSAGES)
        self.assertTrue(deny & channel_refresh.CREATE_PUBLIC_THREADS)
        self.assertTrue(deny & channel_refresh.SEND_MESSAGES_IN_THREADS)

    def test_archives_hide_every_non_bot_overwrite(self):
        channel = {
            "permission_overwrites": [
                {
                    "id": channel_refresh.GUILD_ID,
                    "type": 0,
                    "allow": str(channel_refresh.VIEW_CHANNEL),
                    "deny": "0",
                },
                {
                    "id": "member-role",
                    "type": 0,
                    "allow": str(channel_refresh.VIEW_CHANNEL),
                    "deny": "0",
                },
                {
                    "id": channel_refresh.BOT_ID,
                    "type": 1,
                    "allow": "0",
                    "deny": str(channel_refresh.VIEW_CHANNEL),
                },
            ]
        }

        result = education_upgrade.archive_permissions(channel)

        for overwrite in result:
            if overwrite["id"] == channel_refresh.BOT_ID:
                self.assertTrue(int(overwrite["allow"]) & channel_refresh.VIEW_CHANNEL)
                self.assertFalse(int(overwrite["deny"]) & channel_refresh.VIEW_CHANNEL)
            else:
                self.assertFalse(int(overwrite["allow"]) & channel_refresh.VIEW_CHANNEL)
                self.assertTrue(int(overwrite["deny"]) & channel_refresh.VIEW_CHANNEL)

    def test_archive_state_preserves_exact_channel_metadata(self):
        channel = {
            "id": "resource-id",
            "name": "resources",
            "topic": "Old useful content",
            "position": 7,
            "parent_id": channel_refresh.EDUCATION_CATEGORY_ID,
            "permission_overwrites": [{"id": "role", "type": 0, "allow": "1", "deny": "2"}],
        }

        content = education_upgrade.archive_state_content(channel)
        restored = __import__("json").loads(content.split("\n", 1)[1])

        self.assertEqual(restored, education_upgrade.archive_state(channel))
        self.assertLessEqual(len(content), 2000)

    def test_runtime_packages_both_asset_sets(self):
        dockerfile = (
            Path(__file__).resolve().parents[1] / "Dockerfile"
        ).read_text(encoding="utf-8")

        self.assertIn("COPY assets/ ./assets/", dockerfile)

    def test_replaced_channels_are_archived_only_after_forum_verification(self):
        events = []
        forge_forum = {"id": "forge-forum"}
        trading_forum = {"id": "trading-forum"}

        with (
            patch.object(education_upgrade, "verify_assets", side_effect=lambda: events.append("assets")),
            patch.object(channel_refresh, "get_guild_channels", return_value=[]),
            patch.object(channel_refresh, "index_channels", return_value={}),
            patch.object(education_upgrade, "validate_existing_forums", side_effect=lambda _: events.append("forums-preflight")),
            patch.object(education_upgrade, "validate_archive_candidates", side_effect=lambda _: events.append("archive-preflight")),
            patch.object(channel_refresh, "ensure_forum", return_value=forge_forum),
            patch.object(education_upgrade, "ensure_trading_forum", return_value=trading_forum),
            patch.object(education_upgrade, "apply_guides", side_effect=lambda *args, **kwargs: events.append(f"apply-{kwargs['label']}")),
            patch.object(education_upgrade, "verify_forums", side_effect=lambda: events.append("verify-forums")),
            patch.object(education_upgrade, "archive_replaced_channels", side_effect=lambda: events.append("archive")),
            patch.object(education_upgrade, "verify_archives", side_effect=lambda: events.append("verify-archives")),
        ):
            education_upgrade.apply()

        self.assertLess(events.index("verify-forums"), events.index("archive"))
        self.assertLess(events.index("archive"), events.index("verify-archives"))


if __name__ == "__main__":
    unittest.main()
