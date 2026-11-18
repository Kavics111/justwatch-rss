#!/usr/bin/env python3
"""
JustWatch -> RSS generator.

Lekérdezi a JustWatch belső GraphQL API-ját (ugyanazt, amit a
www.justwatch.com/hu/uj oldal használ), és egy RSS 2.0 feedet ír ki a
streamingre frissen felkerült filmekből/sorozatokból.

Csak a Python standard library kell hozzá (urllib) -- nincs pip install.

Használat:
    python generate_feed.py --out _site/rss.xml
    python generate_feed.py --out _site/rss.xml --self-url https://felhasznalo.github.io/repo/rss.xml

Teszt (offline), elmentett API-válaszból:
    python generate_feed.py --mock-file sample.json --out rss.xml
"""

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

# ---------------------------------------------------------------------------
# Beállítások -- ezeket szabadon módosíthatod
# ---------------------------------------------------------------------------
COUNTRY = "HU"          # országkód
LANGUAGE = "hu"         # nyelv
MAX_ITEMS = 80          # hány tétel kerüljön a feedbe (API max ~600)
POSTER_PROFILE = "s332" # poszter méret (s166, s332, s592 ...)
PAGE_SIZE = 100         # tétel/lapkérés -- az API ~100 felett "page too large" hibát ad
MAX_PAGES = 6           # max hány lapot kérjen le (6*100 = a teljes ~600-as lista)

# Ha csak bizonyos szolgáltatók újdonságai érdekelnek, írd ide a neveket
# (pontosan, ahogy a JustWatch adja, pl. "Netflix", "Max", "Disney Plus").
# Üres halmaz = minden szolgáltató.
PROVIDER_ALLOWLIST = set()
# Példa:
# PROVIDER_ALLOWLIST = {"Netflix", "Max", "Disney Plus", "Amazon Prime Video"}

ENDPOINT = "https://apis.justwatch.com/graphql"
SITE = "https://www.justwatch.com"
IMG_BASE = "https://images.justwatch.com"
SOURCE_PAGE = f"{SITE}/{COUNTRY.lower()}/uj"
USER_AGENT = (
    "Mozilla/5.0 (JustWatch-RSS; +https://github.com) "
    "AppleWebKit/537.36 Chrome/120 Safari/537.36"
)

QUERY = """
query GetNewTitles($country: Country!, $language: Language!, $first: Int!, $after: String) {
  newTitles(country: $country, first: $first, after: $after) {
    pageInfo { endCursor hasNextPage }
    edges {
      node {
        __typename
        id
        objectType
        content(country: $country, language: $language) {
          title
          fullPath
          shortDescription
          originalReleaseYear
          posterUrl
          genres { shortName }
        }
        ... on Season {
          show {
            content(country: $country, language: $language) { title fullPath }
          }
        }
        offers(country: $country, platform: WEB) {
          monetizationType
          newElementCount
          package { clearName }
        }
      }
    }
  }
}
"""


def _fetch_page(first, after):
    body = json.dumps(
        {"query": QUERY,
         "variables": {"country": COUNTRY, "language": LANGUAGE,
                       "first": first, "after": after}}
    ).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL hiba: {payload['errors']}")
    return payload["data"]["newTitles"]


def fetch_new_titles(target):
    """Lapozva kéri le a tételeket, amíg össze nem gyűlik `target` darab
    (vagy elfogy a lista / elértük a MAX_PAGES-t)."""
    edges = []
    after = None
    for _ in range(MAX_PAGES):
        nt = _fetch_page(PAGE_SIZE, after)
        edges.extend(nt.get("edges") or [])
        info = nt.get("pageInfo") or {}
        after = info.get("endCursor")
        if len(edges) >= target or not info.get("hasNextPage") or not after:
            break
    return edges


def poster_url(template):
    if not template:
        return None
    return IMG_BASE + template.replace("{profile}", POSTER_PROFILE).replace("{format}", "jpg")


def providers_of(node):
    """Szolgáltatók az ajánlatokból, duplikátumok nélkül, max új-rész-számmal."""
    seen = {}
    for off in node.get("offers") or []:
        pkg = (off.get("package") or {}).get("clearName")
        if not pkg:
            continue
        n = off.get("newElementCount") or 0
        seen[pkg] = max(seen.get(pkg, 0), n)
    return seen  # {name: newElementCount}


