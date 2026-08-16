import os
import unittest
from unittest.mock import AsyncMock

os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
os.environ.setdefault("DISCORD_GUILD_ID", "forge-guild")

import bot


def staff_message(**overrides):
    message = {
        "attachments": [],
        "author": {"bot": False, "id": "staff-1", "username": "Joe"},
        "channel_id": "ticket-thread",
        "content": "We can help with that.",
        "guild_id": bot.GUILD_ID,
        "id": "original-message",
        "member": {"roles": [bot.ROLES["founder"]]},
    }
    message.update(overrides)
    return message


class BotSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_message_is_ignored_before_moderation(self):
        forge_bot = bot.ForgeBot()
        forge_bot.api = AsyncMock()

        await forge_bot.handle_message(staff_message(guild_id=None, content="free nitro"))

        forge_bot.api.assert_not_awaited()

    async def test_other_guild_is_ignored(self):
        forge_bot = bot.ForgeBot()
        forge_bot.api = AsyncMock()

        await forge_bot.handle_message(staff_message(guild_id="another-guild"))

        forge_bot.api.assert_not_awaited()

    async def test_ticket_relay_posts_before_deleting_original(self):
        forge_bot = bot.ForgeBot()
        calls = []

        async def fake_api(method, path, data=None):
            calls.append((method, path, data))
            if method == "GET":
                return {"parent_id": bot.CHANNELS["open_ticket"]}
            if method == "POST" and path == "/channels/ticket-thread/messages":
                return {"id": "relay-message"}
            return {}

        forge_bot.api = fake_api

        await forge_bot.handle_message(staff_message())

        relay_index = next(
            index for index, call in enumerate(calls)
            if call[0] == "POST" and call[1] == "/channels/ticket-thread/messages"
        )
        delete_index = next(
            index for index, call in enumerate(calls)
            if call[0] == "DELETE" and call[1].endswith("/original-message")
        )
        self.assertLess(relay_index, delete_index)

        relay_payload = calls[relay_index][2]
        self.assertEqual(relay_payload["allowed_mentions"], {"parse": []})
        self.assertEqual(relay_payload["embeds"][0]["author"]["name"], "Forge Team")

        ticket_posts = [
            call for call in calls
            if call[0] == "POST" and call[1] == "/channels/ticket-thread/messages"
        ]
        self.assertEqual(len(ticket_posts), 1)

        audit_payloads = [
            call[2] for call in calls
            if call[0] == "POST" and call[1] == f"/channels/{bot.CHANNELS['mod_logs']}/messages"
        ]
        self.assertEqual(len(audit_payloads), 1)
        audit_description = audit_payloads[0]["embeds"][0]["description"]
        self.assertIn("staff-1", audit_description)
        self.assertNotIn("We can help with that.", audit_description)

    async def test_failed_ticket_relay_preserves_original(self):
        forge_bot = bot.ForgeBot()
        calls = []

        async def fake_api(method, path, data=None):
            calls.append((method, path, data))
            if method == "GET":
                return {"parent_id": bot.CHANNELS["open_ticket"]}
            if method == "POST" and path == "/channels/ticket-thread/messages":
                return None
            return {}

        forge_bot.api = fake_api

        await forge_bot.handle_message(staff_message())

        original_deletes = [
            call for call in calls
            if call[0] == "DELETE" and call[1].endswith("/original-message")
        ]
        self.assertEqual(original_deletes, [])

    async def test_attachment_relay_uses_copied_file_and_audit(self):
        forge_bot = bot.ForgeBot()
        forge_bot.download_ticket_attachments = AsyncMock(return_value=[{
            "content": b"image-bytes",
            "content_type": "image/png",
            "filename": "chart.png",
        }])
        forge_bot.api_multipart = AsyncMock(return_value={"id": "relay-message"})
        forge_bot.api = AsyncMock(return_value={})
        forge_bot.log = AsyncMock()

        relayed = await forge_bot.relay_ticket_staff_message(staff_message(
            attachments=[{
                "content_type": "image/png",
                "filename": "chart.png",
                "size": 11,
                "url": "https://cdn.discordapp.com/attachments/1/2/chart.png",
            }],
        ))

        self.assertTrue(relayed)
        payload = forge_bot.api_multipart.await_args.args[1]
        self.assertEqual(payload["attachments"], [{"id": 0, "filename": "chart.png"}])
        forge_bot.api.assert_awaited_once_with(
            "DELETE",
            "/channels/ticket-thread/messages/original-message",
        )
        forge_bot.log.assert_awaited_once()

    async def test_untrusted_attachment_host_is_rejected(self):
        forge_bot = bot.ForgeBot()

        files = await forge_bot.download_ticket_attachments([{
            "filename": "file.png",
            "size": 10,
            "url": "https://example.com/file.png",
        }])

        self.assertIsNone(files)


if __name__ == "__main__":
    unittest.main()
