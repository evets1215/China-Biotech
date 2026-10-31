"""Aggregations shared by the CLI and the dashboard."""

from __future__ import annotations

from collections import Counter, defaultdict

from tracker.store import Database, today, year_of


def _sum(values) -> float:
    return round(sum(v for v in values if isinstance(v, (int, float))), 1)


def summary(db: Database) -> dict:
    deals = db.deals
    by_status = Counter(d.get("status") for d in deals)
    return {
        "deals": len(deals),
        "by_status": dict(by_status),
        "upfront_usd_m": _sum(d.get("upfront_usd_m") for d in deals),
        "total_value_usd_m": _sum(d.get("total_value_usd_m") for d in deals),
        "licensors": len({d["licensor"] for d in deals}),
        "licensees": len({d["licensee"] for d in deals}),
        "potential": sum(1 for p in db.pipeline if p.get("stage") == "potential"),
        "future": sum(1 for p in db.pipeline if p.get("stage") == "future"),
        "options_open": sum(1 for d in deals if d.get("deal_type") == "Option" and d.get("status") == "active"),
    }


def by_year(db: Database) -> list[dict]:
    rows: dict[int, dict] = defaultdict(lambda: {"deals": 0, "upfront_usd_m": 0.0, "total_value_usd_m": 0.0, "terminated": 0})
    for d in db.deals:
        y = year_of(d)
        if y is None:
            continue
        r = rows[y]
        r["deals"] += 1
        r["upfront_usd_m"] += d.get("upfront_usd_m") or 0
        r["total_value_usd_m"] += d.get("total_value_usd_m") or 0
        r["terminated"] += d.get("status") == "terminated"
    return [{"year": y, **{k: round(v, 1) if isinstance(v, float) else v for k, v in rows[y].items()}} for y in sorted(rows)]


def group(db: Database, field: str, top: int | None = None) -> list[dict]:
    rows: dict[str, dict] = defaultdict(lambda: {"deals": 0, "upfront_usd_m": 0.0, "total_value_usd_m": 0.0})
    for d in db.deals:
        key = d.get(field) or "Undisclosed"
        r = rows[key]
        r["deals"] += 1
        r["upfront_usd_m"] += d.get("upfront_usd_m") or 0
        r["total_value_usd_m"] += d.get("total_value_usd_m") or 0
    out = [{field: k, **{kk: round(vv, 1) if isinstance(vv, float) else vv for kk, vv in v.items()}} for k, v in rows.items()]
    out.sort(key=lambda r: (-r["deals"], -r["upfront_usd_m"]))
    return out[:top] if top else out


def upcoming_catalysts(db: Database, days: int | None = None) -> list[dict]:
    """Catalysts dated today or later, from both deals and pipeline items."""
    import datetime as dt

    start = today()
    end = (dt.date.today() + dt.timedelta(days=days)).isoformat() if days else "9999"
    out = []
    for d in db.deals:
        for c in d.get("catalysts") or []:
            if start <= str(c["date"]) <= end:
                out.append({"date": str(c["date"]), "event": c["event"], "id": d["id"],
                            "label": f"{d['licensor']} -> {d['licensee']}", "asset": d.get("asset") or d.get("target", "")})
    for p in db.pipeline:
        for c in p.get("catalysts") or []:
            if start <= str(c["date"]) <= end:
                out.append({"date": str(c["date"]), "event": c["event"], "id": p["id"],
                            "label": f"{p['company']} ({p['stage']})", "asset": p.get("asset", "")})
    return sorted(out, key=lambda r: r["date"])
