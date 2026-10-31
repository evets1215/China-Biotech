"""Pull new deals from BioPharma Dive's public China-licensing tracker.

BioPharma Dive ("Drugs from China are reshaping biotech. Track the licensing
deals here.") publishes its deal table as a Datawrapper chart. Datawrapper
exposes the underlying data at ``https://datawrapper.dwcdn.net/<chart>/<ver>/dataset.csv``.

``sync`` only *adds* deals it has not seen (matched on licensor + licensee +
date within a few days). It never overwrites fields you have curated by hand;
it only fills fields that are blank.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
import urllib.request

from tracker.store import Database, norm_name, today

CHART_ID = "ZTFPS"
CHART_BASE = f"https://datawrapper.dwcdn.net/{CHART_ID}/"
ARTICLE_URL = "https://www.biopharmadive.com/news/china-biotech-drug-licensing-deals-pipeline/758283/"
SOURCE_LABEL = "BioPharma Dive China licensing tracker"
USER_AGENT = "china-biotech-deal-tracker/1.0 (+https://github.com/evets1215/China-Biotech)"

AREA_MAP = {
    "cancer": "Cancer",
    "immune diseases": "Immune diseases",
    "metabolic diseases": "Metabolic diseases",
    "cns disorders": "CNS disorders",
    "multiple": "Multiple",
    "other": "Other",
    "undisclosed": "Undisclosed",
}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (fixed https host)
        return resp.read().decode("utf-8-sig")


def latest_dataset_url() -> str:
    """The chart root redirects (via meta refresh) to the latest published version."""
    html = _get(CHART_BASE)
    m = re.search(rf"{CHART_ID}/(\d+)/", html)
    if not m:
        raise RuntimeError("Could not find the latest Datawrapper version for the BioPharma Dive tracker")
    return f"{CHART_BASE}{m.group(1)}/dataset.csv"


def _money(v: str) -> float | None:
    v = (v or "").strip().replace(",", "").replace("$", "")
    if not v or v.upper() in {"N/A", "NA", "UNDISCLOSED", "-"}:
        return None
    try:
        f = float(v)
    except ValueError:
        return None
    return int(f) if f.is_integer() else round(f, 2)


def _date(v: str) -> str | None:
    v = (v or "").strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _area(v: str) -> str:
    parts = [p.strip().lower() for p in (v or "").split(",") if p.strip()]
    if len(parts) > 1:
        return "Multiple"
    return AREA_MAP.get(parts[0], "Other") if parts else "Undisclosed"


def _modality(v: str) -> str | None:
    v = (v or "").strip()
    return None if not v or v.lower() == "undisclosed" else v


def parse_rows(text: str) -> list[dict]:
    """Convert the Datawrapper CSV into tracker deal records (without ids)."""
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        get = lambda *keys: next((r[k] for k in r if k and any(k.lower().startswith(x) for x in keys)), "")  # noqa: E731
        announced = _date(get("date of deal"))
        licensor = get("licensor").strip()
        licensee = get("licensee").strip()
        if not (announced and licensor and licensee):
            continue
        equity_raw = get("upfront equity").strip()
        phase = get("phase of development").strip()
        rec = {
            "announced": announced,
            "licensor": licensor,
            "licensee": licensee,
            "deal_type": "License",
            "target": get("treatment type").strip() or None,
            "modality": _modality(get("modality")),
            "therapeutic_area": _area(get("therapeutic area")),
            "phase_at_deal": None if phase.lower() in ("", "undisclosed") else phase,
            "upfront_usd_m": _money(get("upfront value")),
            "total_value_usd_m": _money(get("total deal value")),
            "status": "active",
            "sources": [u for u in [get("link to coverage").strip(), ARTICLE_URL] if u],
            "data_source": SOURCE_LABEL,
            "last_verified": today(),
        }
        if equity_raw:
            eq = _money(equity_raw)
            if eq is not None and "%" not in equity_raw:
                rec["equity_usd_m"] = eq
            else:
                rec["notes"] = f"Equity component: {equity_raw}"
        rows.append(rec)
    return rows


def _same_deal(a: dict, b: dict, days: int = 5) -> bool:
    if norm_name(a["licensee"]) != norm_name(b.get("licensee", "")):
        return False
    la, lb = norm_name(a["licensor"]), norm_name(b.get("licensor", ""))
    if not (la and lb and (la in lb or lb in la)):
        return False
    try:
        da = dt.date.fromisoformat(a["announced"])
        db_ = dt.date.fromisoformat(str(b.get("announced"))[:10])
    except ValueError:
        return str(a["announced"])[:7] == str(b.get("announced"))[:7]
    return abs((da - db_).days) <= days


def merge(db: Database, incoming: list[dict]) -> tuple[list[dict], list[dict]]:
    """Merge parsed rows into ``db``. Returns (added, enriched) lists."""
    added, enriched = [], []
    for rec in incoming:
        match = next((d for d in db.deals if _same_deal(rec, d)), None)
        if match:
            filled = False
            for k, v in rec.items():
                if k in ("status", "last_verified", "data_source", "sources", "notes", "deal_type"):
                    continue
                if v not in (None, "", []) and match.get(k) in (None, "", []):
                    match[k] = v
                    filled = True
            if filled:
                enriched.append(match)
            continue
        rec["id"] = db.next_deal_id(rec["announced"])
        rec["licensor_hq"] = db.company_hq(rec["licensor"]) or "China"
        hq = db.company_hq(rec["licensee"])
        if hq:
            rec["licensee_hq"] = hq
        ctype = db.company_type(rec["licensee"])
        if ctype:
            rec["licensee_type"] = ctype
        db.deals.append(rec)
        added.append(rec)
    return added, enriched


def sync(db: Database, csv_text: str | None = None) -> tuple[list[dict], list[dict]]:
    text = csv_text if csv_text is not None else _get(latest_dataset_url())
    return merge(db, parse_rows(text))
