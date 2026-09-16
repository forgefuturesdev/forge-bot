"""Versioned Discord refresh. `plan` is read-only; `apply` requires live preflight.

No member messages or customer certificates are deleted. Existing lounge history
is archived privately, not destroyed. Staff identities are resolved by username
AND checked against the existing Founder role before publication.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from zipfile import ZipFile

import channel_refresh as api

VERSION = "2026.09.16"
MARKER = f"Forge community | {VERSION}"
ASSETS = Path(__file__).parent / "assets" / "community"
ASSET_ARCHIVE = Path(__file__).parent / 'community-assets.zip'


def asset_bytes(name):
    if Path(name).name != name:
        raise api.DiscordError('Invalid asset name')
    if (ASSETS / name).is_file():
        return (ASSETS / name).read_bytes()
    with ZipFile(ASSET_ARCHIVE) as archive:
        return archive.read(name)
FOUNDER = "1482020646622990356"
MOD = "1482020649433038981"
MEMBER = "1482020669452451850"
CHANNEL_IDS = {
    "rules": "1474405959806881863",
    "get-roles": "1482020874101199099",
    "verified-staff": "1482020884108804198",
    "payout-proofs": "1482020900852207798",
    "eval-passes": "1482020903947735070",
    "trade-ideas": "1482020906917429311",
    "rules-explained": "1482020956309295328",
    "faq": "1482020980564955217",
    "open-ticket": "1482020983362682903",
    "platform-status": "1482020987221446818",
    "bug-reports": "1482020989930967152",
    "daily-highlights": "1482427993140760636",
}
LOUNGES = {"challenge-chat": "1482020948902150227", "qualified-lounge": "1482020952672964779"}
MOD_LOGS = "1482021016820777201"
COMMUNITY = "1482020887644602369"
FORGE_CATEGORY = "1482020945408561314"
PRIMARY_MESSAGES = {
    'rules': '1482037707348770982', 'get-roles': '1482057046311440425',
    'verified-staff': '1482046465529610353', 'payout-proofs': '1483026352277028887',
    'eval-passes': '1482057727592239115', 'trade-ideas': '1482056771089469602',
    'open-ticket': '1482048020924334264', 'bug-reports': '1482057528421384246',
    'rules-explained': '1538620866697494691',
}
SUPERSEDED_MESSAGES = {
    'get-roles': ['1482057057547976826', '1482057054016372917', '1482057050304413766'],
    'trade-ideas': ['1482056772989751347'], 'bug-reports': ['1482057530418008225'],
    'rules-explained': ['1538620868437999748'],
}
VIEW = 1 << 10
SEND = 1 << 11
READ = 1 << 16
REACT = 1 << 6
ATTACH = 1 << 15
EMBED = 1 << 14
PUBLIC_THREAD = 1 << 35
PRIVATE_THREAD = 1 << 36
THREAD_REPLY = 1 << 38
WRITE = SEND | PUBLIC_THREAD | PRIVATE_THREAD | THREAD_REPLY
LOCKED = {"rules", "get-roles", "verified-staff", "rules-explained", "daily-highlights", "faq", "open-ticket", "platform-status", "bug-reports"}


def call(method, path, payload=None):
    for attempt in range(5):
        response = api.request(method, path, json_body=payload, reason=MARKER)
        if response.status_code != 429:
            return api.expect(response, (200, 201, 204), path)
        time.sleep(min(float(response.json().get('retry_after', 1)), 60) + .2)
    raise api.DiscordError(f'Rate limit persists: {method} {path}')


def all_members():
    result, after = [], ""
    while True:
        page = call("GET", f"/guilds/{api.GUILD_ID}/members?limit=1000" + (f"&after={after}" if after else ""))
        result.extend(page)
        if len(page) < 1000:
            return result
        after = page[-1]["user"]["id"]


def resolve_staff(members):
    found = {}
    for username in ("forgefutures", "jackforgefutures"):
        matches = [m for m in members if m.get("user", {}).get("username") == username and not m["user"].get("bot")]
        if len(matches) != 1 or FOUNDER not in matches[0].get("roles", []):
            raise api.DiscordError(f"Cannot verify current Founder @{username}; refusing staff-directory update")
        found[username] = str(matches[0]["user"]["id"])
    return found


def locked_overwrites(channel, roles, *, ticket=False):
    """Remove *all* non-staff send overrides; one role allow can beat @everyone deny.

    Private ticket membership still controls access; members may reply only to
    private threads they have been invited to, never create their own threads.
    No existing visibility is widened by locking an existing channel.
    """
    trusted_roles = {FOUNDER, MOD} | {str(r['id']) for r in roles if r.get('tags', {}).get('bot_id') == api.BOT_ID}
    overwrites = [dict(o) for o in channel.get('permission_overwrites', [])]
    if not any(str(o['id']) == api.GUILD_ID and int(o['type']) == 0 for o in overwrites):
        overwrites.append({'id': api.GUILD_ID, 'type': 0, 'allow': '0', 'deny': '0'})
    if ticket and not any(str(o['id']) == MEMBER and int(o['type']) == 0 for o in overwrites):
        overwrites.append({'id': MEMBER, 'type': 0, 'allow': '0', 'deny': '0'})
    for o in overwrites:
        trusted = (int(o['type']) == 0 and str(o['id']) in trusted_roles) or (int(o['type']) == 1 and str(o['id']) == api.BOT_ID)
        if trusted:
            continue
        allow, deny = int(o.get('allow', 0)) & ~WRITE, int(o.get('deny', 0)) | WRITE
        if ticket and int(o['type']) == 0 and str(o['id']) == MEMBER:
            allow |= THREAD_REPLY
            deny &= ~THREAD_REPLY
        o.update(allow=str(allow), deny=str(deny))
    # A global bot/staff Send Messages permission is overridden by the channel's
    # @everyone deny, so preserve an explicit staff/bot publishing route.
    for principal, kind in [(FOUNDER, 0), (MOD, 0), (api.BOT_ID, 1)]:
        existing = next((o for o in overwrites if str(o['id']) == principal and int(o['type']) == kind), None)
        if existing is None:
            existing = {'id': principal, 'type': kind, 'allow': '0', 'deny': '0'}
            overwrites.append(existing)
        allowed = WRITE | (VIEW | READ | EMBED | ATTACH if kind == 1 else 0)
        existing['allow'] = str(int(existing['allow']) | allowed)
        existing['deny'] = str(int(existing['deny']) & ~allowed)
    return overwrites


def embed(title, description, fields=()):
    return {
        'title': title, 'description': description, 'color': 0xFF6B00,
        'author': {'name': 'FORGE FUTURES', 'icon_url': api.FORGE_ICON_URL},
        'fields': [{'name': name, 'value': value, 'inline': False} for name, value in fields],
        'footer': {'text': MARKER},
    }


def button(label, custom_id, style=2):
    return {'type': 2, 'style': style, 'label': label, 'custom_id': custom_id}


def panel(key, title, description, fields=(), buttons=(), assets=()):
    value = {'key': key, 'embeds': [embed(title, description, fields)], 'assets': list(assets)}
    value['components'] = [{'type': 1, 'components': list(buttons)[n:n+5]} for n in range(0, len(buttons), 5)]
    return value


def panels(staff, public_bug_id=None):
    ticket = f"<#{CHANNEL_IDS['open-ticket']}>"
    bugs = f"<#{public_bug_id}>" if public_bug_id else 'the Community bug-discussion channel'
    return {
        'get-roles': [panel('roles', 'MAKE THE FORGE YOURS',
            'Choose the markets and sessions you follow. Click a button again to remove that role.',
            [('Markets', 'ES / MES or NQ / MNQ — choose one or both.'),
             ('Sessions', 'Europe / London and US / New York. These are preferences, not trading permissions.'),
             ('In The Forge', 'The community role is self-selectable. Founder, moderator and qualified roles are never self-assigned.')],
            [button('ES / MES', 'role_es_trader'), button('NQ / MNQ', 'role_nq_trader'),
             button('London / Europe', 'role_eu_session'), button('New York / US', 'role_us_session'), button('In The Forge', 'role_challenger')])],
        'rules': [panel('rules', 'THE FORGE CODE', 'A trading community built on respect, useful discussion and clear boundaries.',
            [('01 · Respect the room', 'No harassment, hate, threats, doxxing or targeted abuse. Challenge an idea, not the person.'),
             ('02 · Keep it useful', 'Use the right channel. No spam, unsolicited adverts, referral farming or competing-server promotion.'),
             ('03 · Protect your account', f'Staff will never ask for passwords, recovery codes, MFA codes or wallet seed phrases. Verify usernames in <#{CHANNEL_IDS["verified-staff"]}> and use {ticket} for account support.'),
             ('04 · Share responsibly', 'Trade ideas are discussion, not signals or guarantees. Do not fabricate payouts or passes. Clearly label examples and redact private account details.'),
             ('05 · Trading rules', 'Discord rules do not replace account terms. Check [current plan rules](https://forge-futures.com/rules) and your dashboard. All Forge trading accounts are simulated.'),
             ('06 · Moderation', 'Staff may remove unsafe content and restrict accounts that break these rules. Raise a moderation concern privately through a ticket.')])],
        'verified-staff': [panel('staff', 'VERIFY THE PERSON. NOT THE DISPLAY NAME.', 'These are the current Forge Futures founders. Click the mentions to open the exact accounts.',
            [('Joe | Forge Futures', f'<@{staff["forgefutures"]}>\nUsername: **`forgefutures`**'),
             ('Jack | Forge Futures', f'<@{staff["jackforgefutures"]}>\nUsername: **`jackforgefutures`**'),
             ('Stay safe', f'Display names and avatars can be copied. Start support in {ticket}. Never send passwords, MFA codes, payment-card details or wallet keys in Discord. We will not ask you to pay a staff member personally.')])],
        'open-ticket': [panel('support', 'Open a Support Ticket', 'Account question, billing issue or platform problem? Open a private ticket with the Forge team.',
            [('How it works', '1. Click Open ticket.\n2. Follow the private thread link shown only to you.\n3. Describe the issue and reply in that thread.'),
             ('Help us find it', 'Include the affected account/order reference, approximate time and time zone, what you expected and what actually happened. Redact screenshots.'),
             ('Keep secrets out', 'Never post passwords, MFA/recovery codes, full payment-card details, private keys or identity documents. This public panel is read-only; replies happen inside your private ticket.')],
            [button('Open ticket', 'open_ticket', 1)])],
        'bug-reports': [panel('bugs', 'REPORT A PLATFORM BUG', 'Give us something we can reproduce. Account-specific details belong in a private bug ticket.',
            [('Include', 'Page or feature · device/browser · steps to reproduce · expected result · actual result · approximate time and time zone.'),
             ('Screenshots', 'Hide names, balances, account identifiers and other private details before sharing publicly.'),
             ('Community reports', f'For non-sensitive issues and discussion, use {bugs}. For an order, account or billing problem, use the private button below.')],
            [button('Private bug report', 'bug_ticket', 1)])],
        'payout-proofs': [panel('payouts', 'PAYOUTS · VERIFIED, NOT JUST POSTED', 'Share your Forge-issued payout certificate and celebrate the milestone.',
            [('Check the record', 'A screenshot alone is not verification. Use the certificate’s genuine verification link and check its current status. Do not share bank details or private account information.'),
             ('Examples below', '**DESIGN EXAMPLES ONLY — fictional names, amounts, dates and certificate references. These are not customer payouts, proof of payment or promised results.**')]),
            panel('payout-example', 'EXAMPLE · PAYOUT CERTIFICATE', '**ILLUSTRATIVE TEMPLATE — NOT AN ACTUAL PAYOUT.**\nFictional recipient and reference. The image shows the certificate design only; its sample QR/reference is not evidence of a verified payment.', assets=['EXAMPLE-payout-certificate.png']),
            panel('lifetime-example', 'EXAMPLE · LIFETIME PAYOUT CERTIFICATE', '**ILLUSTRATIVE TEMPLATE — NOT ACTUAL EARNINGS.**\nFictional cumulative amount and recipient. Not a performance claim or a promise of future payouts.', assets=['EXAMPLE-lifetime-certificate.png'])],
        'eval-passes': [panel('passes', 'EVALUATION PASSED. NEXT CHAPTER.', 'Share the milestone, then keep the same discipline into your qualified account.',
            [('Share your achievement', 'Use your Forge-issued certificate or a redacted dashboard screenshot. Include the tier and size if you wish; keep private identifiers hidden.'),
             ('What happens next', 'Follow the qualification steps shown in your dashboard, including any required checks, agreement and activation fee. Passing does not itself guarantee a payout.')]),
            panel('pass-example', 'EXAMPLE · QUALIFIED TRADER CERTIFICATE', '**ILLUSTRATIVE TEMPLATE — NOT A REAL TRADER RESULT.**\nFictional recipient and certificate reference. This showcases the design after qualification; all Forge accounts remain simulated.', assets=['EXAMPLE-qualified-certificate.png'])],
        'trade-ideas': [panel('ideas', 'TRADE IDEAS · SHOW YOUR THINKING', 'A useful idea explains the setup and what would invalidate it. This is a discussion room, not a signal service.',
            [('Post format', '**Contract / timeframe:**\n**Session / time zone:**\n**Context and thesis:**\n**Entry condition:**\n**Invalidation / risk:**\n**Scheduled news:**\n**Chart:**'),
             ('Keep it honest', 'Label live ideas versus hindsight reviews. Do not promise returns, pressure others to copy trades or post account credentials. Update your original idea when the thesis changes.'),
             ('Illustrative example', '**MNQ · 5 minute · London session**\nThesis: watch the opening range.\nCondition: wait for a break and retest.\nInvalidation: failure back into the range.\nRisk: decide the stop and size before entry.\nNo live price levels or trade recommendation are implied.')])],
        'rules-explained': [panel('plans', 'CHOOSE YOUR PLAN. KNOW YOUR RULES.', 'Zero, Standard and Advanced at a glance. Use the attached Forge plan graphics, then read the current [Plans](https://forge-futures.com/plans) and [Rules](https://forge-futures.com/rules).',
            [('Evaluation ≠ Qualified', 'The evaluation target and consistency requirements differ from qualified-account payout requirements. Use the correct stage when comparing.'),
             ('Before purchase', 'The artwork shows monthly USD fees before discount. Confirm the current FORGE offer and exact price at checkout. Reset/activation fees are separate. All accounts are simulated; eligibility and terms apply.')],
            assets=['zero.png', 'standard.png', 'advanced.png', '50k-comparison.png'])],
    }


def history(channel_id):
    # Bounded newest-first inventory. Existing current posts are also discoverable
    # via pins once pinned, so normal community traffic cannot create duplicates.
    messages = call('GET', f'/channels/{channel_id}/messages?limit=100')
    pins = call('GET', f'/channels/{channel_id}/messages/pins')
    return list({str(m['id']): m for m in messages + [p['message'] for p in pins.get('items', [])]}.values())


def backup(channel, messages):
    # Keep rollback data inside the existing staff-only mod log, never public.
    data = json.dumps({'version': VERSION, 'channel': channel, 'messages': messages}, ensure_ascii=False).encode()
    response = api.request('POST', f'/channels/{MOD_LOGS}/messages', files={
        'payload_json': (None, json.dumps({'content': f'{MARKER} · rollback snapshot for <#{channel["id"]}>', 'allowed_mentions': {'parse': []}}), 'application/json'),
        'files[0]': (f'forge-refresh-{channel["id"]}.json', data, 'application/json'),
    })
    api.expect(response, (200, 201), 'Private rollback backup')


def publish_panel(channel_id, spec, messages, replace_id=None):
    marker = f'{MARKER} | {spec["key"]}'
    existing = next((m for m in messages if str(m.get('author', {}).get('id')) == api.BOT_ID and any(e.get('footer', {}).get('text') == marker for e in m.get('embeds', []))), None)
    if existing:
        return existing['id']
    if replace_id:
        original = next((m for m in messages if str(m['id']) == replace_id), None)
        if not original or str(original.get('author', {}).get('id')) != api.BOT_ID:
            raise api.DiscordError(f'Replacement message identity mismatch: {replace_id}')
    path = f'/channels/{channel_id}/messages' + (f'/{replace_id}' if replace_id else '')
    method = 'PATCH' if replace_id else 'POST'
    payload = {'content': '', 'embeds': spec['embeds'], 'components': spec['components'], 'attachments': [], 'allowed_mentions': {'parse': []}}
    payload['embeds'][0]['footer']['text'] = marker
    api.validate_embeds(payload['embeds'])
    handles = []
    try:
        if spec['assets']:
            payload['attachments'] = [{'id': n, 'filename': name} for n, name in enumerate(spec['assets'])]
            files = {'payload_json': (None, json.dumps(payload), 'application/json')}
            for n, name in enumerate(spec['assets']):
                files[f'files[{n}]'] = (name, asset_bytes(name), 'image/png')
            result = api.expect(api.request(method, path, files=files), (200, 201), 'Community panel')
        else:
            result = call(method, path, payload)
        call('PUT', f'/channels/{channel_id}/messages/pins/{result["id"]}')
        return result['id']
    finally:
        for handle in handles:
            handle.close()


def preflight():
    if not api.TOKEN:
        raise api.DiscordError('DISCORD_BOT_TOKEN is required')
    if api.GUILD_ID != '1474405047679848643':
        raise api.DiscordError('Wrong guild; refusing community refresh')
    channels = {str(c['id']): c for c in api.get_guild_channels()}
    for name, channel_id in CHANNEL_IDS.items():
        c = channels.get(channel_id)
        if not c or c.get('type') not in (0, 5) or api.channel_key(c['name']) != name:
            raise api.DiscordError(f'Expected #{name} at {channel_id}; inspect before continuing')
    roles = call('GET', f'/guilds/{api.GUILD_ID}/roles')
    staff = resolve_staff(all_members())
    for specs in panels(staff).values():
        for spec in specs:
            api.validate_embeds(spec['embeds'])
            for asset in spec['assets']:
                if not asset_bytes(asset):
                    raise api.DiscordError(f'Missing asset {asset}')
    # Never publish backups into a missing/public log without inspection.
    log = channels.get(MOD_LOGS)
    everyone = next((o for o in (log or {}).get('permission_overwrites', []) if str(o['id']) == api.GUILD_ID), {})
    if not log or not int(everyone.get('deny', 0)) & VIEW:
        raise api.DiscordError('Private mod-log visibility requires review before backup')
    return channels, roles, staff


def plan():
    channels, roles, staff = preflight()
    for name, specs in panels(staff).items():
        messages = history(CHANNEL_IDS[name])
        print(f'PLAN: #{name}: {len(specs)} panels; {len(messages)} recent/pinned messages preserved')
    for name in LOCKED:
        channel = channels[CHANNEL_IDS[name]]
        print(f'PLAN: #{name}: read-only parent; private replies={name == "open-ticket"}')
        locked_overwrites(channel, roles, ticket=name == 'open-ticket')
    for name, channel_id in LOUNGES.items():
        c = channels.get(channel_id)
        if c:
            print(f'PLAN: #{c["name"]}: archive privately, preserve history (deletion awaits inspection)')
    print('PLAN: create member-writable bug-discussion at bottom of Community; no production mutations')


def bug_channel(channels):
    matches = [c for c in channels.values() if api.channel_key(c['name']) == 'bug-discussion']
    if len(matches) > 1 or (matches and matches[0].get('parent_id') != COMMUNITY):
        raise api.DiscordError('Ambiguous bug-discussion channel')
    return matches[0] if matches else None


def apply():
    channels, roles, staff = preflight()
    community = channels.get(COMMUNITY)
    if not community or community['type'] != 4 or 'COMMUNITY' not in community['name'].upper():
        raise api.DiscordError('Community category identity mismatch')
    bug = bug_channel(channels)
    if not bug:
        overwrites = [dict(o) for o in community.get('permission_overwrites', [])]
        member = next((o for o in overwrites if str(o['id']) == MEMBER and int(o['type']) == 0), None)
        if member is None:
            member = {'id': MEMBER, 'type': 0, 'allow': '0', 'deny': '0'}
            overwrites.append(member)
        allowed = VIEW | READ | SEND | ATTACH | EMBED
        member.update(allow=str(int(member['allow']) | allowed), deny=str(int(member['deny']) & ~allowed))
        bug = call('POST', f'/guilds/{api.GUILD_ID}/channels', {
            'name': 'bug-discussion', 'type': 0, 'parent_id': COMMUNITY,
            'topic': 'Public, non-sensitive platform bug reports. Use Support for private account/order details.',
            'permission_overwrites': overwrites, 'rate_limit_per_user': 10,
        })
    bottom = max((c.get('position', 0) for c in channels.values() if c.get('parent_id') == COMMUNITY), default=0) + 1
    call('PATCH', f'/guilds/{api.GUILD_ID}/channels', [{'id': bug['id'], 'position': bottom}])
    for name, specs in panels(staff, bug['id']).items():
        channel = channels[CHANNEL_IDS[name]]
        messages = history(channel['id'])
        # Back up once per panel version, before changing any source message.
        if not any(any(e.get('footer', {}).get('text', '').startswith(MARKER) for e in m.get('embeds', [])) for m in messages):
            backup(channel, messages)
        primary = None
        for index, spec in enumerate(specs):
            message_id = publish_panel(channel['id'], spec, messages, PRIMARY_MESSAGES.get(name) if index == 0 else None)
            primary = primary or message_id
        for old_id in SUPERSEDED_MESSAGES.get(name, []):
            old = next((m for m in messages if str(m['id']) == old_id), None)
            if not old or str(old.get('author', {}).get('id')) != api.BOT_ID:
                raise api.DiscordError(f'Superseded message identity mismatch: {old_id}')
            call('PATCH', f'/channels/{channel["id"]}/messages/{old_id}', {
                'content': f'Updated guide: https://discord.com/channels/{api.GUILD_ID}/{channel["id"]}/{primary}',
                'embeds': [], 'attachments': [], 'components': [], 'allowed_mentions': {'parse': []},
            })
        print(f'UPDATED #{name}: {len(specs)} panels; member posts preserved', flush=True)
    for channel in channels.values():
        name = api.channel_key(channel['name'])
        if name in LOCKED or (channel.get('parent_id') == FORGE_CATEGORY and channel['id'] not in LOUNGES.values() and channel['type'] in (0, 5)):
            overwrite = locked_overwrites(channel, roles, ticket=name == 'open-ticket')
            if overwrite != channel.get('permission_overwrites', []):
                backup(channel, [])
                call('PATCH', f'/channels/{channel["id"]}', {'permission_overwrites': overwrite})
            print(f'LOCKED #{name}', flush=True)
    verify()


def verify():
    channels, roles, staff = preflight()
    bug = bug_channel(channels)
    if not bug:
        raise api.DiscordError('Public bug-discussion is missing')
    for name, specs in panels(staff, bug['id']).items():
        messages = history(CHANNEL_IDS[name])
        for spec in specs:
            marker = f'{MARKER} | {spec["key"]}'
            matches = [m for m in messages if str(m.get('author', {}).get('id')) == api.BOT_ID and any(e.get('footer', {}).get('text') == marker for e in m.get('embeds', []))]
            if len(matches) != 1:
                raise api.DiscordError(f'Expected exactly one {name}/{spec["key"]} panel')
            if len(matches[0].get('attachments', [])) != len(spec['assets']):
                raise api.DiscordError(f'Attachment mismatch in {name}')
    for channel in channels.values():
        name = api.channel_key(channel['name'])
        if name in LOCKED or (channel.get('parent_id') == FORGE_CATEGORY and channel['id'] not in LOUNGES.values() and channel['type'] in (0, 5)):
            expected = locked_overwrites(channel, roles, ticket=name == 'open-ticket')
            if expected != channel.get('permission_overwrites', []):
                raise api.DiscordError(f'Unsafe member-write overwrite in #{name}')
    member = next((o for o in bug.get('permission_overwrites', []) if str(o['id']) == MEMBER), {})
    if int(member.get('deny', 0)) & SEND or not int(member.get('allow', 0)) & SEND:
        raise api.DiscordError('Public bug-discussion is not member-writable')
    print('VERIFIED community panels, attachments, exact staff identities and member-write locks', flush=True)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'plan'
    if mode not in {'plan', 'apply', 'verify'}:
        raise SystemExit('Usage: community_refresh.py [plan|apply|verify]')
    {'plan': plan, 'apply': apply, 'verify': verify}[mode]()
