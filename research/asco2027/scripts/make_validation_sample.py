"""Draw the validation sample: 150 cohort agents (60 China, 60 US, 30 other), fixed random seed 2027."""
import csv
import random
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
R = [r for r in csv.DictReader((BASE / "data/cohort.csv").open(encoding="utf-8")) if r["in_cohort"] == "1"]
random.seed(2027)
pick = []
for country, n in (("China", 60), ("US", 60), ("Other", 30)):
    pick += random.sample([r for r in R if r["country"] == country], n)
random.shuffle(pick)
cols = ["agent", "nct", "sponsor", "first_start", "title", "auto_country", "auto_drug_type", "auto_targets",
        "coder_country", "coder_drug_type", "coder_targets", "coder_is_new_cancer_drug_yes_no", "coder_notes"]
with (BASE / "validation/validation_sample_150.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(cols)
    for r in pick:
        w.writerow([r["agent"], "https://clinicaltrials.gov/study/" + r["nct"], r["sponsor"], r["first_start"], r["title"],
                    r["country"], r["modality"], r["targets"], "", "", "", "", ""])
print("validation sample:", len(pick))
