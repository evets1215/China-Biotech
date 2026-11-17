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
