# Accuracy audit, 17 Nov 2026

Scope: the numbers in `abstract_draft.md` as of commit "Add detailed methods and a reproducible one-command pipeline".

## Verdict

| Result | Arithmetic reproduces? | Underlying data reliable? | Use in an abstract? |
|---|---|---|---|
| Cohort size and China/US volume by year | Yes | Partly. Counts are of registered agent names; known gaps below | Only with stated caveats |
| Drug type shares | Yes | Partly. 16% of agents have no drug type, more in China (24%) than the US (9%); some mislabels seen | Only with stated caveats |
| Target counts, breadth, per-target shares | Yes | **No** | **No** |
| New classes, "leader", novelty type, follower lag | Yes | **No** | **No** |

## What was checked

1. **Arithmetic.** Every abstract number was recomputed from `data/cohort.csv` with separate code. All matched.
2. **All 366 "new classes"** were read one by one against general knowledge of the drugs.
3. **Known older drugs** were looked up to see how the pipeline had handled them.
4. **30 random cohort agents** whose target came from trial text were compared with that text.

Checks 2-4 were done by the same author who built the pipeline, without external sources. They can show that errors
exist; they cannot give a certified error rate.

## Findings

### A. The trial download misses first-in-human trials (affects everything)
The query keeps trials whose **current** phase label is phase 1 or 1/2. Sponsors update that label as a trial grows.
Example: Pfizer's first-in-human trial of PF-07248144 (NCT04606446, started Nov 2020) is now labelled phase 2, so the
drug is absent from the dataset. Effects: missing agents, later apparent start dates, and gaps in the 2010-2019
history that make old classes look new.

### B. Target extraction errors
- **Trial-text targets are wrong about half the time.** In the sample of 30, about 14 were fully correct. Typical
  errors: a combination partner's target ("in combination with a PARP inhibitor"), a patient-selection marker
  ("HR+/HER2- breast cancer"), or part of a longer list.
- **This tier is used far more for China.** 159 of 605 China agents with a target (26%) rely on trial text, versus
  62 of 685 US agents (9%).
- **A lexicon bug adds EGFR to HER3 drugs.** "human epidermal growth factor receptor 3" matches the EGFR pattern, so
  patritumab deruxtecan is coded "EGFR | HER3".
- **Targets named in the second sentence of the NCI definition are missed** (e.g. vadastuximab talirine has no CD33).
- **Wrong assignments on well-known drugs:** iberdomide coded as a CD20 cell therapy; mezigdomide as a BCMA antibody;
  lutetium dotatate and ART4215 given PARP1.

### C. "New class" errors (at least 70 of 366 visibly wrong; the true number is higher)
- **False novelty.** Classes flagged as new that plainly existed before 2020: CD33 antibody-drug conjugates
  (2013), HER3 antibody-drug conjugates (2016), IKZF1/3 degraders (2016), ROS1 inhibitors, SSTR2 radioligands,
  MAT2A inhibitors (2018), CDK2/4/6 inhibitors (2018).
- **Same idea split across drug-type labels.** A PD-1/VEGF agent labelled "monoclonal antibody" counts as a new
  class although PD-1/VEGF bispecifics already existed; "cytokine" and "bispecific" versions of IL-15/PD-1 count twice.
- **Single-target bispecifics** usually mean the second target is not in the lexicon, not that the class is new.
- **Wrong drug type or target on the first agent** (e.g. a small-molecule BCL-2 inhibitor labelled as an antibody).

### D. Sponsor country errors
- **The registry shows the current owner.** After an acquisition the sponsor name on old trials changes, so a drug
  can be credited to the acquirer's country (FS120, originated in the UK, is credited to China; KSQ's USP1 inhibitor
  is credited to Roche).
- **Individual misassignments** seen: BerGenBio (Norway) coded US; Evopoint (China) coded Other.

### E. Agent identity errors
- **Renamed drugs count as new.** Afamitresgene autoleucel (first trial 2017 as "MAGE-A4c1032T") appears as a
  2023 agent.
