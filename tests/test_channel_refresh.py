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
    def test_emoji_decorated_channel_names_resolve_by_stable_suffix(self):
        indexed = channel_refresh.index_channels([
            channel("faq-id", "❓┃faq"),
            channel("status-id", "⚡┃platform-status"),
            channel("plain-id", "links"),
        ])

        self.assertEqual(indexed["faq"]["id"], "faq-id")
        self.assertEqual(indexed["platform-status"]["id"], "status-id")
        self.assertEqual(indexed["links"]["id"], "plain-id")

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

    def test_education_titles_are_clean_public_names(self):
        guides = channel_refresh.build_education_guides()
        self.assertEqual(
            [guide["name"] for guide in guides],
            [
                "How Forge Works",
                "Platform Orders & Positions",
                "Risk Discipline & Account Guardrails",
                "Payout Readiness & Limits",
                "Trader Process: Prepare, Execute, Review, Reset",
            ],
        )
        for guide in guides:
            rendered = str(guide["embeds"])
            self.assertNotIn("--", rendered)
            self.assertNotIn(" -> ", rendered)
            self.assertNotIn("00-", guide["name"])
            self.assertNotIn("01-", guide["name"])
            self.assertNotIn("02-", guide["name"])

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
            patch.object(channel_refresh, "update_forum_guide") as update_guide,
            patch.object(channel_refresh, "find_version_message", return_value="current"),
            patch.object(channel_refresh, "post_and_pin") as post_and_pin,
            patch.object(channel_refresh, "request") as api_request,
        ):
            channel_refresh.apply()

        create_guide.assert_not_called()
        self.assertEqual(update_guide.call_count, 5)
        post_and_pin.assert_not_called()
        api_request.assert_not_called()

    def test_legacy_education_titles_are_renamed_without_duplicate_guides(self):
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
        legacy_threads = [
            {
                "id": str(index),
                "name": guide["legacy_names"][0],
                "parent_id": "forum",
            }
            for index, guide in enumerate(channel_refresh.build_education_guides(), start=1)
        ]

        with (
            patch.object(channel_refresh, "get_guild_channels", return_value=channels),
            patch.object(channel_refresh, "ensure_forum", return_value=forum),
            patch.object(channel_refresh, "active_and_archived_threads", return_value=legacy_threads),
            patch.object(channel_refresh, "create_forum_guide") as create_guide,
            patch.object(channel_refresh, "update_forum_guide") as update_guide,
            patch.object(channel_refresh, "find_version_message", return_value="current"),
            patch.object(channel_refresh, "post_and_pin"),
        ):
            channel_refresh.apply()

        create_guide.assert_not_called()
        renamed_pairs = {
            (call.args[0]["name"], call.args[1]["name"])
            for call in update_guide.call_args_list
        }
        self.assertEqual(
            renamed_pairs,
            {
                (guide["legacy_names"][0], guide["name"])
                for guide in channel_refresh.build_education_guides()
            },
        )

    def test_stale_artwork_is_rebound_as_exactly_one_attachment(self):
        guide = channel_refresh.build_education_guides()[0]
        current_embeds = __import__("json").loads(__import__("json").dumps(guide["embeds"]))
        current_embeds[0]["image"] = {"url": "https://cdn.discordapp.com/old-image.png"}
        responses = [
            SimpleNamespace(
                status_code=200,
                json=lambda: {
                    "embeds": current_embeds,
                    "attachments": [{"id": "old", "filename": guide["asset"]}],
                },
            ),
            SimpleNamespace(status_code=200, json=lambda: {}),
        ]

        with patch.object(channel_refresh, "request", side_effect=responses) as api_request:
            channel_refresh.update_forum_guide(
                {"id": "guide-thread", "name": guide["name"]},
                guide,
            )

        self.assertEqual(api_request.call_count, 2)
        patch_call = api_request.call_args_list[1]
        self.assertEqual(patch_call.args[:2], ("PATCH", "/channels/guide-thread/messages/guide-thread"))
        self.assertIn("files", patch_call.kwargs)
        payload = __import__("json").loads(
            patch_call.kwargs["files"]["payload_json"][1]
        )
        self.assertEqual(
            payload["attachments"],
            [{"id": 0, "filename": "forge-education-education-hub.png"}],
        )
        self.assertEqual(
            payload["embeds"][0]["image"],
            {"url": "attachment://forge-education-education-hub.png"},
        )


if __name__ == "__main__":
    unittest.main()
