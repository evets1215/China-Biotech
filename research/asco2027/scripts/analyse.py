"""Leadership analysis: China vs US in new oncology agents, targets and drug types, 2020-2026.

Everything here is restricted to industry-sponsored agents.
A "class" is a drug type plus its target set (1 or 2 targets), e.g. "Antibody-drug conjugate | B7-H3".
A class is "new" if no industry agent of that class was registered in 2010-2019.
The "leader" is the country of the sponsor whose agent entered the registry first.
"""
import collections
import csv
import json
import statistics
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
R = [r for r in csv.DictReader((BASE / "data/cohort.csv").open(encoding="utf-8")) if r["sponsor_class"] == "INDUSTRY"]
for r in R:
    r["in_cohort"] = int(r["in_cohort"])
    r["tset"] = tuple(r["targets"].split("|")) if r["targets"] else ()
coh = [r for r in R if r["in_cohort"]]
out = {"cohort_n": len(coh), "cohort_by_country": dict(collections.Counter(r["country"] for r in coh))}


def pct(a, b):
    return round(100 * a / b, 1) if b else None


def share(c):
    return {"China": c["China"], "US": c["US"], "Other": c["Other"], "china_share_of_cn_us": pct(c["China"], c["China"] + c["US"])}


def months(s):
    return int(s[:4]) * 12 + int(s[5:7])


# 1. volume by year
vol = collections.defaultdict(collections.Counter)
for r in coh:
    vol[r["year"]][r["country"]] += 1
out["new_agents_by_year"] = {y: share(vol[y]) for y in sorted(vol)}

# 2. drug type mix
mod = collections.defaultdict(collections.Counter)
for r in coh:
    mod[r["modality"]][r["country"]] += 1
out["by_modality"] = {m: share(c) for m, c in sorted(mod.items(), key=lambda kv: -sum(kv[1].values()))}
# early vs late period, to show the trend per drug type
trend = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
for r in coh:
    trend[r["modality"]]["2020-2022" if r["year"] <= "2022" else "2023-2026"][r["country"]] += 1
out["modality_trend_china_share"] = {m: {p: pct(c["China"], c["China"] + c["US"]) for p, c in sorted(d.items())} for m, d in trend.items()}

# 3. first-to-clinic classes
def classes(max_targets):
    known = [r for r in R if r["tset"] and len(r["tset"]) <= max_targets and r["modality"] != "Unclassified"]
    by_class = collections.defaultdict(list)
    for r in known:
        by_class[(r["modality"], r["tset"])].append(r)
    seen_targets = {t for r in R if r["first_start"] < "2020-01" for t in r["tset"]}
    res = []
    for key, members in by_class.items():
        members.sort(key=lambda r: r["first_start"])
        first = members[0]
        if first["first_start"] < "2020-01":
            continue
        tie = {m["country"] for m in members if m["first_start"] == first["first_start"]}
        def first_of(c):
            return next((m["first_start"] for m in members if m["country"] == c), "")
        ts = key[1]
        novelty = ("new target" if any(t not in seen_targets for t in ts)
                   else "new target pair" if len(ts) > 1 else "new drug type on known target")
        res.append({"modality": key[0], "targets": "|".join(ts), "novelty": novelty, "first_start": first["first_start"],
                    "leader": first["country"] if len(tie) == 1 else "Tie", "first_agent": first["agent"],
                    "first_sponsor": first["sponsor"], "first_nct": first["nct"], "n_agents": len(members),
                    "n_china": sum(m["country"] == "China" for m in members), "n_us": sum(m["country"] == "US" for m in members),
                    "china_first": first_of("China"), "us_first": first_of("US")})
    return sorted(res, key=lambda c: c["first_start"])