- **One excluded trial can remove a drug.** AZD9592 was dropped because one of its trials was a microdosing study.
- **A few imaging tracers and non-drugs remain** (e.g. a carbon-11 PARP tracer; an agent named "VEGF-A").

## What is needed before any target- or class-level number is reported
1. Re-download **all phases** of interventional cancer drug trials since 2010 and take each agent's first trial of any phase.
2. Fix the bugs in B and E; use the full NCI definition for targets; reject targets from partner-drug phrases.
3. Define classes by target set alone, with drug type as a secondary label, to stop label-splitting.
4. Have the list of new classes (a few hundred rows) checked by a person against company sources, and report the
   validation agreement for the whole cohort.
5. Or replace steps 1-3 with a licensed pipeline database (Citeline, Cortellis, GlobalData, PharmCube), which
   curates target and drug type by hand.

---

# Version 2 rebuild (same day)

## What changed
| Audit finding | Change in version 2 |
|---|---|
| A. First-in-human trials missed | All interventional cancer drug trials are downloaded, with no phase or date filter (72,031 trials, up from 21,945). The cohort takes each agent's first trial of any phase, and requires it to be phase 1 or 2 |
| B. Partner-drug and patient-selection targets | Trial text is cut into clauses and only clauses naming the agent are used |
| B. EGFR added to HER3 drugs; PD-1 added to VISTA drugs | Lexicon patterns corrected |
| B. Targets in the second sentence of the NCI definition missed | Second sentence is used when the first names no target, if the drug is said to act on the target |
| C. Same idea split across drug-type labels | Primary class is now the target set alone; the old definition is kept as a secondary analysis |
| C. Cereblon modulators mislabelled | Added to the protein degrader rule |
| E. One excluded trial removes a drug | Non-therapeutic trials are dropped before agents are built, so the drug is kept |
| E. Imaging tracers and target-only names | Carbon-11 added; names that are only a target are dropped |
| D. Individual country errors seen | Corrected in the sponsor lists |

## Re-test of the drugs that exposed the problems
Now correct: patritumab deruxtecan (HER3 only), vadastuximab talirine (CD33), AZD9592 (present; EGFR + c-MET),
iberdomide (degrader), ART4215 (Pol theta), PF-07248144 (present, 2020, KAT6), afamitresgene autoleucel (now dated
2019), lutetium dotatate (SSTR2, 2004), surzetoclax and XNW5004 (small molecules; Evopoint coded China).

Still wrong or incomplete: TQB3602 (a proteasome inhibitor coded PD-1), gecacitinib (drug type), PF-06873600 and
CC-90009 (no target, because their NCI definitions do not name one), FS120 and KSQ-4279 (credited to the current
owner's country).

## Effect on results
| Result | Version 1 | Version 2 |
|---|---|---|
| Cohort | 2,859 | 2,969 |
| China / US agents | 1,145 / 1,009 | 1,180 / 1,054 |
| New classes (primary definition) | 366 | 182 |
| First: US / China / other | 164 / 98 / 104 | 88 / 49 / 44 (1 tie) |
| China share of China-plus-US firsts, 2020-22 to 2023-26 | 32% to 43% | 29% to 42% |
| Previously undrugged targets, US vs China | 37 vs 12 | 23 vs 4 |
| New target pairs, US vs China | 67 vs 60 | 62 vs 45 |

The direction of every finding is unchanged; the counts of "firsts" halved because classes are no longer split by
drug type and the pre-2020 history is fuller.

## Author's re-check of the 182 new classes
Read one by one, as before. About 12 are doubtful and are flagged in the `author_flag` column of
`results/new_classes_review.csv`. This is again the author's own reading, not independent validation, and it can
only catch drugs the author recognises.

## Still required
1. A person checks `results/new_classes_review.csv` (182 rows) against company sources.
2. A person codes `validation/validation_sample_150.csv`.
3. China's registry is merged when the export is available.
