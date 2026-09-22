from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import os
import sys
import types
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape

os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
requests_stub = types.ModuleType("requests")
requests_stub.RequestException = Exception
requests_stub.get = lambda *args, **kwargs: None
requests_stub.post = lambda *args, **kwargs: None
sys.modules.setdefault("requests", requests_stub)

import market_feed
import newsroom


NOW = datetime(2026, 9, 21, 17, 0, tzinfo=timezone.utc)


def rss_item(title="Nasdaq futures rise - Reuters", url="https://example.com/news", date=None):
    published = format_datetime(date or NOW)
    return (
        f"<item><title>{escape(title)}</title><link>{escape(url)}</link>"
        f"<pubDate>{published}</pubDate><source>Reuters</source></item>"
    )


def rss(*items):
    return ("<rss><channel>" + "".join(items) + "</channel></rss>").encode()


def response(status=200, content=None):
    return types.SimpleNamespace(status_code=status, content=content or rss(rss_item()))


class MarketNewsTests(unittest.TestCase):
    def test_parses_dated_source_linked_headlines(self):
        items = newsroom.parse_market_news_rss(rss(rss_item()), source="Google News", now=NOW)
        self.assertEqual(items[0]["title"], "Nasdaq futures rise")
        self.assertEqual(items[0]["source"], "Reuters")
        self.assertEqual(items[0]["url"], "https://example.com/news")

    def test_rejects_stale_future_undated_and_unsafe_items(self):
        content = rss(
            rss_item(date=NOW - timedelta(hours=49)),
            rss_item(date=NOW + timedelta(hours=1)),
            rss_item(url="javascript:alert(1)"),
            "<item><title>Undated</title><link>https://example.com/a</link></item>",
            rss_item(title=""),
        )
        self.assertEqual(newsroom.parse_market_news_rss(content, source="CNBC", now=NOW), [])

    def test_malformed_and_oversized_responses_are_not_headlines(self):
        for content in (b"<html>bad gateway", b"x" * 1_000_001, b"<rss><channel/></rss>"):
            self.assertEqual(newsroom.parse_market_news_rss(content, source="CNBC", now=NOW), [])

    def test_retry_recovers_without_using_backup(self):
        content = rss(rss_item(date=datetime.now(timezone.utc)))
        with patch.object(newsroom.requests, "get", side_effect=[response(503), response(content=content)]) as get:
            items = newsroom.fetch_market_news()
        self.assertEqual(len(items), 1)
        self.assertEqual(get.call_count, 2)
        self.assertTrue(all(call.args[0] == newsroom.NEWS_RSS_URL for call in get.call_args_list))
        self.assertTrue(all(call.kwargs["timeout"] == 10 for call in get.call_args_list))

    def test_backup_recovers_after_primary_network_failure(self):
        content = rss(rss_item(date=datetime.now(timezone.utc)))
        with patch.object(newsroom.requests, "get", side_effect=[
            newsroom.requests.RequestException("offline"), response(502), response(content=content),
        ]) as get:
            items = newsroom.fetch_market_news()
        self.assertEqual(len(items), 1)
        self.assertEqual(get.call_args.args[0], newsroom.NEWS_BACKUP_RSS_URL)

    def test_empty_feed_falls_back_and_results_are_deduplicated_and_limited(self):
        date = datetime.now(timezone.utc)
        content = rss(rss_item(date=date), rss_item(date=date), rss_item("Other headline", "https://example.com/b", date))
        with patch.object(newsroom.requests, "get", side_effect=[
            response(content=b"<rss><channel/></rss>"), response(content=b"not xml"), response(content=content),
        ]):
            self.assertEqual(len(newsroom.fetch_market_news(count=1)), 1)

    def test_total_outage_stays_failed_with_bounded_attempts_and_no_post(self):
        with patch.object(newsroom.requests, "get", return_value=response(503)) as get, patch.object(
            market_feed, "post_discord"
        ) as post:
            self.assertFalse(market_feed.post_market_news())
        self.assertEqual(get.call_count, 4)
        post.assert_not_called()

    def test_already_posted_news_is_success_without_duplicate_send(self):
        item = {"title": "Nasdaq futures rise", "url": "https://example.com/news"}
        with patch.object(market_feed, "get_market_news", return_value=[item]), patch.object(
            market_feed, "recent_channel_links", return_value={item["url"]}
        ), patch.object(market_feed, "post_discord") as post:
            self.assertTrue(market_feed.post_market_news())
        post.assert_not_called()

    def test_market_feed_uses_rss_helper_not_search_client(self):
        with patch.object(market_feed, "fetch_market_news", return_value=[]) as fetch:
            self.assertEqual(market_feed.get_market_news(5), [])
        fetch.assert_called_once_with(5, headers=market_feed.SOURCE_HEADERS, timeout=10)


if __name__ == "__main__":
    unittest.main()
