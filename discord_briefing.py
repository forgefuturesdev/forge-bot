#!/usr/bin/env python3
"""
Forge Futures — Discord Daily Market Briefings
3x daily in #daily-highlights:
  🇬🇧 UK Open — 7:30 AM GMT
  🇺🇸 US Open — 2:00 PM GMT
  🌏 Asia Open — 11:30 PM GMT
Each tailored to its region with a global snapshot.
"""
import requests
import json
import feedparser
import sys
from datetime import datetime, timezone
import os

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
BASE = "https://discord.com/api/v10"
HEADERS_D = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
CHANNEL = "1482427993140760636"  # daily-highlights
ORANGE = 0xFE602F
YF_HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_quote(symbol):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d",
                        headers=YF_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()["chart"]["result"][0]
            meta = data["meta"]
            quotes = data.get("indicators", {}).get("quote", [{}])[0]
            info = {"price": meta.get("regularMarketPrice"),
                    "prev": meta.get("previousClose") or meta.get("chartPreviousClose")}
            if quotes.get("high"):
                info["high_5d"] = max(h for h in quotes["high"] if h)
            if quotes.get("low"):
                info["low_5d"] = min(l for l in quotes["low"] if l)
            return info
    except: pass
    return {}

def fmt(val, dec=2):
    if not val: return "N/A"
    return f"{val:,.{dec}f}" if val > 100 else f"{val:.{dec}f}"

def chg(price, prev):
    if not price or not prev: return "N/A", "◆"
    pct = ((price - prev) / prev) * 100
    return f"{"+" if pct >= 0 else ""}{pct:.2f}%", "▲" if pct >= 0 else "▼"

def get_news(query, count=5):
    items = []
    try:
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en")
        for e in feed.entries[:count]:
            title = e.title
            if " - " in title: title = title.rsplit(" - ", 1)[0]
            items.append(title[:100])
    except: pass
    return items

def get_calendar():
    events = []
    try:
        r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=10)
        if r.status_code == 200:
            for e in r.json():
                if e.get("impact") == "High":
                    events.append(f"◆ {e.get('title', 'Unknown')} — Forecast: {e.get('forecast', 'N/A')} | Prev: {e.get('previous', 'N/A')}")
    except: pass
    return events[:6]

