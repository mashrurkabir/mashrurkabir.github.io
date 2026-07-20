#!/usr/bin/env python3
"""
update_articles.py — pull Mashrur Kabir's latest posts from their RSS feeds,
accumulate them in a permanent JSON ledger, and inject them into writing.html
between marker comments.

Standard library only (no pip install). Runs in CI from
.github/workflows/update-articles.yml, and is safe to run locally:

    python scripts/update_articles.py

Design notes
------------
* RSS feeds are windows, not archives — most platforms serve only the newest
  10–20 items, so anything older would silently fall off the site if the page
  mirrored the feed directly. Instead, every item ever seen is stored in
  data/articles.json (the "ledger"). Feeds are only the diff source: new items
  are appended, existing items are refreshed (title/summary/date), and nothing
  is ever deleted by the script. To remove an article from the site, delete it
  from the ledger — and make sure it is gone from the live feed too, or the
  next run will re-add it.
* writing.html shows the newest MAX_ITEMS per source, plus a compact "Archive"
  section (all sources merged, newest first) for everything older. The archive
  renders only once something actually ages out of a featured list, so the
  page looks unchanged until then.
* The script owns only the regions between the ARTICLES markers in
  writing.html. Everything else on the page is hand-written and left alone.
* If a feed fails to fetch/parse, that source is re-rendered from the ledger
  (identical output → no commit). Only a total failure of every feed aborts
  the run non-zero, and neither file is written on an aborted run.
* Substack has no posts yet: while its ledger is empty, the "coming soon"
  panel is rendered, and it flips to a real list automatically the first time
  a post exists — no code change needed.
"""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "writing.html"
LEDGER = ROOT / "data" / "articles.json"

MAX_ITEMS = 6          # newest N posts featured per source; older ones → Archive
MIN_DESC = 60          # a <description> shorter than this is treated as a mere
                       # subtitle, and we fall back to the article body prose
STORE_SUMMARY = 300    # summaries are clipped to this length before storage
TIMEOUT = 20           # seconds per feed request

CONTENT_ENC = "{http://purl.org/rss/1.0/modules/content/}encoded"
UA = "Mozilla/5.0 (compatible; mashrurkabir-site/1.0; +https://mashrurkabir.com)"

SUBSTACK_URL = "https://mashrurk.substack.com"

SOURCES = {
    "proxima": {
        "url": "https://proximareport.com/author/mashrur/feed",
        "label": "Proxima Report",
        "badge_class": "badge badge--proxima",
        "cta": "Read on Proxima Report",
    },
    "substack": {
        "url": "https://mashrurk.substack.com/feed",
        "label": "Substack",
        "badge_class": "badge",
        "cta": "Read on Substack",
    },
}

INDENT = "          "        # 10 spaces — entry markup inside a writing-section
SECTION_INDENT = "        "  # 8 spaces — the generated Archive section itself


# --------------------------------------------------------------------------
# Fetch + parse
# --------------------------------------------------------------------------
def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def parse_feed(raw: bytes) -> list[dict]:
    root = ET.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        return []

    items: list[dict] = []
    for it in channel.findall("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not title or not link:
            continue

        dt = None
        raw_date = (it.findtext("pubDate") or "").strip()
        if raw_date:
            try:
                dt = parsedate_to_datetime(raw_date)
            except (TypeError, ValueError):
                dt = None

        # <description> is often just a short subtitle; when it is, fall back to
        # the opening prose of the full article body (content:encoded).
        desc = strip_html(it.findtext("description") or "")
        summary = desc
        if len(desc) < MIN_DESC:
            body = strip_html(it.findtext(CONTENT_ENC) or "")
            summary = body or desc

        items.append(
            {
                "title": title,
                "link": link,
                "date": dt,
                "summary": truncate(summary, STORE_SUMMARY),
            }
        )
    return items


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    """Flatten an HTML snippet down to a single clean line of plain text."""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def truncate(text: str, n: int = 180) -> str:
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0].rstrip(",.;:—- ") + "…"


def fmt_date(dt: datetime | None) -> tuple[str | None, str | None]:
    if dt is None:
        return None, None
    return dt.strftime("%Y-%m"), dt.strftime("%b %Y")


def esc(s: str) -> str:
    return html.escape(s, quote=True)


