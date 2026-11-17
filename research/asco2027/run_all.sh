#!/usr/bin/env bash
# Reproduce every result from the frozen input snapshots. Needs Python 3.10+ (standard library only).
#   ./run_all.sh            use the snapshots in data/snapshot/ (exact reproduction)
#   ./run_all.sh --refresh  download today's data instead (numbers will differ)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data/raw/ncit results validation

if [[ "${1:-}" == "--refresh" ]]; then
  python3 scripts/fetch_ctgov.py
  curl -sSL -o data/raw/ncit/Thesaurus.FLAT.zip https://evs.nci.nih.gov/ftp1/NCI_Thesaurus/Thesaurus.FLAT.zip
  rm -f data/history_check.json          # the history lookups must be redone for a new download
else
  cat data/snapshot/ctgov_oncology_all_2026-11-17.jsonl.gz.part* | gunzip -c > data/raw/ctgov_oncology_all.jsonl
  cp data/snapshot/NCI_Thesaurus_FLAT_2026-11-17.zip data/raw/ncit/Thesaurus.FLAT.zip
fi
python3 -c "import zipfile; zipfile.ZipFile('data/raw/ncit/Thesaurus.FLAT.zip').extractall('data/raw/ncit')"

# data/originator_overrides.csv (out-licensed drugs -> Chinese originator) is committed; regenerate it with
# scripts/make_originator_overrides.py (needs PyYAML) only when the deal tracker changes.
python3 scripts/build_agents.py      # 1. agents and their first registered trial
python3 scripts/classify.py          # 2. first classification pass (creates the names to look up)
python3 scripts/history_check.py     # 3. pre-2020 trial history (uses the cached data/history_check.json if present)
python3 scripts/classify.py          # 4. final classification, applying the history exclusion
python3 scripts/analyse.py > /dev/null   # 5. results/summary.json and results/new_classes.csv
python3 scripts/make_validation_sample.py
python3 scripts/make_figures.py          # figures/*.svg
sha256sum data/cohort.csv results/summary.json results/new_classes.csv results/new_classes_review.csv figures/*.svg validation/validation_sample_150.csv
