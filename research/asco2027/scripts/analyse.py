"""Leadership analysis: China vs US in new oncology agents, targets and drug types, 2020-2026.

A "class" is a drug type plus its set of targets (e.g. Antibody-drug conjugate | B7-H3).
A class is "new" if no agent of that class appears in the registry before 2020 (look-back to 2010).
"""
import collections
import csv
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
R = list(csv.DictReader((BASE / "data/cohort.csv").open(encoding="utf-8")))
for r in R:
    r["in_cohort"] = int(r["in_cohort"])
    r["tset"] = tuple(r["targets"].split("|")) if r["targets"] else ()
coh = [r for r in R if r["in_cohort"]]
out = {}


def pct(a, b):
    return round(100 * a / b, 1) if b else None


# 1. volume by year and country
vol = collections.defaultdict(collections.Counter)
for r in coh:
    vol[r["year"]][r["country"]] += 1
out["new_agents_by_year"] = {y: dict(vol[y]) for y in sorted(vol)}

# 2. drug type mix, China vs US (all cohort agents with a drug type)
mod = collections.defaultdict(collections.Counter)
for r in coh:
    mod[r["modality"]][r["country"]] += 1
out["by_modality"] = {m: {**dict(c), "china_share_of_cn_us": pct(c["China"], c["China"] + c["US"])}
                      for m, c in sorted(mod.items(), key=lambda kv: -sum(kv[1].values()))}

# 3. first-to-clinic: new classes (drug type + target set), judged against all agents since 2010
known = [r for r in R if r["tset"] and r["modality"] != "Unclassified"]
by_class = collections.defaultdict(list)
for r in known:
    by_class[(r["modality"], r["tset"])].append(r)
new_classes = []
for key, members in by_class.items():
    members.sort(key=lambda r: r["first_start"])
    first = members[0]
    if first["first_start"] < "2020-01":
        continue
    # tie: several agents in the same first month
    lead_month = first["first_start"]
    leaders = {m["country"] for m in members if m["first_start"] == lead_month}
    leader = first["country"] if len(leaders) == 1 else "Tie"
    def first_of(c):
        return next((m["first_start"] for m in members if m["country"] == c), None)
    new_classes.append({"modality": key[0], "targets": "|".join(key[1]), "first_start": lead_month, "leader": leader,
                        "first_agent": first["agent"], "first_sponsor": first["sponsor"], "n_agents": len(members),
                        "china_first": first_of("China"), "us_first": first_of("US"),
                        "n_china": sum(m["country"] == "China" for m in members), "n_us": sum(m["country"] == "US" for m in members)})
new_classes.sort(key=lambda c: c["first_start"])
lead = collections.Counter(c["leader"] for c in new_classes)
out["new_classes_total"] = len(new_classes)
out["new_classes_leader"] = dict(lead)
by_year = collections.defaultdict(collections.Counter)
for c in new_classes:
    by_year[c["first_start"][:4]][c["leader"]] += 1
out["new_classes_leader_by_year"] = {y: {**dict(c), "china_share_of_cn_us": pct(c["China"], c["China"] + c["US"])} for y, c in sorted(by_year.items())}
by_mod = collections.defaultdict(collections.Counter)
for c in new_classes:
    by_mod[c["modality"]][c["leader"]] += 1
out["new_classes_leader_by_modality"] = {m: {**dict(c), "china_share_of_cn_us": pct(c["China"], c["China"] + c["US"])}
                                         for m, c in sorted(by_mod.items(), key=lambda kv: -sum(kv[1].values()))}

# 4. novelty type: new target (never seen in any drug type before 2020) vs new drug type on a known target
seen_before = set()
for r in known:
    if r["first_start"] < "2020-01":
        seen_before.update(r["tset"])
nov = collections.defaultdict(collections.Counter)
for c in new_classes:
    ts = c["targets"].split("|")
    kind = "new target" if any(t not in seen_before for t in ts) else ("new combination of known targets" if len(ts) > 1 else "new drug type on known target")
    c["novelty"] = kind
    nov[kind][c["leader"]] += 1
out["new_classes_by_novelty"] = {k: {**dict(c), "china_share_of_cn_us": pct(c["China"], c["China"] + c["US"])} for k, c in nov.items()}

# 5. follower lag where both countries entered a new class
lags = {"China first": [], "US first": []}
for c in new_classes:
    if c["china_first"] and c["us_first"] and c["china_first"] != c["us_first"]:
        def m(s):
            return int(s[:4]) * 12 + int(s[5:7])
        d = m(c["us_first"]) - m(c["china_first"])
        (lags["China first"] if d > 0 else lags["US first"]).append(abs(d))
import statistics
out["follower_lag_months"] = {k: {"n": len(v), "median": statistics.median(v) if v else None} for k, v in lags.items()}
out["classes_entered_by_both"] = sum(1 for c in new_classes if c["china_first"] and c["us_first"])
out["classes_china_only"] = sum(1 for c in new_classes if c["china_first"] and not c["us_first"])
out["classes_us_only"] = sum(1 for c in new_classes if c["us_first"] and not c["china_first"])

# 6. breadth and concentration of targets among cohort agents with a target
br = {}
for country in ("China", "US"):
    cnt = collections.Counter()
    n = 0
    for r in coh:
        if r["country"] == country and r["tset"]:
            n += 1
            for t in r["tset"]:
                cnt[t] += 1
    tot = sum(cnt.values())
    top10 = sum(v for _, v in cnt.most_common(10))
    br[country] = {"agents_with_target": n, "unique_targets": len(cnt), "top10_share_pct": pct(top10, tot),
                   "hhi": round(sum((v / tot) ** 2 for v in cnt.values()) * 10000), "top10": cnt.most_common(10)}
out["target_breadth"] = br

# 7. per-target leadership among frequent targets (>= 12 cohort agents from China+US)
tc = collections.defaultdict(collections.Counter)
for r in coh:
    for t in r["tset"]:
        tc[t][r["country"]] += 1
rows = []
for t, c in tc.items():
    n = c["China"] + c["US"]
    if n >= 12:
        rows.append((t, c["China"], c["US"], pct(c["China"], n)))
rows.sort(key=lambda x: -x[3])
out["target_china_share"] = rows

# 8. coverage
cov = {}
for country in ("China", "US", "Other"):
    sub = [r for r in coh if r["country"] == country]
    cov[country] = {"n": len(sub), "target_identified_pct": pct(sum(1 for r in sub if r["tset"]), len(sub)),
                    "drug_type_identified_pct": pct(sum(1 for r in sub if r["modality"] != "Unclassified"), len(sub))}
out["coverage"] = cov

(BASE / "results/summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
with (BASE / "results/new_classes.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(new_classes[0]))
    w.writeheader()
    w.writerows(new_classes)
print(json.dumps(out, indent=1, ensure_ascii=False))
