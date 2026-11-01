"""Loading, saving and validating the deal database.

The source of truth is plain YAML in ``data/``:

* ``data/deals.yaml``     - signed deals (active, pending, completed, terminated)
* ``data/pipeline.yaml``  - deals that have not happened yet: *potential*
                            (reported talks, option decisions, NewCo formation)
                            and *future* (watchlist of unpartnered assets)
* ``data/companies.yaml`` - company -> HQ country / type, used to normalise names

Everything is human-editable; the CLI is a convenience layer on top.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DEALS_FILE = DATA_DIR / "deals.yaml"
PIPELINE_FILE = DATA_DIR / "pipeline.yaml"
COMPANIES_FILE = DATA_DIR / "companies.yaml"

# --------------------------------------------------------------------------- #
# Controlled vocabularies
# --------------------------------------------------------------------------- #
DEAL_STATUSES = {
    "active": "Deal in force (licence, option or collaboration running)",
    "pending": "Announced but not yet closed (e.g. awaiting antitrust clearance)",
    "completed": "Acquisition closed / deal fully consummated",
    "terminated": "Ended: rights returned, option declined or partner exited",
}
DEAL_TYPES = [
    "License",
    "Option",
    "Collaboration",
    "NewCo",
    "Acquisition",
    "Platform",
]
PIPELINE_STAGES = {
    "potential": "Reported talks, pending option decisions, NewCo being formed",
    "future": "Watchlist: unpartnered asset with ex-China rights likely available",
}
LIKELIHOOD = ["high", "medium", "low"]
THERAPEUTIC_AREAS = [
    "Cancer",
    "Immune diseases",
    "Metabolic diseases",
    "Cardiovascular",
    "CNS disorders",
    "Respiratory",
    "Kidney diseases",
    "Infectious diseases",
    "Rare diseases",
    "Multiple",
    "Other",
    "Undisclosed",
]

# Finer than modality, for comparables: what kind of molecule changed hands.
# Optional; sync leaves it blank and a reviewer fills it in.
DEAL_FORMATS = [
    "ADC",
    "Bispecific / multispecific",
    "T-cell engager",
    "Monoclonal antibody",
    "Other biologic",
    "Small molecule",
    "Peptide",
    "Nucleic acid",
    "Cell or gene therapy",
    "Radiopharmaceutical",
    "Undisclosed",
]

# Field order used when writing YAML so diffs stay readable.
DEAL_FIELDS = [
    "id",
    "announced",
    "licensor",
    "licensor_hq",
    "licensee",
    "licensee_hq",
    "licensee_type",
    "deal_type",
    "asset",
    "target",
    "modality",
    "format",
    "therapeutic_area",
    "indication",
    "phase_at_deal",
    "territory",
    "upfront_usd_m",
    "equity_usd_m",
    "milestones_usd_m",
    "total_value_usd_m",
    "royalties",
    "status",
    "status_date",
    "status_note",
    "development_status",
    "catalysts",
    "events",
    "sources",
    "data_source",
    "notes",
    "last_verified",
]
PIPELINE_FIELDS = [
    "id",
    "stage",
    "company",
    "company_hq",
    "asset",
    "target",
    "modality",
    "therapeutic_area",
    "indication",
    "phase",
    "ex_china_rights",
    "likelihood",
    "potential_partners",
    "rationale",
    "signals",
    "catalysts",
    "added",
    "last_reviewed",
    "sources",
    "notes",
]
REQUIRED_DEAL_FIELDS = ["id", "announced", "licensor", "licensee", "deal_type", "status"]
REQUIRED_PIPELINE_FIELDS = ["id", "stage", "company", "asset", "rationale"]

DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
MONEY_FIELDS = ["upfront_usd_m", "equity_usd_m", "milestones_usd_m", "total_value_usd_m"]


# --------------------------------------------------------------------------- #
# YAML helpers
# --------------------------------------------------------------------------- #
class _Dumper(yaml.SafeDumper):
    """Dumper that indents lists and never emits anchors/aliases."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):  # noqa: D401
        return super().increase_indent(flow, False)

    def ignore_aliases(self, data: Any) -> bool:  # noqa: D401
        return True


def _str_presenter(dumper: yaml.SafeDumper, data: str):
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_Dumper.add_representer(str, _str_presenter)


def _normalise_dates(obj: Any) -> Any:
    """PyYAML parses ``2024-05-01`` into ``date``; keep everything as strings."""
    if isinstance(obj, (dt.date, dt.datetime)):
        return obj.isoformat()[:10]
    if isinstance(obj, dict):
        return {k: _normalise_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalise_dates(v) for v in obj]
    return obj


