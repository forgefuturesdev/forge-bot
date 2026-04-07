#!/usr/bin/env python3
"""
Forge Futures Discord Daily Report
Generates a summary of server activity and sends it to Joe via Telegram.
"""
import requests
import json
from datetime import datetime, timezone, timedelta
import os

DISCORD_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "1474405047679848643")
JOE_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "875670264")

HEADERS = {"Authorization": f"Bot {DISCORD_TOKEN}", "Content-Type": "application/json"}
BASE = "https://discord.com/api/v10"

def api(path):
    r = requests.get(f"{BASE}{path}", headers=HEADERS)
    return r.json() if r.status_code == 200 else None

def get_member_count():
    members = api(f"/guilds/{GUILD_ID}?with_counts=true")
    if members:
        return members.get('approximate_member_count', 0), members.get('approximate_presence_count', 0)
    return 0, 0

def get_recent_messages(channel_id, hours=24):
    """Count messages in last N hours."""
    msgs = api(f"/channels/{channel_id}/messages?limit=100")
    if not msgs or isinstance(msgs, dict):
        return 0
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    count = 0
    for m in msgs:
        try:
            ts = datetime.fromisoformat(m['timestamp'].replace('+00:00', '+00:00'))
            if ts > cutoff:
                count += 1
        except:
            pass
    return count

def get_active_threads():
    data = api(f"/guilds/{GUILD_ID}/threads/active")
    if data:
        return data.get('threads', [])
    return []

def get_new_members(hours=24):
    members = api(f"/guilds/{GUILD_ID}/members?limit=100")
    if not members:
        return []
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    new = []
    for m in members:
        try:
            joined = datetime.fromisoformat(m['joined_at'])
            if joined > cutoff:
                new.append(m['user']['username'])
        except:
            pass
    return new

def generate_report(period="daily"):
    hours = 12 if period == "morning" else 24
    
    total_members, online_now = get_member_count()
    new_members = get_new_members(hours)
    active_threads = get_active_threads()
    
    # Key channels to check
    channels = {
        "general-chat": "1482020891008307343",
        "questions": "1482020910524272691",
        "introductions": "1482100275488489734",
        "trade-ideas": "1482020906917429311",
        "challenge-chat": "1482020948902150227",
        "wins": "1482020897714999377",
        "bug-reports": "1482020989930967152",
    }
    
    channel_activity = {}
    total_messages = 0
    for name, cid in channels.items():
        count = get_recent_messages(cid, hours)
        if count > 0:
            channel_activity[name] = count
        total_messages += count
    
    # Open tickets
    open_tickets = [t for t in active_threads if t.get('parent_id') == '1482020983362682903']
    
    # Build report
    now = datetime.now(timezone.utc)
    time_label = "Morning" if period == "morning" else "Evening"
    
    report = f"🔥 **Forge Futures Discord — {time_label} Report**\n"
    report += f"📅 {now.strftime('%A %d %B %Y')}\n\n"
    
    report += f"👥 **Members:** {total_members} total"
    if online_now:
        report += f" ({online_now} online)"
    report += "\n"
    
    if new_members:
        report += f"🆕 **New joins ({hours}h):** {len(new_members)} — {', '.join(new_members[:10])}\n"
    else:
        report += f"🆕 **New joins ({hours}h):** None\n"
    
    report += f"💬 **Messages ({hours}h):** {total_messages}\n"
    
    if channel_activity:
        report += "\n**Active channels:**\n"
        for ch, count in sorted(channel_activity.items(), key=lambda x: -x[1]):
            report += f"  • #{ch}: {count} messages\n"
    
    if open_tickets:
        report += f"\n🎫 **Open tickets:** {len(open_tickets)}\n"
        for t in open_tickets:
            report += f"  • {t['name']}\n"
    else:
        report += f"\n🎫 **Open tickets:** None\n"
    
    # Action items
    actions = []
    if open_tickets:
        actions.append(f"⚠️ {len(open_tickets)} open ticket(s) need attention")
    if total_messages == 0:
        actions.append("💤 Server is quiet — consider posting something to spark conversation")
    if new_members:
        actions.append(f"👋 {len(new_members)} new member(s) — check if they introduced themselves")
    
    if actions:
        report += "\n**Action items:**\n"
        for a in actions:
            report += f"  {a}\n"
    else:
        report += "\n✅ Nothing needs attention right now.\n"
    
    return report

def send_to_joe(message):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": JOE_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    )

if __name__ == "__main__":
    import sys
    period = sys.argv[1] if len(sys.argv) > 1 else "daily"
    report = generate_report(period)
    print(report)
    send_to_joe(report)
    print("\n✅ Report sent to Joe via Telegram")