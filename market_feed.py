#!/usr/bin/env python3
"""
Forge Futures Market Feed — News & Economic Calendar
Posts to Discord #market-watch channel.
Runs on cron or can be called directly.
"""
import requests
import json
from datetime import datetime, timezone, timedelta
from ddgs import DDGS
import os

DISCORD_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
MARKET_WATCH = os.environ.get("DISCORD_MARKET_WATCH_CHANNEL_ID", "1482020924298362912")
HEADERS = {"Authorization": f"Bot {DISCORD_TOKEN}", "Content-Type": "application/json"}
BASE = "https://discord.com/api/v10"

IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟡",
    "Low": "🟢",
    "Holiday": "📅",
    "Non-Economic": "⚪",
}

def post_discord(channel_id, embeds, components=None):
    data = {"embeds": embeds}
    if components:
        data["components"] = components
    r = requests.post(f"{BASE}/channels/{channel_id}/messages",
        headers=HEADERS, json=data)
    return r.status_code in [200, 201]


def get_economic_calendar():
    """Fetch this week's economic calendar from ForexFactory."""
    try:
        r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return []


def post_daily_calendar():
    """Post today's and tomorrow's high/medium impact events."""
    events = get_economic_calendar()
    if not events:
        return False
    
    now = datetime.now(timezone.utc)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    
    # Filter for today and tomorrow, medium+ impact, USD-related
    today_events = []
    tomorrow_events = []
    
    for e in events:
        try:
            event_date = datetime.fromisoformat(e['date']).date()
            impact = e.get('impact', '')
            country = e.get('country', '')
            
            # Focus on USD events (most relevant for ES/NQ) and high-impact global
            if impact in ['High', 'Medium'] and country in ['USD', 'All', '']:
                event_info = {
                    "time": datetime.fromisoformat(e['date']).strftime('%H:%M ET'),
                    "title": e.get('title', ''),
                    "impact": impact,
                    "forecast": e.get('forecast', '—'),
                    "previous": e.get('previous', '—'),
                }
                
                if event_date == today:
                    today_events.append(event_info)
                elif event_date == tomorrow:
                    tomorrow_events.append(event_info)
        except:
            continue
    
    # Build embed
    fields = []
    
    if today_events:
        today_text = ""
        for e in today_events:
            emoji = IMPACT_EMOJI.get(e['impact'], '⚪')
            today_text += f"{emoji} **{e['time']}** — {e['title']}"
            if e['forecast'] != '—':
                today_text += f"\n　Forecast: `{e['forecast']}` | Previous: `{e['previous']}`"
            today_text += "\n"
        fields.append({"name": f"📅 Today ({today.strftime('%a %d %b')})", "value": today_text.strip(), "inline": False})
    else:
        fields.append({"name": f"📅 Today ({today.strftime('%a %d %b')})", "value": "No high-impact USD events today ✅", "inline": False})
    
    if tomorrow_events:
        tmrw_text = ""
        for e in tomorrow_events:
            emoji = IMPACT_EMOJI.get(e['impact'], '⚪')
            tmrw_text += f"{emoji} **{e['time']}** — {e['title']}"
            if e['forecast'] != '—':
                tmrw_text += f"\n　Forecast: `{e['forecast']}` | Previous: `{e['previous']}`"
            tmrw_text += "\n"
        fields.append({"name": f"📅 Tomorrow ({tomorrow.strftime('%a %d %b')})", "value": tmrw_text.strip(), "inline": False})
    
    # Impact key
    fields.append({
        "name": "Impact Key",
        "value": "🔴 High　🟡 Medium　🟢 Low",
        "inline": False
    })
    
    embed = {
        "title": "📊 Economic Calendar",
        "color": 0xFE602F,
        "fields": fields,
        "footer": {"text": f"Updated {now.strftime('%H:%M UTC')} | Source: ForexFactory"},
        "timestamp": now.isoformat()
    }
    
    return post_discord(MARKET_WATCH, [embed])


def post_market_news():
    """Post latest market news relevant to futures traders."""
    try:
        results = DDGS().news("futures market S&P 500 NASDAQ economy", max_results=8)
    except:
        return False
    
    if not results:
        return False
    
    now = datetime.now(timezone.utc)
    
    # Build news items - max 5 most relevant
    news_text = ""
    count = 0
    seen_titles = set()
    
    for r in results:
        title = r.get('title', '')
        source = r.get('source', '')
        url = r.get('url', '')
        
        # Skip duplicates
        title_key = title[:50].lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        
        # Determine impact level based on keywords
        title_lower = title.lower()
        if any(w in title_lower for w in ['fed', 'fomc', 'cpi', 'jobs', 'payroll', 'inflation', 'rate cut', 'rate hike', 'crash', 'surge']):
            emoji = "🔴"
        elif any(w in title_lower for w in ['gdp', 'pmi', 'earnings', 'oil', 'treasury', 'yields', 'housing']):
            emoji = "🟡"
        else:
            emoji = "🟢"
        
        news_text += f"{emoji} **[{title}]({url})**\n{source}\n\n"
        count += 1
        if count >= 5:
            break
    
    if not news_text:
        return False
    
    embed = {
        "title": "📰 Market News",
        "description": news_text,
        "color": 0x2B2D31,
        "footer": {"text": f"Updated {now.strftime('%H:%M UTC')} | 🔴 High 🟡 Medium 🟢 Low impact"},
        "timestamp": now.isoformat()
    }
    
    return post_discord(MARKET_WATCH, [embed])


def post_weekly_ahead():
    """Post upcoming week's key events (Sunday/Monday morning)."""
    events = get_economic_calendar()
    if not events:
        return False
    
    now = datetime.now(timezone.utc)
    
    # Get all high-impact events this week
    high_impact = []
    for e in events:
        if e.get('impact') == 'High' and e.get('country') in ['USD', 'All', '']:
            try:
                dt = datetime.fromisoformat(e['date'])
                high_impact.append({
                    "day": dt.strftime('%A'),
                    "date": dt.strftime('%d %b'),
                    "time": dt.strftime('%H:%M ET'),
                    "title": e.get('title', ''),
                    "forecast": e.get('forecast', '—'),
                    "previous": e.get('previous', '—'),
                })
            except:
                continue
    
    if not high_impact:
        text = "No high-impact USD events this week. Clear to trade ✅"
    else:
        text = ""
        for e in high_impact:
            text += f"🔴 **{e['day']} {e['date']}** at {e['time']}\n"
            text += f"　{e['title']}"
            if e['forecast'] != '—':
                text += f" (Forecast: `{e['forecast']}` | Prev: `{e['previous']}`)"
            text += "\n\n"
    
    embed = {
        "title": "📋 Week Ahead — Key Events",
        "description": text,
        "color": 0xFE602F,
        "footer": {"text": f"Source: ForexFactory | {now.strftime('%d %b %Y')}"},
    }
    
    return post_discord(MARKET_WATCH, [embed])


if __name__ == "__main__":
    import sys
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if mode in ["calendar", "all"]:
        if post_daily_calendar():
            print("✅ Economic calendar posted")
        else:
            print("❌ Calendar failed")
    
    if mode in ["news", "all"]:
        if post_market_news():
            print("✅ Market news posted")
        else:
            print("❌ News failed")
    
    if mode == "weekly":
        if post_weekly_ahead():
            print("✅ Weekly ahead posted")
        else:
            print("❌ Weekly failed")