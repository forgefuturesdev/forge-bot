from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
import unittest

# Reuse the repository's offline dependency fixtures; no live posts in tests.
import test_market_safety
import discord_briefing as briefing
import newsroom


def response(code, body):
    return SimpleNamespace(status_code=code, json=lambda: body)


class BriefingDeliveryTests(unittest.TestCase):
    def test_delivery_retries_in_process_without_relying_on_railway_restart(self):
        with patch.object(briefing.sys, 'argv', ['discord_briefing.py', 'uk', '--force']), patch.object(briefing, 'deliver_session', side_effect=[False, RuntimeError('temporary'), True]) as delivery, patch('time.sleep') as sleep:
            briefing.main()
            self.assertEqual(delivery.call_count, 3)
            self.assertEqual([c.args[0] for c in sleep.call_args_list], [15, 30])

    def test_exhausted_delivery_retries_exit_nonzero(self):
        with patch.object(briefing.sys, 'argv', ['discord_briefing.py', 'uk', '--force']), patch.object(briefing, 'deliver_session', return_value=False), patch('time.sleep'):
            with self.assertRaises(SystemExit) as failure:
                briefing.main()
            self.assertEqual(failure.exception.code, 1)

    def test_late_start_is_allowed_for_all_sessions_in_both_seasons(self):
        for session, hour, minute, month in [
            ('uk', 6, 30, 9), ('uk', 7, 30, 1),
            ('us', 13, 0, 9), ('us', 14, 0, 1),
            ('asia', 22, 30, 9), ('asia', 23, 30, 1),
        ]:
            target = datetime(2026, month, 16, hour, minute, tzinfo=timezone.utc)
            for delay in [0, 1, 2, 4, 10, 30, 44]:
                with self.subTest(session=session, month=month, delay=delay):
                    self.assertTrue(briefing.should_run_session(session, target + timedelta(minutes=delay)))
            self.assertFalse(briefing.should_run_session(session, target - timedelta(seconds=1)))
            self.assertFalse(briefing.should_run_session(session, target + timedelta(minutes=45)))
            self.assertFalse(briefing.should_run_session(session, target + timedelta(hours=1)))

    def test_weekends_are_not_silently_suppressed(self):
        for day in [19, 20]:
            self.assertTrue(briefing.should_run_session('uk', datetime(2026, 9, day, 6, 33, tzinfo=timezone.utc)))

    def test_midnight_keeps_asia_session_date(self):
        now = datetime(2026, 1, 17, 0, 5, tzinfo=timezone.utc)
        self.assertTrue(briefing.should_run_session('asia', now))
        self.assertEqual(briefing.session_delivery_key('asia', now), 'Forge briefing | asia | 2026-01-16')

    def test_dst_mismatch_weeks_use_each_sessions_own_timezone(self):
        for month, day in [(3, 16), (10, 26)]:
            self.assertTrue(briefing.should_run_session('uk', datetime(2026, month, day, 7, 33, tzinfo=timezone.utc)))
            self.assertTrue(briefing.should_run_session('us', datetime(2026, month, day, 13, 3, tzinfo=timezone.utc)))

    def test_existing_published_post_is_not_sent_again(self):
        with patch.object(briefing, 'prior_delivery', return_value={'id': 'posted', 'flags': 1}), patch.object(briefing, 'post_discord') as send:
            self.assertTrue(briefing.deliver_session('uk', datetime.now(timezone.utc)))
            send.assert_not_called()

    def test_partial_delivery_retries_publish_without_duplicate(self):
        with patch.object(briefing, 'prior_delivery', return_value={'id': 'posted', 'flags': 0}), patch.object(briefing.requests, 'post', return_value=response(200, {})) as publish, patch.object(briefing, 'post_discord') as send:
            self.assertTrue(briefing.deliver_session('uk', datetime.now(timezone.utc)))
            self.assertIn('/posted/crosspost', publish.call_args.args[0])
            send.assert_not_called()

    def test_history_failure_stops_delivery(self):
        with patch.object(briefing.requests, 'get', return_value=response(403, {})):
            with self.assertRaises(RuntimeError):
                briefing.prior_delivery('key')

    def test_other_users_cannot_spoof_delivery_marker(self):
        marker = 'Forge briefing | uk | 2026-09-16'
        body = [{'author': {'id': 'someone'}, 'embeds': [{'footer': {'text': marker}}]}]
        with patch.object(briefing.requests, 'get', return_value=response(200, body)):
            self.assertIsNone(briefing.prior_delivery(marker))

    def test_first_delivery_has_persistent_key_and_nonce(self):
        now = datetime(2026, 9, 19, 6, 33, tzinfo=timezone.utc)
        with patch.object(briefing, 'prior_delivery', return_value=None), patch.object(briefing, 'build_briefing', return_value={'description': 'Session', 'footer': {'text': 'Source'}}), patch.object(briefing, 'post_discord', return_value=True) as send:
            self.assertTrue(briefing.deliver_session('uk', now))
            self.assertIn('Weekend edition', send.call_args.args[2][0]['description'])
            self.assertEqual(send.call_args.kwargs['delivery_key'], 'Forge briefing | uk | 2026-09-19')
        with patch.object(newsroom.requests, 'post', return_value=response(200, {'id': 'a'})) as send:
            newsroom.post_discord('t', 'c', [{'title': 'test'}], delivery_key='key')
            payload = send.call_args.kwargs['json']
            self.assertTrue(payload['enforce_nonce'])
            self.assertEqual(len(payload['nonce']), 24)
