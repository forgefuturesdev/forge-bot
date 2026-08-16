#!/usr/bin/env python3
"""Source-linked Forge Futures briefings for the major market sessions."""

from datetime import datetime, timedelta, timezone
import os
import sys
from zoneinfo import ZoneInfo

import feedparser
import requests

from newsroom import (
    FORGE_ORANGE,
    brand_embed,
    filter_unseen_news,
    headline_category,
    post_discord,
    recent_channel_links,
    render_calendar_events,
    render_headlines,
    render_market_lens,
    select_calendar_events,
)


TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL = os.environ.get(
    "DISCORD_DAILY_HIGHLIGHTS_CHANNEL_ID",
    "1482427993140760636",
)
REQUEST_TIMEOUT_SECONDS = 10
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}


SESSION_CONFIG = {
    "uk": {
        "title": "🇬🇧 LONDON OPEN · MARKET DESK",
        "timezone": "Europe/London",
        "schedule_timezone": "Europe/London",
        "target_time": (7, 30),
        "query": "stock market UK FTSE Europe futures today",
        "snapshot": [
            ("ES", "ES=F", 2),
            ("NQ", "NQ=F", 2),
            ("FTSE", "%5EFTSE", 2),
            ("DAX", "%5EGDAXI", 2),
        ],
        "cross_market": [
            ("GBP/USD", "GBPUSD=X", 4),
            ("EUR/USD", "EURUSD=X", 4),
            ("VIX", "%5EVIX", 2),
            ("DXY", "DX-Y.NYB", 3),
            ("US 10Y", "%5ETNX", 3),
        ],
    },
    "us": {
        "title": "🇺🇸 NEW YORK OPEN · MARKET DESK",
        "timezone": "America/New_York",
        "schedule_timezone": "America/New_York",
        "target_time": (9, 0),
        "query": "S&P 500 Nasdaq futures US market economy today",
        "snapshot": [
            ("ES", "ES=F", 2),
            ("NQ", "NQ=F", 2),
            ("VIX", "%5EVIX", 2),
        ],
        "cross_market": [
            ("DXY", "DX-Y.NYB", 3),
            ("US 10Y", "%5ETNX", 3),
            ("Crude", "CL=F", 2),
            ("Gold", "GC=F", 2),
        ],
    },
    "asia": {
        "title": "🌏 ASIA OPEN · MARKET DESK",
        "timezone": "Asia/Tokyo",
        "schedule_timezone": "Europe/London",
        "target_time": (23, 30),
        "query": "Asia markets Nikkei Hang Seng futures today",
        "snapshot": [
            ("ES", "ES=F", 2),
            ("NQ", "NQ=F", 2),
            ("Nikkei", "%5EN225", 2),
            ("Hang Seng", "%5EHSI", 2),
        ],
        "cross_market": [
            ("USD/JPY", "JPY=X", 3),
            ("VIX", "%5EVIX", 2),
            ("Crude", "CL=F", 2),
            ("Gold", "GC=F", 2),
        ],
    },
}


def get_quote(symbol: str) -> dict:
    try:
        response = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"interval": "1d", "range": "5d"},
            headers=YAHOO_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            return {}
        results = response.json().get("chart", {}).get("result") or []
        if not results:
            return {}
        meta = results[0].get("meta", {})
        return {
            "price": meta.get("regularMarketPrice"),
            "prev": meta.get("previousClose") or meta.get("chartPreviousClose"),
            "timestamp": meta.get("regularMarketTime"),
        }
    except (requests.RequestException, TypeError, ValueError):
        return {}


