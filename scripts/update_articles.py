#!/usr/bin/env python3
"""
update_articles.py — pull Mashrur Kabir's latest posts from their RSS feeds and
inject them into writing.html, between marker comments.

Standard library only (no pip install). Runs in CI from
.github/workflows/update-articles.yml, and is safe to run locally:

    python scripts/update_articles.py

Design notes
------------
* The script owns only the regions between the ARTICLES markers in writing.html.
  Everything else on the page is hand-written and left untouched.
* If a feed fails to fetch/parse, that source's region is left as-is (we never
  blank good content on a transient network blip). Only a total failure of every
  feed aborts the run non-zero.
* Substack has no posts yet: when a feed returns zero items, the "coming soon"
  panel is rendered instead, and it flips to a real list automatically the first
  time a post exists — no code change needed.
"""

from __future__ import annotations

import html
import re
import sys
import urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "writing.html"

MAX_ITEMS = 6          # newest N posts shown per source
MIN_DESC = 60          # a <description> shorter than this is treated as a mere
                       # subtitle, and we fall back to the article body prose
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

INDENT = "          "  # 10 spaces — matches the nesting inside writing.html


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
            {"title": title, "link": link, "date": dt, "summary": summary}
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
# Render
# --------------------------------------------------------------------------
def render_entry(item: dict, src: dict, delay: str) -> str:
    machine, human = fmt_date(item["date"])
    url = esc(item["link"])
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
        f'{INDENT}    <h3><a href="{url}" target="_blank" rel="noopener">{esc(item["title"])}</a></h3>',
    ]
    summary = truncate(item["summary"])
    if summary:
        lines.append(f'{INDENT}    <p class="entry-summary">{esc(summary)}</p>')
    lines += [
        f'{INDENT}    <a class="text-link" href="{url}" target="_blank" rel="noopener">'
        f'{esc(src["cta"])} <span aria-hidden="true">&rarr;</span></a>',
        f"{INDENT}  </div>",
        f"{INDENT}</article>",
    ]
    return "\n".join(lines)


def render_entries(items: list[dict], src: dict) -> str:
    blocks = []
    for i, item in enumerate(items[:MAX_ITEMS]):
        delay = "" if i == 0 else str(min(i, 3))  # stagger, matching the site
        blocks.append(render_entry(item, src, delay))
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
    content = original = TARGET.read_text(encoding="utf-8")
    any_success = False

    for key, src in SOURCES.items():
        try:
            items = parse_feed(fetch(src["url"]))
        except Exception as e:  # noqa: BLE001 — any failure: keep existing content
            print(f"[warn] {key}: fetch/parse failed ({e}); leaving existing content",
                  file=sys.stderr)
            continue
        any_success = True

        if key == "substack":
            content = replace_inline(
                content, "substack-count", "Latest essays" if items else "Coming soon"
            )
            inner = render_entries(items, src) if items else substack_coming_soon()
        else:
            if not items:
                print(f"[warn] {key}: no items parsed; leaving existing content",
                      file=sys.stderr)
                continue
            inner = render_entries(items, src)

        content = replace_block(content, key, inner)
        print(f"[ok] {key}: {len(items)} item(s)")

    if not any_success:
        raise SystemExit("All feeds failed to fetch; aborting without changes")

    if content != original:
        TARGET.write_text(content, encoding="utf-8")
        print("writing.html updated")
    else:
        print("no changes")


if __name__ == "__main__":
    main()
