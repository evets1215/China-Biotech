# ASCO 2027 abstract: where China leads and where the US leads in new cancer drugs

**Status: preliminary pilot (17 Nov 2026). Numbers are not yet abstract-ready - see "Known problems".**

## Question
For cancer drugs entering human trials in 2020-2026, which targets and drug types are led by China-based
sponsors and which by US-based sponsors?

## Pipeline
| Step | Script | Output |
|---|---|---|
| 1. Download early-phase cancer trials (Phase 1 and 1/2, start 2010+) from ClinicalTrials.gov | `scripts/fetch_ctgov.py` | `data/raw/ctgov_phase1_oncology.jsonl` (not committed; re-run to recreate) |
| 2. Split combination regimens into agents, link to the NCI Thesaurus, find each agent's first registered trial | `scripts/build_agents.py` | `data/agents_all.json` (not committed) |
| 3. Assign sponsor country, drug type, targets, tumour group | `scripts/classify.py`, `scripts/lexicon.py`, `scripts/sponsor_lists.py` | `data/cohort.csv` |
| 4. Analysis | `scripts/analyse.py` | `results/summary.json`, `results/new_classes.csv` |

The NCI Thesaurus flat file comes from https://evs.nci.nih.gov/ftp1/NCI_Thesaurus/Thesaurus.FLAT.zip
(unzip into `data/raw/ncit/`).

## Definitions
- **Cohort:** agents whose first registered trial started Jan 2020 - Sep 2026, industry sponsor (n = 3,361).
- **Sponsor country:** headquarters of the sponsor's ultimate parent (China incl. Hong Kong / US / Other),
  from name rules plus hand-curated lists in `sponsor_lists.py`.
- **Class:** drug type + set of targets. A class is "new" if no agent of that class was registered 2010-2019.
- **Leader:** country of the sponsor of the earliest registered trial in a new class.

## Known problems (must fix before submission)
1. **Registry coverage.** Only ClinicalTrials.gov. Trials registered only on China's registry
   (chinadrugtrials.org.cn) are missing, which under-counts China.
2. **Uneven target coverage.** A target was identified for 55% of China agents vs 65% of US agents; drug type for
   70% vs 87%. Chinese company code names often have no public description.
3. **Classification errors.** A spot check of 30 new classes found clear errors (combination partners counted as
   targets, cell therapies with long target lists, wrong first sponsor). No formal validation has been done.
4. **"First registered trial" is a proxy** for first-in-human.
5. **Class analysis mixes sponsors:** the cohort is industry-only, but class novelty is judged against all sponsors.
6. 2026 covers January-September only.
