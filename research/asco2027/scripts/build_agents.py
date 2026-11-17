"""Agent-level table: split combination names, link to NCI Thesaurus, find each agent's first registered trial."""
import collections
import csv
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
csv.field_size_limit(sys.maxsize)

def norm(s: str) -> str:
    s = re.sub(r"[®™]", "", s.lower())
    return re.sub(r"[^a-z0-9α-ω]+", "", s)

# ---------- NCI Thesaurus: drug-like concepts ----------
SEM_OK = ("Pharmacologic Substance", "Immunologic Factor", "Amino Acid, Peptide, or Protein", "Organic Chemical",
          "Biologically Active Substance", "Nucleic Acid, Nucleoside, or Nucleotide", "Cell", "Clinical Drug",
          "Therapeutic or Preventive Procedure", "Antibiotic", "Hormone", "Inorganic Chemical", "Chemical Viewed Structurally",
          "Indicator, Reagent, or Diagnostic Aid", "Virus", "Bacterium", "Vitamin", "Enzyme", "Receptor", "Element, Ion, or Isotope")
ncit, syn2code = {}, {}
with (BASE / "data/raw/ncit/Thesaurus.txt").open(encoding="utf-8") as fh:
    for row in csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
        if len(row) < 8:
            continue
        code, _, parents, syns, definition, display, status, sem = row[:8]
        if not any(s in sem for s in SEM_OK) or "Therapeutic or Preventive Procedure" == sem:
            continue
        if not definition:
            continue
        names = syns.split("|")
        ncit[code] = {"code": code, "name": display or names[0], "definition": definition, "sem": sem, "parents": parents}
        for n in names:
            k = norm(n)
            if len(k) >= 4:
                syn2code.setdefault(k, code)
print("ncit drug-like concepts", len(ncit), "synonyms", len(syn2code))

# ---------- split intervention names into agent strings ----------
DRUG_TYPES = {"DRUG", "BIOLOGICAL", "GENETIC", "COMBINATION_PRODUCT"}
SPLIT = re.compile(r"\s*(?:\+|;|,|/(?!\d)|\band\b|\bplus\b|\bwith\b|\bin combination with\b|\bcombined with\b|\bfollowed by\b|\bor\b|&)\s*", re.I)
NOISE = re.compile(
    r"\b(placebo|saline|standard|chemotherapy|radiotherapy|radiation|supportive|pretreatment|pre-treatment|monotherapy|"
    r"combination|dose|escalation|expansion|cohort|arm|part|phase|regimen|treatment|therapy|injection|tablets?|capsules?|"
    r"infusion|oral|intravenous|iv|subcutaneous|sc|solution|suspension|for|selected|single|agent|investigational|drug|"
    r"biological|level|group|schedule|low|high|mg|kg|qd|bid|q\dw|weekly|daily|cells?)\b", re.I)

def agents_in(name: str):
    s = re.sub(r"\(.*?\)", " ", name)
    out = []
    for part in SPLIT.split(s):
        raw = part.strip(" .:-")
        if not raw:
            continue
        k_full = norm(raw)
        if k_full in syn2code:
            out.append((raw, k_full))
            continue
        cleaned = re.sub(r"\b\d+(\.\d+)?\s*(mg|mcg|ug|g|ml|mg/kg|mg/m2)\b", " ", raw, flags=re.I)
        cleaned = NOISE.sub(" ", cleaned).strip(" .:-")
        cleaned = re.sub(r"\s+", " ", cleaned)
        k = norm(cleaned)
        if len(k) >= 3 and not k.isdigit() and len(cleaned.split()) <= 4:
            out.append((cleaned, k))
    return out

rows = [json.loads(l) for l in (BASE / "data/raw/ctgov_phase1_oncology.jsonl").open()]
first, n_trials = {}, collections.Counter()
for r in rows:
    start = (r["start"] or r["first_submit"] or "9999-99")[:7]
    seen = set()
    for iv in r["interventions"]:
        if iv["type"] not in DRUG_TYPES or not iv["name"]:
            continue
        cands = agents_in(iv["name"])
        for o in (iv.get("other") or []):
            if len(cands) == 1:  # aliases only meaningful for single-agent interventions
                k = norm(re.sub(r"\(.*?\)", " ", o))
                if len(k) >= 3 and not k.isdigit():
                    cands.append((o, k))
        # resolve to one id per agent: NCIt code if any alias matches, else the primary key
        ids = []
        single = len(agents_in(iv["name"])) == 1
        if single:
            code = next((syn2code[k] for _, k in cands if k in syn2code), None)
            ids.append((code or cands[0][1], cands[0][0], iv))
        else:
            for raw, k in cands:
                ids.append((syn2code.get(k, k), raw, iv))
        for aid, raw, iv_ in ids:
            if aid in seen:
                continue
            seen.add(aid)
            n_trials[aid] += 1
            cur = first.get(aid)
            if cur is None or start < cur["first_start"]:
                first[aid] = {"agent_id": aid, "agent": raw, "first_start": start, "nct": r["nct"], "iv_desc": iv_.get("desc"),
                              "iv_type": iv_["type"], "iv_other": iv_.get("other")}

by_nct = {r["nct"]: r for r in rows}
agents = []
for aid, a in first.items():
    t = by_nct[a["nct"]]
    n = ncit.get(aid)
    agents.append({**a, "n_trials": n_trials[aid], "ncit_name": n and n["name"], "ncit_def": n and n["definition"],
                   "sponsor": t["sponsor"], "sponsor_class": t["sponsor_class"], "collaborators": t["collaborators"],
                   "countries": t["countries"], "phases": t["phases"], "title": t["title"],
                   "official_title": t["official_title"], "summary": t["summary"], "conditions": t["conditions"],
                   "cond_mesh": t["cond_mesh"], "enrollment": t["enrollment"], "status": t["status"]})
agents.sort(key=lambda d: (d["first_start"], d["agent_id"]))
(BASE / "data/agents_all.json").write_text(json.dumps(agents, ensure_ascii=False))
new = [a for a in agents if "2020-01" <= a["first_start"] <= "2026-10" and a["sponsor_class"] == "INDUSTRY"]
print("agents", len(agents), "| new industry 2020-01..2026-10:", len(new), "| with NCIt:", sum(1 for a in new if a["ncit_def"]))
print(sorted(collections.Counter(a["first_start"][:4] for a in new).items()))
print("sponsors", len({a["sponsor"] for a in new}))
import random; random.seed(3)
for a in random.sample(new, 30):
    print(a["first_start"], "|", a["agent"][:30], "|", a["sponsor"][:30], "|", (a["ncit_def"] or "-")[:110])
