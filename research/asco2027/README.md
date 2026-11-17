# ASCO 2027 abstract: where China leads and where the US leads in new cancer drugs

**Status: version 2 (17 Nov 2026).** Version 1 failed an accuracy audit ([`AUDIT.md`](AUDIT.md)). The pipeline was
rebuilt on all-phase trial data with corrected target rules. Version 2 has had the author's own re-check but no
independent validation. Before any number is submitted, a person must (1) code `validation/validation_sample_150.csv`
and (2) check `results/new_classes_review.csv`.

**Full methods and how to reproduce every number: [`METHODS.md`](METHODS.md). One command: `./run_all.sh`.**

## Question
For cancer drugs entering human trials in 2020-2026, which targets and drug types are led by China-based
sponsors and which by US-based sponsors?

## Files
| File | What it is |
|---|---|
| `METHODS.md` | Every rule and definition, and how to reproduce the results |
| `AUDIT.md` | What the accuracy audit found in version 1 and what version 2 changed |
| `abstract_draft.md` | Draft abstract with current numbers |
| `run_all.sh` | Regenerates everything from the frozen inputs in `data/snapshot/` |
| `data/cohort.csv` | One row per agent with country, drug type, targets and their sources |
| `results/summary.json` | All reported numbers |
| `results/new_classes.csv` | New target classes with first agent, sponsor and trial |
| `results/new_classes_review.csv` | The same list as a checking sheet for a human reviewer |
| `validation/validation_sample_150.csv` | Random sample of agents for manual coding |

