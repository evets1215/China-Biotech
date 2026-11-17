"""For each cohort agent, count ClinicalTrials.gov studies (any phase, any condition) that used it before 2020.

A non-zero count means the agent is not new in 2020-2026 (e.g. an approved drug, or one first tested outside
phase 1 oncology). Results are cached in data/history_check.json. Run after classify.py, then run classify.py again.
"""
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "data/history_check.json"
cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
names = sorted({r["query_name"] for r in csv.DictReader((BASE / "data/cohort.csv").open(encoding="utf-8"))
                if r["sponsor_class"] == "INDUSTRY" and r["first_start"] >= "2020-01" and len(r["query_name"]) >= 4})
todo = [n for n in names if n not in cache]
print("agents", len(names), "to query", len(todo), flush=True)


def count(name):
    q = {"query.intr": '"%s"' % name.replace('"', ""), "filter.advanced": "AREA[StartDate]RANGE[MIN,2019-12-31]",
         "pageSize": 1, "countTotal": "true", "fields": "NCTId", "format": "json"}
    url = "https://clinicaltrials.gov/api/v2/studies?" + urllib.parse.urlencode(q)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research-script/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return name, json.load(r).get("totalCount", 0)
        except Exception as e:
            time.sleep(1.5 * (attempt + 1))
    return name, None


with ThreadPoolExecutor(max_workers=4) as ex:
    for i, (name, n) in enumerate(ex.map(count, todo), 1):
        if n is not None:
            cache[name] = n
        if i % 200 == 0:
            CACHE.write_text(json.dumps(cache))
            print(i, flush=True)
CACHE.write_text(json.dumps(cache, indent=0, sort_keys=True))
print("done; with prior trials:", sum(1 for n in names if cache.get(n, 0) > 0), "| failed:", sum(1 for n in names if n not in cache))
