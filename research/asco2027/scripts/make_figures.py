"""Draw the figures as SVG from results/summary.json (standard library only).

Output: figures/fig1_volume_by_year.svg, fig2_drug_type_share.svg, fig3_first_to_clinic.svg, fig4_target_share.svg
Colour follows the entity in every figure: China = blue, US = orange, other countries = grey.
"""
import json
from pathlib import Path
from xml.sax.saxutils import escape

BASE = Path(__file__).resolve().parent.parent
O = json.loads((BASE / "results/summary.json").read_text())
OUT = BASE / "figures"
OUT.mkdir(exist_ok=True)

CN, US, OTH = "#2a78d6", "#eb6834", "#a8a69f"
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#77756f", "#e1e0d9", "#c3c2b7", "#fcfcfb"
FONT = 'system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif'
NOTE = "Source: ClinicalTrials.gov, retrieved 17 Nov 2026. Industry-sponsored agents. Preliminary; not independently validated."


class Svg:
    def __init__(self, w, h, title, subtitle):
        self.w, self.h, self.parts = w, h, []
        self.text(24, 34, title, size=18, weight=600, fill=INK)
        self.text(24, 56, subtitle, size=13, fill=INK2)

    def text(self, x, y, s, size=12, fill=INK2, anchor="start", weight=400):
        self.parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
                          f'font-weight="{weight}">{escape(str(s))}</text>')

    def line(self, x1, y1, x2, y2, stroke=GRID, width=1):
        self.parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{width}"/>')

    def raw(self, s):
        self.parts.append(s)

    def hbar(self, x0, y, length, h, fill, title, direction=1):
        """Horizontal bar from baseline x0; rounded 4px at the data end, square at the baseline."""
        if length <= 0:
            return
        r = min(4, length, h / 2)
        x1 = x0 + direction * length
        d = (f"M{x0:.1f},{y:.1f} H{x1 - direction * r:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} "
             f"V{y + h - r:.1f} Q{x1:.1f},{y + h:.1f} {x1 - direction * r:.1f},{y + h:.1f} H{x0:.1f} Z")
        self.parts.append(f'<path d="{d}" fill="{fill}"><title>{escape(title)}</title></path>')

    def legend(self, x, y, items):
        for label, colour in items:
            self.raw(f'<rect x="{x}" y="{y - 9}" width="10" height="10" rx="2" fill="{colour}"/>')
            self.text(x + 15, y, label, size=12, fill=INK2)
            x += 15 + 7.2 * len(label) + 18

    def save(self, name):
        self.text(24, self.h - 14, NOTE, size=10.5, fill=MUTED)
        body = "\n".join(self.parts)
        (OUT / name).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
            f'font-family=\'{FONT}\'>\n<rect width="100%" height="100%" fill="{SURFACE}"/>\n{body}\n</svg>\n', encoding="utf-8")
        print("wrote", name)


