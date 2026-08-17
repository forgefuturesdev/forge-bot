#!/usr/bin/env python3
"""Forge Futures market headlines, economic calendar and weekly outlook."""

from datetime import datetime, timedelta, timezone
import os
import sys
from zoneinfo import ZoneInfo

from ddgs import DDGS
import requests

from newsroom import (
    FORGE_ORANGE,
    brand_embed,
    fetch_economic_calendar,
    filter_unseen_news,
    headline_category,
    headline_fields,
    post_discord as send_discord,
    recent_channel_links,
    render_calendar_events,
    render_market_lens,
    select_calendar_events,
)


DISCORD_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
MARKET_WATCH = os.environ.get(
    "DISCORD_MARKET_WATCH_CHANNEL_ID",
    "1482020924298362912",
)
ANNOUNCEMENTS_CHANNEL = os.environ.get(
    "DISCORD_ANNOUNCEMENTS_CHANNEL_ID",
    "1482020877146263594",
)
REQUEST_TIMEOUT_SECONDS = 10
SOURCE_HEADERS = {"User-Agent": "Mozilla/5.0"}


def post_discord(channel_id: str, embeds: list[dict], *, publish: bool = False) -> bool:
    return bool(
        send_discord(
            DISCORD_TOKEN,
            channel_id,
            embeds,
            publish=publish,
        )
    )


def calendar_fields(
    events: list[dict],
    *,
    title: str,
    limit: int,
) -> list[dict]:
    if not events:
        return [{
            "name": title,
            "value": render_calendar_events([]),
            "inline": False,
        }]
    fields: list[dict] = []
    selected = events[:limit]
    for index in range(0, len(selected), 4):
        chunk = selected[index:index + 4]
        suffix = "" if index == 0 else f" · CONTINUED {index // 4 + 1}"
        fields.append({
            "name": f"{title}{suffix}",
            "value": render_calendar_events(chunk, limit=4),
            "inline": False,
        })
    return fields


def get_economic_calendar() -> list[dict]:
    return fetch_economic_calendar(
        headers=SOURCE_HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def post_daily_calendar() -> bool:
    events = get_economic_calendar()
    if not events:
        print("Economic calendar source returned no data")
        return False

    now = datetime.now(timezone.utc)
    selected = select_calendar_events(
        events,
        start=now - timedelta(hours=1),
        hours=37,
        impacts=("High", "Medium"),
    )
    london_now = now.astimezone(ZoneInfo("Europe/London"))
    embed = brand_embed(
        {
            "title": "📊 ECONOMIC CALENDAR · NEXT 36 HOURS",
            "description": (
                f"**{london_now:%A %d %B %Y}** · USD-focused medium and "
                "high-impact releases, shown in UK and New York time."
            ),
            "color": FORGE_ORANGE,
            "fields": calendar_fields(
                selected,
                title="SCHEDULED RISK WINDOWS",
                limit=8,
            ) + [
                {
                    "name": "HOW TO USE THIS",
                    "value": (
                        "• Confirm event times with a primary calendar before trading.\n"
                        "• Forecasts are estimates, not outcomes.\n"
                        "• Volatility can rise before and after scheduled releases."
                    ),
                    "inline": False,
                },
            ],
        },
        timestamp=now,
        data_note="Public calendar feed may be delayed or incomplete",
    )
    return post_discord(MARKET_WATCH, [embed])


def get_market_news(count: int = 14) -> list[dict]:
    try:
        results = list(
            DDGS().news(
                "futures market S&P 500 Nasdaq Federal Reserve economy",
                max_results=count,
            )
        )
    except Exception as exc:
        print(f"Market news search failed: {type(exc).__name__}")
        return []

    items: list[dict] = []
    for result in results:
        title = str(result.get("title") or "")
        items.append(
            {
                "title": title,
                "source": result.get("source") or "Market source",
                "url": result.get("url"),
                "category": headline_category(title),
            }
        )
    return items


def post_market_news() -> bool:
    news = get_market_news()
    if not news:
        return False

    seen_links = recent_channel_links(DISCORD_TOKEN, MARKET_WATCH, limit=80)
    fresh_news = filter_unseen_news(news, seen_links, limit=5)
    if not fresh_news:
        print("No fresh market headlines to post")
        return True

    now = datetime.now(timezone.utc)
    london_now = now.astimezone(ZoneInfo("Europe/London"))
    embed = brand_embed(
        {
            "title": "📰 MARKET PULSE",
            "description": (
                f"**{london_now:%A %d %B · %H:%M UK}** · Fresh, source-linked "
                "headlines selected for index-futures traders."
            ),
            "color": FORGE_ORANGE,
            "fields": headline_fields(
                fresh_news,
                title="WHAT'S MOVING",
                limit=5,
            ) + [
                {
                    "name": "TRADER LENS",
                    "value": render_market_lens(fresh_news),
                    "inline": False,
                },
            ],
        },
        timestamp=now,
        data_note="Headlines can change after publication",
    )
    # Market Watch is the higher-frequency internal feed. Curated session and
    # weekly posts are the outward-facing messages published to followers.
    return post_discord(MARKET_WATCH, [embed])


def post_weekly_ahead() -> bool:
    events = get_economic_calendar()
    if not events:
        print("Economic calendar source returned no data")
        return False

    now = datetime.now(timezone.utc)
    selected = select_calendar_events(
        events,
        start=now - timedelta(hours=1),
        hours=24 * 8,
        impacts=("High",),
    )
    embed = brand_embed(
        {
            "title": "📋 THE WEEK AHEAD · KEY EVENTS",
            "description": (
                "The major USD risk windows currently shown by the calendar feed. "
                "Times are displayed in both the UK and New York time zones."
            ),
            "color": FORGE_ORANGE,
            "fields": calendar_fields(
                selected,
                title="HIGH-IMPACT CALENDAR",
                limit=12,
            ) + [
                {
                    "name": "FORGE CHECKLIST",
                    "value": (
                        "• Mark the main release windows before the week begins.\n"
                        "• Reconfirm dates and times with primary sources.\n"
                        "• Treat forecasts as context rather than a directional signal."
                    ),
                    "inline": False,
                },
            ],
        },
        timestamp=now,
        data_note="Public calendar feed may be delayed or incomplete",
    )
    return post_discord(ANNOUNCEMENTS_CHANNEL, [embed], publish=True)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    handlers = {
        "calendar": post_daily_calendar,
        "news": post_market_news,
        "weekly": post_weekly_ahead,
    }
    if mode == "all":
        selected = ["calendar", "news"]
    elif mode in handlers:
        selected = [mode]
    else:
        print(f"Unknown market feed mode: {mode}")
        raise SystemExit(2)

    failures: list[str] = []
    for selected_mode in selected:
        if handlers[selected_mode]():
            print(f"OK: {selected_mode.title()} completed")
        else:
            failures.append(selected_mode)
            print(f"ERROR: {selected_mode.title()} failed")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
