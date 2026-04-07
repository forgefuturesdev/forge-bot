#!/usr/bin/env python3
"""
Forge Marketing Discord Bot v2 — Full-featured server management.
Handles: reaction roles, welcome DMs, auto-mod, logging, tickets,
anti-raid, anti-spam, warnings, and common auto-responses.
"""
import asyncio
import aiohttp
import json
import time
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.stdout.reconfigure(line_buffering=True)

import os

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "1474405047679848643")
BOT_ID = os.environ.get("DISCORD_BOT_ID", "1482017269092716645")
BASE = "https://discord.com/api/v10"
GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"

# ============================================================
# CONFIGURATION
# ============================================================

ROLES = {
    "founder": "1482020646622990356",
    "mod": "1482020649433038981",
    "qualified": "1482020652318720021",
    "challenger": "1482020655338750043",
    "og": "1482020658685804574",
    "member": "1482020669452451850",
    "es_trader": "1482020672396853299",
    "nq_trader": "1482020675186196613",
    "eu_session": "1482020677941727294",
    "us_session": "1482020680731070657",
}

CHANNELS = {
    "welcome": "1482020870204559373",
    "get_roles": "1482020874101199099",
    "announcements": "1482020877146263594",
    "links": "1482020880723873853",
    "verified_staff": "1482020884108804198",
    "general_chat": "1482020891008307343",
    "introductions": "1482100275488489734",
    "wins": "1482020897714999377",
    "payout_proofs": "1482020900852207798",
    "eval_passes": "1482020903947735070",
    "trade_ideas": "1482020906917429311",
    "questions": "1482020910524272691",
    "es_chat": "1482020917738733679",
    "nq_chat": "1482020920645390438",
    "market_watch": "1482020924298362912",
    "trade_of_the_week": "1482020927901536368",
    "resources": "1482020935199490059",
    "challenge_chat": "1482020948902150227",
    "qualified_lounge": "1482020952672964779",
    "rules_explained": "1482020956309295328",
    "promotions": "1482020959627251815",
    "faq": "1482020980564955217",
    "open_ticket": "1482020983362682903",
    "platform_status": "1482020987221446818",
    "bug_reports": "1482020989930967152",
    "mod_logs": "1482021016820777201",
    "mod_chat": "1482021013163348139",
    "rules": "1474405959806881863",
    "daily_highlights": "1482020877146263594",
}

CATEGORIES = {
    "support": "1482020976754448524",
}

STAFF_ROLES = {ROLES["founder"], ROLES["mod"]}

# Anti-spam settings
SPAM_THRESHOLD = 5        # messages in window = spam
SPAM_WINDOW = 5           # seconds
SPAM_MUTE_DURATION = 300  # 5 min mute

# Anti-raid settings
RAID_JOIN_THRESHOLD = 8   # joins in window = raid
RAID_JOIN_WINDOW = 10     # seconds

# Blocked patterns
BLOCKED_PATTERNS = [
    r'discord\.gg/\S+',                    # Discord invite links
    r'discord\.com/invite/\S+',            # Discord invite links alt
    r'free\s*nitro',                        # Nitro scams
    r'@everyone',                           # @everyone abuse
    r'@here',                               # @here abuse
    r'(?:https?://)?(?:bit\.ly|t\.co|tinyurl)\S+',  # URL shorteners (often scams)
]

# Allowed invite - our own server
ALLOWED_INVITES = ['HuC8UsGn']

# Auto-responses for common questions
AUTO_RESPONSES = {
    "how do i get started": "Check out <#{welcome}> for a getting started guide, and grab your roles in <#{get_roles}>! Our challenge plans are at https://forge-futures.com/plans",
    "what are the rules": "Full server rules are in <#{rules}>. Challenge trading rules are in <#{rules_explained}>. You can also check https://forge-futures.com/rules",
    "how do payouts work": "Pass your evaluation → get a qualified account → trade profitably → request a payout. Splits are 70-90% depending on your plan. Full details in <#{rules_explained}>",
    "how do i open a ticket": "Head to <#{open_ticket}> and click the 🎫 reaction to create a support ticket!",
    "when does the market open": "CME Futures: Sunday 6:00 PM – Friday 5:00 PM ET, with a daily halt 5:00-6:00 PM ET.",
    "what can i trade": "Phase 1: E-mini S&P 500 (ES) and Micro E-mini NASDAQ-100 (MNQ). More instruments coming later!",
    "is this a scam": "Forge Futures staff will **NEVER** DM you first. Check <#{verified_staff}> for official team members. If someone DMs you claiming to be staff, report them immediately.",
}

# Format auto-responses with channel IDs
for key in AUTO_RESPONSES:
    AUTO_RESPONSES[key] = AUTO_RESPONSES[key].format(**CHANNELS)

