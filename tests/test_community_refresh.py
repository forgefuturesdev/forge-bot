import unittest
from unittest.mock import AsyncMock, patch
import test_bot_security
import bot
import community_refresh as refresh


class CommunityRefreshTests(unittest.TestCase):
    def test_panel_update_preserves_message_id_and_disables_mentions(self):
        spec = refresh.panel('rules', 'Title', 'Text')
        messages = [{'id': 'old', 'author': {'id': refresh.api.BOT_ID}, 'embeds': []}]
        with patch.object(refresh, 'call', side_effect=[{'id': 'old'}, {}]) as call:
            self.assertEqual(refresh.publish_panel('channel', spec, messages, 'old'), 'old')
            self.assertEqual(call.call_args_list[0].args[:2], ('PATCH', '/channels/channel/messages/old'))
            self.assertEqual(call.call_args_list[0].args[2]['allowed_mentions'], {'parse': []})

    def test_panel_never_replaces_member_content(self):
        with patch.object(refresh, 'call') as call:
            with self.assertRaises(refresh.api.DiscordError):
                refresh.publish_panel('channel', refresh.panel('x', 'Title', 'Text'), [{'id': 'old', 'author': {'id': 'member'}}], 'old')
            call.assert_not_called()

    def test_existing_versioned_panel_is_not_posted_twice(self):
        spec = refresh.panel('rules', 'Title', 'Text')
        messages = [{'id': 'current', 'author': {'id': refresh.api.BOT_ID}, 'embeds': [{'footer': {'text': refresh.MARKER + ' | rules'}}]}]
        with patch.object(refresh, 'call') as call:
            self.assertEqual(refresh.publish_panel('channel', spec, messages), 'current')
            call.assert_not_called()

    def test_asset_archive_has_exactly_the_reviewed_pngs(self):
        from zipfile import ZipFile
        with ZipFile(refresh.ASSET_ARCHIVE) as archive:
            for specs in refresh.panels({'forgefutures': 'joe', 'jackforgefutures': 'jack'}).values():
                for spec in specs:
                    for name in spec['assets']:
                        self.assertTrue(archive.read(name).startswith(b'\x89PNG\r\n\x1a\n'))

    def test_exact_staff_usernames_and_founder_role_are_required(self):
        members = [{'user': {'id': name, 'username': name}, 'roles': [refresh.FOUNDER]} for name in ['forgefutures', 'jackforgefutures']]
        self.assertEqual(set(refresh.resolve_staff(members)), {'forgefutures', 'jackforgefutures'})
        members[1]['roles'] = [refresh.MEMBER]
        with self.assertRaises(refresh.api.DiscordError):
            refresh.resolve_staff(members)

    def test_all_panels_meet_discord_limits(self):
        staff = {'forgefutures': 'joe', 'jackforgefutures': 'new-jack'}
        for name, panels in refresh.panels(staff, 'bugs').items():
            for spec in panels:
                refresh.api.validate_embeds(spec['embeds'])
                self.assertLessEqual(len(spec['assets']), 10)
                for row in spec['components']:
                    self.assertLessEqual(len(row['components']), 5)
                    self.assertTrue(all(len(b['label']) <= 80 for b in row['components']))

    def test_all_certificate_examples_are_explicitly_fictional(self):
        for specs in refresh.panels({'forgefutures': 'joe', 'jackforgefutures': 'jack'}).values():
            for spec in specs:
                if any(a.startswith('EXAMPLE-') for a in spec['assets']):
                    e = spec['embeds'][0]
                    self.assertIn('EXAMPLE', e['title'])
                    self.assertIn('ILLUSTRATIVE TEMPLATE', e['description'])
                    self.assertIn('Fictional', e['description'])

    def test_locks_remove_role_and_member_overrides_without_widening_visibility(self):
        channel = {'permission_overwrites': [
            {'id': 'other-role', 'type': 0, 'allow': str(refresh.WRITE), 'deny': str(refresh.VIEW)},
            {'id': 'other-user', 'type': 1, 'allow': str(refresh.WRITE), 'deny': '0'},
            {'id': refresh.FOUNDER, 'type': 0, 'allow': str(refresh.WRITE), 'deny': '0'},
        ]}
        locked = refresh.locked_overwrites(channel, [])
        for item in locked:
            if item['id'] not in {refresh.FOUNDER, refresh.MOD, refresh.api.BOT_ID}:
                self.assertFalse(int(item['allow']) & refresh.WRITE)
                self.assertEqual(int(item['deny']) & refresh.WRITE, refresh.WRITE)
        self.assertTrue(int(locked[0]['deny']) & refresh.VIEW)
        self.assertEqual(channel['permission_overwrites'][0]['allow'], str(refresh.WRITE))
        bot_permission = next(o for o in locked if o['id'] == refresh.api.BOT_ID)
        self.assertTrue(int(bot_permission['allow']) & refresh.SEND)

    def test_ticket_parent_is_locked_but_members_can_reply_in_invited_private_threads(self):
        member = next(o for o in refresh.locked_overwrites({}, [], ticket=True) if o['id'] == refresh.MEMBER)
        self.assertTrue(int(member['allow']) & refresh.THREAD_REPLY)
        self.assertFalse(int(member['deny']) & refresh.THREAD_REPLY)
        for permission in [refresh.SEND, refresh.PUBLIC_THREAD, refresh.PRIVATE_THREAD]:
            self.assertTrue(int(member['deny']) & permission)