def get_news(query: str, count: int = 10) -> list[dict]:
    try:
        response = requests.get(
            "https://news.google.com/rss/search",
            params={"q": query, "hl": "en-GB", "gl": "GB", "ceid": "GB:en"},
            headers=YAHOO_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            return []
        feed = feedparser.parse(response.content)
    except requests.RequestException:
        return []

    items: list[dict] = []
    for entry in feed.entries[:count]:
        title = str(entry.get("title") or "")
        source = entry.get("source") or {}
        source_name = source.get("title") if isinstance(source, dict) else str(source)
        if not source_name and " - " in title:
            title, source_name = title.rsplit(" - ", 1)
        item = {
            "title": title,
            "source": source_name or "Google News",
            "url": entry.get("link"),
        }
        item["category"] = headline_category(title)
        items.append(item)
    return items


def get_calendar_feed() -> list[dict]:
    try:
        response = requests.get(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            headers=YAHOO_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        return response.json() if response.status_code == 200 else []
    except (requests.RequestException, TypeError, ValueError):
        return []


def format_price(value: object, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):,.{decimals}f}"


def format_change(price: object, previous: object) -> str:
    if price is None or previous in (None, 0):
        return "   N/A"
    percentage = ((float(price) - float(previous)) / float(previous)) * 100
    arrow = "▲" if percentage >= 0 else "▼"
    return f"{arrow} {percentage:+.2f}%"


def render_quote_board(rows: list[tuple[str, str, int]], quotes: dict[str, dict]) -> str:
    rendered: list[str] = []
    for label, symbol, decimals in rows:
        quote = quotes.get(symbol, {})
        rendered.append(
            f"{label:<10} {format_price(quote.get('price'), decimals):>12}  "
            f"{format_change(quote.get('price'), quote.get('prev'))}"
        )
    return "```\n" + "\n".join(rendered) + "\n```"


def quote_as_of(quotes: dict[str, dict]) -> str:
    timestamps = [
        int(quote["timestamp"])
        for quote in quotes.values()
        if quote.get("timestamp")
    ]
    if not timestamps:
        return "Quote timestamp unavailable"
    observed = datetime.fromtimestamp(max(timestamps), tz=timezone.utc)
    london = observed.astimezone(ZoneInfo("Europe/London"))
    new_york = observed.astimezone(ZoneInfo("America/New_York"))
    return f"Quotes as of {london:%d %b %H:%M UK} / {new_york:%H:%M ET}"


def build_briefing(session: str) -> dict:
    config = SESSION_CONFIG[session]
    symbols = {
        symbol
        for _, symbol, _ in config["snapshot"] + config["cross_market"]
    }
    quotes = {symbol: get_quote(symbol) for symbol in symbols}

    seen_links = recent_channel_links(TOKEN, CHANNEL, limit=40)
    headlines = filter_unseen_news(
        get_news(config["query"]),
        seen_links,
        limit=4,
    )
    calendar = select_calendar_events(
        get_calendar_feed(),
        start=datetime.now(timezone.utc) - timedelta(hours=1),
        hours=37,
    )

    local_now = datetime.now(ZoneInfo(config["timezone"]))
    embed = {
        "title": config["title"],
        "description": (
            f"**{local_now:%A %d %B %Y}** · Indicative session overview. "
            "Confirm time-sensitive information with the linked sources."
        ),
        "color": FORGE_ORANGE,
        "fields": [
            {
                "name": "SESSION SNAPSHOT",
                "value": render_quote_board(config["snapshot"], quotes),
                "inline": False,
            },
            {
                "name": "CROSS-MARKET BOARD",
                "value": render_quote_board(config["cross_market"], quotes),
                "inline": False,
            },
            {
                "name": "NEXT RISK WINDOWS",
                "value": render_calendar_events(calendar, limit=4),
                "inline": False,
            },
            {
                "name": "WHAT'S MOVING",
                "value": render_headlines(headlines, limit=4),
                "inline": False,
            },
            {
                "name": "TRADER LENS",
                "value": render_market_lens(headlines),
                "inline": False,
            },
            {
                "name": "DATA CHECK",
                "value": (
                    f"{quote_as_of(quotes)}. Yahoo Finance quotes and the public "
                    "calendar feed may be delayed, stale or incomplete."
                ),
                "inline": False,
            },
        ],
    }
    return brand_embed(embed, data_note="Indicative data may be delayed")


def build_uk_briefing() -> dict:
    return build_briefing("uk")


def build_us_briefing() -> dict:
    return build_briefing("us")


def build_asia_briefing() -> dict:
    return build_briefing("asia")


def post_embed(embed: dict) -> bool:
    result = post_discord(TOKEN, CHANNEL, [embed], publish=True)
    return bool(result)


def should_run_session(session: str, now: datetime | None = None) -> bool:
    config = SESSION_CONFIG[session]
    utc_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    local_now = utc_now.astimezone(ZoneInfo(config["schedule_timezone"]))
    target_hour, target_minute = config["target_time"]
    return (local_now.hour, local_now.minute) == (target_hour, target_minute)


def main() -> None:
    args = sys.argv[1:]
    session = args[0] if args else "uk"
    if session not in SESSION_CONFIG:
        print(f"Unknown session: {session}")
        raise SystemExit(2)
    if "--force" not in args and not should_run_session(session):
        timezone_name = SESSION_CONFIG[session]["schedule_timezone"]
        target_hour, target_minute = SESSION_CONFIG[session]["target_time"]
        print(
            f"SKIP: {session.upper()} briefing is scheduled for "
            f"{target_hour:02d}:{target_minute:02d} {timezone_name}"
        )
        return

    posted = post_embed(build_briefing(session))
    if not posted:
        print(f"ERROR: {session.upper()} briefing failed")
        raise SystemExit(1)
    print(f"OK: {session.upper()} briefing posted and published")


if __name__ == "__main__":
    main()