# Word blacklist
BLACKLISTED_WORDS = [
    'nigger', 'nigga', 'faggot', 'retard', 'kys',
]

# ============================================================
# BOT CLASS
# ============================================================

class ForgeBot:
    def __init__(self):
        self.session = None
        self.ws = None
        self.heartbeat_interval = None
        self.sequence = None
        self.running = True
        self.session_id = None
        self.reaction_roles = {}
        self.ticket_message_id = None
        
        # Anti-spam tracking
        self.message_timestamps = defaultdict(list)  # user_id -> [timestamps]
        self.warned_users = defaultdict(int)          # user_id -> warning count
        self.muted_users = {}                          # user_id -> mute_until
        
        # Ticket cooldown (prevent double-creation)
        self.ticket_cooldown = {}                      # user_id -> timestamp
        
        # Anti-raid tracking
        self.join_timestamps = []
        self.raid_mode = False
        
    # ============================================================
    # API HELPERS
    # ============================================================
    
    async def api(self, method, path, data=None):
        headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
        url = f"{BASE}{path}"
        try:
            async with self.session.request(method, url, headers=headers, json=data) as resp:
                if resp.status == 429:
                    retry = (await resp.json()).get('retry_after', 1)
                    await asyncio.sleep(retry + 0.5)
                    return await self.api(method, path, data)
                if resp.status in [200, 201, 204]:
                    return await resp.json() if resp.status != 204 else {}
                else:
                    text = await resp.text()
                    print(f"API {resp.status}: {method} {path} -> {text[:150]}")
                    return None
        except Exception as e:
            print(f"API Error: {e}")
            return None

    async def log(self, title, description, color=0x95A5A6):
        """Send a log entry to #mod-logs."""
        await self.api("POST", f"/channels/{CHANNELS['mod_logs']}/messages", {
            "embeds": [{"title": title, "description": description, "color": color,
                       "timestamp": datetime.now(timezone.utc).isoformat()}]
        })

    async def set_member_channel_visibility(self):
        """Sync target public channels to their live category overwrites and ensure Member can view."""
        member_role = ROLES['member']
        view_channel = 1024
        target_names = {'faq', 'open-ticket', 'platform-status', 'bug-reports', 'daily-highlights'}

        channels = await self.api("GET", f"/guilds/{GUILD_ID}/channels")
        if not channels or isinstance(channels, dict):
            return [('FETCH_CHANNELS', 'guild', False)]

        by_id = {c['id']: c for c in channels}
        targets = []
        for ch in channels:
            if ch.get('name', '').lower() in target_names:
                targets.append(ch)

        updated = []
        for ch in targets:
            channel_id = ch['id']
            channel_name = ch.get('name', channel_id)
            parent_id = ch.get('parent_id')
            overwrites = []

            if parent_id and parent_id in by_id:
                parent = by_id[parent_id]
                parent_overwrites = parent.get('permission_overwrites', []) or []
                # copy parent overwrites first
                overwrites = [dict(ow) for ow in parent_overwrites]
            else:
                overwrites = [dict(ow) for ow in (ch.get('permission_overwrites', []) or [])]

            # ensure Member has view access in resulting overwrite set
            found_member = False
            for ow in overwrites:
                if ow.get('id') == member_role and ow.get('type') == 0:
                    allow = int(ow.get('allow', '0'))
                    deny = int(ow.get('deny', '0'))
                    allow |= view_channel
                    deny &= ~view_channel
                    ow['allow'] = str(allow)
                    ow['deny'] = str(deny)
                    found_member = True
                    break
            if not found_member:
                overwrites.append({'id': member_role, 'type': 0, 'allow': str(view_channel), 'deny': '0'})

            payload = {'permission_overwrites': overwrites}
            result = await self.api("PATCH", f"/channels/{channel_id}", payload)
            updated.append((channel_name, channel_id, bool(result is not None)))

        return updated

    # ============================================================
    # REACTION ROLES
    # ============================================================
    
    async def setup_reaction_roles(self):
        msgs = await self.api("GET", f"/channels/{CHANNELS['get_roles']}/messages?limit=10")
        if not msgs:
            return
        for msg in msgs:
            embeds = msg.get('embeds', [])
            if not embeds:
                continue
            title = embeds[0].get('title', '')
            mid = msg['id']
            
            if 'What Do You Trade' in title:
                self.reaction_roles[mid] = {'🟢': ROLES['es_trader'], '🔵': ROLES['nq_trader']}
            elif 'When Do You Trade' in title:
                self.reaction_roles[mid] = {'🌍': ROLES['eu_session'], '🇺🇸': ROLES['us_session']}
            elif 'Your Forge Futures Status' in title:
                self.reaction_roles[mid] = {'🔥': ROLES['challenger']}
        
        # Also find the ticket message
        ticket_msgs = await self.api("GET", f"/channels/{CHANNELS['open_ticket']}/messages?limit=5")
        if ticket_msgs:
            for msg in ticket_msgs:
                embeds = msg.get('embeds', [])
                if embeds and 'Open a Support Ticket' in embeds[0].get('title', ''):
                    self.ticket_message_id = msg['id']
                    break
        
        print(f"Reaction roles: {len(self.reaction_roles)} messages mapped")
        print(f"Ticket message: {self.ticket_message_id}")

    async def handle_reaction_add(self, data):
        msg_id = data.get('message_id')
        user_id = data.get('user_id')
        emoji = data.get('emoji', {}).get('name', '')
        member = data.get('member', {})
        user = member.get('user', {})
        
        if user.get('bot'):
            return
        
        username = user.get('username', 'Unknown')
        
        # Reaction roles
        if msg_id in self.reaction_roles:
            role_id = self.reaction_roles[msg_id].get(emoji)
            if role_id:
                await self.api("PUT", f"/guilds/{GUILD_ID}/members/{user_id}/roles/{role_id}")
                print(f"  ✅ Role assigned: {username} got {emoji}")
        
        # Ticket creation
        if msg_id == self.ticket_message_id and emoji == '🎫':
            await self.create_ticket(user_id, username)
            # Remove the reaction so they can click again later
            await self.api("DELETE", f"/channels/{CHANNELS['open_ticket']}/messages/{msg_id}/reactions/🎫/{user_id}")

    async def handle_reaction_remove(self, data):
        msg_id = data.get('message_id')
        user_id = data.get('user_id')
        emoji = data.get('emoji', {}).get('name', '')
        
        if msg_id in self.reaction_roles:
            role_id = self.reaction_roles[msg_id].get(emoji)
            if role_id:
                await self.api("DELETE", f"/guilds/{GUILD_ID}/members/{user_id}/roles/{role_id}")
                print(f"  ❌ Role removed: {user_id} lost {emoji}")

    # ============================================================
    # TICKET SYSTEM
    # ============================================================
    
    async def create_ticket(self, user_id, username):
        """Create a private thread for the support ticket."""
        # Cooldown check — prevent double creation
        now = time.time()
        if user_id in self.ticket_cooldown and now - self.ticket_cooldown[user_id] < 30:
            return
        self.ticket_cooldown[user_id] = now
        
        thread = await self.api("POST", f"/channels/{CHANNELS['open_ticket']}/threads", {
            "name": f"ticket-{username}",
            "type": 12,  # GUILD_PRIVATE_THREAD
            "auto_archive_duration": 1440,  # 24 hours
            "invitable": False,
        })
        
        if thread and 'id' in thread:
            thread_id = thread['id']
            # Add the user to the thread
            await self.api("PUT", f"/channels/{thread_id}/thread-members/{user_id}")
            
            # Add all founders and mods to the ticket
            members = await self.api("GET", f"/guilds/{GUILD_ID}/members?limit=50")
            if members:
                for m in members:
                    member_roles = set(m.get('roles', []))
                    if member_roles & STAFF_ROLES and not m.get('user', {}).get('bot'):
                        staff_id = m['user']['id']
                        await self.api("PUT", f"/channels/{thread_id}/thread-members/{staff_id}")
            
            # Send welcome message in the ticket
            await self.api("POST", f"/channels/{thread_id}/messages", {
                "embeds": [{
                    "title": "🎫 Support Ticket",
                    "description": (
                        f"Hey <@{user_id}>, thanks for opening a ticket!\n\n"
                        "**Please describe your issue:**\n"
                        "• What's the problem?\n"
                        "• What account/plan does it relate to?\n"
                        "• Any screenshots?\n\n"
                        "A staff member will respond within 24 hours."
                    ),
                    "color": 0xFE602F,
                }],
                "components": [{
                    "type": 1,
                    "components": [{
                        "type": 2,
                        "style": 4,
                        "label": "Close Ticket",
                        "emoji": {"name": "🔒"},
                        "custom_id": f"close_ticket_{thread_id}"
                    }]
                }]
            })
            
            print(f"  🎫 Ticket created for {username}")
            await self.log("🎫 New Ticket", f"**{username}** opened a support ticket.", 0x3498DB)

    # ============================================================
    # WELCOME / MEMBER EVENTS
    # ============================================================
    
    async def handle_member_join(self, data):
        user = data.get('user', {})
        user_id = user.get('id')
        username = user.get('username', 'Unknown')
        
        if user.get('bot'):
            return
        
        now = time.time()
        print(f"  👋 Join: {username}")
        
        # Anti-raid check
        self.join_timestamps = [t for t in self.join_timestamps if now - t < RAID_JOIN_WINDOW]
        self.join_timestamps.append(now)
        
        if len(self.join_timestamps) >= RAID_JOIN_THRESHOLD and not self.raid_mode:
            self.raid_mode = True
            print("  🚨 RAID DETECTED — activating raid mode")
            await self.log("🚨 RAID DETECTED", 
                f"**{len(self.join_timestamps)} joins in {RAID_JOIN_WINDOW}s!**\nRaid mode activated. New joins will be kicked.",
                0xFF0000)
            # Set verification to highest
            await self.api("PATCH", f"/guilds/{GUILD_ID}", {"verification_level": 4})
            # Auto-disable after 5 minutes
            asyncio.create_task(self.disable_raid_mode())
        
        if self.raid_mode:
            # Kick during raid mode
            await self.api("DELETE", f"/guilds/{GUILD_ID}/members/{user_id}")
            print(f"  🚫 Kicked {username} (raid mode)")
            return
        
        # Assign roles
        await self.api("PUT", f"/guilds/{GUILD_ID}/members/{user_id}/roles/{ROLES['member']}")
        await self.api("PUT", f"/guilds/{GUILD_ID}/members/{user_id}/roles/{ROLES['og']}")
        
        # Welcome DM
        try:
            dm = await self.api("POST", "/users/@me/channels", {"recipient_id": user_id})
            if dm and 'id' in dm:
                await self.api("POST", f"/channels/{dm['id']}/messages", {
                    "embeds": [{
                        "title": "🔥 Welcome to Forge Futures!",
                        "description": (
                            "You just joined the home of elite futures traders.\n\n"
                            "**Get Started:**\n"
                            f"1️⃣ Grab your roles in <#{CHANNELS['get_roles']}>\n"
                            f"2️⃣ Introduce yourself in <#{CHANNELS['introductions']}>\n"
                            f"3️⃣ Jump into <#{CHANNELS['general_chat']}>\n"
                            "4️⃣ Check plans: [forge-futures.com/plans](https://forge-futures.com/plans)\n\n"
                            f"Questions? → <#{CHANNELS['questions']}>\n"
                            f"Support? → <#{CHANNELS['open_ticket']}>\n\n"
                            "⚠️ **Staff will NEVER DM you first.** If anyone claims otherwise — it's a scam."
                        ),
                        "color": 0xFE602F,
                        "footer": {"text": "Where Elite Traders Are Forged"}
                    }]
                })
                print(f"  📨 Welcome DM sent to {username}")
        except Exception as e:
            print(f"  ⚠️ Could not DM {username}: {e}")
        
        # Keep #welcome clean — do not post a new public welcome message for every join.
        
        # Log
        account_age = user.get('created_at', 'Unknown')
        await self.log("👋 Member Joined", 
            f"**{username}** (<@{user_id}>)\nID: `{user_id}`\nRoles: @Member, @OG Member",
            0x2ECC71)

    async def handle_member_leave(self, data):
        user = data.get('user', {})
        username = user.get('username', 'Unknown')
        user_id = user.get('id')
        
        if user.get('bot'):
            return
        
        print(f"  👋 Leave: {username}")
        await self.log("👋 Member Left", f"**{username}** (`{user_id}`) left the server.", 0xE74C3C)

    async def disable_raid_mode(self):
        await asyncio.sleep(300)  # 5 minutes
        self.raid_mode = False
        await self.api("PATCH", f"/guilds/{GUILD_ID}", {"verification_level": 2})
        print("  ✅ Raid mode disabled")
        await self.log("✅ Raid Mode Disabled", "Verification level restored to Medium.", 0x2ECC71)

    # ============================================================
    # INTERACTION HANDLER (buttons)
    # ============================================================
    
    async def handle_interaction(self, data):
        """Handle button clicks and other interactions."""
        interaction_type = data.get('type')
        
        # Type 3 = Message Component (button click)
        if interaction_type == 3:
            custom_id = data.get('data', {}).get('custom_id', '')
            user = data.get('member', {}).get('user', {}) or data.get('user', {})
            username = user.get('username', 'Unknown')
            channel_id = data.get('channel_id')
            interaction_id = data.get('id')
            interaction_token = data.get('token')
            
            # Close ticket button
            if custom_id.startswith('close_ticket_'):
                # Acknowledge the interaction immediately
                await self.api("POST", 
                    f"/interactions/{interaction_id}/{interaction_token}/callback",
                    {"type": 4, "data": {"embeds": [{
                        "title": "🔒 Ticket Closed",
                        "description": f"This ticket was closed by **{username}**.\n\nIf you need further help, open a new ticket in <#{CHANNELS['open_ticket']}>.",
                        "color": 0xE74C3C,
                    }], "flags": 0}}
                )
                
                # Archive and lock the thread
                await self.api("PATCH", f"/channels/{channel_id}", {
                    "archived": True,
                    "locked": True
                })
                
                await self.log("🔒 Ticket Closed", f"Ticket in <#{channel_id}> closed by **{username}**.", 0xE74C3C)
                print(f"  🔒 Ticket closed by {username}")
            
            # Open ticket button (for the main ticket channel)
            elif custom_id == 'open_ticket':
                user_id = user.get('id')
                # Acknowledge
                await self.api("POST",
                    f"/interactions/{interaction_id}/{interaction_token}/callback",
                    {"type": 4, "data": {"content": "🎫 Creating your ticket...", "flags": 64}}
                )
                await self.create_ticket(user_id, username)
            
            # Bug report ticket button
            elif custom_id == 'bug_ticket':
                user_id = user.get('id')
                await self.api("POST",
                    f"/interactions/{interaction_id}/{interaction_token}/callback",
                    {"type": 4, "data": {"content": "🐛 Creating your bug report ticket...", "flags": 64}}
                )
                # Create bug-specific ticket
                now = time.time()
                if user_id in self.ticket_cooldown and now - self.ticket_cooldown[user_id] < 30:
                    return
                self.ticket_cooldown[user_id] = now
                
                thread = await self.api("POST", f"/channels/{CHANNELS['open_ticket']}/threads", {
                    "name": f"bug-{username}",
                    "type": 12,
                    "auto_archive_duration": 1440,
                    "invitable": False,
                })
                if thread and 'id' in thread:
                    thread_id = thread['id']
                    await self.api("PUT", f"/channels/{thread_id}/thread-members/{user_id}")
                    members = await self.api("GET", f"/guilds/{GUILD_ID}/members?limit=50")
                    if members:
                        for m in members:
                            mroles = set(m.get('roles', []))
                            if mroles & STAFF_ROLES and not m.get('user', {}).get('bot'):
                                await self.api("PUT", f"/channels/{thread_id}/thread-members/{m['user']['id']}")
                    await self.api("POST", f"/channels/{thread_id}/messages", {
                        "embeds": [{
                            "title": "🐛 Bug Report",
                            "description": (
                                f"Hey <@{user_id}>, thanks for reporting a bug!\n\n"
                                "**Please include:**\n"
                                "📝 What happened?\n"
                                "🔄 Steps to reproduce\n"
                                "✅ What should have happened?\n"
                                "📸 Screenshots or screen recordings\n"
                                "💻 Device & browser\n\n"
                                "The team will investigate ASAP."
                            ),
                            "color": 0xE74C3C,
                        }],
                        "components": [{"type": 1, "components": [{
                            "type": 2, "style": 4, "label": "Close Ticket",
                            "emoji": {"name": "🔒"}, "custom_id": f"close_ticket_{thread_id}"
                        }]}]
                    })
                    await self.log("🐛 Bug Report", f"Bug ticket opened by **{username}** in <#{thread_id}>", 0xE74C3C)
                    print(f"  🐛 Bug ticket created for {username}")
            
            # Role buttons
            elif custom_id.startswith('role_'):
                role_map = {
                    'role_es_trader': ROLES['es_trader'],
                    'role_nq_trader': ROLES['nq_trader'],
                    'role_eu_session': ROLES['eu_session'],
                    'role_us_session': ROLES['us_session'],
                    'role_challenger': ROLES['challenger'],
                }
                role_id = role_map.get(custom_id)
                if role_id:
                    user_id = user.get('id')
                    member_data = data.get('member', {})
                    current_roles = set(member_data.get('roles', []))
                    
                    role_names = {
                        'role_es_trader': '📈 ES Trader',
                        'role_nq_trader': '📉 NQ Trader',
                        'role_eu_session': '🌍 EU Session',
                        'role_us_session': '🇺🇸 US Session',
                        'role_challenger': '🔥 Active Challenger',
                    }
                    role_label = role_names.get(custom_id, 'Role')
                    
                    if role_id in current_roles:
                        # Remove role (toggle off)
                        await self.api("DELETE", f"/guilds/{GUILD_ID}/members/{user_id}/roles/{role_id}")
                        await self.api("POST",
                            f"/interactions/{interaction_id}/{interaction_token}/callback",
                            {"type": 4, "data": {"content": f"❌ Removed **{role_label}**", "flags": 64}}
                        )
                        print(f"  ❌ Role removed: {username} lost {role_label}")
                    else:
                        # Add role (toggle on)
                        await self.api("PUT", f"/guilds/{GUILD_ID}/members/{user_id}/roles/{role_id}")
                        await self.api("POST",
                            f"/interactions/{interaction_id}/{interaction_token}/callback",
                            {"type": 4, "data": {"content": f"✅ Added **{role_label}**", "flags": 64}}
                        )
                        print(f"  ✅ Role added: {username} got {role_label}")

    # ============================================================
    # AUTO-MODERATION
    # ============================================================
    
    async def handle_message(self, data):
        author = data.get('author', {})
        user_id = author.get('id')
        username = author.get('username', 'Unknown')
        content = data.get('content', '')
        channel_id = data.get('channel_id')
        message_id = data.get('id')
        member = data.get('member', {})
        member_roles = set(member.get('roles', []))
        
        # Ignore bots
        if author.get('bot'):
            return
        
        content_lower = content.lower().strip()
        
        # --- BLACKLISTED WORDS ---
        for word in BLACKLISTED_WORDS:
            if word in content_lower:
                await self.api("DELETE", f"/channels/{channel_id}/messages/{message_id}")
                await self.warn_user(user_id, username, channel_id, "Blacklisted language")
                return
        
        # --- BLOCKED PATTERNS (scam links, invite links, etc) ---
        for pattern in BLOCKED_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                matched_text = match.group(0)
                # Check if it's our own invite
                is_allowed = any(inv in matched_text for inv in ALLOWED_INVITES)
                if not is_allowed:
                    await self.api("DELETE", f"/channels/{channel_id}/messages/{message_id}")
                    await self.api("POST", f"/channels/{channel_id}/messages", {
                        "content": f"<@{user_id}> Links/invites are not allowed without staff permission.",
                    })
                    await self.log("🔗 Link Blocked", 
                        f"**{username}** in <#{channel_id}>:\n`{content[:200]}`", 0xE67E22)
                    return
        
        # --- SPAM DETECTION ---
        now = time.time()
        self.message_timestamps[user_id] = [
            t for t in self.message_timestamps[user_id] if now - t < SPAM_WINDOW
        ]
        self.message_timestamps[user_id].append(now)
        
        if len(self.message_timestamps[user_id]) >= SPAM_THRESHOLD:
            await self.mute_user(user_id, username, channel_id, SPAM_MUTE_DURATION, "Spam detected")
            self.message_timestamps[user_id] = []
            return
        
        # --- CAPS LOCK DETECTION (>80% caps, >20 chars) ---
        if len(content) > 20:
            alpha_chars = [c for c in content if c.isalpha()]
            if alpha_chars and sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars) > 0.8:
                await self.api("POST", f"/channels/{channel_id}/messages", {
                    "content": f"<@{user_id}> Easy on the caps lock 😅"
                })

        # --- TICKET STAFF RELAY (hide admin identity) ---
        if member_roles & STAFF_ROLES and content_lower not in ['!close', '!closeticket', '!done']:
            # Check if this is a ticket thread
            channel_data = await self.api("GET", f"/channels/{channel_id}")
            if channel_data and channel_data.get('parent_id') == CHANNELS['open_ticket']:
                # It's a staff member in a ticket — relay through bot
                await self.api("DELETE", f"/channels/{channel_id}/messages/{message_id}")
                await self.api("POST", f"/channels/{channel_id}/messages", {
                    "embeds": [{
                        "description": content,
                        "color": 0xFE602F,
                        "author": {"name": "Forge Team"},
                    }]
                })
                return

        # --- TICKET CLOSE COMMAND ---
        if content_lower in ['!close', '!closeticket', '!done']:
            # Check if this is a ticket thread
            channel_data = await self.api("GET", f"/channels/{channel_id}")
            if channel_data and channel_data.get('parent_id') == CHANNELS['open_ticket']:
                # It's a ticket thread — close it
                username = author.get('username', 'Unknown')
                await self.api("POST", f"/channels/{channel_id}/messages", {
                    "embeds": [{
                        "title": "🔒 Ticket Closed",
                        "description": f"This ticket was closed by **{username}**.\n\nIf you need further help, open a new ticket in <#{CHANNELS['open_ticket']}>.",
                        "color": 0xE74C3C,
                    }]
                })
                # Archive and lock the thread
                await self.api("PATCH", f"/channels/{channel_id}", {
                    "archived": True,
                    "locked": True
                })
                await self.log("🔒 Ticket Closed", f"Ticket in <#{channel_id}> closed by **{username}**.", 0xE74C3C)
                print(f"  🔒 Ticket closed by {username}")
                return
        
        # --- TICKET STAFF RELAY (hide admin identity) ---
        if member_roles & STAFF_ROLES and content_lower not in ['!close', '!closeticket', '!done']:
            # Check if this is a ticket thread
            channel_data = await self.api("GET", f"/channels/{channel_id}")
            if channel_data and channel_data.get('parent_id') == CHANNELS['open_ticket']:
                # It's a staff member in a ticket — relay through bot
                await self.api("DELETE", f"/channels/{channel_id}/messages/{message_id}")
                await self.api("POST", f"/channels/{channel_id}/messages", {
                    "embeds": [{
                        "description": content,
                        "color": 0xFE602F,
                        "author": {"name": "Forge Team"},
                    }]
                })
                return
        
        # --- TICKET CLOSE COMMAND ---
        if content_lower in ['!close', '!closeticket', '!done']:
            # Check if this is a ticket thread
            channel_data = await self.api("GET", f"/channels/{channel_id}")
            if channel_data and channel_data.get('parent_id') == CHANNELS['open_ticket']:
                # It's a ticket thread — close it
                username = author.get('username', 'Unknown')
                await self.api("POST", f"/channels/{channel_id}/messages", {
                    "embeds": [{
                        "title": "🔒 Ticket Closed",
                        "description": f"This ticket was closed by **{username}**.\n\nIf you need further help, open a new ticket in <#{CHANNELS['open_ticket']}>.",
                        "color": 0xE74C3C,
                    }]
                })
                # Archive and lock the thread
                await self.api("PATCH", f"/channels/{channel_id}", {
                    "archived": True,
                    "locked": True
                })
                await self.log("🔒 Ticket Closed", f"Ticket in <#{channel_id}> closed by **{username}**.", 0xE74C3C)
                print(f"  🔒 Ticket closed by {username}")
                return
        
        # --- ADMIN COMMAND: FIX PUBLIC CHANNEL VISIBILITY ---
        if content_lower == '!fixpublicchannels' and member_roles & STAFF_ROLES:
            results = await self.set_member_channel_visibility()
            ok = [f"{name} ({cid})" for name, cid, success in results if success and name != 'FETCH_CHANNELS']
            fail = [f"{name} ({cid})" for name, cid, success in results if not success and name != 'FETCH_CHANNELS']
            if results and results[0][0] == 'FETCH_CHANNELS':
                msg = f"❌ Could not fetch guild channels: {results[0][2]}"
            else:
                msg = f"✅ Updated member visibility on {len(ok)} target(s)."
                if ok:
                    msg += " Updated: " + ", ".join(ok[:10])
                if fail:
                    msg += " Failed: " + ", ".join(fail[:10])
            await self.api("POST", f"/channels/{channel_id}/messages", {"content": msg[:1900]})
            await self.log("🛠️ Public channel visibility updated", msg[:1900], 0x2ECC71)
            return

        # --- AUTO-RESPONSES ---
        for trigger, response in AUTO_RESPONSES.items():
            if trigger in content_lower:
                await self.api("POST", f"/channels/{channel_id}/messages", {
                    "content": response
                })
                return  # Only one auto-response per message

    # ============================================================
    # MODERATION ACTIONS
    # ============================================================
    
    async def warn_user(self, user_id, username, channel_id, reason):
        self.warned_users[user_id] += 1
        count = self.warned_users[user_id]
        
        if count >= 3:
            # Auto-mute after 3 warnings
            await self.mute_user(user_id, username, channel_id, 3600, f"3 warnings reached ({reason})")
        else:
            await self.api("POST", f"/channels/{channel_id}/messages", {
                "content": f"⚠️ <@{user_id}> Warning {count}/3: {reason}. Next warning may result in a mute."
            })
            await self.log("⚠️ Warning", 
                f"**{username}** — Warning {count}/3\nReason: {reason}\nChannel: <#{channel_id}>",
                0xF1C40F)
    
    async def mute_user(self, user_id, username, channel_id, duration, reason):
        # Use Discord's timeout feature
        timeout_until = datetime.fromtimestamp(
            time.time() + duration, tz=timezone.utc
        ).isoformat()
        
        await self.api("PATCH", f"/guilds/{GUILD_ID}/members/{user_id}", {
            "communication_disabled_until": timeout_until
        })
        
        minutes = duration // 60
        await self.api("POST", f"/channels/{channel_id}/messages", {
            "content": f"🔇 <@{user_id}> has been muted for {minutes} minutes. Reason: {reason}"
        })
        
        await self.log("🔇 User Muted", 
            f"**{username}** (`{user_id}`)\nDuration: {minutes} minutes\nReason: {reason}",
            0xE74C3C)
        
        print(f"  🔇 Muted {username} for {minutes}min: {reason}")

    # ============================================================
    # MESSAGE EDIT/DELETE LOGGING
    # ============================================================
    
    async def handle_message_update(self, data):
        author = data.get('author', {})
        if author.get('bot'):
            return
        
        content = data.get('content', '')
        channel_id = data.get('channel_id')
        username = author.get('username', 'Unknown')
        
        if content:  # Only log if we have the new content
            await self.log("✏️ Message Edited",
                f"**{username}** in <#{channel_id}>:\n{content[:500]}",
                0x3498DB)
    
    async def handle_message_delete(self, data):
        channel_id = data.get('channel_id')
        msg_id = data.get('id')
        # We don't have the content of deleted messages without caching
        # Just log the event
        await self.log("🗑️ Message Deleted",
            f"Message `{msg_id}` deleted in <#{channel_id}>",
            0x95A5A6)

    # ============================================================
    # BAN / UNBAN LOGGING
    # ============================================================
    
    async def handle_ban(self, data):
        user = data.get('user', {})
        username = user.get('username', 'Unknown')
        user_id = user.get('id')
        await self.log("🔨 User Banned",
            f"**{username}** (`{user_id}`) was banned.",
            0xFF0000)
    
    async def handle_unban(self, data):
        user = data.get('user', {})
        username = user.get('username', 'Unknown')
        user_id = user.get('id')
        await self.log("🔓 User Unbanned",
            f"**{username}** (`{user_id}`) was unbanned.",
            0x2ECC71)

    # ============================================================
    # GATEWAY CONNECTION
    # ============================================================
    
    async def heartbeat(self):
        while self.running:
            await asyncio.sleep(self.heartbeat_interval / 1000)
            if self.ws and not self.ws.closed:
                await self.ws.send_json({"op": 1, "d": self.sequence})

    async def connect(self):
        self.session = aiohttp.ClientSession()
        
        while self.running:
            try:
                async with self.session.ws_connect(GATEWAY_URL) as ws:
                    self.ws = ws
                    
                    msg = await ws.receive_json()
                    self.heartbeat_interval = msg['d']['heartbeat_interval']
                    
                    heartbeat_task = asyncio.create_task(self.heartbeat())
                    
                    # Identify with all needed intents
                    # GUILDS(1) | GUILD_MEMBERS(2) | GUILD_MODERATION(4) | 
                    # GUILD_MESSAGE_REACTIONS(1024) | GUILD_MESSAGES(512) |
                    # MESSAGE_CONTENT(32768) | DIRECT_MESSAGES(4096)
                    intents = 1 | 2 | 4 | 512 | 1024 | 4096 | 32768
                    
                    await ws.send_json({
                        "op": 2,
                        "d": {
                            "token": TOKEN,
                            "intents": intents,
                            "properties": {"os": "linux", "browser": "forge-marketing", "device": "forge-marketing"}
                        }
                    })
                    
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            self.sequence = data.get('s')
                            
                            if data['op'] == 0:
                                event = data['t']
                                d = data['d']
                                
                                if event == 'READY':
                                    self.session_id = d['session_id']
                                    print(f"🔥 Forge Marketing Bot v2 ONLINE")
                                    print(f"  Session: {self.session_id}")
                                    print(f"  Guilds: {len(d['guilds'])}")
                                    await self.setup_reaction_roles()
                                    await self.log("🤖 Bot Online", 
                                        "Forge Marketing bot connected and monitoring.", 0x2ECC71)
                                    print("  ✅ Ready!")
                                    
                                elif event == 'MESSAGE_REACTION_ADD':
                                    await self.handle_reaction_add(d)
                                elif event == 'MESSAGE_REACTION_REMOVE':
                                    await self.handle_reaction_remove(d)
                                elif event == 'GUILD_MEMBER_ADD':
                                    await self.handle_member_join(d)
                                elif event == 'GUILD_MEMBER_REMOVE':
                                    await self.handle_member_leave(d)
                                elif event == 'INTERACTION_CREATE':
                                    await self.handle_interaction(d)
                                elif event == 'MESSAGE_CREATE':
                                    await self.handle_message(d)
                                elif event == 'MESSAGE_UPDATE':
                                    await self.handle_message_update(d)
                                elif event == 'MESSAGE_DELETE':
                                    await self.handle_message_delete(d)
                                elif event == 'GUILD_BAN_ADD':
                                    await self.handle_ban(d)
                                elif event == 'GUILD_BAN_REMOVE':
                                    await self.handle_unban(d)
                                    
                            elif data['op'] == 7:
                                print("  🔄 Reconnect requested")
                                break
                            elif data['op'] == 9:
                                print("  ❌ Invalid session")
                                await asyncio.sleep(5)
                                break
                    
                    heartbeat_task.cancel()
                    
            except Exception as e:
                print(f"  ❌ Connection error: {e}")
                await asyncio.sleep(5)
        
        await self.session.close()

    def stop(self):
        self.running = False

async def main():
    bot = ForgeBot()
    await bot.connect()

if __name__ == "__main__":
    asyncio.run(main())
