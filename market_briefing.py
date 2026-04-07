#!/usr/bin/env python3
"""
Forge Futures — Joe's Daily Market Briefing (Telegram)
Single message, twice daily at 7am and 7pm GMT.
Includes market data + headlines + competitor intel.
"""
import requests
import json
import feedparser
from datetime import datetime, timezone
import os

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
JOE = "875670264"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def send(text):
    r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": JOE, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=15)
    if r.status_code != 200:
        # Retry without markdown
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": JOE, "text": text, "disable_web_page_preview": True}, timeout=15)

def get_quote(symbol):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d",
                        headers=HEADERS, timeout=10)
        if r.status_code == 200:
            meta = r.json()["chart"]["result"][0]["meta"]
            return {"price": meta.get("regularMarketPrice"),
                    "prev": meta.get("previousClose") or meta.get("chartPreviousClose")}
    except: pass
    return {}

def chg(price, prev):
    if not price or not prev: return "N/A"
    pct = ((price - prev) / prev) * 100
    return f"{"+" if pct >= 0 else ""}{pct:.2f}%"

def arrow(price, prev):
    if not price or not prev: return "◆"
    return "▲" if price >= prev else "▼"

def get_news():
    items = []
    try:
        feed = feedparser.parse("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258")
        for e in feed.entries[:4]:
            items.append(e.title[:90])
    except: pass
    try:
        feed = feedparser.parse("https://news.google.com/rss/search?q=stock+market+futures+today&hl=en-US&gl=US&ceid=US:en")
        for e in feed.entries[:3]:
            title = e.title
            if " - " in title: title = title.rsplit(" - ", 1)[0]
            items.append(title[:90])
    except: pass
    return items[:6]

def get_competitor_intel():
    intel = []
    # Discord counts
    for name, code in [("Topstep", "topstep"), ("FundedNext", "fundednext"), ("Alpha", "alphatrading")]:
        try:
            r = requests.get(f"https://discord.com/api/v9/invites/{code}?with_counts=true", timeout=5)
            if r.status_code == 200:
                d = r.json()
                intel.append(f"{name}: {d.get("approximate_member_count",0):,} members")
        except: pass
    # News
    for comp in ["FTMO", "Topstep", "FundedNext", "Alpha Futures"]:
        try:
            feed = feedparser.parse(f"https://news.google.com/rss/search?q={comp.replace(" ", "+")}+prop+firm&hl=en-US&gl=US&ceid=US:en")
            for e in feed.entries[:1]:
                title = e.title
                if " - " in title: title = title.rsplit(" - ", 1)[0]
                intel.append(f"{comp}: {title[:80]}")
        except: pass
    return intel

def main():
    now = datetime.now()
    session = "MORNING" if now.hour < 12 else "EVENING"
    date_str = now.strftime("%a %d %b %Y")
    
    # Fetch data
    es = get_quote("ES=F")
    nq = get_quote("NQ=F")
    vix = get_quote("%5EVIX")
    oil = get_quote("CL=F")
    gold = get_quote("GC=F")
    dxy = get_quote("DX-Y.NYB")
    tnx = get_quote("%5ETNX")
    
    news = get_news()
    competitors = get_competitor_intel()
    
    # VIX label
    vp = vix.get("price", 0)
    vix_label = "Low" if vp < 15 else ("Neutral" if vp < 20 else ("Elevated" if vp < 30 else "High Fear"))
    
    # Build single message
    lines = []
    lines.append(f"🔥 *{session} BRIEFING* — {date_str}")
    lines.append("")
    
    # Markets
    for label, data, prefix, dec in [
        ("ES", es, "", 2), ("NQ", nq, "", 2), ("VIX", vix, "", 2),
        ("Oil", oil, "$", 2), ("Gold", gold, "$", 2), ("DXY", dxy, "", 3), ("10Y", tnx, "", 3)
    ]:
        p = data.get("price")
        prev = data.get("prev")
        if p:
            extra = f" ({vix_label})" if label == "VIX" else ""
            suffix = "%" if label == "10Y" else ""
            lines.append(f"{arrow(p,prev)} *{label}* {prefix}{p:,.{dec}f}{suffix}  {chg(p,prev)}{extra}")
    
    lines.append("")
    
    # Headlines
    if news:
        lines.append("📰 *Headlines*")
        for n in news[:5]:
            lines.append(f"◆ {n}")
        lines.append("")
    
    # Competitors
    if competitors:
        lines.append("🕵️ *Competitors*")
        for c in competitors[:5]:
            lines.append(f"◆ {c}")
    
    msg = "\n".join(lines)
    
    # Telegram limit is 4096 chars — this should fit in one
    if len(msg) > 4000:
        msg = msg[:4000] + "..."
    
    send(msg)
    print(f"✅ {session} briefing sent ({len(msg)} chars)")

if __name__ == "__main__":
    main()