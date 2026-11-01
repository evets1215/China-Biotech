"""Build a self-contained HTML dashboard (docs/index.html) from the YAML data.

The page is static: data is embedded as JSON, all filtering/sorting/charting
happens in the browser. The template shares its data layer (``templates/core.js``)
with the alternative designs in ``templates/designs/``. Serve ``docs/`` with GitHub Pages or just open the file.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from tracker import __version__
from tracker.store import ROOT, Database, read_yaml

TEMPLATE = Path(__file__).parent / "templates" / "dashboard.html"
CORE = Path(__file__).parent / "templates" / "core.js"
DEFAULT_OUT = ROOT / "docs" / "index.html"


def payload(db: Database) -> dict:
    return {
        "generated": dt.date.today().isoformat(),
        "version": __version__,
        "deals": db.deals,
        "pipeline": db.pipeline,
        "policy": read_yaml(db.data_dir / "policy.yaml"),
    }


def build(db: Database, out: Path | None = None) -> Path:
    out = Path(out) if out else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload(db), ensure_ascii=False, separators=(",", ":"))
    # Prevent "</script>" inside data from closing the script tag.
    data = data.replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__CORE__*/", CORE.read_text(encoding="utf-8"))
    html = html.replace("/*__DATA__*/null", data)
    out.write_text(html, encoding="utf-8")
    return out
