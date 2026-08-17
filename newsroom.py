"""Shared Forge Futures newsroom delivery and formatting helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import xml.etree.ElementTree as ElementTree
from zoneinfo import ZoneInfo

import requests


DISCORD_BASE = "https://discord.com/api/v10"
DISCORD_TIMEOUT_SECONDS = 15
DISCORD_EMBED_COUNT_LIMIT = 10
DISCORD_EMBED_TOTAL_LIMIT = 6000
DISCORD_FIELD_COUNT_LIMIT = 25
DISCORD_FIELD_NAME_LIMIT = 256
DISCORD_FIELD_VALUE_LIMIT = 1024
DISCORD_TITLE_LIMIT = 256
DISCORD_DESCRIPTION_LIMIT = 4096
DISCORD_FOOTER_LIMIT = 2048
CALENDAR_JSON_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CALENDAR_XML_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
CALENDAR_REQUEST_ATTEMPTS = 2
FORGE_ORANGE = 0xFE602F
FORGE_SITE_URL = os.environ.get("FORGE_SITE_URL", "https://forge-futures.com")
FORGE_DISCORD_URL = os.environ.get(
    "FORGE_DISCORD_INVITE_URL",
    "https://discord.gg/KQSQRgMZZB",
)
FORGE_ICON_URL = os.environ.get(
    "FORGE_ICON_URL",
    f"{FORGE_SITE_URL.rstrip('/')}/favicon.png",
)

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
URL_PATTERN = re.compile(r"https://[^\s>)\]}]+")


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    message_id: str | None = None
    published: bool = False
    error: str | None = None

    def __bool__(self) -> bool:
        return self.ok


def discord_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
    }


def clean_text(value: object, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    text = text.replace("@everyone", "everyone").replace("@here", "here")
    text = text.replace("[", "\\[").replace("]", "\\]")
    return text[:limit].rstrip()


def safe_https_url(value: object) -> str | None:
    try:
        parsed = urlsplit(str(value or "").strip())
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def canonical_url(value: object) -> str | None:
    safe_url = safe_https_url(value)
    if not safe_url:
        return None
    parsed = urlsplit(safe_url)
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_KEYS
        and not key.lower().startswith(TRACKING_QUERY_PREFIXES)
    ]
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), path, urlencode(query), "")
    )


def markdown_link(title: object, url: object) -> str | None:
    safe_url = safe_https_url(url)
    if not safe_url:
        return None
    if len(safe_url) > 700:
        parsed = urlsplit(safe_url)
        safe_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    if len(safe_url) > 700:
        return None
    return f"[{clean_text(title, 130)}]({safe_url})"


def embed_character_count(embed: dict) -> int:
    total = len(str(embed.get("title") or ""))
    total += len(str(embed.get("description") or ""))
    total += len(str(embed.get("footer", {}).get("text") or ""))
    total += len(str(embed.get("author", {}).get("name") or ""))
    for field in embed.get("fields", []):
        total += len(str(field.get("name") or ""))
        total += len(str(field.get("value") or ""))
    return total


def validate_embeds(embeds: list[dict]) -> str | None:
    if not 1 <= len(embeds) <= DISCORD_EMBED_COUNT_LIMIT:
        return f"embed count must be 1-{DISCORD_EMBED_COUNT_LIMIT}"
    for embed_index, embed in enumerate(embeds, start=1):
        if len(str(embed.get("title") or "")) > DISCORD_TITLE_LIMIT:
            return f"embed {embed_index} title exceeds {DISCORD_TITLE_LIMIT} characters"
        if len(str(embed.get("description") or "")) > DISCORD_DESCRIPTION_LIMIT:
            return (
                f"embed {embed_index} description exceeds "
                f"{DISCORD_DESCRIPTION_LIMIT} characters"
            )
        if len(str(embed.get("footer", {}).get("text") or "")) > DISCORD_FOOTER_LIMIT:
            return f"embed {embed_index} footer exceeds {DISCORD_FOOTER_LIMIT} characters"
        fields = embed.get("fields", [])
        if len(fields) > DISCORD_FIELD_COUNT_LIMIT:
            return f"embed {embed_index} has more than {DISCORD_FIELD_COUNT_LIMIT} fields"
        for field_index, field in enumerate(fields, start=1):
            if len(str(field.get("name") or "")) > DISCORD_FIELD_NAME_LIMIT:
                return (
                    f"embed {embed_index} field {field_index} name exceeds "
                    f"{DISCORD_FIELD_NAME_LIMIT} characters"
                )
            if len(str(field.get("value") or "")) > DISCORD_FIELD_VALUE_LIMIT:
                return (
                    f"embed {embed_index} field {field_index} value exceeds "
                    f"{DISCORD_FIELD_VALUE_LIMIT} characters"
                )
        if embed_character_count(embed) > DISCORD_EMBED_TOTAL_LIMIT:
            return f"embed {embed_index} exceeds {DISCORD_EMBED_TOTAL_LIMIT} characters"
    return None


def discord_error_summary(response: object) -> str:
    try:
        payload = response.json()
    except (TypeError, ValueError, AttributeError):
        payload = {}
    if not isinstance(payload, dict):
        return ""
    code = clean_text(payload.get("code"), 30)
    message = clean_text(payload.get("message"), 160)
    details = " · ".join(part for part in (code, message) if part)
    return f" ({details})" if details else ""


def brand_embed(
    embed: dict,
    *,
    timestamp: datetime | None = None,
    data_note: str | None = None,
) -> dict:
    branded = dict(embed)
    branded.setdefault("color", FORGE_ORANGE)
    branded.setdefault("url", FORGE_SITE_URL)
    branded["author"] = {
        "name": "FORGE FUTURES · MARKET DESK",
        "url": FORGE_SITE_URL,
        "icon_url": FORGE_ICON_URL,
    }
    footer_parts = [
        "Curated by Forge Futures",
        "Source-linked information",
        "Not financial advice",
    ]
    if data_note:
        footer_parts.append(clean_text(data_note, 220))
    footer_parts.append("forge-futures.com")
    branded["footer"] = {
        "text": " • ".join(footer_parts),
        "icon_url": FORGE_ICON_URL,
    }
    branded["timestamp"] = (timestamp or datetime.now(timezone.utc)).isoformat()
    return branded


def post_discord(
    token: str,
    channel_id: str,
    embeds: list[dict],
    *,
    publish: bool = False,
) -> DeliveryResult:
    validation_error = validate_embeds(embeds)
    if validation_error:
        error = f"Discord payload rejected locally: {validation_error}"
        print(error)
        return DeliveryResult(False, error=error)

    payload = {
        "allowed_mentions": {"parse": []},
        "embeds": embeds,
    }
    try:
        response = requests.post(
            f"{DISCORD_BASE}/channels/{channel_id}/messages",
            headers=discord_headers(token),
            json=payload,
            timeout=DISCORD_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        error = f"Discord post failed: {type(exc).__name__}"
        print(error)
        return DeliveryResult(False, error=error)

    if response.status_code not in (200, 201):
        error = (
            f"Discord post failed with HTTP {response.status_code}"
            f"{discord_error_summary(response)}"
        )
        print(error)
        return DeliveryResult(False, error=error)

    message_id = str(response.json().get("id") or "") or None
    if not publish:
        return DeliveryResult(True, message_id=message_id)
    if not message_id:
        error = "Discord post succeeded without a message id; publishing was skipped"
        print(error)
        return DeliveryResult(False, error=error)

    try:
        crosspost = requests.post(
            f"{DISCORD_BASE}/channels/{channel_id}/messages/{message_id}/crosspost",
            headers=discord_headers(token),
            timeout=DISCORD_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        error = f"Discord publish failed: {type(exc).__name__}"
        print(error)
        return DeliveryResult(False, message_id=message_id, error=error)

    if crosspost.status_code not in (200, 201):
        error = (
            f"Discord publish failed with HTTP {crosspost.status_code}"
            f"{discord_error_summary(crosspost)}"
        )
        print(error)
        return DeliveryResult(False, message_id=message_id, error=error)
    return DeliveryResult(True, message_id=message_id, published=True)


def recent_channel_links(token: str, channel_id: str, limit: int = 50) -> set[str]:
    try:
        response = requests.get(
            f"{DISCORD_BASE}/channels/{channel_id}/messages?limit={max(1, min(limit, 100))}",
            headers=discord_headers(token),
            timeout=DISCORD_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        return set()
    if response.status_code != 200:
        return set()

    links: set[str] = set()
    for message in response.json():
        rendered = json.dumps(
            {
                "content": message.get("content"),
                "embeds": message.get("embeds"),
            },
            ensure_ascii=False,
        )
        for raw_url in URL_PATTERN.findall(rendered):
            normalized = canonical_url(raw_url.rstrip(".,;\\\""))
            if normalized:
                links.add(normalized)
    return links


def filter_unseen_news(
    items: list[dict],
    seen_links: set[str],
    *,
    limit: int = 5,
) -> list[dict]:
    selected: list[dict] = []
    local_links: set[str] = set()
    local_titles: set[str] = set()
    for item in items:
        normalized = canonical_url(item.get("url"))
        title_key = clean_text(item.get("title"), 130).casefold()
        if not normalized or not title_key:
            continue
        if normalized in seen_links or normalized in local_links or title_key in local_titles:
            continue
        selected.append({**item, "url": normalized})
        local_links.add(normalized)
        local_titles.add(title_key)
        if len(selected) >= limit:
            break
    return selected


def headline_category(title: object) -> str:
    lowered = str(title or "").casefold()
    categories = [
        ("Rates & Fed", ("fed", "fomc", "rate cut", "rate hike", "treasury", "yield")),
        ("Inflation", ("cpi", "ppi", "inflation", "prices")),
        ("Growth & jobs", ("payroll", "jobs", "unemployment", "gdp", "pmi")),
        ("Energy", ("oil", "crude", "opec", "energy")),
        ("Technology", ("nasdaq", "semiconductor", "ai ", "nvidia", "technology")),
        ("Equities", ("s&p", "stocks", "equities", "earnings")),
    ]
    for category, terms in categories:
        if any(term in lowered for term in terms):
            return category
    return "Markets"


MARKET_LENS = {
    "Rates & Fed": "Rates and Fed headlines can quickly reshape index-futures volatility and valuation expectations.",
    "Inflation": "Inflation releases often move Treasury yields, the dollar and expectations for future rates.",
    "Growth & jobs": "Growth and labour data can change the market's view of demand, earnings and central-bank policy.",
    "Energy": "Energy moves can affect inflation expectations and risk sentiment across futures markets.",
    "Technology": "Large technology moves can have an outsized influence on Nasdaq futures.",
    "Equities": "Broad equity headlines can alter risk appetite across ES and NQ futures.",
    "Markets": "Fresh macro and market headlines can increase volatility around major session opens.",
}


def headline_blocks(items: list[dict], *, limit: int = 5) -> list[str]:
    blocks: list[str] = []
    for item in items[:limit]:
        link = markdown_link(item.get("title"), item.get("url"))
        if not link:
            continue
        source = clean_text(item.get("source") or urlsplit(item["url"]).netloc, 45)
        category = clean_text(item.get("category") or headline_category(item.get("title")), 35)
        block = f"**{category}** · {link}\n{source}"
        if len(block) <= DISCORD_FIELD_VALUE_LIMIT:
            blocks.append(block)
    return blocks


def render_headlines(items: list[dict], *, limit: int = 5) -> str:
    blocks = headline_blocks(items, limit=limit)
    if not blocks:
        return "No fresh, non-duplicate headlines were returned by the current sources."
    return "\n\n".join(blocks)


def headline_fields(items: list[dict], *, title: str, limit: int = 5) -> list[dict]:
    blocks = headline_blocks(items, limit=limit)
    if not blocks:
        return [{
            "name": title,
            "value": "No fresh, non-duplicate headlines were returned by the current sources.",
            "inline": False,
        }]

    chunks: list[str] = []
    current: list[str] = []
    for block in blocks:
        candidate = "\n\n".join([*current, block])
        if current and len(candidate) > DISCORD_FIELD_VALUE_LIMIT:
            chunks.append("\n\n".join(current))
            current = [block]
        else:
            current.append(block)
    if current:
        chunks.append("\n\n".join(current))

    return [
        {
            "name": title if index == 0 else f"{title} · CONTINUED {index + 1}",
            "value": chunk,
            "inline": False,
        }
        for index, chunk in enumerate(chunks)
    ]


def render_market_lens(items: list[dict], *, limit: int = 3) -> str:
    categories: list[str] = []
    for item in items:
        category = str(item.get("category") or headline_category(item.get("title")))
        if category not in categories:
            categories.append(category)
    if not categories:
        return "Stay alert to scheduled releases and verify market information with primary sources."
    return "\n".join(f"• {MARKET_LENS[category]}" for category in categories[:limit])


def parse_calendar_xml(payload: bytes) -> list[dict]:
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return []

    events: list[dict] = []
    for node in root.findall(".//event"):
        date_value = str(node.findtext("date") or "").strip()
        time_value = str(node.findtext("time") or "").strip().replace(" ", "")
        parsed_date: datetime | None = None
        for date_format in ("%m-%d-%Y %I:%M%p", "%m-%d-%Y %H:%M"):
            try:
                parsed_date = datetime.strptime(
                    f"{date_value} {time_value}",
                    date_format,
                )
                break
            except ValueError:
                continue
        if not parsed_date:
            continue
        events.append({
            "title": str(node.findtext("title") or "").strip(),
            "country": str(node.findtext("country") or "").strip(),
            "date": parsed_date.isoformat(),
            "impact": str(node.findtext("impact") or "").strip(),
            "forecast": str(node.findtext("forecast") or "").strip(),
            "previous": str(node.findtext("previous") or "").strip(),
        })
    return events


def fetch_economic_calendar(
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 10,
) -> list[dict]:
    for attempt in range(1, CALENDAR_REQUEST_ATTEMPTS + 1):
        try:
            response = requests.get(
                CALENDAR_JSON_URL,
                headers=headers,
                timeout=timeout,
            )
            if response.status_code == 200:
                events = response.json()
                if isinstance(events, list) and events:
                    return events
            else:
                print(
                    "Economic calendar JSON returned HTTP "
                    f"{response.status_code} (attempt {attempt})"
                )
        except (requests.RequestException, TypeError, ValueError) as exc:
            print(
                "Economic calendar JSON request failed: "
                f"{type(exc).__name__} (attempt {attempt})"
            )

    try:
        response = requests.get(
            CALENDAR_XML_URL,
            headers=headers,
            timeout=timeout,
        )
        if response.status_code == 200:
            events = parse_calendar_xml(response.content)
            if events:
                return events
        else:
            print(f"Economic calendar XML returned HTTP {response.status_code}")
    except requests.RequestException as exc:
        print(f"Economic calendar XML request failed: {type(exc).__name__}")
    return []


def parse_event_datetime(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("America/New_York"))
    return parsed.astimezone(timezone.utc)


def select_calendar_events(
    events: list[dict],
    *,
    start: datetime | None = None,
    hours: int = 36,
    impacts: tuple[str, ...] = ("High",),
) -> list[dict]:
    window_start = (start or datetime.now(timezone.utc)).astimezone(timezone.utc)
    window_end = window_start + timedelta(hours=hours)
    selected: list[dict] = []
    for event in events:
        event_time = parse_event_datetime(event.get("date"))
        if not event_time or not window_start <= event_time <= window_end:
            continue
        if event.get("impact") not in impacts:
            continue
        if event.get("country") not in ("USD", "All", "", None):
            continue
        selected.append({**event, "event_time": event_time})
    return sorted(selected, key=lambda event: event["event_time"])


def render_calendar_events(events: list[dict], *, limit: int = 6) -> str:
    if not events:
        return (
            "The current feed returned no matching events for this window. "
            "Verify the official economic calendar before trading."
        )
    london = ZoneInfo("Europe/London")
    new_york = ZoneInfo("America/New_York")
    lines: list[str] = []
    for event in events[:limit]:
        event_time = event["event_time"]
        uk_time = event_time.astimezone(london)
        et_time = event_time.astimezone(new_york)
        title = clean_text(event.get("title") or "Scheduled release", 100)
        forecast = clean_text(event.get("forecast") or "—", 30)
        previous = clean_text(event.get("previous") or "—", 30)
        lines.append(
            f"🔴 **{uk_time:%a %d %b · %H:%M UK} / {et_time:%H:%M ET}**\n"
            f"{title} · Forecast `{forecast}` · Previous `{previous}`"
        )
    return "\n\n".join(lines)