def summarise(cl):
    s = {"n": len(cl), "leader": share(collections.Counter(c["leader"] for c in cl)),
         "tie": sum(c["leader"] == "Tie" for c in cl)}
    by = collections.defaultdict(collections.Counter)
    for c in cl:
        by[c["first_start"][:4]][c["leader"]] += 1
    s["by_year"] = {y: share(c) for y, c in sorted(by.items())}
    per = collections.defaultdict(collections.Counter)
    for c in cl:
        per["2020-2022" if c["first_start"] < "2023" else "2023-2026"][c["leader"]] += 1
    s["by_period"] = {p: share(c) for p, c in sorted(per.items())}
    bm = collections.defaultdict(collections.Counter)
    for c in cl:
        bm[c["modality"]][c["leader"]] += 1
    s["by_modality"] = {m: share(c) for m, c in sorted(bm.items(), key=lambda kv: -sum(kv[1].values()))}
    bn = collections.defaultdict(collections.Counter)
    for c in cl:
        bn[c["novelty"]][c["leader"]] += 1
    s["by_novelty"] = {k: share(c) for k, c in bn.items()}
    lag = {"China first": [], "US first": []}
    for c in cl:
        if c["china_first"] and c["us_first"] and c["china_first"] != c["us_first"]:
            d = months(c["us_first"]) - months(c["china_first"])
            lag["China first" if d > 0 else "US first"].append(abs(d))
    s["follower_lag_months"] = {k: {"n": len(v), "median": statistics.median(v) if v else None} for k, v in lag.items()}
    s["entered_by_both"] = sum(1 for c in cl if c["china_first"] and c["us_first"])
    return s


primary = classes(2)
out["new_classes_primary_1_or_2_targets"] = summarise(primary)
out["new_classes_sensitivity_single_target"] = summarise(classes(1))

# 4. breadth and concentration
br = {}
for country in ("China", "US"):
    cnt, n = collections.Counter(), 0
    for r in coh:
        if r["country"] == country and r["tset"]:
            n += 1
            cnt.update(r["tset"])
    tot = sum(cnt.values())
    br[country] = {"agents_with_target": n, "unique_targets": len(cnt),
                   "top10_share_pct": pct(sum(v for _, v in cnt.most_common(10)), tot),
                   "hhi": round(sum((v / tot) ** 2 for v in cnt.values()) * 10000), "top10": cnt.most_common(10)}
only_cn = {t for r in coh if r["country"] == "China" for t in r["tset"]}
only_us = {t for r in coh if r["country"] == "US" for t in r["tset"]}
br["targets_only_china"] = sorted(only_cn - only_us)
br["targets_only_us"] = sorted(only_us - only_cn)
out["target_breadth"] = br

# 5. per-target share (>= 12 China+US agents)
tc = collections.defaultdict(collections.Counter)
for r in coh:
    for t in r["tset"]:
        tc[t][r["country"]] += 1
rows = [(t, c["China"], c["US"], pct(c["China"], c["China"] + c["US"])) for t, c in tc.items() if c["China"] + c["US"] >= 12]
out["target_china_share"] = sorted(rows, key=lambda x: -x[3])

# 6. tumour group
tg = collections.defaultdict(collections.Counter)
for r in coh:
    tg[r["tumour_group"]][r["country"]] += 1
out["by_tumour_group"] = {g: share(c) for g, c in sorted(tg.items(), key=lambda kv: -sum(kv[1].values()))}

# 7. progression: agents first registered 2020-2022 with a later Phase 2 or 3 trial in the dataset
prog = {}
for country in ("China", "US"):
    sub = [r for r in coh if r["country"] == country and r["year"] <= "2022"]
    prog[country] = {"n": len(sub), "multi_trial_pct": pct(sum(int(r["n_trials"]) > 1 for r in sub), len(sub))}
out["agents_2020_2022_with_more_than_one_trial"] = prog

# 8. coverage, and how far it could move the headline
cov = {}
for country in ("China", "US", "Other"):
    sub = [r for r in coh if r["country"] == country]
    cov[country] = {"n": len(sub), "target_identified_pct": pct(sum(1 for r in sub if r["tset"]), len(sub)),
                    "drug_type_identified_pct": pct(sum(1 for r in sub if r["modality"] != "Unclassified"), len(sub)),
                    "ncit_source_pct": pct(sum(1 for r in sub if r["target_source"] == "NCI Thesaurus"), len(sub))}
out["coverage"] = cov

(BASE / "results/summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
with (BASE / "results/new_classes.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(primary[0]))
    w.writeheader()
    w.writerows(primary)
print(json.dumps(out, indent=1, ensure_ascii=False))
