"""Download oncology Phase 1 (incl. Phase 1/2) interventional trials from ClinicalTrials.gov API v2.

Output: data/raw/ctgov_phase1_oncology.jsonl (one trimmed study per line).
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "ctgov_phase1_oncology.jsonl"
COND = ("cancer OR neoplasm OR tumor OR tumour OR carcinoma OR lymphoma OR leukemia OR myeloma OR sarcoma "
        "OR melanoma OR glioma OR glioblastoma OR malignancy OR malignant")
ADV = ("AREA[StudyType]INTERVENTIONAL AND AREA[Phase](EARLY_PHASE1 OR PHASE1) "
       "AND AREA[StartDate]RANGE[2010-01-01,MAX]")
FIELDS = ",".join([
    "NCTId", "BriefTitle", "OfficialTitle", "BriefSummary", "DetailedDescription", "ArmGroupDescription", "ArmGroupLabel", "Phase", "StartDate", "StartDateType",
    "OverallStatus", "EnrollmentCount", "LeadSponsorName", "LeadSponsorClass", "CollaboratorName",
    "Condition", "Keyword", "InterventionType", "InterventionName", "InterventionOtherName",
    "InterventionDescription", "LocationCountry", "StudyFirstSubmitDate", "ConditionMeshTerm",
    "InterventionMeshTerm",
])


def get(url):
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research-script/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:  # retry transient errors
            print("retry", attempt, e, file=sys.stderr)
            time.sleep(2 ** attempt)
    raise SystemExit("failed: " + url)


def trim(s):
    p = s["protocolSection"]
    ident, status, design = p.get("identificationModule", {}), p.get("statusModule", {}), p.get("designModule", {})
    spons, arms = p.get("sponsorCollaboratorsModule", {}), p.get("armsInterventionsModule", {})
    locs = p.get("contactsLocationsModule", {}).get("locations", [])
    d = s.get("derivedSection", {})
    return {
        "nct": ident.get("nctId"),
        "title": ident.get("briefTitle"),
        "official_title": ident.get("officialTitle"),
        "summary": p.get("descriptionModule", {}).get("briefSummary"),
        "detail": p.get("descriptionModule", {}).get("detailedDescription"),
        "arms": [" ".join(filter(None, [g.get("label"), g.get("description")])) for g in arms.get("armGroups", [])],
        "phases": design.get("phases"),
        "start": (status.get("startDateStruct") or {}).get("date"),
        "start_type": (status.get("startDateStruct") or {}).get("type"),
        "first_submit": status.get("studyFirstSubmitDate"),
        "status": status.get("overallStatus"),
        "enrollment": (design.get("enrollmentInfo") or {}).get("count"),
        "sponsor": (spons.get("leadSponsor") or {}).get("name"),
        "sponsor_class": (spons.get("leadSponsor") or {}).get("class"),
        "collaborators": [c.get("name") for c in spons.get("collaborators", [])],
        "conditions": p.get("conditionsModule", {}).get("conditions"),
        "keywords": p.get("conditionsModule", {}).get("keywords"),
        "interventions": [{"type": i.get("type"), "name": i.get("name"), "other": i.get("otherNames"),
                           "desc": i.get("description")} for i in arms.get("interventions", [])],
        "countries": sorted({l.get("country") for l in locs if l.get("country")}),
        "cond_mesh": [m.get("term") for m in d.get("conditionBrowseModule", {}).get("meshes", [])],
        "int_mesh": [m.get("term") for m in d.get("interventionBrowseModule", {}).get("meshes", [])],
    }


def main():
    token, n = None, 0
    with OUT.open("w") as fh:
        while True:
            q = {"query.cond": COND, "filter.advanced": ADV, "fields": FIELDS, "pageSize": 1000, "format": "json"}
            if token:
                q["pageToken"] = token
            else:
                q["countTotal"] = "true"
            data = get("https://clinicaltrials.gov/api/v2/studies?" + urllib.parse.urlencode(q))
            if "totalCount" in data:
                print("total", data["totalCount"], flush=True)
            for s in data.get("studies", []):
                fh.write(json.dumps(trim(s), ensure_ascii=False) + "\n")
                n += 1
            token = data.get("nextPageToken")
            print(n, flush=True)
            if not token:
                break
    print("done", n)


if __name__ == "__main__":
    main()
