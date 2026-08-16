import os
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
requests_stub.get = lambda *args, **kwargs: None
requests_stub.post = lambda *args, **kwargs: None
sys.modules.setdefault("requests", requests_stub)

import channel_refresh


def channel(channel_id, name, channel_type=0, parent_id=None, topic=None, tags=None):
    return {
        "id": channel_id,
        "name": name,
        "type": channel_type,
        "parent_id": parent_id,
        "topic": topic,
        "available_tags": tags or [],
    }


class ChannelRefreshTests(unittest.TestCase):
    def test_all_content_fits_discord_limits_and_assets_exist(self):
        channels = {
            name: channel(f"id-{name}", name)
            for name in channel_refresh.CHANNEL_NAMES
        }
        channels[channel_refresh.FORUM_NAME] = channel(
            "forum", channel_refresh.FORUM_NAME, channel_type=15
        )

        for guide in channel_refresh.build_education_guides():
            channel_refresh.validate_embeds(guide["embeds"])
            self.assertTrue((channel_refresh.ASSET_DIR / guide["asset"]).is_file())
        for embeds in channel_refresh.build_public_channel_embeds(channels).values():
            channel_refresh.validate_embeds(embeds)

    def test_current_payout_rules_are_rendered(self):
        guide = next(
            guide
            for guide in channel_refresh.build_education_guides()
            if guide["tag"] == "Payouts"
        )
        rendered = str(guide["embeds"])

        self.assertIn("Zero $200 | Standard $500 | Advanced $1,000", rendered)
        self.assertIn("lower of 50%", rendered)
        self.assertIn("90%", rendered)
        self.assertIn("$15,000", rendered)
        self.assertIn("within 24 hours", rendered)

    def test_education_forum_is_information_only_for_members(self):
        payload = channel_refresh.desired_forum_payload()
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

    def test_apply_is_additive_and_idempotent(self):
        channels = [
            channel(f"id-{name}", name)
            for name in channel_refresh.CHANNEL_NAMES
        ]
        tags = [
            {"id": str(index), "name": tag}
            for index, tag in enumerate(
                ("Start Here", "Platform", "Risk", "Payouts", "Psychology"),
                start=1,
            )
        ]
        forum = channel(
            "forum",
            channel_refresh.FORUM_NAME,
            channel_type=15,
            parent_id=channel_refresh.EDUCATION_CATEGORY_ID,
            topic=channel_refresh.FORUM_TOPIC,
            tags=tags,
        )
        channels.append(forum)
        thread_names = [
            {"id": str(index), "name": guide["name"], "parent_id": "forum"}
            for index, guide in enumerate(channel_refresh.build_education_guides(), start=1)
        ]

        with (
            patch.object(channel_refresh, "get_guild_channels", return_value=channels),
            patch.object(channel_refresh, "ensure_forum", return_value=forum),
            patch.object(channel_refresh, "active_and_archived_threads", return_value=thread_names),
            patch.object(channel_refresh, "create_forum_guide") as create_guide,
            patch.object(channel_refresh, "find_version_message", return_value="current"),
            patch.object(channel_refresh, "post_and_pin") as post_and_pin,
            patch.object(channel_refresh, "request") as api_request,
        ):
            channel_refresh.apply()

        create_guide.assert_not_called()
        post_and_pin.assert_not_called()
        api_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
