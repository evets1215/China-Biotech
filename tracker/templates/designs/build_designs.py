"""Build the alternative designs in docs/designs/ from the data already embedded in docs/index.html.

The live dashboard (tracker/templates/dashboard.html) is built by ``python -m tracker build``;
these are the two other directions, kept for comparison.

Standard library only, so it runs without the tracker's dependencies:

    python3 tracker/templates/designs/build_designs.py
"""

from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
SOURCE = ROOT / "docs" / "index.html"
OUT = ROOT / "docs" / "designs"
DESIGNS = ["terminal", "pipeline"]


def main() -> None:
    match = re.search(r'<script id="data" type="application/json">(.*?)</script>', SOURCE.read_text(encoding="utf-8"), re.S)
    if not match:
        raise SystemExit(f"No embedded data found in {SOURCE}")
    data = match.group(1)
    core = (HERE.parent / "core.js").read_text(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    for name in DESIGNS:
        template = HERE / f"{name}.html"
        if not template.exists():
            continue
        html = template.read_text(encoding="utf-8")
        html = html.replace("/*__DATA__*/null", data).replace("/*__CORE__*/", core)
        (OUT / f"{name}.html").write_text(html, encoding="utf-8")
        print(f"wrote {OUT / (name + '.html')}")


if __name__ == "__main__":
    main()
