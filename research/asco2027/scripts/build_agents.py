"""Agent-level table: split combination names, link to NCI Thesaurus, find each agent's first registered trial.

For every agent we also collect the sentences that mention it by name (across all of its trials), because later
trials often describe a drug better than its first trial does.
"""
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
          "Antibiotic", "Hormone", "Inorganic Chemical", "Chemical Viewed Structurally",
          "Indicator, Reagent, or Diagnostic Aid", "Virus", "Bacterium", "Vitamin", "Enzyme", "Receptor", "Element, Ion, or Isotope")
ncit, syn2code = {}, {}
with (BASE / "data/raw/ncit/Thesaurus.txt").open(encoding="utf-8") as fh:
    for row in csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
        if len(row) < 8:
            continue
        code, _, parents, syns, definition, display, status, sem = row[:8]
        if not any(s in sem for s in SEM_OK) or not definition:
            continue
        names = syns.split("|")
        ncit[code] = {"code": code, "name": display or names[0], "definition": definition}
        for n in names:
            k = norm(n)
            if len(k) >= 4:
                syn2code.setdefault(k, code)
print("ncit drug-like concepts", len(ncit), "synonyms", len(syn2code))

# ---------- split intervention names into agent strings ----------
DRUG_TYPES = {"DRUG", "BIOLOGICAL", "GENETIC", "COMBINATION_PRODUCT"}
SPLIT = re.compile(r"\s*(?:\+|;|；|,|，|/(?!\d)|\band\b|\bplus\b|\bwith\b|\bin combination with\b|\bcombined with\b|\bfollowed by\b|\bor\b|&)\s*", re.I)
NOISE = re.compile(
    r"\b(placebo|saline|standard|chemotherapy|radiotherapy|radiation|supportive|pretreatment|pre-treatment|monotherapy|"
    r"combination|dose|escalation|expansion|cohort|arm|part|phase|regimen|treatment|therapy|injection|tablets?|capsules?|"
    r"infusion|oral|intravenous|iv|subcutaneous|sc|solution|suspension|for|selected|single|agent|investigational|drug|"
    r"biological|level|group|schedule|low|high|mg|kg|qd|bid|q\dw|weekly|daily|cells?|powder|ascending|mtd|rp2d|pr2d|"
    r"multi-?target|tosylate|hydrochloride|mesylate|maleate|citrate)\b", re.I)


def ncit_lookup(raw: str):
    """Match a name to NCIt, also trying with trailing words removed ("Olaparib 200" -> olaparib)."""
    words = raw.split()
    for end in range(len(words), 0, -1):
        k = norm(" ".join(words[:end]))
        if k in syn2code:
            return syn2code[k]
    return None


def agents_in(name: str):
    s = re.sub(r"[（(].*?[)）]", " ", name)
    out = []
    for part in SPLIT.split(s):
        raw = part.strip(" .:-")
        if not raw:
            continue
        code = ncit_lookup(raw)
        if code:
            out.append((raw, code))
            continue
        cleaned = re.sub(r"\b\d+(\.\d+)?\s*(mg|mcg|ug|g|ml|mg/kg|mg/m2)\b", " ", raw, flags=re.I)
        cleaned = NOISE.sub(" ", cleaned).strip(" .:-")
        cleaned = re.sub(r"\s+", " ", cleaned)
        code = ncit_lookup(cleaned) if cleaned else None
        if code:
            out.append((cleaned, code))
            continue
        k = norm(cleaned)
        if len(k) >= 3 and not k.isdigit() and len(cleaned.split()) <= 4:
            out.append((cleaned, k))
    return out


SENT = re.compile(r"(?<=[a-z0-9\)\]])[.;]\s+(?=[A-Z\[])|\n+")


def sentences(text):
    return [s.strip() for s in SENT.split(text or "") if s and s.strip()]


