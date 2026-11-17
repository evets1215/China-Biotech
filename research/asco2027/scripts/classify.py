"""Classify each new investigational agent: sponsor country, drug type, target(s), tumour group.

Input : data/agents_all.json (from build_agents.py)
Output: data/cohort.csv  (one row per agent whose first registered trial started 2020-01..2026-09, industry sponsor)
"""
import collections
import csv
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from lexicon import MODALITY_RX, TARGET_RX, TUMOUR_RX  # noqa: E402
from sponsor_lists import sponsor_country  # noqa: E402

START, END = "2020-01", "2026-09"
CODE = re.compile(r"[A-Za-z]{1,10}[- ]?\d{2,}|\d{2,}[A-Za-z]{2,}")
INN = re.compile(r"\w{4,}(?:mab|tug|nib|tinib|ciclib|rasib|parib|lisib|cel|leucel|gene|vec|stat|tide|mig|bart|fusp|cept|kin|tecan|dotin|degib|clax|mide)\b", re.I)
BAD_NAME = re.compile(r"x ?10\^|\bgroup\b|\bcohort\b|\barm\b|^\W*$|^[A-D]:", re.I)
COMBO = re.compile(r"(?:,?\s*(?:alone (?:and|or) )?(?:in |as )?(?:combination|combined|co-administ\w+) (?:with|therapy).*?(?:\.|$)|"
                   r"\s(?:plus|with or without|\+|and/or)\s.*?(?:\.|$)|\s(?:alone or|as monotherapy or|monotherapy and)\s.*?(?:\.|$))", re.I | re.S)
EXCLUDE = re.compile(r"healthy (?:volunteer|subject|participant|male|adult)|bioavailab|bioequivalen|biosimilar|pk similarity|"
                     r"mass balance|\bADME\b|food effect|drug[- ]drug interaction|cachexia|mucositis|neutropenia|nausea|imaging agent|"
                     r"diagnostic|PET imaging|PET/CT", re.I)
ONC = re.compile(r"cancer|tumou?r|neoplasm|carcinoma|lymphoma|leuk[ae]{1,2}mi|myeloma|sarcoma|melanoma|gliom|glioblastoma|malignan|"
                 r"myelodysplas|NSCLC|SCLC|\bAML\b|mesothelioma|blastoma|myelofibrosis", re.I)


def first_sentences(text, n=1):
    return " ".join(re.split(r"(?<=[a-z0-9\)])\.\s+(?=[A-Z])", text or "")[:n])


def find_targets(text):
    return [name for name, rx in TARGET_RX.items() if rx.search(text)]


def find_modality(text):
    for lab, rx in MODALITY_RX:
        if rx.search(text):
            return lab
    return None


def main():
    agents = json.load((BASE / "data/agents_all.json").open())
    new = [a for a in agents if a["first_start"] <= END]  # all agents since 2010, so novelty can be judged against history
    sites = collections.defaultdict(set)
    for a in new:
        if a["sponsor_class"] == "INDUSTRY":
            sites[a["sponsor"]] |= set(a["countries"])

    rows, dropped = [], collections.Counter()
    for a in new:
        name = a["agent"]
        cond_text = " ".join((a["conditions"] or []) + (a["cond_mesh"] or []) + [a["title"] or ""])
        if EXCLUDE.search(" ".join(filter(None, [a["title"], a["official_title"]]))) or "14C" in name:
            dropped["healthy-volunteer / PK / biosimilar / supportive-care study"] += 1
            continue
        if not ONC.search(cond_text):
            dropped["not oncology"] += 1
            continue
        if BAD_NAME.search(name) or not (a["ncit_def"] or CODE.search(name) or INN.search(name)):
            dropped["not an identifiable agent name"] += 1
            continue
        ncit1 = first_sentences(a["ncit_def"], 1)
        trial_txt = COMBO.sub(". ", " . ".join(filter(None, [a["title"], a["official_title"], a["iv_desc"]])))
        summ = COMBO.sub(". ", first_sentences(a["summary"], 2))
        tiers = [("NCI Thesaurus", ncit1), ("Trial title/intervention", trial_txt), ("Trial summary", summ)]
        targets, t_src = [], ""
        for src, txt in tiers:
            if txt:
                targets = find_targets(txt)
                if targets:
                    t_src = src
                    break
        modality, m_src = None, ""
        for src, txt in tiers:
            if txt:
                modality = find_modality(txt)
                if modality:
                    m_src = src
                    break
        if modality is None:
            modality = find_modality(name) or "Unclassified"
        # bispecific ADC: keep ADC label but flag
        all_txt = " ".join(t for _, t in tiers)
        bsadc = bool(re.search(r"bispecific antibody[- ]drug conjugate|bispecific ADC|bsADC|BsADC", all_txt))
        tumour = next((lab for lab, rx in TUMOUR_RX if rx.search(" ".join(a["conditions"] or []) + " " + (a["title"] or ""))), "Other")
        if a["sponsor_class"] == "INDUSTRY":
            country = sponsor_country(a["sponsor"], sites[a["sponsor"]])
        else:
            sc = set(a["countries"])
            country = "China" if sc and sc <= {"China"} else ("US" if "United States" in sc else "Other")
        in_cohort = int(a["sponsor_class"] == "INDUSTRY" and a["first_start"] >= START)
        targets = [t for t in targets if not (t == "CD3" and modality.startswith("CAR-T"))]
        if modality == "Antibody-drug conjugate" and len(targets) >= 2:
            bsadc = True
        rows.append({
            "agent": name, "agent_id": a["agent_id"], "first_start": a["first_start"], "year": a["first_start"][:4],
            "nct": a["nct"], "sponsor": a["sponsor"], "sponsor_class": a["sponsor_class"], "in_cohort": in_cohort, "country": country, "site_countries": "|".join(a["countries"]),
            "phases": "|".join(a["phases"] or []), "modality": modality, "modality_source": m_src,
            "targets": "|".join(sorted(targets)), "n_targets": len(targets), "target_source": t_src,
            "bispecific_adc": int(bsadc), "tumour_group": tumour, "has_ncit": int(bool(a["ncit_def"])),
            "title": a["title"],
        })
    rows.sort(key=lambda r: (r["first_start"], r["agent"]))
    with (BASE / "data/cohort.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("all agents kept", len(rows), "dropped", dict(dropped))
    coh = [r for r in rows if r["in_cohort"]]
    print("cohort (industry, first trial 2020-01..2026-09):", len(coh))
    for c in ("China", "US", "Other"):
        sub = [r for r in coh if r["country"] == c]
        print(f"{c:6} n={len(sub):5} target identified {100*sum(1 for r in sub if r['targets'])/len(sub):.0f}%  "
              f"drug type identified {100*sum(1 for r in sub if r['modality']!='Unclassified')/len(sub):.0f}%")
    print(collections.Counter(r["modality"] for r in coh).most_common())


if __name__ == "__main__":
    main()
