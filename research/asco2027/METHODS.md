# Methods

Detailed, reproducible methods for *"Where China leads and where the United States leads: targets and drug types of
investigational cancer agents entering first-in-human trials, 2020-2026"*.

Every number in `abstract_draft.md` is produced by the code in `scripts/` from the two input files in
`data/snapshot/`. Section 9 gives the one command that regenerates them and the checksums to compare against.

---

> **Accuracy note.** These methods reproduce the numbers exactly. That is not the same as the numbers being
> correct. Version 1 of this pipeline failed an accuracy audit; this is version 2, rebuilt to fix the audit
> findings (`AUDIT.md`). Version 2 has had the same author's re-check but **no independent validation yet**.

## 1. Study design

Retrospective cross-sectional analysis of public clinical trial registry records. No patient-level data were used.

**Unit of analysis:** the investigational agent (a drug candidate), not the trial.

**Question:** among investigational cancer agents whose first registered trial started between January 2020 and
September 2026, which molecular targets and drug types are led by China-based sponsors and which by US-based sponsors?

## 2. Data sources

| Source | What it provides | Retrieved | Frozen copy | SHA-256 |
|---|---|---|---|---|
| ClinicalTrials.gov API v2 (`https://clinicaltrials.gov/api/v2/studies`) | Trial records | 17 Nov 2026 | `data/snapshot/ctgov_oncology_all_2026-11-17.jsonl.gz.part00` and `.part01` (one gzip file split in two) | `8b023521...632ff9335` (uncompressed file) |
| NCI Thesaurus flat file (`https://evs.nci.nih.gov/ftp1/NCI_Thesaurus/Thesaurus.FLAT.zip`) | Drug names, synonyms and definitions | 17 Nov 2026 | `data/snapshot/NCI_Thesaurus_FLAT_2026-11-17.zip` | `bbb28631...176d6736` |
| ClinicalTrials.gov API v2, per-agent count queries | Whether each agent had any trial before 2020 | 17 Nov 2026 | `data/history_check.json` | - |

Full checksums: `8b023521f6a9b1976718fe10fbd267d81d20f13004f25ed3bb17332632ff9335` and
`bbb28631799046e1227ac221636c2de6bb1d2b79bf6c8e0a1143a797176d6736`.

China's drug trial registry (chinadrugtrials.org.cn) is **not** included: it blocks automated access. See section 8.

## 3. Trial retrieval (`scripts/fetch_ctgov.py`)

One API query, paged 1,000 records at a time:

- **Condition (`query.cond`):** `cancer OR neoplasm OR tumor OR tumour OR carcinoma OR lymphoma OR leukemia OR myeloma
  OR sarcoma OR melanoma OR glioma OR glioblastoma OR malignancy OR malignant`
- **Filter (`filter.advanced`):** `AREA[StudyType]INTERVENTIONAL AND AREA[InterventionType](DRUG OR BIOLOGICAL OR
  GENETIC OR COMBINATION_PRODUCT)`

There is **no phase filter and no date filter**. Sponsors update a trial's phase label as it grows, so a
first-in-human trial can later be labelled phase 2 (version 1 kept only trials currently labelled phase 1 and
missed such drugs). All dates are kept so that the history of each target before 2020 is as complete as the
registry allows.

Fields kept per trial: NCT number, brief and official title, brief summary, detailed description, arm labels and
descriptions, phase, start date, first-submission date, status, enrolment, lead sponsor name and class,
collaborators, conditions, keywords, condition and intervention MeSH terms, site countries, and every intervention
(type, name, other names, description).

**Result:** 72,031 trials.

## 4. From trials to agents (`scripts/build_agents.py`)

0. **Non-therapeutic trials are dropped first** (title matches healthy volunteers, bioavailability, bioequivalence,
   biosimilar, mass balance, food effect, drug-drug interaction, supportive care, imaging/PET, dosimetry or
   microdosing; `NON_THERAPEUTIC`). 69,569 trials remain. The agent is kept if it has other trials.
1. **Interventions considered:** types `DRUG`, `BIOLOGICAL`, `GENETIC` and `COMBINATION_PRODUCT`.
2. **Splitting combinations:** text in parentheses is removed, then the intervention name is split on `+ ; , /`,
   and the words *and, plus, with, in combination with, combined with, followed by, or, &*. Each part is a candidate
   agent.
3. **Linking to the NCI Thesaurus:** names are normalised (lower case, non-alphanumeric characters removed) and
   matched to any synonym of an NCI Thesaurus concept that has a definition and a drug-like semantic type (the list
   is `SEM_OK` in the script; 30,178 concepts, 139,377 synonyms). If the full name does not match, trailing words
   are dropped one at a time ("Olaparib 200" matches *olaparib*). For single-agent interventions, the registry's
   "other names" are also tried.