def _ordered(record: dict, order: list[str]) -> dict:
    out = {k: record[k] for k in order if k in record and record[k] not in (None, "", [])}
    for k, v in record.items():  # keep unknown/custom fields at the end
        if k not in out and v not in (None, "", []):
            out[k] = v
    return out


def read_yaml(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or []
    return _normalise_dates(data)


def write_yaml(path: Path, records: list[dict], order: list[str], header: str) -> None:
    body = yaml.dump(
        [_ordered(r, order) for r in records],
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    path.write_text(header.rstrip() + "\n\n" + body, encoding="utf-8")


DEALS_HEADER = """\
# China -> US/global biotech out-licensing deals (signed).
# Edit by hand or via `python -m tracker add|update`. Run `python -m tracker validate` after edits.
# Money is in USD millions as announced (headline "up to" values; not risk-adjusted).
# Inclusion rule: China-based licensor grants rights that include the United States."""

PIPELINE_HEADER = """\
# Deals that have not happened yet.
#   stage: potential -> reported talks / option decision pending / NewCo forming
#   stage: future    -> watchlist of unpartnered Chinese assets (analyst judgement, verify before use)
# Promote an entry to a signed deal with `python -m tracker promote <id> ...`."""


# --------------------------------------------------------------------------- #
# Database object
# --------------------------------------------------------------------------- #
@dataclass
class Database:
    deals: list[dict] = field(default_factory=list)
    pipeline: list[dict] = field(default_factory=list)
    companies: dict[str, dict] = field(default_factory=dict)
    data_dir: Path = DATA_DIR

    # ---- persistence ------------------------------------------------------ #
    @classmethod
    def load(cls, data_dir: Path | None = None) -> "Database":
        d = Path(data_dir) if data_dir else DATA_DIR
        companies_raw = {}
        cpath = d / "companies.yaml"
        if cpath.exists():
            with cpath.open(encoding="utf-8") as fh:
                companies_raw = yaml.safe_load(fh) or {}
        db = cls(
            deals=read_yaml(d / "deals.yaml"),
            pipeline=read_yaml(d / "pipeline.yaml"),
            companies=companies_raw,
            data_dir=d,
        )
        return db

    def save(self) -> None:
        self.deals.sort(key=lambda r: (str(r.get("announced", "")), r.get("id", "")), reverse=True)
        self.pipeline.sort(key=lambda r: (r.get("stage", ""), r.get("company", ""), r.get("id", "")))
        write_yaml(self.data_dir / "deals.yaml", self.deals, DEAL_FIELDS, DEALS_HEADER)
        write_yaml(self.data_dir / "pipeline.yaml", self.pipeline, PIPELINE_FIELDS, PIPELINE_HEADER)

    # ---- lookups ---------------------------------------------------------- #
    def deal(self, deal_id: str) -> dict | None:
        return next((d for d in self.deals if d.get("id") == deal_id), None)

    def pipeline_item(self, item_id: str) -> dict | None:
        return next((p for p in self.pipeline if p.get("id") == item_id), None)

    def company_hq(self, name: str) -> str | None:
        info = self.companies.get(name)
        return info.get("hq") if isinstance(info, dict) else None

    def company_type(self, name: str) -> str | None:
        info = self.companies.get(name)
        return info.get("type") if isinstance(info, dict) else None

    # ---- id generation ---------------------------------------------------- #
    def next_deal_id(self, announced: str) -> str:
        year = str(announced)[:4]
        prefix = f"CN-{year}-"
        nums = [
            int(d["id"][len(prefix):])
            for d in self.deals
            if str(d.get("id", "")).startswith(prefix) and d["id"][len(prefix):].isdigit()
        ]
        return f"{prefix}{(max(nums) + 1 if nums else 1):03d}"

    def next_pipeline_id(self, stage: str) -> str:
        prefix = "POT-" if stage == "potential" else "FUT-"
        nums = [
            int(p["id"][len(prefix):])
            for p in self.pipeline
            if str(p.get("id", "")).startswith(prefix) and p["id"][len(prefix):].isdigit()
        ]
        return f"{prefix}{(max(nums) + 1 if nums else 1):03d}"


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate(db: Database) -> list[str]:
    """Return a list of human-readable problems (empty list == valid)."""
    errors: list[str] = []
    seen: set[str] = set()

    for i, d in enumerate(db.deals):
        where = f"deals[{i}] ({d.get('id', '?')})"
        for f in REQUIRED_DEAL_FIELDS:
            if not d.get(f):
                errors.append(f"{where}: missing required field '{f}'")
        did = d.get("id")
        if did in seen:
            errors.append(f"{where}: duplicate id '{did}'")
        seen.add(did)
        if d.get("status") and d["status"] not in DEAL_STATUSES:
            errors.append(f"{where}: status '{d['status']}' not in {sorted(DEAL_STATUSES)}")
        if d.get("deal_type") and d["deal_type"] not in DEAL_TYPES:
            errors.append(f"{where}: deal_type '{d['deal_type']}' not in {DEAL_TYPES}")
        if d.get("format") and d["format"] not in DEAL_FORMATS:
            errors.append(f"{where}: format '{d['format']}' not in {DEAL_FORMATS}")
        if d.get("therapeutic_area") and d["therapeutic_area"] not in THERAPEUTIC_AREAS:
            errors.append(f"{where}: therapeutic_area '{d['therapeutic_area']}' not in {THERAPEUTIC_AREAS}")
        for f in ("announced", "status_date", "last_verified"):
            if d.get(f) and not DATE_RE.match(str(d[f])):
                errors.append(f"{where}: {f} '{d[f]}' must be YYYY, YYYY-MM or YYYY-MM-DD")
        for f in MONEY_FIELDS:
            v = d.get(f)
            if v is not None and (not _is_number(v) or v < 0):
                errors.append(f"{where}: {f} must be a non-negative number (USD millions), got {v!r}")
        up, tot = d.get("upfront_usd_m"), d.get("total_value_usd_m")
        if _is_number(up) and _is_number(tot) and tot + 0.5 < up:
            errors.append(f"{where}: total_value_usd_m ({tot}) is smaller than upfront_usd_m ({up})")
        if d.get("status") == "terminated" and not d.get("status_date"):
            errors.append(f"{where}: terminated deals need a status_date")
        for key in ("catalysts", "events"):
            for j, ev in enumerate(d.get(key) or []):
                if not isinstance(ev, dict) or not ev.get("date") or not ev.get("event"):
                    errors.append(f"{where}: {key}[{j}] needs 'date' and 'event'")
                elif not DATE_RE.match(str(ev["date"])):
                    errors.append(f"{where}: {key}[{j}] date '{ev['date']}' is not ISO formatted")

    for i, p in enumerate(db.pipeline):
        where = f"pipeline[{i}] ({p.get('id', '?')})"
        for f in REQUIRED_PIPELINE_FIELDS:
            if not p.get(f):
                errors.append(f"{where}: missing required field '{f}'")
        pid = p.get("id")
        if pid in seen:
            errors.append(f"{where}: duplicate id '{pid}'")
        seen.add(pid)
        if p.get("stage") and p["stage"] not in PIPELINE_STAGES:
            errors.append(f"{where}: stage '{p['stage']}' not in {sorted(PIPELINE_STAGES)}")
        if p.get("likelihood") and p["likelihood"] not in LIKELIHOOD:
            errors.append(f"{where}: likelihood '{p['likelihood']}' not in {LIKELIHOOD}")
        if p.get("therapeutic_area") and p["therapeutic_area"] not in THERAPEUTIC_AREAS:
            errors.append(f"{where}: therapeutic_area '{p['therapeutic_area']}' not in {THERAPEUTIC_AREAS}")
        for j, s in enumerate(p.get("signals") or []):
            if not isinstance(s, dict) or not s.get("date") or not s.get("note"):
                errors.append(f"{where}: signals[{j}] needs 'date' and 'note'")

    return errors


# --------------------------------------------------------------------------- #
# Small shared helpers
# --------------------------------------------------------------------------- #
def today() -> str:
    return dt.date.today().isoformat()


def year_of(record: dict) -> int | None:
    a = str(record.get("announced") or "")
    return int(a[:4]) if a[:4].isdigit() else None


def norm_name(name: str) -> str:
    """Loose company-name key used for de-duplication."""
    s = name.lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(
        r"\b(pharmaceuticals?|pharma|biopharma(ceuticals?)?|biosciences?|biotech(nology)?|biologics|"
        r"therapeutics|medicines|life science|group|holdings?|co\.?|inc\.?|ltd\.?|limited|"
        r"international|jiangsu|shanghai|suzhou|beijing|hangzhou|zhejiang|sichuan|hebei)\b",
        " ",
        s,
    )
    return re.sub(r"[^a-z0-9]+", "", s)
