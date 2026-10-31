# China → US biotech out-licensing tracker

A version-controlled system for tracking every deal in which a **China-based biotech/pharma
out-licenses rights that include the United States**. It covers:

| Bucket | What it is | Where it lives |
|---|---|---|
| **Past & active deals** | Signed licences, options, collaborations, NewCos and acquisitions, with status (`active`, `pending`, `completed`, `terminated`) and history | `data/deals.yaml` |
| **Potential deals** | Open options a licensee can still exercise (derived automatically from deals), plus reported talks / NewCos in formation | `data/pipeline.yaml` (`stage: potential`) |
| **Future deals** | Watchlist of Chinese assets with ex-China rights that look unpartnered, with a likelihood rating and rationale | `data/pipeline.yaml` (`stage: future`) |
| **Policy watch** | US/China rules that change how deals can be structured | `data/policy.yaml` |
| **Inbox** | Weekly auto-scan of news headlines that may be new deals, rumours or terminations | `data/inbox.md` |

Everything is plain YAML, so changes are reviewed in pull requests and the full history is in git.

## What's in it today (as of 2026-10-31)

* **162 signed deals** (2011 → Oct 2026): 151 active, 8 terminated, 3 completed acquisitions.
  * 2025–2026 coverage is comprehensive. It is imported from [BioPharma Dive's China licensing tracker](https://www.biopharmadive.com/news/china-biotech-drug-licensing-deals-pipeline/758283/)
    and cross-checked against [Vision Lifesciences' 2026 tracker](https://visionlifesciences.com/insights/china-biotech-outbound-licensing-tracker).
  * 2011–2024 coverage is **landmark deals only**. These were curated from company announcements and include the terminations
    (Novartis/BeiGene, AbbVie/I-Mab, EQRx, Biogen/InnoCare…), so the record shows deals that failed as well as those that worked.
* **3 open options** (Takeda/Ascentage, AbbVie/Simcere, AbbVie/Zelgen) and a **10-asset future watchlist**.
* Disclosed upfronts of about $25B; headline "up to" value of about $331B.

> Figures are as announced. Headline totals include milestones and are not risk-adjusted. Different
> trackers count deals differently. The curated pre-2025 records and the watchlist should be spot-checked
> against primary sources before you use them in anything formal.

## Dashboard

`docs/index.html` is a self-contained page (no server, no external scripts). It has filters, KPIs,
charts by year, area and licensee, a sortable deal table with expandable details, and tabs for
potential deals, the watchlist, status changes and policy.

* **Locally:** open `docs/index.html` in a browser.
* **Online:** in GitHub, go to *Settings → Pages* and deploy from branch `main`, folder `/docs`.

Rebuild it after any data change with `python -m tracker build`.

## Quick start

```bash
pip install -r requirements.txt
```

```bash
python -m tracker stats                      # headline numbers, by year
```

```bash
python -m tracker list --since 2026-01-01 --sort upfront --limit 20
```

```bash
python -m tracker list --licensee Merck --status active
```

```bash
python -m tracker pipeline                   # potential + future deals and open options
```

```bash
python -m tracker show CN-2025-034           # full record for one deal
```

```bash
python -m tracker export --format xlsx       # exports/china_biotech_deals.xlsx (also csv, json)
```

## Keeping it current

**1. New signed deal**

```bash
python -m tracker add --announced 2026-11-03 --licensor "Akeso" --licensee "Pfizer" \
  --asset "AK104" --target "PD-1 x CTLA-4" --area Cancer --deal-type License \
  --upfront 300 --total 2500 --territory "Ex-China" --source https://example.com/press-release
```

**2. Status change (termination, option exercised, acquisition closed)**

```bash
python -m tracker update CN-2024-004 --status terminated --date 2026-11-15 \
  --note "Takeda declined option" --source https://example.com/pr
```

**3. Upcoming catalysts and events** (these show in the dashboard's *Status changes & catalysts* tab)

```bash
python -m tracker update CN-2022-002 --catalyst "2027-03-31|Phase 3 topline readout"
```

```bash
python -m tracker catalysts --days 180
```

**4. Rumoured / potential deal → signed deal**

```bash
python -m tracker pipeline-add --stage potential --company "Hengrui Pharma" --asset "SHR-A1811" \
  --rationale "Bloomberg reports talks with two big pharmas" --signal "Talks reported" --source https://example.com
```

```bash
python -m tracker signal POT-001 --note "Exclusivity agreed" --likelihood high
```

```bash
python -m tracker promote POT-001 --announced 2026-12-01 --licensee "AstraZeneca" --upfront 250 --total 1800
```

Promoting keeps the pre-deal signals in the new deal's history.

**5. Automatic weekly refresh.** `.github/workflows/weekly-update.yml` runs every Monday. It:
1. runs `tracker sync` to pull new deals from BioPharma Dive's public tracker. Sync only adds new deals or fills
   blank fields; it never overwrites your edits.
2. runs `tracker scan-news` over Google News, BioPharma Dive, Fierce Biotech, Endpoints and STAT, and writes candidate
   headlines (new deals, "in talks" rumours, terminations) to `data/inbox.md`.
3. rebuilds the dashboard and **opens a pull request** for review.

For the PR step, enable *Settings → Actions → General → "Allow GitHub Actions to create and approve pull requests"*.
You can also trigger it by hand from the Actions tab (*Run workflow*).

## Data model

Signed deal (`data/deals.yaml`):

| Field | Notes |
|---|---|
| `id` | `CN-<year>-<nnn>`, assigned automatically |
| `announced` | `YYYY-MM-DD` (or `YYYY-MM` when only the month is known) |
| `licensor`, `licensor_hq` | Chinese company granting rights |
| `licensee`, `licensee_hq`, `licensee_type` | Big Pharma / Mid-size Pharma / Biotech / NewCo |
| `deal_type` | License, Option, Collaboration, NewCo, Acquisition, Platform |
| `asset`, `target`, `modality`, `therapeutic_area`, `indication`, `phase_at_deal` | What was licensed |
| `territory` | e.g. Ex-Greater China, Global, US & Canada |
| `upfront_usd_m`, `equity_usd_m`, `milestones_usd_m`, `total_value_usd_m`, `royalties` | Economics in US$ millions |
| `status`, `status_date`, `status_note` | active / pending / completed / terminated |
| `development_status` | e.g. "Marketed in US (FDA approval Nov 2023)" |
| `events`, `catalysts` | Lists of `{date, event}`: past history and upcoming dates |
| `sources`, `data_source`, `notes`, `last_verified` | Provenance |

Pipeline item (`data/pipeline.yaml`): `id` (`POT-nnn` / `FUT-nnn`), `stage`, `company`, `asset`, `target`,
`modality`, `therapeutic_area`, `phase`, `ex_china_rights`, `likelihood` (high/medium/low), `potential_partners`,
`rationale`, `signals` (`{date, note, source}`), `catalysts`.

`data/companies.yaml` maps company names to HQ country and type. It is used to fill in licensee details and to
recognise Chinese companies in headlines. Add new names there as they appear.

Run `python -m tracker validate` after hand edits. CI runs validation, the unit tests
(`python -m unittest discover -s tests`) and a dashboard build on every push.

## Project layout

```
data/            deals.yaml, pipeline.yaml, companies.yaml, policy.yaml, inbox.md
docs/index.html  generated dashboard
tracker/         CLI (cli.py), storage + validation (store.py), stats, dashboard builder,
                 BioPharma Dive sync, news scanner
tests/           unit tests
.github/         CI + weekly update workflow
```