4. **Unlinked names:** dose amounts and a fixed list of non-name words (*injection, tablets, cohort, dose
   escalation, placebo...*; `NOISE` in the script) are removed. The remainder is kept if it is at least three
   characters, not purely numeric, and at most four words.
5. **Agent identifier:** the NCI Thesaurus concept code if linked, otherwise the normalised name.
6. **First registered trial:** the trial with the earliest start date (first-submission date if the start date is
   missing), at month precision.
7. **Sponsor attribution:** the agent is attributed to the sponsor of the earliest trial that names the agent in
   its brief or official title, provided that trial starts within 12 months of the agent's first trial; otherwise to
   the sponsor of the first trial. This prevents a new drug being attributed to the sponsor of a trial in which it
   is only a combination partner.
8. **Descriptive text:** for each agent, sentences that contain the agent's name are collected from the titles,
   summary and detailed description of its first 12 trials. Each sentence is cut into clauses at words that
   introduce another drug or an earlier treatment (*in combination with, plus, with or without, followed by,
   versus, prior, after, resistant to, treated with...*; `CLAUSE`), and **only clauses that name the agent are
   kept** (maximum 40). The first clause of the intervention description is also kept when the agent is the only
   drug in that intervention (maximum 5). This stops a partner drug's description being attributed to the agent.

**Result:** 20,722 agents.

## 5. Classification (`scripts/classify.py`)

### 5.1 Exclusions, applied in this order

| Step | Rule | Agents removed |
|---|---|---|
| a | Name is an imaging or carbon-14 isotope label (`IMAGING_NAME`), or is nothing but a target name (e.g. "VEGF-A") | 231 |
| b | Conditions, MeSH terms and title of the attributed trial contain no cancer term (`ONC`) | 1,196 |
| c | Name is not an identifiable agent: no NCI Thesaurus link, no code-like pattern (letters followed by two or more digits) and no international non-proprietary name suffix (*-mab, -tinib, -cel...*), or it is a dose/arm label | 7,655 |
| d | Name variants of the same drug merged (5.2) | 476 rows merged |
| e | Sponsor of the attributed trial is not industry, or first trial before January 2020 or after September 2026 | - |
| f | First trial is phase 3, phase 4 or has no phase (mostly biosimilars, generics and new formulations) | 111 |
| g | Any ClinicalTrials.gov trial before 2020, in any disease (5.3) | 154 |

**Study cohort: 2,969 agents.** All other agents (10,787 in total after steps a-d) stay in `data/cohort.csv` with
`in_cohort = 0`; they are the history against which new classes are judged (section 6).

### 5.2 De-duplication

Each agent gets one canonical key: its NCI Thesaurus concept name if linked; otherwise the first code-like token in
its name (for example "CBA-1205 3" and "CBA-1205 5" both give `cba1205`); otherwise the normalised name. Rows
sharing a key are merged. The merged record keeps the earliest first-trial date and the best available annotation
(a row with a target is preferred to one without).

### 5.3 History check (`scripts/history_check.py`)

For each cohort agent, the registry is queried for studies of **any phase and any disease** whose intervention
matches the agent's name as a quoted phrase and whose start date is on or before 31 December 2019. The name used is
the agent's code-like token if it has one, otherwise its cleaned name. Names shorter than four characters are not
queried. An agent with one or more matches is excluded as not new. Query results are cached in
`data/history_check.json` so that the exclusion is reproducible.

### 5.4 Sponsor country (`scripts/sponsor_lists.py`)

Each industry sponsor is assigned to **China** (including Hong Kong), **US** or **Other**, according to the
headquarters of its ultimate parent company. Rules are applied in this order:

1. Name contains an entry in the hand-curated US list (`US_OVERRIDE`, 42 entries) → US.
2. Name contains an entry in the hand-curated China list (`CHINA_EXTRA`, 51 entries: Chinese companies that
   register under a foreign subsidiary name) or matches the China name pattern (`CN`: Chinese city and province
   names and well-known Chinese companies) → China.
3. Name contains an entry in the hand-curated non-US, non-China list (`OTHER`, 195 entries, e.g. Novartis, Roche
   including Genentech, AstraZeneca, Takeda) → Other.
4. All of the sponsor's first-trial sites are in China → China.
5. Any site in the United States → US.
6. Otherwise → Other.

The curated lists were written by one person from general knowledge of company headquarters and have not been
independently checked.