def build_uk_briefing():
    """UK/London open briefing — focus on European markets."""
    es = get_quote("ES=F"); nq = get_quote("NQ=F")
    vix = get_quote("%5EVIX"); oil = get_quote("CL=F")
    gold = get_quote("GC=F"); dxy = get_quote("DX-Y.NYB")
    tnx = get_quote("%5ETNX")
    ftse = get_quote("%5EFTSE"); dax = get_quote("%5EGDAXI")
    gbp = get_quote("GBPUSD=X"); eur = get_quote("EURUSD=X")
    
    es_chg, es_arr = chg(es.get("price"), es.get("prev"))
    nq_chg, nq_arr = chg(nq.get("price"), nq.get("prev"))
    ftse_chg, ftse_arr = chg(ftse.get("price"), ftse.get("prev"))
    dax_chg, dax_arr = chg(dax.get("price"), dax.get("prev"))
    
    vp = vix.get("price", 0)
    vix_label = "Low" if vp < 15 else ("Neutral" if vp < 20 else ("Elevated" if vp < 30 else "High Fear"))
    
    news = get_news("stock+market+UK+FTSE+Europe+today")
    calendar = get_calendar()
    
    news_text = "\n".join(f"◆ {n}" for n in news[:5]) or "◆ No major headlines"
    cal_text = "\n".join(calendar[:4]) or "◆ No high-impact events today"
    
    return {
        "title": "🇬🇧  LONDON OPEN — DAILY BRIEFING",
        "description": f"**{datetime.now().strftime('%A %d %B %Y')}** — Pre-market overview ahead of the London session.",
        "color": ORANGE,
        "fields": [
            {"name": "━━  US FUTURES  ━━", "inline": False,
             "value": f"```\nES  (S&P 500)   {fmt(es.get('price'))}   {es_arr} {es_chg}\nNQ  (Nasdaq)   {fmt(nq.get('price'))}   {nq_arr} {nq_chg}\n```"},
            {"name": "━━  EUROPE  ━━", "inline": False,
             "value": f"```\nFTSE 100      {fmt(ftse.get('price'))}   {ftse_arr} {ftse_chg}\nDAX           {fmt(dax.get('price'))}   {dax_arr} {dax_chg}\nGBP/USD         {fmt(gbp.get('price'),4)}   {chg(gbp.get('price'),gbp.get('prev'))[1]} {chg(gbp.get('price'),gbp.get('prev'))[0]}\nEUR/USD         {fmt(eur.get('price'),4)}   {chg(eur.get('price'),eur.get('prev'))[1]} {chg(eur.get('price'),eur.get('prev'))[0]}\n```"},
            {"name": "━━  MACRO  ━━", "inline": False,
             "value": f"```\nVIX            {fmt(vix.get('price'))}   ({vix_label})\nDXY            {fmt(dxy.get('price'),3)}\n10Y Yield      {fmt(tnx.get('price'),3)}%\nCrude Oil    ${fmt(oil.get('price'))}\nGold         ${fmt(gold.get('price'))}\n```"},
            {"name": "━━  ECONOMIC CALENDAR  ━━", "inline": False, "value": cal_text},
            {"name": "━━  HEADLINES  ━━", "inline": False, "value": news_text},
        ],
        "footer": {"text": "Forge Futures ◆ Next: US Open (2:00 PM GMT)"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

def build_us_briefing():
    """US/New York open briefing — focus on US markets."""
    es = get_quote("ES=F"); nq = get_quote("NQ=F")
    vix = get_quote("%5EVIX"); oil = get_quote("CL=F")
    gold = get_quote("GC=F"); dxy = get_quote("DX-Y.NYB")
    tnx = get_quote("%5ETNX")
    
    es_chg, es_arr = chg(es.get("price"), es.get("prev"))
    nq_chg, nq_arr = chg(nq.get("price"), nq.get("prev"))
    
    vp = vix.get("price", 0)
    vix_label = "Low" if vp < 15 else ("Neutral" if vp < 20 else ("Elevated" if vp < 30 else "High Fear"))
    
    news = get_news("stock+market+US+S%26P+Nasdaq+today")
    
    es_levels = ""
    if es.get("price"):
        p = es["price"]
        es_levels = f"**ES** Support: {round(p-50,-1):,.0f} / {round(p-100,-1):,.0f}  ◆  Resistance: {round(p+50,-1):,.0f} / {round(p+100,-1):,.0f}"
    nq_levels = ""
    if nq.get("price"):
        p = nq["price"]
        nq_levels = f"\n**NQ** Support: {round(p-200,-2):,.0f} / {round(p-400,-2):,.0f}  ◆  Resistance: {round(p+200,-2):,.0f} / {round(p+400,-2):,.0f}"
    
    news_text = "\n".join(f"◆ {n}" for n in news[:5]) or "◆ No major headlines"
    
    return {
        "title": "🇺🇸  NEW YORK OPEN — DAILY BRIEFING",
        "description": f"**{datetime.now().strftime('%A %d %B %Y')}** — Pre-market overview ahead of the US session.",
        "color": ORANGE,
        "fields": [
            {"name": "━━  US FUTURES  ━━", "inline": False,
             "value": f"```\nES  (S&P 500)   {fmt(es.get('price'))}   {es_arr} {es_chg}\nNQ  (Nasdaq)   {fmt(nq.get('price'))}   {nq_arr} {nq_chg}\n```"},
            {"name": "━━  MACRO  ━━", "inline": False,
             "value": f"```\nVIX            {fmt(vix.get('price'))}   ({vix_label})\nDXY            {fmt(dxy.get('price'),3)}\n10Y Yield      {fmt(tnx.get('price'),3)}%\nCrude Oil    ${fmt(oil.get('price'))}\nGold         ${fmt(gold.get('price'))}\n```"},
            {"name": "━━  KEY LEVELS  ━━", "inline": False, "value": es_levels + nq_levels},
            {"name": "━━  HEADLINES  ━━", "inline": False, "value": news_text},
        ],
        "footer": {"text": "Forge Futures ◆ Next: Asia Open (11:30 PM GMT)"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

def build_asia_briefing():
    """Asia open briefing — focus on Asian markets + overnight preview."""
    es = get_quote("ES=F"); nq = get_quote("NQ=F")
    vix = get_quote("%5EVIX")
    nikkei = get_quote("%5EN225")
    hsi = get_quote("%5EHSI")
    
    es_chg, es_arr = chg(es.get("price"), es.get("prev"))
    nq_chg, nq_arr = chg(nq.get("price"), nq.get("prev"))
    nik_chg, nik_arr = chg(nikkei.get("price"), nikkei.get("prev"))
    hsi_chg, hsi_arr = chg(hsi.get("price"), hsi.get("prev"))
    
    news = get_news("stock+market+Asia+Nikkei+today")
    news_text = "\n".join(f"◆ {n}" for n in news[:5]) or "◆ No major headlines"
    
    return {
        "title": "🌏  ASIA OPEN — DAILY BRIEFING",
        "description": f"**{datetime.now().strftime('%A %d %B %Y')}** — Overnight preview ahead of the Asia session.",
        "color": ORANGE,
        "fields": [
            {"name": "━━  US CLOSE  ━━", "inline": False,
             "value": f"```\nES  (S&P 500)   {fmt(es.get('price'))}   {es_arr} {es_chg}\nNQ  (Nasdaq)   {fmt(nq.get('price'))}   {nq_arr} {nq_chg}\nVIX            {fmt(vix.get('price'))}\n```"},
            {"name": "━━  ASIA PACIFIC  ━━", "inline": False,
             "value": f"```\nNikkei 225    {fmt(nikkei.get('price'))}   {nik_arr} {nik_chg}\nHang Seng     {fmt(hsi.get('price'))}   {hsi_arr} {hsi_chg}\n```"},
            {"name": "━━  HEADLINES  ━━", "inline": False, "value": news_text},
        ],
        "footer": {"text": "Forge Futures ◆ Next: UK Open (7:30 AM GMT)"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

def post_embed(embed):
    r = requests.post(f"{BASE}/channels/{CHANNEL}/messages", headers=HEADERS_D,
                      json={"embeds": [embed]})
    return r.status_code == 200

def main():
    session = sys.argv[1] if len(sys.argv) > 1 else "uk"
    
    if session == "uk":
        embed = build_uk_briefing()
    elif session == "us":
        embed = build_us_briefing()
    elif session == "asia":
        embed = build_asia_briefing()
    else:
        print(f"Unknown session: {session}")
        return
    
    ok = post_embed(embed)
    print(f"{'✅' if ok else '❌'} {session.upper()} briefing posted to Discord")

if __name__ == "__main__":
    main()