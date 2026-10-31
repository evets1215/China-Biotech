"""Command-line interface:  python -m tracker <command> [options]

Run ``python -m tracker --help`` for the command list.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from tracker import stats
from tracker.store import (
    DEAL_FIELDS,
    DEAL_STATUSES,
    DEAL_TYPES,
    LIKELIHOOD,
    PIPELINE_FIELDS,
    PIPELINE_STAGES,
    ROOT,
    THERAPEUTIC_AREAS,
    Database,
    today,
    validate,
)


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def money(v) -> str:
    if v is None or v == "":
        return "n/d"
    v = float(v)
    return f"${v / 1000:,.2f}B" if v >= 1000 else f"${v:,.0f}M"


def table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [len(h) for h in headers]
    for r in rows:
        widths = [max(w, len(str(c))) for w, c in zip(widths, r)]
    line = lambda r: "  ".join(str(c).ljust(w) for c, w in zip(r, widths))  # noqa: E731
    return "\n".join([line(headers), line(["-" * w for w in widths])] + [line(r) for r in rows])


def trunc(s, n: int) -> str:
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def parse_kv(pairs: list[str] | None) -> dict:
    out = {}
    for p in pairs or []:
        if "=" not in p:
            raise SystemExit(f"--set expects field=value, got {p!r}")
        k, v = p.split("=", 1)
        k = k.strip()
        if k.endswith("_usd_m"):
            v = None if v.strip() in ("", "null", "n/d") else float(v)
            v = int(v) if isinstance(v, float) and v.is_integer() else v
        out[k] = v
    return out


def parse_event(s: str) -> dict:
    if "|" not in s:
        raise SystemExit(f"Events/catalysts use 'YYYY-MM-DD|description', got {s!r}")
    date, text = s.split("|", 1)
    return {"date": date.strip(), "event": text.strip()}


def save_checked(db: Database) -> int:
    errors = validate(db)
    if errors:
        print("Not saved - validation failed:", *errors, sep="\n  ", file=sys.stderr)
        return 1
    db.save()
    return 0


def matches(d: dict, a: argparse.Namespace) -> bool:
    if a.status and d.get("status") not in a.status:
        return False
    if a.year and not str(d.get("announced", "")).startswith(str(a.year)):
        return False
    if a.since and str(d.get("announced", "")) < a.since:
        return False
    if a.licensee and a.licensee.lower() not in d.get("licensee", "").lower():
        return False
    if a.licensor and a.licensor.lower() not in d.get("licensor", "").lower():
        return False
    if a.area and a.area.lower() not in (d.get("therapeutic_area") or "").lower():
        return False
    if a.modality and a.modality.lower() not in (d.get("modality") or "").lower():
        return False
    if a.hq and a.hq.lower() != (d.get("licensee_hq") or "").lower():
        return False
    if a.type and d.get("deal_type") != a.type:
        return False
    if a.min_upfront is not None and (d.get("upfront_usd_m") or 0) < a.min_upfront:
        return False
    if a.search:
        blob = json.dumps(d, ensure_ascii=False).lower()
        if a.search.lower() not in blob:
            return False
    return True


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_list(db: Database, a) -> int:
    rows = [d for d in db.deals if matches(d, a)]
    key = {
        "date": lambda d: str(d.get("announced", "")),
        "upfront": lambda d: d.get("upfront_usd_m") or -1,
        "total": lambda d: d.get("total_value_usd_m") or -1,
    }[a.sort]
    rows.sort(key=key, reverse=True)
    if a.limit:
        rows = rows[: a.limit]
    print(table(
        [[d["id"], d.get("announced", ""), trunc(d["licensor"], 26), trunc(d["licensee"], 22),
          trunc(d.get("asset") or d.get("target"), 30), trunc(d.get("therapeutic_area"), 14),
          money(d.get("upfront_usd_m")), money(d.get("total_value_usd_m")), d.get("status", "")] for d in rows],
        ["ID", "Announced", "Licensor (China)", "Licensee", "Asset / target", "Area", "Upfront", "Total", "Status"],
    ))
    print(f"\n{len(rows)} deal(s). Upfront disclosed: {money(sum(d.get('upfront_usd_m') or 0 for d in rows))}; "
          f"headline value: {money(sum(d.get('total_value_usd_m') or 0 for d in rows))}")
    return 0


def cmd_show(db: Database, a) -> int:
    rec = db.deal(a.id) or db.pipeline_item(a.id)
    if not rec:
        print(f"No deal or pipeline item with id {a.id}", file=sys.stderr)
        return 1
    import yaml

    print(yaml.safe_dump(rec, sort_keys=False, allow_unicode=True, width=100))
    return 0


def cmd_add(db: Database, a) -> int:
    rec = {
        "announced": a.announced,
        "licensor": a.licensor,
        "licensor_hq": a.licensor_hq or db.company_hq(a.licensor) or "China",
        "licensee": a.licensee,
        "licensee_hq": a.licensee_hq or db.company_hq(a.licensee),
        "licensee_type": a.licensee_type or db.company_type(a.licensee),
        "deal_type": a.deal_type,
        "asset": a.asset,
        "target": a.target,
        "modality": a.modality,
        "therapeutic_area": a.area,
        "indication": a.indication,
        "phase_at_deal": a.phase,
        "territory": a.territory,
        "upfront_usd_m": a.upfront,
        "equity_usd_m": a.equity,
        "milestones_usd_m": a.milestones,
        "total_value_usd_m": a.total if a.total is not None else (
            (a.upfront or 0) + (a.equity or 0) + (a.milestones or 0) if a.milestones is not None else None),
        "royalties": a.royalties,
        "status": a.status,
        "sources": a.source or [],
        "data_source": "Manual entry",
        "notes": a.notes,
        "last_verified": today(),
    }
    rec["id"] = a.id or db.next_deal_id(a.announced)
    db.deals.append(rec)
    rc = save_checked(db)
    if rc == 0:
        print(f"Added {rec['id']}: {a.licensor} -> {a.licensee} ({a.asset or a.target or 'asset n/d'})")
    return rc


def cmd_update(db: Database, a) -> int:
    rec = db.deal(a.id) or db.pipeline_item(a.id)
    if not rec:
        print(f"No deal or pipeline item with id {a.id}", file=sys.stderr)
        return 1
    is_deal = rec in db.deals
    if a.status:
        if is_deal and a.status not in DEAL_STATUSES:
            raise SystemExit(f"status must be one of {sorted(DEAL_STATUSES)}")
        old = rec.get("status")
        rec["status"] = a.status
        rec["status_date"] = a.date or today()
        if a.note:
            rec["status_note"] = a.note
        rec.setdefault("events", []).append(
            {"date": rec["status_date"], "event": f"Status {old} -> {a.status}" + (f": {a.note}" if a.note else "")})
    elif a.note:
        rec.setdefault("events", []).append({"date": a.date or today(), "event": a.note})
    for e in a.event or []:
        rec.setdefault("events", []).append(parse_event(e))
    for c in a.catalyst or []:
        rec.setdefault("catalysts", []).append(parse_event(c))
    for s in a.source or []:
        rec.setdefault("sources", []).append(s)
    rec.update(parse_kv(a.set))
    if is_deal:
        rec["last_verified"] = today()
    else:
        rec["last_reviewed"] = today()
    rc = save_checked(db)
    if rc == 0:
        print(f"Updated {a.id}")
    return rc


def cmd_pipeline(db: Database, a) -> int:
    rows = [p for p in db.pipeline if not a.stage or p.get("stage") == a.stage]
    order = {"high": 0, "medium": 1, "low": 2}
    rows.sort(key=lambda p: (p.get("stage", ""), order.get(p.get("likelihood"), 3), p.get("company", "")))
    print(table(
        [[p["id"], p.get("stage", ""), trunc(p["company"], 24), trunc(p.get("asset"), 28), trunc(p.get("target"), 22),
          p.get("phase", ""), p.get("likelihood", ""), trunc(p.get("potential_partners"), 30)] for p in rows],
        ["ID", "Stage", "Company", "Asset", "Target", "Phase", "Likelihood", "Possible partners"],
    ))
    opts = [d for d in db.deals if d.get("deal_type") == "Option" and d.get("status") == "active"]
    if opts and a.stage in (None, "potential"):
        print("\nOpen option deals (decision pending):")
        for d in opts:
            print(f"  {d['id']}  {d['licensor']} -> {d['licensee']}  {d.get('asset') or d.get('target')}")
    return 0


def cmd_pipeline_add(db: Database, a) -> int:
    rec = {
        "id": a.id or db.next_pipeline_id(a.stage),
        "stage": a.stage,
        "company": a.company,
        "company_hq": a.company_hq or db.company_hq(a.company) or "China",
        "asset": a.asset,
        "target": a.target,
        "modality": a.modality,
        "therapeutic_area": a.area,
        "indication": a.indication,
        "phase": a.phase,
        "ex_china_rights": a.rights,
        "likelihood": a.likelihood,
        "potential_partners": a.partners,
        "rationale": a.rationale,
        "signals": [{"date": a.date or today(), "note": a.signal, **({"source": a.source[0]} if a.source else {})}] if a.signal else [],
        "added": today(),
        "last_reviewed": today(),
        "sources": a.source or [],
    }
    db.pipeline.append(rec)
    rc = save_checked(db)
    if rc == 0:
        print(f"Added {rec['id']} ({a.stage}): {a.company} {a.asset}")
    return rc


def cmd_signal(db: Database, a) -> int:
    rec = db.pipeline_item(a.id)
    if not rec:
        print(f"No pipeline item {a.id}", file=sys.stderr)
        return 1
    sig = {"date": a.date or today(), "note": a.note}
    if a.source:
        sig["source"] = a.source
    rec.setdefault("signals", []).append(sig)
    if a.stage:
        rec["stage"] = a.stage
    if a.likelihood:
        rec["likelihood"] = a.likelihood
    rec["last_reviewed"] = today()
    rc = save_checked(db)
    if rc == 0:
        print(f"Logged signal on {a.id}")
    return rc


def cmd_promote(db: Database, a) -> int:
    p = db.pipeline_item(a.id)
    if not p:
        print(f"No pipeline item {a.id}", file=sys.stderr)
        return 1
    rec = {
        "announced": a.announced,
        "licensor": p["company"],
        "licensor_hq": p.get("company_hq", "China"),
        "licensee": a.licensee,
        "licensee_hq": db.company_hq(a.licensee),
        "licensee_type": db.company_type(a.licensee),
        "deal_type": a.deal_type,
        "asset": p.get("asset"),
        "target": p.get("target"),
        "modality": p.get("modality"),
        "therapeutic_area": p.get("therapeutic_area"),
        "indication": p.get("indication"),
        "phase_at_deal": p.get("phase"),
        "territory": a.territory,
        "upfront_usd_m": a.upfront,
        "total_value_usd_m": a.total,
        "status": "active",
        "events": [{"date": s["date"], "event": f"Pre-deal signal: {s['note']}"} for s in p.get("signals") or []],
        "sources": (a.source or []) + (p.get("sources") or []),
        "data_source": "Manual entry",
        "notes": f"Promoted from pipeline item {p['id']}.",
        "last_verified": today(),
    }
    rec["id"] = db.next_deal_id(a.announced)
    db.deals.append(rec)
    db.pipeline.remove(p)
    rc = save_checked(db)
    if rc == 0:
        print(f"Promoted {a.id} -> {rec['id']}")
    return rc


def cmd_stats(db: Database, a) -> int:
    s = stats.summary(db)
    print(f"Deals tracked: {s['deals']}  ({', '.join(f'{k}: {v}' for k, v in sorted(s['by_status'].items()))})")
    print(f"Disclosed upfront: {money(s['upfront_usd_m'])}   Headline value: {money(s['total_value_usd_m'])}")
    print(f"Chinese licensors: {s['licensors']}   Licensees: {s['licensees']}")
    print(f"Pipeline: {s['potential']} potential, {s['future']} future-watchlist, {s['options_open']} open options\n")
    if a.by == "year":
        rows = stats.by_year(db)
        print(table([[r["year"], r["deals"], money(r["upfront_usd_m"]), money(r["total_value_usd_m"]), r["terminated"]] for r in rows],
                    ["Year", "Deals", "Upfront", "Headline value", "Since terminated"]))
    else:
        field = {"licensee": "licensee", "licensor": "licensor", "area": "therapeutic_area",
                 "modality": "modality", "hq": "licensee_hq", "status": "status", "type": "deal_type"}[a.by]
        rows = stats.group(db, field, top=a.top)
        print(table([[trunc(r[field], 40), r["deals"], money(r["upfront_usd_m"]), money(r["total_value_usd_m"])] for r in rows],
                    [a.by.capitalize(), "Deals", "Upfront", "Headline value"]))
    return 0


def cmd_catalysts(db: Database, a) -> int:
    rows = stats.upcoming_catalysts(db, a.days)
    if not rows:
        print("No upcoming catalysts recorded. Add one with:\n"
              "  python -m tracker update <id> --catalyst '2027-03-31|Phase 3 topline readout'")
        return 0
    print(table([[r["date"], r["id"], trunc(r["label"], 40), trunc(r["asset"], 24), trunc(r["event"], 60)] for r in rows],
                ["Date", "ID", "Deal / item", "Asset", "Event"]))
    return 0


def cmd_validate(db: Database, a) -> int:
    errors = validate(db)
    if errors:
        print(f"{len(errors)} problem(s):", *errors, sep="\n  ")
        return 1
    print(f"OK - {len(db.deals)} deals and {len(db.pipeline)} pipeline items are valid.")
    return 0


def _flat(rec: dict) -> dict:
    out = {}
    for k, v in rec.items():
        if isinstance(v, list):
            if v and isinstance(v[0], dict):
                v = "; ".join(f"{x.get('date', '')} {x.get('event') or x.get('note', '')}".strip() for x in v)
            else:
                v = "; ".join(str(x) for x in v)
        out[k] = v
    return out


def cmd_export(db: Database, a) -> int:
    out_dir = Path(a.out or ROOT / "exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    deals = [_flat(d) for d in db.deals]
    pipe = [_flat(p) for p in db.pipeline]
    dcols = DEAL_FIELDS + sorted({k for d in deals for k in d} - set(DEAL_FIELDS))
    pcols = PIPELINE_FIELDS + sorted({k for p in pipe for k in p} - set(PIPELINE_FIELDS))
    if a.format == "csv":
        for name, rows, cols in (("deals.csv", deals, dcols), ("pipeline.csv", pipe, pcols)):
            with (out_dir / name).open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=cols)
                w.writeheader()
                w.writerows(rows)
        print(f"Wrote {out_dir / 'deals.csv'} and {out_dir / 'pipeline.csv'}")
    elif a.format == "json":
        (out_dir / "deals.json").write_text(json.dumps({"deals": db.deals, "pipeline": db.pipeline}, indent=2, ensure_ascii=False))
        print(f"Wrote {out_dir / 'deals.json'}")
    else:
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
        except ImportError:
            print("openpyxl is required for xlsx export: pip install openpyxl", file=sys.stderr)
            return 1
        wb = Workbook()
        for i, (title, rows, cols) in enumerate((("Deals", deals, dcols), ("Pipeline", pipe, pcols))):
            ws = wb.active if i == 0 else wb.create_sheet()
            ws.title = title
            ws.append(cols)
            for c in ws[1]:
                c.font = Font(bold=True)
            for r in rows:
                ws.append([r.get(c) for c in cols])
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
        path = out_dir / "china_biotech_deals.xlsx"
        wb.save(path)
        print(f"Wrote {path}")
    return 0


def cmd_sync(db: Database, a) -> int:
    from tracker import sync_biopharmadive as bpd

    text = Path(a.csv).read_text(encoding="utf-8-sig") if a.csv else None
    added, enriched = bpd.sync(db, text)
    for d in added:
        print(f"  + {d['id']}  {d['announced']}  {d['licensor']} -> {d['licensee']}  {money(d.get('upfront_usd_m'))} upfront")
    for d in enriched:
        print(f"  ~ {d['id']}  filled blank fields from BioPharma Dive")
    print(f"{len(added)} new deal(s), {len(enriched)} enriched.")
    if a.dry_run:
        print("(dry run - nothing saved)")
        return 0
    return save_checked(db) if (added or enriched) else 0


def cmd_scan(db: Database, a) -> int:
    from tracker import news_scan

    hits = news_scan.scan(db)
    out = Path(a.out) if a.out else db.data_dir / "inbox.md"
    out.write_text(news_scan.render_inbox(hits), encoding="utf-8")
    new = sum(1 for h in hits if not h["known_deal"])
    print(f"{len(hits)} relevant headline(s), {new} possibly new -> {out}")
    return 0


def cmd_build(db: Database, a) -> int:
    from tracker import dashboard

    out = dashboard.build(db, Path(a.out) if a.out else None)
    print(f"Dashboard written to {out}")
    return 0


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m tracker", description="China -> US biotech out-licensing deal tracker")
    p.add_argument("--data-dir", help="Alternative data directory (default: ./data)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="List signed deals with filters")
    s.add_argument("--status", nargs="*", choices=sorted(DEAL_STATUSES))
    s.add_argument("--year", type=int)
    s.add_argument("--since", help="Announced on/after YYYY-MM-DD")
    s.add_argument("--licensee")
    s.add_argument("--licensor")
    s.add_argument("--area")
    s.add_argument("--modality")
    s.add_argument("--hq", help="Licensee HQ country, e.g. US")
    s.add_argument("--type", choices=DEAL_TYPES)
    s.add_argument("--min-upfront", type=float, help="USD millions")
    s.add_argument("--search", help="Free-text search across all fields")
    s.add_argument("--sort", choices=["date", "upfront", "total"], default="date")
    s.add_argument("--limit", type=int)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="Show one deal or pipeline item in full")
    s.add_argument("id")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("add", help="Add a signed deal")
    s.add_argument("--id")
    s.add_argument("--announced", required=True, help="YYYY-MM-DD")
    s.add_argument("--licensor", required=True, help="Chinese company granting rights")
    s.add_argument("--licensee", required=True, help="Company receiving rights")
    s.add_argument("--licensor-hq")
    s.add_argument("--licensee-hq")
    s.add_argument("--licensee-type", choices=["Big Pharma", "Mid-size Pharma", "Biotech", "NewCo", "Other"])
    s.add_argument("--deal-type", choices=DEAL_TYPES, default="License")
    s.add_argument("--asset")
    s.add_argument("--target")
    s.add_argument("--modality")
    s.add_argument("--area", choices=THERAPEUTIC_AREAS)
    s.add_argument("--indication")
    s.add_argument("--phase")
    s.add_argument("--territory")
    s.add_argument("--upfront", type=float, help="USD millions")
    s.add_argument("--equity", type=float, help="USD millions")
    s.add_argument("--milestones", type=float, help="USD millions")
    s.add_argument("--total", type=float, help="USD millions (headline 'up to')")
    s.add_argument("--royalties")
    s.add_argument("--status", choices=sorted(DEAL_STATUSES), default="active")
    s.add_argument("--source", action="append", help="URL (repeatable)")
    s.add_argument("--notes")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("update", help="Change status, log events/catalysts or edit fields")
    s.add_argument("id")
    s.add_argument("--status", help="New status (deals: active/pending/completed/terminated)")
    s.add_argument("--date", help="Date of the status change / note (default today)")
    s.add_argument("--note")
    s.add_argument("--event", action="append", help="'YYYY-MM-DD|what happened' (repeatable)")
    s.add_argument("--catalyst", action="append", help="'YYYY-MM-DD|upcoming event' (repeatable)")
    s.add_argument("--source", action="append")
    s.add_argument("--set", action="append", help="field=value (repeatable)")
    s.set_defaults(func=cmd_update)

    s = sub.add_parser("pipeline", help="List potential and future deals")
    s.add_argument("--stage", choices=sorted(PIPELINE_STAGES))
    s.set_defaults(func=cmd_pipeline)

    s = sub.add_parser("pipeline-add", help="Add a potential or future (watchlist) deal")
    s.add_argument("--id")
    s.add_argument("--stage", choices=sorted(PIPELINE_STAGES), required=True)
    s.add_argument("--company", required=True)
    s.add_argument("--company-hq")
    s.add_argument("--asset", required=True)
    s.add_argument("--target")
    s.add_argument("--modality")
    s.add_argument("--area", choices=THERAPEUTIC_AREAS)
    s.add_argument("--indication")
    s.add_argument("--phase")
    s.add_argument("--rights", help="Ex-China rights status, e.g. 'available', 'unknown'")
    s.add_argument("--likelihood", choices=LIKELIHOOD)
    s.add_argument("--partners", help="Plausible licensees")
    s.add_argument("--rationale", required=True)
    s.add_argument("--signal", help="First signal / news note")
    s.add_argument("--date")
    s.add_argument("--source", action="append")
    s.set_defaults(func=cmd_pipeline_add)

    s = sub.add_parser("signal", help="Log a news signal on a pipeline item")
    s.add_argument("id")
    s.add_argument("--note", required=True)
    s.add_argument("--date")
    s.add_argument("--source")
    s.add_argument("--stage", choices=sorted(PIPELINE_STAGES), help="Move to a new stage")
    s.add_argument("--likelihood", choices=LIKELIHOOD)
    s.set_defaults(func=cmd_signal)

    s = sub.add_parser("promote", help="Turn a pipeline item into a signed deal")
    s.add_argument("id")
    s.add_argument("--announced", required=True)
    s.add_argument("--licensee", required=True)
    s.add_argument("--deal-type", choices=DEAL_TYPES, default="License")
    s.add_argument("--territory")
    s.add_argument("--upfront", type=float)
    s.add_argument("--total", type=float)
    s.add_argument("--source", action="append")
    s.set_defaults(func=cmd_promote)

    s = sub.add_parser("stats", help="Summary statistics")
    s.add_argument("--by", choices=["year", "licensee", "licensor", "area", "modality", "hq", "status", "type"], default="year")
    s.add_argument("--top", type=int, default=15)
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("catalysts", help="Upcoming catalysts across deals and pipeline")
    s.add_argument("--days", type=int, help="Only the next N days")
    s.set_defaults(func=cmd_catalysts)

    s = sub.add_parser("validate", help="Check the data files")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("export", help="Export to CSV / Excel / JSON")
    s.add_argument("--format", choices=["csv", "xlsx", "json"], default="xlsx")
    s.add_argument("--out", help="Output directory (default ./exports)")
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("sync", help="Pull new deals from BioPharma Dive's public tracker")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--csv", help="Use a local copy of the dataset instead of downloading")
    s.set_defaults(func=cmd_sync)

    s = sub.add_parser("scan-news", help="Scan news feeds; write candidates to data/inbox.md")
    s.add_argument("--out")
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("build", help="Build the HTML dashboard (docs/index.html)")
    s.add_argument("--out")
    s.set_defaults(func=cmd_build)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db = Database.load(Path(args.data_dir) if args.data_dir else None)
    return args.func(db, args)