# ---------------------------------------------------------------- Figure 1: volume by year (two lines)
def fig1():
    years = sorted(O["new_agents_by_year"])
    cn = [O["new_agents_by_year"][y]["China"] for y in years]
    us = [O["new_agents_by_year"][y]["US"] for y in years]
    W, H, L, R, T, B = 760, 420, 60, 110, 96, 70
    s = Svg(W, H, "New investigational cancer agents entering trials, by sponsor country",
            f"Agents with a first registered trial in each year (n = {O['cohort_n']:,} in total; 2026 is January-September only)")
    s.legend(24, 80, [("China-based sponsors", CN), ("US-based sponsors", US)])
    ymax = 250
    X = lambda i: L + (W - L - R) * i / (len(years) - 1)
    Y = lambda v: T + (H - T - B) * (1 - v / ymax)
    for v in range(0, ymax + 1, 50):
        s.line(L, Y(v), W - R, Y(v), AXIS if v == 0 else GRID)
        s.text(L - 8, Y(v) + 4, v, size=11, fill=MUTED, anchor="end")
    for i, y in enumerate(years):
        s.text(X(i), H - B + 20, y + ("*" if y == "2026" else ""), size=11, fill=MUTED, anchor="middle")
    s.text(X(len(years) - 1), H - B + 36, "*Jan-Sep", size=10.5, fill=MUTED, anchor="middle")
    for vals, colour, name in ((us, US, "US"), (cn, CN, "China")):
        full = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals[:-1]))
        s.raw(f'<polyline points="{full}" fill="none" stroke="{colour}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        n = len(vals)   # partial final year: thinner connector, hollow marker
        s.raw(f'<line x1="{X(n-2):.1f}" y1="{Y(vals[-2]):.1f}" x2="{X(n-1):.1f}" y2="{Y(vals[-1]):.1f}" stroke="{colour}" stroke-width="2" stroke-opacity="0.45"/>')
        for i, v in enumerate(vals):
            last = i == n - 1
            s.raw(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="4.5" fill="{SURFACE if last else colour}" stroke="{colour if last else SURFACE}" '
                  f'stroke-width="2"><title>{name}, {years[i]}: {v} agents</title></circle>')
        s.text(X(n - 1) + 12, Y(vals[-1]) + 4, f"{name} {vals[-1]}", size=12, fill=INK, weight=600)
    # selective labels: first year and the last full year
    s.text(X(0) + 10, Y(us[0]) - 8, us[0], size=11, fill=INK2)
    s.text(X(0) + 10, Y(cn[0]) + 16, cn[0], size=11, fill=INK2)
    s.text(X(len(years) - 2), Y(cn[-2]) - 10, cn[-2], size=11, fill=INK2, anchor="middle")
    s.text(X(len(years) - 2), Y(us[-2]) + 20, us[-2], size=11, fill=INK2, anchor="middle")
    s.save("fig1_volume_by_year.svg")


# ---------------------------------------------------------------- shared: bars diverging from 50%
def diverging(name, title, subtitle, rows, label_w=250):
    """rows: (label, china_n, us_n). Bar runs from the 50% line towards the country with the majority."""
    row_h, T = 26, 112
    W, H = 760, T + row_h * len(rows) + 62
    s = Svg(W, H, title, subtitle)
    s.legend(24, 80, [("China-based sponsors ahead", CN), ("US-based sponsors ahead", US)])
    x_mid, half = label_w + (W - label_w - 70) / 2, (W - label_w - 70) / 2
    for pct in (0, 25, 50, 75, 100):
        x = x_mid + (pct - 50) / 50 * half
        s.line(x, T - 6, x, T + row_h * len(rows), AXIS if pct == 50 else GRID)
        lab = "even" if pct == 50 else (f"{100 - pct}% US" if pct < 50 else f"{pct}% China")
        s.text(x, T - 12, lab, size=10.5, fill=MUTED, anchor="middle")
    for i, (label, c, u) in enumerate(rows):
        share = 100 * c / (c + u)
        y = T + i * row_h + 5
        s.text(label_w - 12, y + 12, label, size=12, fill=INK2, anchor="end")
        length = abs(share - 50) / 50 * half
        direction = 1 if share >= 50 else -1
        tip = f"{label}: China {c}, US {u} ({share:.0f}% China)"
        s.hbar(x_mid, y, max(length, 1.5), 16, CN if share >= 50 else US, tip, direction)
        txt = "even" if c == u else (f"{share:.0f}% China" if share >= 50 else f"{100 - share:.0f}% US")
        tx = x_mid + direction * (length + 6)
        s.text(tx, y + 12, txt, size=11.5, fill=INK, anchor="start" if direction > 0 else "end", weight=600)
        s.text(W - 24, y + 12, f"n = {c + u}", size=10.5, fill=MUTED, anchor="end")
    s.save(name)


def fig2():
    skip = {"Unclassified", "In vivo CAR"}
    rows = [(m, v["China"], v["US"]) for m, v in O["by_modality"].items() if m not in skip]
    rows.sort(key=lambda r: -r[1] / (r[1] + r[2]))
    un = O["by_modality"]["Unclassified"]
    diverging("fig2_drug_type_share.svg", "Where each country leads, by drug type",
              f"Share of China-plus-US agents, 2020-Sep 2026 (excludes {un['China'] + un['US']} agents with no identifiable drug type)", rows)


def fig4():
    rows = [(t, c, u) for t, c, u, _ in O["target_china_share"] if c + u >= 15 and "unspecified" not in t]
    rows.sort(key=lambda r: -r[1] / (r[1] + r[2]))
    cov = O["coverage"]
    diverging("fig4_target_share.svg", "Where each country leads, by molecular target",
              f"Targets with 15 or more China-plus-US agents. A target was identified for "
              f"{cov['China']['target_identified_pct']:.0f}% of China and {cov['US']['target_identified_pct']:.0f}% of US agents.",
              rows, label_w=170)


# ---------------------------------------------------------------- Figure 3: first-to-clinic (two panels of grouped bars)
def fig3():
    P = O["new_classes_primary_target_set"]
    nov, per = P["by_novelty"], P["by_period"]
    groups_a = [("Undrugged target", nov["new target"]), ("New target pair", nov["new target pair"])]
    groups_b = [("2020-2022", per["2020-2022"]), ("2023-2026*", per["2023-2026"])]
    W, H, T = 760, 430, 126
    s = Svg(W, H, "Which country was first into trials with a new target class",
            f"{P['n']} target classes (one target or a pair) with no registered trial before 2020, by country of the first industry sponsor")
    s.legend(24, 80, [("China", CN), ("US", US), ("Other countries", OTH)])
    ymax, base = 70, H - 86

    def panel(x0, width, heading, groups):
        s.text(x0, T - 16, heading, size=12.5, fill=INK, weight=600)
        Y = lambda v: base - (base - T) * v / ymax
        for v in range(0, ymax + 1, 10):
            if v % 20 == 0:
                s.line(x0, Y(v), x0 + width, Y(v), AXIS if v == 0 else GRID)
                s.text(x0 - 6, Y(v) + 4, v, size=10.5, fill=MUTED, anchor="end")
        gw = width / len(groups)
        for gi, (label, d) in enumerate(groups):
            cx = x0 + gw * gi + gw / 2
            for bi, (key, colour) in enumerate((("China", CN), ("US", US), ("Other", OTH))):
                v = d[key]
                x = cx + (bi - 1.5) * 26 + 1
                h = base - Y(v)
                r = min(4, h)
                if v:
                    s.raw(f'<path d="M{x:.1f},{base:.1f} V{Y(v) + r:.1f} Q{x:.1f},{Y(v):.1f} {x + r:.1f},{Y(v):.1f} H{x + 24 - r:.1f} '
                          f'Q{x + 24:.1f},{Y(v):.1f} {x + 24:.1f},{Y(v) + r:.1f} V{base:.1f} Z" fill="{colour}">'
                          f'<title>{label}, {key}: {v}</title></path>')
                s.text(x + 12, Y(v) - 5, v, size=11.5, fill=INK, anchor="middle", weight=600)
            s.text(cx, base + 18, label, size=11.5, fill=INK2, anchor="middle")
            sh = d["china_share_of_cn_us"]
            s.text(cx, base + 34, f"China share: {sh:.0f}%", size=10.5, fill=MUTED, anchor="middle")

    panel(56, 310, "By kind of novelty", groups_a)
    panel(430, 300, "By period", groups_b)
    s.text(430, base + 52, "*to September 2026. China share = China / (China + US).", size=10.5, fill=MUTED)
    s.text(56, base + 52, "Undrugged = no agent on that target before 2020.", size=10.5, fill=MUTED)
    s.save("fig3_first_to_clinic.svg")


fig1(), fig2(), fig3(), fig4()
