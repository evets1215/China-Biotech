"""Classify each investigational agent: sponsor country, drug type, target(s), tumour group.

Targets are accepted from two kinds of text only:
  1. the first sentence of the agent's NCI Thesaurus definition (describes what the drug is), or
  2. sentences in the agent's own trials that mention the agent by name, and only where the target appears in a
     drug-describing context ("anti-X", "X inhibitor", "targeting X" ...), not a patient-selection context
     ("X-positive", "X-mutant").

Input : data/agents_all.json      Output: data/cohort.csv (all agents since 2010; `in_cohort` marks the study cohort)
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
IMAGING_NAME = re.compile(r"\b(?:68|18|64|89|99m|124|111|11|14)\]?-?(?:Ga|F|Cu|Zr|Tc|I|In|C)\b|\[?(?:68Ga|18F|64Cu|89Zr|99mTc|124I|111In|11C|14C)", re.I)
# The cohort needs a first trial that could be a first-in-human study. Phase 3/4 first trials are mostly
# biosimilars, generics and new formulations.
EARLY_PHASES = {"EARLY_PHASE1", "PHASE1", "PHASE2"}
# In the second sentence of an NCI definition, a target counts only after a verb saying the drug acts on it.
ACTS_ON = re.compile(r"(?:binds? to|binds|targets?|directed against|inhibits?|blocks?|degrad\w+|antagoni[sz]es?|activates?)\b[^.;]{0,90}$", re.I)
ONC = re.compile(r"cancer|tumou?r|neoplasm|carcinoma|lymphoma|leuk[ae]{1,2}mi|myeloma|sarcoma|melanoma|gliom|glioblastoma|malignan|"
                 r"myelodysplas|NSCLC|SCLC|\bAML\b|mesothelioma|blastoma|myelofibrosis", re.I)

PRE = re.compile(r"(?:anti[- ]?|against (?:the |human |both )?|target(?:ing|s|ed)? (?:the |human |both )?|directed (?:against|to|at) (?:the |human )?|"
                 r"inhibitor of (?:the |human )?|inhibits (?:the )?|antagonist of |agonist of |degrader of |degrades |binds? (?:to )?(?:the |human )?|"
                 r"specific (?:for|to) |blocking |blocks |recogni[sz](?:es|ing) |[x×/] ?|and )$", re.I)
POST = re.compile(r"^[- ]?(?:\)|\]|,)?\s?(?:targeting|targeted|directed|specific|selective|inhibitor|antagonist|agonist|degrader|blocker|blockade|"
                  r"antibod|mAb|monoclonal|ADC\b|CAR\b|CAR[- ]T|TCR|bispecific|bsAb|[x×/] ?[A-Z]|antibody-drug|PROTAC|radioligand|vaccine|"
                  r"T[- ]cell engager|TKI\b|kinase inhibitor|modulator|binder|nanobody|fusion protein|conjugate|ligand|trap\b|"
                  r"chimeric|and [A-Z0-9-]{2,12} (?:bispecific|dual|inhibitor|antibod))", re.I)
SELECTION = re.compile(r"^[- ]?(?:\+|positive|pos\b|mutant|mutat|expressing|express|amplifi|alter|low\b|high\b|overexpress|negative|"
                       r"rearrang|wild|deficien|aberra|driven|fusion[- ]positive|status|gene)", re.I)
# Parts of the construct that are not the tumour target of a cell therapy
CELL_NON_TARGETS = {"4-1BB", "CD28", "CD27", "CD3", "OX40", "ICOS", "IL-15", "IL-7", "IL-12", "IL-18", "IL-21", "IL-2 pathway",
                    "PD-1", "TGF-β", "CD40", "CD16A", "NKG2D", "CCR4", "CXCR4", "IL-10", "CBL-B", "HPK1", "CD5", "CD7"}


TOK = re.compile(r"(?<![A-Za-z0-9])(?:\[?\d{2,3}[A-Za-z]{1,2}\]?[- ]?)?([A-Za-z]{1,8}[- ]?\d{2,}[A-Za-z0-9]*(?:-[A-Za-z0-9]+)?)")


def canonical(name, ncit_name):
    """One key per drug: NCI Thesaurus concept if linked, else the first code-like token, else the cleaned name."""
    if ncit_name:
        return "N:" + ncit_name.lower()
    m = TOK.search(name)
    if m:
        return "C:" + re.sub(r"[^a-z0-9]", "", m.group(1).lower())
    return "X:" + re.sub(r"[^a-z0-9]", "", name.lower())


def query_name(name, ncit_name):
    """Name used to look the drug up in the registry history check."""
    m = TOK.search(name)
    if m:
        return m.group(1)
    return re.sub(r"^(?:[A-D]\d? |of |product: |optional |coformulat\w+ |comparator )", "", name, flags=re.I).strip()


def first_sentence(text):
    return re.split(r"(?<=[a-z0-9\)])\.\s+(?=[A-Z])", text or "")[0]


def targets_free(text):
    return {name for name, rx in TARGET_RX.items() if rx.search(text)}


def targets_acted_on(text):
    found = set()
    for name, rx in TARGET_RX.items():
        for m in rx.finditer(text):
            if ACTS_ON.search(text[max(0, m.start() - 110):m.start()]):
                found.add(name)
                break
    return found


def sentence_n(text, n):
    parts = re.split(r"(?<=[a-z0-9\)])\.\s+(?=[A-Z])", text or "")
    return parts[n] if len(parts) > n else ""


def targets_in_context(text):
    found = set()
    for name, rx in TARGET_RX.items():
        for m in rx.finditer(text):
            before, after = text[max(0, m.start() - 40):m.start()], text[m.end():m.end() + 45]
            pre, post = bool(PRE.search(before)), bool(POST.search(after))
            if SELECTION.search(after) and not pre:
                continue
            if pre or post:
                found.add(name)
                break
    return found


def find_modality(text):
    for lab, rx in MODALITY_RX:
        if rx.search(text):
            return lab
    return None


def tidy(targets, modality):
    t = set(targets)
    if {"KRAS G12C", "KRAS G12D", "pan-KRAS / pan-RAS"} & t:
        t.discard("KRAS (other/unspecified)")
    if modality.startswith("CAR-T") or modality == "In vivo CAR":
        kept = t - CELL_NON_TARGETS
        t = kept if kept else t & {"CD5", "CD7"}
    if "EGFRvIII" in t:
        t.discard("EGFR")
    return t


def load_overrides():
    """alias -> (drug group, originator, originator country), from the deal tracker (make_originator_overrides.py)."""
    path = BASE / "data/originator_overrides.csv"
    if not path.exists():
        return {}
    return {r["alias"]: r for r in csv.DictReader(path.open(encoding="utf-8"))}


def main():
    overrides = load_overrides()
    agents = json.load((BASE / "data/agents_all.json").open())
    agents = [a for a in agents if a["first_start"] <= END]
    sites = collections.defaultdict(set)
    for a in agents:
        if a["sponsor_class"] == "INDUSTRY":
            sites[a["sponsor"]] |= set(a["countries"])

    rows, dropped = [], collections.Counter()
    for a in agents:
        name = a["agent"]
        if IMAGING_NAME.search(name) or any(rx.fullmatch(name.strip()) for rx in TARGET_RX.values()):
            dropped["imaging tracer, or a name that is only a target"] += 1
            continue
        if not ONC.search(" ".join((a["conditions"] or []) + (a["cond_mesh"] or []) + [a["title"] or ""])):
            dropped["not oncology"] += 1
            continue
        if BAD_NAME.search(name) or not (a["ncit_def"] or CODE.search(name) or INN.search(name)):
            dropped["not an identifiable agent name"] += 1
            continue

        ncit1 = first_sentence(a["ncit_def"]).split(" with potential ")[0]
        own = " . ".join(a["iv_descs"] + a["texts"])
        # drug type
        modality, m_src = None, ""
        for src, txt in (("NCI Thesaurus", ncit1), ("NCI Thesaurus", a["ncit_def"] or ""), ("Trial text naming the agent", own)):
            if txt:
                modality = find_modality(txt)
                if modality:
                    m_src = src
                    break
        if modality is None:
            modality, m_src = (find_modality(name), "Agent name") if find_modality(name) else ("Unclassified", "")
        # targets
        targets, t_src = set(), ""
        if ncit1:
            targets = tidy(targets_free(ncit1), modality)
            if not targets:
                targets = tidy(targets_acted_on(sentence_n(a["ncit_def"], 1).split(" with potential ")[0]), modality)
            t_src = "NCI Thesaurus" if targets else ""
        if not targets and own:
            targets = tidy(targets_in_context(own), modality)
            t_src = "Trial text naming the agent" if targets else ""
        if modality in ("Small molecule", "Protein degrader") and len(targets) > 3:
            targets, t_src = set(), ""   # multi-kinase lists: not a clean target assignment
        bsadc = modality == "Antibody-drug conjugate" and len(targets) >= 2

        tumour = next((lab for lab, rx in TUMOUR_RX if rx.search(" ".join(a["conditions"] or []) + " " + (a["title"] or ""))), "Other")
        if a["sponsor_class"] == "INDUSTRY":
            country = sponsor_country(a["sponsor"], sites[a["sponsor"]])
        else:
            sc = set(a["countries"])
            country = "China" if sc and sc <= {"China"} else ("US" if "United States" in sc else "Other")
        # Out-licensed drugs: credit the originator, and give every code name of the drug the same key so they merge.
        canon = canonical(name, a["ncit_name"])
        # Match on the agent's own name only (its registry "other names" can include combination partners).
        norm_keys = {canon[2:], re.sub(r"[^a-z0-9]", "", name.lower()), re.sub(r"[^a-z0-9]", "", (a["ncit_name"] or "").lower())}
        ov = next((overrides[k] for k in sorted(norm_keys) if k in overrides), None)
        registry_country, originator, basis = country, "", "registered sponsor"
        if ov:
            canon = "D:" + ov["drug_group"]
            country, originator, basis = ov["originator_country"], ov["originator"], "originator (deal " + ov["deal_id"] + ")"
        rows.append({
            "agent": name, "canon": canon, "query_name": query_name(name, a["ncit_name"]),
            "originator": originator, "country_basis": basis, "registry_sponsor_country": registry_country,
            "agent_id": a["agent_id"], "ncit_name": a["ncit_name"] or "", "first_start": a["first_start"],
            "year": a["first_start"][:4], "nct": a["attr_nct"], "sponsor": a["sponsor"], "sponsor_class": a["sponsor_class"],
            "first_phase": "|".join(a.get("first_phases") or []),
            "early_first_trial": int(bool(set(a.get("first_phases") or []) & EARLY_PHASES)),
            "in_cohort": int(a["sponsor_class"] == "INDUSTRY" and a["first_start"] >= START), "country": country,
            "site_countries": "|".join(a["countries"]), "modality": modality, "modality_source": m_src,
            "targets": "|".join(sorted(targets)), "n_targets": len(targets), "target_source": t_src,
            "bispecific_adc": int(bsadc), "tumour_group": tumour, "n_trials": a["n_trials"],
            "reached_phase2_3": int(any(p in ("PHASE2", "PHASE3") for p in a["later_phase"])), "title": a["title"],
        })
    # --- de-duplicate: one row per canonical drug, keeping the earliest record and the best annotation ---
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r["canon"]].append(r)
    merged = []
    for canon, g in groups.items():
        g.sort(key=lambda r: r["first_start"])
        keep = dict(g[0])
        best = max(g, key=lambda r: (bool(r["targets"]), r["modality"] != "Unclassified", r["target_source"] == "NCI Thesaurus"))
        for f in ("modality", "modality_source", "targets", "n_targets", "target_source", "bispecific_adc"):
            keep[f] = best[f]
        if keep["originator"]:
            keep["sponsor_class"] = "INDUSTRY"     # licensed from a company, whoever ran the first registered trial
        ind = next((r for r in g if r["sponsor_class"] == "INDUSTRY"), None)
        if keep["sponsor_class"] != "INDUSTRY" and ind and ind["first_start"][:4] == keep["first_start"][:4]:
            for f in ("sponsor", "sponsor_class", "country", "nct", "site_countries", "title"):
                keep[f] = ind[f]
        keep["n_name_variants"] = len(g)
        keep["n_trials"] = max(int(r["n_trials"]) for r in g)
        keep["reached_phase2_3"] = max(r["reached_phase2_3"] for r in g)
        keep["in_cohort"] = int(keep["sponsor_class"] == "INDUSTRY" and keep["first_start"] >= START)
        if keep["in_cohort"] and not keep["early_first_trial"]:
            keep["in_cohort"] = 0
            dropped["first trial is phase 3/4 or has no phase (not a first-in-human candidate)"] += 1
        merged.append(keep)
    dropped["duplicate name variants merged"] = len(rows) - len(merged)
    rows = merged
    # --- history check: registered anywhere on ClinicalTrials.gov (any phase, any disease) before 2020? ---
    hist_path = BASE / "data/history_check.json"
    hist = json.loads(hist_path.read_text()) if hist_path.exists() else {}
    for r in rows:
        r["prior_trials_before_2020"] = hist.get(r["query_name"], "")
        if r["in_cohort"] and hist.get(r["query_name"], 0) > 0:
            r["in_cohort"] = 0
            dropped["older drug: registered trial before 2020 (any phase or disease)"] += 1
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
    print(collections.Counter(r["n_targets"] for r in coh))


if __name__ == "__main__":
    main()