# --------------------------------------------------------------------------
# Ledger — data/articles.json, the permanent record of everything ever seen
# --------------------------------------------------------------------------
def load_ledger() -> dict:
    if not LEDGER.exists():
        return {"version": 1, "sources": {}}
    try:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        # Never silently replace a corrupt ledger — that would wipe the archive.
        raise SystemExit(f"{LEDGER} is not valid JSON ({e}); fix it or restore it from git")
    data.setdefault("sources", {})
    return data


def save_ledger(ledger: dict) -> None:
    text = json.dumps(ledger, ensure_ascii=False, indent=2) + "\n"
    if LEDGER.exists() and LEDGER.read_text(encoding="utf-8") == text:
        return
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(text, encoding="utf-8", newline="\n")


def norm_link(link: str) -> str:
    """Dedupe key — tolerate a trailing-slash difference, nothing fancier."""
    return link.strip().rstrip("/")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def sort_key(entry: dict) -> datetime:
    """Newest-first ordering: publish date, else when we first saw the item."""
    dt = parse_iso(entry.get("date")) or parse_iso(entry.get("first_seen"))
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def merge_into_ledger(stored: list[dict], fetched: list[dict]) -> tuple[list[dict], int]:
    """Append new feed items, refresh known ones in place, delete nothing."""
    by_link = {norm_link(e["link"]): e for e in stored}
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    added = 0

    for item in fetched:
        key = norm_link(item["link"])
        iso_date = item["date"].isoformat() if item["date"] else None
        entry = by_link.get(key)
        if entry is None:
            by_link[key] = {
                "title": item["title"],
                "link": item["link"],
                "date": iso_date,
                "summary": item["summary"],
                "first_seen": now_iso,
            }
            added += 1
        else:
            # The live feed stays authoritative for content; the ledger for existence.
            entry["title"] = item["title"]
            entry["summary"] = item["summary"]
            if iso_date:
                entry["date"] = iso_date

    merged = sorted(by_link.values(), key=sort_key, reverse=True)
    return merged, added


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------
def render_entry(entry: dict, src: dict, delay: str) -> str:
    machine, human = fmt_date(parse_iso(entry.get("date")))
    url = esc(entry["link"])
    delay_attr = f' data-delay="{delay}"' if delay else ""

    lines = [
        f'{INDENT}<article class="entry reveal"{delay_attr}>',
        f"{INDENT}  <div class=\"entry-meta\">",
        f'{INDENT}    <span class="{src["badge_class"]}">{esc(src["label"])}</span>',
    ]
    if machine:
        lines.append(f'{INDENT}    <time datetime="{machine}">{human}</time>')
    lines += [
        f"{INDENT}  </div>",
        f"{INDENT}  <div>",
        f'{INDENT}    <h3><a href="{url}" target="_blank" rel="noopener">{esc(entry["title"])}</a></h3>',
    ]
    summary = truncate(entry.get("summary", ""))
    if summary:
        lines.append(f'{INDENT}    <p class="entry-summary">{esc(summary)}</p>')
    lines += [
        f'{INDENT}    <a class="text-link" href="{url}" target="_blank" rel="noopener">'
        f'{esc(src["cta"])} <span aria-hidden="true">&rarr;</span></a>',
        f"{INDENT}  </div>",
        f"{INDENT}</article>",
    ]
    return "\n".join(lines)


def render_entries(entries: list[dict], src: dict) -> str:
    blocks = []
    for i, entry in enumerate(entries[:MAX_ITEMS]):
        delay = "" if i == 0 else str(min(i, 3))  # stagger, matching the site
        blocks.append(render_entry(entry, src, delay))
    return "\n\n".join(blocks)


def substack_coming_soon() -> str:
    return "\n".join(
        [
            f'{INDENT}<div class="coming-soon reveal">',
            f'{INDENT}  <span class="card-status">In the hangar</span>',
            f"{INDENT}  <p>Independent essays are on the way — longer-leash thinking on "
            f"propulsion, autonomy, and the verification frontier. The first post lands "
            f"when it&rsquo;s ready, not before.</p>",
            f'{INDENT}  <a class="text-link" href="{SUBSTACK_URL}" target="_blank" '
            f'rel="noopener">Subscribe <span aria-hidden="true">&rarr;</span></a>',
            f"{INDENT}</div>",
        ]
    )


