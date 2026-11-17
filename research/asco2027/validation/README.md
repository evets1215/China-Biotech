# Validation sample

`validation_sample_150.csv` is a random sample of 150 cohort agents (60 China, 60 US, 30 other; seed 2027).

A human coder who has not seen the analysis should fill the `coder_*` columns for each row, using the trial page
(link in `nct`) and the company's own pipeline page or press releases:

| Column | What to enter |
|---|---|
| `coder_country` | Headquarters country of the sponsor's ultimate parent: China (incl. Hong Kong), US, or Other |
| `coder_drug_type` | One of the drug types in `scripts/lexicon.py` (e.g. Small molecule, Antibody-drug conjugate) |
| `coder_targets` | The drug's molecular target(s), separated by `|`; leave empty if not publicly disclosed |
| `coder_is_new_cancer_drug_yes_no` | "no" if the row is not a new investigational cancer drug (e.g. an approved drug, a dose label, an imaging agent) |
| `coder_notes` | Source used, or anything unclear |

The abstract should report agreement between the `auto_*` and `coder_*` columns for country, drug type and target.
Ideally two coders work independently so that inter-coder agreement can be reported as well.
