"""Run with:  python -m unittest discover -s tests"""

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tracker import cli, stats, sync_biopharmadive
from tracker.store import DATA_DIR, Database, norm_name, validate

SAMPLE_CSV = """Licensee,Licensor,Date of deal,Upfront value* (millions),Upfront equity (% or $),Total deal value** (millions),Therapeutic area,Modality,**INTERNAL** W/Biologics detail,Treatment type (lead),Phase of development,Link to coverage,Year
Acme Pharma,Example Biotech Co.,10/30/26,"1,250.00",,"6,000.00",Cancer,Biologics,Biologics,PD-1 x VEGF bispecific,Phase 2,https://example.com/a,2026
Roche,Rona Therapeutics,10/14/26,100.00,,"1,160.00",Metabolic diseases,Nucleic acid,Nucleic acid,RNAi drug targeting ALK7,Undisclosed,,2026
NewCo Bio,Sample Pharma,9/1/26,N/A,15%,N/A,"Cancer, Immune diseases",Undisclosed,,Undisclosed,Undisclosed,,2026
"""


class TempDataTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for name in ("deals.yaml", "pipeline.yaml", "companies.yaml", "policy.yaml"):
            shutil.copy(DATA_DIR / name, self.tmp / name)
        self.db = Database.load(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.main(["--data-dir", str(self.tmp), *args])
        return rc, buf.getvalue()


class TestShippedData(unittest.TestCase):
    def test_repository_data_is_valid(self):
        db = Database.load()
        self.assertEqual(validate(db), [])
        self.assertGreater(len(db.deals), 100)

    def test_ids_unique(self):
        db = Database.load()
        ids = [d["id"] for d in db.deals] + [p["id"] for p in db.pipeline]
        self.assertEqual(len(ids), len(set(ids)))


class TestValidation(TempDataTest):
    def test_bad_status_and_money(self):
        self.db.deals.append({"id": "X-1", "announced": "2026-01-01", "licensor": "A", "licensee": "B",
                              "deal_type": "License", "status": "maybe", "upfront_usd_m": "lots"})
        errs = validate(self.db)
        self.assertTrue(any("status 'maybe'" in e for e in errs))
        self.assertTrue(any("upfront_usd_m" in e for e in errs))

    def test_terminated_needs_date(self):
        self.db.deals.append({"id": "X-2", "announced": "2026-01-01", "licensor": "A", "licensee": "B",
                              "deal_type": "License", "status": "terminated"})
        self.assertTrue(any("status_date" in e for e in validate(self.db)))

    def test_format_is_optional_but_checked(self):
        self.db.deals.append({"id": "X-3", "announced": "2026-01-01", "licensor": "A", "licensee": "B",
                              "deal_type": "License", "status": "active"})
        self.assertEqual(validate(self.db), [])
        self.db.deals[-1]["format"] = "Antibody thing"
        self.assertTrue(any("format 'Antibody thing'" in e for e in validate(self.db)))


class TestCli(TempDataTest):
    def test_add_update_terminate(self):
        rc, out = self.run_cli("add", "--announced", "2026-10-30", "--licensor", "Test Bio", "--licensee", "Pfizer",
                               "--asset", "TB-001", "--upfront", "50", "--total", "500", "--area", "Cancer")
        self.assertEqual(rc, 0, out)
        db = Database.load(self.tmp)
        new = next(d for d in db.deals if d.get("asset") == "TB-001")
        self.assertEqual(new["licensee_hq"], "US")  # filled from companies.yaml
        rc, out = self.run_cli("update", new["id"], "--status", "terminated", "--date", "2026-10-31", "--note", "Rights returned")
        self.assertEqual(rc, 0, out)
        d = Database.load(self.tmp).deal(new["id"])
        self.assertEqual(d["status"], "terminated")
        self.assertEqual(d["events"][-1]["date"], "2026-10-31")

    def test_pipeline_add_signal_promote(self):
        rc, out = self.run_cli("pipeline-add", "--stage", "potential", "--company", "Test Bio", "--asset", "TB-002",
                               "--rationale", "Reported talks", "--signal", "Bloomberg reports talks", "--date", "2026-10-01")
        self.assertEqual(rc, 0, out)
        pid = next(p["id"] for p in Database.load(self.tmp).pipeline if p["asset"] == "TB-002")
        self.assertTrue(pid.startswith("POT-"))
        self.assertEqual(self.run_cli("signal", pid, "--note", "Term sheet signed")[0], 0)
        rc, out = self.run_cli("promote", pid, "--announced", "2026-10-31", "--licensee", "Merck & Co.", "--upfront", "100")
        self.assertEqual(rc, 0, out)
        db = Database.load(self.tmp)
        self.assertIsNone(db.pipeline_item(pid))
        deal = next(d for d in db.deals if d.get("asset") == "TB-002")
        self.assertEqual(len(deal["events"]), 2)

    def test_list_stats_export_build(self):
        rc, out = self.run_cli("list", "--licensee", "Pfizer", "--limit", "3")
        self.assertEqual(rc, 0)
        self.assertIn("Pfizer", out)
        for by in ("year", "licensee", "area", "status"):
            self.assertEqual(self.run_cli("stats", "--by", by)[0], 0)
        self.assertEqual(self.run_cli("export", "--format", "csv", "--out", str(self.tmp / "out"))[0], 0)
        self.assertTrue((self.tmp / "out" / "deals.csv").exists())
        self.assertEqual(self.run_cli("build", "--out", str(self.tmp / "index.html"))[0], 0)
        html = (self.tmp / "index.html").read_text()
        self.assertNotIn("/*__DATA__*/null", html)
        self.assertNotIn("</script><", html.split('id="data"')[1].split("</script>")[0])


class TestSync(TempDataTest):
    def test_parse_and_merge(self):
        rows = sync_biopharmadive.parse_rows(SAMPLE_CSV)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["upfront_usd_m"], 1250)
        self.assertEqual(rows[0]["announced"], "2026-10-30")
        self.assertEqual(rows[2]["therapeutic_area"], "Multiple")
        self.assertIsNone(rows[2]["upfront_usd_m"])
        before = len(self.db.deals)
        added, _ = sync_biopharmadive.merge(self.db, rows)
        # Rona/Roche (one day off) is already tracked, so only two are new.
        self.assertEqual(len(added), 2)
        self.assertEqual(len(self.db.deals), before + 2)
        self.assertEqual(validate(self.db), [])
        added_again, _ = sync_biopharmadive.merge(self.db, sync_biopharmadive.parse_rows(SAMPLE_CSV))
        self.assertEqual(added_again, [])


class TestHelpers(unittest.TestCase):
    def test_norm_name(self):
        self.assertEqual(norm_name("Jiangsu Hengrui Pharmaceuticals Co., Ltd."), norm_name("Hengrui Pharma"))

    def test_stats(self):
        db = Database.load()
        s = stats.summary(db)
        self.assertEqual(s["deals"], len(db.deals))
        self.assertEqual(sum(r["deals"] for r in stats.by_year(db)), len(db.deals))


if __name__ == "__main__":
    unittest.main()
