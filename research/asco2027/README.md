# ASCO 2027 abstract: where China leads and where the US leads in new cancer drugs

**Status: second pass (17 Nov 2026). Numbers are preliminary until China's registry is merged and the validation sample is coded.**

**Full methods and how to reproduce every number: [`METHODS.md`](METHODS.md). One command: `./run_all.sh`.**

## Question
For cancer drugs entering human trials in 2020-2026, which targets and drug types are led by China-based
sponsors and which by US-based sponsors?

## Pipeline
| Step | Script | Output |
|---|---|---|
| 1. Download early-phase cancer trials (Phase 1 and 1/2, start 2010+) from ClinicalTrials.gov | `scripts/fetch_ctgov.py` | `data/raw/ctgov_phase1_oncology.jsonl` (frozen copy in `data/snapshot/`) |
| 2. Split combination regimens into agents, link to the NCI Thesaurus, find each agent's first registered trial | `scripts/build_agents.py` | `data/agents_all.json` (not committed) |
| 3. Assign sponsor country, drug type, targets, tumour group | `scripts/classify.py`, `scripts/lexicon.py`, `scripts/sponsor_lists.py` | `data/cohort.csv` |
| 3b. Look up each cohort agent's pre-2020 trial history, then re-run step 3 | `scripts/history_check.py` | `data/history_check.json` |
| 4. Analysis | `scripts/analyse.py` | `results/summary.json`, `results/new_classes.csv` |

The NCI Thesaurus flat file comes from https://evs.nci.nih.gov/ftp1/NCI_Thesaurus/Thesaurus.FLAT.zip
(unzip into `data/raw/ncit/`).

## Definitions
- **Cohort:** investigational agents whose first registered trial started Jan 2020 - Sep 2026, industry sponsor
  (n = 2,859). Name variants of one drug are merged (358 rows merged across all years), and agents with any
  ClinicalTrials.gov trial before 2020, in any phase or disease, are excluded (165; `scripts/history_check.py`).
  The count is of drug candidates, not approved or distinct "new drugs", and is still an upper bound: the same
  drug under two companies' code names is not yet merged.
- **Sponsor country:** headquarters of the sponsor's ultimate parent (China incl. Hong Kong / US / Other),
  from name rules plus hand-curated lists in `sponsor_lists.py`.
- **Class:** drug type + one or two targets, industry agents only. A class is "new" if no industry agent of that class was registered 2010-2019.
- **Target rule:** a target counts only if it is in the first sentence of the agent's NCI Thesaurus definition, or in a
  sentence naming the agent where the target is described as what the drug acts on (not a patient-selection marker).
- **Leader:** country of the sponsor of the earliest registered trial in a new class.

## Other files
- `abstract_draft.md` - draft abstract with the current numbers.
- `validation/validation_sample_150.csv` - random sample for manual coding (instructions in `validation/README.md`).

## Open problems
1. **China's registry is missing.** chinadrugtrials.org.cn blocks automated access. A CSV export is being collected
   separately; put it in `data/raw/` and it will need a merge step (match on drug name and sponsor, keep the earlier date).
2. **Uneven target coverage.** A target was assigned for 51% of China agents vs 66% of US agents; drug type for 74% vs 91%.
   Chinese company code names often have no public description. This biases target-level results against China.
3. **No formal validation yet.** An informal look at 40 new classes found about 5 questionable ones (wrong target or
   wrong sponsor country). The validation sample must be coded before any accuracy figure is reported.
4. **"First registered trial" is a proxy** for first-in-human.
5. **Results moved when the rules were tightened.** The first pass gave China 43% of China-plus-US "firsts", rising from
   24% (2020) to 65% (2025). The second pass gives 38% overall, rising from 32% (2020-2022) to 44% (2023-2026).
   Treat the trend as sensitive to method until validated.
6. Tumour-group coding is unreliable (multi-tumour trials are assigned to the first match) and is not reported.
7. 2026 covers January-September only.
8. The history check matches names loosely, so a few genuinely new agents with short code names (e.g. "A201") are
   wrongly excluded.