def build_item(node):
    content = node.get("content") or {}
    title = content.get("title") or ""
    if not title:
        return None

    otype = node.get("objectType")
    display = title
    link_path = content.get("fullPath")

    # Évad esetén a sorozat neve + az évad címe ("A show neve – Évad 3")
    if otype == "SHOW_SEASON":
        show = (node.get("show") or {}).get("content") or {}
        show_title = show.get("title")
        if show_title:
            display = f"{show_title} – {title}"

    year = content.get("originalReleaseYear")
    if year and otype == "MOVIE":
        display = f"{display} ({year})"

    provs = providers_of(node)
    if PROVIDER_ALLOWLIST and not (set(provs) & PROVIDER_ALLOWLIST):
        return None

    prov_names = list(provs.keys())
    headline = display
    if prov_names:
        headline = f"{display} — {', '.join(prov_names[:3])}"

    link = (SITE + link_path) if link_path else SOURCE_PAGE
    guid = node.get("id") or link

    # Leírás (HTML, CDATA-ban)
    parts = []
    poster = poster_url(content.get("posterUrl"))
    if poster:
        parts.append(
            f'<img src="{escape(poster)}" alt="{escape(display)}" '
            f'style="max-width:200px;float:right;margin:0 0 8px 12px;border-radius:6px" />'
        )
    desc = content.get("shortDescription")
    if desc:
        parts.append(f"<p>{escape(desc)}</p>")
    if provs:
        prov_line = ", ".join(
            f"{escape(name)}" + (f" ({cnt} új rész)" if cnt else "")
            for name, cnt in provs.items()
        )
        parts.append(f"<p><strong>Új itt:</strong> {prov_line}</p>")
    genres = [g.get("shortName") for g in (content.get("genres") or []) if g.get("shortName")]
    if genres:
        parts.append(f"<p><em>Műfaj:</em> {escape(', '.join(genres))}</p>")
    description_html = "\n".join(parts) if parts else display

    return {
        "title": headline,
        "link": link,
        "guid": guid,
        "description_html": description_html,
        "category": otype or "",
    }


def build_rss(edges, self_url=None):
    now = datetime.now(timezone.utc)
    items = []
    for edge in edges:
        node = edge.get("node") or {}
        item = build_item(node)
        if item:
            items.append(item)
        if len(items) >= MAX_ITEMS:
            break

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">')
    lines.append("<channel>")
    lines.append("<title>JustWatch – Új a streamingen (HU)</title>")
    lines.append(f"<link>{escape(SOURCE_PAGE)}</link>")
    lines.append(
        "<description>Frissen a magyar streaming-kínálatba került "
        "filmek és sorozatok a JustWatch alapján.</description>"
    )
    lines.append("<language>hu</language>")
    lines.append(f"<lastBuildDate>{format_datetime(now)}</lastBuildDate>")
    lines.append("<generator>justwatch-rss</generator>")
    if self_url:
        lines.append(
            f'<atom:link href="{escape(self_url)}" rel="self" type="application/rss+xml" />'
        )
    for it in items:
        lines.append("<item>")
        lines.append(f"<title>{escape(it['title'])}</title>")
        lines.append(f"<link>{escape(it['link'])}</link>")
        lines.append(f'<guid isPermaLink="false">{escape(it["guid"])}</guid>')
        if it["category"]:
            lines.append(f"<category>{escape(it['category'])}</category>")
        lines.append(f"<description><![CDATA[{it['description_html']}]]></description>")
        lines.append("</item>")
    lines.append("</channel>")
    lines.append("</rss>")
    return "\n".join(lines), len(items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="rss.xml", help="kimeneti RSS fájl")
    ap.add_argument("--self-url", default=None, help="a feed szétküldött URL-je (atom:link self)")
    ap.add_argument("--mock-file", default=None, help="offline teszt: elmentett API JSON-ból olvas")
    args = ap.parse_args()

    try:
        if args.mock_file:
            with open(args.mock_file, encoding="utf-8") as f:
                data = json.load(f)
            edges = data["data"]["newTitles"]["edges"]
        else:
            # Szűrés nélkül elég MAX_ITEMS tétel; allowlist esetén lapozzunk
            # végig (sok tétel kieshet a szűrőn).
            target = MAX_ITEMS * 50 if PROVIDER_ALLOWLIST else MAX_ITEMS
            edges = fetch_new_titles(target)
    except Exception as e:  # noqa: BLE001
        print(f"HIBA a lekérdezéskor: {e}", file=sys.stderr)
        return 1

    xml, n = build_rss(edges, self_url=args.self_url)

    import os
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"OK: {n} tétel → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