rows = [json.loads(l) for l in (BASE / "data/raw/ctgov_phase1_oncology.jsonl").open()]
rows.sort(key=lambda r: (r["start"] or r["first_submit"] or "9999-99"))
trials_of = collections.defaultdict(list)   # agent id -> [(start, nct, raw name, intervention)]
names_of = collections.defaultdict(set)     # agent id -> normalised name keys
for r in rows:
    start = (r["start"] or r["first_submit"] or "9999-99")[:7]
    seen = set()
    for iv in r["interventions"]:
        if iv["type"] not in DRUG_TYPES or not iv["name"]:
            continue
        cands = agents_in(iv["name"])
        single = len(cands) == 1
        if single:
            aid, raw = cands[0][1], cands[0][0]
            keys = {norm(raw)}
            for o in (iv.get("other") or []):
                ko = norm(re.sub(r"[（(].*?[)）]", " ", o))
                if len(ko) >= 4 and not ko.isdigit():
                    keys.add(ko)
                    if aid not in ncit and ko in syn2code:
                        aid = syn2code[ko]
            cands = [(raw, aid)]
        for raw, aid in cands:
            if aid in seen:
                continue
            seen.add(aid)
            trials_of[aid].append((start, r["nct"], raw, iv if single else None))
            names_of[aid].add(norm(raw))
            if single:
                names_of[aid] |= keys

by_nct = {r["nct"]: r for r in rows}
agents = []
for aid, tl in trials_of.items():
    tl.sort(key=lambda x: x[0])
    first_start, first_nct, raw, _ = tl[0]
    keys = {k for k in names_of[aid] if len(k) >= 4}
    if aid in ncit:
        keys.add(norm(ncit[aid]["name"]))

    def named_in_title(nct):
        t = by_nct[nct]
        blob = norm((t["title"] or "") + " " + (t["official_title"] or ""))
        return any(k in blob for k in keys)

    # Attribute the agent to the sponsor of the earliest trial that names it in the title, if that trial starts
    # within 12 months of the agent's first appearance; otherwise to the sponsor of the first trial.
    def months(s):
        return int(s[:4]) * 12 + int(s[5:7]) if s[:4].isdigit() and s[5:7].isdigit() else 10 ** 6
    attr = next((x for x in tl if named_in_title(x[1]) and months(x[0]) - months(first_start) <= 12), tl[0])
    t = by_nct[attr[1]]

    texts, iv_descs = [], []
    for start, nct, _, iv in tl[:12]:
        tr = by_nct[nct]
        if iv and iv.get("desc"):
            iv_descs.append(iv["desc"])
        for field in ("title", "official_title", "summary", "detail"):
            for s in sentences(tr.get(field)):
                if any(k in norm(s) for k in keys):
                    texts.append(s[:600])
        for arm in tr.get("arms") or []:
            if any(k in norm(arm) for k in keys):
                texts.append(arm[:400])
    n = ncit.get(aid)
    agents.append({
        "agent_id": aid, "agent": raw, "first_start": first_start, "first_nct": first_nct, "n_trials": len(tl),
        "attr_nct": attr[1], "ncit_name": n and n["name"], "ncit_def": n and n["definition"],
        "sponsor": t["sponsor"], "sponsor_class": t["sponsor_class"], "countries": t["countries"],
        "phases": t["phases"], "title": t["title"], "conditions": t["conditions"], "cond_mesh": t["cond_mesh"],
        "official_title": t["official_title"],
        "texts": list(dict.fromkeys(texts))[:40], "iv_descs": list(dict.fromkeys(iv_descs))[:5],
        "later_phase": sorted({ph for _, nct, _, _ in tl for ph in (by_nct[nct]["phases"] or [])}),
    })
agents.sort(key=lambda d: (d["first_start"], str(d["agent_id"])))
(BASE / "data/agents_all.json").write_text(json.dumps(agents, ensure_ascii=False))
new = [a for a in agents if "2020-01" <= a["first_start"] <= "2026-09" and a["sponsor_class"] == "INDUSTRY"]
print("agents", len(agents), "| industry, first trial 2020-01..2026-09:", len(new),
      "| with NCIt:", sum(1 for a in new if a["ncit_def"]), "| with name-sentences:", sum(1 for a in new if a["texts"]))
