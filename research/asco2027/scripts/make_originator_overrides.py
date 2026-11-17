"""Build data/originator_overrides.csv from the repository's deal tracker (../../data/deals.yaml).

Each out-licensed drug named in the tracker is listed with all of its code names, so that the analysis can
(1) credit the drug to its Chinese originator even when the licensee sponsored the first registered trial, and
(2) merge the originator's and the licensee's code names into one drug.

Needs PyYAML. It is not part of run_all.sh: the generated CSV is committed, so the pipeline stays standard-library only.
Re-run it whenever the deal tracker changes.
"""
import csv
import re
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parent.parent
deals = yaml.safe_load((BASE.parent.parent / "data/deals.yaml").read_text(encoding="utf-8"))
TOK = re.compile(r"[A-Za-z]{2,8}[- ]?\d{2,}[A-Za-z0-9]*(?:-[A-Za-z0-9]+)?|[A-Za-z]{6,}(?:mab|nib|tecan|cept|tug|mig|cel|bart|dotin|clax)\b")
GENERIC = {"option"}
# Licensee code names that the deal tracker does not list. Added from the author's memory of company announcements;
# each should be verified against the licensee's pipeline page. Key = an alias already in the tracker.
EXTRA_ALIASES = {
    "skb264": ["MK-2870", "sacituzumab tirumotecan"],
    "hs20093": ["GSK5764227"],
    "hs20089": ["GSK5733584"],
    "db1303": ["BNT323", "trastuzumab pamirtecan"],
    "db1311": ["BNT324"],
    "yl202": ["BNT326"],
    "pm8002": ["BNT327", "pumitamig"],
    "lm299": ["MK-2010"],
    "ssgj707": ["PF-08634404"],
    "shr4849": ["IDE849"],
    "hrs1167": ["M9466"],
    "blb01d1": ["BMS-986507", "izalontamab brengitecan"],
    "ivonescimab": ["AK112", "SMT112"],
    "rc48": ["disitamab vedotin"],
    "sysa1801": ["CRB-701"],
}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def split_drugs(asset):
    """Split on commas/semicolons that are outside parentheses: each piece is one drug with its aliases."""
    out, depth, cur = [], 0, ""
    for ch in asset:
        depth += ch == "("
        depth -= ch == ")"
        if ch in ",;" and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    return [p.strip() for p in out + [cur] if p.strip()]


rows, seen = [], {}
for d in deals:
    for i, piece in enumerate(split_drugs(d.get("asset") or "")):
        aliases = sorted({norm(t) for t in TOK.findall(piece) if norm(t) not in GENERIC and len(norm(t)) >= 5})
        if not aliases:
            continue
        group = next((seen[a] for a in aliases if a in seen), f"{d['id']}-{i + 1}")   # same drug in two deals -> one group
        extra = sorted({norm(x) for a in aliases for x in EXTRA_ALIASES.get(a, [])} - set(aliases))
        for a, src in [(a, "deal tracker") for a in aliases] + [(a, "author's memory - verify") for a in extra]:
            if a not in seen:
                seen[a] = group
                rows.append({"alias": a, "drug_group": group, "drug_as_listed": piece, "originator": d["licensor"],
                             "originator_country": "China", "licensee": d["licensee"], "deal_id": d["id"],
                             "deal_announced": d["announced"], "alias_source": src})
rows.sort(key=lambda r: (r["drug_group"], r["alias"]))
with (BASE / "data/originator_overrides.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print("aliases", len(rows), "| drugs", len({r["drug_group"] for r in rows}))