### 5.5 Drug type (`MODALITY_RULES` in `scripts/lexicon.py`)

Twelve categories, tested in a fixed order with the first match taken: in vivo CAR; CAR-T / engineered cell
therapy; radioligand; antibody-drug conjugate; bispecific / multispecific antibody; protein degrader; cancer
vaccine; oncolytic virus; nucleic acid (mRNA/siRNA/antisense); cytokine / fusion protein; monoclonal antibody; small
molecule. Each is a regular expression of defining terms (for example *antibody-drug conjugate, ADC, vedotin,
deruxtecan* for antibody-drug conjugates).

The rules are applied to, in order: (1) the first sentence of the NCI Thesaurus definition, up to the words "with
potential"; (2) the whole NCI definition; (3) the agent's own descriptive text (section 4, step 8); (4) the agent
name. Agents matching none are "Unclassified".

### 5.6 Molecular target (`TARGETS` in `scripts/lexicon.py`)

A curated lexicon of 221 oncology targets, each with a regular expression of aliases (for example *HER2 = HER-2,
ERBB2, EGFR2*). Targets are accepted from only two kinds of text:

1. **NCI Thesaurus definition, first sentence** (up to "with potential"): every lexicon target mentioned is accepted.
   If the first sentence names none, the **second sentence** is used, but a target counts only if it follows a verb
   saying the drug acts on it (*binds to, targets, directed against, inhibits, blocks, degrades...*; `ACTS_ON`).
2. **Only if (1) gives none - the agent's own descriptive text:** a target is accepted only if it appears in a
   drug-describing context:
   - *preceded* within 40 characters by a term such as *anti-, against, targeting, directed against, inhibitor of,
     antagonist of, degrader of, binds to* (`PRE`), or
   - *followed* within 45 characters by a term such as *inhibitor, antagonist, antibody, ADC, CAR, bispecific,
     degrader, -targeting, × [another target]* (`POST`).

   A mention followed by a patient-selection term (*-positive, mutant, expressing, amplified, low, high...*;
   `SELECTION`) is rejected unless a preceding drug-context term is present. This stops "HER2-positive breast
   cancer" from being read as a HER2-targeted drug.

Clean-up rules: for cell therapies, parts of the engineered construct that are not the tumour target (for example
4-1BB, CD28, CD3, IL-15; `CELL_NON_TARGETS`) are removed; a generic "KRAS" mention is dropped when a specific KRAS
mutation or pan-KRAS is present; "EGFR" is dropped when EGFRvIII is present; small molecules or degraders with more
than three targets are treated as having no clean target assignment.

## 6. Outcomes (`scripts/analyse.py`)

Cohort outcomes use industry-sponsored agents only.

| Outcome | Definition |
|---|---|
| **Volume** | Number of cohort agents by sponsor country and year of first trial |
| **Drug type share** | For each drug type, China's agents ÷ (China's + US agents) |
| **Per-target share** | Same ratio per target, reported for targets with at least 12 China-plus-US agents |
| **Target breadth** | Number of distinct lexicon targets among a country's agents |
| **Target concentration** | Share of all target assignments accounted for by the country's 10 most common targets; Herfindahl-Hirschman index |
| **Class (primary)** | A target set of one or two targets, **regardless of drug type** (e.g. "B7-H3", or "PD-1 + VEGF"). Agents with no target or more than two targets are not assigned to a class |
| **New class** | A class for which **no agent of any sponsor type** (industry, academic or government) has a registered trial before January 2020 |
| **Leader** | Sponsor country of the earliest cohort agent in a new class. If cohort agents from different countries share the earliest month, the class is a tie (one occurred) |
| **Novelty type** | *New target*: at least one target was not carried by any agent before 2020. *New target pair*: two targets, each seen before 2020 but not together. *Known target, first time as sole target*: one target, seen before 2020 only alongside others |
| **Follower lag** | For new classes entered by both countries, months between the first China agent and the first US agent |

**Sensitivity analysis:** single-target classes only.

**Secondary analysis:** the class is defined as target set **plus drug type** (the version 1 definition). It is
reported for comparison only, because it counts the same target set again whenever the drug type label differs.

No hypothesis tests were performed; all results are descriptive counts and proportions.

## 7. Validation (not yet done)

