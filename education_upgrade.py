#!/usr/bin/env python3
"""Build the two Forge education forums and retire the replaced text channels."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import channel_refresh as public_info


RELEASE_VERSION = "2026.08.16.2"
RELEASE_MARKER = f"Forge education upgrade | v{RELEASE_VERSION}"
TRADING_FORUM_NAME = "trading-education"
TRADING_FORUM_TOPIC = (
    f"{RELEASE_MARKER} | Practical trading education for simulated futures traders."
)
TRADING_ASSET_DIR = Path(__file__).resolve().parent / "assets" / "trading-education"
ARCHIVE_STATE_MARKER = f"{RELEASE_MARKER} | rollback state"
ARCHIVE_TARGETS = {
    "resources": "archive-resources",
    "trading-psychology": "archive-trading-psychology",
    "risk-management": "archive-risk-management",
}


def trading_embed(
    title: str,
    description: str,
    *,
    image_name: str,
    fields: list[dict],
) -> dict:
    return public_info.public_embed(
        title,
        description,
        fields=fields,
        section="TRADING EDUCATION",
        image_name=image_name,
    )


def build_trading_guides() -> list[dict]:
    return [
        {
            "name": "Chart Patterns",
            "tag": "Technical Analysis",
            "asset": "chart-patterns.png",
            "embeds": [
                trading_embed(
                    "Chart Patterns",
                    (
                        "Chart patterns organise price action into a shape that is easier to read. "
                        "They describe what has happened. They do not predict what must happen next."
                    ),
                    image_name="chart-patterns.png",
                    fields=[
                        {
                            "name": "Common Structures",
                            "value": (
                                "Triangles show price compressing. Flags show a short pause after a strong move. "
                                "Double tops and bottoms show a second test of an earlier area. Head and shoulders "
                                "shows three swings with the middle swing extending furthest."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Context Comes First",
                            "value": (
                                "Mark the prior trend, the nearby range and the timeframe. The same shape can mean "
                                "something different in a strong trend, at a major level or in thin conditions."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Before You Act",
                            "value": (
                                "Define the level that confirms the idea, the level that invalidates it and the "
                                "maximum loss before placing an order. A break can fail, so confirmation is not a guarantee."
                            ),
                            "inline": False,
                        },
                    ],
                )
            ],
        },
        {
            "name": "Candlestick Basics",
            "tag": "Technical Analysis",
            "asset": "candlestick-basics.png",
            "embeds": [
                trading_embed(
                    "Candlestick Basics",
                    (
                        "A candlestick summarises the open, high, low and close for one period. "
                        "Read the candle in context rather than treating one shape as a trade signal."
                    ),
                    image_name="candlestick-basics.png",
                    fields=[
                        {
                            "name": "Body and Wicks",
                            "value": (
                                "The body spans the open and close. The upper wick reaches the period high and the "
                                "lower wick reaches the period low. A large body shows a wide open-to-close move."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "What a Candle Cannot Tell You",
                            "value": (
                                "A candle does not show the exact order of every price move inside the period. "
                                "It also cannot confirm intent, future direction or available liquidity on its own."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Practical Use",
                            "value": (
                                "Compare the candle with recent structure, volume, the session and nearby levels. "
                                "Use one consistent timeframe for the decision you are making."
                            ),
                            "inline": False,
                        },
                    ],
                )
            ],
        },
        {
            "name": "Market Structure",
            "tag": "Technical Analysis",
            "asset": "market-structure.png",
            "embeds": [
                trading_embed(
                    "Market Structure",
                    (
                        "Market structure is the sequence of swing highs, swing lows and ranges visible on a chart. "
                        "It gives a consistent way to describe trend and balance without guessing."
                    ),
                    image_name="market-structure.png",
                    fields=[
                        {
                            "name": "Rising, Falling and Balanced",
                            "value": (
                                "Higher swing highs and higher swing lows describe rising structure. Lower swing highs "
                                "and lower swing lows describe falling structure. Repeated overlap between boundaries "
                                "describes a range."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Choose the Timeframe",
                            "value": (
                                "A five-minute chart can fall while an hourly chart still rises. State the timeframe "
                                "before naming the structure and use the one that matches the planned trade."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Structure Can Change",
                            "value": (
                                "A broken swing does not guarantee a new trend. Watch the next reaction and decide in "
                                "advance what evidence would invalidate your reading."
                            ),
                            "inline": False,
                        },
                    ],
                )
            ],
        },
        {
            "name": "Support & Resistance",
            "tag": "Technical Analysis",
            "asset": "support-resistance.png",
            "embeds": [
                trading_embed(
                    "Support & Resistance",
                    (
                        "Support and resistance mark areas where price has previously reacted. "
                        "Treat them as zones built from evidence, not exact lines that price must respect."
                    ),
                    image_name="support-resistance.png",
                    fields=[
                        {
                            "name": "Building a Zone",
                            "value": (
                                "Start with prior swing highs, swing lows, range edges and repeated closes. Keep the zone "
                                "wide enough to reflect normal price variation but narrow enough to guide a decision."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Reaction, Break and Retest",
                            "value": (
                                "Price may reject a zone, move through it or return after a break. None of these outcomes "
                                "is guaranteed. Wait for the behaviour your plan requires."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Keep It Usable",
                            "value": (
                                "Prioritise a small number of clear zones. If every price is marked, the chart no longer "
                                "helps you decide where the idea is wrong."
                            ),
                            "inline": False,
                        },
                    ],
                )
            ],
        },
        {
            "name": "Risk Management & Position Sizing",
            "tag": "Risk",
            "asset": "risk-position-sizing.png",
            "embeds": [
                trading_embed(
                    "Risk Management & Position Sizing",
                    (
                        "Risk is decided before the order is sent. Position size must fit the planned stop distance, "
                        "the contract value and the account rules."
                    ),
                    image_name="risk-position-sizing.png",
                    fields=[
                        {
                            "name": "Define the Loss First",
                            "value": (
                                "Choose the price that invalidates the trade and calculate the loss per contract at that "
                                "distance. Reduce the number of contracts if the total loss is too large."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Include Trading Friction",
                            "value": (
                                "Fast markets can fill beyond the expected price. Leave room for slippage and do not use "
                                "the account loss limit as a working stop."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Protect the Session",
                            "value": (
                                "Set a personal session limit below the platform limit. Do not widen a stop to avoid "
                                "accepting a planned loss, and stop trading when decision quality drops."
                            ),
                            "inline": False,
                        },
                    ],
                )
            ],
        },
        {
            "name": "Trading Psychology",
            "tag": "Psychology",
            "asset": "trading-psychology.png",
            "embeds": [
                trading_embed(
                    "Trading Psychology",
                    (
                        "Trading psychology is the ability to follow a sound process while outcomes remain uncertain. "
                        "Discipline is easier when the plan is written before pressure arrives."
                    ),
                    image_name="trading-psychology.png",
                    fields=[
                        {
                            "name": "Separate Decision From Outcome",
                            "value": (
                                "A good decision can lose and a poor decision can win. Review whether the trade followed "
                                "the plan instead of judging the process from one result."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Recognise the Warning Signs",
                            "value": (
                                "Rushing, increasing size after a loss, moving a stop and taking an unplanned setup are "
                                "reasons to pause. A short break is cheaper than trading to repair an emotion."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Build a Repeatable Routine",
                            "value": (
                                "Use a pre-trade checklist, a fixed review routine and clear conditions for ending the "
                                "session. Consistency matters more than intensity."
                            ),
                            "inline": False,
                        },
                    ],
                )
            ],
        },
        {
            "name": "Trading Sessions & Economic News",
            "tag": "Markets",
            "asset": "sessions-economic-news.png",
            "embeds": [
                trading_embed(
                    "Trading Sessions & Economic News",
                    (
                        "ES, NQ, MES and MNQ trade for most of the working week, but liquidity and volatility change "
                        "through the day. Scheduled economic releases can change both very quickly."
                    ),
                    image_name="sessions-economic-news.png",
                    fields=[
                        {
                            "name": "Session Conditions",
                            "value": (
                                "Activity often changes around the European open, the US cash open, major releases and "
                                "the daily futures maintenance break. Use current exchange times because daylight-saving "
                                "changes can move the local clock."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Economic Releases",
                            "value": (
                                "Inflation, employment, central-bank and growth releases can widen spreads and increase "
                                "slippage. Check the calendar before the session and know the exact Forge news rule for your tier."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "No Calendar Is Perfect",
                            "value": (
                                "Release times can change and unscheduled news can still move the market. A calendar is a "
                                "planning tool, not protection from volatility."
                            ),
                            "inline": False,
                        },
                    ],
                )
            ],
        },
        {
            "name": "Trading Plans & Journaling",
            "tag": "Process",
            "asset": "trading-plans-journaling.png",
            "embeds": [
                trading_embed(
                    "Trading Plans & Journaling",
                    (
                        "A trading plan defines the decision before the trade. A journal records what happened so the "
                        "process can be reviewed with evidence instead of memory."
                    ),
                    image_name="trading-plans-journaling.png",
                    fields=[
                        {
                            "name": "Before the Trade",
                            "value": (
                                "Record the setup, timeframe, entry condition, invalidation, position size, session window "
                                "and any scheduled news. If one of these is missing, the trade is not fully planned."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "After the Trade",
                            "value": (
                                "Save the entry and exit, a chart image, the reason for each action and whether the plan was "
                                "followed. Keep factual notes before adding an opinion."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "During Review",
                            "value": (
                                "Look for repeated process errors, not only profit and loss. Change one rule at a time and "
                                "review enough examples before deciding whether the change helped."
                            ),
                            "inline": False,
                        },
                    ],
                )
            ],
        },
    ]


def desired_trading_forum_payload() -> dict:
    member_allow = (
        public_info.VIEW_CHANNEL
        | public_info.READ_MESSAGE_HISTORY
        | public_info.ADD_REACTIONS
    )
    member_deny = (
        public_info.SEND_MESSAGES
        | public_info.CREATE_PUBLIC_THREADS
        | public_info.CREATE_PRIVATE_THREADS
        | public_info.SEND_MESSAGES_IN_THREADS
    )
    bot_allow = member_allow | member_deny
    return {
        "name": TRADING_FORUM_NAME,
        "type": 15,
        "parent_id": public_info.EDUCATION_CATEGORY_ID,
        "topic": TRADING_FORUM_TOPIC,
        "default_auto_archive_duration": 10080,
        "default_forum_layout": 2,
        "default_sort_order": 0,
        "available_tags": [
            {"name": "Technical Analysis", "moderated": False, "emoji_name": "📊"},
            {"name": "Risk", "moderated": False, "emoji_name": "🛡️"},
            {"name": "Psychology", "moderated": False, "emoji_name": "🧠"},
            {"name": "Markets", "moderated": False, "emoji_name": "🌍"},
            {"name": "Process", "moderated": False, "emoji_name": "📝"},
        ],
        "permission_overwrites": [
            {
                "id": public_info.GUILD_ID,
                "type": 0,
                "allow": str(member_allow),
                "deny": str(member_deny),
            },
            {
                "id": public_info.BOT_ID,
                "type": 1,
                "allow": str(bot_allow),
                "deny": "0",
            },
        ],
    }


def ensure_trading_forum(channels: dict[str, dict]) -> dict:
    existing = channels.get(TRADING_FORUM_NAME)
    if existing:
        if existing.get("type") != 15:
            raise public_info.DiscordError("trading-education exists but is not a forum")
        if existing.get("parent_id") != public_info.EDUCATION_CATEGORY_ID:
            raise public_info.DiscordError("trading-education is outside the Education category")
        if RELEASE_MARKER not in str(existing.get("topic") or ""):
            raise public_info.DiscordError("trading-education is not managed by this release")
        return existing
    return public_info.expect(
        public_info.request(
            "POST",
            f"/guilds/{public_info.GUILD_ID}/channels",
            json_body=desired_trading_forum_payload(),
            reason=f"Create {RELEASE_MARKER} Trading Education",
        ),
        (200, 201),
        "Trading Education forum creation",
    )


def verify_assets() -> None:
    public_info.verify_assets()
    for guide in build_trading_guides():
        asset_path = TRADING_ASSET_DIR / guide["asset"]
        if not asset_path.is_file() or asset_path.stat().st_size <= 0:
            raise public_info.DiscordError(f"Missing Trading Education asset: {asset_path.name}")
        public_info.validate_embeds(guide["embeds"])


def forum_from_names(channels: dict[str, dict], names: tuple[str, ...]) -> dict | None:
    return next((channels.get(name) for name in names if channels.get(name)), None)


def validate_existing_forums(channels: dict[str, dict]) -> None:
    forge = forum_from_names(
        channels,
        (public_info.FORUM_NAME, *public_info.LEGACY_FORUM_NAMES),
    )
    if forge:
        if forge.get("type") != 15 or forge.get("parent_id") != public_info.EDUCATION_CATEGORY_ID:
            raise public_info.DiscordError("Existing Forge Education channel has an unexpected type or category")
        if public_info.CONTENT_MARKER not in str(forge.get("topic") or ""):
            raise public_info.DiscordError("Existing Forge Education channel is missing its managed marker")
    trading = channels.get(TRADING_FORUM_NAME)
    if trading:
        if trading.get("type") != 15 or trading.get("parent_id") != public_info.EDUCATION_CATEGORY_ID:
            raise public_info.DiscordError("Existing Trading Education channel has an unexpected type or category")
        if RELEASE_MARKER not in str(trading.get("topic") or ""):
            raise public_info.DiscordError("Existing Trading Education channel is missing its managed marker")


def archive_state(channel: dict) -> dict:
    return {
        "id": str(channel["id"]),
        "name": str(channel["name"]),
        "topic": channel.get("topic"),
        "position": channel.get("position"),
        "parent_id": channel.get("parent_id"),
        "permission_overwrites": channel.get("permission_overwrites", []),
    }


def archive_state_content(channel: dict) -> str:
    content = ARCHIVE_STATE_MARKER + "\n" + json.dumps(
        archive_state(channel),
        separators=(",", ":"),
        ensure_ascii=True,
    )
    if len(content) > 2000:
        raise public_info.DiscordError(
            f"Rollback metadata is too large for #{channel.get('name')}"
        )
    return content


def archive_permissions(channel: dict) -> list[dict]:
    overwrites = [dict(item) for item in channel.get("permission_overwrites", [])]
    seen_bot = False
    seen_everyone = False
    for overwrite in overwrites:
        allow = int(overwrite.get("allow", "0")) & ~public_info.VIEW_CHANNEL
        deny = int(overwrite.get("deny", "0")) | public_info.VIEW_CHANNEL
        if str(overwrite.get("id")) == public_info.BOT_ID:
            seen_bot = True
            allow |= (
                public_info.VIEW_CHANNEL
                | public_info.READ_MESSAGE_HISTORY
                | public_info.SEND_MESSAGES
            )
            deny &= ~public_info.VIEW_CHANNEL
        if str(overwrite.get("id")) == public_info.GUILD_ID:
            seen_everyone = True
        overwrite["allow"] = str(allow)
        overwrite["deny"] = str(deny)
    if not seen_everyone:
        overwrites.append(
            {
                "id": public_info.GUILD_ID,
                "type": 0,
                "allow": "0",
                "deny": str(public_info.VIEW_CHANNEL),
            }
        )
    if not seen_bot:
        overwrites.append(
            {
                "id": public_info.BOT_ID,
                "type": 1,
                "allow": str(
                    public_info.VIEW_CHANNEL
                    | public_info.READ_MESSAGE_HISTORY
                    | public_info.SEND_MESSAGES
                ),
                "deny": "0",
            }
        )
    return overwrites


def validate_archive_candidates(channels: dict[str, dict]) -> None:
    for public_name, archive_name in ARCHIVE_TARGETS.items():
        public_channel = channels.get(public_name)
        archive_channel = channels.get(archive_name)
        if public_channel and archive_channel and public_channel.get("id") != archive_channel.get("id"):
            raise public_info.DiscordError(
                f"Both #{public_name} and #{archive_name} exist; refusing an ambiguous archive"
            )
        channel = public_channel or archive_channel
        if not channel:
            continue
        if channel.get("type") != 0:
            raise public_info.DiscordError(f"#{channel.get('name')} is not a text channel")
        if channel.get("parent_id") != public_info.EDUCATION_CATEGORY_ID:
            raise public_info.DiscordError(
                f"#{channel.get('name')} is outside the Education category"
            )
        if public_channel:
            archive_state_content(public_channel)


def find_archive_state_message(channel_id: str) -> dict | None:
    messages = public_info.expect(
        public_info.request("GET", f"/channels/{channel_id}/messages?limit=100"),
        (200,),
        "Education archive message inventory",
    )
    return next(
        (
            message
            for message in messages
            if str(message.get("author", {}).get("id")) == public_info.BOT_ID
            and str(message.get("content") or "").startswith(ARCHIVE_STATE_MARKER + "\n")
        ),
        None,
    )


def archive_channel(channel: dict, archive_name: str) -> None:
    channel_id = str(channel["id"])
    backup_message = find_archive_state_message(channel_id)
    created_backup_id: str | None = None
    if not backup_message:
        backup_message = public_info.expect(
            public_info.request(
                "POST",
                f"/channels/{channel_id}/messages",
                json_body={
                    "allowed_mentions": {"parse": []},
                    "content": archive_state_content(channel),
                },
            ),
            (200, 201),
            f"Rollback state for #{channel.get('name')}",
        )
        created_backup_id = str(backup_message["id"])
    channel_renamed = False
    try:
        public_info.expect(
            public_info.request(
                "PATCH",
                f"/channels/{channel_id}",
                json_body={
                    "name": archive_name,
                    "topic": (
                        f"{RELEASE_MARKER} | Hidden rollback archive. "
                        "Original messages are preserved."
                    ),
                },
                reason=f"Archive replaced Education channel for {RELEASE_MARKER}",
            ),
            (200,),
            f"Archive #{channel.get('name')}",
        )
        channel_renamed = True
        for overwrite in archive_permissions(channel):
            public_info.expect(
                public_info.request(
                    "PUT",
                    f"/channels/{channel_id}/permissions/{overwrite['id']}",
                    json_body={
                        "type": overwrite["type"],
                        "allow": overwrite["allow"],
                        "deny": overwrite["deny"],
                    },
                    reason=f"Hide replaced Education channel for {RELEASE_MARKER}",
                ),
                (200, 204),
                f"Hide #{archive_name} from members",
            )
    except Exception:
        if created_backup_id and not channel_renamed:
            public_info.request(
                "DELETE",
                f"/channels/{channel_id}/messages/{created_backup_id}",
                reason=f"Remove unused rollback state for {RELEASE_MARKER}",
            )
        raise


def archive_replaced_channels() -> None:
    channels = public_info.index_channels(public_info.get_guild_channels())
    validate_archive_candidates(channels)
    for public_name, archive_name in ARCHIVE_TARGETS.items():
        channel = channels.get(public_name)
        if not channel:
            print(f"CHECKED: hidden #{archive_name}")
            continue
        archive_channel(channel, archive_name)
        print(f"ARCHIVED: #{public_name} as hidden #{archive_name}")


def delete_replaced_channels() -> None:
    """Permanently delete only the three explicitly retired Education channels."""
    channels = public_info.index_channels(public_info.get_guild_channels())
    validate_archive_candidates(channels)
    for public_name, archive_name in ARCHIVE_TARGETS.items():
        channel = channels.get(public_name) or channels.get(archive_name)
        if not channel:
            print(f"CHECKED: retired #{public_name} is already deleted")
            continue
        public_info.expect(
            public_info.request(
                "DELETE",
                f"/channels/{channel['id']}",
                reason=f"Permanently remove user-approved empty Education archive for {RELEASE_MARKER}",
            ),
            (200, 204),
            f"Delete #{channel.get('name')}",
        )
        print(f"DELETED: #{channel.get('name')}")


def verify_guide_forum(
    forum: dict,
    guides: list[dict],
    *,
    attachment_prefix: str,
    label: str,
) -> None:
    threads = {
        str(thread.get("name")): thread
        for thread in public_info.active_and_archived_threads(str(forum["id"]))
    }
    missing = [guide["name"] for guide in guides if guide["name"] not in threads]
    if missing:
        raise public_info.DiscordError(f"Missing {label} guides: {', '.join(missing)}")
    for guide in guides:
        thread_id = str(threads[guide["name"]]["id"])
        message = public_info.expect(
            public_info.request("GET", f"/channels/{thread_id}/messages/{thread_id}"),
            (200,),
            f"{label} guide verification {guide['name']}",
        )
        if public_info.embed_copy_signature(message.get("embeds", [])) != public_info.embed_copy_signature(guide["embeds"]):
            raise public_info.DiscordError(f"{label} guide copy is stale: {guide['name']}")
        attachments = message.get("attachments", [])
        expected_filename = public_info.guide_attachment_name(guide, attachment_prefix)
        rich_image_embeds = [
            embed
            for embed in message.get("embeds", [])
            if embed.get("title") and embed.get("image", {}).get("url")
        ]
        if rich_image_embeds or len(attachments) != 1:
            raise public_info.DiscordError(
                f"{label} guide must show exactly one image: {guide['name']}"
            )
        if str(attachments[0].get("filename")) != expected_filename:
            raise public_info.DiscordError(f"{label} guide artwork is stale: {guide['name']}")


def verify_information_only_forum(forum: dict, label: str) -> None:
    everyone = next(
        (
            overwrite
            for overwrite in forum.get("permission_overwrites", [])
            if str(overwrite.get("id")) == public_info.GUILD_ID
        ),
        None,
    )
    if not everyone:
        raise public_info.DiscordError(f"{label} is missing the member permission boundary")
    allow = int(everyone.get("allow", "0"))
    deny = int(everyone.get("deny", "0"))
    required_deny = (
        public_info.SEND_MESSAGES
        | public_info.CREATE_PUBLIC_THREADS
        | public_info.CREATE_PRIVATE_THREADS
        | public_info.SEND_MESSAGES_IN_THREADS
    )
    if not (allow & public_info.VIEW_CHANNEL) or not (allow & public_info.READ_MESSAGE_HISTORY):
        raise public_info.DiscordError(f"{label} is not readable by members")
    if deny & required_deny != required_deny:
        raise public_info.DiscordError(f"{label} is not information-only")


def verify_forums() -> None:
    channels = public_info.index_channels(public_info.get_guild_channels())
    forge_forum = channels.get(public_info.FORUM_NAME)
    trading_forum = channels.get(TRADING_FORUM_NAME)
    if not forge_forum:
        raise public_info.DiscordError("Forge Education forum is missing")
    if not trading_forum or RELEASE_MARKER not in str(trading_forum.get("topic") or ""):
        raise public_info.DiscordError("Trading Education forum is missing")
    verify_information_only_forum(forge_forum, "Forge Education")
    verify_information_only_forum(trading_forum, "Trading Education")
    verify_guide_forum(
        forge_forum,
        public_info.build_education_guides(),
        attachment_prefix="forge-education",
        label="Forge Education",
    )
    verify_guide_forum(
        trading_forum,
        build_trading_guides(),
        attachment_prefix="trading-education",
        label="Trading Education",
    )


def verify_deleted_channels() -> None:
    channels = public_info.index_channels(public_info.get_guild_channels())
    for public_name, archive_name in ARCHIVE_TARGETS.items():
        if channels.get(public_name):
            raise public_info.DiscordError(f"Replaced channel is still public: #{public_name}")
        if channels.get(archive_name):
            raise public_info.DiscordError(f"Retired archive still exists: #{archive_name}")


def apply_guides(
    forum: dict,
    guides: list[dict],
    *,
    asset_dir: Path,
    attachment_prefix: str,
    label: str,
) -> None:
    threads = {
        str(thread.get("name")): thread
        for thread in public_info.active_and_archived_threads(str(forum["id"]))
    }
    for guide in reversed(guides):
        thread = public_info.find_guide_thread(threads, guide)
        if thread:
            public_info.update_forum_guide(
                thread,
                guide,
                asset_dir=asset_dir,
                attachment_prefix=attachment_prefix,
                label=label,
            )
            print(f"CHECKED: {label} guide {guide['name']}")
            continue
        thread_id = public_info.create_forum_guide(
            forum,
            guide,
            asset_dir=asset_dir,
            attachment_prefix=attachment_prefix,
            label=label,
        )
        print(f"CREATED: {label} guide {guide['name']} ({thread_id})")


def plan() -> None:
    verify_assets()
    channels = public_info.index_channels(public_info.get_guild_channels())
    validate_existing_forums(channels)
    validate_archive_candidates(channels)
    forge = forum_from_names(
        channels,
        (public_info.FORUM_NAME, *public_info.LEGACY_FORUM_NAMES),
    )
    print(f"PLAN: #{public_info.FORUM_NAME} {'will be updated' if forge else 'will be created'}")
    print(
        f"PLAN: #{TRADING_FORUM_NAME} "
        f"{'will be updated' if channels.get(TRADING_FORUM_NAME) else 'will be created'}"
    )
    for guide in build_trading_guides():
        print(f"PLAN: Trading Education guide {guide['name']} [{guide['tag']}]")
    for public_name, archive_name in ARCHIVE_TARGETS.items():
        if channels.get(public_name):
            state = "will be permanently deleted"
        elif channels.get(archive_name):
            state = f"hidden as #{archive_name} and will be permanently deleted"
        else:
            state = "already deleted"
        print(f"PLAN: #{public_name} {state}")
    print("DESTRUCTIVE: the three user-approved empty retired channels will be permanently deleted")


def apply() -> None:
    verify_assets()
    channels = public_info.index_channels(public_info.get_guild_channels())
    validate_existing_forums(channels)
    validate_archive_candidates(channels)

    forge_forum = public_info.ensure_forum(channels)
    apply_guides(
        forge_forum,
        public_info.build_education_guides(),
        asset_dir=public_info.ASSET_DIR,
        attachment_prefix="forge-education",
        label="Forge Education",
    )

    channels = public_info.index_channels(public_info.get_guild_channels())
    trading_forum = ensure_trading_forum(channels)
    apply_guides(
        trading_forum,
        build_trading_guides(),
        asset_dir=TRADING_ASSET_DIR,
        attachment_prefix="trading-education",
        label="Trading Education",
    )

    verify_forums()
    delete_replaced_channels()
    verify_deleted_channels()
    print("OK: Forge Education and Trading Education are live and verified")


def verify() -> None:
    verify_assets()
    verify_forums()
    verify_deleted_channels()
    print("OK: education upgrade, single-image cards and retired channel deletion verified")


def restore_archive(channel: dict) -> None:
    message = find_archive_state_message(str(channel["id"]))
    if not message:
        raise public_info.DiscordError(f"Rollback metadata is missing: #{channel.get('name')}")
    content = str(message.get("content") or "")
    state = json.loads(content.split("\n", 1)[1])
    public_info.expect(
        public_info.request(
            "PATCH",
            f"/channels/{channel['id']}",
            json_body={
                "name": state["name"],
                "topic": state.get("topic"),
                "position": state.get("position"),
                "parent_id": state.get("parent_id"),
            },
            reason=f"Restore Education channel from {RELEASE_MARKER}",
        ),
        (200,),
        f"Restore #{state['name']}",
    )
    desired_overwrites = {
        str(overwrite["id"]): overwrite
        for overwrite in state.get("permission_overwrites", [])
    }
    current_overwrites = {
        str(overwrite["id"]): overwrite
        for overwrite in channel.get("permission_overwrites", [])
    }
    for overwrite_id in current_overwrites.keys() - desired_overwrites.keys():
        public_info.expect(
            public_info.request(
                "DELETE",
                f"/channels/{channel['id']}/permissions/{overwrite_id}",
                reason=f"Restore Education permissions from {RELEASE_MARKER}",
            ),
            (200, 204),
            f"Remove archive permission from #{state['name']}",
        )
    for overwrite in desired_overwrites.values():
        public_info.expect(
            public_info.request(
                "PUT",
                f"/channels/{channel['id']}/permissions/{overwrite['id']}",
                json_body={
                    "type": overwrite["type"],
                    "allow": overwrite["allow"],
                    "deny": overwrite["deny"],
                },
                reason=f"Restore Education permissions from {RELEASE_MARKER}",
            ),
            (200, 204),
            f"Restore permissions for #{state['name']}",
        )
    public_info.expect(
        public_info.request(
            "DELETE",
            f"/channels/{channel['id']}/messages/{message['id']}",
            reason=f"Remove used rollback state for {RELEASE_MARKER}",
        ),
        (200, 204),
        f"Remove rollback state for #{state['name']}",
    )


def rollback() -> None:
    channels = public_info.index_channels(public_info.get_guild_channels())
    for archive_name in ARCHIVE_TARGETS.values():
        channel = channels.get(archive_name)
        if channel:
            restore_archive(channel)
            print(f"RESTORED: #{archive_name}")

    channels = public_info.index_channels(public_info.get_guild_channels())
    trading_forum = channels.get(TRADING_FORUM_NAME)
    if trading_forum and RELEASE_MARKER in str(trading_forum.get("topic") or ""):
        public_info.expect(
            public_info.request(
                "DELETE",
                f"/channels/{trading_forum['id']}",
                reason=f"Roll back {RELEASE_MARKER}",
            ),
            (200, 204),
            "Trading Education rollback",
        )
        print(f"REMOVED: managed #{TRADING_FORUM_NAME} forum")

    channels = public_info.index_channels(public_info.get_guild_channels())
    forge_forum = channels.get(public_info.FORUM_NAME)
    if forge_forum and public_info.CONTENT_MARKER in str(forge_forum.get("topic") or ""):
        public_info.expect(
            public_info.request(
                "PATCH",
                f"/channels/{forge_forum['id']}",
                json_body={
                    "name": public_info.LEGACY_FORUM_NAMES[0],
                    "topic": (
                        f"{public_info.CONTENT_MARKER} | Structured, information-only "
                        "Forge Futures education."
                    ),
                },
                reason=f"Roll back {RELEASE_MARKER} forum rename",
            ),
            (200,),
            "Forge Education rollback",
        )
        print(f"RESTORED: #{public_info.LEGACY_FORUM_NAMES[0]}")
    print("OK: education forums rolled back; permanently deleted retired channels cannot be restored")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if mode not in {"plan", "apply", "verify", "rollback"}:
        raise SystemExit("Usage: python education_upgrade.py [plan|apply|verify|rollback]")
    if not public_info.TOKEN:
        raise SystemExit("DISCORD_BOT_TOKEN is required")
    try:
        {"plan": plan, "apply": apply, "verify": verify, "rollback": rollback}[mode]()
    except (public_info.DiscordError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