def render_archive(ledger: dict) -> str:
    """Compact rows for everything older than the featured windows, merged."""
    older: list[tuple[dict, dict]] = []
    for key, src in SOURCES.items():
        entries = ledger["sources"].get(key, [])
        older += [(entry, src) for entry in entries[MAX_ITEMS:]]
    older.sort(key=lambda pair: sort_key(pair[0]), reverse=True)

    if not older:
        return (
            f"{SECTION_INDENT}<!-- The Archive section appears here automatically "
            f"once pieces age out of the featured lists above. -->"
        )

    n = len(older)
    count = f"{n} older piece" + ("" if n == 1 else "s")
    ind = SECTION_INDENT
    lines = [
        f'{ind}<section class="writing-section reveal" aria-labelledby="archive-title">',
        f'{ind}  <div class="writing-section-head">',
        f"{ind}    <h2 id=\"archive-title\">Archive</h2>",
        f'{ind}    <span class="count">{esc(count)}</span>',
        f"{ind}  </div>",
        f'{ind}  <ol class="archive-list">',
    ]
    for entry, src in older:
        machine, human = fmt_date(parse_iso(entry.get("date")))
        url = esc(entry["link"])
        date_cell = (
            f'<time datetime="{machine}">{human}</time>'
            if machine
            else '<span class="archive-undated" aria-hidden="true">&mdash;</span>'
        )
        lines += [
            f"{ind}    <li>",
            f'{ind}      <a href="{url}" target="_blank" rel="noopener">',
            f"{ind}        {date_cell}",
            f'{ind}        <span class="archive-title">{esc(entry["title"])}</span>',
            f'{ind}        <span class="archive-source">{esc(src["label"])}</span>',
            f"{ind}      </a>",
            f"{ind}    </li>",
        ]
    lines += [f"{ind}  </ol>", f"{ind}</section>"]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Inject into writing.html
# --------------------------------------------------------------------------
def replace_block(content: str, key: str, inner: str) -> str:
    """Replace the multi-line region between block markers, preserving indent."""
    start = f"<!-- ARTICLES:{key}:start -->"
    end = f"<!-- ARTICLES:{key}:end -->"
    si, ei = content.find(start), content.find(end)
    if si == -1 or ei == -1:
        raise SystemExit(f"Block markers for '{key}' not found in {TARGET.name}")
    si_end = si + len(start)
    indent = content[content.rfind("\n", 0, ei) + 1 : ei]  # indent before end marker
    return content[:si_end] + f"\n{inner}\n{indent}" + content[ei:]


def replace_inline(content: str, key: str, text: str) -> str:
    """Replace a short inline region between markers (e.g. the section count)."""
    start = f"<!-- ARTICLES:{key}:start -->"
    end = f"<!-- ARTICLES:{key}:end -->"
    si, ei = content.find(start), content.find(end)
    if si == -1 or ei == -1:
        raise SystemExit(f"Inline markers for '{key}' not found in {TARGET.name}")
    return content[: si + len(start)] + esc(text) + content[ei:]


def main() -> None:
    ledger = load_ledger()
    sources_data = ledger["sources"]
    content = original = TARGET.read_text(encoding="utf-8")
    any_success = False

    for key, src in SOURCES.items():
        try:
            fetched = parse_feed(fetch(src["url"]))
        except Exception as e:  # noqa: BLE001 — any failure: fall back to the ledger
            print(f"[warn] {key}: fetch/parse failed ({e}); rendering from the ledger",
                  file=sys.stderr)
        else:
            any_success = True
            merged, added = merge_into_ledger(sources_data.get(key, []), fetched)
            sources_data[key] = merged
            print(f"[ok] {key}: feed has {len(fetched)} item(s), {added} new; "
                  f"ledger holds {len(merged)}")

        stored = sources_data.get(key, [])
        if key == "substack":
            content = replace_inline(
                content, "substack-count", "Latest essays" if stored else "Coming soon"
            )
            inner = render_entries(stored, src) if stored else substack_coming_soon()
        else:
            if not stored:
                print(f"[warn] {key}: nothing in feed or ledger; leaving existing content",
                      file=sys.stderr)
                continue
            inner = render_entries(stored, src)
        content = replace_block(content, key, inner)

    content = replace_block(content, "archive", render_archive(ledger))

    if not any_success:
        raise SystemExit("All feeds failed to fetch; aborting without changes")

    save_ledger(ledger)
    if content != original:
        TARGET.write_text(content, encoding="utf-8", newline="\n")
        print("writing.html updated")
    else:
        print("no changes")


if __name__ == "__main__":
    main()
