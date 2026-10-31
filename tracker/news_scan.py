"""Scan public news feeds for new / rumoured China out-licensing deals.

Writes ``data/inbox.md``: a review queue of headlines that look like
China -> US/EU licensing activity and are *not* already in ``deals.yaml``.
A human (or Claude) reviews the inbox and then runs ``tracker add`` /
``tracker pipeline-add`` for the real ones. Nothing is added automatically
because headlines are noisy and deal terms need checking against the
press release.
"""

from __future__ import annotations

import datetime as dt
import email.utils
import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from tracker.store import Database, norm_name

USER_AGENT = "Mozilla/5.0 (compatible; china-biotech-deal-tracker/1.0)"

GOOGLE_NEWS_QUERIES = [
    "China biotech licensing deal upfront",
    "Chinese drugmaker license global rights",
    "Hengrui OR Hansoh OR Innovent OR CSPC OR Akeso license deal",
    "China biotech NewCo ex-China rights",
    "Chinese biotech in talks license drug",
]
DIRECT_FEEDS = [
    "https://www.biopharmadive.com/feeds/news/",
    "https://www.fiercebiotech.com/rss/xml",
    "https://endpts.com/feed/",
    "https://www.statnews.com/feed/",
]

DEAL_WORDS = re.compile(
    r"\b(licen[cs]e[sd]?|licensing|rights|upfront|up-front|option|collaboration|partnership|"
    r"newco|acquir\w*|buyout|deal|pact|milestones?)\b",
    re.I,
)
CHINA_WORDS = re.compile(r"\b(china|chinese|hong kong|shanghai|beijing|suzhou|hangzhou|jiangsu)\b", re.I)
RUMOUR_WORDS = re.compile(r"\b(in talks|talks|nears?|considering|explor\w+|weighs?|bid|sources say|people familiar)\b", re.I)
TERMINATION_WORDS = re.compile(r"\b(terminat\w+|returns? rights|hands? back|ends? (?:pact|deal|partnership)|drops?)\b", re.I)


def google_news_url(query: str) -> str:
    q = urllib.parse.quote_plus(f"{query} when:14d")
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def fetch(url: str, timeout: int = 30) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # network errors are expected for some feeds
        print(f"  ! skipped {url[:80]}: {exc}")
        return None


def parse_feed(xml_text: str) -> list[dict]:
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    for it in root.iter("item"):
        title = html.unescape((it.findtext("title") or "").strip())
        link = (it.findtext("link") or "").strip()
        pub = it.findtext("pubDate") or ""
        try:
            date = email.utils.parsedate_to_datetime(pub).date().isoformat()
        except (TypeError, ValueError):
            date = ""
        desc = re.sub(r"<[^>]+>", " ", html.unescape(it.findtext("description") or ""))
        items.append({"title": title, "link": link, "date": date, "summary": desc.strip()[:300]})
    return items


def china_names(db: Database) -> set[str]:
    names = {d["licensor"] for d in db.deals if d.get("licensor")}
    names |= {p["company"] for p in db.pipeline if p.get("company")}
    names |= {n for n, info in db.companies.items() if isinstance(info, dict) and info.get("hq") in ("China", "Hong Kong")}
    return names


def classify(item: dict, db: Database, cn_names: set[str]) -> dict | None:
    text = f"{item['title']} {item['summary']}"
    named = sorted(n for n in cn_names if len(n) > 3 and re.search(rf"\b{re.escape(n.split(' (')[0])}\b", text, re.I))
    if not DEAL_WORDS.search(text):
        return None
    if not (CHINA_WORDS.search(text) or named):
        return None
    tags = []
    if TERMINATION_WORDS.search(text):
        tags.append("possible termination")
    if RUMOUR_WORDS.search(item["title"]):
        tags.append("potential/rumour")
    if re.search(r"\$\s?\d", text):
        tags.append("has $ terms")
    # Does it look like a deal we already track?
    known = None
    tl = norm_name(text)
    for d in db.deals:
        a, b = norm_name(d.get("licensor", "")), norm_name(d.get("licensee", ""))
        if a and b and a in tl and b in tl:
            known = d["id"]
            break
    return {**item, "tags": tags, "companies": named, "known_deal": known}


def scan(db: Database, extra_feeds: list[str] | None = None) -> list[dict]:
    urls = [google_news_url(q) for q in GOOGLE_NEWS_QUERIES] + DIRECT_FEEDS + (extra_feeds or [])
    cn = china_names(db)
    seen, hits = set(), []
    for url in urls:
        text = fetch(url)
        if not text:
            continue
        for item in parse_feed(text):
            key = re.sub(r"\W+", "", item["title"].lower())[:90]
            if key in seen:
                continue
            seen.add(key)
            hit = classify(item, db, cn)
            if hit:
                hits.append(hit)
    hits.sort(key=lambda h: h["date"], reverse=True)
    return hits


def render_inbox(hits: list[dict]) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    new = [h for h in hits if not h["known_deal"]]
    known = [h for h in hits if h["known_deal"]]
    lines = [
        "# Deal inbox (auto-generated)",
        "",
        f"_Last scan: {now}. Headlines that look like China out-licensing activity._",
        "",
        "Review each item. For a real signed deal run `python -m tracker add ...`; for talks/rumours run",
        "`python -m tracker pipeline-add --stage potential ...`; for a termination run",
        "`python -m tracker update <id> --status terminated ...`. This file is overwritten on every scan.",
        "",
        f"## Possibly new ({len(new)})",
        "",
        "| Date | Headline | Tags | Companies recognised |",
        "|---|---|---|---|",
    ]
    for h in new:
        title = h["title"].replace("|", "\\|")
        lines.append(f"| {h['date']} | [{title}]({h['link']}) | {', '.join(h['tags'])} | {', '.join(h['companies'][:4])} |")
    lines += ["", f"## Already tracked ({len(known)})", "", "| Date | Headline | Deal id | Tags |", "|---|---|---|---|"]
    for h in known:
        title = h["title"].replace("|", "\\|")
        lines.append(f"| {h['date']} | [{title}]({h['link']}) | {h['known_deal']} | {', '.join(h['tags'])} |")
    return "\n".join(lines) + "\n"