`scripts/make_validation_sample.py` draws a stratified random sample of 150 cohort agents (60 China, 60 US, 30 other;
Python `random` seed 2027) into `validation/validation_sample_150.csv`. A coder who has not seen the automated
result records sponsor country, drug type, target(s) and whether the row is a genuine new cancer drug, using the
trial record and company sources (instructions in `validation/README.md`). Planned measures: percentage agreement
and Cohen's kappa between automated and manual coding for country and drug type; for targets, the proportion of
agents with an exact match and the proportion of automated targets confirmed. Two independent coders are preferred,
so that inter-coder agreement can also be reported.

A second sheet, `results/new_classes_review.csv`, lists every new class with its first agent, sponsor and trial, the
author's own doubts pre-filled (`author_flag`), and blank columns for a reviewer to confirm the targets, whether
the class really was new before 2020, and the originator's country.

**Until both are done, no accuracy figure can be stated.**

## 8. Limitations that affect interpretation

1. **Single registry.** Trials registered only on China's registry are missing, which under-counts China-based
   sponsors.
2. **Uneven annotation.** A target was assigned for 52% of China agents and 65% of US agents; a drug type for 73%
   and 90%. Target and class results therefore describe a smaller share of China's agents, and China's targets
   rely more often on trial text, the weaker source.
3. **False novelty remains possible.** If an older drug's target was not extracted, its class looks new. The
   author's re-check of the 182 new classes found about a dozen doubtful ones (`results/new_classes_review.csv`).
4. **Sponsor names reflect the current owner.** After an acquisition or licence the registry renames the sponsor on
   old trials, so some agents are credited to the acquirer's country, not the originator's.
5. **"First registered trial" is a proxy** for first-in-human.
6. **Cohort size is an upper bound.** The same drug under two companies' code names is not merged, and renamed
   drugs are linked only when the NCI Thesaurus lists both names.
7. **The history check is loose.** It matches names as phrases, so a few new agents with short code names are
   wrongly excluded.
8. **Target lexicon is finite** (221 targets). Targets outside it are not counted, which understates breadth for
   both countries and under-counts truly novel targets.
9. **Sponsor country lists are hand-curated** by one person and unvalidated.
10. **Partial final year.** 2026 covers January to September.
11. **Results have moved with each revision of the rules** (see `AUDIT.md`), which is itself a warning about
    how far to trust any single figure before validation.

## 9. Reproducing the results

Requirements: Python 3.10 or later (tested on 3.13.18), standard library only; `bash`, `gunzip`, `sha256sum`.

```bash
cd research/asco2027
```

```bash
./run_all.sh
```

This unpacks the frozen inputs, runs the five steps in order (`build_agents.py`, `classify.py`,
`history_check.py`, `classify.py` again, `analyse.py`), draws the validation sample, and prints checksums.
It takes about ten minutes. The output files should have these SHA-256 checksums:

| File | SHA-256 |
|---|---|
| `data/cohort.csv` | `71b2529251b83cb444fcafcee569fc433aa7a35f10f992f970d83e3926d6301a` |
| `results/summary.json` | `e1977ff43c9c6f2186ebbb1c9b7d2698df3c7ad37b34e8953f08ca0d1ab3a382` |
| `results/new_classes.csv` | `50a3950310b58921563d0d35da067132f173c83bef73c4b8e2d320d55d333b06` |
| `results/new_classes_review.csv` | `e567aebfe82293548277ec887acbdaef5afd13c34102df8b59a0c88629972c1e` |
| `validation/validation_sample_150.csv` | `b5eacefad7dea5194f7804bbc19e98706eae627be56a029b345b65d3e93f5664` |

The pipeline was run twice from the frozen inputs with different Python hash seeds and gave identical checksums.

To repeat the study on current data instead (numbers will differ, because the registry changes daily):

```bash
./run_all.sh --refresh
```

### Where each abstract number comes from

| Abstract statement | Key in `results/summary.json` |
|---|---|
| 2,969 agents; 1,180 China; 1,054 US | `cohort_n`, `cohort_by_country` |
| Yearly counts | `new_agents_by_year` |
| Drug type shares | `by_modality[*].china_share_of_cn_us` |
| Target assigned for 52% vs 65% | `coverage[*].target_identified_pct` |
| 180 vs 140 targets; top-10 share 27% vs 37% | `target_breadth` |
| 182 new classes; 88 US, 49 China, 44 other, 1 tie | `new_classes_primary_target_set.leader`, `.tie` |
| 29% rising to 42% | `new_classes_primary_target_set.by_period` |
| New targets 23 vs 4; new target pairs 62 vs 45 | `new_classes_primary_target_set.by_novelty` |

The list of new classes, with the first agent, sponsor and trial for each, is `results/new_classes.csv`.
The agent-level dataset, one row per agent with every assigned value and its source, is `data/cohort.csv`.