class TicketFlowTests(unittest.IsolatedAsyncioTestCase):
    def event(self, custom_id='open_ticket', channel=None, roles=()):
        return {'guild_id': bot.GUILD_ID, 'type': 3, 'id': 'interaction', 'token': 'test', 'application_id': bot.BOT_ID,
                'channel_id': channel or bot.CHANNELS['open_ticket'], 'data': {'custom_id': custom_id},
                'member': {'user': {'id': 'requester', 'username': 'test-user'}, 'roles': list(roles)}}

    async def test_failed_ticket_creation_returns_actionable_ephemeral_error(self):
        b = bot.ForgeBot()
        b.api = AsyncMock(return_value={})
        b.create_ticket = AsyncMock(return_value={'error': 'Please try again'})
        await b.handle_interaction(self.event())
        self.assertEqual(b.api.call_args_list[0].args[2], {'type': 5, 'data': {'flags': 64}})
        self.assertEqual(b.api.call_args_list[-1].args[2]['content'], 'Please try again')

    async def test_bug_button_uses_private_ticket_and_returns_link(self):
        b = bot.ForgeBot()
        b.api = AsyncMock(return_value={})
        b.create_ticket = AsyncMock(return_value={'id': 'private-ticket'})
        await b.handle_interaction(self.event('bug_ticket', bot.CHANNELS['bug_reports']))
        b.create_ticket.assert_awaited_once_with('requester', 'test-user', bug=True)
        self.assertIn('<#private-ticket>', b.api.call_args_list[-1].args[2]['content'])

    async def test_ticket_failure_does_not_claim_success(self):
        b = bot.ForgeBot()
        b.api = AsyncMock(return_value=None)
        result = await b.create_ticket('user', 'name')
        self.assertIn('error', result)
        self.assertNotIn('user', b.ticket_cooldown)

    async def test_add_member_failure_archives_unusable_ticket(self):
        b = bot.ForgeBot()
        b.api = AsyncMock(side_effect=[{'id': 'thread'}, None, {}])
        result = await b.create_ticket('user', 'name')
        self.assertIn('error', result)
        b.api.assert_any_await('PATCH', '/channels/thread', {'archived': True, 'locked': True})

    async def test_successful_ticket_is_private_and_invites_requester(self):
        b = bot.ForgeBot()
        b.log = AsyncMock()
        b.api = AsyncMock(side_effect=[{'id': 'thread'}, {}, [], {'id': 'welcome'}])
        result = await b.create_ticket('user', 'name', bug=True)
        self.assertEqual(result, {'id': 'thread'})
        payload = b.api.call_args_list[0].args[2]
        self.assertEqual(payload['type'], 12)
        self.assertFalse(payload['invitable'])
        b.api.assert_any_await('PUT', '/channels/thread/thread-members/user')
        welcome = b.api.call_args_list[-1].args[2]
        self.assertEqual(welcome['allowed_mentions'], {'parse': []})
        self.assertIn('\n', welcome['embeds'][0]['description'])
        self.assertNotIn('\\n', welcome['embeds'][0]['description'])

    async def test_close_control_cannot_target_another_channel(self):
        b = bot.ForgeBot()
        b.api = AsyncMock(return_value={'id': 'thread', 'type': 12, 'parent_id': bot.CHANNELS['open_ticket']})
        await b.handle_interaction(self.event('close_ticket_other', 'thread'))
        self.assertFalse(any(c.args[0] == 'PATCH' and c.args[1] == '/channels/thread' for c in b.api.call_args_list))

    async def test_role_failure_is_not_reported_as_success(self):
        b = bot.ForgeBot()
        b.api = AsyncMock(return_value=None)
        await b.handle_interaction(self.event('role_es_trader', bot.CHANNELS['get_roles']))
        self.assertIn('could not be updated', b.api.call_args_list[-1].args[2]['content'])

    async def test_founder_role_is_never_self_assignable(self):
        b = bot.ForgeBot()
        b.api = AsyncMock(return_value={})
        await b.handle_interaction(self.event('role_founder', bot.CHANNELS['get_roles']))
        self.assertFalse(any(c.args[0] == 'PUT' for c in b.api.call_args_list))

    async def test_other_guild_cannot_use_controls(self):
        b = bot.ForgeBot()
        b.api = AsyncMock()
        event = self.event()
        event['guild_id'] = 'other-guild'
        await b.handle_interaction(event)
        b.api.assert_not_awaited()
